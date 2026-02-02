import logging
import re
from aiogram import Router, F, types
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from states.states import Registration
from keyboards.builders import (
    get_skip_edit_keyboard, get_gender_keyboard, get_region_keyboard,
    get_interests_keyboard, get_photo_keyboard, get_location_keyboard,
    get_user_main_menu, get_contact_keyboard, get_edit_profile_menu
)
from utils.validation import is_valid_name, is_valid_age, normalize_phone
from database import get_session
from database.repositories import UserRepository, RegionRepository, InterestRepository

router = Router()

@router.message(F.text == "▶️ Продолжить регистрацию")
async def resume_registration(message: Message, state: FSMContext, user: dict | None):
    if not user:
        await message.answer("Ошибка. Пользователь не найден.")
        return

    if user["registered"]:
        await message.answer(
            "Регистрация уже завершена ✅",
            reply_markup=get_user_main_menu()
        )
        return

    await state.update_data(
        phone=user["number"]
    )

    await state.set_state(Registration.name)

    await message.answer(
        "Продолжаем регистрацию.\nВведите ваше имя:",
        reply_markup=types.ReplyKeyboardRemove()
    )


@router.message(F.contact)
async def process_contact(message: Message, state: FSMContext, user: dict | None):
    raw_phone = message.contact.phone_number.strip()
    phone = normalize_phone(raw_phone)  
    tg_id = message.from_user.id

    if user is not None:
        if user["role"] == "admin":
            from keyboards.builders import get_admin_menu_keyboard
            await message.answer(
                "Добро пожаловать в админ-панель!",
                reply_markup=get_admin_menu_keyboard()
            )
            return

        if user["registered"]:
            await message.answer(
                f"С возвращением, {user['name'] or 'пользователь'}!",
                reply_markup=get_user_main_menu()
            )
            return
        else:
            await message.answer("Давайте завершим регистрацию.")
    else:
        async with get_session() as session:
            user_repo = UserRepository(session)
            success = await user_repo.register_phone(phone, tg_id)
            
        if success:
            await message.answer(f"Номер добавлен. Заполняем профиль.")
        else:
            # If register failed, it might be that user exists but wasn't in cache yet
            # Let's try to proceed
            pass

    await state.update_data(phone=phone)
    await state.set_state(Registration.name)
    await message.answer("Введите ваше Имя:", reply_markup=types.ReplyKeyboardRemove())


@router.message(Registration.name)
async def reg_name(message: Message, state: FSMContext, user: dict | None):
    data = await state.get_data()
    edit_mode = data.get("edit_mode", False)

    name = message.text.strip()
    
    if edit_mode and name == "Оставить без изменений":
        name = data.get("name")
    else:
        if not is_valid_name(name):
            await message.answer("🚫 Не похоже на имя. Только буквы. Попробуйте еще раз.")
            return

    try:
        await state.update_data(name=name)

        if data.get("single_edit"):
            data["name"] = name
            async with get_session() as session:
                user_repo = UserRepository(session)
                await user_repo.update_profile(data["phone"], data)
            
            await message.answer("Готово!", reply_markup=get_user_main_menu())
            await message.answer("Имя обновлено!", reply_markup=get_edit_profile_menu())
            await state.set_state(None)
            return

        if edit_mode:
            current = data.get("surname", "не указано")
            await message.answer(
                f"Текущая фамилия: {current}\nВведите новую фамилию или оставьте без изменений:",
                reply_markup=get_skip_edit_keyboard()
            )
        else:
            await message.answer("Введите вашу фамилию:")

        await state.set_state(Registration.surname)
    except Exception as e:
        logging.error(f"Error in reg_name for user {message.from_user.id}: {e}")
        await message.answer("😔 Произошла ошибка. Попробуйте ещё раз или обратитесь к администратору.")
        await state.clear()


@router.message(Registration.surname)
async def reg_surname(message: Message, state: FSMContext, user: dict | None):
    data = await state.get_data()
    edit_mode = data.get("edit_mode", False)

    surname = message.text.strip()
    
    if edit_mode and surname == "Оставить без изменений":
        surname = data.get("surname")
    else:
        if not is_valid_name(surname):
            await message.answer("🚫 Не похоже на фамилию. Только буквы. Попробуйте еще раз.")
            return

    await state.update_data(surname=surname)

    if data.get("single_edit"):
        data["surname"] = surname
        async with get_session() as session:
            user_repo = UserRepository(session)
            await user_repo.update_profile(data["phone"], data)
            
        await message.answer("Готово!", reply_markup=get_user_main_menu())
        await message.answer("Фамилия обновлена!", reply_markup=get_edit_profile_menu())
        await state.set_state(None)
        return

    if edit_mode:
        current = data.get("gender") or "не указан"
        await message.answer(f"Текущий пол: {current}")

    await message.answer("Укажите пол:", reply_markup=get_gender_keyboard(edit_mode))
    await state.set_state(Registration.gender)

