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

import db
from parser import get_v2_keys, validate_v2_key
from keep_alive import keep_alive

# Загружаем переменные из .env
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# Reply-меню (в стиле GEMERA)
main_reply_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🏠 Главное меню")],
        [KeyboardButton(text="👤 Личный кабинет")],
        [KeyboardButton(text="❓ Помощь в подключении")],
        [KeyboardButton(text="💳 Оплата")]
    ],
    resize_keyboard=True
)

# Inline-клавиатура пользователя
def user_keyboard(is_admin=False):
    kb = InlineKeyboardBuilder()
    kb.button(text="💠 Установить V2", callback_data="install_v2")
    kb.button(text="♻️ Обновить ключ", callback_data="update_key")
    kb.button(text="💰 Баланс", callback_data="balance")
    kb.button(text="👥 Рефералы", callback_data="referrals")
    if is_admin:
        kb.button(text="⚙️ Админка", callback_data="admin_menu")
    return kb.adjust(2).as_markup()

# Админ-клавиатура
def admin_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Все пользователи", callback_data="all_users")
    kb.button(text="⬅️ Назад", callback_data="back")
    return kb.as_markup()

# /start
@dp.message(F.text == "/start")
async def start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    args = message.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    db.add_user(user_id, username, referral_from=ref_id)

    is_admin = (username == ADMIN_USERNAME)
    await message.answer("👋 Привет! Добро пожаловать в бота.", reply_markup=main_reply_menu)

# /profile
@dp.message(F.text == "/profile")
async def profile(message: Message):
    user = db.get_user(message.from_user.id)
    balance = db.get_balance(message.from_user.id)
    until = user[5] if user else "-"
    await message.answer(f"👤 <b>Профиль:</b>\n💸 Баланс: {balance}₽\n📅 Подписка до: {until}")

# Установить V2
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

# Обновить ключ
@dp.callback_query(F.data == "update_key")
async def update_key(call: types.CallbackQuery):
    key = db.get_active_key()
    if key:
        await call.message.answer(f"🔄 Обновлённый ключ:\n<code>{key}</code>")
    else:
        await call.message.answer("❌ Нет доступных ключей")

# Баланс
@dp.callback_query(F.data == "balance")
async def balance(call: types.CallbackQuery):
    balance = db.get_balance(call.from_user.id)
    await call.message.answer(f"💰 Баланс: <b>{balance}₽</b>\nНапиши админу @{ADMIN_USERNAME} для пополнения.")

# Рефералы
@dp.callback_query(F.data == "referrals")
async def referrals(call: types.CallbackQuery):
    user_id = call.from_user.id
    link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    await call.message.answer(f"👥 Твоя реферальная ссылка:\n{link}\n🔁 За каждого друга — 100₽!")

# Админ-панель
@dp.callback_query(F.data == "admin_menu")
async def admin_menu(call: types.CallbackQuery):
    await call.message.answer("⚙️ Админ-панель", reply_markup=admin_keyboard())

@dp.callback_query(F.data == "all_users")
async def all_users(call: types.CallbackQuery):
    users = db.get_all_users()
    msg = "\n".join([f"👤 {u[1]} | {u[0]} | {u[5] or '-'}" for u in users])
    await call.message.answer(f"<b>Все пользователи:</b>\n{msg or 'Нет пользователей.'}")

@dp.callback_query(F.data == "back")
async def back(call: types.CallbackQuery):
    is_admin = (call.from_user.username == ADMIN_USERNAME)
    await call.message.answer("↩️ Возвращаюсь...", reply_markup=user_keyboard(is_admin))

# 🆕 Новые функции с reply-кнопками
@dp.message(F.text == "🏠 Главное меню")
async def reply_main_menu(message: Message):
    is_admin = (message.from_user.username == ADMIN_USERNAME)
    await message.answer("🏠 Главное меню", reply_markup=user_keyboard(is_admin))

@dp.message(F.text == "👤 Личный кабинет")
async def reply_profile_button(message: Message):
    user = db.get_user(message.from_user.id)
    balance = db.get_balance(message.from_user.id)
    until = user[5] if user else "-"
    await message.answer(f"👤 <b>Профиль:</b>\n💸 Баланс: {balance}₽\n📅 Подписка до: {until}")

@dp.message(F.text == "❓ Помощь в подключении")
async def reply_help(message: Message):
    await message.answer(
        "📥 Скачать V2ray:\n"
        "https://apps.apple.com/ru/app/v2box-v2ray-client/id6446814690\n\n"
        "1. Получи ключ через меню\n"
        "2. Вставь в приложение\n"
        "3. Подключайся — готово!"
    )

@dp.message(F.text == "💳 Оплата")
async def reply_payment(message: Message):
    await message.answer(
        "💳 <b>Тарифы:</b>\n"
        "1 месяц — 300₽\n"
        "3 месяца — 800₽\n"
        "12 месяцев — 2500₽\n\n"
        f"📨 Напиши админу: @{ADMIN_USERNAME} для пополнения"
    )

# 🚀 Запуск
async def main():
    keep_alive()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
