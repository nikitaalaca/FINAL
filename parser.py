import requests
from bs4 import BeautifulSoup

# Пример источников. Можно расширить.
V2_SOURCES = [
    "https://raw.githubusercontent.com/mahdibland/V2RayAggregator/master/sub/sub_merge.txt",
    "https://pastebin.com/raw/ZzGTySZE"
]

def get_v2_keys():
    keys = []
    for url in V2_SOURCES:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                lines = response.text.strip().splitlines()
                keys += [line.strip() for line in lines if line.startswith("vmess://")]
        except Exception as e:
            print(f"[!] Ошибка при парсинге {url}: {e}")
    return list(set(keys))  # удаляем дубликаты

def validate_v2_key(key: str) -> bool:
    # Упрощённая проверка: можно сделать проверку по curl или ping
    try:
        if key.startswith("vmess://") and len(key) > 20:
            return True
        return False
    except Exception:
        return False
