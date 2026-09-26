"""
أدوات مساعدة:
- show_screen: يعدّل رسالة البوت الحالية بدل حذفها وإرسال واحدة جديدة (نظام "شاشة واحدة" سريع).
- check_subscription: يتحقق من اشتراك المستخدم بالقناة الإجبارية.
"""
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

import sheets_service as db


def _with_support_button(reply_markup: InlineKeyboardMarkup | None) -> InlineKeyboardMarkup:
    """يضيف زر 'تواصل مع الدعم' بشكل دائم أسفل أي شاشة يعرضها البوت.
    إذا كان رابط الدعم بالإعدادات رابط تلغرام صالح (فيه يوزر)، الزر يفتح المحادثة مباشرة."""
    rows = list(reply_markup.inline_keyboard) if reply_markup else []
    link = db.get_settings().get("SUPPORT_LINK", "").strip()
    if link.startswith("http"):
        rows.append([InlineKeyboardButton(text="🆘 تواصل مع الدعم", url=link)])
    else:
        rows.append([InlineKeyboardButton(text="🆘 تواصل مع الدعم", callback_data="support")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def show_screen(
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    text: str | None = None,
    photo: str | None = None,
    reply_markup: InlineKeyboardMarkup | None = None,
):
    """يعرض شاشة جديدة عبر تعديل رسالة الحالة السابقة إن أمكن، وإلا يحذفها ويرسل بديلة — بأسرع طريقة ممكنة.
    كل شاشة تُضاف لها تلقائيًا زر تواصل مع الدعم بشكل ثابت."""
    reply_markup = _with_support_button(reply_markup)
    data = await state.get_data()
    msg_id = data.get("screen_msg_id")
    had_photo = data.get("screen_has_photo", False)

    try:
        if msg_id and (bool(photo) == bool(had_photo)):
            if photo:
                await bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=text, reply_markup=reply_markup)
            else:
                await bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=text, reply_markup=reply_markup)
            await state.update_data(screen_msg_id=msg_id, screen_has_photo=bool(photo))
            return
    except TelegramBadRequest:
        pass

    if msg_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except TelegramBadRequest:
            pass

    if photo:
        msg = await bot.send_photo(chat_id=chat_id, photo=photo, caption=text, reply_markup=reply_markup)
    else:
        msg = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup)

    await state.update_data(screen_msg_id=msg.message_id, screen_has_photo=bool(photo))


async def is_subscribed(bot: Bot, user_id: int) -> bool:
    settings = db.get_settings()
    channel_id = settings.get("CHANNEL_ID", "").strip()
    if not channel_id:
        return True
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False
