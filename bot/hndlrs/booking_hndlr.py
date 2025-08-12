# import asyncio
# import os
# import re
# from datetime import datetime, date, timedelta
# from typing import Optional
#
# import pytz
# from aiogram import Router, Bot, Dispatcher, F
# from aiogram.filters import StateFilter
# from aiogram.exceptions import TelegramBadRequest
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import State, StatesGroup
# from aiogram.types import (
#     Message,
#     CallbackQuery,
#     InlineKeyboardMarkup,
#     InlineKeyboardButton,
# )
# from dotenv import load_dotenv
# from yookassa import Payment, Refund
#
# from bot.config import (
#     create_payment,
#     rubitime,
#     check_payment_status,
#     create_user_keyboard,
#     create_back_keyboard,
# )
# from models.models import (
#     get_active_tariffs,
#     create_booking,
#     User,
#     get_user_by_telegram_id,
#     get_promocode_by_name,
#     Promocode,
#     format_booking_notification,
#     Tariff,
# )
#
# from utils.logger import get_logger
#
# # Тихая настройка логгера для модуля
# load_dotenv()
#
# router = Router()
# MOSCOW_TZ = pytz.timezone("Europe/Moscow")
# ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
# logger = get_logger(__name__)
#
#
# class Booking(StatesGroup):
#     """Состояния для процесса бронирования."""
#
#     SELECT_TARIFF = State()
#     ENTER_DATE = State()
#     ENTER_TIME = State()
#     ENTER_DURATION = State()
#     ENTER_PROMOCODE = State()
#     PAYMENT = State()
#     STATUS_PAYMENT = State()
#
#
# def format_payment_notification(user, booking_data, status="SUCCESS"):
#     """Форматирует красивое уведомление об оплате для админа.
#
#     Args:
#         user: Объект пользователя.
#         booking_data: Данные бронирования (словарь с tariff_name, visit_date, amount, payment_id).
#         status: Статус платежа ("SUCCESS", "FAILED", "PENDING", "CANCELLED").
#
#     Returns:
#         str: Отформатированное сообщение.
#     """
#     status_emojis = {
#         "SUCCESS": "✅",
#         "FAILED": "❌",
#         "PENDING": "⏳",
#         "CANCELLED": "🚫",
#     }
#
#     status_emoji = status_emojis.get(status, "❓")
#     status_texts = {
#         "SUCCESS": "УСПЕШНО ОПЛАЧЕНО",
#         "FAILED": "ОШИБКА ОПЛАТЫ",
#         "PENDING": "ОЖИДАЕТ ОПЛАТЫ",
#         "CANCELLED": "ОПЛАТА ОТМЕНЕНА",
#     }
#     status_text = status_texts.get(status, "НЕИЗВЕСТНЫЙ СТАТУС")
#
#     message = f"""💳 <b>{status_text}</b> {status_emoji}
#
# 👤 <b>Клиент:</b> {user.full_name or 'Не указано'}
# 📞 <b>Телефон:</b> {user.phone or 'Не указано'}
#
# 💰 <b>Детали платежа:</b>
# ├ <b>Сумма:</b> {booking_data.get('amount', 0):.2f} ₽
# ├ <b>Тариф:</b> {booking_data.get('tariff_name', 'Неизвестно')}
# ├ <b>Дата брони:</b> {booking_data.get('visit_date', '').strftime('%d.%m.%Y') if booking_data.get('visit_date') else 'Неизвестно'}
# └ <b>Payment ID:</b> <code>{booking_data.get('payment_id', 'Неизвестно')}</code>
#
# ⏰ <i>Время: {datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M:%S')}</i>"""
#
#     return message.strip()
#
#
# def format_user_booking_notification(user, booking_data, confirmed: bool) -> str:
#     """Форматирует красивое уведомление о бронировании для пользователя.
#
#     Args:
#         user: Объект пользователя.
#         booking_data: Данные бронирования (словарь с tariff_name, tariff_purpose, visit_date, visit_time, duration, amount, discount, promocode_name).
#         confirmed: Флаг подтверждения брони (True для "Опенспейс", False для "Переговорной").
#
#     Returns:
#         str: Отформатированное сообщение.
#     """
#     tariff_emojis = {
#         "meeting": "🤝",
#         "workspace": "💼",
#         "event": "🎉",
#         "office": "🏢",
#         "coworking": "💻",
#     }
#
#     purpose = booking_data.get("tariff_purpose", "").lower()
#     tariff_emoji = tariff_emojis.get(purpose, "📋")
#     visit_date = booking_data.get("visit_date")
#     visit_time = booking_data.get("visit_time")
#
#     if visit_time:
#         datetime_str = (
#             f"{visit_date.strftime('%d.%m.%Y')} в {visit_time.strftime('%H:%M')}"
#         )
#     else:
#         datetime_str = f"{visit_date.strftime('%d.%m.%Y')} (весь день)"
#
#     discount_info = ""
#     if booking_data.get("discount", 0) > 0:
#         promocode_name = booking_data.get("promocode_name", "Неизвестный")
#         discount = booking_data.get("discount", 0)
#         discount_info = (
#             f"\n💰 <b>Скидка:</b> {discount}% (промокод: <code>{promocode_name}</code>)"
#         )
#
#     duration_info = ""
#     if booking_data.get("duration"):
#         duration_info = f"\n⏱ <b>Длительность:</b> {booking_data['duration']} час(ов)"
#
#     status_text = "Бронь подтверждена ✅" if confirmed else "Ожидайте подтверждения ⏳"
#     status_instruction = (
#         "" if confirmed else "\n📩 Мы свяжемся с вами для подтверждения брони."
#     )
#
#     message = f"""🎉 <b>Ваша бронь создана!</b> {tariff_emoji}
#
# 📋 <b>Детали брони:</b>
# ├ <b>Тариф:</b> {booking_data.get('tariff_name', 'Неизвестно')}
# ├ <b>Дата и время:</b> {datetime_str}{duration_info}
# └ <b>Сумма:</b> {booking_data.get('amount', 0):.2f} ₽{discount_info}
#
# 📌 <b>Статус:</b> {status_text}{status_instruction}
#
# ⏰ <i>Время создания: {datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y %H:%M:%S')}</i>"""
#
#     return message.strip()
#
#
# def create_tariff_keyboard(telegram_id: int) -> InlineKeyboardMarkup:
#     """
#     Создаёт инлайн-клавиатуру с активными тарифами, исключая 'Тестовый день' для пользователей с успешными бронированиями.
#
#     Args:
#         telegram_id: Telegram ID пользователя.
#
#     Returns:
#         InlineKeyboardMarkup: Клавиатура с тарифами и кнопкой отмены.
#     """
#     try:
#         user = get_user_by_telegram_id(telegram_id)
#         successful_bookings = user.successful_bookings
#         tariffs = get_active_tariffs()
#         buttons = []
#         for tariff in tariffs:
#             if tariff.service_id == 47890 and successful_bookings > 0:
#                 continue
#             buttons.append(
#                 [
#                     InlineKeyboardButton(
#                         text=f"{tariff.name} ({tariff.price} {'₽/ч' if tariff.purpose == 'Переговорная' else '₽'})",
#                         callback_data=f"tariff_{tariff.id}",
#                     )
#                 ]
#             )
#         buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
#         keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
#         logger.debug("Создана клавиатура с тарифами")
#         return keyboard
#     except Exception as e:
#         logger.error(f"Ошибка при создании клавиатуры тарифов: {str(e)}")
#         return InlineKeyboardMarkup(
#             inline_keyboard=[
#                 [InlineKeyboardButton(text="Отмена", callback_data="cancel")]
#             ]
#         )
#
#
# def create_date_keyboard() -> InlineKeyboardMarkup:
#     """
#     Создаёт инлайн-клавиатуру с датами (сегодня + 7 дней).
#
#     Returns:
#         InlineKeyboardMarkup: Клавиатура с датами и кнопкой отмены.
#     """
#     today = datetime.now(MOSCOW_TZ).date()
#     buttons = []
#     for i in range(8):  # Сегодня + 7 дней
#         date = today + timedelta(days=i)
#         buttons.append(
#             [
#                 InlineKeyboardButton(
#                     text=date.strftime("%d.%m.%Y"),
#                     callback_data=f"date_{date.strftime('%Y-%m-%d')}",
#                 )
#             ]
#         )
#     buttons.append([InlineKeyboardButton(text="Отмена", callback_data="cancel")])
#     keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
#     logger.debug("Создана клавиатура с датами")
#     return keyboard
#
#
# def create_payment_keyboard(
#     confirmation_url: str, amount: float
# ) -> InlineKeyboardMarkup:
#     """
#     Создаёт клавиатуру с кнопкой оплаты и отмены.
#
#     Args:
#         confirmation_url: URL для оплаты через YooKassa.
#         amount: Сумма платежа.
#
#     Returns:
#         InlineKeyboardMarkup: Клавиатура с кнопками оплаты и отмены.
#     """
#     logger.debug(f"Создание клавиатуры для оплаты, сумма: {amount}")
#     keyboard = InlineKeyboardMarkup(
#         inline_keyboard=[
#             [
#                 InlineKeyboardButton(
#                     text=f"Оплатить {amount:.2f} ₽", url=confirmation_url
#                 ),
#                 InlineKeyboardButton(text="Отмена", callback_data="cancel_payment"),
#             ]
#         ]
#     )
#     return keyboard
#
#
# @router.callback_query(F.data == "booking")
# async def start_booking(
#     callback_query: CallbackQuery, state: FSMContext, bot: Bot
# ) -> None:
#     """
#     Обработчик нажатия кнопки 'Забронировать'. Показывает активные тарифы.
#
#     Args:
#         callback_query: Callback-запрос от кнопки.
#         state: Контекст состояния FSM.
#         bot: Экземпляр бота.
#     """
#     tariffs = get_active_tariffs()
#     if not tariffs:
#         await callback_query.message.edit_text(
#             # await callback_query.message.answer(
#             "Нет доступных тарифов для бронирования.",
#             reply_markup=create_back_keyboard(),
#         )
#         logger.info(
#             f"Пользователь {callback_query.from_user.id} попытался забронировать, "
#             f"но нет активных тарифов"
#         )
#         # try:
#         #     await callback_query.message.delete()
#         # except TelegramBadRequest as e:
#         #     logger.warning(
#         #         f"Не удалось удалить сообщение для пользователя {callback_query.from_user.id}: {str(e)}"
#         #     )
#         await callback_query.answer()
#         return
#
#     await state.set_state(Booking.SELECT_TARIFF)
#     await callback_query.message.edit_text(
#         # await callback_query.message.answer(
#         "Выберите тариф:",
#         reply_markup=create_tariff_keyboard(callback_query.from_user.id),
#     )
#     logger.info(
#         f"Пользователь {callback_query.from_user.id} начал процесс бронирования"
#     )
#     # try:
#     #     await callback_query.message.delete()
#     # except TelegramBadRequest as e:
#     #     logger.warning(
#     #         f"Не удалось удалить сообщение для пользователя {callback_query.from_user.id}: {str(e)}"
#     #     )
#     await callback_query.answer()
#
#
# @router.callback_query(Booking.SELECT_TARIFF, F.data.startswith("tariff_"))
# async def process_tariff_selection(
#     callback_query: CallbackQuery, state: FSMContext
# ) -> None:
#     """
#     Обработка выбора тарифа. Показывает клавиатуру с датами.
#
#     Args:
#         callback_query: Callback-запрос с выбранным тарифом.
#         state: Контекст состояния FSM.
#     """
#     tariff_id = int(callback_query.data.split("_")[1])
#     tariffs = get_active_tariffs()
#     tariff = next((t for t in tariffs if t.id == tariff_id), None)
#     if not tariff:
#         await callback_query.message.edit_text(
#             text="Тариф не найден. Попробуйте снова.",
#             reply_markup=create_tariff_keyboard(callback_query.from_user.id),
#         )
#         logger.warning(
#             f"Пользователь {callback_query.from_user.id} выбрал несуществующий тариф: {tariff_id}"
#         )
#         await callback_query.answer()
#         return
#
#     await state.update_data(
#         tariff_id=tariff.id,
#         tariff_name=tariff.name,
#         tariff_purpose=tariff.purpose.lower(),
#         tariff_service_id=tariff.service_id,
#         tariff_price=tariff.price,
#     )
#     await state.set_state(Booking.ENTER_DATE)
#     await callback_query.message.edit_text(
#         text=f"Вы выбрали тариф: {tariff.name}\nВыберите дату визита:",
#         reply_markup=create_date_keyboard(),
#     )
#     logger.info(
#         f"Пользователь {callback_query.from_user.id} выбрал тариф {tariff.name}"
#     )
#     await callback_query.answer()
#
#
# @router.callback_query(Booking.ENTER_DATE, F.data.startswith("date_"))
# async def process_date_selection(
#     callback_query: CallbackQuery, state: FSMContext
# ) -> None:
#     """
#     Обработка выбора даты через инлайн-клавиатуру.
#
#     Args:
#         callback_query: Callback-запрос с выбранной датой.
#         state: Контекст состояния FSM.
#     """
#     try:
#         visit_date = datetime.strptime(
#             callback_query.data.split("_")[1], "%Y-%m-%d"
#         ).date()
#         today = datetime.now(MOSCOW_TZ).date()
#         if visit_date < today:
#             await callback_query.message.edit_text(
#                 text="Дата не может быть в прошлом. Выберите снова:",
#                 reply_markup=create_date_keyboard(),
#             )
#             logger.warning(
#                 f"Пользователь {callback_query.from_user.id} выбрал прошедшую дату: {visit_date}"
#             )
#             await callback_query.answer()
#             return
#
#         data = await state.get_data()
#         tariff_purpose = data["tariff_purpose"]
#         tariff_name = data["tariff_name"]
#         await state.update_data(visit_date=visit_date)
#         if tariff_purpose == "переговорная":
#             await state.set_state(Booking.ENTER_TIME)
#             await callback_query.message.edit_text(
#                 text="Введите время визита (чч:мм, например, 14:30):",
#                 reply_markup=create_back_keyboard(),
#             )
#             logger.info(
#                 f"Пользователь {callback_query.from_user.id} выбрал дату {visit_date} для тарифа {tariff_name} через клавиатуру"
#             )
#         else:
#             await state.set_state(Booking.ENTER_PROMOCODE)
#             await callback_query.message.edit_text(
#                 text="Введите промокод (или /skip для пропуска):",
#                 reply_markup=create_back_keyboard(),
#             )
#             logger.info(
#                 f"Пользователь {callback_query.from_user.id} выбрал дату {visit_date} для тарифа {tariff_name} через клавиатуру"
#             )
#         await callback_query.answer()
#     except ValueError as e:
#         await callback_query.message.edit_text(
#             text="Ошибка при обработке даты. Попробуйте снова:",
#             reply_markup=create_date_keyboard(),
#         )
#         logger.error(
#             f"Ошибка при обработке даты для пользователя {callback_query.from_user.id}: {str(e)}"
#         )
#         await callback_query.answer()
#
#
# @router.message(Booking.ENTER_DATE)
# async def process_date(message: Message, state: FSMContext) -> None:
#     """
#     Обработка введённой даты текстом. Проверяет формат и запрашивает время для 'Переговорной' или промокод.
#
#     Args:
#         message: Входящее сообщение с датой.
#         state: Контекст состояния FSM.
#     """
#     try:
#         visit_date = datetime.strptime(message.text, "%Y-%m-%d").date()
#         today = datetime.now(MOSCOW_TZ).date()
#         if visit_date < today:
#             await message.answer(
#                 text="Дата не может быть в прошлом. Введите снова (гггг-мм-дд) или выберите из календаря:",
#                 reply_markup=create_date_keyboard(),
#             )
#             logger.warning(
#                 f"Пользователь {message.from_user.id} ввёл прошедшую дату: {message.text}"
#             )
#             return
#     except ValueError:
#         await message.answer(
#             text="Неверный формат даты. Введите в формате гггг-мм-дд (например, 2025-07-25) или выберите из календаря:",
#             reply_markup=create_date_keyboard(),
#         )
#         logger.warning(
#             f"Пользователь {message.from_user.id} ввёл неверный формат даты: {message.text}"
#         )
#         return
#
#     data = await state.get_data()
#     tariff_purpose = data["tariff_purpose"]
#     tariff_name = data["tariff_name"]
#     await state.update_data(visit_date=visit_date)
#     if tariff_purpose == "переговорная":
#         await state.set_state(Booking.ENTER_TIME)
#         await message.answer(
#             text="Введите время визита (чч:мм, например, 14:30):",
#             reply_markup=create_back_keyboard(),
#         )
#         logger.info(
#             f"Пользователь {message.from_user.id} ввёл дату {visit_date} для тарифа {tariff_name} текстом"
#         )
#     else:
#         await state.set_state(Booking.ENTER_PROMOCODE)
#         await message.answer(
#             text="Введите промокод (или /skip для пропуска):",
#             reply_markup=create_back_keyboard(),
#         )
#         logger.info(
#             f"Пользователь {message.from_user.id} ввёл дату {visit_date} для тарифа {tariff_name} текстом"
#         )
#
#
# @router.message(Booking.ENTER_TIME)
# async def process_time(message: Message, state: FSMContext) -> None:
#     """
#     Обработка введённого времени для 'Переговорной'. Запрашивает продолжительность.
#
#     Args:
#         message: Входящее сообщение с временем.
#         state: Контекст состояния FSM.
#     """
#     try:
#         visit_time = datetime.strptime(message.text, "%H:%M").time()
#     except ValueError:
#         await message.answer(
#             "Неверный формат времени. Введите в формате чч:мм (например, 14:30):",
#             reply_markup=create_back_keyboard(),
#         )
#         logger.warning(
#             f"Пользователь {message.from_user.id} ввёл неверный формат времени: {message.text}"
#         )
#         return
#
#     await state.update_data(visit_time=visit_time)
#     await state.set_state(Booking.ENTER_DURATION)
#     await message.answer(
#         "Введите продолжительность бронирования в часах (например, 2):",
#         reply_markup=create_back_keyboard(),
#     )
#     logger.info(f"Пользователь {message.from_user.id} ввёл время {visit_time}")
#
#
# @router.message(Booking.ENTER_DURATION)
# async def process_duration(message: Message, state: FSMContext) -> None:
#     """
#     Обработка введённой продолжительности. Запрашивает промокод.
#
#     Args:
#         message: Входящее сообщение с продолжительностью.
#         state: Контекст состояния FSM.
#     """
#     try:
#         duration = int(message.text)
#         if duration <= 0:
#             await message.answer(
#                 "Продолжительность должна быть больше 0. Введите снова:",
#                 reply_markup=create_back_keyboard(),
#             )
#             logger.warning(
#                 f"Пользователь {message.from_user.id} ввёл некорректную продолжительность: {message.text}"
#             )
#             return
#     except ValueError:
#         await message.answer(
#             "Введите целое число часов (например, 2):",
#             reply_markup=create_back_keyboard(),
#         )
#         logger.warning(
#             f"Пользователь {message.from_user.id} ввёл неверный формат продолжительности: {message.text}"
#         )
#         return
#
#     await state.update_data(duration=duration)
#     await state.set_state(Booking.ENTER_PROMOCODE)
#     await message.answer(
#         "Введите промокод (или /skip для пропуска):",
#         reply_markup=create_back_keyboard(),
#     )
#     logger.info(
#         f"Пользователь {message.from_user.id} ввёл продолжительность {duration} ч"
#     )
#
#
# @router.message(Booking.ENTER_PROMOCODE)
# async def process_promocode(message: Message, state: FSMContext) -> None:
#     """
#     Обработка введённого промокода или его пропуска. Создаёт платёж или бронь в зависимости от тарифа.
#
#     Args:
#         message: Входящее сообщение с промокодом.
#         state: Контекст состояния FSM.
#     """
#     data = await state.get_data()
#     tariff_purpose = data["tariff_purpose"]
#     tariff_name = data["tariff_name"]
#     tariff_price = data["tariff_price"]
#     promocode_id: Optional[int] = None
#     promocode_name: Optional[str] = None
#     discount: float = 0
#
#     if message.text != "/skip":
#         promocode_name = message.text.strip()
#         promocode = get_promocode_by_name(promocode_name)
#
#         if not promocode:
#             await message.answer(
#                 "Промокод не найден или неактивен. Введите другой или используйте /skip для продолжения.",
#                 reply_markup=create_back_keyboard(),
#             )
#             logger.warning(
#                 f"Пользователь {message.from_user.id} ввёл несуществующий или неактивный промокод: {promocode_name}"
#             )
#             return
#
#         if promocode.expiration_date and promocode.expiration_date < datetime.now(
#             MOSCOW_TZ
#         ):
#             await message.answer(
#                 "Срок действия промокода истёк. Введите другой или используйте /skip для продолжения.",
#                 reply_markup=create_back_keyboard(),
#             )
#             logger.warning(
#                 f"Пользователь {message.from_user.id} ввёл просроченный промокод: {promocode_name}"
#             )
#             return
#
#         if promocode.usage_quantity <= 0:
#             await message.answer(
#                 "Промокод исчерпал лимит использований. Введите другой или используйте /skip для продолжения.",
#                 reply_markup=create_back_keyboard(),
#             )
#             logger.warning(
#                 f"Пользователь {message.from_user.id} ввёл исчерпанный промокод: {promocode_name}"
#             )
#             return
#
#         discount = promocode.discount
#         promocode_id = promocode.id
#         await message.answer(
#             f"Промокод '{promocode_name}' применён! Скидка: {discount}%",
#             reply_markup=create_back_keyboard(),
#         )
#         logger.info(
#             f"Пользователь {message.from_user.id} применил промокод {promocode_name} со скидкой {discount}%"
#         )
#     else:
#         logger.info(f"Пользователь {message.from_user.id} пропустил промокод")
#
#     duration = data.get("duration")
#     if tariff_purpose == "переговорная" and duration:
#         amount = tariff_price * duration
#         if duration >= 3:
#             additional_discount = 10
#             total_discount = min(100, discount + additional_discount)
#             amount *= 1 - total_discount / 100
#             logger.info(
#                 f"Применена скидка {total_discount}% (промокод: {discount}%, "
#                 f"дополнительно: {additional_discount}%) для бронирования на {duration} ч, "
#                 f"итоговая сумма: {amount:.2f}"
#             )
#         else:
#             amount *= 1 - discount / 100
#             logger.info(
#                 f"Применена скидка {discount}% для бронирования на {duration} ч, "
#                 f"итоговая сумма: {amount:.2f}"
#             )
#     else:
#         amount = tariff_price * (1 - discount / 100)
#         logger.info(
#             f"Применена скидка {discount}% для тарифа {tariff_name}, "
#             f"итоговая сумма: {amount:.2f}"
#         )
#
#     description = f"Бронь: {tariff_name}, дата: {data['visit_date']}"
#     if tariff_purpose == "переговорная":
#         description += f", время: {data.get('visit_time')}, длительность: {duration} ч, сумма: {amount:.2f} ₽"
#     else:
#         description += f", сумма: {amount:.2f} ₽"
#     if promocode_name:
#         description += f", промокод: {promocode_name} ({discount}%)"
#
#     await state.update_data(
#         amount=amount,
#         promocode_id=promocode_id,
#         promocode_name=promocode_name,
#         discount=discount,
#     )
#
#     if tariff_purpose == "переговорная":
#         await handle_free_booking(message, state, bot=message.bot, paid=False)
#     elif amount == 0:
#         await handle_free_booking(message, state, bot=message.bot, paid=True)
#     else:
#         payment_id, confirmation_url = await create_payment(description, amount)
#         if not payment_id or not confirmation_url:
#             await message.answer(
#                 "Ошибка при создании платежа. Попробуйте позже.",
#                 reply_markup=create_user_keyboard(),
#             )
#             logger.error(
#                 f"Не удалось создать платёж для пользователя {message.from_user.id}"
#             )
#             await state.clear()
#             return
#
#         await state.update_data(payment_id=payment_id)
#         payment_message = await message.answer(
#             f"Оплатите бронирование:\n{description}",
#             reply_markup=create_payment_keyboard(confirmation_url, amount),
#         )
#         await state.update_data(payment_message_id=payment_message.message_id)
#         await state.set_state(Booking.STATUS_PAYMENT)
#
#         task = asyncio.create_task(poll_payment_status(message, state, bot=message.bot))
#         await state.update_data(payment_task=task)
#         logger.info(
#             f"Создан платёж {payment_id} для пользователя {message.from_user.id}, "
#             f"сумма: {amount:.2f}"
#         )
#
#
# def format_phone_for_rubitime(phone: str) -> str:
#     """
#     Форматирует номер телефона для Rubitime в формате +7**********.
#
#     Args:
#         phone: Исходный номер телефона.
#
#     Returns:
#         str: Форматированный номер или "Не указано", если номер некорректен.
#     """
#     if not phone or phone == "Не указано":
#         return "Не указано"
#
#     digits = re.sub(r"[^0-9]", "", phone)
#     if digits.startswith("8") or digits.startswith("+7"):
#         if len(digits) >= 11:
#             return f"+7{digits[-10:]}"
#     logger.warning(f"Некорректный формат номера телефона: {phone}")
#     return "Не указано"
#
#
# async def handle_free_booking(
#     message: Message, state: FSMContext, bot: Bot, paid: bool = True
# ) -> None:
#     """
#     Обработка бронирования без оплаты (для "Переговорной" или если сумма после скидки = 0).
#
#     Args:
#         message: Входящее сообщение.
#         state: Контекст состояния FSM.
#         bot: Экземпляр бота.
#         paid: Флаг, указывающий, оплачена ли бронь (True для бесплатных, False для "Переговорной").
#     """
#     data = await state.get_data()
#     tariff_id = data["tariff_id"]
#     tariff_name = data["tariff_name"]
#     tariff_purpose = data["tariff_purpose"]
#     tariff_service_id = data["tariff_service_id"]
#     visit_date = data["visit_date"]
#     visit_time = data.get("visit_time")
#     duration = data.get("duration")
#     amount = data["amount"]
#     promocode_id = data.get("promocode_id")
#     promocode_name = data.get("promocode_name", "-")
#     discount = data.get("discount", 0)
#
#     booking, admin_message, session = create_booking(
#         user_id=message.from_user.id,
#         tariff_id=tariff_id,
#         visit_date=visit_date,
#         visit_time=visit_time,
#         duration=duration,
#         promocode_id=promocode_id,
#         amount=amount,
#         paid=paid,
#         confirmed=(False if tariff_purpose == "переговорная" else True),
#     )
#     if not booking:
#         if session:
#             session.close()
#         await message.answer(
#             admin_message or "Ошибка при создании брони.",
#             reply_markup=create_user_keyboard(),
#         )
#         logger.warning(
#             f"Не удалось создать бронь для пользователя {message.from_user.id}"
#         )
#         await state.clear()
#         return
#
#     try:
#         user = session.query(User).filter_by(telegram_id=message.from_user.id).first()
#
#         # Уменьшаем количество использований промокода, если он применён
#         if promocode_id:
#             promocode = session.query(Promocode).filter_by(id=promocode_id).first()
#             if promocode:
#                 promocode.usage_quantity -= 1
#                 session.add(promocode)
#                 logger.info(
#                     f"Промокод {promocode_name} использован, "
#                     f"осталось использований: {promocode.usage_quantity}"
#                 )
#
#         # Увеличиваем счетчик успешных бронирований для тарифов "Опенспейс" при успешной брони
#         if tariff_purpose == "опенспейс" and booking.confirmed:
#             user.successful_bookings += 1
#             logger.info(
#                 f"Увеличен счетчик successful_bookings для пользователя {user.telegram_id} "
#                 f"до {user.successful_bookings}"
#             )
#
#         session.commit()
#
#         # Формируем дату и время для Rubitime
#         if tariff_purpose == "переговорная" and visit_time and duration:
#             rubitime_date = datetime.combine(visit_date, visit_time).strftime(
#                 "%Y-%m-%d %H:%M:%S"
#             )
#             rubitime_duration = duration * 60
#         else:
#             rubitime_date = visit_date.strftime("%Y-%m-%d") + " 09:00:00"
#             rubitime_duration = None
#
#         formatted_phone = format_phone_for_rubitime(user.phone or "Не указано")
#         rubitime_params = {
#             "service_id": tariff_service_id,
#             "name": user.full_name or "Не указано",
#             "email": user.email or "Не указано",
#             "phone": formatted_phone,
#             "record": rubitime_date,
#             "comment": f"Промокод: {promocode_name}, скидка: {discount}%",
#             "coupon": promocode_name,
#             "coupon_discount": f"{discount}%",
#             "price": amount,
#         }
#         if rubitime_duration:
#             rubitime_params["duration"] = rubitime_duration
#
#         rubitime_id = await rubitime("create_record", rubitime_params)
#         if rubitime_id:
#             booking.rubitime_id = rubitime_id
#             session.commit()
#             logger.info(
#                 f"Запись в Rubitime создана: ID {rubitime_id}, date={rubitime_date}, "
#                 f"duration={rubitime_duration}, price={amount}"
#             )
#
#             # Обновляем admin_message с актуальным rubitime_id
#             updated_booking_data = {
#                 **data,
#                 "rubitime_id": rubitime_id,
#             }
#             admin_message = format_booking_notification(
#                 user,
#                 session.query(Tariff).filter_by(id=tariff_id).first(),
#                 updated_booking_data,
#             )
#
#         await bot.send_message(
#             ADMIN_TELEGRAM_ID,
#             admin_message,
#             parse_mode="HTML",
#         )
#
#         # Формируем сообщение для пользователя
#         response_text = format_user_booking_notification(
#             user,
#             {**data, "rubitime_id": rubitime_id or "Не создано"},
#             confirmed=(tariff_purpose != "переговорная"),
#         )
#         await message.answer(
#             response_text,
#             parse_mode="HTML",
#             reply_markup=create_user_keyboard(),
#         )
#         logger.info(
#             f"Бронь создана для пользователя {message.from_user.id}, "
#             f"ID брони {booking.id}, paid={paid}, amount={amount}"
#         )
#     except Exception as e:
#         logger.error(f"Ошибка при обработке брони: {str(e)}")
#         session.rollback()
#         await message.answer(
#             "Ошибка при создании брони. Попробуйте позже.",
#             reply_markup=create_user_keyboard(),
#         )
#     finally:
#         if session:
#             session.close()
#         await state.clear()
#
#
# async def poll_payment_status(message: Message, state: FSMContext, bot: Bot) -> None:
#     """
#     Проверка статуса платежа с ограничением по времени.
#
#     Args:
#         message: Входящее сообщение.
#         state: Контекст состояния FSM.
#         bot: Экземпляр бота.
#     """
#     data = await state.get_data()
#     payment_id = data["payment_id"]
#     payment_message_id = data["payment_message_id"]
#     tariff_id = data["tariff_id"]
#     tariff_name = data["tariff_name"]
#     tariff_purpose = data["tariff_purpose"]
#     tariff_service_id = data["tariff_service_id"]
#     visit_date = data["visit_date"]
#     visit_time = data.get("visit_time")
#     duration = data.get("duration")
#     amount = data["amount"]
#     promocode_id = data.get("promocode_id")
#     promocode_name = data.get("promocode_name", "-")
#     discount = data.get("discount", 0)
#
#     max_attempts = 60
#     delay = 5
#     user = None
#     for _ in range(max_attempts):
#         status = await check_payment_status(payment_id)
#         if status == "succeeded":
#             booking, admin_message, session = create_booking(
#                 user_id=message.from_user.id,
#                 tariff_id=tariff_id,
#                 visit_date=visit_date,
#                 visit_time=visit_time,
#                 duration=duration,
#                 promocode_id=promocode_id,
#                 amount=amount,
#                 paid=True,
#                 confirmed=(True if duration is None else False),
#                 payment_id=payment_id,
#             )
#             if not booking:
#                 if session:
#                     session.close()
#                 await bot.edit_message_text(
#                     text="Ошибка при создании брони. Попробуйте позже.",
#                     chat_id=message.chat.id,
#                     message_id=payment_message_id,
#                     reply_markup=create_user_keyboard(),
#                 )
#                 logger.warning(
#                     f"Не удалось создать бронь после оплаты для пользователя {message.from_user.id}"
#                 )
#                 await state.clear()
#                 return
#             try:
#                 user = (
#                     session.query(User)
#                     .filter_by(telegram_id=message.from_user.id)
#                     .first()
#                 )
#
#                 # Уменьшаем количество использований промокода, если он применён
#                 if promocode_id:
#                     promocode = (
#                         session.query(Promocode).filter_by(id=promocode_id).first()
#                     )
#                     if promocode:
#                         promocode.usage_quantity -= 1
#                         session.add(promocode)
#                         logger.info(
#                             f"Промокод {promocode_name} использован, "
#                             f"осталось использований: {promocode.usage_quantity}"
#                         )
#
#                 # Увеличиваем счетчик успешных бронирований для тарифов "Опенспейс" при успешной брони
#                 if tariff_purpose == "опенспейс" and booking.confirmed:
#                     user.successful_bookings += 1
#                     logger.info(
#                         f"Увеличен счетчик successful_bookings для пользователя {user.telegram_id} "
#                         f"до {user.successful_bookings}"
#                     )
#
#                 session.commit()
#
#                 # Формируем дату и время для Rubitime
#                 if tariff_purpose == "переговорная" and visit_time and duration:
#                     rubitime_date = datetime.combine(visit_date, visit_time).strftime(
#                         "%Y-%m-%d %H:%M:%S"
#                     )
#                     rubitime_duration = duration * 60
#                 else:
#                     rubitime_date = visit_date.strftime("%Y-%m-%d") + " 09:00:00"
#                     rubitime_duration = None
#
#                 formatted_phone = format_phone_for_rubitime(user.phone or "Не указано")
#                 rubitime_params = {
#                     "service_id": tariff_service_id,
#                     "name": user.full_name or "Не указано",
#                     "email": user.email or "Не указано",
#                     "phone": formatted_phone,
#                     "record": rubitime_date,
#                     "comment": f"Промокод: {promocode_name}, скидка: {discount}%",
#                     "coupon": promocode_name,
#                     "coupon_discount": f"{discount}%",
#                     "price": amount,
#                 }
#                 if rubitime_duration:
#                     rubitime_params["duration"] = rubitime_duration
#
#                 rubitime_id = await rubitime("create_record", rubitime_params)
#                 if rubitime_id:
#                     booking.rubitime_id = rubitime_id
#                     session.commit()
#                     logger.info(
#                         f"Запись в Rubitime создана: ID {rubitime_id}, date={rubitime_date}, "
#                         f"duration={rubitime_duration}, price={amount}"
#                     )
#
#                     # Обновляем admin_message с актуальным rubitime_id
#                     updated_booking_data = {
#                         **data,
#                         "rubitime_id": rubitime_id,
#                     }
#                     admin_message = format_booking_notification(
#                         user,
#                         session.query(Tariff).filter_by(id=tariff_id).first(),
#                         updated_booking_data,
#                     )
#
#                 # Отправляем уведомление об успешной оплате
#                 payment_notification = format_payment_notification(
#                     user, data, status="SUCCESS"
#                 )
#                 await bot.send_message(
#                     ADMIN_TELEGRAM_ID,
#                     payment_notification,
#                     parse_mode="HTML",
#                 )
#                 await bot.send_message(
#                     ADMIN_TELEGRAM_ID,
#                     admin_message,
#                     parse_mode="HTML",
#                 )
#
#                 # Формируем сообщение для пользователя
#                 response_text = format_user_booking_notification(
#                     user,
#                     {**data, "rubitime_id": rubitime_id or "Не создано"},
#                     confirmed=(tariff_purpose != "переговорная"),
#                 )
#                 await bot.edit_message_text(
#                     text=response_text,
#                     chat_id=message.chat.id,
#                     message_id=payment_message_id,
#                     parse_mode="HTML",
#                     reply_markup=create_user_keyboard(),
#                 )
#                 logger.info(
#                     f"Бронь создана после оплаты для пользователя {message.from_user.id}, "
#                     f"ID брони {booking.id}, amount={amount}"
#                 )
#             except Exception as e:
#                 logger.error(f"Ошибка после успешной оплаты: {str(e)}")
#                 session.rollback()
#                 # Отправляем уведомление об ошибке
#                 # payment_notification = format_payment_notification(
#                 #     user, data, status="FAILED"
#                 # )
#                 if user:
#                     payment_notification = format_payment_notification(
#                         user, data, status="FAILED"
#                     )
#                 else:
#                     payment_notification = (
#                         f"⚠️ Ошибка: не удалось создать бронь. Пользователь не найден.\n"
#                         f"Payment ID: {payment_id}\n"
#                         f"Сумма: {amount} руб."
#                     )
#                 await bot.send_message(
#                     ADMIN_TELEGRAM_ID,
#                     payment_notification,
#                     parse_mode="HTML",
#                 )
#                 await bot.edit_message_text(
#                     text="Ошибка при создании брони. Попробуйте позже.",
#                     chat_id=message.chat.id,
#                     message_id=payment_message_id,
#                     reply_markup=create_user_keyboard(),
#                 )
#             finally:
#                 if session:
#                     session.close()
#                 await state.clear()
#             return
#         elif status == "canceled":
#             payment_notification = format_payment_notification(
#                 user, data, status="CANCELLED"
#             )
#             await bot.send_message(
#                 ADMIN_TELEGRAM_ID,
#                 payment_notification,
#                 parse_mode="HTML",
#             )
#             await bot.edit_message_text(
#                 text="Платёж отменён.",
#                 chat_id=message.chat.id,
#                 message_id=payment_message_id,
#                 reply_markup=create_user_keyboard(),
#             )
#             await state.clear()
#             return
#         await asyncio.sleep(delay)
#
#     payment_notification = format_payment_notification(user, data, status="FAILED")
#     await bot.send_message(
#         ADMIN_TELEGRAM_ID,
#         payment_notification,
#         parse_mode="HTML",
#     )
#     await bot.edit_message_text(
#         text="Время оплаты истекло. Попробуйте снова.",
#         chat_id=message.chat.id,
#         message_id=payment_message_id,
#         reply_markup=create_user_keyboard(),
#     )
#     await state.clear()
#     logger.warning(f"Время оплаты истекло для payment_id {payment_id}")
#
#
# @router.callback_query(Booking.STATUS_PAYMENT, F.data == "cancel_payment")
# async def cancel_payment(callback_query: CallbackQuery, state: FSMContext) -> None:
#     """
#     Обработка отмены платежа.
#
#     Args:
#         callback_query: Callback-запрос.
#         state: Контекст состояния FSM.
#     """
#     data = await state.get_data()
#     payment_id = data.get("payment_id")
#     payment_message_id = data.get("payment_message_id")
#     payment_task = data.get("payment_task")
#
#     user = get_user_by_telegram_id(callback_query.from_user.id)
#
#     if payment_task and not payment_task.done():
#         payment_task.cancel()
#         logger.info(f"Задача проверки платежа {payment_id} отменена")
#
#     if payment_id:
#         try:
#             status = await check_payment_status(payment_id)
#             if status == "succeeded":
#                 refund = Refund.create(
#                     {
#                         "amount": {
#                             "value": f"{data['amount']:.2f}",
#                             "currency": "RUB",
#                         },
#                         "payment_id": payment_id,
#                         "description": f"Возврат для брони {payment_id}",
#                     }
#                 )
#                 logger.info(
#                     f"Возврат создан для платежа {payment_id}, refund_id={refund.id}"
#                 )
#             elif status == "pending":
#                 Payment.cancel(payment_id)
#                 logger.info(f"Платёж {payment_id} отменён в YooKassa")
#             else:
#                 logger.info(
#                     f"Платёж {payment_id} уже в статусе {status}, отмена не требуется"
#                 )
#         except Exception as e:
#             logger.warning(f"Не удалось обработать платёж {payment_id}: {str(e)}")
#             logger.info(f"Завершаем отмену без дополнительного обращения к YooKassa")
#
#     payment_notification = format_payment_notification(user, data, status="CANCELLED")
#     await callback_query.message.bot.send_message(
#         ADMIN_TELEGRAM_ID,
#         payment_notification,
#         parse_mode="HTML",
#     )
#     await callback_query.message.edit_text(
#         text="Платёж отменён.",
#         reply_markup=create_user_keyboard(),
#     )
#     await state.clear()
#     logger.info(f"Платёж отменён для пользователя {callback_query.from_user.id}")
#     await callback_query.answer()
#
#
# @router.callback_query(
#     F.data == "cancel",
#     StateFilter(
#         Booking.SELECT_TARIFF,
#         Booking.ENTER_DATE,
#         Booking.ENTER_TIME,
#         Booking.ENTER_DURATION,
#         Booking.ENTER_PROMOCODE,
#     ),
# )
# @router.callback_query(
#     F.data == "main_menu",
#     StateFilter(
#         Booking.SELECT_TARIFF,
#         Booking.ENTER_DATE,
#         Booking.ENTER_TIME,
#         Booking.ENTER_DURATION,
#         Booking.ENTER_PROMOCODE,
#     ),
# )
# async def cancel_booking(callback_query: CallbackQuery, state: FSMContext) -> None:
#     """
#     Обработка нажатия кнопки 'Главное меню' в состояниях бронирования.
#
#     Args:
#         callback_query: Callback-запрос.
#         state: Контекст состояния FSM.
#     """
#     await state.clear()
#     await callback_query.message.edit_text(
#         text="Бронирование отменено.", reply_markup=create_user_keyboard()
#     )
#     logger.info(f"Пользователь {callback_query.from_user.id} вернулся в главное меню")
#     await callback_query.answer()
#
#
# def register_book_handlers(dp: Dispatcher) -> None:
#     """Регистрация обработчиков."""
#     dp.include_router(router)
"""
Обновленный обработчик бронирования для работы через API
"""
import os
import asyncio
import pytz
import re
from datetime import datetime, timedelta, date, time
from typing import Optional

