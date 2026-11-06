# PyCask: RESTful Bitcask Key-Value Store

PyCask is a learning project implementing a persistent key-value store in Python, with a FastAPI REST API. It uses append-only binary records and an in-memory index of the latest byte offset for each live key.

## Implemented features

- **Append-only binary storage:** PUT and DELETE records are appended to disk; updates do not overwrite earlier records.
- **Index rebuilding:** Startup replays the log to reconstruct the index, keeping the latest value and applying deletions.
- **Explicit deletion records:** A record's operation field distinguishes deletion from user data. Every string, including `__DELETED__` and the empty string, can be stored as a value.
- **Compaction:** Copies only live values into a temporary file, flushes and syncs that file, then replaces the original with `os.replace`. The file handle and index change together under the lock. A failed replacement leaves the original usable.
- **Thread safety within one DB instance:** Reads, writes, deletes and compaction share a reentrant lock so a read cannot use offsets from a different file generation. Operations are serialized.
- **REST endpoints:** CRUD operations and manual compaction.
- **Concurrent load-test client:** A configurable thread pool sends overlapping HTTP requests, reports successful and failed writes separately, and reads back every successful write to verify the exact value.

Index lookup has expected O(1) cost; retrieving a value also reads and decodes its bytes from disk. Values are not cached in memory.

## Installation and use

Use Python 3.11 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 127.0.0.1 --port 8000
```

The default database is `database.data` in the working directory. Set `PYCASK_DATA_FILE` to choose another file:

```bash
PYCASK_DATA_FILE=/tmp/demo.data uvicorn main:app --host 127.0.0.1 --port 8000
```

Run a **single server process**. Multiple workers or multiple DB instances sharing a file are unsupported: the lock and index are in memory. Database handles are opened during API startup and closed during shutdown.

Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

## API reference

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/` | Health and live key count |
| PUT | `/keys/{key}` | Create or update a string value |
| GET | `/keys/{key}` | Read a value; 404 when absent |
| DELETE | `/keys/{key}` | Append a deletion record; 204 with an empty body, or 404 |
| POST | `/compact` | Rewrite the file with only current live values |

```bash
curl -X PUT http://127.0.0.1:8000/keys/my_key \
  -H 'Content-Type: application/json' \
  -d '{"value": "__DELETED__"}'

curl http://127.0.0.1:8000/keys/my_key
curl -X POST http://127.0.0.1:8000/compact
curl -X DELETE http://127.0.0.1:8000/keys/my_key
```

## Storage format and recovery

Version 2 starts with the eight-byte marker `b"PyCask\x02\n"`. Each record has a little-endian `<BII` header: operation (1 = PUT, 2 = DELETE), UTF-8 key byte length, and UTF-8 value byte length. DELETE records have no value bytes.

Startup checks record framing and rebuilds the index. An incomplete final header or payload is discarded with a warning, allowing later appends to remain readable. Invalid operation fields and invalid UTF-8 are rejected. There are no checksums, so this does not detect every kind of corruption; corrupted lengths can also resemble an interrupted final append.

A complete legacy file using native `struct.pack("II", ...)` records is automatically converted on first open. The original bytes are retained in `<database path>.v1.bak`, which is never overwritten. An incomplete legacy file is rejected without replacing it. Legacy files should be migrated on the platform that wrote them because their byte order is platform dependent.

**Legacy ambiguity:** The original format used the literal value `__DELETED__` for tombstones. It cannot distinguish an intentional deletion from that string stored as normal data. Migration preserves the old restart behavior, treating those legacy records as deletions; it cannot recover the original intent. New version 2 writes do not have this ambiguity.

Writes flush Python's buffer before returning, but do not call `fsync` on each request. Compaction syncs the replacement file, but does not sync the containing directory. This project does **not** guarantee durability through a power loss. It also has no transactions, authentication, replication or multi-process coordination.

## Concurrent load testing

With the server running:

```bash
python load_test.py --records 1000 --workers 8 --timeout 10
```

Use `--base-url` to choose a different server. The JSON report includes attempted, successful and failed writes; verified reads and mismatches; write-phase duration; successful writes per second; median and p95 HTTP write latency. It exits with a nonzero status on write or verification failures.

Each run uses a unique key prefix and leaves its records in the database. Use a separate test database for benchmarks. Throughput includes HTTP and client overhead, and depends on the environment; no production throughput claim is made.

## Verification

```bash
python -m unittest discover -s tests -v
```

The tests cover literal tombstone strings, empty and Unicode values, persistence across reopening, deletion, space reclamation, writes after compaction, replacement failure, partial tails, legacy migration, concurrent access during compaction, dictionary-model comparisons, actual REST requests, load-client concurrency and failure reporting.
