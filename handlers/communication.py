import logging
from aiogram import Router, F, types
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest

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



from states.states import Registration, MessageState


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
    
    await message.answer("<b>Ваши друзья:</b>", parse_mode=ParseMode.HTML)
    
    for friend in friends:
        name = friend.get('name') or "Без имени"
        surname = friend.get('surname') or ""
        text = f"👤 {name} {surname}"
        
        markup = None
        if friend.get('tg_id'):
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💬 Написать сообщение", callback_data=f"write_message_{friend['tg_id']}")],
                [InlineKeyboardButton(text="❌ Удалить из друзей", callback_data=f"del_friend_ask_{friend['tg_id']}")]
            ])
        
        await message.answer(text, reply_markup=markup)


@router.callback_query(lambda c: c.data.startswith("del_friend_ask_"))
async def ask_delete_friend(callback: types.CallbackQuery, user: dict | None):
    friend_id = int(callback.data.split("_")[3])
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да, удалить", callback_data=f"del_friend_yes_{friend_id}")],
        [InlineKeyboardButton(text="Отмена", callback_data=f"del_friend_no_{friend_id}")]
    ])
    
    await callback.message.edit_text(
        f"{callback.message.text}\n\n⚠️ Вы уверены, что хотите удалить этого пользователя из друзей?", 
        reply_markup=markup
    )
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("del_friend_no_"))
async def cancel_delete_friend(callback: types.CallbackQuery):
    original_text = callback.message.text.split("\n\n⚠️")[0]
    friend_id = int(callback.data.split("_")[3])
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💬 Написать сообщение", callback_data=f"write_message_{friend_id}")],
        [InlineKeyboardButton(text="❌ Удалить из друзей", callback_data=f"del_friend_ask_{friend_id}")]
    ])
    
    await callback.message.edit_text(original_text, reply_markup=markup)
    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("del_friend_yes_"))
async def perform_delete_friend(callback: types.CallbackQuery, user: dict | None):
    friend_id = int(callback.data.split("_")[3])
    
    async with get_session() as session:
        user_repo = UserRepository(session)
        friend_info = await user_repo.get_by_tg_id(friend_id)
        friend_name = "Пользователь"
        if friend_info:
            friend_name = f"{friend_info.name or ''} {friend_info.surname or ''}".strip() or "Пользователь"
    
    async with get_session() as session:
        friend_repo = FriendRepository(session)
        await friend_repo.delete_friend(user['tg_id'], friend_id)
        
    await callback.message.delete()
    await callback.answer("Пользователь удален из друзей.")
    
    my_name = f"{user.get('name', '')} {user.get('surname', '')}".strip() or "Пользователь"
    
    await callback.message.answer(f"❌ Вы удалили {friend_name} из друзей.")
    
    try:
        await callback.bot.send_message(
            friend_id,
            f"😔 {my_name} удалил(а) вас из друзей."
        )
    except:
        pass  


@router.callback_query(lambda c: c.data.startswith("write_message_"))
async def start_write_message(callback: types.CallbackQuery, state: FSMContext):
    target_id = int(callback.data.split("_")[2])
    
    await state.update_data(target_id=target_id)
    await state.set_state(MessageState.waiting_message)
    
    await callback.message.answer(
        "Введите текст сообщения:",
        reply_markup=types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="Отмена")]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
    )
    await callback.answer()


