from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

def get_edit_profile_menu():
    """Клавиатура для меню редактирования профиля"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Имя", callback_data="edit_field_name"),
         InlineKeyboardButton(text="✏️ Фамилия", callback_data="edit_field_surname")],
        [InlineKeyboardButton(text="🚻 Пол", callback_data="edit_field_gender"),
         InlineKeyboardButton(text="🎂 Возраст", callback_data="edit_field_age")],
        [InlineKeyboardButton(text="📍 Регион", callback_data="edit_field_region")],
        [InlineKeyboardButton(text="❤️ Интересы", callback_data="edit_field_interests")],
        [InlineKeyboardButton(text="📸 Фото", callback_data="edit_field_photo")],
        [InlineKeyboardButton(text="🌍 Местоположение", callback_data="edit_field_location")],
        [InlineKeyboardButton(text="🔙 Назад в профиль", callback_data="back_to_profile")]
    ])

def get_event_card_keyboard_optimized(event_id: int, user_phone: str, 
                                     organizer_phone: str, is_participant: bool):
    """Клавиатура для карточки мероприятия друзей (с кнопкой карты по ТЗ)"""
    if user_phone == organizer_phone:
        return None  
    
    buttons = [[InlineKeyboardButton(text="🗺 Смотреть на карте", 
                                    callback_data=f"view_map_{event_id}")]]
    
    if is_participant:
        buttons.append([InlineKeyboardButton(text="❌ Отказаться от участия", 
                                callback_data=f"leave_event_{event_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="✅ Участвовать", 
                                callback_data=f"join_event_{event_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_my_event_card_keyboard(event_id: int, is_organizer: bool):
    """Клавиатура для карточки 'Мои мероприятия' (с кнопками карты и участников по ТЗ)"""
    buttons = [
        [InlineKeyboardButton(text="🗺 Смотреть на карте", 
                             callback_data=f"view_map_{event_id}")],
        [InlineKeyboardButton(text="👥 Смотреть список участников", 
                             callback_data=f"view_participants_{event_id}")]
    ]
    
    if is_organizer:
        buttons.append([InlineKeyboardButton(text="💌 Пригласить друзей", 
                                callback_data=f"invite_to_event_{event_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="❌ Отказаться от участия", 
                                callback_data=f"leave_event_{event_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_description_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Пропустить")],
            [KeyboardButton(text="❌ Отменить создание")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_skip_edit_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Оставить без изменений")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_event_creation_keyboard():
    """Standard keyboard for event creation with cancel option."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отменить создание")]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )


def get_resume_registration_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="▶️ Продолжить регистрацию")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_gender_keyboard(edit_mode=False):
    keyboard = [
        [KeyboardButton(text="Муж"), KeyboardButton(text="Жен")],
        [KeyboardButton(text="Пропустить")]
    ]
    if edit_mode:
        keyboard.append([KeyboardButton(text="Оставить без изменений")])
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_region_keyboard(regions: list[str], edit_mode=False):
    """Динамическая клавиатура регионов из списка"""
    if not regions:
        kb = [[KeyboardButton(text="⏭ Регионы еще не добавлены (пропустить)")]]
    else:
        kb = [[KeyboardButton(text=region)] for region in regions]
    
    if edit_mode:
        kb.append([KeyboardButton(text="Оставить без изменений")])
    
    return ReplyKeyboardMarkup(
        keyboard=kb,
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_interests_keyboard(all_interests: list[str], selected: list[str] = [], edit_mode=False) -> InlineKeyboardMarkup:
    """Динамическая inline-клавиатура интересов из списка"""
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[])
    
    if not all_interests:
        inline_kb.inline_keyboard.append([
            InlineKeyboardButton(text="⏭ Интересы еще не добавлены (пропустить)", callback_data="skip_interests")
        ])
    else:
        for interest in all_interests:
            text = f"✅ {interest}" if interest in selected else interest
            callback_data = interest[:60] if len(interest.encode('utf-8')) <= 60 else interest[:20]
            inline_kb.inline_keyboard.append([
                InlineKeyboardButton(text=text, callback_data=callback_data)
            ])
        
        buttons_row = [InlineKeyboardButton(text="Готово", callback_data="done")]
        if edit_mode:
            buttons_row.append(InlineKeyboardButton(text="Оставить без изменений", callback_data="keep_current"))
        
        inline_kb.inline_keyboard.append(buttons_row)
    
    return inline_kb

def get_photo_keyboard(edit_mode=False):
    keyboard = [[KeyboardButton(text="Пропустить")]]
    
    if edit_mode:
        keyboard.append([KeyboardButton(text="Оставить без изменений")])
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_admin_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📥 Загрузить списки")],
            [KeyboardButton(text="📊 Отчет по пользователям")],
            [KeyboardButton(text="📅 Отчет по мероприятиям")],
        ],
        resize_keyboard=True
    )


def get_user_main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Мой профиль")],
            [KeyboardButton(text="💬 Общение")],
            [KeyboardButton(text="🎉 Мероприятия")],
            [KeyboardButton(text="❓ Помощь")],
        ],
        resize_keyboard=True,
        one_time_keyboard=False  
    )

def get_events_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Мероприятия друзей")],
            [KeyboardButton(text="Мои мероприятия")],
            [KeyboardButton(text="Создать мероприятие")],
            [KeyboardButton(text="Назад")],
        ],
        resize_keyboard=True
    )

def get_start_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Запустить")]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

def get_contact_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Предоставить номер", request_contact=True)]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )

def get_location_keyboard(edit_mode=False):
    keyboard = [
        [KeyboardButton(text="📱 Поделиться геолокацией", request_location=True)],
        [KeyboardButton(text="💻 Ручной ввод координат")],
        [KeyboardButton(text="Пропустить")]
    ]
    
    if edit_mode:
        keyboard.append([KeyboardButton(text="Оставить без изменений")])
    
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )


def get_friends_select_keyboard(friends: list, selected: list = []) -> InlineKeyboardMarkup:
    """Клавиатура для выбора друзей при приглашении на мероприятие."""
    buttons = []
    for friend in friends:
        tg_id = friend.get('tg_id')
        name = f"{friend.get('name', '')} {friend.get('surname', '')}".strip() or "Пользователь"
        is_selected = tg_id in selected
        text = f"✅ {name}" if is_selected else name
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"sel_friend_{tg_id}")])
    
    control_buttons = []
    if friends:
        control_buttons.append(InlineKeyboardButton(text="✅ Выбрать всех", callback_data="sel_all_friends"))
    control_buttons.append(InlineKeyboardButton(text="📨 Отправить", callback_data="send_invites"))
    buttons.append(control_buttons)
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_invites")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_participants_manage_keyboard(event_id: int, participants: list) -> InlineKeyboardMarkup:
    """Клавиатура для управления участниками мероприятия (организатором)."""
    buttons = []
    for p in participants:
        phone, name, surname, tg_id = p
        display_name = f"{name or ''} {surname or ''}".strip() or "Пользователь"
        phone_short = phone[-4:] if phone else "0000"
        buttons.append([
            InlineKeyboardButton(
                text=f"❌ {display_name}", 
                callback_data=f"rm_part_{event_id}_{phone_short}"
            )
        ])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"back_participants_{event_id}")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

