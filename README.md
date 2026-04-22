# PyCask: RESTful Bitcask Key-Value Store

PyCask is a persistent, disk-based Key-Value database engine written from scratch in pure Python, wrapped in a high-performance asynchronous REST API using FastAPI. 

It is built upon the foundational principles of the Bitcask architecture (Log-Structured Hash Table), offering an append-only disk storage mechanism combined with an in-memory Hash Index for **O(1) read performance**.

## Features

- **Persistence:** Uses an append-only file format. Data remains safe and persistent across server restarts.
- **High Read Performance:** An in-memory Hash Index tracks byte offsets, allowing single disk seek operations for data retrieval.
- **Thread-Safety:** Disk I/O operations are safeguarded using explicit locking mechanisms, enabling safe concurrent read/write operations from multiple API clients.
- **Microservice Ready:** Served over HTTP via FastAPI, making it accessible from any language as a standalone key-value cache/store.
- **Compaction Engine:** Includes an endpoint to merge and compact the append-only logs, removing deleted entries and recovering physical disk space.

## Architecture & State

1. **Storage Layer (`bitcask.py`):** Handles all binary packing (`struct`), byte offset management, sequential disk writes, and concurrency locks.
2. **Network Layer (`main.py`):** Exposes the database engine via a RESTful JSON API. The database instance is injected as a Singleton into the ASGI event loop, ensuring the memory index persists across HTTP requests.

## Installation & Setup

It is recommended to run the project inside an isolated virtual environment.

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install fastapi uvicorn requests

# 3. Start the API server
uvicorn main:app --reload
```

## API Reference

The API runs on `http://127.0.0.1:8000` by default. You can view the interactive Swagger UI at `/docs`.

### 1. Write / Update Key
**`PUT /keys/{key}`**
```bash
curl -X PUT "[http://127.0.0.1:8000/keys/my_key](http://127.0.0.1:8000/keys/my_key)" \
     -H "Content-Type: application/json" \
     -d '{"value": "Hello PyCask!"}'
```

### 2. Read Key
**`GET /keys/{key}`**
```bash
curl -X GET "[http://127.0.0.1:8000/keys/my_key](http://127.0.0.1:8000/keys/my_key)"
```

### 3. Delete Key
**`DELETE /keys/{key}`**
```bash
# Uses Tombstone mechanism under the hood
curl -X DELETE "[http://127.0.0.1:8000/keys/my_key](http://127.0.0.1:8000/keys/my_key)"
```

### 4. Run Compaction
**`POST /compact`**
```bash
# Compresses the log file and clears physical space of deleted items
curl -X POST "[http://127.0.0.1:8000/compact](http://127.0.0.1:8000/compact)"
```

## Benchmarking & Load Testing

A client script is included to simulate concurrent traffic and measure the throughput/latency of the engine.

While the server is running, execute the load test in a separate terminal:

```bash
python load_test.py
```

**Sample Output on standard hardware:**
```text
--- LOAD TEST RESULTS ---
Total records written: 1000
Total time elapsed: 0.95 seconds
Write Throughput: 1056.11 req/sec

Verification: Reading user:506 from memory (O(1))...
Read latency: 1.06 ms
```
