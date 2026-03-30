from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.texts import get_text

def get_main_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text("ru", "services"), callback_data="services")],
        [InlineKeyboardButton(text=get_text("ru", "contacts"), callback_data="contacts")],
        [InlineKeyboardButton(text=get_text("ru", "order"), callback_data="order")]
    ])

def get_services_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text("ru", "germany_s"), callback_data="service_germany")],
        [InlineKeyboardButton(text=get_text("ru", "china"), callback_data="service_china")],
        [InlineKeyboardButton(text=get_text("ru", "schengen"), callback_data="service_schengen")],
        [InlineKeyboardButton(text=get_text("ru", "other"), callback_data="service_other")],
        [InlineKeyboardButton(text=get_text("ru", "back"), callback_data="main_menu")]


cat > keyboards/inline.py << 'EOF'
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.texts import get_text

def get_main_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text("ru", "services"), callback_data="services")],
        [InlineKeyboardButton(text=get_text("ru", "contacts"), callback_data="contacts")],
        [InlineKeyboardButton(text=get_text("ru", "order"), callback_data="order")]
    ])

def get_services_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text("ru", "germany_s"), callback_data="service_germany")],
        [InlineKeyboardButton(text=get_text("ru", "china"), callback_data="service_china")],
        [InlineKeyboardButton(text=get_text("ru", "schengen"), callback_data="service_schengen")],
        [InlineKeyboardButton(text=get_text("ru", "other"), callback_data="service_other")],
        [InlineKeyboardButton(text=get_text("ru", "back"), callback_data="main_menu")]
    ])

def get_back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=get_text("ru", "back"), callback_data="services")]
    ])
