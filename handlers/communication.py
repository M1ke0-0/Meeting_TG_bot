import logging
import sqlite3
from aiogram import Router, F, types
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode

from database.users import (
    get_user_by_tg_id, add_friend_db, get_friends_db, check_is_friend,
    send_friend_request, accept_friend_request, decline_friend_request,
    delete_friend_db
)
from database.common import get_all_regions, get_all_interests
from config import DB_PATH
from utils.validation import escape_html

router = Router()

class SearchState(StatesGroup):
    waiting_message = State()

def get_communication_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👥 Друзья")],
            [KeyboardButton(text="🔍 Поиск друзей")],
            [KeyboardButton(text="Назад")],
        ],
        resize_keyboard=True
    )

def get_find_friends_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Показать возможных друзей")],
            [KeyboardButton(text="Условия поиска")],
            [KeyboardButton(text="Назад")] 
        ],
        resize_keyboard=True
    )

def get_search_filters_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Пол", callback_data="filter_gender"),
         InlineKeyboardButton(text="Возраст", callback_data="filter_age")],
        [InlineKeyboardButton(text="Регион", callback_data="filter_region"),
         InlineKeyboardButton(text="Интересы", callback_data="filter_interests")],
        [InlineKeyboardButton(text="🔍 Начать поиск", callback_data="start_search_btn")]
    ])

@router.message(F.text == "💬 Общение")
async def communication_menu_handler(message: Message, user: dict | None):
    if user is None or not user["registered"]:
        await message.answer("Сначала зарегистрируйтесь.")
        return

    await message.answer(
        "Раздел общения 💬\nВыберите действие:",
        reply_markup=get_communication_menu()
    )


@router.message(F.text == "👥 Друзья")
async def show_friends(message: Message, user: dict | None):
    if user is None or not user.get("registered"):
        await message.answer("Сначала зарегистрируйтесь.")
        return
        
    friends = get_friends_db(user["tg_id"])
    
    if not friends:
        await message.answer("У вас пока нет друзей.")
        return
    
    await message.answer(f"Ваши друзья ({len(friends)}):")
    for f in friends:
        safe_name = escape_html(f['name'])
        safe_surname = escape_html(f['surname'] or '')
        text = f"👤 {safe_name} {safe_surname}, {f['age']}"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Чат", callback_data=f"write_msg_{f['tg_id']}")],
            [InlineKeyboardButton(text="❌ Удалить", callback_data=f"del_friend_{f['tg_id']}")]
        ])
        await message.answer(text, reply_markup=kb)


@router.message(F.text == "🔍 Поиск друзей")
async def find_friends_menu(message: Message, state: FSMContext, user: dict | None):
    if user is None or not user.get("registered"):
        await message.answer("Сначала зарегистрируйтесь.")
        return
    await message.answer("Поиск друзей:", reply_markup=get_find_friends_menu())

@router.message(F.text == "Показать возможных друзей")
async def show_possible_friends(message: Message, state: FSMContext, user: dict | None):
    if user is None or not user.get("registered"):
        await message.answer("Сначала зарегистрируйтесь.")
        return
    await perform_search(message, user, defaults=True)

@router.message(F.text == "Условия поиска")
async def search_conditions(message: Message, state: FSMContext, user: dict | None):
    if user is None or not user.get("registered"):
        await message.answer("Сначала зарегистрируйтесь.")
        return
    await state.update_data(
        search_gender=None,
        search_age_range=None,
        search_region=None,
        search_interests=[]
    )
    await message.answer("Укажите параметры поиска:", reply_markup=get_search_filters_keyboard())


@router.callback_query(F.data == "filter_gender")
async def filter_gender(callback: types.CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Муж", callback_data="set_gender_Муж"),
         InlineKeyboardButton(text="Жен", callback_data="set_gender_Жен")],
        [InlineKeyboardButton(text="Любой", callback_data="set_gender_Any")]
    ])
    await callback.message.answer("Укажите пол:", reply_markup=kb)
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("set_gender_"))
async def set_gender(callback: types.CallbackQuery, state: FSMContext):
    gender = callback.data.split("_")[2]
    val = None if gender == "Any" else gender
    await state.update_data(search_gender=val)
    await callback.message.answer(f"Пол выбран: {escape_html(gender)}")
    await callback.answer()

@router.callback_query(F.data == "filter_age")
async def filter_age(callback: types.CallbackQuery):
    ranges = ["15-20", "21-25", "26-30", "31-35", "36-40"]
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    row = []
    for r in ranges:
        row.append(InlineKeyboardButton(text=r, callback_data=f"set_age_{r}"))
        if len(row) == 2:
            kb.inline_keyboard.append(row)
            row = []
    if row: kb.inline_keyboard.append(row)
    await callback.message.answer("Укажите возраст:", reply_markup=kb)
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("set_age_"))
async def set_age_range(callback: types.CallbackQuery, state: FSMContext):
    r = callback.data.split("_")[2]
    # Validate age range format
    if not r or '-' not in r:
        await callback.answer("Неверный формат")
        return
    await state.update_data(search_age_range=r)
    await callback.message.answer(f"Возраст выбран: {escape_html(r)}")
    await callback.answer()

