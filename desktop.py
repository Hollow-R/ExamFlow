
import os
import html
import threading
import time
from pathlib import Path

import webview

from examflow.client_connection import (
    check_server_connection,
    load_saved_server_url,
    save_server_url,
)


class ConnectionApi:
    def __init__(self, window):
        self.window = window

    def connect(self, server_url):
        try:
            normalized_url = check_server_connection(server_url)
            save_server_url(normalized_url)
        except (RuntimeError, ValueError) as error:
            return {"success": False, "message": str(error)}

        self.window.load_url(normalized_url)
        return {"success": True, "message": "Sunucuya bağlanılıyor."}


def _connection_page():
    template_path = Path(__file__).parent / "templates" / "client_connect.html"
    page = template_path.read_text(encoding="utf-8")
    saved_url = html.escape(load_saved_server_url(), quote=True)
    return page.replace("__SAVED_SERVER_URL__", saved_url)


def main():
    mode = os.environ.get("EXAMFLOW_MODE", "server").lower()
    server_url = os.environ.get("EXAMFLOW_SERVER_URL")
    if mode == "client" and not server_url:
        window = webview.create_window(
            title="ExamFlow - Sunucuya Bağlan",
            html=_connection_page(),
            width=560,
            height=620,
            min_size=(420, 500),
            resizable=True,
        )
        window.expose(ConnectionApi(window).connect)
    elif mode == "client" or server_url:
        window_url = check_server_connection(server_url)
        webview.create_window(
            title="ExamFlow",
            url=window_url,
            width=1200,
            height=800,
            min_size=(900, 600),
            resizable=True,
        )
    elif mode == "server":
        from app import start_server

        server_thread = threading.Thread(target=start_server, daemon=True)
        server_thread.start()
        time.sleep(1)
        window_url = "http://127.0.0.1:{}".format(
            os.environ.get("EXAMFLOW_PORT", "5000")
        )
        webview.create_window(
            title="ExamFlow",
            url=window_url,
            width=1200,
            height=800,
            min_size=(900, 600),
            resizable=True,
        )
    else:
        raise ValueError("EXAMFLOW_MODE 'server' veya 'client' olmalıdır.")

    webview.start()


if __name__ == "__main__":
    main()
