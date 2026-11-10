import json
import os
import tempfile
import unittest
from unittest.mock import patch

from examflow.client_connection import (
    check_server_connection,
    load_saved_server_url,
    normalize_server_url,
    save_server_url,
)


class ClientConnectionTests(unittest.TestCase):
    def test_normalize_server_url(self):
        self.assertEqual(
            normalize_server_url(" http://192.168.1.20:5000/ "),
            "http://192.168.1.20:5000",
        )

    def test_rejects_non_server_urls(self):
        invalid_urls = [
            "192.168.1.20:5000",
            "ftp://192.168.1.20:5000",
            "http://user:pass@192.168.1.20:5000",
            "http://192.168.1.20:5000/path",
            "http://192.168.1.20:5000/?token=value",
        ]
        for value in invalid_urls:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_server_url(value)

    def test_health_check_requires_examflow_service(self):
        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, _type, _value, _traceback):
                return None

            def read(self):
                return b'{"service":"ExamFlow","status":"ok"}'

        with patch(
            "examflow.client_connection.urlopen",
            return_value=FakeResponse(),
        ) as urlopen:
            result = check_server_connection("http://192.168.1.20:5000/")
        self.assertEqual(result, "http://192.168.1.20:5000")
        urlopen.assert_called_once_with(
            "http://192.168.1.20:5000/health",
            timeout=3,
        )

    def test_rejects_other_services_and_connection_errors(self):
        class FakeResponse:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, _type, _value, _traceback):
                return None

            def read(self):
                return b'{"service":"NotExamFlow"}'

        with patch(
            "examflow.client_connection.urlopen",
            return_value=FakeResponse(),
        ):
            with self.assertRaises(ValueError):
                check_server_connection("http://192.168.1.20:5000")

        with patch(
            "examflow.client_connection.urlopen",
            side_effect=OSError("network down"),
        ):
            with self.assertRaises(ValueError):
                check_server_connection("http://192.168.1.20:5000")

    def test_save_and_load_connection_setting(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.dict(os.environ, {"APPDATA": temporary_directory}):
                save_server_url("http://192.168.1.20:5000")
                self.assertEqual(
                    load_saved_server_url(),
                    "http://192.168.1.20:5000",
                )
                path = os.path.join(
                    temporary_directory,
                    "ExamFlow",
                    "client.json",
                )
                with open(path, "r", encoding="utf-8") as settings_file:
                    self.assertEqual(
                        json.load(settings_file),
                        {"server_url": "http://192.168.1.20:5000"},
                    )

    def test_load_rejects_non_object_settings(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            with patch.dict(os.environ, {"APPDATA": temporary_directory}):
                settings_dir = os.path.join(temporary_directory, "ExamFlow")
                os.makedirs(settings_dir)
                path = os.path.join(settings_dir, "client.json")
                with open(path, "w", encoding="utf-8") as settings_file:
                    json.dump([], settings_file)
                with self.assertRaises(RuntimeError):
                    load_saved_server_url()


if __name__ == "__main__":
    unittest.main()