@router.callback_query(F.data == "filter_region")
async def filter_region(callback: types.CallbackQuery):
    regions = get_all_regions()
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for reg in regions[:30]: 
        kb.inline_keyboard.append([InlineKeyboardButton(text=reg, callback_data=f"set_search_region_{reg}")])
    await callback.message.answer("Укажите регион:", reply_markup=kb)
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("set_search_region_"))
async def set_region_search(callback: types.CallbackQuery, state: FSMContext):
    reg = callback.data.replace("set_search_region_", "")
    await state.update_data(search_region=reg)
    await callback.message.answer(f"Регион выбран: {escape_html(reg)}")
    await callback.answer()

@router.callback_query(F.data == "filter_interests")
async def filter_interests_start(callback: types.CallbackQuery, state: FSMContext):
    interests = get_all_interests()
    kb = InlineKeyboardMarkup(inline_keyboard=[])
    for i in interests[:30]:
        kb.inline_keyboard.append([InlineKeyboardButton(text=i, callback_data=f"add_search_int_{i}")])
    kb.inline_keyboard.append([InlineKeyboardButton(text="✅ Готово / Сбросить", callback_data="done_search_int")])
    await callback.message.answer("Укажите интерес:", reply_markup=kb)
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("add_search_int_"))
async def add_search_interest(callback: types.CallbackQuery, state: FSMContext):
    i = callback.data.replace("add_search_int_", "")
    data = await state.get_data()
    current = data.get("search_interests", [])
    if i not in current:
        current.append(i)
    else:
        current.remove(i) 
    await state.update_data(search_interests=current)
    await callback.answer(f"Интересы: {', '.join(current)}")

