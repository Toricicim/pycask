"""Concurrent HTTP load test with full read-back verification."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import statistics
import time
import uuid

import requests


def run_load_test(base_url, records, workers, timeout):
    if records < 1 or workers < 1 or timeout <= 0:
        raise ValueError("records, workers and timeout must be positive")
    base_url = base_url.rstrip("/")
    # Avoid overwriting an earlier run's keys or accidentally verifying stale data.
    prefix = "loadtest:" + uuid.uuid4().hex
    payloads = [
        (f"{prefix}:{i}", json.dumps({"id": i, "name": f"User_{i}"}))
        for i in range(records)
    ]

    def write(item):
        key, value = item
        start = time.perf_counter()
        try:
            response = requests.put(f"{base_url}/keys/{key}", json={"value": value}, timeout=timeout)
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError(f"Unexpected write status: {response.status_code}")
            return item, time.perf_counter() - start, None
        except (requests.RequestException, ValueError) as exc:
            return item, time.perf_counter() - start, str(exc)

    def verify(item):
        key, expected = item
        try:
            response = requests.get(f"{base_url}/keys/{key}", timeout=timeout)
            response.raise_for_status()
            if response.json() != {"key": key, "value": expected}:
                return f"Value mismatch for {key}"
        except (requests.RequestException, ValueError) as exc:
            return str(exc)
        return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        start = time.perf_counter()
        results = list(pool.map(write, payloads))
        elapsed = time.perf_counter() - start
        successful = [(item, latency) for item, latency, error in results if error is None]
        verification_errors = list(pool.map(verify, [item for item, _ in successful]))

    latencies = sorted(latency * 1000 for _, latency in successful)
    write_errors = [error for _, _, error in results if error is not None]
    failed_reads = [error for error in verification_errors if error is not None]
    return {
        "attempted": records,
        "workers": workers,
        "successful_writes": len(successful),
        "failed_writes": len(write_errors),
        "verified_reads": len(successful) - len(failed_reads),
        "failed_verifications": len(failed_reads),
        "write_seconds": elapsed,
        "successful_writes_per_second": len(successful) / elapsed,
        "write_latency_median_ms": statistics.median(latencies) if latencies else None,
        "write_latency_p95_ms": latencies[max(0, (95 * len(latencies) + 99) // 100 - 1)] if latencies else None,
        "sample_errors": (write_errors + failed_reads)[:5],
        "key_prefix": prefix,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--records", type=int, default=1000)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=10)
    args = parser.parse_args()
    if args.records < 1 or args.workers < 1 or args.timeout <= 0:
        parser.error("records, workers and timeout must be positive")
    result = run_load_test(args.base_url, args.records, args.workers, args.timeout)
    print(json.dumps(result, indent=2))
    return 1 if result["failed_writes"] or result["failed_verifications"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
