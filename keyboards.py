from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def kb_subscribe(channel_link: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📢 الانضمام إلى القناة", url=channel_link)
    b.button(text="✅ لقد اشتركت", callback_data="checksub")
    b.adjust(1)
    return b.as_markup()


def kb_main_menu(menus: list[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for m in menus:
        b.button(text=m, callback_data=f"menu:{m}")
    b.button(text="📦 طلباتي", callback_data="myorders")
    b.adjust(1)
    return b.as_markup()


def kb_services(services: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for s in services:
        b.button(text=s["name_ar"], callback_data=f"service:{s['id']}")
    b.button(text="⬅️ رجوع", callback_data="back:main")
    b.adjust(1)
    return b.as_markup()


def kb_options(options: list[dict], service_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for o in options:
        b.button(text=f"{o['label']} - {o['price']}", callback_data=f"option:{o['id']}")
    b.button(text="⬅️ رجوع", callback_data=f"backservices")
    b.adjust(1)
    return b.as_markup()


def kb_discount_choice() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏷️ لدي كود خصم", callback_data="discount:yes")
    b.button(text="متابعة بدون كود", callback_data="discount:no")
    b.adjust(1)
    return b.as_markup()


def kb_payment_methods(methods: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for m in methods:
        b.button(text=m["name_ar"], callback_data=f"pay:{m['id']}")
    b.button(text="⬅️ رجوع", callback_data="backoptions")
    b.adjust(1)
    return b.as_markup()


def kb_admin_decision(order_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ قبول", callback_data=f"admin:accept:{order_id}")
    b.button(text="❌ رفض", callback_data=f"admin:reject:{order_id}")
    b.adjust(2)
    return b.as_markup()


def kb_back_main() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ القائمة الرئيسية", callback_data="back:main")
    return b.as_markup()
