import re
import requests
import base64
import socket
from bs4 import BeautifulSoup

# ⏱ Таймаут соединения при проверке ключа
TIMEOUT = 3

# 📌 Список источников с ключами
SOURCES = [
    "https://raw.githubusercontent.com/malekal/V2rayFree/main/README.md",
    "https://v2rayshare.com/",
    "https://freev2ray.org/",
    "https://www.v2rayssr.com/",
]

# 🧠 Вспомогательная функция: извлекает vmess/vless ссылки
def extract_links(text):
    pattern = r'(vmess|vless)://[a-zA-Z0-9+/=]+'
    return re.findall(pattern, text)

# 🌐 Парсинг всех источников
def get_v2_keys():
    keys = set()

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    for url in SOURCES:
        try:
            r = requests.get(url, headers=headers, timeout=5)
            text = r.text
            links = extract_links(text)
            keys.update(links)
        except Exception as e:
            print(f"Ошибка при получении ключей с {url}: {e}")
            continue

    print(f"[parser] Получено ссыл: {len(keys)}")
    return list(keys)

# 🔍 Проверка работоспособности V2 ключа (по IP/порту)
def validate_v2_key(link):
    try:
        raw = link.split("://")[1]
        decoded = base64.b64decode(raw + "===").decode("utf-8", errors="ignore")

        # Пробуем извлечь адрес и порт
        if "add" in decoded and "port" in decoded:
            addr = re.search(r'"add"\s*:\s*"([^"]+)"', decoded)
            port = re.search(r'"port"\s*:\s*"?(\\d+|\d+)"?', decoded)
        else:
            addr = re.search(r'address\s*:\s*([^,\n]+)', decoded)
            port = re.search(r'port\s*:\s*(\d+)', decoded)

        if addr and port:
            host = addr.group(1).strip()
            port = int(port.group(1).strip())

            with socket.create_connection((host, port), timeout=TIMEOUT):
                return True
    except Exception:
        pass
    return False
