import re
from datetime import datetime
from html import escape as html_escape

def is_valid_name(text: str) -> bool:
    return bool(re.match(r'^[a-zA-Zа-яА-ЯёЁ\s-]+$', text))

def is_valid_age(text: str) -> bool:
    return text.isdigit() and 0 < int(text) < 120

def escape_html(text: str) -> str:
    """Escape HTML special characters to prevent injection attacks."""
    if text is None:
        return ""
    return html_escape(str(text))

def normalize_phone(phone: str) -> str:
    """
    Normalize phone number to consistent format with +.
    Examples: 79001234567 -> +79001234567, 89001234567 -> +79001234567
    """
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
    """Check if string is a valid date in DD.MM.YYYY format."""
    try:
        datetime.strptime(date_text, '%d.%m.%Y')
        return True
    except ValueError:
        return False

def is_valid_time(time_text: str) -> bool:
    """Check if string is a valid time in HH:MM format."""
    try:
        datetime.strptime(time_text, '%H:%M')
        return True
    except ValueError:
        return False
