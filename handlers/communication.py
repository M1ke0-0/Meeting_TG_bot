import logging
from aiogram import Router, F, types
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode

from database import get_session
from database.repositories import (
    UserRepository, FriendRepository, InterestRepository, RegionRepository
)
from keyboards.builders import get_user_main_menu, get_interests_keyboard, get_region_keyboard


class SearchStates(StatesGroup):
    waiting_gender = State()
    waiting_region = State()
    waiting_age = State()
    waiting_interests = State()


router = Router()

@router.message(F.text == "💬 Общение")
async def communication_menu(message: Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Друзья")],
            [KeyboardButton(text="Поиск друзей")],
            [KeyboardButton(text="Входящие заявки")],
            [KeyboardButton(text="Назад")],
        ],
        resize_keyboard=True
    )
    await message.answer("Меню общения", reply_markup=kb)


# --- Friends List ---

@router.message(F.text == "Друзья")
async def show_friends(message: Message, user: dict | None):
    if not user: 
        return

    async with get_session() as session:
        friend_repo = FriendRepository(session)
        friends = await friend_repo.get_friends(user['tg_id'])
    
    if not friends:
        await message.answer("У вас пока нет друзей.")
        return
    
    text = "<b>Ваши друзья:</b>\n"
    for friend in friends:
        name = friend.get('name') or "Без имени"
        surname = friend.get('surname') or ""
        text += f"• {name} {surname}\n"
    
    await message.answer(text, parse_mode=ParseMode.HTML)


# --- Incoming Requests ---

@router.message(F.text == "Входящие заявки")
async def show_requests(message: Message, user: dict | None):
    if not user: 
        return
    
    async with get_session() as session:
        friend_repo = FriendRepository(session)
        requests = await friend_repo.get_incoming_requests(user['tg_id'])

    if not requests:
        await message.answer("Входящих заявок нет.")
        return

    await message.answer(f"Входящих заявок: {len(requests)}")
    
    for req in requests:
        name = req.get('name') or "Без имени"
        surname = req.get('surname') or ""
        age = req.get('age') or "?"
        region = req.get('region') or "Неизвестно"
        interests = req.get('interests') or ""
        
        caption = (
            f"👤 <b>{name} {surname}</b>\n"
            f"🎂 Возраст: {age}\n"
            f"📍 Регион: {region}\n"
            f"❤️ Интересы: {interests}"
        )
        
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"friend_accept_{req['tg_id']}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"friend_decline_{req['tg_id']}")
            ]
        ])
        
        if req.get('photo'):
            try:
                await message.answer_photo(req['photo'], caption=caption, reply_markup=markup, parse_mode=ParseMode.HTML)
                continue
            except:
                pass
        
        await message.answer(caption, reply_markup=markup, parse_mode=ParseMode.HTML)


@router.callback_query(lambda c: c.data.startswith("friend_accept_"))
async def accept_friend(callback: types.CallbackQuery, user: dict | None):
    friend_id = int(callback.data.split("_")[2])
    
    async with get_session() as session:
        friend_repo = FriendRepository(session)
        success = await friend_repo.accept_request(user['tg_id'], friend_id)
        
        if success:
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.answer("Заявка принята! ✅")
            await callback.message.answer("Теперь вы друзья!")
            
            # Notify sender
            try:
                my_name = f"{user.get('name','')} {user.get('surname','')}".strip()
                await callback.bot.send_message(friend_id, f"👋 {my_name} принял(а) вашу заявку в друзья!")
            except:
                pass
        else:
            await callback.answer("Ошибка при добавлении.")


@router.callback_query(lambda c: c.data.startswith("friend_decline_"))
async def decline_friend(callback: types.CallbackQuery, user: dict | None):
    friend_id = int(callback.data.split("_")[2])
    
    async with get_session() as session:
        friend_repo = FriendRepository(session)
        await friend_repo.decline_request(user['tg_id'], friend_id)
        
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Заявка отклонена ❌")


# --- Search Friends ---

@router.message(F.text == "Поиск друзей")
async def search_friends_start(message: Message, state: FSMContext):
    await state.clear()
    
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔍 Найти по интересам")],
            [KeyboardButton(text="🔍 Расширенный поиск")],
            [KeyboardButton(text="Назад")]
        ],
        resize_keyboard=True
    )
    await message.answer("Выберите режим поиска:", reply_markup=kb)


@router.message(F.text == "🔍 Найти по интересам")
async def search_by_interests(message: Message, state: FSMContext, user: dict | None):
    if not user:
        return
        
    user_interests = user.get('interests')
    if not user_interests:
        await message.answer("В вашем профиле не указаны интересы.")
        return
    
    interests_list = user_interests.split(",") if isinstance(user_interests, str) else user_interests
    
    async with get_session() as session:
        user_repo = UserRepository(session)
        results = await user_repo.search_users(
            current_phone=user["number"],
            interests=interests_list
        )
        
    await show_search_results(message, results, user)


