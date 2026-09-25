"""
\u0637\u0628\u0642\u0629 \u0627\u0644\u0648\u0635\u0648\u0644 \u0625\u0644\u0649 Google Sheet.
\u0643\u0644 \u0634\u064a\u0621 (\u0627\u0644\u0625\u0639\u062f\u0627\u062f\u0627\u062a\u060c \u0627\u0644\u062e\u062f\u0645\u0627\u062a\u060c \u0627\u0644\u0623\u0633\u0639\u0627\u0631\u060c \u0637\u0631\u0642 \u0627\u0644\u062f\u0641\u0639\u060c \u0623\u0643\u0648\u0627\u062f \u0627\u0644\u062e\u0635\u0645\u060c \u0627\u0644\u0637\u0644\u0628\u0627\u062a) \u064a\u064f\u0642\u0631\u0623 \u0648\u064a\u064f\u0643\u062a\u0628 \u0645\u0646 \u0647\u0646\u0627.
\u062a\u0633\u062a\u062e\u062f\u0645 \u0643\u0627\u0634 \u0628\u0633\u064a\u0637 (TTL) \u0644\u0644\u0642\u0631\u0627\u0621\u0627\u062a \u0627\u0644\u0645\u062a\u0643\u0631\u0631\u0629 \u062d\u062a\u0649 \u064a\u0628\u0642\u0649 \u0631\u062f \u0627\u0644\u0628\u0648\u062a \u0633\u0631\u064a\u0639\u064b\u0627 \u062c\u062f\u064b\u0627
\u0648\u0644\u0627 \u0646\u0633\u062a\u0647\u0644\u0643 \u062d\u0635\u0629 Google Sheets API \u0628\u0633\u0631\u0639\u0629.
\u062a\u062d\u062a\u0648\u064a \u0623\u064a\u0636\u064b\u0627 \u0639\u0644\u0649 \u0625\u0639\u0627\u062f\u0629 \u0645\u062d\u0627\u0648\u0644\u0629 \u062a\u0644\u0642\u0627\u0626\u064a\u0629 (retry with backoff) \u0639\u0646\u062f \u062a\u062c\u0627\u0648\u0632 \u062d\u0635\u0629
\u0627\u0644\u0642\u0631\u0627\u0621\u0629 (\u062e\u0637\u0623 429)\u060c \u0628\u062f\u0644 \u0623\u0646 \u064a\u0646\u0647\u0627\u0631 \u0627\u0644\u0628\u0648\u062a \u0641\u0648\u0631\u064b\u0627 \u0648\u064a\u062f\u062e\u0644 \u0628\u062d\u0644\u0642\u0629 \u0625\u0639\u0627\u062f\u0629 \u062a\u0634\u063a\u064a\u0644 \u0645\u062a\u0643\u0631\u0631\u0629
\u062a\u0633\u062a\u0647\u0644\u0643 \u0627\u0644\u062d\u0635\u0629 \u0623\u0643\u062b\u0631 \u0648\u0623\u0643\u062b\u0631.
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
    """\u064a\u0646\u0641\u0630 \u0623\u064a \u0627\u0633\u062a\u062f\u0639\u0627\u0621 \u0644\u0640 gspread\u060c \u0648\u0625\u0646 \u0641\u0634\u0644 \u0628\u0633\u0628\u0628 \u062a\u062c\u0627\u0648\u0632 \u0627\u0644\u062d\u0635\u0629 (429) \u064a\u0639\u064a\u062f \u0627\u0644\u0645\u062d\u0627\u0648\u0644\u0629
    \u0645\u0639 \u062a\u0623\u062e\u064a\u0631 \u0645\u062a\u0632\u0627\u064a\u062f (4s, 8s, 16s, 32s, 64s) \u0628\u062f\u0644 \u0645\u0627 \u064a\u0646\u0647\u0627\u0631 \u0627\u0644\u0628\u0648\u062a \u0641\u0648\u0631\u064b\u0627.
    \u0623\u064a \u062e\u0637\u0623 \u0622\u062e\u0631 \u063a\u064a\u0631 429 \u064a\u064f\u0631\u0641\u0639 \u0641\u0648\u0631\u064b\u0627 \u0643\u0645\u0627 \u0647\u0648."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except APIError as e:
            is_quota = "429" in str(e) or "Quota exceeded" in str(e)
            if not is_quota or attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning("\u062a\u062c\u0627\u0648\u0632 \u062d\u0635\u0629 Google Sheets (429)\u060c \u0625\u0639\u0627\u062f\u0629 \u0645\u062d\u0627\u0648\u0644\u0629 \u062e\u0644\u0627\u0644 %ss (\u0645\u062d\u0627\u0648\u0644\u0629 %s/%s)",
                            delay, attempt + 1, max_retries)
            time.sleep(delay)


