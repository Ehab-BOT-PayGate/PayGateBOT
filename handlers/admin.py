from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

import sheets_service as db
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
