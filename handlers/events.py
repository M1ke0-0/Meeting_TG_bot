import logging
import asyncio
import re
import uuid
import os
from datetime import datetime
from aiogram import Router, F, types
from aiogram.types import Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

from states.states import CreateEvent
from keyboards.builders import (
    get_interests_keyboard, get_description_keyboard, get_photo_keyboard,
    get_user_main_menu, get_events_menu_keyboard, get_event_card_keyboard_optimized,
    get_my_event_card_keyboard, get_event_creation_keyboard
)
from utils.validation import escape_html, is_valid_date, is_valid_time

from database import get_session
from database.repositories import (
    EventRepository, ParticipantRepository, InviteRepository, 
    UserRepository, InterestRepository, FriendRepository
)

router = Router()

def mask_phone(phone: str) -> str:
    """Mask phone number for privacy, showing only last 4 digits."""
    if not phone or len(phone) < 4:
        return "***"
    return f"***{phone[-4:]}"

async def get_event_card_text(event: dict, session=None):
    """Формирует текст карточки мероприятия с экранированием HTML"""
    safe_name = escape_html(event.get('name', ''))
    safe_date = escape_html(event.get('date', ''))
    safe_time = escape_html(event.get('time', ''))
    safe_address = escape_html(event.get('address') or 'не указан')
    safe_desc = escape_html(event.get('description') or 'нет описания')
    safe_interests = escape_html(event.get('interests') or '')
    
    organizer_phone = event.get('organizer_phone')
    masked_organizer = mask_phone(organizer_phone)
    
    # Try to get organizer name
    organizer_name = masked_organizer
    if session:
        user_repo = UserRepository(session)
        organizer = await user_repo.get_by_phone(organizer_phone)
        if organizer:
            organizer_name = f"{organizer.name or ''} {organizer.surname or ''}".strip() or masked_organizer
    
    safe_organizer = escape_html(organizer_name)

    return (
        f"📅 <b>{safe_name}</b>\n"
        f"🕒 {safe_date} в {safe_time}\n"
        f"📍 {safe_address}\n"
        f"👤 Организатор: {safe_organizer}\n"
        f"📋 {safe_desc}\n"
        f"🏷 {safe_interests}"
    )


@router.message(F.text == "🎉 Мероприятия")
async def events_menu(message: Message):
    await message.answer("Выберите действие:", reply_markup=get_events_menu_keyboard())

# --- Creating Events ---

@router.message(F.text == "Создать мероприятие")
async def create_event_start(message: Message, state: FSMContext, user: dict | None):
    if not user:
        await message.answer("Ошибка: пользователь не найден.")
        return
        
    await state.clear()
    await message.answer(
        "Введите название мероприятия:", 
        reply_markup=get_event_creation_keyboard()
    )
    await state.set_state(CreateEvent.name)


