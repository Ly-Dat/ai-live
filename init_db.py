"""Create data/data.db with the same tables the app creates (utils/my_handle.py).
Run once from the AI-Vtuber folder:  python init_db.py
Fixes: webui.py crashing with "TypeError: 'NoneType' object is not iterable" on first start."""
import os
import sqlite3

os.makedirs("data", exist_ok=True)
conn = sqlite3.connect("data/data.db")
conn.executescript("""
CREATE TABLE IF NOT EXISTS danmu (username TEXT NOT NULL, content TEXT NOT NULL, ts DATETIME NOT NULL);
CREATE TABLE IF NOT EXISTS entrance (username TEXT NOT NULL, ts DATETIME NOT NULL);
CREATE TABLE IF NOT EXISTS gift (username TEXT NOT NULL, gift_name TEXT NOT NULL, gift_num INT NOT NULL,
    unit_price REAL NOT NULL, total_price REAL NOT NULL, ts DATETIME NOT NULL);
CREATE TABLE IF NOT EXISTS integral (platform TEXT NOT NULL, username TEXT NOT NULL, uid TEXT NOT NULL,
    integral INT NOT NULL, view_num INT NOT NULL, sign_num INT NOT NULL, last_sign_ts DATETIME NOT NULL,
    total_price INT NOT NULL, last_ts DATETIME NOT NULL);
""")
conn.commit()
conn.close()
print("OK: data/data.db created")