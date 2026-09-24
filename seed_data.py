# -*- coding: utf-8 -*-
"""
سكربت تعبئة تلقائي — يُشغَّل مرة واحدة فقط.
ينشئ كل التبويبات السبعة المطلوبة داخل Google Sheet ويعبّيها بكل البيانات
(الإعدادات، الألعاب، البطاقات، الاشتراكات، طرق الدفع) مباشرة عبر الـ API.
هذا يتجاوز تمامًا مشكلة ترميز اللغة العربية التي تحدث عند استيراد ملفات CSV
من تطبيق الجوال، لأن البيانات هنا تُرسل كنص Unicode مباشرة عبر الإنترنت.

طريقة التشغيل (مرة واحدة فقط):
    python seed_data.py
"""
import gspread
from google.oauth2.service_account import Credentials

from config import GOOGLE_SHEET_ID, GOOGLE_CREDENTIALS_FILE

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)
sheet = gc.open_by_key(GOOGLE_SHEET_ID)


def get_or_create_ws(title: str, rows: int = 200, cols: int = 10):
    try:
        return sheet.worksheet(title)
    except gspread.WorksheetNotFound:
        return sheet.add_worksheet(title=title, rows=rows, cols=cols)


def write_rows(ws, rows):
    ws.clear()
    ws.update(range_name="A1", values=rows, value_input_option="USER_ENTERED")


# ---------------- الإعدادات ----------------
settings_rows = [
    ["key", "value"],
    ["BOT_TOKEN", "8812627598:AAF-NrfhWZSAOQOgJCnJ71LXW8mMZI9xxFQ"],
    ["ADMIN_ID", "1679341347"],
    ["CHANNEL_ID", "@Syria_PayGate"],
    ["CHANNEL_LINK", "https://t.me/Syria_PayGate"],
    ["SUPPORT_LINK", "https://t.me/1679341347"],
    ["START_CUSTOMER_NUMBER", "1310"],
]
write_rows(get_or_create_ws("Settings"), settings_rows)
print("✅ Settings")

# ---------------- الخدمات ----------------
MENU_GAMES = "شحن ألعاب"
MENU_CARDS = "بطاقات شحن عالمية"
MENU_SUBS = "تفعيل الاشتراكات"

games = [
    "PUBG Mobile", "Free Fire", "Clash of Clans", "Call of Duty Mobile",
    "Delta Force", "FC Mobile", "EA Sports FC (FIFA Points)",
    "Mobile Legends: Bang Bang", "Genshin Impact", "Honkai: Star Rail",
    "Roblox", "Fortnite", "Valorant", "League of Legends: Wild Rift",
    "Brawl Stars", "8 Ball Pool", "Standoff 2", "Arena of Valor",
    "State of Survival", "Blood Strike", "Sausage Man", "Undawn",
    "Honor of Kings", "Zenless Zone Zero", "Rules of Survival",
    "Minecraft", "eFootball",
]
cards = ["Visa Card", "Steam Card", "Epic Games Card", "iTunes Card", "Razer Gold", "Amazon Gift Card"]
subs = [
    "ChatGPT Plus", "Claude Pro", "Gemini (Google AI Pro)", "Microsoft Copilot Pro",
    "Flow (Google AI)", "CapCut Pro", "Netflix Premium", "Spotify Premium",
    "YouTube Premium", "Canva Pro", "Perplexity Pro", "Shahid VIP",
]

services_rows = [["id", "menu_name", "name_ar", "type", "image", "extra_prompt", "active", "sort_order"]]
sid = 1
for i, g in enumerate(games, start=1):
    services_rows.append([f"g{sid}", MENU_GAMES, g, "GAME", "", "", "TRUE", i]); sid += 1
for i, c in enumerate(cards, start=1):
    services_rows.append([f"c{sid}", MENU_CARDS, c, "CARD", "", "", "TRUE", i]); sid += 1
for i, s in enumerate(subs, start=1):
    services_rows.append([f"s{sid}", MENU_SUBS, s, "SERVICE", "", "", "TRUE", i]); sid += 1

write_rows(get_or_create_ws("Services", rows=100, cols=8), services_rows)
print("✅ Services")