@router.message(F.text == "❌ Отменить создание")
async def cancel_creation(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Создание отменено.", reply_markup=get_events_menu_keyboard())


@router.message(CreateEvent.name)
async def event_name(message: Message, state: FSMContext):
    if not message.text:
        return
    await state.update_data(name=message.text)
    await message.answer("Введите дату (ДД.ММ.ГГГГ):", reply_markup=get_event_creation_keyboard())
    await state.set_state(CreateEvent.date)


@router.message(CreateEvent.date)
async def event_date(message: Message, state: FSMContext):
    if not is_valid_date(message.text):
        await message.answer("🚫 Неверный формат даты. Используйте ДД.ММ.ГГГГ (например, 25.12.2025)")
        return
    await state.update_data(date=message.text)
    await message.answer("Введите время (ЧЧ:ММ):", reply_markup=get_event_creation_keyboard())
    await state.set_state(CreateEvent.time)


@router.message(CreateEvent.time)
async def event_time(message: Message, state: FSMContext):
    if not is_valid_time(message.text):
        await message.answer("🚫 Неверный формат времени. Используйте ЧЧ:ММ (например, 18:30)")
        return
    await state.update_data(time=message.text)
    
    # Fetch interests async
    async with get_session() as session:
        interest_repo = InterestRepository(session)
        interests_list = await interest_repo.get_all_names()
    
    await message.answer(
        "Выберите интересы (теги) мероприятия:",
        reply_markup=get_interests_keyboard(interests_list, [])
    )
    await state.set_state(CreateEvent.interests)


@router.callback_query(CreateEvent.interests)
async def event_interests_callback(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    interests = data.get('interests', [])

    if callback.data == "done":
        if not interests:
            await callback.answer("🚫 Укажите хотя бы один интерес.")
            return
        await state.update_data(interests=interests)
        await state.set_state(CreateEvent.address)
        await callback.message.answer(
            "Введите адрес мероприятия (или отправьте геолокацию 📎):",
            reply_markup=get_event_creation_keyboard()
        )
        await callback.answer()
        return

    # Check for ignore edit profile callback
    if callback.data == "keep_current": 
        await callback.answer()
        return

    if callback.data in interests:
        interests.remove(callback.data)
    else:
        interests.append(callback.data)

    await state.update_data(interests=interests)
    
    # Fetch interests async
    async with get_session() as session:
        interest_repo = InterestRepository(session)
        interests_list = await interest_repo.get_all_names()
        
    await callback.message.edit_reply_markup(
        reply_markup=get_interests_keyboard(interests_list, interests)
    )
    await callback.answer()


from utils.geocoding import get_coordinates

@router.message(CreateEvent.address)
async def event_address(message: Message, state: FSMContext):
    if message.location:
        lat, lon = message.location.latitude, message.location.longitude
        addr_str = f"Геолокация: {lat}, {lon}"
        
        # Try to reverse geocode if possible (optional, maybe later)
        await state.update_data(address=addr_str, latitude=lat, longitude=lon)
        
        await message.answer(
            "Введите описание мероприятия (или нажмите «Пропустить»):",
            reply_markup=get_description_keyboard()
        )
        await state.set_state(CreateEvent.description)
        
    elif message.text:
        # Try to geocode
        await message.answer("🔍 Ищем адрес...")
        
        coordinates = await asyncio.to_thread(get_coordinates, message.text)
        
        if coordinates:
            lat, lon, formatted_addr = coordinates
            await state.update_data(
                 temp_address=formatted_addr, 
                 temp_lat=lat, 
                 temp_lon=lon
            )
            
            # Send location validation
            kb = types.ReplyKeyboardMarkup(
                keyboard=[
                    [types.KeyboardButton(text="Да, верно")],
                    [types.KeyboardButton(text="Нет, ввести заново")]
                ],
                resize_keyboard=True
            )
            
            await message.bot.send_location(chat_id=message.chat.id, latitude=lat, longitude=lon)
            await message.answer(
                f"Мы нашли этот адрес:\n📍 {formatted_addr}\n\nЭто верное место?", 
                reply_markup=kb
            )
            await state.set_state(CreateEvent.confirm_address)
        else:
            await message.answer(
                "❌ Не удалось найти такой адрес.\nПопробуйте уточнить (например, добавьте город) или используйте кнопку «Отправить геолокацию» 📎."
            )
            return

    else:
        await message.answer("Введите адрес текстом или отправьте геометку.")
        return


@router.message(CreateEvent.confirm_address)
async def confirm_address_handler(message: Message, state: FSMContext):
    if message.text == "Да, верно":
        data = await state.get_data()
        
        await state.update_data(
            address=data.get("temp_address"),
            latitude=data.get("temp_lat"),
            longitude=data.get("temp_lon")
        )
        
        await message.answer(
            "Адрес сохранен!\nВведите описание мероприятия (или нажмите «Пропустить»):",
            reply_markup=get_description_keyboard()
        )
        await state.set_state(CreateEvent.description)
        
    else:
        await message.answer(
            "Хорошо, введите адрес еще раз:",
            reply_markup=get_event_creation_keyboard()
        )
        await state.set_state(CreateEvent.address)



@router.message(CreateEvent.description)
async def event_description(message: Message, state: FSMContext):
    text = message.text
    if text == "Пропустить":
        desc = ""
    else:
        desc = text

    await state.update_data(description=desc)
    await message.answer(
        "Прикрепите фото/документ (или нажмите «Пропустить»):",
        reply_markup=get_photo_keyboard()
    )
    await state.set_state(CreateEvent.photo)


@router.message(CreateEvent.photo)
async def event_photo(message: Message, state: FSMContext):
    if message.text == "Пропустить":
        await state.update_data(photo_file_id=None, document_file_id=None)
    elif message.photo:
        await state.update_data(
            photo_file_id=message.photo[-1].file_id, 
            document_file_id=None
        )
    elif message.document:
        doc = message.document
        if doc.mime_type and doc.mime_type.startswith("image/"):
             await state.update_data(
                 document_file_id=doc.file_id, 
                 photo_file_id=None
             )
        else:
            await message.answer("Пожалуйста, отправьте изображение (как фото или файл).")
            return
    else:
        await message.answer("Отправьте фото или нажмите «Пропустить».")
        return
    
    await state.set_state(CreateEvent.invite_friends)
    
    # Ask about inviting friends
    kb = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Да, пригласить")],
            [types.KeyboardButton(text="Нет, создать так")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer("Хотите пригласить друзей, которым это может быть интересно?", reply_markup=kb)


@router.message(CreateEvent.invite_friends)
async def event_invite_friends(message: Message, state: FSMContext, user: dict | None):
    data = await state.get_data()
    invite = (message.text == "Да, пригласить")
    
    notifications_to_send = []
    invited_count = 0
    
    async with get_session() as session:
        event_repo = EventRepository(session)
        event_id = await event_repo.create(user["number"], data)
        
        if not event_id:
            await message.answer("Ошибка при создании мероприятия.", reply_markup=get_events_menu_keyboard())
            await state.clear()
            return
            
        if invite:
            user_repo = UserRepository(session)
            invite_repo = InviteRepository(session)
            
            # Find friends with matching interests
            potential_friends = await user_repo.find_potential_friends(
                user["number"], 
                data.get("interests", [])
            )
            
            for friend in potential_friends:
                # Add invite
                if await invite_repo.create_invite(event_id, friend["phone"]):
                    invited_count += 1
                    # Collect data for notification
                    if friend.get("tg_id"):
                        notifications_to_send.append(friend["tg_id"])
    
    # Send notifications after DB transaction is committed
    if notifications_to_send:
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="✅ Принять", callback_data=f"invite_accept_{event_id}")],
            [types.InlineKeyboardButton(text="❌ Отклонить", callback_data=f"invite_decline_{event_id}")]
        ])
        
        for tg_id in notifications_to_send:
            try:
                await message.bot.send_message(
                    tg_id,
                    f"Вас приглашают на мероприятие «{data['name']}»!",
                    reply_markup=markup
                )
            except Exception as e:
                logging.error(f"Failed to send invite to tg_id {tg_id}: {e}")

    await message.answer(
        f"Мероприятие «{data['name']}» создано! 🎉\n" +
        (f"Приглашено друзей: {invited_count}" if invite else ""),
        reply_markup=get_events_menu_keyboard()
    )
    await state.clear()