from aiogram import Router, F, Bot, Dispatcher
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from utils.logger import get_logger
from utils.api_client import get_api_client
from bot.config import create_back_keyboard, create_user_keyboard

logger = get_logger(__name__)

router = Router()
MOSCOW_TZ = pytz.timezone("Europe/Moscow")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")


class Booking(StatesGroup):
    SELECT_TARIFF = State()
    ENTER_DATE = State()
    ENTER_TIME = State()
    ENTER_DURATION = State()
    ENTER_PROMOCODE = State()
    PAYMENT = State()
    STATUS_PAYMENT = State()


def format_payment_notification(user, booking_data, status="SUCCESS"):
    """Форматирование уведомления об оплате"""
    status_emojis = {
        "SUCCESS": "✅",
        "FAILED": "❌",
        "CANCELLED": "🚫",
        "PENDING": "⏳",
    }

    status_emoji = status_emojis.get(status, "❓")

    status_texts = {
        "SUCCESS": "ПЛАТЕЖ УСПЕШЕН",
        "FAILED": "ПЛАТЕЖ НЕ ПРОШЕЛ",
        "CANCELLED": "ПЛАТЕЖ ОТМЕНЕН",
        "PENDING": "ОЖИДАНИЕ ПЛАТЕЖА",
    }

    status_text = status_texts.get(status, "НЕИЗВЕСТНЫЙ СТАТУС")

    message = f"""💳 <b>{status_text}</b> {status_emoji}

👤 <b>Пользователь:</b> {user.get('full_name', 'Не указано')}
📱 <b>Telegram:</b> @{user.get('username', 'Не указан')}
📞 <b>Телефон:</b> {user.get('phone', 'Не указан')}

📋 <b>Тариф:</b> {booking_data.get('tariff_name')}
📅 <b>Дата визита:</b> {booking_data.get('visit_date')}
💰 <b>Сумма:</b> {booking_data.get('amount')} ₽

🆔 <b>ID платежа:</b> {booking_data.get('payment_id', 'Не указан')}"""

    return message


