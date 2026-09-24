import asyncio

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

import sheets_service as db
import keyboards as kb
from states import AdminFlow

router = Router()


def _is_admin(user_id: int) -> bool:
    admin_id = db.get_settings().get("ADMIN_ID", "").strip()
    return str(user_id) == admin_id


@router.callback_query(F.data.startswith("admin:accept:"))
async def cb_admin_accept(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("غير مصرح لك بهذا الإجراء", show_alert=True)
        return

    order_id = callback.data.split(":", 2)[2]
    order = db.get_order(order_id)
    if not order:
        await callback.answer("لم يتم العثور على الطلب", show_alert=True)
        return

    db.update_order_status(order_id, "مقبول ✅")

    try:
        await callback.bot.send_message(
            chat_id=int(order.get("user_id")),
            text=f"✅ تم قبول طلبك رقم #{order_id} وسيتم تنفيذه الآن. شكرًا لثقتك بنا!",
        )
    except Exception:
        pass

    if callback.message.caption is not None:
        await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ تم القبول")
    else:
        await callback.message.edit_text(callback.message.text + "\n\n✅ تم القبول")
    await callback.answer("تم القبول ✅")


@router.callback_query(F.data.startswith("admin:reject:"))
async def cb_admin_reject(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("غير مصرح لك بهذا الإجراء", show_alert=True)
        return

    order_id = callback.data.split(":", 2)[2]
    await state.set_state(AdminFlow.waiting_reject_reason)
    await state.update_data(reject_order_id=order_id)
    await callback.message.answer(f"✍️ أرسل سبب رفض الطلب #{order_id} (أو أرسل - لعدم ذكر سبب):")
    await callback.answer()


@router.message(AdminFlow.waiting_reject_reason)
async def msg_reject_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("reject_order_id")
    order = db.get_order(order_id)
    reason = message.text.strip()
    await state.clear()

    if not order:
        await message.answer("لم يتم العثور على الطلب.")
        return

    db.update_order_status(order_id, "مرفوض ❌")

    reason_text = "" if reason == "-" else f"\nالسبب: {reason}"
    try:
        await message.bot.send_message(
            chat_id=int(order.get("user_id")),
            text=f"❌ نعتذر، تم رفض طلبك رقم #{order_id}.{reason_text}\nللاستفسار تواصل مع الدعم.",
        )
    except Exception:
        pass

    await message.answer(f"تم رفض الطلب #{order_id} وإبلاغ العميل.")


# ---------------- رسائل جماعية (Broadcast) ----------------
@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        return  # تجاهل تام لغير المدير، حتى لا يعرف أحد أن هذا الأمر موجود أصلًا

    await state.set_state(AdminFlow.waiting_broadcast_message)
    await message.answer(
        "📢 أرسل الآن الرسالة التي تريد إرسالها لكل الزبائن (نص أو صورة مع تعليق).\n"
        "أو أرسل /cancel لإلغاء العملية."
    )


@router.message(AdminFlow.waiting_broadcast_message, Command("cancel"))
async def cmd_broadcast_cancel_early(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("تم الإلغاء.")


@router.message(AdminFlow.waiting_broadcast_message)
async def msg_broadcast_content(message: Message, state: FSMContext):
    await state.update_data(broadcast_chat_id=message.chat.id, broadcast_message_id=message.message_id)
    await state.set_state(AdminFlow.waiting_broadcast_confirm)

    customer_count = len(db.get_all_customer_ids())
    await message.answer(
        f"👆 هذه معاينة الرسالة كما ستصل للزبائن.\nسيتم إرسالها لعدد {customer_count} زبون.\nهل تريد المتابعة؟",
        reply_markup=kb.kb_broadcast_confirm(),
    )


@router.callback_query(AdminFlow.waiting_broadcast_confirm, F.data == "broadcast:cancel")
async def cb_broadcast_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("تم إلغاء الإرسال الجماعي.")
    await callback.answer()


@router.callback_query(AdminFlow.waiting_broadcast_confirm, F.data == "broadcast:confirm")
async def cb_broadcast_confirm(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    src_chat_id = data.get("broadcast_chat_id")
    src_message_id = data.get("broadcast_message_id")
    await state.clear()

    await callback.message.edit_text("⏳ جاري الإرسال... سأخبرك بالنتيجة عند الانتهاء.")
    await callback.answer()

    customer_ids = db.get_all_customer_ids()
    sent, failed = 0, 0
    for uid in customer_ids:
        try:
            await callback.bot.copy_message(chat_id=uid, from_chat_id=src_chat_id, message_id=src_message_id)
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)

    await callback.bot.send_message(
        chat_id=src_chat_id,
        text=f"✅ انتهى الإرسال الجماعي.\nوصلت: {sent}\nفشلت: {failed} (غالبًا بسبب حظر الزبون للبوت)",
    )
