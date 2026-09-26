from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

import sheets_service as db
import keyboards as kb
from states import OrderFlow
from utils import show_screen, format_price

router = Router()


@router.callback_query(F.data.startswith("pay:"))
async def cb_choose_payment(callback: CallbackQuery, state: FSMContext):
    pm_id = callback.data.split(":", 1)[1]
    pm = db.get_payment_method_by_id(pm_id)
    if not pm:
        await callback.answer("طريقة الدفع غير متاحة حاليًا", show_alert=True)
        return

    await state.update_data(payment_method=pm.get("name_ar"), payment_wallet=pm.get("wallet_number"))
    await state.set_state(OrderFlow.waiting_proof)

    text = (
        f"💰 قم بتحويل المبلغ عبر {pm.get('name_ar')} إلى الرقم التالي:\n\n"
        f"`{pm.get('wallet_number')}`\n"
        "(اضغط على الرقم لنسخه)\n\n"
        "بعد التحويل، أرسل رقم عملية التحويل أو صورة عن إثبات الدفع 👇\n"
        "⚠️ الرجاء إرسال رقم العملية فقط أو صورة الإثبات، دون أي رسالة إضافية."
    )
    await show_screen(bot=callback.bot, chat_id=callback.message.chat.id, state=state, text=text)
    await callback.answer()


@router.message(OrderFlow.waiting_proof)
async def msg_proof(message: Message, state: FSMContext):
    if message.photo:
        proof = message.photo[-1].file_id
        proof_is_photo = True
    elif message.text:
        proof = message.text.strip()
        proof_is_photo = False
    else:
        await message.answer("الرجاء إرسال رقم العملية كنص أو صورة عن إثبات الدفع.")
        return

    await state.update_data(proof=proof, proof_is_photo=proof_is_photo)
    try:
        await message.delete()
    except Exception:
        pass

    data = await state.get_data()
    s_type = data.get("service_type")
    extra_prompt = (data.get("service_extra_prompt") or "").strip()

    if s_type == "GAME":
        await state.set_state(OrderFlow.waiting_extra_info)
        await show_screen(
            bot=message.bot, chat_id=message.chat.id, state=state,
            text="🆔 أرسل الآن معرف حسابك (ID) في اللعبة:",
        )
    elif s_type == "CARD":
        await state.set_state(OrderFlow.waiting_extra_info)
        await show_screen(
            bot=message.bot, chat_id=message.chat.id, state=state,
            text="✍️ أرسل اسم حامل البطاقة المطلوب (بالإنكليزية):",
        )
    elif s_type == "SERVICE" and extra_prompt:
        # خدمة تحتاج معلومة إضافية مخصصة (من عمود extra_prompt بالشيت)
        await state.set_state(OrderFlow.waiting_extra_info)
        await show_screen(bot=message.bot, chat_id=message.chat.id, state=state, text=extra_prompt)
    else:
        # اشتراكات/خدمات تفعيلها يدوي بالكامل: لا حاجة لأي معلومة إضافية،
        # ننهي الطلب مباشرة ونطلب من الزبون التواصل مع الدعم لإتمام التفعيل.
        await finalize_order(message.bot, message.chat.id, state, message.from_user, extra_info="")


@router.message(OrderFlow.waiting_extra_info)
async def msg_extra_info(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("الرجاء إرسال المعلومات المطلوبة كنص.")
        return

    extra_info = message.text.strip()
    try:
        await message.delete()
    except Exception:
        pass

    await finalize_order(message.bot, message.chat.id, state, message.from_user, extra_info)


async def finalize_order(bot, chat_id, state: FSMContext, user, extra_info: str):
    data = await state.get_data()
    s_type = data.get("service_type")

    order_id = db.create_order(
        user_id=user.id,
        username=f"@{user.username}" if user.username else "",
        full_name=user.full_name,
        service_name=data.get("service_name"),
        option_label=data.get("option_label"),
        base_price=data.get("base_price"),
        discount_code=data.get("discount_code"),
        final_price=data.get("final_price"),
        payment_method=data.get("payment_method"),
        proof=data.get("proof"),
        extra_info=extra_info,
    )

    if s_type == "SERVICE" and not extra_info:
        settings = db.get_settings()
        support_link = settings.get("SUPPORT_LINK", "")
        confirm_text = (
            f"✅ تم استلام طلبك بنجاح!\nرقم الطلب: {order_id}\n\n"
            "🆘 التفعيل يتم يدويًا بالكامل — الرجاء التواصل مع الدعم الآن لإتمام تفعيل حسابك:\n"
            f"{support_link}"
        )
    else:
        confirm_text = f"✅ تم تسجيل طلبك بنجاح!\nرقم الطلب: {order_id}\nسيتم مراجعته والرد عليك قريبًا."

    await show_screen(
        bot=bot, chat_id=chat_id, state=state,
        text=confirm_text,
        reply_markup=kb.kb_back_main(),
    )
    await state.set_state(None)

    await notify_admin(bot, order_id, data, extra_info, user.id)


async def notify_admin(bot, order_id, data, extra_info, user_chat_id):
    settings = db.get_settings()
    admin_id = settings.get("ADMIN_ID", "").strip()
    if not admin_id:
        return

    proof = data.get("proof", "")
    caption = (
        f"🆕 طلب جديد #{order_id}\n\n"
        f"الخدمة: {data.get('service_name')}\n"
        f"الخيار: {data.get('option_label')}\n"
        f"السعر الأساسي: {format_price(data.get('base_price'))}$\n"
        f"كود الخصم: {data.get('discount_code') or '-'}\n"
        f"السعر النهائي: {format_price(data.get('final_price'))}$\n"
        f"طريقة الدفع: {data.get('payment_method')}\n"
        f"المعلومات الإضافية: {extra_info or '-'}\n"
        f"العميل: {user_chat_id}"
    )

    # تنبيه إن كان رقم العملية (وليس صورة) مستخدمًا في طلب سابق — احتمال احتيال أو خطأ
    if not data.get("proof_is_photo") and proof:
        dup_orders = [o for o in db.find_orders_by_proof(proof) if str(o.get("order_id")) != str(order_id)]
        if dup_orders:
            dup_ids = "، ".join(f"#{o.get('order_id')}" for o in dup_orders)
            caption += f"\n\n⚠️ تنبيه: رقم العملية هذا استُخدم سابقًا في الطلب/الطلبات: {dup_ids}"

    markup = kb.kb_admin_decision(order_id)
    if data.get("proof_is_photo"):
        await bot.send_photo(chat_id=admin_id, photo=proof, caption=caption, reply_markup=markup)
    else:
        caption += f"\nإثبات الدفع (رقم العملية): {proof}"
        await bot.send_message(chat_id=admin_id, text=caption, reply_markup=markup)