def format_user_booking_notification(user, booking_data, confirmed: bool) -> str:
    """Форматирование уведомления о брони для пользователя"""
    tariff_emojis = {
        "рабочее место": "💻",
        "переговорная": "🏢",
        "день": "☀️",
        "месяц": "📅",
    }

    purpose = booking_data.get("tariff_purpose", "").lower()
    tariff_emoji = tariff_emojis.get(purpose, "📋")

    visit_date = booking_data.get("visit_date")
    visit_time = booking_data.get("visit_time")

    # Форматирование даты и времени
    if isinstance(visit_date, str):
        try:
            visit_date = datetime.fromisoformat(visit_date).date()
        except:
            pass

    if isinstance(visit_time, str):
        try:
            visit_time = datetime.strptime(visit_time, "%H:%M:%S").time()
        except:
            pass

    if visit_time:
        datetime_str = (
            f"{visit_date.strftime('%d.%m.%Y')} в {visit_time.strftime('%H:%M')}"
        )
    else:
        datetime_str = f"{visit_date.strftime('%d.%m.%Y')} (весь день)"

    discount_info = ""
    if booking_data.get("promocode_name"):
        promocode_name = booking_data.get("promocode_name", "Неизвестный")
        discount = booking_data.get("discount", 0)
        discount_info = f"\n🎁 <b>Промокод:</b> {promocode_name} (-{discount}%)"

    duration_info = ""
    if booking_data.get("duration"):
        duration_info = f"\n⏱ <b>Длительность:</b> {booking_data['duration']} час(ов)"

    status_text = "Бронь подтверждена ✅" if confirmed else "Ожидайте подтверждения ⏳"
    status_instruction = (
        "\n\n📍 Ждем вас по адресу: г. Москва, ул. Примерная, д. 1"
        if confirmed
        else "\n\n⏳ Администратор свяжется с вами для подтверждения брони."
    )

    message = f"""🎉 <b>Ваша бронь создана!</b> {tariff_emoji}

📋 <b>Тариф:</b> {booking_data.get('tariff_name')}
📅 <b>Дата и время:</b> {datetime_str}{duration_info}
💰 <b>Сумма:</b> {booking_data.get('amount')} ₽{discount_info}

<b>Статус:</b> {status_text}{status_instruction}"""

    return message


