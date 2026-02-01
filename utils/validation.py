import re
from html import escape as html_escape

def is_valid_name(text: str) -> bool:
    return bool(re.match(r'^[a-zA-Zа-яА-ЯёЁ]+$', text))

def is_valid_age(text: str) -> bool:
    return text.isdigit() and 0 < int(text) < 120

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
        cleaned = '+7' + cleaned[1:]
    elif cleaned.startswith('7') and len(cleaned) == 11:
        cleaned = '+' + cleaned
    elif not cleaned.startswith('+'):
        cleaned = '+' + cleaned
    
    return cleaned
