import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv
from datetime import datetime, timedelta

import db
from parser import get_v2_keys, validate_v2_key
from keep_alive import keep_alive

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# 📲 Главное меню
main_reply_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏠 Главное меню")],
        [KeyboardButton(text="👤 Личный кабинет")],
        [KeyboardButton(text="❓ Помощь в подключении")],
        [KeyboardButton(text="💳 Оплата")]
    ],
    resize_keyboard=True
)

# 🔘 Инлайн-кнопки пользователя
def user_keyboard(is_admin=False):
    kb = InlineKeyboardBuilder()
    kb.button(text="💠 Установить V2", callback_data="install_v2")
    kb.button(text="♻️ Обновить ключ", callback_data="update_key")
    kb.button(text="💰 Баланс", callback_data="balance")
    kb.button(text="👥 Рефералы", callback_data="referrals")
    if is_admin:
        kb.button(text="⚙️ Админка", callback_data="admin_menu")
    return kb.adjust(2).as_markup()

# 🔘 Инлайн-кнопки админа
def admin_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Все пользователи", callback_data="all_users")
    kb.button(text="⬅️ Назад", callback_data="back")
    return kb.as_markup()

# 📆 Вычисление срока подписки
def extend_subscription(days: int):
    today = datetime.today()
    return (today + timedelta(days=days)).strftime("%Y-%m-%d")

# 🚀 /start
@dp.message(F.text == "/start")
async def start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    args = message.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    is_new = db.add_user(user_id, username, referral_from=ref_id)
    if is_new and ref_id and ref_id != user_id:
        db.update_balance(ref_id, +100)

    is_admin = (username == ADMIN_USERNAME)
    await message.answer("👋 Привет! Добро пожаловать в бота.", reply_markup=main_reply_menu)

# 👤 Профиль
@dp.message(F.text == "/profile")
async def profile(message: Message):
    user = db.get_user(message.from_user.id)
    balance = db.get_balance(message.from_user.id)
    until = user[5] if user else "-"
    await message.answer(f"👤 <b>Профиль:</b>\n💸 Баланс: {balance}₽\n📅 Подписка до: {until}")

# 💠 Установить V2
@dp.callback_query(F.data == "install_v2")
async def install_v2(call: types.CallbackQuery):
    keys = get_v2_keys()
    for key in keys:
        if validate_v2_key(key):
            db.add_key(key)
            db.update_until(call.from_user.id, "2025-12-31")
            await call.message.answer(f"🔑 Твой V2 ключ:\n<code>{key}</code>")
            return
    await call.message.answer("❌ Нет доступных ключей")

# ♻️ Обновить ключ
@dp.callback_query(F.data == "update_key")
async def update_key(call: types.CallbackQuery):
    key = db.get_active_key()
    if key:
        await call.message.answer(f"🔄 Обновлённый ключ:\n<code>{key}</code>")
    else:
        await call.message.answer("❌ Нет доступных ключей")

# 💰 Баланс
@dp.callback_query(F.data == "balance")
async def balance_menu(call: types.CallbackQuery):
    balance = db.get_balance(call.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Оплатить подписку (1 мес)", callback_data="pay_with_balance")],
        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="topup_info")]
    ])
    await call.message.answer(f"💰 Баланс: <b>{balance}₽</b>", reply_markup=kb)

# 💳 Пополнить баланс (инфо)
@dp.callback_query(F.data == "topup_info")
async def topup_info(call: types.CallbackQuery):
    await call.message.answer(f"📨 Напиши админу @{ADMIN_USERNAME} для пополнения")

# 💸 Оплата 1 мес с баланса
@dp.callback_query(F.data == "pay_with_balance")
async def pay_with_balance(call: types.CallbackQuery):
    user_id = call.from_user.id
    price = 300
    balance = db.get_balance(user_id)
    if balance >= price:
        db.update_balance(user_id, -price)
        db.update_until(user_id, extend_subscription(30))
        await call.message.answer("✅ Подписка активирована на 1 месяц!")
    else:
        await call.message.answer("❌ Недостаточно средств.")

# 💳 Меню тарифов
@dp.message(F.text == "💳 Оплата")
async def reply_payment(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕐 1 месяц — 300₽", callback_data="sub_1m")],
        [InlineKeyboardButton(text="🗓 3 месяца — 800₽", callback_data="sub_3m")],
        [InlineKeyboardButton(text="📅 12 месяцев — 2500₽", callback_data="sub_12m")]
    ])
    await message.answer("💳 Выберите тариф:", reply_markup=kb)

