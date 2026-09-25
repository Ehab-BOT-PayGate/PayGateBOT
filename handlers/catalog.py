from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext

import sheets_service as db
import keyboards as kb
from states import OrderFlow
from utils import show_screen

router = Router()


@router.callback_query(F.data.startswith("menu:"))
async def cb_choose_menu(callback: CallbackQuery, state: FSMContext):
    menu_name = callback.data.split(":", 1)[1]
    services = db.get_services_by_menu(menu_name)
    await state.update_data(menu_name=menu_name, svc_page=0)
    await state.set_state(OrderFlow.choosing_service)

    if not services:
        await callback.answer("لا توجد خدمات متاحة حاليًا في هذا القسم", show_alert=True)
        return

    extra_note = ""
    if "ألعاب" in menu_name:
        extra_note = "\n\n⚡ الشحن يتم عن طريق الـ ID فقط.\n🕐 مدة التنفيذ: من 1 إلى 10 دقائق كحد أقصى."
    elif "بطاقات" in menu_name:
        extra_note = "\n\n✅ جميع البطاقات تعمل في سوريا ومجربة، وأي خلل فيها راجع الدعم لتستعيد أموالك فورًا."
    elif "اشتراك" in menu_name:
        extra_note = (
            "\n\n🤖 تفعيل كافة أدوات الذكاء الصناعي واشتراكات التطبيقات كافة.\n"
            "في حال لم يكن طلبك مدرجًا بالقائمة، تواصل مع الدعم.\n"
            "✅ كافة الاشتراكات مكفولة تمامًا."
        )

    await show_screen(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        state=state,
        text=f"اختر من قائمة {menu_name}:{extra_note}",
        reply_markup=kb.kb_services(services),
    )
    await callback.answer()