@router.message(MessageState.waiting_message)
async def send_friend_message(message: Message, state: FSMContext, user: dict | None):
    if message.text == "Отмена":
        await state.clear()
        await message.answer("Отправка отменена.", reply_markup=get_user_main_menu())
        return

    data = await state.get_data()
    target_id = data.get("target_id")
    
    if not target_id:
        await message.answer("Ошибка: получатель не найден.")
        await state.clear()
        return
        
    sender_name = f"{user.get('name', '')} {user.get('surname', '')}".strip()
    header = f"📩 <b>Сообщение от {sender_name}:</b>"
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Ответить", callback_data=f"write_message_{user['tg_id']}")]
    ])
    
    try:
        if message.photo:
            caption = f"{header}\n\n{message.caption or ''}"
            await message.bot.send_photo(
                target_id,
                photo=message.photo[-1].file_id,
                caption=caption,
                reply_markup=markup,
                parse_mode=ParseMode.HTML
            )
        elif message.document:
            caption = f"{header}\n\n{message.caption or ''}"
            await message.bot.send_document(
                target_id,
                document=message.document.file_id,
                caption=caption,
                reply_markup=markup,
                parse_mode=ParseMode.HTML
            )
        elif message.audio:
            caption = f"{header}\n\n{message.caption or ''}"
            await message.bot.send_audio(
                target_id,
                audio=message.audio.file_id,
                caption=caption,
                reply_markup=markup,
                parse_mode=ParseMode.HTML
            )
        elif message.video:
            caption = f"{header}\n\n{message.caption or ''}"
            await message.bot.send_video(
                target_id,
                video=message.video.file_id,
                caption=caption,
                reply_markup=markup,
                parse_mode=ParseMode.HTML
            )
        elif message.voice:
            await message.bot.send_message(target_id, header, parse_mode=ParseMode.HTML)
            await message.bot.send_voice(
                target_id,
                voice=message.voice.file_id,
                reply_markup=markup
            )
        elif message.video_note:
            await message.bot.send_message(target_id, header, parse_mode=ParseMode.HTML)
            await message.bot.send_video_note(
                target_id,
                video_note=message.video_note.file_id,
                reply_markup=markup
            )
        elif message.sticker:
            await message.bot.send_message(target_id, header, parse_mode=ParseMode.HTML)
            await message.bot.send_sticker(
                target_id,
                sticker=message.sticker.file_id,
                reply_markup=markup
            )
        elif message.text:
            await message.bot.send_message(
                target_id,
                f"{header}\n\n{message.text}",
                reply_markup=markup,
                parse_mode=ParseMode.HTML
            )
        else:
            await message.answer("❌ Этот тип сообщения не поддерживается.")
            await state.clear()
            return
            
        await message.answer("Сообщение отправлено! ✅", reply_markup=get_user_main_menu())
    except Exception as e:
        logging.error(f"Failed to send message: {e}")
        await message.answer("❌ Не удалось отправить сообщение (возможно, пользователь заблокировал бота).")
        
    await state.clear()



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
        result = await friend_repo.accept_request(user['tg_id'], friend_id)
        
        if result is not None:
            await callback.message.edit_reply_markup(reply_markup=None)
            await callback.answer("Заявка принята! ✅")
            await callback.message.answer("Теперь вы друзья!")
            
            try:
                my_name = f"{user.get('name','')} {user.get('surname','')}".strip()
                await callback.bot.send_message(friend_id, f"👋 {my_name} принял(а) вашу заявку в друзья!")
                
                if isinstance(result, int) and result > 0:
                    try:
                        await callback.bot.edit_message_reply_markup(
                            chat_id=friend_id,
                            message_id=result,
                            reply_markup=None
                        )
                    except Exception:
                        pass
            except Exception:
                pass
        else:
            try:
                await callback.answer("Ошибка при добавлении.")
            except TelegramBadRequest:
                pass  


@router.callback_query(lambda c: c.data.startswith("friend_decline_"))
async def decline_friend(callback: types.CallbackQuery, user: dict | None):
    friend_id = int(callback.data.split("_")[2])
    
    async with get_session() as session:
        friend_repo = FriendRepository(session)
        await friend_repo.decline_request(user['tg_id'], friend_id)
        
    await callback.message.edit_reply_markup(reply_markup=None)
    try:
        await callback.answer("Заявка отклонена ❌")
    except TelegramBadRequest:
        pass  



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
    
    async with get_session() as session:
        region_repo = RegionRepository(session)
        regions_list = await region_repo.get_all_names()

    kb = get_region_keyboard(regions_list)
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
        
    await message.answer(f"Найдено: {len(results)}\nПоказываем топ-10:", reply_markup=get_user_main_menu())
    
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
            
            async with get_session() as session2:
                user_repo = UserRepository(session2)
                target_user = await user_repo.get_by_tg_id(target_id)
                target_name = "пользователю"
                if target_user:
                    target_name = f"{target_user.name or ''} {target_user.surname or ''}".strip() or "пользователю"
            
            await callback.message.answer(
                f"📤 Заявка в друзья отправлена {target_name}!\n"
                f"Ожидайте ответа."
            )
            
            try:
                my_name = f"{user.get('name','')} {user.get('surname','')}".strip()
                
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Принять", callback_data=f"friend_accept_{user['tg_id']}"),
                        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"friend_decline_{user['tg_id']}")
                    ]
                ])
                
                await callback.bot.send_message(
                    target_id, 
                    f"📥 Вам пришла заявка в друзья от <b>{my_name}</b>!\n\n"
                    f"Вы можете принять или отклонить её.",
                    reply_markup=markup,
                    parse_mode=ParseMode.HTML
                )
            except:
                pass
        elif result == "already_friends":
            await callback.answer("Вы уже друзья!", show_alert=True)
        elif result == "already_sent":
            await callback.answer("Заявка уже была отправлена.", show_alert=True)
        else:
            await callback.answer("Ошибка при отправке.", show_alert=True)
