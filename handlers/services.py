from aiogram import Router, F
from aiogram.types import CallbackQuery
from keyboards.inline import get_back_keyboard
from utils.texts import get_text

router = Router()

@router.callback_query(F.data.startswith("service_"))
async def show_service(callback: CallbackQuery):
    service = callback.data.split("_")[1]
    text_map = {
        "germany": get_text("ru", "germany_desc"),
        "china": get_text("ru", "china_desc"),
        "schengen": get_text("ru", "schengen_desc"),
        "other": get_text("ru", "other_desc")
    }
    text = text_map.get(service, get_text("ru", "services"))
    await callback.message.edit_text(
        text,
        reply_markup=get_back_keyboard()
    )
    await callback.answer()