# ---------------- الأسعار (Options) ----------------
def disc(market_price, pct=0.05):
    return round(market_price * (1 - pct), 2)


game_tiers = {
    "PUBG Mobile": [("325 UC", 5), ("660 UC", 10), ("1800 UC", 25), ("3850 UC", 50), ("8100 UC", 100)],
    "Free Fire": [("720 Diamonds", 8), ("1450 Diamonds", 16), ("2180 Diamonds", 24), ("5000 Diamonds", 50)],
    "Clash of Clans": [("500 Gems", 5), ("1200 Gems", 10), ("2500 Gems", 20), ("6500 Gems", 50), ("14000 Gems", 100)],
    "Call of Duty Mobile": [("420 CP", 5), ("880 CP", 10), ("2000 CP", 20), ("5000 CP", 50), ("10800 CP", 100)],
    "Delta Force": [("680 Points", 10), ("1980 Points", 25), ("3280 Points", 40), ("6480 Points", 80)],
    "FC Mobile": [("500 FC Points", 5), ("1050 FC Points", 10), ("2200 FC Points", 20), ("5500 FC Points", 50)],
    "EA Sports FC (FIFA Points)": [("500 FIFA Points", 5), ("1050 FIFA Points", 10), ("2200 FIFA Points", 20), ("4600 FIFA Points", 40), ("12000 FIFA Points", 100)],
    "Mobile Legends: Bang Bang": [("172 Diamonds", 5), ("706 Diamonds", 20), ("2195 Diamonds", 60), ("706+706 Diamonds", 40)],
    "Genshin Impact": [("330 Genesis Crystals", 5), ("1090 Genesis Crystals", 15), ("2240 Genesis Crystals", 30), ("3880 Genesis Crystals", 50), ("8080 Genesis Crystals", 100)],
    "Honkai: Star Rail": [("330 Oneiric Shards", 5), ("1090 Oneiric Shards", 15), ("2240 Oneiric Shards", 30), ("3880 Oneiric Shards", 50)],
    "Roblox": [("400 Robux", 5), ("800 Robux", 10), ("1700 Robux", 20), ("4500 Robux", 50), ("10000 Robux", 100)],
    "Fortnite": [("1000 V-Bucks", 8), ("2800 V-Bucks", 20), ("5000 V-Bucks", 32), ("13500 V-Bucks", 80)],
    "Valorant": [("475 VP", 5), ("1000 VP", 10), ("2050 VP", 20), ("3650 VP", 35), ("5350 VP", 50)],
    "League of Legends: Wild Rift": [("425 Wild Cores", 5), ("880 Wild Cores", 10), ("1800 Wild Cores", 20), ("4500 Wild Cores", 50)],
    "Brawl Stars": [("170 Gems", 5), ("360 Gems", 10), ("950 Gems", 25), ("2000 Gems", 50)],
    "8 Ball Pool": [("450 Cash", 5), ("2000 Cash", 15), ("7000 Cash", 40), ("15000 Cash", 80)],
    "Standoff 2": [("500 Gold", 5), ("1200 Gold", 10), ("2500 Gold", 20), ("6000 Gold", 45)],
    "Arena of Valor": [("450 Vouchers", 5), ("960 Vouchers", 10), ("2000 Vouchers", 20), ("5000 Vouchers", 45)],
    "State of Survival": [("450 Diamonds", 5), ("980 Diamonds", 10), ("2100 Diamonds", 20), ("5500 Diamonds", 50)],
    "Blood Strike": [("400 Gold", 5), ("900 Gold", 10), ("2000 Gold", 20), ("5000 Gold", 45)],
    "Sausage Man": [("400 Sausage Coins", 5), ("900 Sausage Coins", 10), ("2000 Sausage Coins", 20)],
    "Undawn": [("400 Coins", 5), ("900 Coins", 10), ("2000 Coins", 20), ("5000 Coins", 45)],
    "Honor of Kings": [("450 Tokens", 5), ("960 Tokens", 10), ("2000 Tokens", 20), ("5000 Tokens", 45)],
    "Zenless Zone Zero": [("330 Polychrome", 5), ("1090 Polychrome", 15), ("2240 Polychrome", 30), ("3880 Polychrome", 50)],
    "Rules of Survival": [("450 Diamonds", 5), ("980 Diamonds", 10), ("2100 Diamonds", 20), ("5500 Diamonds", 50)],
    "Minecraft": [("1720 Minecoins", 10), ("3500 Minecoins", 20), ("8800 Minecoins", 45)],
    "eFootball": [("500 Coins", 5), ("1050 Coins", 10), ("2200 Coins", 20), ("5500 Coins", 45)],
}

