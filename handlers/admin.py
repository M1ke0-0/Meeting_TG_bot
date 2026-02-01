import logging
import uuid
import os
from openpyxl import load_workbook
from aiogram import Router, F, types
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from states.states import AdminLoad
from keyboards.builders import get_admin_menu_keyboard
from database.common import replace_interests, replace_regions

router = Router()

@router.message(F.text == "📥 Загрузить списки")
async def admin_load_lists(message: Message, state: FSMContext, user: dict | None):
    if user is None or user["role"] != "admin":
        await message.answer("Эта функция доступна только администраторам.")
        return

    await state.set_state(AdminLoad.waiting_excel)
    await message.answer(
        "📎 Загрузите Excel-файл:\n\n"
        "• Столбец A — Интересы\n"
        "• Столбец B — Регионы"
    )

@router.message(AdminLoad.waiting_excel, F.document)
async def admin_process_excel(message: Message, state: FSMContext, user: dict | None):
    doc = message.document

    if user is None or user["role"] != "admin":
        await message.answer("Доступ запрещён.")
        return

    if not doc.file_name.lower().endswith((".xlsx", ".xls")):
        await message.answer("🚫 Поддерживаются только Excel-файлы")
        return

    MAX_FILE_SIZE = 5 * 1024 * 1024
    if doc.file_size and doc.file_size > MAX_FILE_SIZE:
        await message.answer("🚫 Файл слишком большой. Максимум 5MB.")
        return

    file_id = uuid.uuid4()
    file_ext = os.path.splitext(doc.file_name)[1]
    file_path = f"/tmp/{file_id}{file_ext}"

    try:
        file = await message.bot.get_file(doc.file_id)
        await message.bot.download_file(file.file_path, file_path)

        wb = load_workbook(file_path)
        ws = wb.active

        interests, regions = [], []
        for row in ws.iter_rows(values_only=True):
            if row and row[0]:
                interests.append(str(row[0]).strip())
            if row and len(row) > 1 and row[1]:
                regions.append(str(row[1]).strip())

        if not interests and not regions:
            await message.answer("🚫 Файл пуст или не содержит данных")
            return

        replace_interests(interests)
        replace_regions(regions)

        await state.clear()
        await message.answer("✅ Списки успешно обновлены", 
                           reply_markup=get_admin_menu_keyboard())
    except Exception as e:
        logging.error(f"Excel processing error: {e}")
        await message.answer("🚫 Ошибка обработки файла")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
        
        try:
            await message.delete()
        except Exception:
            pass

@router.message(F.text == "📊 Отчет по пользователям")
async def generate_users_report(message: Message, user: dict | None):
    if user is None or user["role"] != "admin":
        return

    from utils.excel import export_users_report
    filepath = f"/tmp/users_report_{uuid.uuid4()}.xlsx"
    
    try:
        export_users_report(filepath)
        await message.answer_document(
            document=types.FSInputFile(filepath, filename="users_report.xlsx"),
            caption="📊 Отчет по пользователям готово!"
        )
    except Exception as e:
        logging.error(f"Report error: {e}")
        await message.answer("Ошибка при создании отчета.")
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)


@router.message(F.text == "📅 Отчет по мероприятиям")
async def generate_events_report(message: Message, user: dict | None):
    if user is None or user["role"] != "admin":
        return

    from utils.excel import export_events_report
    filepath = f"/tmp/events_report_{uuid.uuid4()}.xlsx"

    try:
        export_events_report(filepath)
        await message.answer_document(
            document=types.FSInputFile(filepath, filename="events_report.xlsx"),
            caption="📅 Отчет по мероприятиям готово!"
        )
    except Exception as e:
        logging.error(f"Report error: {e}")
        await message.answer("Ошибка при создании отчета.")
    finally:
        if os.path.exists(filepath):
            os.remove(filepath)