@router.message(Registration.gender)
async def reg_gender(message: Message, state: FSMContext, user: dict | None):
    data = await state.get_data()
    edit_mode = data.get("edit_mode", False)

    gender = message.text.strip()
    
    if edit_mode and gender == "Оставить без изменений":
        gender = data.get("gender")
    elif gender == "Пропустить":
        gender = None
    elif gender not in ["Муж", "Жен"]:
        await message.answer("🚫 Выберите из кнопок или пропустите.")
        return

    await state.update_data(gender=gender)

    if data.get("single_edit"):
        data["gender"] = gender
        async with get_session() as session:
            user_repo = UserRepository(session)
            await user_repo.update_profile(data["phone"], data)
            
        await message.answer("Готово!", reply_markup=get_user_main_menu())
        await message.answer("Пол обновлен!", reply_markup=get_edit_profile_menu())
        await state.set_state(None)
        return

    if edit_mode:
        current = data.get("age", "не указан")
        await message.answer(
            f"Текущий возраст: {current}\nВведите новый возраст или оставьте без изменений:",
            reply_markup=get_skip_edit_keyboard()
        )
    else:
        await message.answer("Укажите возраст:", reply_markup=types.ReplyKeyboardRemove())

    await state.set_state(Registration.age)

@router.message(Registration.age)
async def reg_age(message: Message, state: FSMContext, user: dict | None):
    data = await state.get_data()
    edit_mode = data.get("edit_mode", False)

    age = message.text.strip()
    
    if edit_mode and age == "Оставить без изменений":
        age = data.get("age")
    else:
        if not is_valid_age(age):
            await message.answer("🚫 Не похоже на возраст. Только цифры. Попробуйте еще раз.")
            return
        age = int(age)

    await state.update_data(age=age)

    if data.get("single_edit"):
        data["age"] = age
        async with get_session() as session:
            user_repo = UserRepository(session)
            await user_repo.update_profile(data["phone"], data)
            
        await message.answer("Готово!", reply_markup=get_user_main_menu())
        await message.answer("Возраст обновлен!", reply_markup=get_edit_profile_menu())
        await state.set_state(None)
        return

    if edit_mode:
        current = data.get("region", "не указан")
        await message.answer(f"Текущий регион: {current}")

    # Fetch regions async
    async with get_session() as session:
        region_repo = RegionRepository(session)
        regions_list = await region_repo.get_all_names()
        
    await message.answer("Выберите ваш регион:", reply_markup=get_region_keyboard(regions_list, edit_mode))
    await state.set_state(Registration.region)

@router.message(Registration.region)
async def reg_region(message: Message, state: FSMContext, user: dict | None):
    data = await state.get_data()
    edit_mode = data.get("edit_mode", False)

    region = message.text.strip()
    
    # Fetch regions async for validation
    async with get_session() as session:
        region_repo = RegionRepository(session)
        regions_list = await region_repo.get_all_names()
    
    if edit_mode and region == "Оставить без изменений":
        region = data.get("region")
    else:
        if region not in regions_list:
            await message.answer("🚫 Выберите из списка.")
            return

    await state.update_data(region=region)

    if data.get("single_edit"):
        data["region"] = region
        async with get_session() as session:
            user_repo = UserRepository(session)
            await user_repo.update_profile(data["phone"], data)
            
        await message.answer("Готово!", reply_markup=get_user_main_menu())
        await message.answer("Регион обновлен!", reply_markup=get_edit_profile_menu())
        await state.set_state(None)
        return

    if edit_mode:
        current = ", ".join(data.get("interests", [])) or "не указаны"
        await message.answer(f"Текущие интересы: {current}")

    if not edit_mode:
        await state.update_data(interests=[])
    
    # Fetch interests async
    async with get_session() as session:
        interest_repo = InterestRepository(session)
        interests_list = await interest_repo.get_all_names()
    
    await message.answer(
        "Укажите ваши интересы (можно выбрать несколько):",
        reply_markup=get_interests_keyboard(interests_list, data.get("interests", []), edit_mode)
    )
    await state.set_state(Registration.interests)