# --- Viewing Events ---

@router.message(F.text == "Мероприятия друзей")
async def view_friends_events(message: Message, user: dict | None):
    if not user: 
        return
    
    async with get_session() as session:
        event_repo = EventRepository(session)
        events = await event_repo.get_friends_events(user["number"])
    
    if not events:
        await message.answer("Ваши друзья пока не создали мероприятий.", reply_markup=get_events_menu_keyboard())
        return

    for event_row in events:
        # Tuple format from repo:
        # id, name, date, time, address, interests, description, organizer_phone, is_participant
        try:
            (eid, name, date, time, addr, interests, desc, org_phone, lat, lon, is_part) = event_row
            
            event_dict = {
                "name": name,
                "date": date,
                "time": time,
                "address": addr,
                "description": desc,
                "interests": interests,
                "organizer_phone": org_phone
            }
            
            async with get_session() as session:
                caption = await get_event_card_text(event_dict, session)
            
            kb = get_event_card_keyboard_optimized(
                event_id=eid,
                user_phone=user["number"],
                organizer_phone=org_phone,
                is_participant=bool(is_part)
            )
            
            await message.answer(caption, reply_markup=kb, parse_mode=ParseMode.HTML)
        except Exception as e:
            logging.error(f"Error displaying event {event_row}: {e}")


@router.message(F.text == "Мои мероприятия")
async def view_my_events(message: Message, user: dict | None):
    if not user: 
        return
    
    async with get_session() as session:
        event_repo = EventRepository(session)
        organized, participated = await event_repo.get_my_events(user["number"])
    
    if not organized and not participated:
        await message.answer("Вы пока не создали и не участвуете ни в одном мероприятии.", reply_markup=get_events_menu_keyboard())
        return

    async with get_session() as session:
        if organized:
            await message.answer("<b>Вы организатор:</b>", parse_mode=ParseMode.HTML)
            for e_row in organized:
                # id, name, date, time, address, interests, desc, org_phone, is_org, is_part
                eid = e_row[0]
                event_dict = {
                    "name": e_row[1], "date": e_row[2], "time": e_row[3],
                    "address": e_row[4], "interests": e_row[5], "description": e_row[6],
                    "organizer_phone": e_row[7]
                }
                caption = await get_event_card_text(event_dict, session)
                kb = get_my_event_card_keyboard(eid, is_organizer=True)
                await message.answer(caption, reply_markup=kb, parse_mode=ParseMode.HTML)

        if participated:
            await message.answer("<b>Вы участвуете:</b>", parse_mode=ParseMode.HTML)
            for e_row in participated:
                eid = e_row[0]
                event_dict = {
                    "name": e_row[1], "date": e_row[2], "time": e_row[3],
                    "address": e_row[4], "interests": e_row[5], "description": e_row[6],
                    "organizer_phone": e_row[7]
                }
                caption = await get_event_card_text(event_dict, session)
                kb = get_my_event_card_keyboard(eid, is_organizer=False)
                await message.answer(caption, reply_markup=kb, parse_mode=ParseMode.HTML)


