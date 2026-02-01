import sqlite3
from config import DB_PATH, ADMIN_PHONES

def check_user_status(phone: str) -> dict:
    """Возвращает статус пользователя или None"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT role, registered, tg_id, name
            FROM users WHERE number = ?
        """, (phone,))
        row = c.fetchone()
    
    if row:
        return {
            "exists": True,
            "role": row[0],
            "registered": bool(row[1]),
            "tg_id": row[2],
            "name": row[3]
        }
    return {"exists": False}

def register_phone(phone: str, tg_id: int):
    """Добавляем номер + tg_id, роль определяется по ADMIN_PHONES"""
    role = "admin" if phone in ADMIN_PHONES else "user"
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        try:
            c.execute("""
                INSERT INTO users (number, role, tg_id, registered)
                VALUES (?, ?, ?, 0)
            """, (phone, role, tg_id))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def update_user_profile(phone: str, data: dict):
    """Обновляем профиль пользователя в БД"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE users SET
                name = ?, surname = ?, gender = ?, age = ?,
                region = ?, interests = ?, photo_file_id = ?,
                document_file_id = ?, location_lat = ?, location_lon = ?,
                registered = 1
            WHERE number = ?
        """, (
            data.get('name'), data.get('surname'), data.get('gender'),
            data.get('age'), data.get('region'),
            ','.join(data.get('interests', [])) if data.get('interests') else None,
            data.get('photo_file_id'), data.get('document_file_id'),
            data.get('location_lat'), data.get('location_lon'), phone
        ))
        conn.commit()

def get_user_by_tg_id(tg_id: int) -> dict | None:
    """Получает все данные пользователя по telegram ID"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT tg_id, number, role, registered, name, surname, gender, age, 
                   region, interests, photo_file_id, document_file_id, 
                   location_lat, location_lon
            FROM users WHERE tg_id = ?
        """, (tg_id,))
        row = c.fetchone()
    
    if row:
        columns = [
            "tg_id", "number", "role", "registered", "name", "surname", "gender",
            "age", "region", "interests", "photo_file_id", "document_file_id",
            "location_lat", "location_lon"
        ]
        user = dict(zip(columns, row))
        user["registered"] = bool(user["registered"])
        return user
    return None

def find_potential_friends(organizer_phone: str, interests: list[str] = None):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        query = """
            SELECT number, tg_id, name, surname, age, gender, region, interests
            FROM users
            WHERE number != ?
            AND registered = 1
            AND tg_id IS NOT NULL  -- только те, кто заходил в бот
        """
        params = [organizer_phone]

        if interests:
            query += " AND ("
            conditions = []
            for interest in interests:
                conditions.append("interests LIKE ?")
                params.append(f"%{interest}%")
            query += " OR ".join(conditions) + ")"

        c.execute(query, params)
        rows = c.fetchall()

    friends = []
    for row in rows:
        friends.append({
            "phone": row[0],
            "tg_id": row[1],
            "name": row[2] or "—",
            "surname": row[3] or "",
            "age": row[4],
            "gender": row[5],
            "region": row[6],
            "interests": row[7].split(",") if row[7] else []
        })

    if interests:
        friends.sort(
            key=lambda f: len(set(interests) & set(f["interests"])),
            reverse=True
        )

    return friends[:20]

def add_friend_db(user_id: int, friend_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        try:
            c.execute("INSERT INTO friends (user_id, friend_id) VALUES (?, ?)", (user_id, friend_id))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def get_friends_db(user_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT u.tg_id, u.name, u.surname, u.age, u.region, u.interests, u.photo_file_id
            FROM friends f
            JOIN users u ON f.friend_id = u.tg_id
            WHERE f.user_id = ?
        """, (user_id,))
        rows = c.fetchall()
    
    friends = []
    for row in rows:
        friends.append({
            "tg_id": row[0],
            "name": row[1],
            "surname": row[2],
            "age": row[3],
            "region": row[4],
            "interests": row[5],
            "photo": row[6]
        })
    return friends

def check_is_friend(user_id: int, target_id: int) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?", (user_id, target_id))
        return bool(c.fetchone())

def send_friend_request(from_user_id: int, to_user_id: int):
    """Создает заявку в друзья"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        try:
            c.execute("SELECT 1 FROM friends WHERE user_id = ? AND friend_id = ?", (from_user_id, to_user_id))
            if c.fetchone(): return "already_friends"

            c.execute("SELECT 1 FROM friend_requests WHERE from_user_id = ? AND to_user_id = ?", (from_user_id, to_user_id))
            if c.fetchone(): return "already_sent"
            
            c.execute("INSERT INTO friend_requests (from_user_id, to_user_id) VALUES (?, ?)", (from_user_id, to_user_id))
            conn.commit()
            return "ok"
        except sqlite3.IntegrityError:
            return "error"

def get_incoming_requests(user_id: int):
    """Получить входящие заявки"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT u.tg_id, u.name, u.surname, u.age, u.region, u.interests, u.photo_file_id
            FROM friend_requests fr
            JOIN users u ON fr.from_user_id = u.tg_id
            WHERE fr.to_user_id = ?
        """, (user_id,))
        rows = c.fetchall()
        
    requests = []
    for row in rows:
        requests.append({
            "tg_id": row[0],
            "name": row[1],
            "surname": row[2],
            "age": row[3],
            "region": row[4],
            "interests": row[5],
            "photo": row[6]
        })
    return requests

def accept_friend_request(user_id: int, requester_id: int):
    """Принять заявку: добавить в друзья обоих и удалить заявку"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        try:
            c.execute("INSERT OR IGNORE INTO friends (user_id, friend_id) VALUES (?, ?)", (user_id, requester_id))
            c.execute("INSERT OR IGNORE INTO friends (user_id, friend_id) VALUES (?, ?)", (requester_id, user_id))
            
            c.execute("DELETE FROM friend_requests WHERE from_user_id = ? AND to_user_id = ?", (requester_id, user_id))
            conn.commit()
            return True
        except Exception:
            return False

def decline_friend_request(user_id: int, requester_id: int):
    """Отклонить заявку"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM friend_requests WHERE from_user_id = ? AND to_user_id = ?", (requester_id, user_id))
        conn.commit()

def delete_friend_db(user_id: int, friend_id: int):
    """Удалить друга (bidirectional)"""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM friends WHERE user_id = ? AND friend_id = ?", (user_id, friend_id))
        c.execute("DELETE FROM friends WHERE user_id = ? AND friend_id = ?", (friend_id, user_id))
        conn.commit()
