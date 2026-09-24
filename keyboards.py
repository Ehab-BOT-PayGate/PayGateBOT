from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

PAGE_SIZE = 6
MENU_COLORS = ["🟢", "🔵", "🟣", "🟠", "🔴", "🟡", "🟤", "⚪️"]


def kb_subscribe(channel_link: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📢 الانضمام إلى القناة", url=channel_link)
    b.button(text="✅ لقد اشتركت", callback_data="checksub")
    b.adjust(1)
    return b.as_markup()


def kb_main_menu(menus: list[str]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for i, m in enumerate(menus):
        color = MENU_COLORS[i % len(MENU_COLORS)]
        b.button(text=f"{color} {m}", callback_data=f"menu:{m}")
    b.button(text="📦 طلباتي", callback_data="myorders")
    b.adjust(1)
    return b.as_markup()


def _paginate(rows: list[list[InlineKeyboardButton]], items, page: int, item_button, page_callback_prefix: str, back_callback: str) -> InlineKeyboardMarkup:
    start = page * PAGE_SIZE
    page_items = items[start:start + PAGE_SIZE]
    for item in page_items:
        rows.append([item_button(item)])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ السابق", callback_data=f"{page_callback_prefix}:{page-1}"))
    if start + PAGE_SIZE < len(items):
        nav_row.append(InlineKeyboardButton(text="التالي ➡️", callback_data=f"{page_callback_prefix}:{page+1}"))
    if nav_row:
        rows.append(nav_row)

    rows.append([InlineKeyboardButton(text="⬅️ رجوع", callback_data=back_callback)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_services(services: list[dict], page: int = 0) -> InlineKeyboardMarkup:
    return _paginate(
        [], services, page,
        item_button=lambda s: InlineKeyboardButton(text=s["name_ar"], callback_data=f"service:{s['id']}"),
        page_callback_prefix="svcpage",
        back_callback="back:main",
    )


def kb_options(options: list[dict], page: int = 0) -> InlineKeyboardMarkup:
    return _paginate(
        [], options, page,
        item_button=lambda o: InlineKeyboardButton(text=f"{o['label']} - {o['price']}", callback_data=f"option:{o['id']}"),
        page_callback_prefix="optpage",
        back_callback="backservices",
    )


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


def kb_broadcast_confirm() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ إرسال للجميع", callback_data="broadcast:confirm")
    b.button(text="❌ إلغاء", callback_data="broadcast:cancel")
    b.adjust(1)
    return b.as_markup()
