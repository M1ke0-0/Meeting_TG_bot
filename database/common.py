import sqlite3
from config import DB_PATH

def replace_interests(interests: list[str]):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM interests")
        c.executemany(
            "INSERT OR IGNORE INTO interests (name) VALUES (?)",
            [(i.strip(),) for i in interests if i.strip()]
        )
        conn.commit()

def replace_regions(regions: list[str]):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM regions")
        c.executemany(
            "INSERT OR IGNORE INTO regions (name) VALUES (?)",
            [(r.strip(),) for r in regions if r.strip()]
        )
        conn.commit()

def get_all_regions() -> list[str]:
    """Возвращает актуальный список регионов из БД"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM regions ORDER BY name")
        regions = [row[0] for row in c.fetchall()]
    return regions if regions else ["Регионы пока не добавлены"]

def get_all_interests() -> list[str]:
    """Возвращает актуальный список интересов из БД"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT name FROM interests ORDER BY name")
        interests = [row[0] for row in c.fetchall()]
    return interests if interests else ["Интересы пока не добавлены"]
