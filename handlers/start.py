import logging

from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import sheets_service as db
import keyboards as kb
from utils import show_screen, is_subscribed

router = Router()
logger = logging.getLogger(__name__)

WELCOME_TEXT = (
    "👋 أهلًا بك في متجرنا!\n\n"
    "نقدّم لك خدمتين:\n"
    "🎮 شحن ألعاب\n"
    "💳 بطاقات شحن عالمية\n\n"
    "اختر ما يناسبك من القائمة بالأسفل 👇"
)


async def send_main_menu(bot, chat_id, state: FSMContext, page: int = 0):
    menus = db.get_menus()
    await state.update_data(main_page=page)
    await show_screen(
        bot=bot,
        chat_id=chat_id,
        state=state,
        text="اختر القسم الذي تريده:",
        reply_markup=kb.kb_main_menu(menus, page=page),
    )


async def build_welcome_text(number: int, is_new: bool) -> str:
    settings = db.get_settings()
    base_text = settings.get("WELCOME_TEXT", "").strip() or WELCOME_TEXT
    if is_new:
        return (
            base_text
            + f"\n\n🎉 أنت الزبون رقم #{number} الذي ينضم إلى متجرنا — انضم إلينا آلاف العملاء الراضين عن خدمتنا وثقتهم بنا!"
        )
    return base_text


async def send_welcome(bot, chat_id: int, number: int, is_new: bool):
    """رسالة الترحيب: ثابتة مع صورة (إن كانت محفوظة)، وتُرسل دائمًا كرسالة جديدة منفصلة.
    النص والصورة قابلان للتعديل عبر أمر /setwelcome من الأدمن."""
    text = await build_welcome_text(number, is_new)
    settings = db.get_settings()
    image = settings.get("WELCOME_IMAGE", "").strip()

    if image:
        try:
            await bot.send_photo(chat_id=chat_id, photo=image, caption=text)
            return
        except Exception:
            logger.exception("فشل إرسال صورة الترحيب (WELCOME_IMAGE قد يكون غير صالح)")

    await bot.send_message(chat_id=chat_id, text=text)


def _extract_referrer(payload: str, own_id: int) -> str:
    """يستخرج معرف المُحيل من رابط الدعوة (?start=ref123456)."""
    payload = (payload or "").strip()
    if payload.startswith("ref"):
        candidate = payload[3:]
        if candidate.isdigit() and candidate != str(own_id):
            return candidate
    return ""


async def handle_referral_and_welcome(bot, chat_id, user_id: int, referred_by: str):
    number, is_new = db.get_customer_number(user_id, referred_by=referred_by)

    if is_new and referred_by:
        try:
            await bot.send_message(
                chat_id=int(referred_by),
                text=(
                    "🎉 لقد اشترك صديقك في البوت وحصلت على نقطة ولاء واحدة!\n"
                    "سيتم منحك تلقائيًا بطاقة خصم بين 10-20٪ عشوائيًا، تعتمد على الحظ، "
                    "عندما يتم صديقك أول عملية شراء كاملة.\n"
                    "ادعُ المزيد من الأصدقاء لتربح بطاقات خصم أكثر! 🎁"
                ),
            )
        except Exception:
            logger.exception("فشل إرسال إشعار نقطة الولاء للمُحيل user_id=%s", referred_by)

    await send_welcome(bot, chat_id, number, is_new)


@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    referred_by = _extract_referrer(command.args, message.from_user.id)

    if not await is_subscribed(message.bot, message.from_user.id):
        await state.update_data(pending_referred_by=referred_by)
        settings = db.get_settings()
        link = settings.get("CHANNEL_LINK", "")
        await message.answer(
            "⚠️ للاستفادة من خدماتنا، يجب عليك الاشتراك في قناتنا أولًا.",
            reply_markup=kb.kb_subscribe(link),
        )
        return

    await handle_referral_and_welcome(message.bot, message.chat.id, message.from_user.id, referred_by)
    await send_main_menu(message.bot, message.chat.id, state)


@router.callback_query(F.data == "checksub")
async def cb_checksub(callback: CallbackQuery, state: FSMContext):
    if await is_subscribed(callback.bot, callback.from_user.id):
        data = await state.get_data()
        referred_by = data.get("pending_referred_by", "")
        await callback.message.delete()
        await callback.answer("تم التحقق ✅")
        await handle_referral_and_welcome(callback.bot, callback.message.chat.id, callback.from_user.id, referred_by)
        await send_main_menu(callback.bot, callback.message.chat.id, state)
    else:
        await callback.answer("لم يتم العثور على اشتراكك بعد ❌", show_alert=True)


@router.callback_query(F.data == "back:main")
async def cb_back_main(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await state.update_data(screen_msg_id=data.get("screen_msg_id"), screen_has_photo=data.get("screen_has_photo"))
    await send_main_menu(callback.bot, callback.message.chat.id, state)
    await callback.answer()


@router.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery):
    settings = db.get_settings()
    link = settings.get("SUPPORT_LINK", "")
    await callback.answer()
    await callback.message.answer(f"🆘 للتواصل مع الدعم:\n{link}")


@router.callback_query(F.data == "referral")
async def cb_referral(callback: CallbackQuery):
    me = await callback.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref{callback.from_user.id}"
    await callback.answer()
    await callback.message.answer(
        "🎁 ادعُ أصدقاءك إلى المتجر!\n\n"
        "شارك هذا الرابط مع أصدقائك. عند أول اشتراك لصديقك بالبوت تحصل على نقطة ولاء، "
        "وعند إتمامه أول عملية شراء كاملة تحصل تلقائيًا على بطاقة خصم عشوائية بين 10-20٪!\n\n"
        f"{link}"
    )


@router.callback_query(F.data.startswith("mainpage:"))
async def cb_main_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split(":", 1)[1])
    await send_main_menu(callback.bot, callback.message.chat.id, state, page=page)
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    """زر رقم الصفحة في أعلى شريط التنقل — لا يفعل شيئًا سوى إسكات الرسالة."""
    await callback.answer()