@router.callback_query(F.data == "backservices")
async def cb_back_services(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    menu_name = data.get("menu_name")
    services = db.get_services_by_menu(menu_name)
    await state.set_state(OrderFlow.choosing_service)
    await state.update_data(svc_page=0)
    await show_screen(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        state=state,
        text=f"اختر من قائمة {menu_name}:",
        reply_markup=kb.kb_services(services),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("svcpage:"))
async def cb_services_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    menu_name = data.get("menu_name")
    services = db.get_services_by_menu(menu_name)
    await state.update_data(svc_page=page)
    await show_screen(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        state=state,
        text=f"اختر من قائمة {menu_name}:",
        reply_markup=kb.kb_services(services, page=page),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("service:"))
async def cb_choose_service(callback: CallbackQuery, state: FSMContext):
    service_id = callback.data.split(":", 1)[1]
    service = db.get_service_by_id(service_id)
    if not service:
        await callback.answer("هذه الخدمة غير متاحة حاليًا", show_alert=True)
        return

    options = db.get_options(service_id)
    await state.update_data(
        service_id=service_id,
        service_name=service.get("name_ar"),
        service_type=service.get("type"),
        service_extra_prompt=service.get("extra_prompt", ""),
        opt_page=0,
    )
    await state.set_state(OrderFlow.choosing_option)

    s_type = service.get("type")
    if s_type == "GAME":
        intro = f"🎮 {service.get('name_ar')}\nاختر الكمية المطلوبة:"
    elif s_type == "CARD":
        intro = f"💳 {service.get('name_ar')}\nاختر الفئة المطلوبة:"
    else:
        intro = f"اختر الخيار المطلوب لخدمة {service.get('name_ar')}:"

    image = service.get("image") or None
    await show_screen(
        bot=callback.bot,
        chat_id=callback.message.chat.id,
        state=state,
        text=intro,
        photo=image,
        reply_markup=kb.kb_options(options, service_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("option:"))
async def cb_choose_option(callback: CallbackQuery, state: FSMContext):
    option_id = callback.data.split(":", 1)[1]
    option = db.get_option_by_id(option_id)
    if not option:
        await callback.answer("هذا الخيار غير متاح حاليًا", show_alert=True)
        return

    await state.update_data(
        option_id=option_id,
        option_label=option.get("label"),
        base_price=option.get("price"),
        final_price=option.get("price"),
        discount_code="",
    )
    await state.set_state(OrderFlow.asking_discount_choice)

    text = (
        f"الخيار المختار: {option.get('label')}\n"
        f"السعر: {option.get('price')}\n\n"
        "هل لديك كود خصم؟"
    )
    await show_screen(
        bot=callback.bot, chat_id=callback.message.chat.id, state=state,
        text=text, reply_markup=kb.kb_discount_choice(),
    )
    await callback.answer()


@router.callback_query(F.data == "discount:no")
async def cb_discount_no(callback: CallbackQuery, state: FSMContext):
    await show_payment_methods(callback.bot, callback.message.chat.id, state)
    await callback.answer()


@router.callback_query(F.data == "discount:yes")
async def cb_discount_yes(callback: CallbackQuery, state: FSMContext):
    await state.set_state(OrderFlow.entering_discount_code)
    await show_screen(
        bot=callback.bot, chat_id=callback.message.chat.id, state=state,
        text="✍️ أرسل كود الخصم الآن:",
    )
    await callback.answer()


@router.message(OrderFlow.entering_discount_code)
async def msg_discount_code(message: Message, state: FSMContext):
    code_row = db.validate_discount(message.text)
    try:
        await message.delete()
    except Exception:
        pass

    data = await state.get_data()
    base_price = data.get("base_price")

    if not code_row:
        await show_screen(
            bot=message.bot, chat_id=message.chat.id, state=state,
            text="❌ الكود غير صحيح أو منتهي.\nأرسل كودًا آخر، أو اضغط رجوع.",
            reply_markup=kb.kb_discount_choice(),
        )
        await state.set_state(OrderFlow.asking_discount_choice)
        return

    percent = float(code_row.get("percent") or 0)
    try:
        base_num = float(str(base_price).replace(",", ""))
        final_price = round(base_num - (base_num * percent / 100), 2)
    except ValueError:
        final_price = base_price

    await state.update_data(discount_code=code_row.get("code"), final_price=final_price)
    db.increment_discount_usage(code_row.get("code"))

    await show_payment_methods(
        message.bot, message.chat.id, state,
        note=f"✅ تم تطبيق الخصم! السعر بعد الخصم: {final_price}",
    )


async def show_payment_methods(bot, chat_id, state: FSMContext, note: str = ""):
    methods = db.get_payment_methods()
    await state.set_state(OrderFlow.choosing_payment)
    await state.update_data(pay_page=0)
    text = (note + "\n\n" if note else "") + "اختر طريقة الدفع:"
    await show_screen(
        bot=bot, chat_id=chat_id, state=state,
        text=text, reply_markup=kb.kb_payment_methods(methods),
    )


@router.callback_query(F.data.startswith("paypage:"))
async def cb_payment_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split(":", 1)[1])
    methods = db.get_payment_methods()
    await state.update_data(pay_page=page)
    await show_screen(
        bot=callback.bot, chat_id=callback.message.chat.id, state=state,
        text="اختر طريقة الدفع:", reply_markup=kb.kb_payment_methods(methods, page=page),
    )
    await callback.answer()


@router.callback_query(F.data == "backoptions")
async def cb_back_options(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    service_id = data.get("service_id")
    options = db.get_options(service_id)
    await state.set_state(OrderFlow.choosing_option)
    await state.update_data(opt_page=0)
    await show_screen(
        bot=callback.bot, chat_id=callback.message.chat.id, state=state,
        text=f"اختر الخيار المطلوب لخدمة {data.get('service_name')}:",
        reply_markup=kb.kb_options(options, service_id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("optpage:"))
async def cb_options_page(callback: CallbackQuery, state: FSMContext):
    page = int(callback.data.split(":", 1)[1])
    data = await state.get_data()
    service_id = data.get("service_id")
    options = db.get_options(service_id)
    await state.update_data(opt_page=page)
    await show_screen(
        bot=callback.bot, chat_id=callback.message.chat.id, state=state,
        text=f"اختر الخيار المطلوب لخدمة {data.get('service_name')}:",
        reply_markup=kb.kb_options(options, service_id, page=page),
    )
    await callback.answer()
