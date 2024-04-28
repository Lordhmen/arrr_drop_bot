import os

from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
MANIFEST_URL = '/pytonconnect-manifest.json'

# Создаем экземпляр виртуального хранилища MemoryStorage
storage = MemoryStorage()

# Инициализируем бот и диспетчер
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot, storage=storage)
dp.middleware.setup(LoggingMiddleware())
