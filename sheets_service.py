"""
طبقة الوصول إلى Google Sheet.
كل شيء (الإعدادات، الخدمات، الأسعار، طرق الدفع، أكواد الخصم، الطلبات) يُقرأ ويُكتب من هنا.
تستخدم كاش بسيط (TTL) للقراءات المتكررة حتى يبقى رد البوت سريعًا جدًا
ولا نستهلك حصة Google Sheets API بسرعة.
"""
import time
import random
import string
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials
from cachetools import TTLCache

from config import GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_FILE

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

_creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
_gc = gspread.authorize(_creds)
_sheet = _gc.open_by_key(GOOGLE_SHEET_ID)

_ws = {
    "Settings": _sheet.worksheet("Settings"),
    "Services": _sheet.worksheet("Services"),
    "Options": _sheet.worksheet("Options"),
    "PaymentMethods": _sheet.worksheet("PaymentMethods"),
    "DiscountCodes": _sheet.worksheet("DiscountCodes"),
    "Orders": _sheet.worksheet("Orders"),
    "Customers": _sheet.worksheet("Customers"),
}

# كاش قصير الأمد للقراءات المتكررة (لا يشمل الطلبات لأنها تحتاج دقة فورية)
_cache = TTLCache(maxsize=32, ttl=15)


def _records(sheet_name: str):
    cached = _cache.get(sheet_name)
    if cached is not None:
        return cached
    records = _ws[sheet_name].get_all_records()
    _cache[sheet_name] = records
    return records


def clear_cache():
    _cache.clear()


def _truthy(v) -> bool:
    return str(v).strip().upper() in ("TRUE", "1", "YES", "نعم", "صح", "ACTIVE")


# ---------------- الإعدادات ----------------
def get_settings() -> dict:
    rows = _records("Settings")
    return {str(r.get("key", "")).strip(): str(r.get("value", "")).strip() for r in rows if r.get("key")}


# ---------------- الخدمات ----------------
def get_menus() -> list[str]:
    """يبني قائمة الأزرار الرئيسية تلقائيًا من عمود menu_name لكل خدمة فعّالة."""
    rows = [r for r in _records("Services") if _truthy(r.get("active"))]
    rows.sort(key=lambda r: (_to_num(r.get("sort_order")), str(r.get("menu_name"))))
    seen = []
    for r in rows:
        m = str(r.get("menu_name", "")).strip()
        if m and m not in seen:
            seen.append(m)
    return seen


def _to_num(v, default=9999):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def get_services_by_menu(menu_name: str) -> list[dict]:
    rows = [r for r in _records("Services") if _truthy(r.get("active")) and str(r.get("menu_name", "")).strip() == menu_name]
    rows.sort(key=lambda r: _to_num(r.get("sort_order")))
    return rows


def get_service_by_id(service_id: str) -> dict | None:
    for r in _records("Services"):
        if str(r.get("id")) == str(service_id):
            return r
    return None


# ---------------- الكميات / الأسعار ----------------
def get_options(service_id: str) -> list[dict]:
    rows = [r for r in _records("Options") if _truthy(r.get("active")) and str(r.get("service_id")) == str(service_id)]
    rows.sort(key=lambda r: _to_num(r.get("sort_order")))
    return rows


def get_option_by_id(option_id: str) -> dict | None:
    for r in _records("Options"):
        if str(r.get("id")) == str(option_id):
            return r
    return None


# ---------------- طرق الدفع ----------------
def get_payment_methods() -> list[dict]:
    rows = [r for r in _records("PaymentMethods") if _truthy(r.get("active"))]
    rows.sort(key=lambda r: _to_num(r.get("sort_order")))
    return rows


def get_payment_method_by_id(pm_id: str) -> dict | None:
    for r in _records("PaymentMethods"):
        if str(r.get("id")) == str(pm_id):
            return r
    return None


# ---------------- أكواد الخصم ----------------
def validate_discount(code: str) -> dict | None:
    code = code.strip().upper()
    for r in _records("DiscountCodes"):
        if str(r.get("code", "")).strip().upper() == code and _truthy(r.get("active")):
            max_uses = _to_num(r.get("max_uses"), default=0)
            used = _to_num(r.get("used_count"), default=0)
            if max_uses == 0 or used < max_uses:
                return r
    return None


def increment_discount_usage(code: str):
    cell = _ws["DiscountCodes"].find(code, in_column=1)
    if not cell:
        return
    headers = _ws["DiscountCodes"].row_values(1)
    try:
        col = headers.index("used_count") + 1
    except ValueError:
        return
    current = _ws["DiscountCodes"].cell(cell.row, col).value
    current = int(current) if current and str(current).isdigit() else 0
    _ws["DiscountCodes"].update_cell(cell.row, col, current + 1)
    _cache.pop("DiscountCodes", None)


# ---------------- الطلبات ----------------
def _new_order_id() -> str:
    suffix = "".join(random.choices(string.digits, k=3))
    return f"{datetime.now().strftime('%y%m%d%H%M%S')}{suffix}"


def create_order(**fields) -> str:
    order_id = _new_order_id()
    row = [
        order_id,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        str(fields.get("user_id", "")),
        fields.get("username", ""),
        fields.get("full_name", ""),
        fields.get("service_name", ""),
        fields.get("option_label", ""),
        fields.get("base_price", ""),
        fields.get("discount_code", ""),
        fields.get("final_price", ""),
        fields.get("payment_method", ""),
        fields.get("proof", ""),
        fields.get("extra_info", ""),
        "قيد المراجعة",
    ]
    _ws["Orders"].append_row(row, value_input_option="USER_ENTERED")
    return order_id


def get_order(order_id: str) -> dict | None:
    for r in _ws["Orders"].get_all_records():
        if str(r.get("order_id")) == str(order_id):
            return r
    return None


def update_order_status(order_id: str, status: str):
    cell = _ws["Orders"].find(str(order_id), in_column=1)
    if not cell:
        return
    headers = _ws["Orders"].row_values(1)
    try:
        col = headers.index("status") + 1
    except ValueError:
        return
    _ws["Orders"].update_cell(cell.row, col, status)


def get_orders_by_user(user_id: int, limit: int = 10) -> list[dict]:
    rows = [r for r in _ws["Orders"].get_all_records() if str(r.get("user_id")) == str(user_id)]
    rows.reverse()
    return rows[:limit]


# ---------------- رقم الزبون التسلسلي (لأول محادثة فقط) ----------------
def get_customer_number(user_id: int) -> tuple[int, bool]:
    """يرجع (الرقم, هل هو زبون جديد). أول زبون ياخد رقم البداية من Settings (افتراضيًا 1310)."""
    records = _ws["Customers"].get_all_records()
    for r in records:
        if str(r.get("user_id")) == str(user_id):
            try:
                return int(r.get("customer_number")), False
            except (TypeError, ValueError):
                return 0, False

    settings = get_settings()
    try:
        start_num = int(settings.get("START_CUSTOMER_NUMBER", "1310") or 1310)
    except ValueError:
        start_num = 1310

    existing_numbers = []
    for r in records:
        try:
            existing_numbers.append(int(r.get("customer_number")))
        except (TypeError, ValueError):
            pass

    next_num = max(existing_numbers) + 1 if existing_numbers else start_num

    _ws["Customers"].append_row(
        [str(user_id), next_num, datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
        value_input_option="USER_ENTERED",
    )
    return next_num, True