@router.callback_query(Registration.interests)
async def reg_interests_callback(callback: types.CallbackQuery, state: FSMContext, user: dict | None):
    data = await state.get_data()
    edit_mode = data.get("edit_mode", False)
    interests = data.get('interests', [])

    if callback.data == "keep_current":
        
        if data.get("single_edit"):
            await callback.message.answer("Готово!", reply_markup=get_user_main_menu())
            await callback.message.answer("Интересы оставлены без изменений.", reply_markup=get_edit_profile_menu())
            await state.set_state(None)
            await callback.answer()
            return

        await state.set_state(Registration.photo)
        
        if edit_mode:
            current = "есть" if data.get("photo_file_id") or data.get("document_file_id") else "нет"
            await callback.message.answer(f"Текущее фото: {current}")
        
        await callback.message.answer(
            "Загрузите фото (jpg, jpeg, png) или пропустите:",
            reply_markup=get_photo_keyboard(edit_mode)
        )
        await callback.answer()
        return

    if callback.data == "done":
        if not interests:
            await callback.answer("🚫 Укажите хотя бы один интерес.")
            return

        await state.update_data(interests=interests)

        if data.get("single_edit"):
            data["interests"] = interests
            async with get_session() as session:
                user_repo = UserRepository(session)
                await user_repo.update_profile(data["phone"], data)
            
            await callback.message.answer("Готово!", reply_markup=get_user_main_menu())
            await callback.message.answer("Интересы обновлены!", reply_markup=get_edit_profile_menu())
            await state.set_state(None)
            await callback.answer()
            return

        if edit_mode:
            current = "есть" if data.get("photo_file_id") or data.get("document_file_id") else "нет"
            await callback.message.answer(f"Текущее фото: {current}")

        await state.set_state(Registration.photo)
        await callback.message.answer(
            "Загрузите фото (jpg, jpeg, png) или пропустите:",
            reply_markup=get_photo_keyboard(edit_mode)
        )
        await callback.answer()
        return

    if callback.data in interests:
        interests.remove(callback.data)
    else:
        interests.append(callback.data)

    await state.update_data(interests=interests)
    
    # Fetch interests async to update keyboard
    async with get_session() as session:
        interest_repo = InterestRepository(session)
        interests_list = await interest_repo.get_all_names()
        
    await callback.message.edit_reply_markup(
        reply_markup=get_interests_keyboard(interests_list, interests, edit_mode)
    )
    await callback.answer()


@router.message(Registration.photo, F.text == "Оставить без изменений")
async def reg_photo_keep(message: Message, state: FSMContext, user: dict | None):
    data = await state.get_data()
    edit_mode = data.get("edit_mode", False)
    
    if data.get("single_edit"):
        await message.answer("Готово!", reply_markup=get_user_main_menu())
        await message.answer("Фото оставлено без изменений.", reply_markup=get_edit_profile_menu())
        await state.set_state(None)
        return

    if edit_mode:
        current = "есть" if data.get("location_lat") else "нет"
        await message.answer(f"Текущее местоположение: {current}")

    await state.set_state(Registration.location)
    await ask_user_location(message, edit_mode)


@router.message(Registration.photo, F.photo)
async def reg_photo_media(message: Message, state: FSMContext, user: dict | None):
    data = await state.get_data()
    edit_mode = data.get("edit_mode", False)

    photo = message.photo[-1]
    await state.update_data(photo_file_id=photo.file_id, document_file_id=None)

    if data.get("single_edit"):
        # Explicit update before saving
        data["photo_file_id"] = photo.file_id
        data["document_file_id"] = None
        
        async with get_session() as session:
            user_repo = UserRepository(session)
            await user_repo.update_profile(data["phone"], data)
            
        await message.answer("Готово!", reply_markup=get_user_main_menu())
        await message.answer("Фото обновлено!", reply_markup=get_edit_profile_menu())
        await state.set_state(None)
        return

    if edit_mode:
        current = "есть" if data.get("location_lat") else "нет"
        await message.answer(f"Текущее местоположение: {current}")

    await state.set_state(Registration.location)
    await ask_user_location(message, edit_mode)