# ---------------- \u0627\u0644\u0627\u062a\u0635\u0627\u0644 \u0627\u0644\u0623\u0648\u0644\u064a (\u0645\u0639 \u0625\u0639\u0627\u062f\u0629 \u0645\u062d\u0627\u0648\u0644\u0629 \u0639\u0646\u062f \u062a\u062c\u0627\u0648\u0632 \u0627\u0644\u062d\u0635\u0629) ----------------
_creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
_gc = gspread.authorize(_creds)
_sheet = _retry_on_quota(_gc.open_by_key, GOOGLE_SHEET_ID)

_ws = {}
for _name in ("Settings", "Services", "Options", "PaymentMethods", "DiscountCodes", "Orders", "Customers"):
    _ws[_name] = _retry_on_quota(_sheet.worksheet, _name)

# \u0643\u0627\u0634 \u0642\u0635\u064a\u0631 \u0627\u0644\u0623\u0645\u062f \u0644\u0644\u0642\u0631\u0627\u0621\u0627\u062a \u0627\u0644\u0645\u062a\u0643\u0631\u0631\u0629. \u0645\u062f\u0629 \u0623\u0637\u0648\u0644 = \u0637\u0644\u0628\u0627\u062a \u0623\u0642\u0644 \u0644\u062c\u0648\u062c\u0644 = \u0645\u0642\u0627\u0648\u0645\u0629 \u0623\u0643\u0628\u0631 \u0644\u062a\u062c\u0627\u0648\u0632 \u0627\u0644\u062d\u0635\u0629.
_cache = TTLCache(maxsize=32, ttl=30)

# ---------------- \u0625\u0635\u0644\u0627\u062d \u0635\u0641 \u0627\u0644\u0639\u0646\u0627\u0648\u064a\u0646 \u062a\u0644\u0642\u0627\u0626\u064a\u064b\u0627 ----------------
# \u0628\u0639\u0636 \u0627\u0644\u0634\u064a\u062a\u0627\u062a \u0642\u062f \u062a\u064f\u0646\u0634\u0623 \u062f\u0648\u0646 \u0635\u0641 \u0639\u0646\u0627\u0648\u064a\u0646 (\u0627\u0644\u0635\u0641 \u0627\u0644\u0623\u0648\u0644 = \u0628\u064a\u0627\u0646\u0627\u062a \u0641\u0639\u0644\u064a\u0629)\u060c \u0645\u0627 \u064a\u0645\u0646\u0639
# get_all_records \u0645\u0646 \u0627\u0644\u0639\u0645\u0644 \u0628\u0634\u0643\u0644 \u0635\u062d\u064a\u062d. \u0647\u0630\u0647 \u0627\u0644\u062f\u0627\u0644\u0629 \u062a\u062a\u0623\u0643\u062f \u0645\u0646 \u0648\u062c\u0648\u062f \u0635\u0641 \u0627\u0644\u0639\u0646\u0627\u0648\u064a\u0646
# \u0627\u0644\u0635\u062d\u064a\u062d \u0641\u0648\u0642 \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a\u060c \u0648\u062a\u0636\u064a\u0641\u0647 \u062a\u0644\u0642\u0627\u0626\u064a\u064b\u0627 \u0639\u0646\u062f \u0627\u0644\u062d\u0627\u062c\u0629 \u062f\u0648\u0646 \u062d\u0630\u0641 \u0623\u064a \u0628\u064a\u0627\u0646\u0627\u062a \u0645\u0648\u062c\u0648\u062f\u0629.
ORDERS_HEADERS = [
    "order_id", "timestamp", "user_id", "username", "full_name",
    "service_name", "option_label", "base_price", "discount_code",
    "final_price", "payment_method", "proof", "extra_info", "status",
]
# referred_by: \u0645\u0639\u0631\u0641 \u0627\u0644\u0632\u0628\u0648\u0646 \u0627\u0644\u0630\u064a \u0623\u062d\u0627\u0644 \u0647\u0630\u0627 \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645 (\u0641\u0627\u0631\u063a \u0625\u0646 \u0644\u0645 \u064a\u064f\u062d\u064e\u0644 \u0645\u0646 \u0623\u062d\u062f)
# ref_rewarded: TRUE \u0628\u0639\u062f \u0625\u0634\u0639\u0627\u0631 \u0627\u0644\u0623\u062f\u0645\u0646/\u0627\u0644\u062f\u0627\u0639\u064a \u0628\u0623\u0648\u0644 \u0639\u0645\u0644\u064a\u0629 \u0634\u0631\u0627\u0621 \u0645\u062f\u0641\u0648\u0639\u0629 (\u0644\u0645\u0646\u0639 \u0627\u0644\u062a\u0643\u0631\u0627\u0631)
CUSTOMERS_HEADERS = ["user_id", "customer_number", "timestamp", "blocked", "referred_by", "ref_rewarded"]


