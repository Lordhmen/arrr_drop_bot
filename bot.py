import asyncio
import sqlite3
from io import BytesIO

import qrcode
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from aiogram.utils import executor
from aiogram.utils.exceptions import ChatNotFound, Unauthorized
from pytoniq_core import Address

from config import dp, bot
from connector import get_connector

# Создаем соединение с базой данных
conn = sqlite3.connect('bot.db')
cursor = conn.cursor()

# Создаем таблицу для хранения информации о пользователях, если ее нет
cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                  id INTEGER PRIMARY KEY,
                  username TEXT,
                  first_name TEXT,
                  wallet_address TEXT DEFAULT '',
                  subscribed INTEGER DEFAULT 0,
                  balance INTEGER DEFAULT 100
                )''')
# Создаем таблицу для хранения информации о рефералах
cursor.execute('''CREATE TABLE IF NOT EXISTS referrals (
                  referrer_id INTEGER,
                  referral_id INTEGER,
                  FOREIGN KEY(referrer_id) REFERENCES users(id)
                )''')
conn.commit()


# Обработчик команды /start с аргументом (реферальный идентификатор)
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    # Проверяем, есть ли пользователь в базе данных
    cursor.execute("SELECT id FROM users WHERE id=?", (user_id,))
    user_exists = cursor.fetchone()

    if not user_exists:
        cursor.execute("INSERT INTO users (id, username, first_name) VALUES (?, ?, ?)",
                       (user_id, username, first_name))
        conn.commit()

        # Проверяем, был ли передан реферальный идентификатор в аргументе
        if len(message.get_args()) > 0:
            referrer_id = int(message.get_args())
            # Проверяем, существует ли пользователь с таким реферальным идентификатором
            cursor.execute("SELECT id FROM users WHERE id=?", (referrer_id,))
            referrer_exists = cursor.fetchone()
            if referrer_exists:
                # Если пользователь существует, добавляем информацию о реферале
                cursor.execute("INSERT INTO referrals (referrer_id, referral_id) VALUES (?, ?)", (referrer_id, user_id))
                # Начисляем бонус рефереру
                cursor.execute("UPDATE users SET balance=balance+200 WHERE id=?", (referrer_id,))
                conn.commit()

    await check_subscription_and_send_intro(user_id, message)


@dp.callback_query_handler(lambda query: query.data == 'start_ton_connect')
async def variant_ton_connect(callback_query: types.CallbackQuery):
    await callback_query.answer()
    chat_id = callback_query.message.chat.id
    connector = get_connector(chat_id)
    mk_b = InlineKeyboardMarkup()
    wallets_list = connector.get_wallets()
    for wallet in wallets_list:
        mk_b.add(InlineKeyboardButton(text=wallet['name'], callback_data=f'connect:{wallet["name"]}'))
    await callback_query.message.answer(text='Выберите кошелек для подключения:', reply_markup=mk_b)


async def connect_wallet(message: Message, wallet_name: str):
    connector = get_connector(message.chat.id)

    wallets_list = connector.get_wallets()
    wallet = None

    for w in wallets_list:
        if w['name'] == wallet_name:
            wallet = w

    if wallet is None:
        raise Exception(f'Не известный кошелек: {wallet_name}')

    generated_url = await connector.connect(wallet)

    # Generate QR code
    img = qrcode.make(generated_url)
    qr_code_stream = BytesIO()
    img.save(qr_code_stream, 'PNG')
    qr_code_stream.seek(0)

    await message.answer_photo(qr_code_stream, caption='Отсканируйте этот QR-код, чтобы подключить свой кошелек')

    for i in range(1, 180):
        await asyncio.sleep(1)
        if connector.connected:
            if connector.account.address:
                wallet_address = connector.account.address
                wallet_address = Address(wallet_address).to_str(is_bounceable=False)
                cursor.execute("UPDATE users SET wallet_address=? WHERE id=?", (wallet_address, message.chat.id))
                conn.commit()
                await message.answer(f'Вы успешно подключили адрес <code>{wallet_address}</code>')
            return
    else:
        await message.answer('Вышло время для подключения!')


@dp.callback_query_handler(lambda call: call.data.startswith('connect:'))
async def connect_callback_handler(callback_query: CallbackQuery, state: FSMContext):
    wallet_name = callback_query.data.split(':')[1]
    await connect_wallet(callback_query.message, wallet_name)


# Функция для проверки подписки на канал
async def check_subscription(user_id):
    try:
        chat_member = await bot.get_chat_member("@ARRR_TON", user_id)
        return chat_member.is_chat_member()
    except (ChatNotFound, Unauthorized):
        return False


# Функция для проверки подписки и отправки вступительного сообщения
async def check_subscription_and_send_intro(user_id, message):
    subscribed = await check_subscription(user_id)

    if subscribed:
        cursor.execute("SELECT wallet_address, balance FROM users WHERE id=?", (user_id,))
        user_wallet_address_and_balance = cursor.fetchone()

        # Создаем кнопку с реферальной программой
        keyboard = types.InlineKeyboardMarkup()
        referral_button = types.InlineKeyboardButton("Реферальная программа", callback_data="referral_program")
        keyboard.add(referral_button)
        if not user_wallet_address_and_balance[0]:
            ton_connect_button = types.InlineKeyboardButton("Подключить кошелек", callback_data="start_ton_connect")
            keyboard.add(ton_connect_button)

        await message.answer(f"Добро пожаловать! Ваш баланс: {user_wallet_address_and_balance[1]} ARRR", reply_markup=keyboard)
    else:
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton("Подписаться на канал", url="https://t.me/ARRR_TON"))
        keyboard.add(types.InlineKeyboardButton("Проверить подписку", callback_data="check_subscription"))
        await message.answer("Добро пожаловать! Подпишитесь на канал и нажмите кнопку ниже, чтобы продолжить.",
                             reply_markup=keyboard)


# Функция для отправки сообщения о реферальной программе
async def send_referral_info(user_id):
    referral_link = f"https://t.me/arrr_drop_bot?start={user_id}"
    referral_text = "Пригласите друзей и получите бонусы!\n\nКаждый новый пользователь, приглашенный по вашей ссылке, " \
                    "получает бонус 100 ARRR, а вы получаете 200 ARRR, когда они завершат регистрацию и подпишутся на канал."
    await bot.send_message(user_id, f"Ваша реферальная ссылка:\n{referral_link}\n\n{referral_text}",
                           parse_mode=ParseMode.HTML)


# Обработчик для кнопки "Реферальная программа"
@dp.callback_query_handler(lambda query: query.data == 'referral_program')
async def process_referral_program(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    await send_referral_info(user_id)
    await callback_query.answer()  # Ответим, чтобы закрыть уведомление о нажатии кнопки


# Обработчик для проверки подписки
@dp.callback_query_handler(lambda query: query.data == 'check_subscription')
async def process_check_subscription(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    subscribed = await check_subscription(user_id)

    if subscribed:
        cursor.execute("UPDATE users SET subscribed=1 WHERE id=?", (user_id,))
        conn.commit()
        await check_subscription_and_send_intro(user_id, callback_query.message)
    else:
        await callback_query.answer("Пожалуйста, подпишитесь на канал @ARRR_TON, чтобы продолжить.", show_alert=True)


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
