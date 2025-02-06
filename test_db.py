# Импорты необходимых библиотек
import asyncio
import asyncpg
from dotenv import load_dotenv
import os

async def test_connection():
    """
    Тестирование подключения к базе данных PostgreSQL
    
    Процесс:
    1. Загрузка переменных окружения из .env файла
    2. Получение URL базы данных
    3. Попытка установить соединение
    4. Вывод результата
    """
    load_dotenv('.env')  # Явная загрузка переменных окружения
    db_url = os.getenv("DATABASE_URL")
    print(f"Connecting to: {db_url}")
    
    try:
        # Пробуем установить соединение с базой данных
        conn = await asyncpg.connect(db_url)
        print("Success!")
        await conn.close()  # Закрываем соединение
    except Exception as e:
        print(f"Error: {e}")  # Выводим ошибку, если не удалось подключиться

if __name__ == "__main__":
    # Запускаем тест подключения
    asyncio.run(test_connection()) 