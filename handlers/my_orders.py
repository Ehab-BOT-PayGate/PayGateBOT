from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

import sheets_service as db
import keyboards as kb
from utils import show_screen

router = Router()


@router.callback_query(F.data == "myorders")
async def cb_my_orders(callback: CallbackQuery, state: FSMContext):
    orders = db.get_orders_by_user(callback.from_user.id, limit=10)

    if not orders:
        text = "لا توجد لديك طلبات سابقة بعد."
    else:
        lines = ["📦 آخر طلباتك:\n"]
        for o in orders:
            lines.append(
                f"#{o.get('order_id')} — {o.get('service_name')} / {o.get('option_label')}\n"
                f"الحالة: {o.get('status')}\n"
            )
        text = "\n".join(lines)

    await show_screen(
        bot=callback.bot, chat_id=callback.message.chat.id, state=state,
        text=text, reply_markup=kb.kb_back_main(),
    )
    await callback.answer()
