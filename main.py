import asyncpg
from bot import TelegramBot
from database import Database
import os 
import asyncio
import nest_asyncio

# Применяем nest_asyncio для поддержки вложенных циклов событий
# Это необходимо для корректной работы с Telegram API внутри других асинхронных операций
nest_asyncio.apply()

async def main():
    # Создаем пул подключений к PostgreSQL
    # Используем переменную окружения DATABASE_URL для безопасного хранения параметров подключения
    pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))
    
    # Инициализируем объект базы данных
    db = Database(pool)
    # Создаем необходимые таблицы и индексы при первом запуске
    await db.init_db()
    
    # Создаем и инициализируем Telegram бота
    bot = TelegramBot(pool)
    await bot.initialize()  # Настраиваем бота и подключаем обработчики
    
    # Запускаем бота в режиме long polling
    # Это блокирующий вызов, который будет обрабатывать сообщения постоянно
    await bot.app.run_polling()

if __name__ == "__main__":
    # Запускаем главную асинхронную функцию
    asyncio.run(main()) 