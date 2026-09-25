from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import sheets_service as db
import keyboards as kb
from utils import show_screen, is_subscribed

router = Router()

WELCOME_TEXT = (
    "👋 أهلًا بك في متجرنا!\n\n"
    "اختر ما يناسبك من القائمة بالأسفل 👇
    
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


async def build_welcome_text(user_id: int) -> str:
    number, is_new = db.get_customer_number(user_id)
    if is_new:
        return (
            WELCOME_TEXT
            + f"\n\n🎉 أنت الزبون رقم #{number} الذي ينضم إلى متجرنا — انضم إلينا آلاف العملاء الراضين عن خدمتنا وثقتهم بنا!"
        )
    return WELCOME_TEXT


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    if not await is_subscribed(message.bot, message.from_user.id):
        settings = db.get_settings()
        link = settings.get("CHANNEL_LINK", "")
        await message.answer(
            "⚠️ للاستفادة من خدماتنا، يجب عليك الاشتراك في قناتنا أولًا.",
            reply_markup=kb.kb_subscribe(link),
        )
        return

    # رسالة الترحيب ثابتة: تُرسل دائمًا كرسالة جديدة منفصلة ولا تدخل نظام تحديث الشاشات
    await message.answer(await build_welcome_text(message.from_user.id))
    await send_main_menu(message.bot, message.chat.id, state)


@router.callback_query(F.data == "checksub")
async def cb_checksub(callback: CallbackQuery, state: FSMContext):
    if await is_subscribed(callback.bot, callback.from_user.id):
        await callback.message.delete()
        await callback.answer("تم التحقق ✅")
        await callback.message.answer(await build_welcome_text(callback.from_user.id))
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


@router.callback_query(F.data.startswith("mainpage:"))
async def cb_main_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split(":", 1)[1])
    await send_main_menu(callback.bot, callback.message.chat.id, state, page=page)
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    """زر رقم الصفحة في أعلى شريط التنقل — لا يفعل شيئًا سوى إسكات الرسالة."""
    await callback.answer()
