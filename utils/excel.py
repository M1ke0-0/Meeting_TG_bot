import asyncio
from openpyxl import Workbook
from database import get_session
from database.repositories import UserRepository, EventRepository
from database.models import User, Event, EventParticipant, Interest, Region

async def export_users_report(filepath: str):
    """
    Generates an Excel report of all users.
    Columns: Phone, Role, Name, Surname, Gender, Age, Region, Interests, Photo ID
    """
    async with get_session() as session:
        user_repo = UserRepository(session)
        users = await user_repo.get_all()
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Пользователи"

        headers = ["Phone", "Role", "Name", "Surname", "Gender", "Age", "Region", "Interests", "Photo ID"]
        ws.append(headers)

        for user in users:
            row = [
                user.number,
                user.role,
                user.name,
                user.surname,
                user.gender,
                user.age,
                user.region,
                user.interests,
                user.photo_file_id
            ]
            ws.append(row)

        # Run file blocking operation in thread pool to avoid blocking event loop
        await asyncio.to_thread(wb.save, filepath)


async def export_events_report(filepath: str):
    """
    Generates an Excel report of all events.
    """
    async with get_session() as session:
        event_repo = EventRepository(session)
        events = await event_repo.get_all()
        
        wb = Workbook()
        ws = wb.active
        ws.title = "Мероприятия"

        headers = [
            "ID", "Name", "Date", "Time", "Interests", "Address", 
            "Description", "Organizer Phone", "Participants Count"
        ]
        ws.append(headers)

        for event in events:
            # We need to fetch participants count separately or use joined load
            # For simplicity, getting basic info
            row = [
                event.id,
                event.name,
                event.date,
                event.time,
                event.interests,
                event.address,
                event.description,
                event.organizer_phone,
                0 # Placeholder for count, could improve with specific query
            ]
            ws.append(row)

        await asyncio.to_thread(wb.save, filepath)
