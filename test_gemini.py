# Импорты необходимых библиотек
import os
import asyncio
from pydantic_ai.models.gemini import GeminiModel
from pydantic_ai.models.gemini import ModelRequest, UserPromptPart
from dotenv import load_dotenv
import httpx

# Загружаем переменные окружения
load_dotenv()

async def test_gemini():
    """
    Тестирование работы с API Gemini
    
    Процесс:
    1. Настройка HTTP клиента
    2. Инициализация модели Gemini
    3. Создание агентской модели
    4. Отправка тестового запроса
    5. Вывод результата
    """
    # Настройка HTTP клиента с таймаутом 60 секунд
    http_client = httpx.AsyncClient(
        timeout=60.0
    )
    
    # Инициализация модели Gemini с API ключом
    model = GeminiModel(
        model_name="gemini-2.0-flash-thinking-exp-01-21",
        api_key=os.getenv("GEMINI_API_KEY"),
        http_client=http_client
    )
    
    # Создание агентской модели без дополнительных инструментов
    agent_model = await model.agent_model(
        function_tools=[], 
        allow_text_result=True,
        result_tools=[]
    )
    
    # Отправка тестового запроса
    response = await agent_model.request(
        messages=[ModelRequest(parts=[
            UserPromptPart(content="Напиши приветствие для ИТ-бота")
        ])],
        model_settings={
            "temperature": 0.3,  # Низкая температура для более предсказуемых ответов
            "max_output_tokens": 200  # Ограничение длины ответа
        }
    )
    
    # Вывод результата
    print("Ответ Gemini:", response.data)

if __name__ == "__main__":
    # Запускаем тест Gemini API
    asyncio.run(test_gemini()) 