@router.message(Registration.photo, F.document)
async def reg_photo_document(message: Message, state: FSMContext, user: dict | None):
    doc = message.document

    if not doc.mime_type or not doc.mime_type.startswith("image/"):
        await message.answer("🚫 Файл не является изображением.")
        return

    if not doc.file_name.lower().endswith((".jpg", ".jpeg", ".png")):
        await message.answer("🚫 Поддерживаются только JPG, JPEG, PNG.")
        return

    await state.update_data(document_file_id=doc.file_id, photo_file_id=None)

    data = await state.get_data()
    edit_mode = data.get("edit_mode", False)

    if data.get("single_edit"):
        # Explicit update
        data["document_file_id"] = doc.file_id
        data["photo_file_id"] = None
        
        async with get_session() as session:
            user_repo = UserRepository(session)
            await user_repo.update_profile(data["phone"], data)
            
        await message.answer("Готово!", reply_markup=get_user_main_menu())
        await message.answer("Фото обновлено!", reply_markup=get_edit_profile_menu())
        await state.set_state(None)
        return

    if edit_mode:
        current = "есть" if data.get("location_lat") else "нет"
        await message.answer(f"Текущее местоположение: {current}")

    await state.set_state(Registration.location)
    await ask_user_location(message, edit_mode)


@router.message(Registration.photo, F.text == "Пропустить")
async def reg_photo_skip(message: Message, state: FSMContext, user: dict | None):
    data = await state.get_data()
    edit_mode = data.get("edit_mode", False)

    await state.update_data(photo_file_id=None, document_file_id=None)

    if data.get("single_edit"):
        data["photo_file_id"] = None
        data["document_file_id"] = None
        
        async with get_session() as session:
            user_repo = UserRepository(session)
            await user_repo.update_profile(data["phone"], data)
            
        await message.answer("Готово!", reply_markup=get_user_main_menu())
        await message.answer("Фото удалено/пропущено!", reply_markup=get_edit_profile_menu())
        await state.set_state(None)
        return

    if edit_mode:
        current = "есть" if data.get("location_lat") else "нет"
        await message.answer(f"Текущее местоположение: {current}")

    await state.set_state(Registration.location)
    await ask_user_location(message, edit_mode)


@router.message(Registration.photo)
async def reg_photo_invalid(message: Message, state: FSMContext, user: dict | None):
    await message.answer(
        "🚫 Отправьте фото (как изображение или файл JPG/PNG) "
        "или нажмите «Пропустить»"
    )

async def ask_user_location(message: Message, edit_mode=False):
    await message.answer(
        "Укажите ваше местоположение:\n\n"
        "📱 На телефоне — нажмите «Поделиться геолокацией». "
        "Для этого на устройстве должна быть включена геолокация.\n"
        "💻 На ПК — выберите «Ручной ввод» и введите координаты вручную "
        "(широта, долгота, например: 55.7558, 37.6173).\n"
        "Можно также нажать «Пропустить», если не хотите указывать местоположение.",
        reply_markup=get_location_keyboard(edit_mode)
    )


@router.message(Registration.location, F.text == "Оставить без изменений")
async def reg_location_keep(message: Message, state: FSMContext, user: dict | None):
    data = await state.get_data()
    edit_mode = data.get("edit_mode", False)
    
    if data.get("single_edit"):
        await message.answer("Готово!", reply_markup=get_user_main_menu())
        await message.answer("Местоположение оставлено без изменений.", reply_markup=get_edit_profile_menu())
        await state.set_state(None)
        return

    # Finish registration/update
    async with get_session() as session:
        user_repo = UserRepository(session)
        await user_repo.update_profile(data["phone"], data)
        
    await state.clear()

    text = "Профиль обновлён!" if edit_mode else "Регистрация завершена! Добро пожаловать 🎉"
    await message.answer(text, reply_markup=get_user_main_menu())

@router.message(Registration.location, F.location)
async def reg_location_ok(message: Message, state: FSMContext, user: dict | None):
    data = await state.get_data()
    edit_mode = data.get("edit_mode", False)

    await state.update_data(
        location_lat=message.location.latitude,
        location_lon=message.location.longitude
    )
    # Refresh data
    data = await state.get_data()
    
    async with get_session() as session:
        user_repo = UserRepository(session)
        await user_repo.update_profile(data["phone"], data)
    
    if data.get("single_edit"):
        await message.answer("Готово!", reply_markup=get_user_main_menu())
        await message.answer("Местоположение обновлено!", reply_markup=get_edit_profile_menu())
        await state.set_state(None)
        return
        
    await state.clear()

    text = "Профиль обновлён!" if edit_mode else "Регистрация завершена! Добро пожаловать 🎉"
    await message.answer(text, reply_markup=get_user_main_menu())


