import sqlite3
from openpyxl import Workbook
from config import DB_PATH

def export_users_report(filepath: str):
    """
    Generates an Excel report of all users.
    Columns: Phone, Role, Name, Surname, Gender, Age, Region, Interests, Photo ID
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT number, role, name, surname, gender, age, region, interests, photo_file_id 
        FROM users 
        ORDER BY created_at DESC
    """)
    rows = c.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Пользователи"

    headers = ["Phone", "Role", "Name", "Surname", "Gender", "Age", "Region", "Interests", "Photo ID"]
    ws.append(headers)

    for row in rows:
        ws.append(list(row))  

    wb.save(filepath)

def export_events_report(filepath: str):
    """
    Generates an Excel report of all events.
    Columns: ID, Name, Date, Time, Interests, Address, Description, Organizer Phone, 
             Organizer Name, Organizer Surname, Photo File ID, Document File ID, Participants Count
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT 
            e.id, 
            e.name, 
            e.date, 
            e.time, 
            e.interests, 
            e.address, 
            e.description, 
            e.organizer_phone,
            u.name as organizer_name,
            u.surname as organizer_surname,
            e.photo_file_id,
            e.document_file_id,
            COUNT(ep.participant_phone) as participants_count
        FROM events e
        LEFT JOIN users u ON e.organizer_phone = u.number
        LEFT JOIN event_participants ep ON e.id = ep.event_id
        GROUP BY e.id
        ORDER BY e.created_at DESC
    """)
    rows = c.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Мероприятия"

    headers = [
        "ID", "Name", "Date", "Time", "Interests", "Address", 
        "Description", "Organizer Phone", "Organizer Name", "Organizer Surname",
        "Photo File ID", "Document File ID", "Participants Count"
    ]
    ws.append(headers)

    for row in rows:
        ws.append(list(row)) 

    wb.save(filepath)

