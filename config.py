"""
إعدادات الإقلاع الأساسية فقط (لا تُلمس بعد أول تشغيل).
كل الإعدادات المهمة الأخرى (التوكن، معرف المدير، القناة، رابط الدعم)
موجودة في شيت "Settings" داخل ملف Google Sheet، وتُقرأ تلقائيًا عند التشغيل.
"""
import os
from dotenv import load_dotenv

load_dotenv()

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json").strip()

if not GOOGLE_SHEET_ID:
    raise RuntimeError(
        "GOOGLE_SHEET_ID غير موجود في ملف .env — انسخ .env.example إلى .env وعبّئه."
    )