def format_booking_notification(user, tariff, booking_data):
    """Форматирование уведомления о бронировании для админа"""
    tariff_emojis = {
        "рабочее место": "💻",
        "переговорная": "🏢",
        "день": "☀️",
        "месяц": "📅",
    }

    purpose = booking_data.get("tariff_purpose", "").lower()
    tariff_emoji = tariff_emojis.get(purpose, "📋")

    visit_date = booking_data.get("visit_date")
    visit_time = booking_data.get("visit_time")

    if isinstance(visit_date, str):
        try:
            visit_date = datetime.fromisoformat(visit_date).date()
        except:
            pass

    if isinstance(visit_time, str):
        try:
            visit_time = datetime.strptime(visit_time, "%H:%M:%S").time()
        except:
            pass

    if visit_time:
        datetime_str = (
            f"{visit_date.strftime('%d.%m.%Y')} в {visit_time.strftime('%H:%M')}"
        )
    else:
        datetime_str = f"{visit_date.strftime('%d.%m.%Y')} (весь день)"

    discount_info = ""
    if booking_data.get("promocode_name"):
        promocode_name = booking_data.get("promocode_name", "Неизвестный")
        discount = booking_data.get("discount", 0)
        discount_info = f"\n🎁 <b>Промокод:</b> {promocode_name} (-{discount}%)"

    duration_info = ""
    if booking_data.get("duration"):
        duration_info = f"\n⏱ <b>Длительность:</b> {booking_data['duration']} час(ов)"

    message = f"""🎯 <b>НОВАЯ БРОНЬ!</b> {tariff_emoji}

👤 <b>Пользователь:</b> {user.get('full_name', 'Не указано')}
📱 <b>Telegram:</b> @{user.get('username', 'Не указан')}
📞 <b>Телефон:</b> {user.get('phone', 'Не указан')}
📧 <b>Email:</b> {user.get('email', 'Не указан')}

📋 <b>Тариф:</b> {tariff.get('name')}
📅 <b>Дата и время:</b> {datetime_str}{duration_info}
💰 <b>Сумма:</b> {booking_data.get('amount')} ₽{discount_info}

💳 <b>Оплачено:</b> {'Да ✅' if booking_data.get('paid') else 'Нет ❌'}
✅ <b>Подтверждено:</b> {'Да' if booking_data.get('confirmed') else 'Нет ⏳'}"""

    if booking_data.get("rubitime_id"):
        message += f"\n🆔 <b>Rubitime ID:</b> {booking_data['rubitime_id']}"

    return message