@router.message(Registration.location, F.text == "💻 Ручной ввод координат")
async def reg_location_manual_start(message: Message, state: FSMContext, user: dict | None):
    data = await state.get_data()
    edit_mode = data.get("edit_mode", False)

    current = "есть" if edit_mode and data.get("location_lat") else "не указано"
    await message.answer(
        f"Текущее местоположение: {current}\n"
        "Введите координаты вручную в формате: широта, долгота\n"
        "Пример: 55.7558, 37.6173"
    )


@router.message(Registration.location)
async def reg_location_manual_process(
    message: Message,
    state: FSMContext,
    user: dict | None
):
    if not message.text:
        await message.answer(
            "Отправь координаты в формате:\n"
            "55.7558, 37.6173\n"
            "или нажми «Пропустить»"
        )
        return

    data = await state.get_data()
    edit_mode = data.get("edit_mode", False)

    text = message.text.strip()

    if text == "Пропустить":
        await state.update_data(location_lat=None, location_lon=None)
        updated_data = await state.get_data()
        
        phone = updated_data.get("phone")
        if not phone and user:
            phone = user.get("number")
            updated_data["phone"] = phone

        if phone:
            async with get_session() as session:
                user_repo = UserRepository(session)
                await user_repo.update_profile(phone, updated_data)
        
        if data.get("single_edit"):
            await message.answer("Готово!", reply_markup=get_user_main_menu())
            await message.answer("Местоположение пропущено/удалено.", reply_markup=get_edit_profile_menu())
            await state.set_state(None)
            return

        await state.clear()

        text_msg = (
            "Профиль обновлён!"
            if edit_mode
            else "Регистрация завершена! Добро пожаловать 🎉"
        )
        await message.answer(text_msg, reply_markup=get_user_main_menu())
        return

    if text == "Оставить без изменений":
        if data.get("single_edit"):
            await message.answer("Готово!", reply_markup=get_user_main_menu())
            await message.answer("Местоположение оставлено без изменений.", reply_markup=get_edit_profile_menu())
            await state.set_state(None)
            return

        phone = data.get("phone")
        if not phone and user:
            phone = user.get("number")
            data["phone"] = phone
            
        if phone:
            async with get_session() as session:
                user_repo = UserRepository(session)
                await user_repo.update_profile(phone, data)
        await state.clear()

        text_msg = "Профиль обновлён!" if edit_mode else "Регистрация завершена! Добро пожаловать 🎉"
        await message.answer(text_msg, reply_markup=get_user_main_menu())
        return

    match = re.match(
        r'^\s*(-?\d+(\.\d+)?)\s*,\s*(-?\d+(\.\d+)?)\s*$',
        text
    )

    if not match:
        await message.answer(
            "🚫 Неверный формат.\n"
            "Пример: 55.7558, 37.6173\n"
            "Или нажмите «Пропустить»"
        )
        return

    lat = float(match.group(1))
    lon = float(match.group(3))

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        await message.answer(
            "🚫 Координаты вне допустимого диапазона.\n"
            "Широта: от -90 до 90\n"
            "Долгота: от -180 до 180"
        )
        return

    await state.update_data(location_lat=lat, location_lon=lon)
    updated_data = await state.get_data()
    
    phone = updated_data.get("phone")
    if not phone and user:
        phone = user.get("number")
        updated_data["phone"] = phone
        
    if phone:
        async with get_session() as session:
            user_repo = UserRepository(session)
            await user_repo.update_profile(phone, updated_data)
    
    if data.get("single_edit"):
        await message.answer("Готово!", reply_markup=get_user_main_menu())
        await message.answer("Местоположение обновлено!", reply_markup=get_edit_profile_menu())
        await state.set_state(None)
        return
        
    await state.clear()

    text_msg = (
        "Профиль обновлён!"
        if edit_mode
        else "Регистрация завершена! Добро пожаловать 🎉"
    )
    await message.answer(text_msg, reply_markup=get_user_main_menu())
