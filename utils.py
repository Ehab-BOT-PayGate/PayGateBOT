def format_price(value) -> str:
    """يحوّل أي قيمة سعر (رقم أو نص) إلى نص نظيف: 27 تبقى '27'، و4.75 تبقى '4.75'.
    ولا تظهر أبدًا كـ '27.0'. يُستخدم في كل مكان يُعرض فيه السعر للزبون."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return str(value)
    if num == int(num):
        return str(int(num))
    text = f"{num:.2f}".rstrip("0").rstrip(".")
    return text
