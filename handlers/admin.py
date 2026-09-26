import logging
import random
import string

from aiogram import Router, F
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

import sheets_service as db
import keyboards as kb
from states import AdminFlow

router = Router()
logger = logging.getLogger(__name__)

PENDING = "قيد المراجعة"
ACCEPTED = "مقبول ✅"
REJECTED = "مرفوض ❌"
FULFILLED = "منفَّذ 📦"


def _is_admin(user_id: int) -> bool:
    admin_id = db.get_settings().get("ADMIN_ID", "").strip()
    return str(user_id) == admin_id


@router.message(F.photo, F.caption.regexp(r"(?is)^/setwelcome\b"))
async def cmd_set_welcome_image(message: Message):
    """يحفظ صورة ونص الترحيب معًا: يرسلهما الأدمن كصورة، وفي خانة الوصف يكتب
    /setwelcome ثم نص الترحيب الجديد في السطر التالي (اختياري — إن تُرك فارغًا يبقى النص الحالي)."""
    if not _is_admin(message.from_user.id):
        return

    file_id = message.photo[-1].file_id
    db.set_setting("WELCOME_IMAGE", file_id)

    caption = message.caption or ""
    # نزيل كلمة الأمر من أول السطر ونأخذ الباقي كنص الترحيب الجديد
    new_text = caption.split("\n", 1)[1].strip() if "\n" in caption else ""

    if new_text:
        db.set_setting("WELCOME_TEXT", new_text)
        await message.answer("✅ تم حفظ صورة ونص الترحيب الجديدين بنجاح. جرّب /start الآن لرؤيتهما.")
    else:
        await message.answer("✅ تم حفظ صورة الترحيب بنجاح (بقي النص كما هو). جرّب /start الآن لرؤيتها.")


@router.message(Command("setwelcome"))
async def cmd_set_welcome_text_only(message: Message, command: CommandObject):
    """تغيير نص الترحيب فقط (بدون صورة): /setwelcome ثم النص الجديد."""
    if not _is_admin(message.from_user.id):
        return
    new_text = (command.args or "").strip()
    if not new_text:
        await message.answer(
            "✍️ أرسل النص بعد الأمر، مثال:\n/setwelcome أهلًا بك في متجرنا الجديد!\n\n"
            "ولتغيير الصورة أيضًا، أرسلها كصورة واكتب /setwelcome ثم النص الجديد في خانة الوصف."
        )
        return
    db.set_setting("WELCOME_TEXT", new_text)
    await message.answer("✅ تم تحديث نص الترحيب. جرّب /start الآن.")


async def _edit_admin_message(message, new_text: str, reply_markup=None):
    """تعدّل رسالة القرار عند الأدمن (نص أو صورة) بأمان."""
    try:
        if message.caption is not None:
            await message.edit_caption(caption=new_text, reply_markup=reply_markup)
        else:
            await message.edit_text(new_text, reply_markup=reply_markup)
    except TelegramBadRequest:
        pass


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

    if order.get("status") != PENDING:
        await callback.answer("تم معالجة هذا الطلب مسبقًا ✋", show_alert=True)
        return

    db.update_order_status(order_id, ACCEPTED)

    base_text = callback.message.caption if callback.message.caption is not None else callback.message.text

    try:
        await callback.bot.send_message(
            chat_id=int(order.get("user_id")),
            text=f"✅ تم قبول طلبك رقم #{order_id} وسيتم تنفيذه الآن. شكرًا لثقتك بنا!",
        )
    except Exception:
        logger.exception("فشل إرسال إشعار القبول للزبون user_id=%s order_id=%s", order.get("user_id"), order_id)
        await callback.message.answer(
            f"⚠️ تم قبول الطلب #{order_id} في الشيت، لكن تعذّر إرسال إشعار للزبون "
            "(قد يكون حظر البوت أو لم يبدأه من قبل)."
        )

    await _edit_admin_message(
        callback.message,
        (base_text or "") + "\n\n✅ تم القبول",
        reply_markup=kb.kb_admin_fulfill(order_id),
    )
    await callback.answer("تم القبول ✅")


@router.callback_query(F.data.startswith("admin:fulfill:"))
async def cb_admin_fulfill(callback: CallbackQuery):
    if not _is_admin(callback.from_user.id):
        await callback.answer("غير مصرح لك بهذا الإجراء", show_alert=True)
        return

    order_id = callback.data.split(":", 2)[2]
    order = db.get_order(order_id)
    if not order:
        await callback.answer("لم يتم العثور على الطلب", show_alert=True)
        return

    if order.get("status") != ACCEPTED:
        await callback.answer("لا يمكن تنفيذ هذا الطلب في حالته الحالية ✋", show_alert=True)
        return

    db.update_order_status(order_id, FULFILLED)

    base_text = callback.message.caption if callback.message.caption is not None else callback.message.text

    try:
        await callback.bot.send_message(
            chat_id=int(order.get("user_id")),
            text=f"📦 تم تنفيذ طلبك رقم #{order_id} بنجاح! نتمنى لك تجربة ممتعة، ونسعد بزيارتك مجددًا 🎉",
        )
    except Exception:
        logger.exception("فشل إرسال إشعار التنفيذ للزبون user_id=%s order_id=%s", order.get("user_id"), order_id)
        await callback.message.answer(
            f"⚠️ تم تنفيذ الطلب #{order_id} في الشيت، لكن تعذّر إرسال إشعار للزبون."
        )

    await _reward_referrer_if_first_purchase(callback.bot, order.get("user_id"))

    await _edit_admin_message(callback.message, (base_text or "") + "\n\n📦 تم التنفيذ", reply_markup=None)
    await callback.answer("تم ✅")


