import sqlite3
from datetime import datetime

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 0,
    referral_from INTEGER,
    trial_used BOOLEAN DEFAULT 0,
    until TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT,
    active BOOLEAN DEFAULT 1
)
''')

def add_user(user_id, username, referral_from=None):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    if cursor.fetchone() is None:
        cursor.execute("INSERT INTO users (user_id, username, referral_from) VALUES (?, ?, ?)",
                       (user_id, username, referral_from))
        conn.commit()

def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    return cursor.fetchone()

def set_trial_used(user_id):
    cursor.execute("UPDATE users SET trial_used=1 WHERE user_id=?", (user_id,))
    conn.commit()

def update_until(user_id, until_date):
    cursor.execute("UPDATE users SET until=? WHERE user_id=?", (until_date, user_id))
    conn.commit()

def add_balance(user_id, amount):
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()

def get_balance(user_id):
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    result = cursor.fetchone()
    return result[0] if result else 0

def get_all_users():
    cursor.execute("SELECT * FROM users")
    return cursor.fetchall()

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