# ✅ Обработка покупки тарифа
@dp.callback_query(F.data.startswith("sub_"))
async def handle_subscription(call: types.CallbackQuery):
    user_id = call.from_user.id
    price_map = {
        "sub_1m": (300, 30),
        "sub_3m": (800, 90),
        "sub_12m": (2500, 365)
    }
    price, days = price_map[call.data]
    balance = db.get_balance(user_id)
    if balance < price:
        await call.message.answer("❌ Недостаточно средств на балансе.")
        return
    db.update_balance(user_id, -price)
    new_until = extend_subscription(days)
    db.update_until(user_id, new_until)
    await call.message.answer(f"✅ Подписка оформлена до {new_until}!\nСписано {price}₽ с баланса.")

# 👥 Рефералы
@dp.callback_query(F.data == "referrals")
async def referrals(call: types.CallbackQuery):
    user_id = call.from_user.id
    link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    await call.message.answer(f"👥 Твоя реферальная ссылка:\n{link}\n🔁 За каждого друга — 100₽!")

# ⚙️ Админка
@dp.callback_query(F.data == "admin_menu")
async def admin_menu(call: types.CallbackQuery):
    await call.message.answer("⚙️ Админ-панель", reply_markup=admin_keyboard())

@dp.callback_query(F.data == "all_users")
async def all_users(call: types.CallbackQuery):
    users = db.get_all_users()
    msg = "\n".join([f"👤 {u[1]} | id: {u[0]} | {u[5] or '-'}" for u in users])
    await call.message.answer(f"<b>Все пользователи:</b>\n{msg or 'Нет пользователей.'}")

@dp.callback_query(F.data == "back")
async def back(call: types.CallbackQuery):
    is_admin = (call.from_user.username == ADMIN_USERNAME)
    await call.message.answer("↩️ Возвращаюсь...", reply_markup=user_keyboard(is_admin))

# 🏠 Главное меню
@dp.message(F.text == "🏠 Главное меню")
async def reply_main_menu(message: Message):
    is_admin = (message.from_user.username == ADMIN_USERNAME)
    await message.answer("🏠 Главное меню", reply_markup=user_keyboard(is_admin))

# 👤 Кабинет
@dp.message(F.text == "👤 Личный кабинет")
async def reply_profile_button(message: Message):
    user = db.get_user(message.from_user.id)
    balance = db.get_balance(message.from_user.id)
    until = user[5] if user else "-"
    await message.answer(f"👤 <b>Профиль:</b>\n💸 Баланс: {balance}₽\n📅 Подписка до: {until}")

# ❓ Помощь
@dp.message(F.text == "❓ Помощь в подключении")
async def reply_help(message: Message):
    await message.answer(
        "📥 Скачать V2ray:\n"
        "https://apps.apple.com/ru/app/v2box-v2ray-client/id6446814690\n\n"
        "1. Получи ключ через меню\n"
        "2. Вставь в приложение\n"
        "3. Подключайся — готово!"
    )

# 🔧 Админ: пополнение баланса
@dp.message(F.text.startswith("/admin_balance"))
async def admin_balance_cmd(message: Message):
    if message.from_user.username != ADMIN_USERNAME:
        return
    try:
        _, uid, amount = message.text.strip().split()
        db.update_balance(int(uid), int(amount))
        await message.answer(f"✅ Пополнено: {amount}₽ → {uid}")
    except Exception:
        await message.answer("⚠️ Используй: /admin_balance user_id сумма")

# 🔧 Админ: список пользователей
@dp.message(F.text == "/admin_users")
async def admin_users_cmd(message: Message):
    if message.from_user.username != ADMIN_USERNAME:
        return
    users = db.get_all_users()
    text = "\n".join([f"👤 {u[1]} | id: {u[0]} | ₿ {db.get_balance(u[0])}₽ | до: {u[5] or '-'}" for u in users])
    await message.answer(text or "Нет пользователей")

from aiogram.types import BotCommand, BotCommandScopeDefault, MenuButtonCommands

async def set_bot_commands():
    commands = [
        BotCommand(command="start", description="🔹 Главное меню"),
        BotCommand(command="profile", description="👤 Личный кабинет"),
        BotCommand(command="help", description="❓ Помощь в подключении"),
        BotCommand(command="admin_users", description="📊 Пользователи (админ)"),
        BotCommand(command="admin_balance", description="💰 Пополнение (админ)")
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

# 🚀 Запуск
async def main():
    keep_alive()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
