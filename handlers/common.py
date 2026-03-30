from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from keyboards.inline import get_main_menu_keyboard, get_services_keyboard, get_back_keyboard
from utils.texts import get_text
from database import save_application

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        get_text("ru", "welcome"),
        reply_markup=get_main_menu_keyboard()
    )

@router.callback_query(F.data == "main_menu")
async def main_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        get_text("ru", "menu"),
        reply_markup=get_main_menu_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "services")
async def services_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        get_text("ru", "services"),
        reply_markup=get_services_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "contacts")
async def contacts(callback: CallbackQuery):
    text = f"{get_text('ru', 'phone')}\n{get_text('ru', 'work_hours')}\n{get_text('ru', 'price_info')}"
    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "order")
async def order(callback: CallbackQuery):
    await callback.message.edit_text(
        get_text("ru", "ask_contact"),
        reply_markup=get_back_keyboard()
    )
    await callback.answer()

@router.message(F.text)
async def handle_contact(message: Message):
    save_application(
        user_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        language="ru",
        service="general",
        contact=message.text
    )
    await message.answer(
        get_text("ru", "contact_saved"),
        reply_markup=get_main_menu_keyboard()
    )
