import re
from datetime import datetime
from html import escape as html_escape

def is_valid_name(text: str) -> bool:
    return bool(re.match(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', text))

def is_valid_age(text: str) -> bool:
    if not text.isdigit():
        return False
    age = int(text)
    return 15 <= age <= 100

def escape_html(text: str) -> str:
    if text is None:
        return ""
    return html_escape(str(text))

def normalize_phone(phone: str) -> str:
   
    if not phone:
        return phone
    
    cleaned = re.sub(r'[^\d+]', '', phone)
    
    if cleaned.startswith('8') and len(cleaned) == 11:
        cleaned = '+7' + cleaned[1:]
    elif cleaned.startswith('7') and len(cleaned) == 11:
        cleaned = '+' + cleaned
    elif not cleaned.startswith('+'):
        cleaned = '+' + cleaned
    
    return cleaned

def is_valid_date(date_text: str) -> bool:
    try:
        datetime.strptime(date_text, '%d.%m.%Y')
        return True
    except ValueError:
        return False

def is_valid_time(time_text: str) -> bool:
    try:
        datetime.strptime(time_text, '%H:%M')
        return True
    except ValueError:
        return False