def create_date_keyboard() -> InlineKeyboardMarkup:
    """Создание клавиатуры для выбора даты"""
    today = datetime.now(MOSCOW_TZ).date()
    buttons = []

    for i in range(14):  # Показываем 14 дней
        date = today + timedelta(days=i)
        date_str = date.strftime("%d.%m")
        callback_data = f"date_{date.strftime('%Y-%m-%d')}"

        if i == 0:
            date_str = f"Сегодня ({date_str})"
        elif i == 1:
            date_str = f"Завтра ({date_str})"

        buttons.append(
            [InlineKeyboardButton(text=date_str, callback_data=callback_data)]
        )

    buttons.append(
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_tariffs")]
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard


@router.callback_query(F.data == "book")
async def start_booking(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Начало процесса бронирования"""
    api_client = await get_api_client()

    # Получаем пользователя
    user = await api_client.get_user_by_telegram_id(callback_query.from_user.id)

    if not user:
        await callback_query.message.edit_text(
            "❌ Ошибка: пользователь не найден. Пожалуйста, зарегистрируйтесь.",
            reply_markup=create_back_keyboard(),
        )
        await callback_query.answer()
        return

    # Получаем активные тарифы
    tariffs = await api_client.get_active_tariffs()

    if not tariffs:
        await callback_query.message.edit_text(
            "😔 К сожалению, сейчас нет доступных тарифов.",
            reply_markup=create_back_keyboard(),
        )
        await callback_query.answer()
        return

    # Создаем клавиатуру с тарифами
    buttons = []
    successful_bookings = user.get("successful_bookings", 0)

    for tariff in tariffs:
        tariff_id = tariff.get("id")
        tariff_name = tariff.get("name")
        tariff_price = tariff.get("price")

        # Проверяем скидку за количество бронирований
        if successful_bookings >= 10:
            discount_text = " (скидка 10%)"
        else:
            discount_text = ""

        button_text = f"{tariff_name} - {tariff_price}₽{discount_text}"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=button_text, callback_data=f"tariff_{tariff_id}"
                )
            ]
        )

    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="main_menu")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await callback_query.message.edit_text(
        "📋 <b>Выберите тариф:</b>\n\n"
        f"У вас {successful_bookings} успешных бронирований.\n"
        f"{'🎉 У вас скидка 10% на все тарифы!' if successful_bookings >= 10 else ''}",
        reply_markup=keyboard,
        parse_mode="HTML",
    )

    await state.set_state(Booking.SELECT_TARIFF)
    await callback_query.answer()


@router.callback_query(Booking.SELECT_TARIFF, F.data.startswith("tariff_"))
async def select_tariff(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Выбор тарифа"""
    tariff_id = int(callback_query.data.split("_")[1])

    api_client = await get_api_client()

    # Получаем информацию о тарифе
    tariff = await api_client.get_tariff(tariff_id)

    if not tariff:
        await callback_query.message.edit_text(
            "❌ Ошибка: тариф не найден.", reply_markup=create_back_keyboard()
        )
        await callback_query.answer()
        return

    # Сохраняем информацию о тарифе
    await state.update_data(
        tariff_id=tariff_id,
        tariff_name=tariff.get("name"),
        tariff_price=tariff.get("price"),
        tariff_purpose=tariff.get("purpose"),
        tariff_service_id=tariff.get("service_id"),
    )

    # Показываем календарь для выбора даты
    await callback_query.message.edit_text(
        f"📅 <b>Выбор даты</b>\n\n"
        f"Тариф: {tariff.get('name')}\n"
        f"Выберите дату визита:",
        reply_markup=create_date_keyboard(),
        parse_mode="HTML",
    )

    await state.set_state(Booking.ENTER_DATE)
    await callback_query.answer()


@router.callback_query(Booking.ENTER_DATE, F.data.startswith("date_"))
async def select_date(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Выбор даты"""
    date_str = callback_query.data.split("_")[1]
    visit_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    await state.update_data(visit_date=visit_date)

    data = await state.get_data()
    tariff_purpose = data["tariff_purpose"]
    tariff_name = data["tariff_name"]

    if tariff_purpose and "переговорн" in tariff_purpose.lower():
        # Для переговорной запрашиваем время
        await callback_query.message.edit_text(
            f"⏰ <b>Выбор времени</b>\n\n"
            f"Тариф: {tariff_name}\n"
            f"Дата: {visit_date.strftime('%d.%m.%Y')}\n\n"
            f"Введите время начала в формате ЧЧ:ММ (например, 14:30):",
            parse_mode="HTML",
        )
        await state.set_state(Booking.ENTER_TIME)
    else:
        # Для других тарифов переходим к промокоду
        await state.update_data(visit_time=None, duration=None)
        await callback_query.message.edit_text(
            f"🎁 <b>Промокод</b>\n\n"
            f"Тариф: {tariff_name}\n"
            f"Дата: {visit_date.strftime('%d.%m.%Y')}\n\n"
            f"Если у вас есть промокод, введите его.\n"
            f"Или нажмите «Пропустить»:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="➡️ Пропустить", callback_data="skip_promocode"
                        )
                    ]
                ]
            ),
            parse_mode="HTML",
        )
        await state.set_state(Booking.ENTER_PROMOCODE)

    await callback_query.answer()


@router.callback_query(F.data == "back_to_tariffs")
async def back_to_tariffs(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Возврат к выбору тарифов"""
    await state.set_state(Booking.SELECT_TARIFF)
    await start_booking(callback_query, state)


@router.message(Booking.ENTER_DATE)
async def process_date(message: Message, state: FSMContext) -> None:
    """Обработка ввода даты текстом"""
    try:
        visit_date = datetime.strptime(message.text, "%Y-%m-%d").date()
        await state.update_data(visit_date=visit_date)

        data = await state.get_data()
        tariff_purpose = data["tariff_purpose"]

        if tariff_purpose and "переговорн" in tariff_purpose.lower():
            await message.answer(
                "⏰ Введите время начала в формате ЧЧ:ММ (например, 14:30):"
            )
            await state.set_state(Booking.ENTER_TIME)
        else:
            await state.update_data(visit_time=None, duration=None)
            await message.answer(
                "🎁 Если у вас есть промокод, введите его. Или нажмите «Пропустить»:",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="➡️ Пропустить", callback_data="skip_promocode"
                            )
                        ]
                    ]
                ),
            )
            await state.set_state(Booking.ENTER_PROMOCODE)
    except ValueError:
        await message.answer("❌ Неверный формат даты. Используйте формат ГГГГ-ММ-ДД")


