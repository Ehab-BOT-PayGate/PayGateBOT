# keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

PAGE_SIZE = 6  # 6 عناصر لكل صفحة، عنصران في كل صف (3 صفوف)


def _slice_page(items: list, page: int) -> tuple[list, int, int]:
    """يرجع (عناصر الصفحة, رقم الصفحة بعد الضبط, إجمالي الصفحات)."""
    total_pages = max(1, (len(items) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    return items[start:start + PAGE_SIZE], page, total_pages


def _grid_rows(buttons: list[InlineKeyboardButton]) -> list[list[InlineKeyboardButton]]:
    """يرتب الأزرار عنصرين في كل صف."""
    return [buttons[i:i + 2] for i in range(0, len(buttons), 2)]


def _nav_row(prefix: str, page: int, total_pages: int) -> list[list[InlineKeyboardButton]]:
    """صف السابق / رقم الصفحة / التالي — يظهر فقط عند وجود أكثر من صفحة."""
    if total_pages <= 1:
        return []
    row = []
    if page > 0:
        row.append(InlineKeyboardButton(text="◀️ السابق", callback_data=f"{prefix}:{page - 1}"))
    row.append(InlineKeyboardButton(text=f"{page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton(text="التالي ▶️", callback_data=f"{prefix}:{page + 1}"))
    return [row]


def kb_subscribe(channel_link: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📢 الانضمام إلى القناة", url=channel_link)
    b.button(text="✅ لقد اشتركت", callback_data="checksub")
    b.adjust(1)
    return b.as_markup()


def kb_main_menu(menus: list[str], page: int = 0) -> InlineKeyboardMarkup:
    items = [(m, f"menu:{m}") for m in menus] + [("📦 طلباتي", "myorders"), ("🎁 دعوة أصدقاء", "referral")]
    page_items, page, total_pages = _slice_page(items, page)
    buttons = [InlineKeyboardButton(text=t, callback_data=cd, style="success") for t, cd in page_items]
    rows = _grid_rows(buttons) + _nav_row("mainpage", page, total_pages)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_services(services: list[dict], page: int = 0) -> InlineKeyboardMarkup:
    items = [(s["name_ar"], f"service:{s['id']}") for s in services]
    page_items, page, total_pages = _slice_page(items, page)
    buttons = [InlineKeyboardButton(text=t, callback_data=cd, style="success") for t, cd in page_items]
    rows = _grid_rows(buttons) + _nav_row("svcpage", page, total_pages)
    rows.append([InlineKeyboardButton(text="⬅️ رجوع", callback_data="back:main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_options(options: list[dict], service_id: str, page: int = 0) -> InlineKeyboardMarkup:
    items = [(f"{o['label']} - {o['price']}", f"option:{o['id']}") for o in options]
    page_items, page, total_pages = _slice_page(items, page)
    buttons = [InlineKeyboardButton(text=t, callback_data=cd, style="success") for t, cd in page_items]
    rows = _grid_rows(buttons) + _nav_row("optpage", page, total_pages)
    rows.append([InlineKeyboardButton(text="⬅️ رجوع", callback_data="backservices")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_discount_choice() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🏷️ لدي كود خصم", callback_data="discount:yes", style="success")
    b.button(text="متابعة بدون كود", callback_data="discount:no")
    b.adjust(1)
    return b.as_markup()


def kb_payment_methods(methods: list[dict], page: int = 0) -> InlineKeyboardMarkup:
    items = [(m["name_ar"], f"pay:{m['id']}") for m in methods]
    page_items, page, total_pages = _slice_page(items, page)
    buttons = [InlineKeyboardButton(text=t, callback_data=cd, style="success") for t, cd in page_items]
    rows = _grid_rows(buttons) + _nav_row("paypage", page, total_pages)
    rows.append([InlineKeyboardButton(text="⬅️ رجوع", callback_data="backoptions")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def kb_admin_decision(order_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ قبول", callback_data=f"admin:accept:{order_id}", style="success")
    b.button(text="❌ رفض", callback_data=f"admin:reject:{order_id}", style="danger")
    b.adjust(2)
    return b.as_markup()


def kb_admin_fulfill(order_id: str) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="📦 تم التنفيذ", callback_data=f"admin:fulfill:{order_id}", style="success")
    b.adjust(1)
    return b.as_markup()


def kb_back_main() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ القائمة الرئيسية", callback_data="back:main")
    return b.as_markup()
