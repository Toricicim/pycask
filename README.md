# PyCask: Binary Key-Value Store

A persistent, disk-based Key-Value database engine developed from scratch in pure Python. This project is designed to demonstrate the fundamental principles of the Bitcask architecture and Log-Structured File Systems.

Data is stored on the disk in a binary format and managed via an in-memory index, ensuring high-performance data retrieval.

## Features

- **Persistence:** Data is stored using an "append-only" strategy. Data remains persistent and safe even after the program terminates or crashes.
- **High Performance:** Utilizes an in-memory Hash Index to track byte offsets, achieving **O(1)** time complexity for read operations.
- **Binary Protocol:** Unlike text-based formats (like CSV), data is serialized and packed using Python's `struct` module. This ensures safe handling of arbitrary binary data and special characters.
- **Crash Recovery:** Upon initialization, the database scans the existing data file to reconstruct the in-memory index map automatically.
- **Zero Dependencies:** Built entirely using the Python Standard Library (`struct`, `os`). No external packages required.

## Architecture

The engine consists of two main components:

1.  **Disk Storage (Data File):** Records are appended sequentially to the file. Each entry follows this binary layout:
    `[Key Size (4 Bytes)] [Value Size (4 Bytes)] [Key Data] [Value Data]`

2.  **Memory Index (KeyDir):** A Python dictionary (Hash Map) is maintained in RAM, mapping every key to its exact byte offset (location) in the disk file.

## Installation

No external package installation is required. Python 3.x is sufficient.

Clone the repository:

git clone https://github.com/YOUR_USERNAME/py-bitcask-db.git
cd py-bitcask-db

## Usage

You can import the `DB` class into your project as shown below:

```python
from db import DB

# Initialize the database
# (Creates the file if it doesn't exist; loads the index if it does)
db = DB()

# Writing Data
# Keys and values must be strings (automatically encoded to bytes)
db.yaz("user_id", "10245")
db.yaz("username", "johndoe")
print("Data written to disk.")

# Reading Data
# Retrieves data directly from disk using the offset (O(1) speed)
data = db.oku("username")
print(f"Retrieved Value: {data}")

# Querying non-existent data returns None
result = db.oku("non_existent_key")