# --- Event Actions ---

@router.callback_query(F.data.startswith("join_event_"))
async def join_event_handler(callback: types.CallbackQuery, user: dict | None):
    event_id = int(callback.data.split("_")[2])
    
    async with get_session() as session:
        part_repo = ParticipantRepository(session)
        success, msg = await part_repo.join_event(event_id, user["number"])
        
        if success:
            await callback.answer("Вы успешно записались!", show_alert=True)
            # Update message to show "Leave" button
            event_repo = EventRepository(session)
            event = await event_repo.get_by_id(event_id)
            if event:
                kb = get_event_card_keyboard_optimized(
                    event_id, user["number"], event["organizer_phone"], is_participant=True
                )
                await callback.message.edit_reply_markup(reply_markup=kb)
        else:
            if msg == "already_joined":
                await callback.answer("Вы уже участвуете.", show_alert=True)
            else:
                await callback.answer("Ошибка при записи.", show_alert=True)


@router.callback_query(F.data.startswith("leave_event_"))
async def leave_event_handler(callback: types.CallbackQuery, user: dict | None):
    event_id = int(callback.data.split("_")[2])
    
    async with get_session() as session:
        part_repo = ParticipantRepository(session)
        success, msg, organizer_phone = await part_repo.leave_event(event_id, user["number"])
        
        if success:
            await callback.answer("Вы отказались от участия.", show_alert=True)
            
            # Notify organizer if possible
            if organizer_phone:
                user_repo = UserRepository(session)
                organizer = await user_repo.get_by_phone(organizer_phone)
                
                if organizer and organizer.tg_id:
                    try:
                        participant_name = f"{user.get('name', '')} {user.get('surname', '')}".strip()
                        await callback.bot.send_message(
                            organizer.tg_id,
                            f"⚠️ Пользователь {participant_name} отказался от участия в вашем мероприятии."
                        )
                    except Exception as e:
                        logging.error(f"Failed to notify organizer: {e}")
            
            # Update card
            event_repo = EventRepository(session)
            event = await event_repo.get_by_id(event_id)
            if event:
                kb = get_event_card_keyboard_optimized(
                    event_id, user["number"], event["organizer_phone"], is_participant=False
                )
                await callback.message.edit_reply_markup(reply_markup=kb)
            else:
                await callback.message.delete()
        else:
            await callback.answer("Ошибка при выходе.", show_alert=True)


@router.callback_query(F.data.startswith("view_map_"))
async def view_map(callback: types.CallbackQuery):
    event_id = int(callback.data.split("_")[2])
    
    async with get_session() as session:
        event_repo = EventRepository(session)
        event = await event_repo.get_by_id(event_id)
        
    if event and event.get("latitude") and event.get("longitude"):
        await callback.message.answer_location(
            latitude=event["latitude"], 
            longitude=event["longitude"]
        )
        await callback.answer()
    else:
        await callback.answer("Координаты не указаны.", show_alert=True)


@router.callback_query(F.data.startswith("view_participants_"))
async def view_participants(callback: types.CallbackQuery):
    event_id = int(callback.data.split("_")[2])
    
    async with get_session() as session:
        part_repo = ParticipantRepository(session)
        participants = await part_repo.get_participants(event_id)
        
    if not participants:
        await callback.answer("Участников пока нет.", show_alert=True)
        return
        
    text = "👥 <b>Участники:</b>\n\n"
    for p in participants:
        name, surname, age = p
        text += f"• {name} {surname or ''}"
        if age:
            text += f" ({age} лет)"
        text += "\n"
        
    await callback.message.answer(text, parse_mode=ParseMode.HTML)
    await callback.answer()


