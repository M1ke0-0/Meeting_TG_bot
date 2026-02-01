import sqlite3
import logging
from config import DB_PATH

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            number          TEXT PRIMARY KEY,
            role            TEXT NOT NULL CHECK(role IN ('admin', 'user')),
            registered      INTEGER DEFAULT 0,
            tg_id           INTEGER,
            name            TEXT,
            surname         TEXT,
            gender          TEXT,
            age             INTEGER,
            region          TEXT,
            interests       TEXT,
            photo_file_id   TEXT,
            document_file_id TEXT,
            location_lat    REAL,
            location_lon    REAL,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS friends (
            user_id INTEGER,
            friend_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (user_id, friend_id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS friend_requests (
            from_user_id INTEGER,
            to_user_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (from_user_id, to_user_id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            organizer_phone TEXT NOT NULL,
            name TEXT NOT NULL,
            date TEXT NOT NULL,          -- ДД.ММ.ГГГГ
            time TEXT NOT NULL,          -- ЧЧ:ММ
            interests TEXT,              -- через запятую
            address TEXT,
            latitude REAL,               -- координаты для карты
            longitude REAL,
            description TEXT,
            photo_file_id TEXT,
            document_file_id TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organizer_phone) REFERENCES users(number)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS event_participants (
            event_id INTEGER,
            participant_phone TEXT,
            joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (event_id, participant_phone),
            FOREIGN KEY (event_id) REFERENCES events(id),
            FOREIGN KEY (participant_phone) REFERENCES users(number)
        )
    ''')
        
    conn.commit()
    conn.close()
    logging.info("Таблица users готова")

def init_admin_tables():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS interests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS regions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
    """)

    conn.commit()
    conn.close()
