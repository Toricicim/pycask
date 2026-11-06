"""A single-process, thread-safe append-only key-value store."""

import os
import shutil
import struct
import tempfile
import threading
import warnings


MAGIC = b"PyCask\x02\n"
HEADER = struct.Struct("<BII")  # operation, key byte length, value byte length
LEGACY_HEADER = struct.Struct("II")
PUT = 1
DELETE = 2


def _encode(key, value):
    key_bytes = key.encode("utf-8")
    value_bytes = b"" if value is None else value.encode("utf-8")
    operation = DELETE if value is None else PUT
    return HEADER.pack(operation, len(key_bytes), len(value_bytes)) + key_bytes + value_bytes


def _read_record(reader, *, legacy=False):
    """Return (key, value), None at EOF, or raise on a malformed record."""
    header = LEGACY_HEADER if legacy else HEADER
    data = reader.read(header.size)
    if not data:
        return None
    if len(data) != header.size:
        raise EOFError("Incomplete record header")
    if legacy:
        key_len, value_len = header.unpack(data)
        operation = PUT
    else:
        operation, key_len, value_len = header.unpack(data)
        if operation not in (PUT, DELETE) or (operation == DELETE and value_len != 0):
            raise ValueError("Invalid record operation")
    # Validate lengths before allocating memory for an untrusted header.
    remaining = os.fstat(reader.fileno()).st_size - reader.tell()
    if key_len + value_len > remaining:
        raise EOFError("Incomplete record payload")
    key = reader.read(key_len).decode("utf-8")
    value_bytes = reader.read(value_len)
    if operation == DELETE or (legacy and value_bytes == b"__DELETED__"):
        return key, None
    return key, value_bytes.decode("utf-8")


class DB:
    def __init__(self, filepath="database.data") -> None:
        self.filepath = os.path.abspath(os.fspath(filepath))
        # Reads also hold this lock: compaction replaces both the file and offsets.
        self.write_lock = threading.RLock()
        self.index = {}
        self.file = open(self.filepath, "a+b")
        try:
            self.file.seek(0)
            prefix = self.file.read(len(MAGIC))
            if not prefix:
                self.file.write(MAGIC)
                self.file.flush()
            elif prefix != MAGIC:
                if MAGIC.startswith(prefix):
                    raise ValueError("Incomplete database format header")
                self.file.close()
                self._migrate_legacy()
                self.file = open(self.filepath, "r+b")
            self.load()
        except BaseException:
            self.file.close()
            raise

    def put(self, key: str, value: str):
        if not isinstance(value, str):
            raise TypeError("Values must be strings")
        record = _encode(key, value)
        with self.write_lock:
            self.file.seek(0, os.SEEK_END)
            offset = self.file.tell()
            self.file.write(record)
            self.file.flush()
            self.index[key] = offset

    def get(self, key: str):
        with self.write_lock:
            offset = self.index.get(key)
            if offset is None:
                return None
            self.file.seek(offset)
            record = _read_record(self.file)
            if record is None or record[0] != key or record[1] is None:
                raise ValueError("Record does not match the in-memory index")
            return record[1]

    def delete(self, key: str):
        with self.write_lock:
            if key not in self.index:
                return False
            self.file.seek(0, os.SEEK_END)
            self.file.write(_encode(key, None))
            self.file.flush()
            del self.index[key]
            return True

    def compact(self):
        with self.write_lock:
            fd, temporary = tempfile.mkstemp(dir=os.path.dirname(self.filepath), suffix=".compact")
            replacement = os.fdopen(fd, "w+b")
            try:
                replacement.write(MAGIC)
                new_index = {}
                for key in self.index:
                    value = self.get(key)
                    new_index[key] = replacement.tell()
                    replacement.write(_encode(key, value))
                replacement.flush()
                os.fsync(replacement.fileno())
                # Keep the original handle/index usable if replacement fails.
                os.replace(temporary, self.filepath)
                old_file = self.file
                self.file = replacement
                self.index = new_index
                old_file.close()
            except BaseException:
                replacement.close()
                if os.path.exists(temporary):
                    os.unlink(temporary)
                raise

    def load(self):
        with self.write_lock:
            new_index = {}
            self.file.seek(len(MAGIC))
            while True:
                offset = self.file.tell()
                try:
                    record = _read_record(self.file)
                except EOFError:
                    # Remove an interrupted final append before any future writes.
                    self.file.seek(offset)
                    self.file.truncate()
                    self.file.flush()
                    warnings.warn("Discarded an incomplete final record", RuntimeWarning)
                    break
                if record is None:
                    break
                key, value = record
                if value is None:
                    new_index.pop(key, None)
                else:
                    new_index[key] = offset
            self.index = new_index

    def _migrate_legacy(self):
        """Preserve v1 replay semantics and retain its bytes in a .v1.bak file."""
        fd, temporary = tempfile.mkstemp(dir=os.path.dirname(self.filepath), suffix=".compact")
        try:
            with os.fdopen(fd, "wb") as target, open(self.filepath, "rb") as source:
                target.write(MAGIC)
                while (record := _read_record(source, legacy=True)) is not None:
                    target.write(_encode(*record))
                target.flush()
                os.fsync(target.fileno())
                source.seek(0)
                # Exclusive creation prevents overwriting a previous backup.
                with open(self.filepath + ".v1.bak", "xb") as backup:
                    shutil.copyfileobj(source, backup)
                    backup.flush()
                    os.fsync(backup.fileno())
            os.replace(temporary, self.filepath)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        warnings.warn(
            "Migrated legacy database; original saved as .v1.bak. Legacy '__DELETED__' "
            "values are ambiguous and retain their old tombstone meaning.",
            RuntimeWarning,
        )

    def close(self):
        with self.write_lock:
            self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
