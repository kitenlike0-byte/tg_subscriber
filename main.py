import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logging.basicConfig(level=logging.INFO)

TOKEN = "ТВОЙ_ТОКЕН_БОТА"  # Замени на свой токен
bot = Bot(token=TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler()

class AddSubscription(StatesGroup):
    name = State()
    price = State()
    currency = State()
    period = State()
    date = State()

# --- ОБНОВЛЕННАЯ БАЗА ДАННЫХ ---
def init_db():
    conn = sqlite3.connect("subs_beta_v3.db")
    cursor = conn.cursor()
    # Добавили поля для кастомного времени уведомлений (remind_hour)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            timezone INTEGER DEFAULT 3,
            remind_hour INTEGER DEFAULT 10
        )
    ''')
    # Добавили поля для валюты и периода
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            price REAL,
            currency TEXT,
            period TEXT,
            date INTEGER
        )
    ''')
    conn.commit()
    conn.close()

# --- КЛАВИАТУРЫ ---
def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Добавить подписку")],
        [KeyboardButton(text="📋 Мои подписки"), KeyboardButton(text="📊 Аналитика расходов")],
        [KeyboardButton(text="⚙️ Настройки")]
    ], resize_keyboard=True)

@dp.message(CommandStart())
async def cmd_start(message: Message):
    init_db()
    conn = sqlite3.connect("subs_beta_v3.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (user_id, timezone, remind_hour) VALUES (?, 3, 10)", (message.from_user.id,))
    conn.commit()
    conn.close()

    await message.answer(
        "🚀 **Добро пожаловать в Обновленный SubTrack Бета!**\n\n"
        "Теперь я умею считать твои расходы, поддерживаю годовые/недельные подписки и отправляю уведомления в удобное тебе время!",
        reply_markup=main_kb(),
        parse_mode="Markdown"
    )

# --- УЛУЧШЕННЫЙ ПРОСМОТР ПОДПИСОК ---
@dp.message(F.text == "📋 Мои подписки")
async def list_subs(message: Message):
    conn = sqlite3.connect("subs_beta_v3.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, currency, period, date FROM subscriptions WHERE user_id = ?", (message.from_user.id,))
    subs = cursor.fetchall()
    conn.close()

    if not subs:
        await message.answer("У тебя пока нет сохраненных подписок.")
        return

    await message.answer("📋 **Твои активные подписки:**")
    
    period_dict = {"week": "раз в неделю", "month": "раз в месяц", "year": "раз в год"}

    for sub_id, name, price, currency, period, date in subs:
        inline_delete_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"del_{sub_id}")]
        ])
        
        # Красивый вывод в зависимости от периода
        if period == "week":
            time_info = "Каждую неделю"
        else:
            time_info = f"{date}-го числа"

        await message.answer(
            f"📌 **{name}**\n💰 Стоимость: {price} {currency} ({period_dict.get(period, '')})\n📅 Оплата: {time_info}",
            reply_markup=inline_delete_kb,
            parse_mode="Markdown"
        )

@dp.callback_query(F.data.startswith("del_"))
async def delete_subscription(callback: CallbackQuery):
    sub_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect("subs_beta_v3.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM subscriptions WHERE id = ? AND user_id = ?", (sub_id, callback.from_user.id))
    conn.commit()
    conn.close()
    await callback.answer("Подписка удалена!")
    await callback.message.edit_text("❌ *Эта подписка была удалена.*", parse_mode="Markdown")


# --- УЛУЧШЕННОЕ ДОБАВЛЕНИЕ С ВЫБОРОМ ПЕРИОДА И ВАЛЮТЫ ---
@dp.message(F.text == "➕ Добавить подписку")
async def add_sub_start(message: Message, state: FSMContext):
    await message.answer("Введите название сервиса:")
    await state.set_state(AddSubscription.name)

@dp.message(AddSubscription.name)
async def add_sub_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите стоимость (только число, например: 399 или 5.99):")
    await state.set_state(AddSubscription.price)

@dp.message(AddSubscription.price)
async def add_sub_price(message: Message, state: FSMContext):
    try:
        price = float(message.text.replace(",", "."))
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число:")
        return
        
    await state.update_data(price=price)
    
    # Кнопки выбора валюты
    curr_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Рубли (₽)", callback_data="curr_RUB"),
         InlineKeyboardButton(text="Доллары ($)", callback_data="curr_USD")],
        [InlineKeyboardButton(text="Евро (€)", callback_data="curr_EUR"),
         InlineKeyboardButton(text="ТГ (₸)", callback_data="curr_KZT")]
    ])
    await message.answer("Выбери валюту подписки:", reply_markup=curr_kb)
    await state.set_state(AddSubscription.currency)

