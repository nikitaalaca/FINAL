import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties  # ✅ ОБЯЗАТЕЛЬНО
from dotenv import load_dotenv

import db
from parser import get_v2_keys, validate_v2_key
from keep_alive import keep_alive

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")

# ✅ Новый синтаксис создания бота
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())

# 🧾 Клавиатуры
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

# 🟢 Старт
@dp.message(F.text == "/start")
async def start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    args = message.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    db.add_user(user_id, username, referral_from=ref_id)

    is_admin = (username == ADMIN_USERNAME)
    kb = user_keyboard(is_admin)
    await message.answer("👋 Привет! Добро пожаловать в бота.", reply_markup=kb)

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
            db.update_until(call.from_user.id, "2025-12-31")  # пример даты
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
async def balance(call: types.CallbackQuery):
    balance = db.get_balance(call.from_user.id)
    await call.message.answer(f"💰 Текущий баланс: <b>{balance}₽</b>\nНапиши админу @{ADMIN_USERNAME} для пополнения.")

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
    msg = "\n".join([f"👤 {u[1]} | {u[0]} | {u[5] or '-'}" for u in users])
    await call.message.answer(f"<b>Все пользователи:</b>\n{msg or 'Нет пользователей.'}")

@dp.callback_query(F.data == "back")
async def back(call: types.CallbackQuery):
    is_admin = (call.from_user.username == ADMIN_USERNAME)
    await call.message.answer("↩️ Возвращаюсь...", reply_markup=user_keyboard(is_admin))

# 🚀 Старт бота
async def main():
    keep_alive()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
