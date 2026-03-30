import sqlite3
from datetime import datetime

DB_NAME = "applications.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            full_name TEXT,
            language TEXT,
            service TEXT,
            contact TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_application(user_id, username, full_name, language, service, contact):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO applications (user_id, username, full_name, language, service, contact, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, username, full_name, language, service, contact, datetime.now().isoformat()))
    conn.commit()
    conn.close()
