from aiogram import Router, F, types
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.enums import ParseMode

from states.states import Registration
from keyboards.builders import (
    get_user_main_menu, get_admin_menu_keyboard, get_start_keyboard,
    get_resume_registration_keyboard, get_skip_edit_keyboard,
    get_gender_keyboard, get_region_keyboard, get_interests_keyboard,
    get_photo_keyboard, get_location_keyboard, get_edit_profile_menu
)

from database import get_session
from database.repositories import RegionRepository, InterestRepository

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, user: dict | None):
    await state.clear()
    
    if user:
        if user["role"] == "admin":
            await message.answer(
                "Добро пожаловать в админ-панель! 👑",
                reply_markup=get_admin_menu_keyboard()
            )
            return

        if user["registered"]:
            await message.answer(
                f"С возвращением, {user['name'] or 'пользователь'}! 👋",
                reply_markup=get_user_main_menu()
            )
            return

        await message.answer("Ваша регистрация не завершена. Продолжим?", reply_markup=get_resume_registration_keyboard())
    else:
        welcome = (
            "Что может этот бот:\n\n"
            "• Организовывать мероприятия\n"
            "• Искать участников\n"
            "• Общаться по интересам\n\n"
            "Нажмите «Запустить»"
        )
        await message.answer(welcome, reply_markup=get_start_keyboard())

@router.message(F.text == "Запустить")
async def btn_launch(message: Message, state: FSMContext, user: dict | None):
    if user:
        if user["role"] == "admin":
            await message.answer(
                "Добро пожаловать в админ-панель! 👑",
                reply_markup=get_admin_menu_keyboard()
            )
            return

        if user["registered"]:
            await message.answer(
                f"С возвращением, {user['name'] or 'пользователь'}! 👋",
                reply_markup=get_user_main_menu()
            )
            return

        await message.answer("Ваша регистрация не завершена. Продолжим?", reply_markup=get_resume_registration_keyboard())
    else:
        from keyboards.builders import get_contact_keyboard
        text = "Предоставьте номер телефона для регистрации / авторизации"
        await message.answer(text, reply_markup=get_contact_keyboard())

@router.message(F.text.in_({"отмена", "cancel", "Отмена", "/cancel"}))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=get_user_main_menu())


@router.message(F.text == "Назад")
async def back_to_main(message: Message):
    await message.answer("Главное меню", reply_markup=get_user_main_menu())


