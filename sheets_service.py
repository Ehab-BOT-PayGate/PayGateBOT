"""
طبقة الوصول إلى Google Sheet.
كل شيء (الإعدادات، الخدمات، الأسعار، طرق الدفع، أكواد الخصم، الطلبات) يُقرأ ويُكتب من هنا.
تستخدم كاش بسيط (TTL) للقراءات المتكررة حتى يبقى رد البوت سريعًا جدًا
ولا نستهلك حصة Google Sheets API بسرعة.
تحتوي أيضًا على إعادة محاولة تلقائية (retry with backoff) عند تجاوز حصة
القراءة (خطأ 429)، بدل أن ينهار البوت فورًا ويدخل بحلقة إعادة تشغيل متكررة
تستهلك الحصة أكثر وأكثر.
"""
import time
import random
import string
import logging
from datetime import datetime

import gspread
from gspread.exceptions import APIError
from google.oauth2.service_account import Credentials
from cachetools import TTLCache

from config import GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_FILE

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _retry_on_quota(func, *args, max_retries=5, base_delay=4, **kwargs):
    """ينفذ أي استدعاء لـ gspread، وإن فشل بسبب تجاوز الحصة (429) يعيد المحاولة
    مع تأخير متزايد (4s, 8s, 16s, 32s, 64s) بدل ما ينهار البوت فورًا.
    أي خطأ آخر غير 429 يُرفع فورًا كما هو."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except APIError as e:
            is_quota = "429" in str(e) or "Quota exceeded" in str(e)
            if not is_quota or attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning("تجاوز حصة Google Sheets (429)، إعادة محاولة خلال %ss (محاولة %s/%s)",
                            delay, attempt + 1, max_retries)
            time.sleep(delay)


# ---------------- الاتصال الأولي (مع إعادة محاولة عند تجاوز الحصة) ----------------
_creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
_gc = gspread.authorize(_creds)
_sheet = _retry_on_quota(_gc.open_by_key, GOOGLE_SHEET_ID)

_SHEET_NAMES = ("Settings", "Services", "Options", "PaymentMethods", "DiscountCodes", "Orders", "Customers")
_all_ws = {ws.title: ws for ws in _retry_on_quota(_sheet.worksheets)}
_ws = {name: _all_ws[name] for name in _SHEET_NAMES if name in _all_ws}

_missing = [name for name in _SHEET_NAMES if name not in _ws]
if _missing:
    logger.warning("الشيتات التالية غير موجودة في الملف: %s", _missing)

_cache = TTLCache(maxsize=32, ttl=30)

ORDERS_HEADERS = [
    "order_id", "timestamp", "user_id", "username", "full_name",
    "service_name", "option_label", "base_price", "discount_code",
    "final_price", "payment_method", "proof", "extra_info", "status",
]
CUSTOMERS_HEADERS = ["user_id", "customer_number", "timestamp", "blocked", "referred_by", "ref_rewarded"]


def _ensure_header(ws, expected: list[str]) -> bool:
    try:
        first_row = _retry_on_quota(ws.row_values, 1)
    except Exception:
        first_row = []
    normalized = [str(c).strip() for c in first_row]
    if normalized[: len(expected)] == expected:
        return False
    if normalized and expected[: len(normalized)] == normalized:
        for i in range(len(normalized), len(expected)):
            _retry_on_quota(ws.update_cell, 1, i + 1, expected[i])
        return True
    _retry_on_quota(ws.insert_row, expected, index=1, value_input_option="RAW")
    return True


def ensure_all_headers() -> None:
    changed_orders = _ensure_header(_ws["Orders"], ORDERS_HEADERS)
    changed_customers = _ensure_header(_ws["Customers"], CUSTOMERS_HEADERS)
    if changed_orders or changed_customers:
        clear_cache()


def cleanup_customers() -> None:
    ws = _ws["Customers"]
    data = _retry_on_quota(ws.get_all_values, value_render_option="UNFORMATTED_VALUE")
    if len(data) <= 1:
        return

    rows = data[1:]
    seen: dict[str, list] = {}
    order_first_seen: list[str] = []
    for r in rows:
        r = [_denumberize(v) for v in r]
        uid = str(r[0]).strip() if len(r) > 0 else ""
        if not uid or uid in seen:
            continue
        seen[uid] = r
        order_first_seen.append(uid)

    settings = get_settings()
    try:
        start_num = int(settings.get("START_CUSTOMER_NUMBER", "1310") or 1310)
    except ValueError:
        start_num = 1310

    new_rows = []
    for i, uid in enumerate(order_first_seen):
        r = seen[uid]
        ts = r[2] if len(r) > 2 else ""
        blocked = r[3] if len(r) > 3 else "FALSE"
        referred_by = r[4] if len(r) > 4 else ""
        ref_rewarded = r[5] if len(r) > 5 else "FALSE"
        new_rows.append([uid, str(start_num + i), ts, blocked, referred_by, ref_rewarded])

    changed = len(new_rows) != len(rows)
    if not changed:
        for a, b in zip(rows, new_rows):
            a_uid = str(a[0]).strip() if len(a) > 0 else ""
            a_num = str(a[1]).strip() if len(a) > 1 else ""
            a_ts = a[2] if len(a) > 2 else ""
            a_blocked = a[3] if len(a) > 3 else "FALSE"
            a_ref_by = a[4] if len(a) > 4 else ""
            a_ref_rewarded = a[5] if len(a) > 5 else "FALSE"
            if (a_uid != b[0] or a_num != b[1] or a_ts != b[2] or a_blocked != b[3]
                    or a_ref_by != b[4] or a_ref_rewarded != b[5]):
                changed = True
                break
    if not changed:
        return

    last_row = len(rows) + 1
    _retry_on_quota(ws.batch_clear, [f"A2:F{last_row}"])
    if new_rows:
        _retry_on_quota(ws.update, f"A2:F{len(new_rows) + 1}", new_rows, value_input_option="USER_ENTERED")
    _cache.pop("Customers", None)


def _denumberize(value):
    """يحوّل أي رقم عشري يمثّل في الحقيقة عددًا صحيحًا (مثل 1679341347.0 الناتج
    عن قراءة معرّف المستخدم بصيغته غير المنسَّقة) إلى int عادي. بدون هذا، كل
    مقارنة نصية على user_id أو رقم عملية الدفع تفشل لأن '1679341347.0' لا
    تساوي '1679341347'، ما كان سيكسر "طلباتي" والبث الجماعي وربط الزبائن."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _records(sheet_name: str):
    cached = _cache.get(sheet_name)
    if cached is not None:
        return cached
    # UNFORMATTED_VALUE إلزامي: بدونها يرسل جوجل شيت القيمة كما تُعرض بصريًا
    # في الخلية (مثلًا 9.5 تُقرَّب إلى 10 إن كان تنسيق الخلية بدون كسور)
    # بدل الرقم الحقيقي المخزَّن، ما يسبب أسعارًا خاطئة تصل للبوت.
    raw_records = _retry_on_quota(
        _ws[sheet_name].get_all_records, value_render_option="UNFORMATTED_VALUE"
    )
    records = [{k: _denumberize(v) for k, v in r.items()} for r in raw_records]
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


