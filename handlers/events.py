import logging
import re
from datetime import datetime
from aiogram import Router, F, types
from aiogram.types import Message, ReplyKeyboardRemove, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

from states.states import CreateEvent
from keyboards.builders import (
    get_interests_keyboard, get_description_keyboard, get_photo_keyboard,
    get_user_main_menu, get_events_menu_keyboard, get_event_card_keyboard_optimized,
    get_my_event_card_keyboard, get_event_creation_keyboard
)
from database.events import (
    create_event_db, get_friends_events, get_my_events, join_event_db, leave_event_db, 
    get_event_card_text, get_event_by_id, get_event_participants
)
from database.users import find_potential_friends, get_friends_db
from utils.validation import escape_html

# ... (existing imports)

# Add these handlers before view_map_ or similar

@router.callback_query(lambda c: c.data.startswith("invite_more_"))
async def invite_more_handler(callback: types.CallbackQuery, user: dict | None):
    try:
        event_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных.", show_alert=True)
        return

    friends = get_friends_db(user["tg_id"])
    
    if not friends:
        await callback.answer("У вас пока нет друзей, которых можно пригласить.", show_alert=True)
        return
        
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for friend in friends:
        name = f"{friend['name']} {friend['surname']}".strip()
        row = f"[{name}]"
        kb.inline_keyboard.append([
             InlineKeyboardButton(
                text=row,
                callback_data=f"send_invite_{event_id}_{friend['tg_id']}" 
            )
        ])
    
    kb.inline_keyboard.append([InlineKeyboardButton(text="🔙 Закрыть", callback_data="close_invite_list")])
    
    await callback.message.answer("Выберите друга для приглашения:", reply_markup=kb)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("send_invite_"))
async def send_one_invite_handler(callback: types.CallbackQuery, user: dict | None):
    try:
        parts = callback.data.split("_")
        event_id = int(parts[2])
        friend_id = int(parts[3])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных.", show_alert=True)
        return

    event = get_event_by_id(event_id)
    if not event:
        await callback.answer("Мероприятие не найдено.", show_alert=True)
        return

    safe_name = escape_html(user['name'])
    event_name = escape_html(event['name'])
    
    msg_text = (
        f"👋 Привет! Друг {safe_name} приглашает тебя на мероприятие:\n"
        f"<b>{event_name}</b>\n\n"
        f"Посмотреть: <b>🎉 Мероприятия -> Мероприятия друзей</b>"
    )

    try:
        await callback.bot.send_message(friend_id, msg_text, parse_mode=ParseMode.HTML)
        await callback.answer("Приглашение отправлено! ✅", show_alert=True)
    except Exception as e:
        logging.error(f"Failed to send invite: {e}")
        await callback.answer("Не удалось отправить сообщение (возможно, бот заблокирован пользователем).", show_alert=True)


@router.callback_query(F.data == "close_invite_list")
async def close_invite_list(callback: types.CallbackQuery):
    await callback.message.delete()
from utils.geocoding import geocode_address

router = Router()

@router.message(F.text == "🎉 Мероприятия")
async def events_menu(message: Message, user: dict | None):
    if user is None or not user["registered"]:
        await message.answer("Сначала завершите регистрацию.")
        return

    await message.answer(
        "Раздел мероприятий 🎉",
        reply_markup=get_events_menu_keyboard()
    )

@router.message(F.text == "Создать мероприятие")
async def start_create_event(message: Message, state: FSMContext, user: dict | None):
    if user is None or not user["registered"]:
        await message.answer("Сначала зарегистрируйтесь.")
        return

    await state.set_state(CreateEvent.name)
    await message.answer(
        "Введите название мероприятия:\n"
        "(или нажмите /start для отмены)",
        reply_markup=get_event_creation_keyboard()
    )

