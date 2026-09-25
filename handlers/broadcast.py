import asyncio
import logging

from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramBadRequest

import sheets_service as db
from states import AdminFlow

router = Router()
logger = logging.getLogger(__name__)

# تأخير بسيط بين كل رسالة والتي تليها لتجنّب حدود تيليجرام (~20 رسالة/ثانية)
SEND_DELAY_SECONDS = 0.05


def _is_admin(user_id: int) -> bool:
    admin_id = db.get_settings().get("ADMIN_ID", "").strip()
    return str(user_id) == admin_id


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return
    await state.clear()
    await state.set_state(AdminFlow.waiting_broadcast_content)
    await message.answer(
        "📣 أرسل الآن محتوى الرسالة التي تريد بثّها لجميع الزبائن.\n"
        "يمكنك إرسال نص فقط، أو صورة مع نص (Caption).\n\n"
        "أرسل /cancel للإلغاء في أي وقت."
    )


@router.message(Command("cancel"), StateFilter(AdminFlow.waiting_broadcast_content, AdminFlow.waiting_broadcast_button))
async def cmd_broadcast_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("تم إلغاء البث.")


@router.message(AdminFlow.waiting_broadcast_content)
async def msg_broadcast_content(message: Message, state: FSMContext):
    if message.photo:
        await state.update_data(bc_photo=message.photo[-1].file_id, bc_text=message.caption or "")
    elif message.text:
        await state.update_data(bc_photo=None, bc_text=message.text)
    else:
        await message.answer("الرجاء إرسال نص أو صورة مع نص فقط.")
        return

    await state.set_state(AdminFlow.waiting_broadcast_button)
    await message.answer(
        "🔗 إن أردت إضافة زر رابط أسفل الرسالة أرسله بالصيغة التالية:\n"
        "نص الزر | الرابط\n"
        "مثال: زورونا | https://t.me/example\n\n"
        "أو أرسل - لتجاهل الزر."
    )


@router.message(AdminFlow.waiting_broadcast_button)
async def msg_broadcast_button(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    btn_text = None
    btn_url = None
    if text != "-":
        parts = [p.strip() for p in text.split("|", 1)]
        if len(parts) == 2 and parts[0] and parts[1].startswith(("http://", "https://", "tg://")):
            btn_text, btn_url = parts
        else:
            await message.answer(
                "⚠️ الصيغة غير صحيحة. أرسل: نص الزر | الرابط (يبدأ الرابط بـ http:// أو https://)\n"
                "أو أرسل - لتجاهل الزر."
            )
            return

    await state.update_data(bc_btn_text=btn_text, bc_btn_url=btn_url)
    await _show_preview(message.bot, message.chat.id, state)


async def _show_preview(bot, chat_id, state: FSMContext):
    data = await state.get_data()
    text = data.get("bc_text") or ""
    photo = data.get("bc_photo")
    btn_text = data.get("bc_btn_text")
    btn_url = data.get("bc_btn_url")

    b = InlineKeyboardBuilder()
    if btn_text and btn_url:
        b.button(text=btn_text, url=btn_url)
    b.button(text="✅ إرسال للجميع", callback_data="broadcast:confirm", style="success")
    b.button(text="❌ إلغاء", callback_data="broadcast:cancel", style="danger")
    b.adjust(1)

    preview_note = "👀 معاينة الرسالة كما ستصل للزبائن:\n\n"
    if photo:
        await bot.send_photo(chat_id=chat_id, photo=photo, caption=preview_note + text, reply_markup=b.as_markup())
    else:
        await bot.send_message(chat_id=chat_id, text=preview_note + text, reply_markup=b.as_markup())


@router.callback_query(F.data == "broadcast:cancel")
async def cb_broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await callback.answer("تم الإلغاء")


@router.callback_query(F.data == "broadcast:confirm")
async def cb_broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("غير مصرح لك بهذا الإجراء", show_alert=True)
        return

    data = await state.get_data()
    text = data.get("bc_text") or ""
    photo = data.get("bc_photo")
    btn_text = data.get("bc_btn_text")
    btn_url = data.get("bc_btn_url")
    await state.clear()

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass
    await callback.answer("جارٍ الإرسال...")

    send_kb = None
    if btn_text and btn_url:
        b = InlineKeyboardBuilder()
        b.button(text=btn_text, url=btn_url)
        send_kb = b.as_markup()

    user_ids = db.get_broadcast_customers()
    total = len(user_ids)
    sent = 0
    blocked = 0
    failed_other = 0

    status_msg = await callback.message.answer(f"📤 جارٍ الإرسال إلى {total} زبون...")

    for i, uid in enumerate(user_ids, start=1):
        ok = await _send_one(callback.bot, uid, photo, text, send_kb)
        if ok == "sent":
            sent += 1
        elif ok == "blocked":
            blocked += 1
            try:
                db.mark_customer_blocked(uid)
            except Exception:
                logger.exception("فشل تحديث حالة الحظر للزبون %s", uid)
        else:
            failed_other += 1

        await asyncio.sleep(SEND_DELAY_SECONDS)

        if i % 25 == 0 or i == total:
            try:
                await status_msg.edit_text(f"📤 جارٍ الإرسال... {i}/{total}")
            except TelegramBadRequest:
                pass

    failed = blocked + failed_other
    report = (
        "✅ اكتمل البث.\n\n"
        f"تم الإرسال بنجاح: {sent}\n"
        f"فشل: {failed} (منهم محظور البوت: {blocked})\n"
        f"الإجمالي: {total}"
    )
    try:
        await status_msg.edit_text(report)
    except TelegramBadRequest:
        await callback.message.answer(report)


async def _send_one(bot, uid: str, photo, text: str, send_kb) -> str:
    """يرسل رسالة واحدة، مع إعادة محاولة عند تحديد حدود تيليجرام (flood control).
    يرجع 'sent' أو 'blocked' أو 'failed'."""
    try:
        if photo:
            await bot.send_photo(chat_id=int(uid), photo=photo, caption=text, reply_markup=send_kb)
        else:
            await bot.send_message(chat_id=int(uid), text=text, reply_markup=send_kb)
        return "sent"
    except TelegramRetryAfter as e:
        await asyncio.sleep(e.retry_after)
        try:
            if photo:
                await bot.send_photo(chat_id=int(uid), photo=photo, caption=text, reply_markup=send_kb)
            else:
                await bot.send_message(chat_id=int(uid), text=text, reply_markup=send_kb)
            return "sent"
        except TelegramForbiddenError:
            return "blocked"
        except Exception:
            logger.exception("فشل إرسال البث للزبون %s بعد إعادة المحاولة", uid)
            return "failed"
    except TelegramForbiddenError:
        return "blocked"
    except Exception:
        logger.exception("فشل إرسال البث للزبون %s", uid)
        return "failed"