@router.callback_query(F.data == "done_search_int")
async def done_search_int(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ints = data.get("search_interests", [])
    await callback.message.answer(f"Интересы выбраны: {len(ints)}")
    await callback.answer()

@router.callback_query(F.data == "start_search_btn")
async def start_search_handler(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    if user is None or not user.get("registered"):
        await callback.answer("Сначала зарегистрируйтесь.", show_alert=True)
        return
    await callback.message.answer("🔍 Ищу пользователей...")
    await perform_search(callback.message, user, defaults=False, state=state)
    await callback.answer()

async def perform_search(message: Message, user: dict, defaults=True, state: FSMContext = None):
    filters = {}
    if defaults:
        filters = {
            "gender": None, 
            "region": user["region"],
            "interests": user["interests"].split(",") if user["interests"] else [],
            "age_range": None
        }
    else:
        if state:
            data = await state.get_data()
            filters = {
                "gender": data.get("search_gender"),
                "region": data.get("search_region"),
                "interests": data.get("search_interests", []),
                "age_range": data.get("search_age_range")
            }
    
    query = """
        SELECT number, tg_id, name, surname, age, gender, region, interests, photo_file_id
        FROM users
        WHERE registered = 1 AND number != ?
    """
    params = [user['number']]
    
    if filters.get("gender"):
        query += " AND gender = ?"
        params.append(filters["gender"])
    if filters.get("region"):
        query += " AND region = ?"
        params.append(filters["region"])
    if filters.get("age_range"):
        try:
            min_a, max_a = map(int, filters["age_range"].split("-"))
            if 0 < min_a <= max_a < 150:
                query += " AND age >= ? AND age <= ?"
                params.extend([min_a, max_a])
        except (ValueError, AttributeError):
            pass

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(query, params)
        rows = c.fetchall()

    results = []
    user_interests = set(filters.get("interests", []))

    for row in rows:
        target_id = row[1]
        
        if check_is_friend(user["tg_id"], target_id): continue
            
        u_interests = set(row[7].split(',') if row[7] else [])
        overlap = len(user_interests.intersection(u_interests)) if user_interests else 0
        if not defaults and user_interests and overlap == 0: continue
        
        results.append({
            "tg_id": target_id,
            "name": row[2],
            "surname": row[3],
            "age": row[4],
            "gender": row[5],
            "region": row[6],
            "interests": row[7],
            "photo": row[8],
            "score": overlap
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    if not results:
        await message.answer("😔 Пользователи не найдены. Попробуйте изменить условия.")
        return

    for res in results[:10]:
        safe_name = escape_html(res['name'])
        safe_surname = escape_html(res['surname'] or '')
        safe_region = escape_html(res['region'] or '')
        safe_interests = escape_html(res['interests'] or '')
        
        text = f"👤 <b>{safe_name} {safe_surname}</b>, {res['age']}\n"
        text += f"📍 {safe_region}\n"
        text += f"❤️ {safe_interests}\n"
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💬 Чат", callback_data=f"write_msg_{res['tg_id']}")],
            [InlineKeyboardButton(text="➕ Добавить в друзья", callback_data=f"add_req_{res['tg_id']}")]
        ])
        
        if res['photo']:
            try:
                await message.answer_photo(res['photo'], caption=text, reply_markup=kb, parse_mode=ParseMode.HTML)
            except:
                 await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        else:
            await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(lambda c: c.data.startswith("add_req_"))
async def add_friend_request_handler(callback: types.CallbackQuery, user: dict | None):
    if user is None or not user.get("registered"):
        await callback.answer("Сначала зарегистрируйтесь.", show_alert=True)
        return
        
    try:
        target_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных.")
        return
    

    
    if target_id == user["tg_id"]:
        await callback.answer("Нельзя добавить себя в друзья.")
        return
    
    result = send_friend_request(user["tg_id"], target_id)
    if result == "ok":
        await callback.answer("Заявка отправлена! 📩")
        

        
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_req_{user['tg_id']}")],
                [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_req_{user['tg_id']}")]
            ])
            safe_name = escape_html(user['name'])
            safe_surname = escape_html(user['surname'] or '')
            text = f"🔔 <b>Заявка в друзья!</b>\n\n👤 {safe_name} {safe_surname}, {user['age']}"
            await callback.bot.send_message(target_id, text, reply_markup=kb, parse_mode=ParseMode.HTML)
        except Exception:
            logging.error(f"Failed to notify user {target_id} about friend request")
            
    elif result == "already_friends":
        await callback.answer("Вы уже друзья!")
    elif result == "already_sent":
        await callback.answer("Заявка уже отправлена.")
    else:
        await callback.answer("Ошибка.")


@router.callback_query(lambda c: c.data.startswith("accept_req_"))
async def accept_request_handler(callback: types.CallbackQuery, user: dict | None):
    if user is None or not user.get("registered"):
        await callback.answer("Сначала зарегистрируйтесь.", show_alert=True)
        return
        
    try:
        requester_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных.")
        return
        
    if accept_friend_request(user["tg_id"], requester_id):
        await callback.message.edit_text("✅ Заявка принята! Теперь вы друзья.")
        await callback.answer()

        try:
            safe_name = escape_html(user['name'])
            await callback.bot.send_message(requester_id, f"🎉 {safe_name} принял вашу заявку в друзья!")
        except: pass
    else:
        await callback.answer("Ошибка при принятии.")

@router.callback_query(lambda c: c.data.startswith("decline_req_"))
async def decline_request_handler(callback: types.CallbackQuery, user: dict | None):
    if user is None or not user.get("registered"):
        await callback.answer("Сначала зарегистрируйтесь.", show_alert=True)
        return
        
    try:
        requester_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных.")
        return
        
    decline_friend_request(user["tg_id"], requester_id)
    await callback.message.edit_text("❌ Заявка отклонена.")
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("del_friend_"))
async def delete_friend_handler(callback: types.CallbackQuery, user: dict | None):
    if user is None or not user.get("registered"):
        await callback.answer("Сначала зарегистрируйтесь.", show_alert=True)
        return
        
    try:
        target_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных.")
        return
    

    
    if not check_is_friend(user["tg_id"], target_id):
        await callback.answer("Этот пользователь не в вашем списке друзей.")
        return
    
    delete_friend_db(user["tg_id"], target_id)
    
    await callback.message.delete() 
    await callback.answer("Друг удален 🗑")


@router.callback_query(lambda c: c.data.startswith("write_msg_"))
async def write_message_start(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    if user is None or not user.get("registered"):
        await callback.answer("Сначала зарегистрируйтесь.", show_alert=True)
        return
        
    try:
        target_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("Ошибка данных.")
        return
    

    
    target_user = get_user_by_tg_id(target_id)
    if not target_user:
        await callback.answer("Пользователь не найден.")
        return
        
    await state.update_data(target_id=target_id)
    await state.set_state(SearchState.waiting_message)
    await callback.message.answer("Введите сообщение (текст, фото, видео...):")
    await callback.answer()

@router.message(SearchState.waiting_message)
async def send_message_to_user(message: Message, state: FSMContext, user: dict | None):
    if user is None or not user.get("registered"):
        await message.answer("Сначала зарегистрируйтесь.")
        await state.clear()
        return
        
    data = await state.get_data()
    target_id = data.get("target_id")
    
    if not target_id:
        await message.answer("Ошибка: получатель не найден.")
        await state.clear()
        return

    try:
        safe_name = escape_html(user['name'])
        await message.bot.send_message(
            target_id, 
            f"💬 <b>Сообщение от {safe_name}:</b>",
            parse_mode=ParseMode.HTML
        )
        await message.copy_to(
            chat_id=target_id,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="↩️ Ответить", callback_data=f"write_msg_{message.from_user.id}")]
            ])
        )
        await message.answer("Сообщение отправлено! ✅")
    except Exception as e:
        logging.error(f"Message send error: {e}")
        await message.answer("Не удалось отправить сообщение.")
    
    await state.clear()