def set_setting(key: str, value: str) -> None:
    """يحفظ/يحدّث قيمة إعداد واحد في شيت Settings (يضيف صفًا جديدًا إن لم يكن المفتاح موجودًا).
    تُستخدم مثلًا لحفظ WELCOME_IMAGE عبر أمر /setwelcome."""
    ws = _ws["Settings"]
    headers = _retry_on_quota(ws.row_values, 1)
    try:
        key_col = headers.index("key") + 1
        val_col = headers.index("value") + 1
    except ValueError:
        return
    cell = _retry_on_quota(ws.find, key, in_column=key_col)
    if cell:
        _retry_on_quota(ws.update_cell, cell.row, val_col, value)
    else:
        row = [""] * len(headers)
        row[key_col - 1] = key
        row[val_col - 1] = value
        _retry_on_quota(ws.append_row, row, value_input_option="RAW")
    _cache.pop("Settings", None)


# ---------------- الخدمات ----------------
def get_menus() -> list[str]:
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
    cell = _retry_on_quota(_ws["DiscountCodes"].find, code, in_column=1)
    if not cell:
        return
    headers = _retry_on_quota(_ws["DiscountCodes"].row_values, 1)
    try:
        col = headers.index("used_count") + 1
    except ValueError:
        return
    current = _retry_on_quota(_ws["DiscountCodes"].cell, cell.row, col).value
    current = int(current) if current and str(current).isdigit() else 0
    _retry_on_quota(_ws["DiscountCodes"].update_cell, cell.row, col, current + 1)
    _cache.pop("DiscountCodes", None)


