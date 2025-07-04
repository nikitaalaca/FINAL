import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    BotCommand, BotCommandScopeDefault, MenuButtonCommands
)
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

main_reply_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏠 Главное меню")],
        [KeyboardButton(text="👤 Личный кабинет")],
        [KeyboardButton(text="❓ Помощь в подключении")],
        [KeyboardButton(text="💳 Оплата")]
    ],
    resize_keyboard=True
)

def user_keyboard(is_admin=False):
    kb = InlineKeyboardBuilder()
    kb.button(text="💠 Установить V2", callback_data="install_v2")
    kb.button(text="♻️ Обновить ключ", callback_data="update_key")
    kb.button(text="💰 Баланс", callback_data="balance")
    kb.button(text="👥 Рефералы", callback_data="referrals")
    if is_admin:
        kb.button(text="⚙️ Админка", callback_data="admin_menu")
    return kb.adjust(2).as_markup()

def admin_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Все пользователи", callback_data="all_users")
    kb.button(text="⬅️ Назад", callback_data="back")
    return kb.as_markup()

def extend_subscription(days: int):
    return (datetime.today() + timedelta(days=days)).strftime("%Y-%m-%d")

def check_subscription_expiry(user_id):
    user = db.get_user(user_id)
    if not user:
        return False
    until = user[5]
    if not until:
        return False
    today = datetime.today().date()
    try:
        exp = datetime.strptime(until, "%Y-%m-%d").date()
        if today > exp:
            db.set_inactive(user_id)
            return False
        return True
    except:
        return False

@dp.message(F.text == "/start")
async def start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    args = message.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    is_new = db.add_user(user_id, username, referral_from=ref_id)
    check_subscription_expiry(user_id)

    await message.answer("👋 Привет! Добро пожаловать в бота.", reply_markup=main_reply_menu)

@dp.message(F.text == "/profile")
async def profile(message: Message):
    user = db.get_user(message.from_user.id)
    balance = db.get_balance(message.from_user.id)
    until = user[5] if user else "-"
    key = db.get_user_key(message.from_user.id)
    text = f"👤 <b>Профиль:</b>\n💸 Баланс: {balance}₽\n📅 Подписка до: {until}"
    if key:
        text += f"\n🔑 Ключ: <code>{key}</code>"
    await message.answer(text)

@dp.callback_query(F.data == "install_v2")
async def install_v2(call: types.CallbackQuery):
    user_id = call.from_user.id
    user = db.get_user(user_id)

    check_subscription_expiry(user_id)

    if not db.is_user_active(user_id):
        if not user[4]:
            keys = get_v2_keys()
            for k in keys:
                if validate_v2_key(k):
                    db.add_key(k)
                    db.update_until(user_id, extend_subscription(3))
                    db.set_trial_used(user_id)
                    db.assign_key_to_user(user_id, k)
                    await call.message.answer(f"🧪 Пробный ключ (3 дня):\n<code>{k}</code>")
                    return
            await call.message.answer("❌ Нет ключей.")
        else:
            await call.message.answer("⚠️ Пробник уже использован. Оформи подписку.")
    else:
        key = db.get_user_key(user_id)
        await call.message.answer(f"🔑 Твой ключ:\n<code>{key}</code>")

@dp.callback_query(F.data == "update_key")
async def update_key(call: types.CallbackQuery):
    key = db.get_user_key(call.from_user.id)
    if key:
        await call.message.answer(f"🔁 Твой ключ:\n<code>{key}</code>")
    else:
        await call.message.answer("❌ У тебя нет ключа.")

@dp.callback_query(F.data == "balance")
async def balance_menu(call: types.CallbackQuery):
    balance = db.get_balance(call.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Оплатить подписку (1 мес)", callback_data="pay_with_balance")],
        [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="topup_info")]
    ])
    await call.message.answer(f"💰 Баланс: <b>{balance}₽</b>", reply_markup=kb)

@dp.callback_query(F.data == "topup_info")
async def topup_info(call: types.CallbackQuery):
    await call.message.answer(f"📨 Напиши админу @{ADMIN_USERNAME} для пополнения")

@dp.callback_query(F.data == "pay_with_balance")
async def pay_with_balance(call: types.CallbackQuery):
    user_id = call.from_user.id
    price = 300
    balance = db.get_balance(user_id)
    if balance >= price:
        db.update_balance(user_id, -price, "Покупка подписки")
        db.update_until(user_id, extend_subscription(30))
        await call.message.answer("✅ Подписка активирована на 30 дней!")
    else:
        await call.message.answer("❌ Недостаточно средств.")

@dp.message(F.text == "💳 Оплата")
async def reply_payment(message: Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕐 1 месяц — 300₽", callback_data="sub_1m")],
        [InlineKeyboardButton(text="🗓 3 месяца — 800₽", callback_data="sub_3m")],
        [InlineKeyboardButton(text="📅 12 месяцев — 2500₽", callback_data="sub_12m")]
    ])
    await message.answer("💳 Выберите тариф:", reply_markup=kb)

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
        await call.message.answer("❌ Недостаточно средств.")
        return
    db.update_balance(user_id, -price, f"Подписка на {days} дней")
    db.update_until(user_id, extend_subscription(days))
    await call.message.answer(f"✅ Подписка до {extend_subscription(days)}!\nСписано {price}₽.")

