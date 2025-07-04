import sqlite3
from datetime import datetime

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

# 🧾 Таблица пользователей
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 0,
    referral_from INTEGER,
    trial_used BOOLEAN DEFAULT 0,
    until TEXT,
    is_active BOOLEAN DEFAULT 0,
    user_key TEXT
)
''')

# 🔐 Таблица ключей
cursor.execute('''
CREATE TABLE IF NOT EXISTS keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT,
    active BOOLEAN DEFAULT 1
)
''')

# 💳 Таблица истории операций
cursor.execute('''
CREATE TABLE IF NOT EXISTS operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    type TEXT,
    amount INTEGER,
    comment TEXT,
    date TEXT
)
''')

conn.commit()

# ➕ Добавить пользователя (и начислить рефералу)
def add_user(user_id, username, referral_from=None):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO users (user_id, username, referral_from) VALUES (?, ?, ?)",
                       (user_id, username, referral_from))
        conn.commit()
        if referral_from and referral_from != user_id:
            update_balance(referral_from, 100, "Реферал")
        return True
    return False

# 👤 Получить пользователя
def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone()

# ✅ Пробник использован
def set_trial_used(user_id):
    cursor.execute("UPDATE users SET trial_used=1 WHERE user_id=?", (user_id,))
    conn.commit()

# ⏳ Обновить подписку
def update_until(user_id, until_date):
    cursor.execute("UPDATE users SET until=?, is_active=1 WHERE user_id=?", (until_date, user_id))
    conn.commit()

# ❌ Отключить подписку
def set_inactive(user_id):
    cursor.execute("UPDATE users SET is_active=0 WHERE user_id=?", (user_id,))
    conn.commit()

# 💸 Баланс
def update_balance(user_id, amount, comment=""):
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    cursor.execute('''
        INSERT INTO operations (user_id, type, amount, comment, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, "изменение", amount, comment, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def get_balance(user_id):
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else 0

# 🔑 Ключи
def add_key(key):
    cursor.execute("INSERT INTO keys (key) VALUES (?)", (key,))
    conn.commit()

def get_active_key():
    cursor.execute("SELECT key FROM keys WHERE active=1 LIMIT 1")
    result = cursor.fetchone()
    if result:
        cursor.execute("UPDATE keys SET active=0 WHERE key=?", (result[0],))
        conn.commit()
        return result[0]
    return None

def assign_key_to_user(user_id, key):
    cursor.execute("UPDATE users SET user_key=? WHERE user_id=?", (key, user_id))
    conn.commit()

def get_user_key(user_id):
    cursor.execute("SELECT user_key FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None

# 📦 Очистка неактивных ключей
def delete_inactive_keys():
    cursor.execute("DELETE FROM keys WHERE active=0")
    conn.commit()

# ✅ Проверка активности
def is_user_active(user_id):
    cursor.execute("SELECT is_active FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    return result[0] == 1 if result else False

# 📊 Операции
def get_user_operations(user_id):
    cursor.execute('''
        SELECT type, amount, comment, date
        FROM operations
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 20
    ''', (user_id,))
    return cursor.fetchall()

# 👥 Все пользователи
def get_all_users():
    cursor.execute("SELECT * FROM users")
    return cursor.fetchall()
