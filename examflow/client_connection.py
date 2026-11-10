import json
import os
from urllib.error import URLError
from urllib.request import urlopen
from urllib.parse import urlsplit, urlunsplit


def normalize_server_url(value):
    value = value.strip()
    parsed = urlsplit(value)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Sunucu adresi http://IP:5000 biçiminde olmalıdır.")

    path = parsed.path.rstrip("/")
    if path and path != "/":
        raise ValueError("Sunucu adresinde ek bir yol bulunmamalıdır.")
    return urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))


def check_server_connection(server_url, timeout=3):
    health_url = "{}/health".format(normalize_server_url(server_url))
    try:
        with urlopen(health_url, timeout=timeout) as response:
            if response.status != 200:
                raise ValueError("ExamFlow sunucusu sağlık kontrolünü geçemedi.")
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError) as error:
        raise ValueError(
            "Sunucuya bağlanılamadı. Adresi, portu ve ağ bağlantısını kontrol edin."
        ) from error

    if not isinstance(payload, dict) or payload.get("service") != "ExamFlow":
        raise ValueError("Bu adreste geçerli bir ExamFlow sunucusu bulunamadı.")
    return health_url.rsplit("/", 1)[0]


def client_settings_path():
    app_data = os.environ.get("APPDATA")
    if app_data:
        settings_dir = os.path.join(app_data, "ExamFlow")
    else:
        settings_dir = os.path.join(os.path.expanduser("~"), ".examflow")
    return os.path.join(settings_dir, "client.json")


def load_saved_server_url():
    path = client_settings_path()
    try:
        with open(path, "r", encoding="utf-8") as settings_file:
            settings = json.load(settings_file)
    except FileNotFoundError:
        return ""
    except (OSError, ValueError) as error:
        raise RuntimeError("Öğrenci bağlantı ayarları okunamadı.") from error

    if not isinstance(settings, dict):
        raise RuntimeError("Öğrenci bağlantı ayarları geçersiz.")
    server_url = settings.get("server_url", "")
    if not isinstance(server_url, str):
        raise RuntimeError("Öğrenci bağlantı ayarları geçersiz.")
    return server_url


def save_server_url(server_url):
    path = client_settings_path()
    settings_dir = os.path.dirname(path)
    os.makedirs(settings_dir, exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as settings_file:
            json.dump({"server_url": server_url}, settings_file)
    except OSError as error:
        raise RuntimeError("Sunucu bağlantı ayarı kaydedilemedi.") from error