def _ensure_header(ws, expected: list[str]) -> bool:
    try:
        first_row = _retry_on_quota(ws.row_values, 1)
    except Exception:
        first_row = []
    normalized = [str(c).strip() for c in first_row]
    if normalized[: len(expected)] == expected:
        return False
    # \u0625\u0646 \u0643\u0627\u0646 \u0635\u0641 \u0627\u0644\u0639\u0646\u0627\u0648\u064a\u0646 \u0645\u0648\u062c\u0648\u062f\u064b\u0627 \u0648\u0635\u062d\u064a\u062d\u064b\u0627 \u0644\u0643\u0646 \u0646\u0627\u0642\u0635 \u0623\u0639\u0645\u062f\u0629 \u062c\u062f\u064a\u062f\u0629 \u0641\u064a \u0646\u0647\u0627\u064a\u062a\u0647
    # (\u0645\u062b\u0644 \u062a\u0631\u0642\u064a\u0629 \u0633\u0627\u0628\u0642\u0629 \u0623\u0636\u0627\u0641\u062a \u0639\u0645\u0648\u062f "blocked")\u060c \u0623\u0643\u0645\u0644 \u0627\u0644\u0623\u0639\u0645\u062f\u0629 \u0627\u0644\u0646\u0627\u0642\u0635\u0629 \u0641\u0642\u0637
    # \u062f\u0648\u0646 \u0625\u062f\u0631\u0627\u062c \u0635\u0641 \u062c\u062f\u064a\u062f \u0641\u0648\u0642 \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a.
    if normalized and expected[: len(normalized)] == normalized:
        for i in range(len(normalized), len(expected)):
            _retry_on_quota(ws.update_cell, 1, i + 1, expected[i])
        return True
    _retry_on_quota(ws.insert_row, expected, index=1, value_input_option="RAW")
    return True


def ensure_all_headers() -> None:
    """\u062a\u064f\u0633\u062a\u062f\u0639\u0649 \u0645\u0631\u0629 \u0639\u0646\u062f \u0625\u0642\u0644\u0627\u0639 \u0627\u0644\u0628\u0648\u062a. \u062a\u064f\u0635\u0644\u062d \u0635\u0641\u0648\u0641 \u0627\u0644\u0639\u0646\u0627\u0648\u064a\u0646 \u0627\u0644\u0646\u0627\u0642\u0635\u0629 \u0641\u064a Orders \u0648Customers."""
    changed_orders = _ensure_header(_ws["Orders"], ORDERS_HEADERS)
    changed_customers = _ensure_header(_ws["Customers"], CUSTOMERS_HEADERS)
    if changed_orders or changed_customers:
        clear_cache()


def cleanup_customers() -> None:
    """\u062a\u064f\u0633\u062a\u062f\u0639\u0649 \u0645\u0631\u0629 \u0639\u0646\u062f \u0625\u0642\u0644\u0627\u0639 \u0627\u0644\u0628\u0648\u062a. \u062a\u062d\u0630\u0641 \u062a\u0643\u0631\u0627\u0631 \u0627\u0644\u0632\u0628\u0627\u0626\u0646 (\u0646\u0641\u0633 user_id \u0639\u062f\u0629 \u0645\u0631\u0627\u062a)
    \u0648\u062a\u064f\u0639\u064a\u062f \u062a\u0631\u0642\u064a\u0645\u0647\u0645 \u062a\u0633\u0644\u0633\u0644\u064a\u064b\u0627 \u062d\u0633\u0628 \u0623\u0648\u0644 \u0638\u0647\u0648\u0631. \u0622\u0645\u0646\u0629 \u0644\u0644\u062a\u0634\u063a\u064a\u0644 \u0641\u064a \u0643\u0644 \u0645\u0631\u0629: \u0644\u0627 \u062a\u064f\u063a\u064a\u0651\u0631
    \u0634\u064a\u0626\u064b\u0627 \u0625\u0646 \u0643\u0627\u0646\u062a \u0627\u0644\u0628\u064a\u0627\u0646\u0627\u062a \u0645\u0631\u062a\u0628\u0629 \u0623\u0635\u0644\u064b\u0627."""
    ws = _ws["Customers"]
    data = _retry_on_quota(ws.get_all_values)
    if len(data) <= 1:
        return

    rows = data[1:]
    seen: dict[str, list] = {}
    order_first_seen: list[str] = []
    for r in rows:
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


