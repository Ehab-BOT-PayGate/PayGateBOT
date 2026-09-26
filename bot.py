import asyncio
import logging

from aiogram import Bot, Dispatcher, Router, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message

import sheets_service as db
from handlers import start, catalog, order, my_orders, admin, broadcast

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------- Router تشخيصي مؤقت ----------------
# يطبع بالـ logs أي رسالة تصل للبوت مع تفاصيلها الكاملة، بغض النظر إن كانت
# ستُعالج من روتر آخر أو لا. يُستخدم فقط لتشخيص مشكلة "is not handled".
# احذف هذا القسم كاملاً بعد ما تنتهي من التشخيص.
debug_router = Router()


@debug_router.message()
async def debug_any_message(message: Message):
    logger.warning(
        "🔍 DEBUG: رسالة وصلت | from_user_id=%s | chat_id=%s | text=%r | content_type=%s",
        message.from_user.id if message.from_user else None,
        message.chat.id,
        message.text,
        message.content_type,
    )
    # لا نوقف المعالجة هنا — هذا الروتر سيُسجَّل قبل الباقي بشكل منفصل عبر
    # outer_middleware بدل ما يمنع باقي الـ routers من استقبال الرسالة.


async def log_all_updates(handler, event, data):
    """Middleware خارجي: يُسجّل أي تحديث (رسالة أو ضغطة زر) قبل أي فلترة،
    فيوضح فورًا هل الرسالة تصل من تلغرام أصلاً أو لا."""
    try:
        if isinstance(event, Message):
            logger.warning(
                "📩 UPDATE وصل | type=Message | user_id=%s | text=%r",
                event.from_user.id if event.from_user else None,
                event.text,
            )
        else:
            logger.warning("📩 UPDATE وصل | type=%s", type(event).__name__)
    except Exception:
        logger.exception("فشل تسجيل UPDATE بالـ middleware التشخيصي")
    return await handler(event, data)


# ---------------- نهاية القسم التشخيصي ----------------


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

    # نسجّل الـ middleware التشخيصي على أعلى مستوى — سيرى كل تحديث خام
    # قبل أي فلترة من أي روتر.
    dp.update.outer_middleware(log_all_updates)

    dp.include_router(start.router)
    dp.include_router(catalog.router)
    dp.include_router(order.router)
    dp.include_router(my_orders.router)
    dp.include_router(admin.router)
    dp.include_router(broadcast.router)
    dp.include_router(debug_router)  # يجب أن يبقى آخر روتر دائمًا

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