@router.message(F.text == "👤 Мой профиль")
async def show_my_profile(message: Message, user: dict | None):
    if user is None:
        await message.answer("Сначала зарегистрируйтесь.")
        return
    
    from utils.validation import escape_html
    safe_name = escape_html(user['name'] or '—')
    safe_surname = escape_html(user['surname'] or '')
    
    region = user['region'] or ''
    if region == "Регионы пока не добавлены":
        region = ''
    safe_region = escape_html(region)
    
    interests_raw = user['interests'] or ''
    if interests_raw:
        interests_list = [i.strip() for i in interests_raw.split(',') if i.strip() and i.strip() != "Интересы пока не добавлены"]
        interests_clean = ', '.join(interests_list)
    else:
        interests_clean = ''
    safe_interests = escape_html(interests_clean)
    
    safe_gender = escape_html(user['gender'] or '')

    text = f"👤 <b>{safe_name} {safe_surname}</b>\n"
    if user['age']:
        text += f"🎂 Возраст: {user['age']}\n"
    if user['gender']:
        text += f"🚻 Пол: {safe_gender}\n"
    if region:
        text += f"📍 Регион: {safe_region}\n"
    if interests_clean:
        text += f"❤️ Интересы: {safe_interests}\n"

    missing_fields = []
    async with get_session() as session:
        user_has_region = bool(region)  
        if not user_has_region:
            region_repo = RegionRepository(session)
            regions_in_db = await region_repo.get_all_names()
            if regions_in_db: 
                missing_fields.append("регион")
        
        user_has_interests = bool(interests_clean) 
        if not user_has_interests:
            interest_repo = InterestRepository(session)
            interests_in_db = await interest_repo.get_all_names()
            if interests_in_db:  
                missing_fields.append("интересы")
    
    if missing_fields:
        text += f"\n⚠️ <b>Пожалуйста, заполните:</b> {', '.join(missing_fields)}\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать данные", callback_data="edit_profile")]
    ])

    if user['photo_file_id']:
        await message.answer_photo(
            photo=user['photo_file_id'],
            caption=text,
            reply_markup=kb,
            parse_mode=ParseMode.HTML
        )
    elif user['document_file_id']:
        await message.answer_document(
            document=user['document_file_id'],
            caption=text,
            reply_markup=kb,
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(text, reply_markup=kb, parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "edit_profile")
async def start_edit_profile(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    if user is None:
        await callback.message.answer("Ошибка. Пользователь не найден.")
        await callback.answer()
        return

    await state.update_data(
        phone=user["number"],
        edit_mode=True,  
        name=user["name"],
        surname=user["surname"],
        gender=user["gender"],
        age=user["age"],
        region=user["region"],
        interests=user["interests"].split(",") if user["interests"] else [],        
        photo_file_id=user["photo_file_id"],
        document_file_id=user["document_file_id"],
        location_lat=user["location_lat"],
        location_lon=user["location_lon"],
        single_edit=False 
    )
    
    await callback.message.answer(
        "Что вы хотите изменить?",
        reply_markup=get_edit_profile_menu()
    )
    await callback.answer()

@router.callback_query(F.data == "back_to_profile")
async def back_to_profile_handler(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    await state.clear()
    try:
        await callback.message.delete()
    except:
        pass
    await show_my_profile(callback.message, user)
    await callback.answer()

@router.callback_query(F.data == "edit_field_name")
async def edit_field_name(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    await state.update_data(single_edit=True)
    await state.set_state(Registration.name)
    data = await state.get_data()
    current = data.get("name", "не указано")
    await callback.message.answer(
        f"Текущее имя: {current}\nВведите новое имя:",
        reply_markup=get_skip_edit_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "edit_field_surname")
async def edit_field_surname(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    await state.update_data(single_edit=True)
    await state.set_state(Registration.surname)
    data = await state.get_data()
    current = data.get("surname", "не указано")
    await callback.message.answer(
        f"Текущая фамилия: {current}\nВведите новую фамилию:",
        reply_markup=get_skip_edit_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "edit_field_gender")
async def edit_field_gender(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    await state.update_data(single_edit=True)
    await state.set_state(Registration.gender)
    data = await state.get_data()
    current = data.get("gender") or "не выбран"
    await callback.message.answer(
        f"Текущий пол: {current}\nВыберите пол:",
        reply_markup=get_gender_keyboard(edit_mode=True)
    )
    await callback.answer()

@router.callback_query(F.data == "edit_field_age")
async def edit_field_age(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    await state.update_data(single_edit=True)
    await state.set_state(Registration.age)
    data = await state.get_data()
    current = data.get("age", "не указано")
    await callback.message.answer(
        f"Текущий возраст: {current}\nВведите возраст:",
        reply_markup=get_skip_edit_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "edit_field_region")
async def edit_field_region(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    await state.update_data(single_edit=True)
    await state.set_state(Registration.region)
    data = await state.get_data()
    current = data.get("region", "не указано")
    
    async with get_session() as session:
        region_repo = RegionRepository(session)
        regions_list = await region_repo.get_all_names()

    await callback.message.answer(
        f"Текущий регион: {current}\nВыберите регион:",
        reply_markup=get_region_keyboard(regions_list, edit_mode=True)
    )
    await callback.answer()

@router.callback_query(F.data == "edit_field_interests")
async def edit_field_interests(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    await state.update_data(single_edit=True)
    await state.set_state(Registration.interests)
    data = await state.get_data()
    current_list = data.get("interests", [])
    current = ", ".join(current_list) if current_list else "не указаны"
    
    async with get_session() as session:
        interest_repo = InterestRepository(session)
        interests_list = await interest_repo.get_all_names()
    
    await callback.message.answer(
        f"Текущие интересы: {current}\nВыберите новые интересы:",
        reply_markup=get_interests_keyboard(interests_list, current_list, edit_mode=True)
    )
    await callback.answer()

@router.callback_query(F.data == "edit_field_photo")
async def edit_field_photo(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    await state.update_data(single_edit=True)
    await state.set_state(Registration.photo)
    data = await state.get_data()
    current = "есть" if data.get("photo_file_id") or data.get("document_file_id") else "нет"
    await callback.message.answer(
        f"Текущее фото: {current}\nЗагрузите новое фото:",
        reply_markup=get_photo_keyboard(edit_mode=True)
    )
    await callback.answer()

@router.callback_query(F.data == "edit_field_location")
async def edit_field_location(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    await state.update_data(single_edit=True)
    await state.set_state(Registration.location)
    data = await state.get_data()
    current = "есть" if data.get("location_lat") else "нет"
    await callback.message.answer(
        f"Текущее местоположение: {current}\nОтправьте новое местоположение:",
        reply_markup=get_location_keyboard(edit_mode=True)
    )
    await callback.answer()


@router.message(F.text == "❓ Помощь")
async def show_help(message: Message, user: dict | None):
    help_text = (
        "📖 <b>Инструкция по работе с ботом</b>\n\n"
        
        "<b>👤 Мой профиль</b>\n"
        "Просмотр и редактирование ваших данных: имя, фамилия, возраст, пол, регион, интересы, фото.\n\n"
        
        "<b>💬 Общение</b>\n"
        "• <b>Друзья</b> — список ваших друзей, возможность начать чат\n"
        "• <b>Поиск друзей</b> — найдите людей по интересам, региону, возрасту и полу\n\n"
        
        "<b>🎉 Мероприятия</b>\n"
        "• <b>Мероприятия друзей</b> — смотрите события от друзей и участвуйте в них\n"
        "• <b>Мои мероприятия</b> — ваши созданные события и те, в которых вы участвуете\n"
        "• <b>Создать мероприятие</b> — организуйте своё событие и пригласите друзей\n\n"
        
        "<b>💡 Полезные советы:</b>\n"
        "• Заполните профиль полностью для лучшего поиска друзей\n"
        "• Добавьте несколько интересов для расширения круга знакомств\n"
        "• Используйте геолокацию для поиска людей рядом\n"
        "• Приглашайте друзей на мероприятия через бота\n\n"
        
        "Если возникли вопросы, используйте команду /start для перезапуска бота."
    )
    
    await message.answer(help_text, parse_mode=ParseMode.HTML)
