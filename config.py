import os
import sqlite3

from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import ParseMode
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
MANIFEST_URL = 'https://raw.githubusercontent.com/Lordhmen/arrr_drop_bot/master/pytonconnect-manifest.json'

# Создаем экземпляр виртуального хранилища MemoryStorage
storage = MemoryStorage()

# Инициализируем бот и диспетчер
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())

# Создаем соединение с базой данных
conn = sqlite3.connect('bot.db')
cursor = conn.cursor()

photo_start = 'photo_start.jpg'
photo_ref = 'photo_ref.jpg'
photo_sub = 'photo_sub.jpg'
photo_main = 'photo_main.jpg'