@router.message(Booking.ENTER_TIME)
async def process_time(message: Message, state: FSMContext) -> None:
    """Обработка ввода времени"""
    try:
        visit_time = datetime.strptime(message.text, "%H:%M").time()
        await state.update_data(visit_time=visit_time)

        await message.answer(
            "⏱ Введите длительность бронирования в часах (например, 2):"
        )
        await state.set_state(Booking.ENTER_DURATION)
    except ValueError:
        await message.answer("❌ Неверный формат времени. Используйте формат ЧЧ:ММ")


@router.message(Booking.ENTER_DURATION)
async def process_duration(message: Message, state: FSMContext) -> None:
    """Обработка ввода длительности"""
    try:
        duration = int(message.text)

        if duration < 1 or duration > 12:
            await message.answer("❌ Длительность должна быть от 1 до 12 часов")
            return

        await state.update_data(duration=duration)

        await message.answer(
            "🎁 Если у вас есть промокод, введите его. Или нажмите «Пропустить»:",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="➡️ Пропустить", callback_data="skip_promocode"
                        )
                    ]
                ]
            ),
        )
        await state.set_state(Booking.ENTER_PROMOCODE)
    except ValueError:
        await message.answer("❌ Введите число часов")


@router.callback_query(F.data == "skip_promocode")
async def skip_promocode(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Пропуск ввода промокода"""
    await process_promocode_internal(callback_query.message, state, None)
    await callback_query.answer()


@router.message(Booking.ENTER_PROMOCODE)
async def process_promocode(message: Message, state: FSMContext) -> None:
    """Обработка ввода промокода"""
    promocode_name = message.text.strip()
    await process_promocode_internal(message, state, promocode_name)


async def process_promocode_internal(
    message: Message, state: FSMContext, promocode_name: Optional[str]
) -> None:
    """Внутренняя обработка промокода и расчет суммы"""
    data = await state.get_data()
    api_client = await get_api_client()

    # Получаем пользователя
    user = await api_client.get_user_by_telegram_id(
        message.from_user.id if hasattr(message, "from_user") else message.chat.id
    )

    tariff_price = data["tariff_price"]
    promocode_id: Optional[int] = None
    promocode_name_final: Optional[str] = None
    discount: float = 0

    # Проверяем промокод если он введен
    if promocode_name:
        promocode = await api_client.get_promocode_by_name(promocode_name)

        if promocode:
            discount = promocode.get("discount", 0)
            promocode_id = promocode.get("id")
            promocode_name_final = promocode.get("name")

            await message.answer(f"✅ Промокод применен! Скидка: {discount}%")
        else:
            await message.answer("❌ Промокод не найден или недействителен")

    # Рассчитываем сумму
    duration = data.get("duration")
    if duration:
        # Для переговорной - почасовая оплата
        amount = tariff_price * duration
    else:
        amount = tariff_price

    # Применяем скидки
    successful_bookings = user.get("successful_bookings", 0)
    if successful_bookings >= 10:
        additional_discount = 10
        total_discount = min(100, discount + additional_discount)
        await message.answer(
            f"🎉 Дополнительная скидка за лояльность: {additional_discount}%"
        )
    else:
        total_discount = discount

    if total_discount > 0:
        amount = amount * (1 - total_discount / 100)

    # Сохраняем данные
    await state.update_data(
        amount=amount,
        promocode_id=promocode_id,
        promocode_name=promocode_name_final,
        discount=total_discount,
        user_id=user.get("telegram_id"),
    )

    # Формируем описание для платежа
    description = f"Бронь: {data['tariff_name']}, дата: {data['visit_date']}"
    if duration:
        description += f", {duration} час(ов)"

    # Создаем платеж через API
    payment_data = {
        "amount": amount,
        "description": description,
        "return_url": f"https://t.me/{os.getenv('BOT_LINK', 'your_bot')}",
    }

    payment_result = await api_client.create_payment(payment_data)

    if "error" in payment_result:
        await message.answer(
            "❌ Ошибка создания платежа. Попробуйте позже.",
            reply_markup=create_back_keyboard(),
        )
        await state.clear()
        return

    payment_id = payment_result.get("payment_id")
    confirmation_url = payment_result.get("confirmation_url")

    await state.update_data(payment_id=payment_id)

    # Отправляем сообщение с кнопкой оплаты
    visit_time = data.get("visit_time")
    time_str = ""
    if visit_time:
        if isinstance(visit_time, time):
            time_str = f"⏰ Время: {visit_time.strftime('%H:%M')}\n"
        else:
            time_str = f"⏰ Время: {visit_time}\n"

    payment_message = await message.answer(
        f"💳 <b>К оплате: {amount:.2f} ₽</b>\n\n"
        f"📋 Тариф: {data['tariff_name']}\n"
        f"📅 Дата: {data['visit_date']}\n"
        f"{time_str}"
        f"{'⏱ Длительность: ' + str(duration) + ' час(ов)' if duration else ''}\n"
        f"{'🎁 Промокод: ' + promocode_name_final + ' (-' + str(int(total_discount)) + '%)' if promocode_name_final else ''}\n\n"
        f"Нажмите кнопку ниже для оплаты:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить", url=confirmation_url)],
                [
                    InlineKeyboardButton(
                        text="❌ Отменить", callback_data="cancel_payment"
                    )
                ],
            ]
        ),
        parse_mode="HTML",
    )

    await state.update_data(payment_message_id=payment_message.message_id)
    await state.set_state(Booking.STATUS_PAYMENT)

    # Запускаем проверку статуса платежа
    task = asyncio.create_task(poll_payment_status(message, state, bot=message.bot))
    await state.update_data(payment_task=task)


def format_phone_for_rubitime(phone: str) -> str:
    """Форматирование телефона для Rubitime"""
    digits = re.sub(r"[^0-9]", "", phone)
    if digits.startswith("7"):
        digits = "8" + digits[1:]
    return digits


async def create_booking_in_system(message: Message, state: FSMContext) -> None:
    """Создание брони в системе после успешной оплаты"""
    data = await state.get_data()
    api_client = await get_api_client()

    # Получаем пользователя
    user = await api_client.get_user_by_telegram_id(message.from_user.id)

    # Подготавливаем данные для Rubitime
    tariff_service_id = data.get("tariff_service_id")
    visit_date = data["visit_date"]
    visit_time = data.get("visit_time")
    duration = data.get("duration")

    if visit_time and duration:
        rubitime_date = datetime.combine(visit_date, visit_time).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        rubitime_duration = duration * 60
    else:
        rubitime_date = visit_date.strftime("%Y-%m-%d") + " 09:00:00"
        rubitime_duration = None

    formatted_phone = format_phone_for_rubitime(user.get("phone", ""))

    rubitime_params = {
        "phone": formatted_phone,
        "name": user.get("full_name", "Не указано"),
        "email": user.get("email", ""),
        "service_id": tariff_service_id,
        "date": rubitime_date,
    }

    if rubitime_duration:
        rubitime_params["duration"] = rubitime_duration

    # Создаем запись в Rubitime
    rubitime_id = await api_client.create_rubitime_record(rubitime_params)

    # Создаем бронирование через API
    booking_data = {
        "user_id": user.get("telegram_id"),
        "tariff_id": data["tariff_id"],
        "visit_date": data["visit_date"].isoformat(),
        "visit_time": (
            data.get("visit_time").isoformat() if data.get("visit_time") else None
        ),
        "duration": duration,
        "promocode_id": data.get("promocode_id"),
        "amount": data["amount"],
        "payment_id": data.get("payment_id"),
        "paid": True,
        "rubitime_id": rubitime_id,
        "confirmed": False,
    }

    booking_result = await api_client.create_booking(booking_data)

    if "error" not in booking_result:
        # Используем промокод если был применен
        if data.get("promocode_id"):
            await api_client.use_promocode(data["promocode_id"])

        # Обновляем данные для уведомлений
        updated_booking_data = {
            **data,
            "booking_id": booking_result.get("id"),
            "rubitime_id": rubitime_id,
            "paid": True,
            "confirmed": False,
        }

        # Отправляем уведомление админу
        if ADMIN_TELEGRAM_ID:
            tariff = await api_client.get_tariff(data["tariff_id"])
            admin_message = format_booking_notification(
                user, tariff, updated_booking_data
            )

            try:
                await message.bot.send_message(
                    ADMIN_TELEGRAM_ID, admin_message, parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления админу: {e}")

        # Отправляем подтверждение пользователю
        response_text = format_user_booking_notification(
            user, updated_booking_data, confirmed=False
        )

        await message.answer(
            response_text, parse_mode="HTML", reply_markup=create_back_keyboard()
        )


async def poll_payment_status(message: Message, state: FSMContext, bot: Bot) -> None:
    """Проверка статуса платежа"""
    data = await state.get_data()
    payment_id = data["payment_id"]
    payment_message_id = data["payment_message_id"]

    api_client = await get_api_client()

    max_attempts = 60  # 5 минут
    delay = 5  # проверка каждые 5 секунд
    user = None

    for attempt in range(max_attempts):
        try:
            # Проверяем статус платежа через API
            payment_status = await api_client.check_payment_status(payment_id)
            status = payment_status.get("status")

            if status == "succeeded" or payment_status.get("paid"):
                # Платеж успешен
                user = await api_client.get_user_by_telegram_id(message.from_user.id)

                # Создаем бронирование
                await create_booking_in_system(message, state)

                # Удаляем сообщение с кнопкой оплаты
                try:
                    await bot.delete_message(
                        chat_id=message.chat.id, message_id=payment_message_id
                    )
                except:
                    pass

                # Отправляем уведомление об успешной оплате админу
                if ADMIN_TELEGRAM_ID and user:
                    payment_notification = format_payment_notification(
                        user, data, status="SUCCESS"
                    )
                    await bot.send_message(
                        ADMIN_TELEGRAM_ID, payment_notification, parse_mode="HTML"
                    )

                await state.clear()
                return

            elif status in ["canceled", "refunded"]:
                # Платеж отменен или возвращен
                user = await api_client.get_user_by_telegram_id(message.from_user.id)

                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=payment_message_id,
                    text="❌ Платеж отменен.",
                    reply_markup=create_back_keyboard(),
                )

                if ADMIN_TELEGRAM_ID and user:
                    payment_notification = format_payment_notification(
                        user, data, status="CANCELLED"
                    )
                    await bot.send_message(
                        ADMIN_TELEGRAM_ID, payment_notification, parse_mode="HTML"
                    )

                await state.clear()
                return

        except Exception as e:
            logger.error(f"Ошибка проверки статуса платежа: {e}")

        await asyncio.sleep(delay)

    # Таймаут - платеж не завершен
    try:
        user = await api_client.get_user_by_telegram_id(message.from_user.id)

        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=payment_message_id,
            text="⏱ Время ожидания платежа истекло. Попробуйте еще раз.",
            reply_markup=create_back_keyboard(),
        )

        if ADMIN_TELEGRAM_ID and user:
            payment_notification = format_payment_notification(
                user, data, status="FAILED"
            )
            await bot.send_message(
                ADMIN_TELEGRAM_ID, payment_notification, parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Ошибка при таймауте платежа: {e}")

    await state.clear()


@router.callback_query(Booking.STATUS_PAYMENT, F.data == "cancel_payment")
async def cancel_payment(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Отмена платежа"""
    data = await state.get_data()
    payment_id = data.get("payment_id")
    payment_message_id = data.get("payment_message_id")
    payment_task = data.get("payment_task")

    api_client = await get_api_client()
    user = await api_client.get_user_by_telegram_id(callback_query.from_user.id)

    # Отменяем задачу проверки статуса
    if payment_task:
        payment_task.cancel()

    # Отменяем платеж через API
    if payment_id:
        try:
            await api_client.cancel_payment(payment_id)
        except Exception as e:
            logger.error(f"Ошибка отмены платежа: {e}")

    # Обновляем сообщение
    try:
        await callback_query.bot.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=payment_message_id,
            text="❌ Платеж отменен.",
            reply_markup=create_back_keyboard(),
        )
    except:
        pass

    # Отправляем уведомление админу
    if ADMIN_TELEGRAM_ID and user:
        payment_notification = format_payment_notification(
            user, data, status="CANCELLED"
        )
        try:
            await callback_query.bot.send_message(
                ADMIN_TELEGRAM_ID, payment_notification, parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления: {e}")

    await state.clear()
    await callback_query.answer("Платеж отменен")


@router.callback_query(F.data == "cancel_booking")
async def cancel_booking(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Отмена бронирования"""
    await callback_query.message.edit_text(
        "❌ Бронирование отменено.", reply_markup=create_back_keyboard()
    )
    await state.clear()
    await callback_query.answer()


@router.callback_query(F.data == "main_menu")
async def main_menu(callback_query: CallbackQuery, state: FSMContext) -> None:
    """Возврат в главное меню"""
    await state.clear()
    await callback_query.message.edit_text(
        "🏠 Главное меню\n\nВыберите действие:", reply_markup=create_user_keyboard()
    )
    await callback_query.answer()


def register_book_handlers(dp: Dispatcher) -> None:
    """Регистрация обработчиков бронирования"""
    dp.include_router(router)
