import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import sheets_service as db
from handlers import start, catalog, order, my_orders, admin, broadcast

logging.basicConfig(level=logging.INFO)


async def main():
    settings = db.get_settings()
    token = settings.get("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("ضع قيمة BOT_TOKEN في شيت Settings داخل ملف Google Sheet أولًا.")

    # إصلاح تلقائي: يتأكد أن Orders وCustomers لديهما صف عناوين صحيح،
    # وينظّف أي تكرار قديم في Customers. آمن للتشغيل في كل إقلاع.
    logging.info("جارٍ التحقق من صفوف العناوين في الشيت...")
    db.ensure_all_headers()
    db.cleanup_customers()
    logging.info("تم التحقق من الشيت بنجاح.")

    bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(start.router)
    dp.include_router(catalog.router)
    dp.include_router(order.router)
    dp.include_router(my_orders.router)
    dp.include_router(admin.router)
    dp.include_router(broadcast.router)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