def _records(sheet_name: str):
    cached = _cache.get(sheet_name)
    if cached is not None:
        return cached
    records = _retry_on_quota(_ws[sheet_name].get_all_records)
    _cache[sheet_name] = records
    return records


def clear_cache():
    _cache.clear()


def _truthy(v) -> bool:
    return str(v).strip().upper() in ("TRUE", "1", "YES", "\u0646\u0639\u0645", "\u0635\u062d", "ACTIVE")


# ---------------- \u0627\u0644\u0625\u0639\u062f\u0627\u062f\u0627\u062a ----------------
def get_settings() -> dict:
    rows = _records("Settings")
    return {str(r.get("key", "")).strip(): str(r.get("value", "")).strip() for r in rows if r.get("key")}


# ---------------- \u0627\u0644\u062e\u062f\u0645\u0627\u062a ----------------
def get_menus() -> list[str]:
    """\u064a\u0628\u0646\u064a \u0642\u0627\u0626\u0645\u0629 \u0627\u0644\u0623\u0632\u0631\u0627\u0631 \u0627\u0644\u0631\u0626\u064a\u0633\u064a\u0629 \u062a\u0644\u0642\u0627\u0626\u064a\u064b\u0627 \u0645\u0646 \u0639\u0645\u0648\u062f menu_name \u0644\u0643\u0644 \u062e\u062f\u0645\u0629 \u0641\u0639\u0651\u0627\u0644\u0629."""
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


# ---------------- \u0627\u0644\u0643\u0645\u064a\u0627\u062a / \u0627\u0644\u0623\u0633\u0639\u0627\u0631 ----------------
def get_options(service_id: str) -> list[dict]:
    rows = [r for r in _records("Options") if _truthy(r.get("active")) and str(r.get("service_id")) == str(service_id)]
    rows.sort(key=lambda r: _to_num(r.get("sort_order")))
    return rows


def get_option_by_id(option_id: str) -> dict | None:
    for r in _records("Options"):
        if str(r.get("id")) == str(option_id):
            return r
    return None


# ---------------- \u0637\u0631\u0642 \u0627\u0644\u062f\u0641\u0639 ----------------
def get_payment_methods() -> list[dict]:
    rows = [r for r in _records("PaymentMethods") if _truthy(r.get("active"))]
    rows.sort(key=lambda r: _to_num(r.get("sort_order")))
    return rows


def get_payment_method_by_id(pm_id: str) -> dict | None:
    for r in _records("PaymentMethods"):
        if str(r.get("id")) == str(pm_id):
            return r
    return None


# ---------------- \u0623\u0643\u0648\u0627\u062f \u0627\u0644\u062e\u0635\u0645 ----------------
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


# ---------------- \u0627\u0644\u0637\u0644\u0628\u0627\u062a ----------------
# \u0627\u0633\u062a\u0628\u0639\u0627\u062f \u0627\u0644\u062d\u0631\u0648\u0641 \u0627\u0644\u0645\u062a\u0634\u0627\u0628\u0647\u0629 \u0645\u0639 \u0627\u0644\u0623\u0631\u0642\u0627\u0645 (O \u064a\u0634\u0628\u0647 0\u060c I \u064a\u0634\u0628\u0647 1) \u0644\u062a\u0642\u0644\u064a\u0644 \u0627\u0644\u0623\u062e\u0637\u0627\u0621
# \u0639\u0646\u062f \u0643\u062a\u0627\u0628\u0629 \u0631\u0642\u0645 \u0627\u0644\u0637\u0644\u0628 \u064a\u062f\u0648\u064a\u064b\u0627 \u0644\u0644\u062f\u0639\u0645.
_ORDER_ID_LETTERS = [c for c in string.ascii_uppercase if c not in ("O", "I")]


