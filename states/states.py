from aiogram.fsm.state import State, StatesGroup

class Registration(StatesGroup):
    name = State()
    surname = State()
    gender = State()
    age = State()
    region = State()
    interests = State()
    photo = State()
    location = State()
    

class AdminLoad(StatesGroup):
    waiting_excel = State()


class CreateEvent(StatesGroup):
    name = State()
    date = State()
    time = State()
    interests = State()
    address = State()
    description = State()
    photo = State()
    invite_friends = State()
    confirm = State()
    confirm_address = State()
