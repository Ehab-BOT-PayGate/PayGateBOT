from aiogram import Router, F
from aiogram.filters import CommandStart, CommandObject
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

import sheets_service as db
import keyboards as kb
from utils import show_screen, is_subscribed

router = Router()

WELCOME_TEXT = (
    "\u0623\u0647\u0644\u0627 \u0628\u0643 {name} \u0641\u064a \u0645\u062a\u062c\u0631\u0646\u0627.\n"
    "\u0627\u062e\u062a\u0631 \u0645\u0627 \u064a\u0646\u0627\u0633\u0628\u0643 \u0645\u0646 \u0627\u0644\u0642\u0627\u0626\u0645\u0629 \u0641\u064a \u0627\u0644\u0623\u0633\u0641\u0644\n"
    "\u0625\u0646 \u0644\u0645 \u062a\u062c\u062f \u0637\u0644\u0628\u0643 \u0647\u0646\u0627 \u0644\u0627 \u062a\u062a\u0631\u062f\u062f \u0641\u064a \u0627\u0644\u062a\u0648\u0627\u0635\u0644 \u0645\u0639 \u0627\u0644\u062f\u0639\u0645."
)


def _extract_referrer_id(args, user_id):
    if not args or not args.startswith("ref"):
        return None
    candidate = args[3:].strip()
    if not candidate.isdigit() or candidate == str(user_id):
        return None
    return candidate


async def _notify_referrer_of_join(bot, referrer_id):
    try:
        await bot.send_message(
            chat_id=int(referrer_id),
            text=(
                "\u0634\u062e\u0635 \u0627\u0634\u062a\u0631\u0643 \u0628\u0627\u0644\u0628\u0648\u062a \u0645\u0646 \u062e\u0644\u0627\u0644\u0643! \u0631\u0628\u062d\u062a \u0646\u0642\u0637\u0629 \u0648\u0644\u0627\u0621.\n"
                "\u0648\u0633\u062a\u0631\u0628\u062d \u0643\u0648\u0628\u0648\u0646 \u062e\u0635\u0645 \u0628\u064a\u0646 10% \u064820% \u0639\u0646\u062f\u0645\u0627 \u064a\u062a\u0645 \u0635\u062f\u064a\u0642\u0643 \u0623\u0648\u0644 \u0639\u0645\u0644\u064a\u0629 \u0634\u0631\u0627\u0621 \u0645\u062f\u0641\u0648\u0639\u0629."
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
        text="\u0627\u062e\u062a\u0631 \u0627\u0644\u0642\u0633\u0645 \u0627\u0644\u0630\u064a \u062a\u0631\u064a\u062f\u0647:",
        reply_markup=kb.kb_main_menu(menus, page=page),
    )


async def build_welcome_text(user_id: int, name: str, referrer_id=None):
    text = WELCOME_TEXT.format(name=name)
    number, is_new = db.get_customer_number(user_id, referred_by=referrer_id or "")
    notify_referrer = bool(is_new and referrer_id)
    if is_new:
        text += "\n\n\u0623\u0646\u062a \u0627\u0644\u0632\u0628\u0648\u0646 \u0631\u0642\u0645 #" + str(number) + " \u0627\u0644\u0630\u064a \u064a\u0646\u0636\u0645 \u0625\u0644\u0649 \u0645\u062a\u062c\u0631\u0646\u0627 - \u0627\u0646\u0636\u0645 \u0625\u0644\u064a\u0646\u0627 \u0622\u0644\u0627\u0641 \u0627\u0644\u0639\u0645\u0644\u0627\u0621 \u0627\u0644\u0631\u0627\u0636\u064a\u0646 \u0639\u0646 \u062e\u062f\u0645\u062a\u0646\u0627 \u0648\u062b\u0642\u062a\u0647\u0645 \u0628\u0646\u0627!"
    return text, notify_referrer


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    await state.clear()

    referrer_id = _extract_referrer_id(command.args, message.from_user.id)

    if not await is_subscribed(message.bot, message.from_user.id):
        settings = db.get_settings()
        link = settings.get("CHANNEL_LINK", "")
        if referrer_id:
            await state.update_data(pending_referrer=referrer_id)
        await message.answer(
            "\u0644\u0644\u0627\u0633\u062a\u0641\u0627\u062f\u0629 \u0645\u0646 \u062e\u062f\u0645\u0627\u062a\u0646\u0627\u060c \u064a\u062c\u0628 \u0639\u0644\u064a\u0643 \u0627\u0644\u0627\u0634\u062a\u0631\u0627\u0643 \u0641\u064a \u0642\u0646\u0627\u062a\u0646\u0627 \u0623\u0648\u0644\u0627.",
            reply_markup=kb.kb_subscribe(link),
        )
        return

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
        await callback.answer("\u062a\u0645 \u0627\u0644\u062a\u062d\u0642\u0642")

        text, notify_referrer = await build_welcome_text(callback.from_user.id, callback.from_user.full_name, referrer_id)
        await callback.message.answer(text)
        await send_main_menu(callback.bot, callback.message.chat.id, state)

        if notify_referrer:
            await _notify_referrer_of_join(callback.bot, referrer_id)
    else:
        await callback.answer("\u0644\u0645 \u064a\u062a\u0645 \u0627\u0644\u0639\u062b\u0648\u0631 \u0639\u0644\u0649 \u0627\u0634\u062a\u0631\u0627\u0643\u0643 \u0628\u0639\u062f", show_alert=True)


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
    await callback.message.answer("\u0644\u0644\u062a\u0648\u0627\u0635\u0644 \u0645\u0639 \u0627\u0644\u062f\u0639\u0645:\n" + link)


@router.callback_query(F.data == "referral")
async def cb_referral(callback: CallbackQuery):
    bot_user = await callback.bot.get_me()
    link = "https://t.me/" + bot_user.username + "?start=ref" + str(callback.from_user.id)
    await callback.answer()
    await callback.message.answer(
        "\u0634\u0627\u0631\u0643 \u0647\u0630\u0627 \u0627\u0644\u0631\u0627\u0628\u0637 \u0645\u0639 \u0623\u0635\u062f\u0642\u0627\u0626\u0643:\n\n" + link +
        "\n\n\u0643\u0644 \u0635\u062f\u064a\u0642 \u064a\u0646\u0636\u0645 \u0645\u0646 \u062e\u0644\u0627\u0644\u0647 \u0648\u064a\u062a\u0645 \u0623\u0648\u0644 \u0639\u0645\u0644\u064a\u0629 \u0634\u0631\u0627\u0621 \u0645\u062f\u0641\u0648\u0639\u0629\u060c \u0628\u062a\u0631\u0628\u062d \u0643\u0648\u0628\u0648\u0646 \u062e\u0635\u0645 \u0628\u064a\u0646 10% \u064820%!"
    )


@router.callback_query(F.data.startswith("mainpage:"))
async def cb_main_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split(":", 1)[1])
    await send_main_menu(callback.bot, callback.message.chat.id, state, page=page)
    await callback.answer()


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()
