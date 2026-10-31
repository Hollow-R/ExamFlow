
import os
import threading
import time
from urllib.parse import urlparse

import webview


def main():
    server_url = os.environ.get("EXAMFLOW_SERVER_URL")
    if server_url:
        parsed_url = urlparse(server_url)
        if parsed_url.scheme not in ("http", "https") or not parsed_url.netloc:
            raise ValueError("EXAMFLOW_SERVER_URL geçerli bir HTTP(S) adresi olmalıdır.")
        window_url = server_url
    else:
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
        resizable=True
    )

    webview.start()


if __name__ == "__main__":
    main()
