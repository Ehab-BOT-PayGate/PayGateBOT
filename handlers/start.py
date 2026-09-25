# start.py
from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import sheets_service as db
import keyboards as kb
from utils import show_screen, is_subscribed

router = Router()

WELCOME_TEXT = (
    "أهلا بك {name} في متجرنا.\n"
    "اختر ما يناسبك من القائمة في الأسفل\n"
    "إن لم تجد طلبك هنا لا تتردد في التواصل مع الدعم."
)


def _extract_referrer_id(args: str | None, user_id: int) -> str | None:
    """يستخرج معرف الزبون الداعي من صيغة /start ref<user_id>.
    يرجع None إن لم يوجد كود، أو كان غير صالح، أو كان الزبون يحاول إحالة نفسه."""
    if not args or not args.startswith("ref"):
        return None
    candidate = args[3:].strip()
    if not candidate.isdigit() or candidate == str(user_id):
        return None
    return candidate


async def _notify_referrer_of_join(bot, referrer_id: str):
    """إشعار فوري للزبون الداعي عند انضمام صديقه عبر رابط الإحالة."""
    try:
        await bot.send_message(
            chat_id=int(referrer_id),
            text=(
                "🎉 شخص اشترك بالبوت من خلالك! ربحت نقطة ولاء 🏅\n"
                "وستربح كوبون خصم (بين 10% و20%) عندما يتم صديقك أول عملية شراء مدفوعة."
            ),
        )
    except Exception:
        pass


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


async def build_welcome_text(user_id: int, name: str, referrer_id: str | None = None) -> tuple[str, bool]:
    """يرجع (نص الترحيب, هل يجب إشعار الزبون الداعي الآن بانضمام صديقه)."""
    text = WELCOME_TEXT.format(name=name)
    number, is_new = db.get_customer_number(user_id, referred_by=referrer_id or "")
    notify_referrer = bool(is_new and referrer_id)
    if is_new:
        text += f"\n\n🎉 أنت الزبون رقم #{number} الذي ينضم إلى متجرنا — انضم إلينا آلاف العملاء الراضين عن خدمتنا وثقتهم بنا!"
    return text, notify_referrer


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    await state.clear()

    referrer_id = _extract_referrer_id(command.args, message.from_user.id)

    if not await is_subscribed(message.bot, message.from_user.id):
        settings = db.get_settings()
        link = settings.get("CHANNEL_LINK", "")
        # نحفظ كود الإحالة مؤقتًا بالحالة كي لا يضيع إلى حين يشترك ويضغط "لقد اشتركت"
        if referrer_id:
            await state.update_data(pending_referrer=referrer_id)
        await message.answer(
            "⚠️ للاستفادة من خدماتنا، يجب عليك الاشتراك في قناتنا أولًا.",
            reply_markup=kb.kb_subscribe(link),
        )
        return

    # رسالة الترحيب ثابتة: تُرسل دائمًا كرسالة جديدة منفصلة ولا تدخل نظام تحديث الشاشات
    text, notify_referrer = await build_welcome_text(message.from_user.id, message.from_user.full_name, referrer_id)
    await message.answer(text)
    await send_main_menu(message.bot, message.chat.id, state)

    if notify_referrer:
        await _notify_referrer_of_join(message.bot, referrer_id)


@router.callback_query(F.data == "checksub")
async def cb_checksub(callback: CallbackQuery, state: FSMContext):
    if await is_subscribed(callback.bot, callback.from_user.id):
        data = await state.get_data()
        referrer_id = data.get("pending_referrer")

        await callback.message.delete()
        await callback.answer("تم التحقق ✅")

        text, notify_referrer = await build_welcome_text(callback.from_user.id, callback.from_user.full_name, referrer_id)
        await callback.message.answer(text)
        await send_main_menu(callback.bot, callback.message.chat.id, state)

        if notify_referrer:
            await _notify_referrer_of_join(callback.bot, referrer_id)
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
    bot_user = await callback.bot.get_me()
    link = f"https://t.me/{bot_user.username}?start=ref{callback.from_user.id}"
    await callback.answer()
    await callback.message.answer(
        "🎁 شارك هذا الرابط مع أصدقائك:\n\n"
        f"{link}\n\n"
        "كل صديق ينضم من خلاله ويتم أول عملية شراء مدفوعة، بتربح كوبون خصم بين 10% و20%!"
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
