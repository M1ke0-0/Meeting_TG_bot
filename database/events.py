import sqlite3
import logging
from config import DB_PATH
from aiogram.enums import ParseMode
from utils.validation import escape_html

def mask_phone(phone: str) -> str:
    """Mask phone number for privacy, showing only last 4 digits."""
    if not phone or len(phone) < 4:
        return "***"
    return f"***{phone[-4:]}"

async def get_event_card_text(event: dict):
    """Формирует текст карточки мероприятия с экранированием HTML"""
    safe_name = escape_html(event.get('name', ''))
    safe_address = escape_html(event.get('address', ''))
    safe_interests = escape_html(event.get('interests', ''))
    safe_description = escape_html(event.get('description', ''))
    
    text = f"<b>{safe_name}</b>\n"
    text += f"📅 {escape_html(event.get('date', ''))} в {escape_html(event.get('time', ''))}\n"
    if safe_address:
        text += f"📍 {safe_address}\n"
    if safe_interests:
        text += f"❤️ {safe_interests}\n"
    if safe_description:
        text += f"\n{safe_description}\n"
    text += f"\nОрганизатор: {mask_phone(event.get('organizer_phone', ''))}\n"
    return text

def create_event_db(user_phone: str, data: dict):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                INSERT INTO events (
                    organizer_phone, name, date, time, interests, address, 
                    latitude, longitude, description, photo_file_id, document_file_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_phone, data.get("name"), data.get("date"), data.get("time"),
                ','.join(data.get("interests", [])) if data.get("interests") else None,
                data.get("address"), data.get("latitude"), data.get("longitude"),
                data.get("description"),
                data.get("photo_file_id"), data.get("document_file_id")
            ))
            conn.commit()
            return True
    except Exception as e:
        logging.error(f"Error creating event: {e}")
        return False

def get_friends_events(user_phone: str):
    """Get events from friends only (not user's own events) per TZ 1.3.1."""
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT 
                e.id, e.name, e.date, e.time, e.address, e.interests, 
                e.description, e.organizer_phone,
                CASE WHEN ep.participant_phone IS NOT NULL THEN 1 ELSE 0 END as is_participant
            FROM events e
            LEFT JOIN event_participants ep 
                ON e.id = ep.event_id AND ep.participant_phone = ?
            INNER JOIN users u ON e.organizer_phone = u.number
            WHERE e.organizer_phone != ?
              AND u.tg_id IN (
                  -- Friends where I am user_id
                  SELECT f.friend_id FROM friends f
                  INNER JOIN users me ON f.user_id = me.tg_id
                  WHERE me.number = ?
                  UNION
                  -- Friends where I am friend_id
                  SELECT f.user_id FROM friends f
                  INNER JOIN users me ON f.friend_id = me.tg_id
                  WHERE me.number = ?
              )
            ORDER BY e.date ASC, e.time ASC
        """, (user_phone, user_phone, user_phone, user_phone))
        return c.fetchall()

def get_my_events(user_phone: str):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        c.execute("""
            SELECT 
                e.id, e.name, e.date, e.time, e.address, e.interests, 
                e.description, e.organizer_phone,
                1 as is_organizer,
                0 as is_participant
            FROM events e
            WHERE e.organizer_phone = ?
            ORDER BY e.created_at DESC
        """, (user_phone,))
        organized = c.fetchall()

        c.execute("""
            SELECT 
                e.id, e.name, e.date, e.time, e.address, e.interests, 
                e.description, e.organizer_phone,
                0 as is_organizer,
                1 as is_participant
            FROM events e
            JOIN event_participants ep ON e.id = ep.event_id
            WHERE ep.participant_phone = ?
            ORDER BY e.created_at DESC
        """, (user_phone,))
        participated = c.fetchall()
        
        return organized, participated

def join_event_db(event_id: int, phone: str):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        try:
            c.execute("""
                INSERT INTO event_participants (event_id, participant_phone)
                VALUES (?, ?)
            """, (event_id, phone))
            conn.commit()
            return True, None
        except sqlite3.IntegrityError:
            return False, "already_joined"
        except Exception as e:
            return False, str(e)

def leave_event_db(event_id: int, phone: str):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            
            c.execute("""
                SELECT e.organizer_phone 
                FROM events e
                WHERE e.id = ?
            """, (event_id,))
            result = c.fetchone()
            
            if not result:
                return False, "not_found", None
            
            organizer_phone = result[0]
            
            c.execute("""
                DELETE FROM event_participants 
                WHERE event_id = ? AND participant_phone = ?
            """, (event_id, phone))
            
            if c.rowcount == 0:
                return False, "not_participating", None
            
            conn.commit()
            return True, "success", organizer_phone
    except Exception as e:
        return False, str(e), None

def get_event_by_id(event_id: int):
    """Get event details by ID including coordinates."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("""
                SELECT id, name, date, time, address, latitude, longitude,
                       interests, description, organizer_phone, 
                       photo_file_id, document_file_id
                FROM events WHERE id = ?
            """, (event_id,))
            row = c.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logging.error(f"Error getting event by id: {e}")
        return None

def get_event_participants(event_id: int):
    """Get list of participants for an event in format [name, surname, age]."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("""
                SELECT u.name, u.surname, u.age
                FROM event_participants ep
                JOIN users u ON ep.participant_phone = u.number
                WHERE ep.event_id = ?
                ORDER BY u.name, u.surname
            """, (event_id,))
            return c.fetchall()
    except Exception as e:
        logging.error(f"Error getting event participants: {e}")
        return []
