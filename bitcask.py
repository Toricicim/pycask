import struct
import threading
import os


class DB:
    def __init__(self) -> None:
        self.filepath = "database.data"
        self.write_lock = threading.Lock()
        self.index = {}

        # Create an empty file if it doesn't exist to prevent read errors
        if not os.path.exists(self.filepath):
            open(self.filepath, "wb").close()

        # Append-only file handle for write operations
        self.file = open(self.filepath, "ab+")
        self.load()

    def put(self, key: str, value: str):
        key_bytes = key.encode("utf-8")
        val_bytes = value.encode("utf-8")

        key_len = len(key_bytes)
        val_len = len(val_bytes)

        header = struct.pack("II", key_len, val_len)
        record = header + key_bytes + val_bytes

        with self.write_lock:
            offset = self.file.tell()
            self.file.write(record)
            self.file.flush()
            self.index[key] = offset

    def get(self, key: str):
        if key not in self.index:
            return None

        offset = self.index[key]

        # Thread-safe read: Each read operation uses its own file descriptor
        with open(self.filepath, "rb") as f:
            f.seek(offset)
            header_data = f.read(8)
            key_len, val_len = struct.unpack("II", header_data)

            f.read(key_len)  # Skip the key, read only the value
            value_bytes = f.read(val_len)

        return value_bytes.decode("utf-8")

    def delete(self, key: str):
        with self.write_lock:
            if key not in self.index:
                return False

            key_bytes = key.encode("utf-8")
            val_bytes = b"__DELETED__"

            key_len = len(key_bytes)
            val_len = len(val_bytes)

            header = struct.pack("II", key_len, val_len)
            record = header + key_bytes + val_bytes

            self.file.write(record)
            self.file.flush()
            del self.index[key]
            return True

    def load(self):
        with open(self.filepath, "rb") as f:
            while True:
                start_offset = f.tell()
                header_data = f.read(8)

                if len(header_data) < 8:
                    break

                key_len, val_len = struct.unpack("II", header_data)
                key_bytes = f.read(key_len)
                value_bytes = f.read(val_len)

                key = key_bytes.decode("utf-8")

                if value_bytes == b"__DELETED__":
                    if key in self.index:
                        del self.index[key]
                else:
                    self.index[key] = start_offset