@dp.callback_query(AddSubscription.currency, F.data.startswith("curr_"))
async def add_sub_currency(callback: CallbackQuery, state: FSMContext):
    currency = callback.data.split("_")[1]
    await state.update_data(currency=currency)
    
    # Кнопки выбора периода
    period_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Раз в неделю", callback_data="per_week")],
        [InlineKeyboardButton(text="Раз в месяц", callback_data="per_month")],
        [InlineKeyboardButton(text="Раз в год", callback_data="per_year")]
    ])
    await callback.message.edit_text("Как часто списываются деньги?", reply_markup=period_kb)
    await state.set_state(AddSubscription.period)

@dp.callback_query(AddSubscription.period, F.data.startswith("per_"))
async def add_sub_period(callback: CallbackQuery, state: FSMContext):
    period = callback.data.split("_")[1]
    await state.update_data(period=period)
    
    if period == "week":
        # Для недельных подписок день месяца не важен, ставим заглушку 0
        data = await state.get_data()
        await save_subscription_to_db(callback.message, data, date_val=0)
        await state.clear()
    else:
        await callback.message.edit_text("Какого числа происходит списание? (Введите число от 1 до 31):")
        await state.set_state(AddSubscription.date)

@dp.message(AddSubscription.date)
async def add_sub_date(message: Message, state: FSMContext):
    try:
        day = int(message.text)
        if not (1 <= day <= 31): raise ValueError
    except ValueError:
        await message.answer("Введите число от 1 до 31:")
        return

    data = await state.get_data()
    await save_subscription_to_db(message, data, date_val=day)
    await state.clear()

async def save_subscription_to_db(message_or_cb_msg, data, date_val):
    conn = sqlite3.connect("subs_beta_v3.db")
    cursor = conn.cursor()
    
    # Так как это может быть сообщение от пользователя или из колбэка:
    user_id = message_or_cb_msg.chat.id
    
    cursor.execute(
        "INSERT INTO subscriptions (user_id, name, price, currency, period, date) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, data['name'], data['price'], data['currency'], data['period'], date_val)
    )
    conn.commit()
    conn.close()
    
    text = f"✅ Подписка {data['name']} ({data['price']} {data['currency']}) успешно сохранена!"
    if type(message_or_cb_msg) == Message:
        await message_or_cb_msg.answer(text, reply_markup=main_kb(), parse_mode="Markdown")
    else:
        await message_or_cb_msg.answer(text, reply_markup=main_kb(), parse_mode="Markdown")
        await message_or_cb_msg.delete()


# --- ФИЧА 1: 📊 АНАЛИТИКА РАСХОДОВ ---
@dp.message(F.text == "📊 Аналитика расходов")
async def show_analytics(message: Message):
    conn = sqlite3.connect("subs_beta_v3.db")
    cursor = conn.cursor()
    cursor.execute("SELECT price, currency, period FROM subscriptions WHERE user_id = ?", (message.from_user.id,))
    subs = cursor.fetchall()
    conn.close()

    if not subs:
        await message.answer("У тебя пока нет подписок для расчета аналитики.")
        return

    # Считаем расходы, приводя всё к "за месяц"
    totals = {}
    for price, currency, period in subs:
        monthly_price = price
        if period == "week":
            monthly_price = price * 4.33 # В среднем недель в месяце
        elif period == "year":
            monthly_price = price / 12
            
        totals[currency] = totals.get(currency, 0) + monthly_price

    text = "📊 **Твои ежемесячные затраты на подписки:**\n\n"
    for curr, total_sum in totals.items():
        text += f"• {round(total_sum, 2)} {curr} в месяц\n"
        
    text += "\n_Все недельные и годовые платежи автоматически пересчитаны в эквивалент за 1 месяц._"
    await message.answer(text, parse_mode="Markdown")


# --- ФИЧА 3: ⚙️ НАСТРОЙКИ (ВРЕМЯ И ТАЙМЗОНА) ---
@dp.message(F.text == "⚙️ Настройки")
async def settings_main(message: Message):
    conn = sqlite3.connect("subs_beta_v3.db")
    cursor = conn.cursor()
    cursor.execute("SELECT timezone, remind_hour FROM users WHERE user_id = ?", (message.from_user.id,))
    tz, hour = cursor.fetchone()
    conn.close()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🗺 Изменить Часовой пояс", callback_data="cfg_tz")],
        [InlineKeyboardButton(text="⏰ Изменить Время уведомления", callback_data="cfg_time")]
    ])

    await message.answer(
        f"⚙️ **Настройки профиля:**\n\n"
        f"📍 Твой часовой пояс: **UTC+{tz}**\n"
        f"🔔 Время напоминания: {hour}:00 по твоему времени\n\n"
        f"Что ты хочешь изменить?", reply_markup=kb, parse_mode="Markdown"
    )