def _new_order_id() -> str:
    """\u0631\u0642\u0645 \u0637\u0644\u0628 \u0642\u0635\u064a\u0631 \u0648\u0639\u0634\u0648\u0627\u0626\u064a \u0648\u0641\u0631\u064a\u062f: \u062d\u0631\u0641 + 6 \u0623\u0631\u0642\u0627\u0645\u060c \u0645\u062b\u0644 K482915."""
    existing = {str(r.get("order_id")) for r in _records("Orders")}
    for _ in range(50):
        candidate = random.choice(_ORDER_ID_LETTERS) + "".join(random.choices(string.digits, k=6))
        if candidate not in existing:
            return candidate
    # \u0627\u062d\u062a\u064a\u0627\u0637\u064a \u0634\u0628\u0647 \u0645\u0633\u062a\u062d\u064a\u0644 \u0627\u0644\u062d\u062f\u0648\u062b: \u0623\u0636\u0641 \u0628\u0635\u0645\u0629 \u0632\u0645\u0646\u064a\u0629 \u0644\u0636\u0645\u0627\u0646 \u0639\u062f\u0645 \u0627\u0644\u062a\u0643\u0631\u0627\u0631
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
        "\u0642\u064a\u062f \u0627\u0644\u0645\u0631\u0627\u062c\u0639\u0629",
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
    """\u064a\u0628\u062d\u062b \u0639\u0646 \u0643\u0644 \u0627\u0644\u0637\u0644\u0628\u0627\u062a \u0627\u0644\u062a\u064a \u0627\u0633\u062a\u064f\u062e\u062f\u0645 \u0641\u064a\u0647\u0627 \u0646\u0641\u0633 \u0631\u0642\u0645 \u0627\u0644\u0639\u0645\u0644\u064a\u0629 (\u0646\u0635 \u0641\u0642\u0637\u060c \u0644\u064a\u0633 \u0635\u0648\u0631).
    \u064a\u064f\u0633\u062a\u062e\u062f\u0645 \u0644\u062a\u0646\u0628\u064a\u0647 \u0627\u0644\u0623\u062f\u0645\u0646 \u0639\u0646\u062f \u0625\u0639\u0627\u062f\u0629 \u0627\u0633\u062a\u062e\u062f\u0627\u0645 \u0631\u0642\u0645 \u0639\u0645\u0644\u064a\u0629 \u0633\u0627\u0628\u0642."""
    proof = str(proof or "").strip()
    if not proof:
        return []
    return [r for r in _records("Orders") if str(r.get("proof", "")).strip() == proof]


def count_accepted_orders(user_id) -> int:
    """\u064a\u062d\u0633\u0628 \u0639\u062f\u062f \u0637\u0644\u0628\u0627\u062a \u0627\u0644\u0632\u0628\u0648\u0646 \u0627\u0644\u062a\u064a \u0648\u0635\u0644\u062a \u0644\u062d\u0627\u0644\u0629 \u0645\u0642\u0628\u0648\u0644 \u0623\u0648 \u0645\u0646\u0641\u064e\u0651\u0630.
    \u062a\u064f\u0633\u062a\u062e\u062f\u0645 \u0644\u0645\u0639\u0631\u0641\u0629 \u0625\u0646 \u0643\u0627\u0646\u062a \u0639\u0645\u0644\u064a\u0629 \u0627\u0644\u0642\u0628\u0648\u0644 \u0627\u0644\u062d\u0627\u0644\u064a\u0629 \u0647\u064a \u0623\u0648\u0644 \u0639\u0645\u0644\u064a\u0629 \u0634\u0631\u0627\u0621 \u0645\u062f\u0641\u0648\u0639\u0629 \u0644\u0647 (\u0646\u0638\u0627\u0645 \u0627\u0644\u0625\u062d\u0627\u0644\u0629)."""
    paid_statuses = {"\u0645\u0642\u0628\u0648\u0644 \u2705", "\u0645\u0646\u0641\u064e\u0651\u0630 \U0001f4e6"}
    count = 0
    for r in _records("Orders"):
        if str(r.get("user_id")) == str(user_id) and str(r.get("status")) in paid_statuses:
            count += 1
    return count