async def _reward_referrer_if_first_purchase(bot, user_id):
    """إذا كانت هذه أول عملية شراء منفَّذة لهذا الزبون، وكان قد جاء عبر رابط دعوة
    صديق ولم يُكافأ الداعي بعد، يُنشئ كود خصم عشوائي (10-20٪) ويرسله للداعي."""
    if db.count_fulfilled_orders(user_id) != 1:
        return  # ليست أول عملية شراء كاملة

    customer = db.get_customer(user_id)
    if not customer:
        return

    referred_by = str(customer.get("referred_by", "")).strip()
    already_rewarded = str(customer.get("ref_rewarded", "")).strip().upper() == "TRUE"
    if not referred_by or already_rewarded:
        return

    percent = random.randint(10, 20)
    code = "REF" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    db.create_discount_code(code, percent, max_uses=1)
    db.mark_referral_rewarded(user_id)

    try:
        await bot.send_message(
            chat_id=int(referred_by),
            text=(
                f"🎁 مبروك! أتمّ صديقك أول عملية شراء له، وربحت بطاقة خصم {percent}٪!\n\n"
                f"كود الخصم: `{code}`\n"
                "استخدمه في طلبك القادم قبل إدخال الدفع 🛍️"
            ),
        )
    except Exception:
        logger.exception("فشل إرسال بطاقة الخصم للمُحيل user_id=%s", referred_by)


@router.callback_query(F.data.startswith("admin:reject:"))
async def cb_admin_reject(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer("غير مصرح لك بهذا الإجراء", show_alert=True)
        return

    order_id = callback.data.split(":", 2)[2]
    order = db.get_order(order_id)
    if not order:
        await callback.answer("لم يتم العثور على الطلب", show_alert=True)
        return

    if order.get("status") != PENDING:
        await callback.answer("تم معالجة هذا الطلب مسبقًا ✋", show_alert=True)
        return

    # نزيل الأزرار فورًا كي لا يُعالَج الطلب مرتين أثناء انتظار سبب الرفض
    await _edit_admin_message(
        callback.message,
        callback.message.caption if callback.message.caption is not None else callback.message.text,
        reply_markup=None,
    )

    await state.set_state(AdminFlow.waiting_reject_reason)
    await state.update_data(
        reject_order_id=order_id,
        reject_chat_id=callback.message.chat.id,
        reject_msg_id=callback.message.message_id,
        reject_is_photo=callback.message.caption is not None,
        reject_base_text=callback.message.caption if callback.message.caption is not None else callback.message.text,
    )
    await callback.message.answer(f"✍️ أرسل سبب رفض الطلب #{order_id} (أو أرسل - لعدم ذكر سبب):")
    await callback.answer()


@router.message(AdminFlow.waiting_reject_reason)
async def msg_reject_reason(message: Message, state: FSMContext):
    data = await state.get_data()
    order_id = data.get("reject_order_id")
    order = db.get_order(order_id)
    reason = message.text.strip() if message.text else "-"
    await state.clear()

    if not order:
        await message.answer("لم يتم العثور على الطلب.")
        return

    db.update_order_status(order_id, REJECTED)

    reason_text = "" if reason == "-" else f"\nالسبب: {reason}"
    notified = True
    try:
        await message.bot.send_message(
            chat_id=int(order.get("user_id")),
            text=f"❌ نعتذر، تم رفض طلبك رقم #{order_id}.{reason_text}\nللاستفسار تواصل مع الدعم.",
        )
    except Exception:
        logger.exception("فشل إرسال إشعار الرفض للزبون user_id=%s order_id=%s", order.get("user_id"), order_id)
        notified = False

    # تحديث رسالة القرار الأصلية عند الأدمن بإضافة سبب الرفض
    chat_id = data.get("reject_chat_id")
    msg_id = data.get("reject_msg_id")
    base_text = data.get("reject_base_text") or ""
    is_photo = data.get("reject_is_photo")
    if chat_id and msg_id:
        new_text = base_text + f"\n\n❌ تم الرفض{reason_text}"
        try:
            if is_photo:
                await message.bot.edit_message_caption(chat_id=chat_id, message_id=msg_id, caption=new_text)
            else:
                await message.bot.edit_message_text(chat_id=chat_id, message_id=msg_id, text=new_text)
        except TelegramBadRequest:
            pass

    if notified:
        await message.answer(f"تم رفض الطلب #{order_id} وإبلاغ العميل.")
    else:
        await message.answer(
            f"⚠️ تم رفض الطلب #{order_id} في الشيت، لكن تعذّر إرسال إشعار للزبون "
            "(قد يكون حظر البوت أو لم يبدأه من قبل)."
        )
