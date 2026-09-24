import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import sheets_service as db
from handlers import start, catalog, order, my_orders, admin

logging.basicConfig(level=logging.INFO)


async def main():
    settings = db.get_settings()
    token = settings.get("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("ضع قيمة BOT_TOKEN في شيت Settings داخل ملف Google Sheet أولًا.")

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(catalog.router)
    dp.include_router(order.router)
    dp.include_router(my_orders.router)
    dp.include_router(admin.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