# ---------------- \u0631\u0642\u0645 \u0627\u0644\u0632\u0628\u0648\u0646 \u0627\u0644\u062a\u0633\u0644\u0633\u0644\u064a (\u0644\u0623\u0648\u0644 \u0645\u062d\u0627\u062f\u062b\u0629 \u0641\u0642\u0637) ----------------
def get_customer_number(user_id: int, referred_by: str = "") -> tuple[int, bool]:
    """\u064a\u0631\u062c\u0639 (\u0627\u0644\u0631\u0642\u0645, \u0647\u0644 \u0647\u0648 \u0632\u0628\u0648\u0646 \u062c\u062f\u064a\u062f). \u0623\u0648\u0644 \u0632\u0628\u0648\u0646 \u064a\u0627\u062e\u062f \u0631\u0642\u0645 \u0627\u0644\u0628\u062f\u0627\u064a\u0629 \u0645\u0646 Settings (\u0627\u0641\u062a\u0631\u0627\u0636\u064a\u064b\u0627 1310).
    referred_by: \u0645\u0639\u0631\u0641 \u0627\u0644\u0632\u0628\u0648\u0646 \u0627\u0644\u0630\u064a \u0623\u062d\u0627\u0644 \u0647\u0630\u0627 \u0627\u0644\u0645\u0633\u062a\u062e\u062f\u0645 \u2014 \u064a\u064f\u062d\u0641\u0638 \u0641\u0642\u0637 \u0639\u0646\u062f \u0625\u0646\u0634\u0627\u0621 \u0627\u0644\u0632\u0628\u0648\u0646 \u0644\u0623\u0648\u0644 \u0645\u0631\u0629."""
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
    """\u064a\u0631\u062c\u0639 \u0633\u062c\u0644 \u0627\u0644\u0632\u0628\u0648\u0646 \u0643\u0627\u0645\u0644\u064b\u0627 (\u064a\u0634\u0645\u0644 referred_by \u0648ref_rewarded) \u0623\u0648 None \u0625\u0646 \u0644\u0645 \u064a\u0648\u062c\u062f."""
    for r in _records("Customers"):
        if str(r.get("user_id")) == str(user_id):
            return r
    return None


def mark_referral_rewarded(user_id) -> None:
    """\u062a\u064f\u0633\u062a\u062f\u0639\u0649 \u0628\u0639\u062f \u0625\u0634\u0639\u0627\u0631 \u0627\u0644\u0623\u062f\u0645\u0646/\u0627\u0644\u062f\u0627\u0639\u064a \u0628\u0623\u0646 \u0647\u0630\u0627 \u0627\u0644\u0632\u0628\u0648\u0646 \u0627\u0644\u0645\u064f\u062d\u0627\u0644 \u0623\u062a\u0645 \u0623\u0648\u0644 \u0639\u0645\u0644\u064a\u0629 \u0634\u0631\u0627\u0621 \u0645\u062f\u0641\u0648\u0639\u0629\u060c
    \u0644\u0645\u0646\u0639 \u062a\u0643\u0631\u0627\u0631 \u0627\u0644\u0625\u0634\u0639\u0627\u0631 \u0639\u0646\u062f \u0623\u064a \u0637\u0644\u0628\u0627\u062a \u0644\u0627\u062d\u0642\u0629 \u0644\u0647."""
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


# ---------------- \u0627\u0644\u0628\u062b \u0627\u0644\u062c\u0645\u0627\u0639\u064a ----------------
def get_broadcast_customers() -> list[str]:
    """\u0643\u0644 \u0627\u0644\u0632\u0628\u0627\u0626\u0646 \u0627\u0644\u0630\u064a\u0646 \u0644\u0645 \u064a\u062d\u0638\u0631\u0648\u0627 \u0627\u0644\u0628\u0648\u062a \u2014 \u062a\u064f\u0633\u062a\u062e\u062f\u0645 \u0641\u064a \u0625\u0631\u0633\u0627\u0644 \u0627\u0644\u0628\u062b \u0627\u0644\u062c\u0645\u0627\u0639\u064a."""
    records = _records("Customers")
    return [str(r.get("user_id")) for r in records if str(r.get("user_id")) and not _truthy(r.get("blocked"))]


def mark_customer_blocked(user_id) -> None:
    """\u062a\u064f\u0633\u062a\u062f\u0639\u0649 \u0639\u0646\u062f \u0641\u0634\u0644 \u0625\u0631\u0633\u0627\u0644 \u0627\u0644\u0628\u062b \u0644\u0632\u0628\u0648\u0646 \u0628\u0633\u0628\u0628 \u062d\u0638\u0631 \u0627\u0644\u0628\u0648\u062a\u060c \u0641\u0644\u0627 \u0646\u062d\u0627\u0648\u0644 \u0645\u0631\u0627\u0633\u0644\u062a\u0647 \u0645\u062c\u062f\u062f\u064b\u0627."""
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
