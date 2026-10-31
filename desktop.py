
import threading
import time
import webview

from app import start_server


def main():
    # Flask sunucusunu arka planda başlat
    server_thread = threading.Thread(
        target=start_server,
        daemon=True
    )

    server_thread.start()

    # Sunucunun başlaması için kısa süre bekle
    time.sleep(1)

    # Masaüstü penceresini oluştur
    window = webview.create_window(
        title="ExamFlow",
        url="http://127.0.0.1:5000",
        width=1200,
        height=800,
        min_size=(900, 600),
        resizable=True
    )

    webview.start()


if __name__ == "__main__":
    main()
