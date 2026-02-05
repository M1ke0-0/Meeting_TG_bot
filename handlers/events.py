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
    get_my_event_card_keyboard, get_event_creation_keyboard, get_friends_select_keyboard,
    get_participants_manage_keyboard
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

    if callback.data == "keep_current": 
        await callback.answer()
        return

    if callback.data in interests:
        interests.remove(callback.data)
    else:
        interests.append(callback.data)

    await state.update_data(interests=interests)
    
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
        
        await state.update_data(address=addr_str, latitude=lat, longitude=lon)
        
        await message.answer(
            "Введите описание мероприятия (или нажмите «Пропустить»):",
            reply_markup=get_description_keyboard()
        )
        await state.set_state(CreateEvent.description)
        
    elif message.text:
        await message.answer("🔍 Ищем адрес...")
        
        coordinates = await asyncio.to_thread(get_coordinates, message.text)
        
        if coordinates:
            lat, lon, formatted_addr = coordinates
            await state.update_data(
                 temp_address=formatted_addr, 
                 temp_lat=lat, 
                 temp_lon=lon
            )
            
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
    
    if message.text == "Да, пригласить":
        async with get_session() as session:
            friend_repo = FriendRepository(session)
            friends = await friend_repo.get_friends(user['tg_id'])
        
        if not friends:
            await _create_event_without_invites(message, state, user, data)
            return
        
        await state.update_data(selected_friends=[])
        await state.set_state(CreateEvent.select_friends)
        
        await message.answer(
            "Выберите друзей для приглашения:\n(нажмите на друга чтобы выбрать/отменить)",
            reply_markup=get_friends_select_keyboard(friends, [])
        )
    else:
        await _create_event_without_invites(message, state, user, data)


async def _create_event_without_invites(message: Message, state: FSMContext, user: dict, data: dict):
    """Helper to create event without inviting anyone."""
    async with get_session() as session:
        event_repo = EventRepository(session)
        event_id = await event_repo.create(user["number"], data)
        
        if not event_id:
            await message.answer("Ошибка при создании мероприятия.", reply_markup=get_events_menu_keyboard())
            await state.clear()
            return
    
    await message.answer(
        f"Мероприятие «{data['name']}» создано! 🎉",
        reply_markup=get_events_menu_keyboard()
    )
    await state.clear()