@dp.callback_query(F.data == "referrals")
async def referrals(call: types.CallbackQuery):
    user_id = call.from_user.id
    link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    await call.message.answer(f"👥 Твоя ссылка:\n{link}\n🔁 За друга — 100₽!")

@dp.callback_query(F.data == "admin_menu")
async def admin_menu(call: types.CallbackQuery):
    await call.message.answer("⚙️ Админ-панель", reply_markup=admin_keyboard())

@dp.callback_query(F.data == "all_users")
async def all_users(call: types.CallbackQuery):
    users = db.get_all_users()
    msg = "\n".join([f"👤 {u[1]} | id: {u[0]} | до: {u[5] or '-'}" for u in users])
    await call.message.answer(f"<b>Все пользователи:</b>\n{msg or 'Нет пользователей.'}")

@dp.callback_query(F.data == "back")
async def back(call: types.CallbackQuery):
    is_admin = (call.from_user.username == ADMIN_USERNAME)
    await call.message.answer("↩️ Назад", reply_markup=user_keyboard(is_admin))

@dp.message(F.text == "🏠 Главное меню")
async def reply_main_menu(message: Message):
    is_admin = (message.from_user.username == ADMIN_USERNAME)
    await message.answer("🏠 Главное меню", reply_markup=user_keyboard(is_admin))

@dp.message(F.text == "👤 Личный кабинет")
async def reply_profile_button(message: Message):
    user = db.get_user(message.from_user.id)
    balance = db.get_balance(message.from_user.id)
    until = user[5] if user else "-"
    key = db.get_user_key(message.from_user.id)
    text = f"👤 <b>Профиль:</b>\n💸 Баланс: {balance}₽\n📅 Подписка до: {until}"
    if key:
        text += f"\n🔑 Ключ: <code>{key}</code>"
    await message.answer(text)

@dp.message(F.text == "❓ Помощь в подключении")
async def reply_help(message: Message):
    await message.answer(
        "📥 Скачать V2ray:\n"
        "https://apps.apple.com/ru/app/v2box-v2ray-client/id6446814690\n\n"
        "1. Получи ключ через меню\n"
        "2. Вставь в приложение\n"
        "3. Готово!"
    )

@dp.message(F.text == "/history")
async def user_history(message: Message):
    ops = db.get_user_operations(message.from_user.id)
    if not ops:
        await message.answer("ℹ️ Нет операций.")
        return
    text = "<b>📊 История операций:</b>\n"
    for t, a, c, d in ops:
        sign = "+" if int(a) > 0 else ""
        text += f"{d} — {t}: {sign}{a}₽ ({c})\n"
    await message.answer(text)

@dp.message(F.text.startswith("/admin_balance"))
async def admin_balance_cmd(message: Message):
    if message.from_user.username != ADMIN_USERNAME:
        return
    try:
        _, uid, amount = message.text.strip().split()
        db.update_balance(int(uid), int(amount), "Пополнение (админ)")
        await message.answer(f"✅ {amount}₽ → {uid}")
    except Exception:
        await message.answer("⚠️ /admin_balance user_id сумма")

@dp.message(F.text == "/admin_users")
async def admin_users_cmd(message: Message):
    if message.from_user.username != ADMIN_USERNAME:
        return
    users = db.get_all_users()
    text = "\n".join([
        f"👤 {u[1]} | id: {u[0]} | ₿ {db.get_balance(u[0])}₽ | до: {u[5] or '-'}"
        for u in users
    ])
    await message.answer(text or "Нет пользователей.")

@dp.message(F.text == "/check_all")
async def admin_check_all(message: Message):
    if message.from_user.username != ADMIN_USERNAME:
        return
    count = 0
    users = db.get_all_users()
    for u in users:
        uid = u[0]
        if not check_subscription_expiry(uid):
            count += 1
    await message.answer(f"⛔ Отключено {count} пользователей по окончании подписки.")

@dp.message(F.text == "/stats")
async def admin_stats(message: Message):
    if message.from_user.username != ADMIN_USERNAME:
        return
    users = db.get_all_users()
    total = len(users)
    active = sum(1 for u in users if u[6] == 1)
    total_balance = sum(db.get_balance(u[0]) for u in users)
    avg_balance = total_balance // total if total else 0
    keys_issued = sum(1 for u in users if u[7])
    await message.answer(
        f"<b>📊 Статистика:</b>\n"
        f"👥 Всего пользователей: {total}\n"
        f"✅ Активных: {active}\n"
        f"🔑 С ключами: {keys_issued}\n"
        f"💰 Общий баланс: {total_balance}₽\n"
        f"📈 Средний баланс: {avg_balance}₽"
    )

async def set_bot_commands():
    commands = [
        BotCommand(command="start", description="🔹 Главное меню"),
        BotCommand(command="profile", description="👤 Личный кабинет"),
        BotCommand(command="history", description="📊 История операций"),
        BotCommand(command="check_all", description="⛔ Проверка подписок"),
        BotCommand(command="stats", description="📊 Статистика (админ)"),
        BotCommand(command="admin_users", description="📋 Пользователи (админ)"),
        BotCommand(command="admin_balance", description="💰 Пополнение (админ)")
    ]
    await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())

async def main():
    keep_alive()
    await set_bot_commands()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
