from aiogram.fsm.state import State, StatesGroup


class OrderFlow(StatesGroup):
    choosing_menu = State()
    choosing_service = State()
    choosing_option = State()
    asking_discount_choice = State()
    entering_discount_code = State()
    choosing_payment = State()
    waiting_proof = State()
    waiting_extra_info = State()


class AdminFlow(StatesGroup):
    waiting_reject_reason = State()
    waiting_broadcast_content = State()
    waiting_broadcast_button = State()