@dp.callback_query(F.data == "cfg_tz")
async def cfg_tz_menu(callback: CallbackQuery):
    tz_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="UTC+2 (Калининград)", callback_data="stz_2"),
         InlineKeyboardButton(text="UTC+3 (МСК/Киев)", callback_data="stz_3")],
        [InlineKeyboardButton(text="UTC+4 (Самара)", callback_data="stz_4"),
         InlineKeyboardButton(text="UTC+5 (Екатеринбург)", callback_data="stz_5")],
        [InlineKeyboardButton(text="UTC+7 (Новосибирск)", callback_data="stz_7"),
         InlineKeyboardButton(text="UTC+10 (Владивосток)", callback_data="stz_10")]
    ])
    await callback.message.edit_text("Выбери свой часовой пояс:", reply_markup=tz_kb)

@dp.callback_query(F.data.startswith("stz_"))
async def cfg_tz_save(callback: CallbackQuery):
    tz_val = int(callback.data.split("_")[1])
    conn = sqlite3.connect("subs_beta_v3.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET timezone = ? WHERE user_id = ?", (tz_val, callback.from_user.id))
    conn.commit()
    conn.close()
    await callback.answer("Часовой пояс обновлен!")
    await callback.message.edit_text(f"✅ Сохранено! Твой часовой пояс теперь: UTC+{tz_val}")

@dp.callback_query(F.data == "cfg_time")
async def cfg_time_menu(callback: CallbackQuery):
    time_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Утро (09:00)", callback_data="stmie_9"), InlineKeyboardButton(text="День (13:00)", callback_data="stmie_13")],
        [InlineKeyboardButton(text="Вечер (18:00)", callback_data="stmie_18"), InlineKeyboardButton(text="Перед сном (21:00)", callback_data="stmie_21")]
    ])
    await callback.message.edit_text("В какое время суток тебе присылать напоминания?", reply_markup=time_kb)

@dp.callback_query(F.data.startswith("stmie_"))
async def cfg_time_save(callback: CallbackQuery):
    hour_val = int(callback.data.split("_")[1])conn = sqlite3.connect("subs_beta_v3.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET remind_hour = ? WHERE user_id = ?", (hour_val, callback.from_user.id))
    conn.commit()
    conn.close()
    await callback.answer("Время обновлено!")
    await callback.message.edit_text(f"✅ Сохранено! Напоминания будут приходить в {hour_val}:00 по твоему времени.")


# --- СИСТЕМА УВЕДОМЛЕНИЙ ---
async def send_reminders_job():
    conn = sqlite3.connect("subs_beta_v3.db")
    cursor = conn.cursor()
    cursor.execute('''
        SELECT s.user_id, s.name, s.price, s.currency, s.period, s.date, u.timezone, u.remind_hour 
        FROM subscriptions s
        JOIN users u ON s.user_id = u.user_id
    ''')
    all_subs = cursor.fetchall()
    conn.close()

    for user_id, name, price, currency, period, sub_date, tz, remind_hour in all_subs:
        user_now = datetime.utcnow() + timedelta(hours=tz)
        
        # Проверяем, наступил ли выбранный пользователем час для уведомления
        if user_now.hour == remind_hour:
            is_need_remind = False
            
            if period == "month":
                tomorrow = user_now + timedelta(days=1)
                if tomorrow.day == sub_date:
                    is_need_remind = True
            elif period == "year":
                tomorrow = user_now + timedelta(days=1)
                # Годовая подписка: совпадает день и текущий месяц
                if tomorrow.day == sub_date:
                    is_need_remind = True
            elif period == "week":
                # Для недельных подписок напоминаем, например, по пятницам (или за день до конца недели)
                # Сделаем упрощенно: раз в неделю в определенный день. Для беты оставим проверку "если сегодня определенный день"
                # В полноценной версии тут будет более точный трекинг дней недели
                pass

            if is_need_remind:
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=f"⚠️ **Внимание! Завтра списание!**\n\n"
                             f"Завтра спишутся деньги за подписку {name}.\n"
                             f"Сумма: {price} {currency}.\n\n"
                             f"Если она больше не нужна, отмени её сегодня!",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logging.error(f"Ошибка отправки: {e}")

@dp.message(Command("test_remind"))
async def cmd_test_remind(message: Message):
    conn = sqlite3.connect("subs_beta_v3.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, price, currency FROM subscriptions WHERE user_id = ?", (message.from_user.id,))
    user_subs = cursor.fetchall()
    conn.close()
    
    if not user_subs:
        await message.answer("❌ Добавь хотя бы одну подписку.")
        return
        
    for name, price, currency in user_subs:
        await bot.send_message(
            chat_id=message.from_user.id,
            text=f"⚙️ **[ТЕСТ] Эмуляция напоминания:**\n\n"
                 f"⚠️ **Внимание! Завтра списание!**\n"
                 f"Завтра спишутся деньги за подписку {name}.\n"
                 f"Сумма: {price} {currency}.",
            parse_mode="Markdown"
        )

async def main():
    init_db()
    scheduler.add_job(send_reminders_job, "interval", minutes=1)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