@router.message(F.text == "🔍 Расширенный поиск")
async def advanced_search(message: Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Муж"), KeyboardButton(text="Жен")],
            [KeyboardButton(text="Любой")]
        ],
        resize_keyboard=True, one_time_keyboard=True
    )
    await message.answer("Кого ищем? (Пол)", reply_markup=kb)
    await state.set_state(SearchStates.waiting_gender)


@router.message(SearchStates.waiting_gender)
async def search_gender(message: Message, state: FSMContext):
    gender = message.text
    if gender == "Любой":
        gender = None
    
    await state.update_data(gender=gender)
    
    # Fetch regions async
    async with get_session() as session:
        region_repo = RegionRepository(session)
        regions_list = await region_repo.get_all_names()

    kb = get_region_keyboard(regions_list)
    # Add 'Any' option
    kb.keyboard.insert(0, [KeyboardButton(text="Любой")])
    
    await message.answer("В каком регионе?", reply_markup=kb)
    await state.set_state(SearchStates.waiting_region)


@router.message(SearchStates.waiting_region)
async def search_region(message: Message, state: FSMContext):
    region = message.text
    if region == "Любой":
        region = None
        
    await state.update_data(region=region)
    
    await message.answer("Возраст (диапазон, например 20-30, или 'Любой')", reply_markup=ReplyKeyboardRemove())
    await state.set_state(SearchStates.waiting_age)


@router.message(SearchStates.waiting_age)
async def search_age(message: Message, state: FSMContext):
    age_str = message.text
    if age_str.lower() == "любой":
        age_str = None
        
    await state.update_data(age_range=age_str)
    
    # Fetch interests async
    async with get_session() as session:
        interest_repo = InterestRepository(session)
        interests_list = await interest_repo.get_all_names()
        
    await message.answer(
        "Интересы (выберите или нажмите Готово):",
        reply_markup=get_interests_keyboard(interests_list, [])
    )
    await state.set_state(SearchStates.waiting_interests)


@router.callback_query(SearchStates.waiting_interests)
async def search_interests(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    data = await state.get_data()
    interests = data.get('interests', [])

    if callback.data == "done":
        await perform_search(callback.message, data, user, interests)
        await state.clear()
        await callback.answer()
        return
        
    # Handling interest selection
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


async def perform_search(message: Message, criteria: dict, user: dict, interests: list):
    async with get_session() as session:
        user_repo = UserRepository(session)
        results = await user_repo.search_users(
            current_phone=user["number"],
            gender=criteria.get("gender"),
            region=criteria.get("region"),
            age_range=criteria.get("age_range"),
            interests=interests
        )
        
    await show_search_results(message, results, user)


async def show_search_results(message: Message, results: list, user: dict):
    if not results:
        await message.answer("Никого не найдено 😔", reply_markup=get_user_main_menu())
        return
        
    await message.answer(f"Найдено: {len(results)}\nПоказываем топ-10:")
    
    for res in results[:10]:
        tg_id = res['tg_id']
        name = res['name']
        surname = res['surname'] or ""
        age = res['age']
        region = res['region']
        user_interests = res['interests'] or ""
        photo = res['photo']
        
        caption = (
            f"👤 <b>{name} {surname}</b>\n"
            f"🎂 Возраст: {age}\n"
            f"📍 Регион: {region}\n"
            f"❤️ Интересы: {user_interests}"
        )
        
        # Check friend status
        async with get_session() as session:
            friend_repo = FriendRepository(session)
            is_friend = await friend_repo.is_friend(user['tg_id'], tg_id)
            
        if is_friend:
            kb = None
            caption += "\n\n✅ Уже в дузьях"
        else:
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                 InlineKeyboardButton(text="➕ Добавить в друзья", callback_data=f"add_friend_{tg_id}")
            ]])
            
        if photo:
            try:
                await message.answer_photo(photo, caption=caption, reply_markup=kb, parse_mode=ParseMode.HTML)
            except:
                await message.answer(caption, reply_markup=kb, parse_mode=ParseMode.HTML)
        else:
            await message.answer(caption, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(lambda c: c.data.startswith("add_friend_"))
async def add_friend_request(callback: types.CallbackQuery, user: dict | None):
    target_id = int(callback.data.split("_")[2])
    
    async with get_session() as session:
        friend_repo = FriendRepository(session)
        result = await friend_repo.send_request(user['tg_id'], target_id)
        
        if result == "ok":
            await callback.answer("Заявка отправлена! 📨", show_alert=True)
            # Notify target
            try:
                my_name = f"{user.get('name','')} {user.get('surname','')}".strip()
                await callback.bot.send_message(
                    target_id, 
                    f"👋 Вам пришла заявка в друзья от {my_name}!"
                )
            except:
                pass
        elif result == "already_friends":
            await callback.answer("Вы уже друзья!", show_alert=True)
        elif result == "already_sent":
            await callback.answer("Заявка уже была отправлена.", show_alert=True)
        else:
            await callback.answer("Ошибка при отправке.", show_alert=True)
