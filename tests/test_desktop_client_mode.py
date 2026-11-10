import importlib
import sys
import types
import unittest
from unittest.mock import Mock, patch


webview_stub = types.ModuleType("webview")
webview_stub.create_window = Mock()
webview_stub.start = Mock()
with patch.dict(sys.modules, {"webview": webview_stub}):
    desktop = importlib.import_module("desktop")


class DesktopClientModeTests(unittest.TestCase):
    def tearDown(self):
        desktop.webview.create_window.reset_mock()
        desktop.webview.start.reset_mock()

    def test_client_mode_opens_connection_form_and_exposes_connect(self):
        window = Mock()
        desktop.webview.create_window.return_value = window
        with patch.dict("os.environ", {"EXAMFLOW_MODE": "client"}, clear=True):
            with patch.object(desktop, "_connection_page", return_value="<html>"):
                desktop.main()

        desktop.webview.create_window.assert_called_once()
        self.assertEqual(
            desktop.webview.create_window.call_args.kwargs["html"],
            "<html>",
        )
        self.assertTrue(window.expose.called)
        desktop.webview.start.assert_called_once_with()

    def test_connect_checks_and_saves_server_before_navigation(self):
        window = Mock()
        api = desktop.ConnectionApi(window)
        with patch.object(
            desktop,
            "check_server_connection",
            return_value="http://192.168.1.20:5000",
        ) as check_connection:
            with patch.object(desktop, "save_server_url") as save_url:
                result = api.connect("http://192.168.1.20:5000")

        self.assertTrue(result["success"])
        check_connection.assert_called_once_with("http://192.168.1.20:5000")
        save_url.assert_called_once_with("http://192.168.1.20:5000")
        window.load_url.assert_called_once_with("http://192.168.1.20:5000")

    def test_connect_returns_validation_errors_to_the_form(self):
        window = Mock()
        api = desktop.ConnectionApi(window)
        with patch.object(
            desktop,
            "check_server_connection",
            side_effect=ValueError("Invalid address"),
        ):
            result = api.connect("invalid")

        self.assertFalse(result["success"])
        self.assertEqual(result["message"], "Invalid address")
        window.load_url.assert_not_called()


if __name__ == "__main__":
    unittest.main()