@router.message(F.text == "❌ Отменить создание")
async def cancel_event_creation_global(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state and current_state.startswith("CreateEvent:"):
        await state.clear()
        await message.answer("Создание мероприятия отменено.", reply_markup=get_user_main_menu())
    else:
        await message.answer("Нет активного создания.", reply_markup=get_user_main_menu())

@router.message(CreateEvent.name)
async def process_event_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if not name:
        await message.answer("Название не может быть пустым.")
        return
    await state.update_data(name=name)
    await state.set_state(CreateEvent.date)
    await message.answer("Введите дату начала (ДД.ММ.ГГГГ):")

@router.message(CreateEvent.date)
async def process_event_date(message: Message, state: FSMContext):
    date_str = message.text.strip()

    if not re.match(r'^\d{2}\.\d{2}\.\d{4}$', date_str):
        await message.answer("Неверный формат. Пример: 15.03.2025")
        return

    try:
        event_date = datetime.strptime(date_str, "%d.%m.%Y")
    except ValueError:
        await message.answer("Такая дата не существует. Попробуйте ещё раз.")
        return

    today = datetime.now().date()
    if event_date.date() < today:
        await message.answer("Нельзя создавать мероприятие в прошлом 😅")
        return

    await state.update_data(date=date_str, event_date_obj=event_date)
    await state.set_state(CreateEvent.time)
    await message.answer("Введите время начала (ЧЧ:ММ):")

@router.message(CreateEvent.time)
async def process_event_time(message: Message, state: FSMContext):
    time_str = message.text.strip()

    if not re.match(r'^\d{2}:\d{2}$', time_str):
        await message.answer("Неверный формат. Пример: 18:30")
        return

    try:
        hours, minutes = map(int, time_str.split(":"))
        if not (0 <= hours <= 23 and 0 <= minutes <= 59):
            raise ValueError
    except ValueError:
        await message.answer("Такого времени не бывает. Попробуйте ещё раз.")
        return

    data = await state.get_data()
    event_date = data.get("event_date_obj")

    now = datetime.now()
    if event_date and event_date.date() == now.date():
        event_datetime = datetime.combine(event_date.date(), datetime.strptime(time_str, "%H:%M").time())
        if event_datetime <= now:
            await message.answer("Нельзя создавать мероприятие в прошлом или в текущий момент.")
            return

    await state.update_data(time=time_str)
    await state.set_state(CreateEvent.interests)
    await message.answer(
        "Выберите интересы мероприятия (можно несколько):",
        reply_markup=get_interests_keyboard([], edit_mode=False)
    )

@router.callback_query(CreateEvent.interests)
async def process_event_interests(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    interests = data.get('interests', [])

    if callback.data == "done":
        if not interests:
            await callback.message.answer("Укажите хотя бы один интерес.")
            return
        await state.update_data(interests=interests)
        await state.set_state(CreateEvent.address)
        await callback.message.answer("Введите адрес мероприятия:")
        await callback.answer()
        return

    if callback.data in interests:
        interests.remove(callback.data)
    else:
        interests.append(callback.data)

    await state.update_data(interests=interests)
    await callback.message.edit_reply_markup(reply_markup=get_interests_keyboard(interests))
    await callback.answer()

@router.message(CreateEvent.address)
async def process_event_address(message: Message, state: FSMContext):
    address = message.text.strip()
    
    coords = await geocode_address(address)
    
    if not coords:
        await message.answer(
            "⚠️ Не удалось найти такой адрес.\n"
            "Попробуйте ввести более точный адрес, например:\n"
            "Москва, улица Авиамоторная, 8"
        )
        return
    
    lat, lon = coords
    await state.update_data(address=address, latitude=lat, longitude=lon)
    await state.set_state(CreateEvent.description)
    await message.answer(
        f"✅ Адрес найден!\n\nВведите описание мероприятия (можно пропустить):",
        reply_markup=get_description_keyboard()
    )

@router.message(CreateEvent.description, F.text == "Пропустить")
async def skip_event_description(message: Message, state: FSMContext):
    await state.update_data(description=None)
    await state.set_state(CreateEvent.photo)
    await message.answer(
        "Загрузите фото мероприятия (jpg, jpeg, png) или пропустите:",
        reply_markup=get_photo_keyboard()
    )

@router.message(CreateEvent.description)
async def process_event_description(message: Message, state: FSMContext):
    description = message.text.strip()
    await state.update_data(description=description)
    await state.set_state(CreateEvent.photo)
    await message.answer(
        "Загрузите фото мероприятия (jpg, jpeg, png) или пропустите:",
        reply_markup=get_photo_keyboard()
    )

@router.message(CreateEvent.photo, F.photo)
async def process_event_photo_media(message: Message, state: FSMContext):
    photo = message.photo[-1]
    await state.update_data(photo_file_id=photo.file_id, document_file_id=None)
    await state.set_state(CreateEvent.invite_friends)
    await show_invite_friends_list(message, state)

@router.message(CreateEvent.photo, F.document)
async def process_event_photo_document(message: Message, state: FSMContext):
    doc = message.document
    if not doc.mime_type or not doc.mime_type.startswith("image/"):
        await message.answer("🚫 Файл не является изображением.")
        return
    if not doc.file_name.lower().endswith((".jpg", ".jpeg", ".png")):
        await message.answer("🚫 Поддерживаются только JPG, JPEG, PNG.")
        return
    await state.update_data(document_file_id=doc.file_id, photo_file_id=None)
    await state.set_state(CreateEvent.invite_friends)
    await show_invite_friends_list(message, state)

@router.message(CreateEvent.photo, F.text == "Пропустить")
async def process_event_photo_skip(message: Message, state: FSMContext):
    await state.update_data(photo_file_id=None, document_file_id=None)
    await state.set_state(CreateEvent.invite_friends)
    await show_invite_friends_list(message, state)

@router.message(CreateEvent.photo)
async def process_event_photo_invalid(message: Message, state: FSMContext):
    await message.answer(
        "🚫 Отправьте фото (как изображение или файл JPG/PNG) "
        "или нажмите «Пропустить»"
    )

async def show_invite_friends_list(message: Message, state: FSMContext):
    data = await state.get_data()
    interests = data.get("interests", [])

    # Исправлено: показываем только реальных друзей, а не всех подряд
    friends = get_friends_db(message.from_user.id)
    
    # Опционально: можно сортировать друзей, у которых совпадают интересы
    if interests and friends:
        friends.sort(
            key=lambda f: len(set(interests) & set(f["interests"].split(','))) if f["interests"] else 0,
            reverse=True
        )

    if not friends:
        await message.answer(
            "Пока нет подходящих друзей для приглашения 😔\n"
            "Можно продолжить без приглашения.",
            reply_markup=ReplyKeyboardMarkup(
                keyboard=[[KeyboardButton(text="Пропустить")]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
        )
        return

    text = "Выберите друзей для приглашения:\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])

    for friend in friends:
        name = f"{friend['name']} {friend['surname']}".strip()
        age = friend['age'] if friend['age'] else "—"
        row = f"[{name}][{age}]"
        kb.inline_keyboard.append([
            InlineKeyboardButton(
                text=row,
                callback_data=f"invite_friend_{friend['tg_id']}"
            )
        ])

    kb.inline_keyboard.append([
        InlineKeyboardButton(text="Пригласить всех", callback_data="invite_all"),
        InlineKeyboardButton(text="Пропустить", callback_data="skip_invite")
    ])

    await message.answer(text, reply_markup=kb)

@router.callback_query(lambda c: c.data.startswith("invite_friend_"))
async def invite_single_friend(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    if user is None:
        await callback.answer("Сессия истекла", show_alert=True)
        return

    try:
        friend_tg_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных.", show_alert=True)
        return

    data = await state.get_data()
    event_name = data.get("name", "Мероприятие")
    safe_user_name = user.get('name', 'Пользователь')
    safe_event_name = event_name

    try:
        await callback.bot.send_message(
            friend_tg_id,
            f"Привет! {safe_user_name} пригласил тебя на мероприятие «{safe_event_name}»!\n"
            f"Дата: {data.get('date')}, время: {data.get('time')}\n"
            f"Адрес: {data.get('address', 'не указан')}\n"
            "Присоединяйся! 🎉\n\n"
            "Чтобы посмотреть подробности — зайди в бот и нажми «Мероприятия» → «Мероприятия друзей»"
        )
        await callback.answer("Приглашение отправлено!", show_alert=True)

        await callback.bot.send_message(
            callback.from_user.id,
            "Приглашение успешно отправлено!"
        )
    except Exception as e:
        logging.error(f"Ошибка отправки приглашения tg_id={friend_tg_id}: {e}")
        await callback.answer("Не удалось отправить приглашение (пользователь заблокировал бота?)", show_alert=True)

@router.callback_query(F.data == "invite_all")
async def invite_all_friends(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    if user is None:
        await callback.answer("Сессия истекла", show_alert=True)
        return

    data = await state.get_data()
    interests = data.get("interests", [])
    event_name = data.get("name", "Мероприятие")

    friends = find_potential_friends(user["number"], interests)

    sent_count = 0
    failed_count = 0
    for friend in friends:
        try:
            await callback.bot.send_message(
                friend["tg_id"],
                f"Привет! {user['name']} пригласил тебя на мероприятие «{event_name}»!\n"
                f"Дата: {data.get('date')}, время: {data.get('time')}\n"
                "Присоединяйся! 🎉"
            )
            sent_count += 1
        except Exception as e:
            logging.warning(f"Не удалось пригласить {friend['phone']}: {e}")
            failed_count += 1

    await callback.answer(f"Приглашено {sent_count} из {len(friends)} друзей!", show_alert=True)

    await callback.bot.send_message(
        callback.from_user.id,
        f"Приглашено {sent_count} из {len(friends)} друзей (не удалось: {failed_count})"
    )

    await state.set_state(CreateEvent.confirm)
    await show_event_preview(callback.message, state)
    try:
        await callback.message.delete()
    except:
        pass

@router.message(CreateEvent.invite_friends, F.text == "Пропустить")
async def skip_invite_text(message: Message, state: FSMContext):
    await state.set_state(CreateEvent.confirm)
    await show_event_preview(message, state)

@router.callback_query(CreateEvent.invite_friends, F.data == "skip_invite")
async def skip_invite(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(CreateEvent.confirm)
    await show_event_preview(callback.message, state)
    try:
        await callback.message.delete()
    except:
        pass
    await callback.answer("Приглашение пропущено")

async def show_event_preview(message: Message, state: FSMContext):
    data = await state.get_data()
    text = f"<b>{data['name']}</b>\n"
    text += f"Дата: {data['date']}\n"
    text += f"Время: {data['time']}\n"
    if data.get("interests"):
        text += f"Интересы: {', '.join(data['interests'])}\n"
    if data.get("address"):
        text += f"Адрес: {data['address']}\n"
    if data.get("description"):
        text += f"\n{data['description']}\n"

    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Сохранить")],
            [KeyboardButton(text="Отмена")],
        ],
        resize_keyboard=True
    )

    if data.get("photo_file_id"):
        await message.answer_photo(
            photo=data["photo_file_id"],
            caption=text,
            reply_markup=kb,
            parse_mode=ParseMode.HTML
        )
    elif data.get("document_file_id"):
        await message.answer_document(
            document=data["document_file_id"],
            caption=text,
            reply_markup=kb,
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@router.message(CreateEvent.confirm, F.text == "Сохранить")
async def save_event(message: Message, state: FSMContext, user: dict | None):
    if user is None or not user["registered"]:
        await message.answer("Сначала зарегистрируйтесь.")
        await state.clear()
        return

    data = await state.get_data()
    
    if create_event_db(user["number"], data):
         await message.answer("Мероприятие успешно создано! 🎉", 
                            reply_markup=get_user_main_menu())
    else:
         await message.answer("😔 Произошла ошибка при создании мероприятия. Попробуйте позже.")
    
    await state.clear()


@router.message(CreateEvent.confirm, F.text == "Отмена")
async def cancel_event_creation(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Создание мероприятия отменено.", reply_markup=get_user_main_menu())


@router.message(F.text == "Мероприятия друзей")
async def show_friends_events_handler(message: Message, user: dict | None):
    if user is None or not user["registered"]:
        await message.answer("Сначала зарегистрируйтесь.")
        return

    phone = user["number"]
    events = get_friends_events(phone)

    if not events:
        await message.answer("Пока нет мероприятий от ваших друзей 😔\nДобавьте друзей, чтобы видеть их мероприятия!")
        return

    for event in events:
        event_dict = {
            "id": event[0],
            "name": event[1],
            "date": event[2],
            "time": event[3],
            "address": event[4],
            "interests": event[5],
            "description": event[6],
            "organizer_phone": event[7],
            "is_participant": bool(event[8])
        }
        text = await get_event_card_text(event_dict)
        
        kb = get_event_card_keyboard_optimized(
            event_dict["id"], 
            phone, 
            event_dict["organizer_phone"],
            event_dict["is_participant"]
        )

        await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.message(F.text == "Мои мероприятия")
async def show_my_events_handler(message: Message, user: dict | None):
    if user is None or not user["registered"]:
        await message.answer("Сначала зарегистрируйтесь.")
        return

    phone = user["number"]
    organized, participated = get_my_events(phone)

    if not organized and not participated:
        await message.answer("У вас пока нет мероприятий 😔")
        return

    if organized:
        await message.answer("📌 Мои мероприятия (организатор):")
        for event in organized:
            event_dict = {
                "id": event[0], "name": event[1], "date": event[2], 
                "time": event[3], "address": event[4], "interests": event[5], 
                "description": event[6], "organizer_phone": event[7]
            }
            text = await get_event_card_text(event_dict)
            kb = get_my_event_card_keyboard(event_dict["id"], is_organizer=True)
            await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
            
    if participated:
        await message.answer("🎟️ Мои мероприятия (участник):")
        for event in participated:
            event_dict = {
                "id": event[0], "name": event[1], "date": event[2], 
                "time": event[3], "address": event[4], "interests": event[5], 
                "description": event[6], "organizer_phone": event[7],
                "is_participant": bool(event[9])
            }
            text = await get_event_card_text(event_dict)
            kb = get_my_event_card_keyboard(event_dict["id"], is_organizer=False)
            await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)

@router.callback_query(lambda c: c.data.startswith("join_event_"))
async def join_event(callback: types.CallbackQuery, user: dict | None):
    if user is None or not user["registered"]:
        await callback.answer("Сначала зарегистрируйтесь.", show_alert=True)
        return

    try:
        event_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных.", show_alert=True)
        return
        
    phone = user["number"]

    success, message = join_event_db(event_id, phone)
    if success:
         await callback.answer("Вы успешно записались! 🎉", show_alert=True)
         await callback.message.edit_reply_markup(reply_markup=None)
    elif message == "already_joined":
         await callback.answer("Вы уже участвуете в этом мероприятии!", show_alert=True)
    else:
         await callback.answer("Ошибка при записи", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("leave_event_"))
async def leave_event(callback: types.CallbackQuery, user: dict | None):
    if user is None or not user["registered"]:
        await callback.answer("Сначала зарегистрируйтесь.", show_alert=True)
        return

    try:
        event_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных.", show_alert=True)
        return
        
    phone = user["number"]

    success, msg, organizer_phone = leave_event_db(event_id, phone)

    if success:
        await callback.answer("Вы отказались от участия", show_alert=True)
        new_kb = get_event_card_keyboard_optimized(event_id, phone, organizer_phone, False)
        if new_kb:
            await callback.message.edit_reply_markup(reply_markup=new_kb)
        else:
            await callback.message.edit_reply_markup(reply_markup=None)
    elif msg == "not_found":
        await callback.answer("Мероприятие не найдено!", show_alert=True)
    elif msg == "not_participating":
        await callback.answer("Вы не участвуете в этом мероприятии!", show_alert=True)
    else:
        await callback.answer("Ошибка при отказе", show_alert=True)


@router.callback_query(lambda c: c.data.startswith("view_map_"))
async def view_on_map(callback: types.CallbackQuery, user: dict | None):
    """Shows event name, address, and venue with coordinates per TZ."""
    try:
        event_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных.", show_alert=True)
        return
    
    event = get_event_by_id(event_id)
    if not event:
        await callback.answer("Мероприятие не найдено!", show_alert=True)
        return
    
    safe_name = escape_html(event.get('name', 'Мероприятие'))
    safe_address = escape_html(event.get('address', 'Адрес не указан'))
    
    text = f"<b>{safe_name}</b>\n📍 {safe_address}"
    await callback.message.answer(text, parse_mode=ParseMode.HTML)
    
    lat = event.get('latitude')
    lon = event.get('longitude')
    
    if not lat or not lon:
        address = event.get('address', '')
        coords = await geocode_address(address)
        if coords:
            lat, lon = coords
        else:
            lat, lon = 55.7558, 37.6173
            await callback.message.answer("⚠️ Не удалось определить координаты. Показана Москва.")
    
    await callback.message.answer_venue(
        latitude=lat,
        longitude=lon,
        title=event.get('name', 'Мероприятие'),
        address=event.get('address', 'Адрес не указан')
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("view_participants_"))
async def view_participants(callback: types.CallbackQuery, user: dict | None):
    try:
        event_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных.", show_alert=True)
        return
    
    participants = get_event_participants(event_id)
    
    if not participants:
        await callback.answer("Пока нет участников 😔", show_alert=True)
        return
    
    lines = ["<b>👥 Список участников:</b>\n"]
    for name, surname, age in participants:
        safe_name = escape_html(name or '')
        safe_surname = escape_html(surname or '')
        age_str = str(age) if age else ''
        lines.append(f"• {safe_name} {safe_surname}, {age_str}")
    
    text = "\n".join(lines)
    await callback.message.answer(text, parse_mode=ParseMode.HTML)
    await callback.answer()
