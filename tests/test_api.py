from pathlib import Path
import socket
from tempfile import TemporaryDirectory
import threading
import time
import unittest
from unittest.mock import patch

import requests
import uvicorn

from load_test import run_load_test
from main import app


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = TemporaryDirectory()
        cls.environment = patch.dict("os.environ", {"PYCASK_DATA_FILE": str(Path(cls.directory.name) / "api.data")})
        cls.environment.start()
        cls.socket = socket.socket()
        cls.socket.bind(("127.0.0.1", 0))
        cls.base_url = f"http://127.0.0.1:{cls.socket.getsockname()[1]}"
        cls.server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
        cls.thread = threading.Thread(target=cls.server.run, kwargs={"sockets": [cls.socket]}, daemon=True)
        cls.thread.start()
        deadline = time.monotonic() + 10
        while not cls.server.started:
            if not cls.thread.is_alive() or time.monotonic() > deadline:
                cls.tearDownClass()
                raise RuntimeError("Test API server did not start")
            time.sleep(0.01)

    @classmethod
    def tearDownClass(cls):
        cls.server.should_exit = True
        cls.thread.join(timeout=10)
        cls.socket.close()
        cls.environment.stop()
        cls.directory.cleanup()

    def test_crud_and_compaction_endpoints(self):
        health = requests.get(self.base_url + "/", timeout=5)
        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "online")
        url = self.base_url + "/keys/api-key"
        self.assertEqual(requests.get(url, timeout=5).status_code, 404)
        for value in ("first", "__DELETED__", "", "Türkçe 🌍"):
            self.assertEqual(requests.put(url, json={"value": value}, timeout=5).status_code, 200)
            self.assertEqual(requests.post(self.base_url + "/compact", timeout=5).status_code, 200)
            self.assertEqual(requests.get(url, timeout=5).json(), {"key": "api-key", "value": value})
        deleted = requests.delete(url, timeout=5)
        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(deleted.content, b"")
        self.assertEqual(requests.get(url, timeout=5).status_code, 404)
        self.assertEqual(requests.delete(url, timeout=5).status_code, 404)
        self.assertEqual(requests.put(url, json={}, timeout=5).status_code, 422)

    def test_concurrent_load_client_verifies_all_successful_writes(self):
        result = run_load_test(self.base_url, records=50, workers=8, timeout=5)
        self.assertEqual(result["successful_writes"], 50)
        self.assertEqual(result["verified_reads"], 50)
        self.assertEqual(result["failed_writes"], 0)
        self.assertEqual(result["failed_verifications"], 0)

    def test_load_client_reports_transport_errors_as_failures(self):
        with patch("load_test.requests.put", side_effect=requests.ConnectionError("offline")):
            result = run_load_test(self.base_url, records=8, workers=4, timeout=1)
        self.assertEqual(result["successful_writes"], 0)
        self.assertEqual(result["failed_writes"], 8)
        self.assertEqual(result["verified_reads"], 0)
        self.assertEqual(result["successful_writes_per_second"], 0)

    def test_load_client_actually_overlaps_requests_and_detects_wrong_values(self):
        barrier = threading.Barrier(4)
        def simultaneous_write(*args, **kwargs):
            barrier.wait(timeout=3)
            response = requests.Response()
            response.status_code = 200
            return response
        wrong_value = requests.Response()
        wrong_value.status_code = 200
        wrong_value._content = b'{"key": "wrong", "value": "wrong"}'
        with patch("load_test.requests.put", side_effect=simultaneous_write), patch("load_test.requests.get", return_value=wrong_value):
            result = run_load_test(self.base_url, records=4, workers=4, timeout=5)
        self.assertEqual(result["successful_writes"], 4)
        self.assertEqual(result["verified_reads"], 0)
        self.assertEqual(result["failed_verifications"], 4)


if __name__ == "__main__":
    unittest.main()