@router.callback_query(CreateEvent.select_friends)
async def select_friends_callback(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    data = await state.get_data()
    selected = data.get('selected_friends', [])
    
    if callback.data == "cancel_invites":
        await _create_event_without_invites(callback.message, state, user, data)
        await callback.answer()
        return
    
    if callback.data == "sel_all_friends":
        async with get_session() as session:
            friend_repo = FriendRepository(session)
            friends = await friend_repo.get_friends(user['tg_id'])
        selected = [f['tg_id'] for f in friends if f.get('tg_id')]
        await state.update_data(selected_friends=selected)
        await callback.message.edit_reply_markup(
            reply_markup=get_friends_select_keyboard(friends, selected)
        )
        await callback.answer("Все друзья выбраны")
        return
    
    if callback.data == "send_invites":
        if not selected:
            await callback.answer("Выберите хотя бы одного друга!", show_alert=True)
            return
        
        await _create_event_with_invites(callback, state, user, data, selected)
        return
    
    if callback.data.startswith("sel_friend_"):
        friend_tg_id = int(callback.data.split("_")[2])
        
        if friend_tg_id in selected:
            selected.remove(friend_tg_id)
        else:
            selected.append(friend_tg_id)
        
        await state.update_data(selected_friends=selected)
        
        async with get_session() as session:
            friend_repo = FriendRepository(session)
            friends = await friend_repo.get_friends(user['tg_id'])
        
        await callback.message.edit_reply_markup(
            reply_markup=get_friends_select_keyboard(friends, selected)
        )
        await callback.answer()


async def _create_event_with_invites(
    callback: types.CallbackQuery, state: FSMContext, 
    user: dict, data: dict, selected_tg_ids: list
):
    """Create event and send invites to selected friends."""
    notifications_to_send = []
    invited_count = 0
    
    async with get_session() as session:
        event_repo = EventRepository(session)
        event_id = await event_repo.create(user["number"], data)
        
        if not event_id:
            await callback.message.answer("Ошибка при создании мероприятия.", reply_markup=get_events_menu_keyboard())
            await state.clear()
            await callback.answer()
            return
        
        user_repo = UserRepository(session)
        invite_repo = InviteRepository(session)
        
        for tg_id in selected_tg_ids:
            friend_user = await user_repo.get_by_tg_id(tg_id)
            if friend_user and friend_user.number:
                if await invite_repo.create_invite(event_id, friend_user.number):
                    invited_count += 1
                    notifications_to_send.append(tg_id)
    
    if notifications_to_send:
        my_name = f"{user.get('name', '')} {user.get('surname', '')}".strip()
        markup = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="✅ Принять", callback_data=f"invite_accept_{event_id}")],
            [types.InlineKeyboardButton(text="❌ Отклонить", callback_data=f"invite_decline_{event_id}")]
        ])
        
        for tg_id in notifications_to_send:
            try:
                await callback.bot.send_message(
                    tg_id,
                    f"📩 <b>{my_name}</b> приглашает вас на мероприятие «{data['name']}»!",
                    reply_markup=markup,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logging.error(f"Failed to send invite to tg_id {tg_id}: {e}")
    
    await callback.message.edit_text(
        f"Мероприятие «{data['name']}» создано! 🎉\n"
        f"Приглашено друзей: {invited_count}"
    )
    await callback.message.answer("Выберите действие:", reply_markup=get_events_menu_keyboard())
    await state.clear()
    await callback.answer()



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



@router.callback_query(F.data.startswith("join_event_"))
async def join_event_handler(callback: types.CallbackQuery, user: dict | None):
    event_id = int(callback.data.split("_")[2])
    
    async with get_session() as session:
        part_repo = ParticipantRepository(session)
        success, msg = await part_repo.join_event(event_id, user["number"])
        
        if success:
            await callback.answer("Вы успешно записались!", show_alert=True)
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
async def view_participants(callback: types.CallbackQuery, user: dict | None):
    event_id = int(callback.data.split("_")[2])
    
    async with get_session() as session:
        part_repo = ParticipantRepository(session)
        participants = await part_repo.get_participants(event_id)
        
        event_repo = EventRepository(session)
        event = await event_repo.get_by_id(event_id)
        is_organizer = event and event.get('organizer_phone') == user.get('number')
        
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
    
    if is_organizer:
        text += "\n<i>Нажмите «Управление», чтобы удалить участника</i>"
        kb = types.InlineKeyboardMarkup(inline_keyboard=[
            [types.InlineKeyboardButton(text="⚙️ Управление участниками", callback_data=f"manage_participants_{event_id}")]
        ])
        await callback.message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await callback.message.answer(text, parse_mode=ParseMode.HTML)
    
    await callback.answer()


@router.callback_query(F.data.startswith("manage_participants_"))
async def manage_participants(callback: types.CallbackQuery, user: dict | None):
    """Show participants with remove buttons for organizer."""
    event_id = int(callback.data.split("_")[2])
    
    async with get_session() as session:
        event_repo = EventRepository(session)
        event = await event_repo.get_by_id(event_id)
        
        if not event or event.get('organizer_phone') != user.get('number'):
            await callback.answer("Только организатор может управлять участниками.", show_alert=True)
            return
        
        part_repo = ParticipantRepository(session)
        participants = await part_repo.get_participants_with_details(event_id)
    
    if not participants:
        await callback.answer("Участников нет.", show_alert=True)
        return
    
    await callback.message.edit_text(
        "👥 <b>Управление участниками</b>\n\nНажмите, чтобы удалить участника:",
        reply_markup=get_participants_manage_keyboard(event_id, participants),
        parse_mode=ParseMode.HTML
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rm_part_"))
async def remove_participant_handler(callback: types.CallbackQuery, user: dict | None):
    """Remove a participant from event (organizer only)."""
    parts = callback.data.split("_")
    event_id = int(parts[2])
    phone_suffix = parts[3]  

    async with get_session() as session:
        event_repo = EventRepository(session)
        event = await event_repo.get_by_id(event_id)
        
        if not event or event.get('organizer_phone') != user.get('number'):
            await callback.answer("Только организатор может удалять участников.", show_alert=True)
            return
        
        part_repo = ParticipantRepository(session)
        participants = await part_repo.get_participants_with_details(event_id)
        
        target_participant = None
        for p in participants:
            phone, name, surname, tg_id = p
            if phone and phone.endswith(phone_suffix):
                target_participant = p
                break
        
        if not target_participant:
            await callback.answer("Участник не найден.", show_alert=True)
            return
        
        phone, name, surname, tg_id = target_participant
        success, removed_tg_id = await part_repo.remove_participant(event_id, phone)
        
        if success:
            display_name = f"{name or ''} {surname or ''}".strip() or "Пользователь"
            
            if removed_tg_id:
                organizer_name = f"{user.get('name', '')} {user.get('surname', '')}".strip()
                try:
                    await callback.bot.send_message(
                        removed_tg_id,
                        f"😔 Организатор ({organizer_name}) удалил вас из мероприятия «{event['name']}»."
                    )
                except Exception as e:
                    logging.error(f"Failed to notify removed participant: {e}")
            
            await callback.answer(f"Участник {display_name} удалён.", show_alert=True)
            
            updated_participants = await part_repo.get_participants_with_details(event_id)
            if updated_participants:
                await callback.message.edit_reply_markup(
                    reply_markup=get_participants_manage_keyboard(event_id, updated_participants)
                )
            else:
                await callback.message.edit_text("👥 Все участники удалены.")
        else:
            await callback.answer("Ошибка при удалении.", show_alert=True)


@router.callback_query(F.data.startswith("back_participants_"))
async def back_from_manage(callback: types.CallbackQuery):
    """Back to event menu from participant management."""
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data.startswith("invite_to_event_"))
async def invite_users_to_event(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    """Invite friends to an existing event (from My Events)."""
    event_id = int(callback.data.split("_")[3])
    
    async with get_session() as session:
        event_repo = EventRepository(session)
        event = await event_repo.get_by_id(event_id)
        
        if not event:
            await callback.answer("Мероприятие не найдено")
            return
        
        friend_repo = FriendRepository(session)
        friends = await friend_repo.get_friends(user['tg_id'])
    
    if not friends:
        await callback.answer("У вас пока нет друзей для приглашения.", show_alert=True)
        return
    
    await state.update_data(
        invite_event_id=event_id,
        invite_event_name=event['name'],
        selected_invite_friends=[]
    )
    
    await callback.message.answer(
        f"Выберите друзей для приглашения на «{event['name']}»:",
        reply_markup=get_friends_select_keyboard(friends, [])
    )
    await callback.answer()


@router.callback_query(lambda c: c.data in ["sel_all_friends", "send_invites", "cancel_invites"] or c.data.startswith("sel_friend_"))
async def handle_invite_selection(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    """Handle friend selection for existing event invites."""
    data = await state.get_data()
    
    if 'invite_event_id' not in data:
        return  
    
    event_id = data['invite_event_id']
    event_name = data['invite_event_name']
    selected = data.get('selected_invite_friends', [])
    
    if callback.data == "cancel_invites":
        await state.clear()
        await callback.message.delete()
        await callback.answer("Приглашение отменено")
        return
    
    if callback.data == "sel_all_friends":
        async with get_session() as session:
            friend_repo = FriendRepository(session)
            friends = await friend_repo.get_friends(user['tg_id'])
        selected = [f['tg_id'] for f in friends if f.get('tg_id')]
        await state.update_data(selected_invite_friends=selected)
        await callback.message.edit_reply_markup(
            reply_markup=get_friends_select_keyboard(friends, selected)
        )
        await callback.answer("Все друзья выбраны")
        return
    
    if callback.data == "send_invites":
        if not selected:
            await callback.answer("Выберите хотя бы одного друга!", show_alert=True)
            return
        
        invited_count = 0
        my_name = f"{user.get('name', '')} {user.get('surname', '')}".strip()
        
        async with get_session() as session:
            user_repo = UserRepository(session)
            invite_repo = InviteRepository(session)
            
            markup = types.InlineKeyboardMarkup(inline_keyboard=[
                [types.InlineKeyboardButton(text="✅ Принять", callback_data=f"invite_accept_{event_id}")],
                [types.InlineKeyboardButton(text="❌ Отклонить", callback_data=f"invite_decline_{event_id}")]
            ])
            
            for tg_id in selected:
                friend_user = await user_repo.get_by_tg_id(tg_id)
                if friend_user and friend_user.number:
                    if await invite_repo.create_invite(event_id, friend_user.number):
                        invited_count += 1
                        try:
                            await callback.bot.send_message(
                                tg_id,
                                f"📩 <b>{my_name}</b> приглашает вас на мероприятие «{event_name}»!",
                                reply_markup=markup,
                                parse_mode=ParseMode.HTML
                            )
                        except:
                            pass
        
        await state.clear()
        await callback.message.edit_text(f"✅ Приглашения отправлены: {invited_count}")
        await callback.answer()
        return
    
    if callback.data.startswith("sel_friend_"):
        friend_tg_id = int(callback.data.split("_")[2])
        
        if friend_tg_id in selected:
            selected.remove(friend_tg_id)
        else:
            selected.append(friend_tg_id)
        
        await state.update_data(selected_invite_friends=selected)
        
        async with get_session() as session:
            friend_repo = FriendRepository(session)
            friends = await friend_repo.get_friends(user['tg_id'])
        
        await callback.message.edit_reply_markup(
            reply_markup=get_friends_select_keyboard(friends, selected)
        )
        await callback.answer()


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