# ---------------- الطلبات ----------------
_ORDER_ID_LETTERS = [c for c in string.ascii_uppercase if c not in ("O", "I")]


def _new_order_id() -> str:
    existing = {str(r.get("order_id")) for r in _records("Orders")}
    for _ in range(50):
        candidate = random.choice(_ORDER_ID_LETTERS) + "".join(random.choices(string.digits, k=6))
        if candidate not in existing:
            return candidate
    return random.choice(_ORDER_ID_LETTERS) + "".join(random.choices(string.digits, k=6)) + datetime.now().strftime("%S")


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
    _retry_on_quota(_ws["Orders"].append_row, row, value_input_option="USER_ENTERED")
    _cache.pop("Orders", None)
    return order_id


def get_order(order_id: str) -> dict | None:
    for r in _records("Orders"):
        if str(r.get("order_id")) == str(order_id):
            return r
    return None


def update_order_status(order_id: str, status: str):
    cell = _retry_on_quota(_ws["Orders"].find, str(order_id), in_column=1)
    if not cell:
        return
    headers = _retry_on_quota(_ws["Orders"].row_values, 1)
    try:
        col = headers.index("status") + 1
    except ValueError:
        return
    _retry_on_quota(_ws["Orders"].update_cell, cell.row, col, status)
    _cache.pop("Orders", None)


def get_orders_by_user(user_id: int, limit: int = 10) -> list[dict]:
    rows = [r for r in _records("Orders") if str(r.get("user_id")) == str(user_id)]
    rows.reverse()
    return rows[:limit]


def find_orders_by_proof(proof: str) -> list[dict]:
    proof = str(proof or "").strip()
    if not proof:
        return []
    return [r for r in _records("Orders") if str(r.get("proof", "")).strip() == proof]


def count_accepted_orders(user_id) -> int:
    paid_statuses = {"مقبول ✅", "منفَّذ 📦"}
    count = 0
    for r in _records("Orders"):
        if str(r.get("user_id")) == str(user_id) and str(r.get("status")) in paid_statuses:
            count += 1
    return count


# ---------------- رقم الزبون التسلسلي (لأول محادثة فقط) ----------------
def get_customer_number(user_id: int, referred_by: str = "") -> tuple[int, bool]:
    records = _records("Customers")
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

    _retry_on_quota(
        _ws["Customers"].append_row,
        [str(user_id), next_num, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "FALSE", str(referred_by or ""), "FALSE"],
        value_input_option="USER_ENTERED",
    )
    _cache.pop("Customers", None)
    return next_num, True


def get_customer(user_id) -> dict | None:
    for r in _records("Customers"):
        if str(r.get("user_id")) == str(user_id):
            return r
    return None


def mark_referral_rewarded(user_id) -> None:
    cell = _retry_on_quota(_ws["Customers"].find, str(user_id), in_column=1)
    if not cell:
        return
    headers = _retry_on_quota(_ws["Customers"].row_values, 1)
    try:
        col = headers.index("ref_rewarded") + 1
    except ValueError:
        return
    _retry_on_quota(_ws["Customers"].update_cell, cell.row, col, "TRUE")
    _cache.pop("Customers", None)


# ---------------- البث الجماعي ----------------
def get_broadcast_customers() -> list[str]:
    records = _records("Customers")
    return [str(r.get("user_id")) for r in records if str(r.get("user_id")) and not _truthy(r.get("blocked"))]


def mark_customer_blocked(user_id) -> None:
    cell = _retry_on_quota(_ws["Customers"].find, str(user_id), in_column=1)
    if not cell:
        return
    headers = _retry_on_quota(_ws["Customers"].row_values, 1)
    try:
        col = headers.index("blocked") + 1
    except ValueError:
        return
    _retry_on_quota(_ws["Customers"].update_cell, cell.row, col, "TRUE")
    _cache.pop("Customers", None)