@router.callback_query(F.data.startswith("invite_to_event_"))
async def invite_users_to_event(callback: types.CallbackQuery, user: dict | None):
    # Retrieve event to get interests etc
    event_id = int(callback.data.split("_")[3])
    
    async with get_session() as session:
        event_repo = EventRepository(session)
        event = await event_repo.get_by_id(event_id)
        
        if not event:
            await callback.answer("Мероприятие не найдено")
            return
            
        # Find potential friends
        interests = event.get('interests', '').split(",") if event.get('interests') else []
        user_repo = UserRepository(session)
        potential = await user_repo.find_potential_friends(user['number'], interests)
    
    if not potential:
        await callback.answer("Подходящих пользователей не найдено.", show_alert=True)
        return
        
    # Send invites
    invited_count = 0
    async with get_session() as session:
        invite_repo = InviteRepository(session)
        
        for friend in potential:
            if await invite_repo.create_invite(event_id, friend["phone"]):
                invited_count += 1
                try:
                    markup = types.InlineKeyboardMarkup(inline_keyboard=[
                        [types.InlineKeyboardButton(text="✅ Принять", callback_data=f"invite_accept_{event_id}")],
                        [types.InlineKeyboardButton(text="❌ Отклонить", callback_data=f"invite_decline_{event_id}")]
                    ])
                    if friend.get("tg_id"):
                        await callback.bot.send_message(
                            friend["tg_id"],
                            f"Вас приглашают на мероприятие «{event['name']}»!",
                            reply_markup=markup
                        )
                except Exception as e:
                    pass

    await callback.answer(f"Приглашения отправлены: {invited_count}", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("invite_accept_"))
async def process_invite_accept(callback: types.CallbackQuery, user: dict | None):
    if user is None:
        await callback.answer("Ошибка пользователя.", show_alert=True)
        return
        
    try:
        event_id = int(callback.data.split("_")[2])
    except:
        return
    
    async with get_session() as session:
        part_repo = ParticipantRepository(session)
        success, reason = await part_repo.join_event(event_id, user['number'])
    
    if success:
        await callback.message.edit_text(
            f"{callback.message.text}\n\n✅ <b>Вы приняли приглашение!</b>",
            reply_markup=None,
            parse_mode=ParseMode.HTML
        )
        
        # Notify organizer
        async with get_session() as session:
            event_repo = EventRepository(session)
            event = await event_repo.get_by_id(event_id)
            
        if event and event.get('organizer_tg_id'):
            organizer_id = event['organizer_tg_id']
            if organizer_id != user['tg_id']:
                try:
                    participant_name = f"{user.get('name', '')} {user.get('surname', '')}".strip()
                    await callback.bot.send_message(
                        organizer_id,
                        f"🎉 <b>{participant_name}</b> принял(а) ваше приглашение на мероприятие «{event['name']}»!"
                    )
                except Exception as e:
                    logging.error(f"Failed to notify organizer {organizer_id}: {e}")
    else:
        if reason == "already_joined":
            await callback.message.edit_text(
                f"{callback.message.text}\n\nℹ️ <b>Вы уже участвуете.</b>",
                reply_markup=None,
                parse_mode=ParseMode.HTML
            )
        else:
            await callback.answer(f"Ошибка при вступлении: {reason}", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("invite_decline_"))
async def process_invite_decline(callback: types.CallbackQuery, user: dict | None):
    if user is None:
        await callback.answer("Ошибка пользователя.", show_alert=True)
        return
        
    try:
        event_id = int(callback.data.split("_")[2])
    except:
        return
    
    async with get_session() as session:
        invite_repo = InviteRepository(session)
        await invite_repo.update_status(event_id, user['number'], 'declined')
        
        event_repo = EventRepository(session)
        event = await event_repo.get_by_id(event_id)
    
    await callback.message.edit_text(
        f"{callback.message.text}\n\n❌ <b>Вы отклонили приглашение.</b>",
        reply_markup=None,
        parse_mode=ParseMode.HTML
    )

    if event and event.get('organizer_tg_id'):
        organizer_id = event['organizer_tg_id']
        if organizer_id != user['tg_id']:
            try:
                participant_name = f"{user.get('name', '')} {user.get('surname', '')}".strip()
                await callback.bot.send_message(
                    organizer_id,
                    f"😔 <b>{participant_name}</b> отклонил(а) ваше приглашение на мероприятие «{event['name']}»."
                )
            except Exception as e:
                logging.error(f"Failed to notify organizer {organizer_id} of decline: {e}")