options_rows = [["id", "service_id", "label", "price", "active", "sort_order"]]
oid = 1
sid_map_games = {g: f"g{i+1}" for i, g in enumerate(games)}
for g in games:
    service_id = sid_map_games[g]
    order = 1
    for label, market_price in game_tiers.get(g, []):
        price = disc(market_price)
        if price < 4:
            continue
        options_rows.append([f"o{oid}", service_id, label, price, "TRUE", order])
        oid += 1
        order += 1

card_values = [10, 25, 50, 100]
sid_map_cards = {c: f"c{27+i+1}" for i, c in enumerate(cards)}
for c in cards:
    service_id = sid_map_cards[c]
    for order, v in enumerate(card_values, start=1):
        price = round(v + 0.5, 2)
        options_rows.append([f"o{oid}", service_id, f"بطاقة {v}$", price, "TRUE", order])
        oid += 1

sub_prices = {
    "ChatGPT Plus": 20.00, "Claude Pro": 20.00, "Gemini (Google AI Pro)": 19.99,
    "Microsoft Copilot Pro": 19.99, "Flow (Google AI)": 19.99, "CapCut Pro": 9.99,
    "Netflix Premium": 15.00, "Spotify Premium": 11.99, "YouTube Premium": 13.99,
    "Canva Pro": 12.99, "Perplexity Pro": 20.00, "Shahid VIP": 9.99,
}
sid_map_subs = {s: f"s{27+6+i+1}" for i, s in enumerate(subs)}
for s in subs:
    service_id = sid_map_subs[s]
    price = round(sub_prices[s] + 1.5, 2)
    options_rows.append([f"o{oid}", service_id, "اشتراك شهر واحد", price, "TRUE", 1])
    oid += 1

write_rows(get_or_create_ws("Options", rows=200, cols=6), options_rows)
print(f"✅ Options ({len(options_rows) - 1} rows)")

# ---------------- طرق الدفع ----------------
pm_rows = [
    ["id", "name_ar", "wallet_number", "active", "sort_order"],
    ["1", "Syriatel Cash سيرياتيل كاش", "ضع رقم محفظتك هنا", "TRUE", "1"],
    ["2", "MTN Cash أم تي إن كاش", "ضع رقم محفظتك هنا", "TRUE", "2"],
]
write_rows(get_or_create_ws("PaymentMethods", rows=20, cols=5), pm_rows)
print("✅ PaymentMethods (⚠️ عدّل رقم المحفظة يدويًا داخل الشيت)")

# ---------------- أكواد الخصم ----------------
dc_rows = [
    ["code", "percent", "max_uses", "used_count", "active"],
    ["WELCOME10", "10", "0", "0", "TRUE"],
]
write_rows(get_or_create_ws("DiscountCodes", rows=50, cols=5), dc_rows)
print("✅ DiscountCodes")

# ---------------- تبويبات فارغة يملؤها البوت لاحقًا (لا تُمسح إن وُجدت بيانات) ----------------
customers_ws = get_or_create_ws("Customers", rows=1000, cols=3)
if not customers_ws.get_all_values():
    write_rows(customers_ws, [["user_id", "customer_number", "first_seen"]])
print("✅ Customers")

orders_ws = get_or_create_ws("Orders", rows=2000, cols=14)
if not orders_ws.get_all_values():
    write_rows(orders_ws, [[
        "order_id", "timestamp", "user_id", "username", "full_name", "service_name",
        "option_label", "base_price", "discount_code", "final_price",
        "payment_method", "proof", "extra_info", "status",
    ]])
print("✅ Orders")

print("\n🎉 خلص! كل التبويبات جاهزة بالشيت. شغّلي الآن: python bot.py")
