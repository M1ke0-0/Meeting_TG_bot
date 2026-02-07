import asyncio
from openpyxl import Workbook
from database import get_session
from database.repositories import UserRepository, EventRepository
from database.models import User, Event, EventParticipant, Interest, Region

async def export_users_report(filepath: str):
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

        await asyncio.to_thread(wb.save, filepath)


async def export_events_report(filepath: str):

    from database.repositories import ParticipantRepository
    
    async with get_session() as session:
        event_repo = EventRepository(session)
        part_repo = ParticipantRepository(session)
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
            participants = await part_repo.get_participants(event.id)
            participant_count = len(participants) if participants else 0
            
            row = [
                event.id,
                event.name,
                event.date,
                event.time,
                event.interests,
                event.address,
                event.description,
                event.organizer_phone,
                participant_count
            ]
            ws.append(row)

        await asyncio.to_thread(wb.save, filepath)
