import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from handlers import common, services
from database import init_db

logging.basicConfig(level=logging.INFO)

async def main():
    init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(common.router)
    dp.include_router(services.router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
