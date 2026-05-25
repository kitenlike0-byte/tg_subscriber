import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Настройка логирования и токена
logging.basicConfig(level=logging.INFO)
TOKEN = "8910227751:AAH22yGJzyiQ67hg60fiimLUCUHfO25iMRQ"  # Замени на свой токен от @BotFather

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Стейты для создания подписки
class AddSubscription(StatesGroup):
    name = State()
    price = State()
    date = State()

# Инициализация простой БД
def init_db():
    conn = sqlite3.connect("subs.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            price TEXT,
            date TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Клавиатура
def main_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Добавить подписку")],
        [KeyboardButton(text="📋 Мои подписки"), KeyboardButton(text="💎 Отключить рекламу")]
    ], resize_keyboard=True)

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я помогу тебе контролировать твои подписки (Netflix, VPN, Яндекс и др.) "
        "и вовремя напоминать о списаниях, чтобы ты не терял деньги.",
        reply_markup=main_kb()
    )

# --- ПРОСМОТР ПОДПИСОК ---
@dp.message(F.text == "📋 Мои подписки")
async def list_subs(message: Message):
    conn = sqlite3.connect("subs.db")
    cursor = conn.cursor()
    cursor.execute("SELECT name, price, date FROM subscriptions WHERE user_id = ?", (message.from_user.id,))
    subs = cursor.fetchall()
    conn.close()

    if not subs:
        await message.answer("У тебя пока нет добавленных подписок. Нажми '➕ Добавить подписку'.")
        return

    text = "🔔 **Твои активные подписки:**\n\n"
    for name, price, date in subs:
        text += f"• {name} — {price} (Списание: {date}-го числа)\n"
    
    # Имитация рекламы для бесплатных пользователей
    text += "\n---\n⚡ *Реклама: Купи Премиум за $1, чтобы отключить рекламу и разблокировать уведомления!*"
    
    await message.answer(text, parse_mode="Markdown")

# --- ДОБАВЛЕНИЕ ПОДПИСКИ (FSM) ---
@dp.message(F.text == "➕ Добавить подписку")
async def add_sub_start(message: Message, state: FSMContext):
    await message.answer("Введите название сервиса (например: Netflix, VPN):")
    await state.set_state(AddSubscription.name)

@dp.message(AddSubscription.name)
async def add_sub_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Введите стоимость (например: 499 руб или $10):")
    await state.set_state(AddSubscription.price)

@dp.message(AddSubscription.price)
async def add_sub_price(message: Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("Какого числа каждого месяца происходит списание? (Введите только число от 1 до 31):")
    await state.set_state(AddSubscription.date)

@dp.message(AddSubscription.date)
async def add_sub_date(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    name = data['name']
    price = data['price']
    date = message.text

    # Сохраняем в БД
    conn = sqlite3.connect("subs.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO subscriptions (user_id, name, price, date) VALUES (?, ?, ?, ?)",
                   (user_id, name, price, date))
    conn.commit()
    conn.close()

    await state.clear()
    await message.answer(f"✅ Подписка {name} успешно добавлена!", reply_markup=main_kb(), parse_mode="Markdown")

# --- МОНЕТИЗАЦИЯ ---
@dp.message(F.text == "💎 Отключить рекламу")
async def premium_info(message: Message):
    await message.answer(
        "🌟 **Премиум-режим всего за $1 / месяц**\n\n"
        "Что вы получите:\n"
        "1.Полное отключение рекламы.\n"
        "2. Уведомления за 1 и 3 дня до списания (в Telegram).\n"
        "3. Безлимитное количество подписок (сейчас лимит 3).\n\n"
        "Для оплаты напишите админу: @твой_юзернейм (или используйте кнопку оплаты, когда настроите Telegram Pay)",
        parse_mode="Markdown"
    )

async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
