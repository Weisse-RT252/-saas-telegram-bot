import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import google.generativeai as genai
from google.generativeai.types import GenerationConfig
from io import BytesIO
from dotenv import load_dotenv
import time
import asyncio
import httpx
from google.api_core.exceptions import GoogleAPIError

# Загрузка переменных окружения
load_dotenv()

# Настройки приложения
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Инициализация Gemini:cite[6]
genai.configure(
    api_key=os.getenv("GEMINI_API_KEY"),
    transport="rest",
    client_options={
        # "api_endpoint": "https://generativelanguage.googleapis.com/v1"
    }
)

# Глобальный счетчик запросов
REQUEST_COUNTER = 0

gemini_model = genai.GenerativeModel("gemini-2.0-flash-exp")

async def verify_tor_ip():
    """Проверка текущего IP"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("https://api.ipify.org", timeout=15)
            return response.text
    except Exception as e:
        logging.error(f"IP verification failed: {e}")
        return None

async def start(update: Update, _):
    """Обработка команды /start"""
    await update.message.reply_text(
        "🤖 Я обновленный бот с интеграцией Gemini через Tor!\n"
        "Поддерживаю:\n"
        "- Текст/голосовые\n"
        "- Изображения\n"
        "- PDF документы\n"
        "/ip - Проверить IP\n"
        "/process_doc - Анализ PDF"
    )

async def handle_message(update: Update, context):
    """Обработка входящих сообщений"""
    global REQUEST_COUNTER
    message = update.message
    max_retries = 30
    
    for attempt in range(max_retries):
        try:
            REQUEST_COUNTER += 1
            if REQUEST_COUNTER % 2 == 0:
                await verify_tor_ip()

            contents = []

            # Базовый текст
            if message.text:
                contents.append({"role": "user", "parts": [{"text": message.text}]})

            # Обработка изображений
            if message.photo:
                photo_file = await message.photo[-1].get_file()
                img_data = await photo_file.download_as_bytearray()
                contents.append({
                    "role": "user",
                    "parts": [{
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": img_data.decode("latin-1")
                        }
                    }]
                })

            # Обработка документов
            if message.document:
                doc_file = await message.document.get_file()
                doc_data = await doc_file.download_as_bytearray()
                
                if message.document.mime_type == "application/pdf":
                    contents.append({
                        "role": "user",
                        "parts": [{
                            "file_data": {
                                "mime_type": "application/pdf",
                                "file_uri": f"data:application/pdf;base64,{doc_data.hex()}"
                            }
                        }]
                    })
                else:
                    contents.append({
                        "role": "user",
                        "parts": [{"text": f"Документ типа {message.document.mime_type}"}]
                    })

            # Генерация контента
            response = gemini_model.generate_content(
                contents=contents,
                generation_config=GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=1000,
                ),
                request_options={"timeout": 30}
            )
            
            if not response.text:
                raise ValueError("Пустой ответ от Gemini API")

            await message.reply_text(response.text)
            return  # Успешная отправка

        except Exception as e:
            logging.error(f"Ошибка (попытка {attempt+1}): {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)  # Экспоненциальная задержка
                
    await message.reply_text("⚠️ Не удалось обработать запрос после нескольких попыток")

async def check_ip(update: Update, _):
    """Проверка текущего IP"""
    try:
        response = requests.get("https://api.ipify.org?format=json", timeout=10)
        await update.message.reply_text(f"🌐 Текущий IP: {response.json()['ip']}")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def process_document(update: Update, context):
    """Обработка PDF документов через Gemini"""
    try:
        doc_file = await update.message.document.get_file()
        doc_data = await doc_file.download_as_bytearray()

        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(
            [
                "Проанализируй PDF документ:",
                {
                    "file_data": {
                        "mime_type": "application/pdf",
                        "file_uri": f"data:application/pdf;base64,{doc_data.hex()}"
                    }
                }
            ],
            generation_config=GenerationConfig(
                temperature=0.5,
                max_output_tokens=2000
            )
        )

        await update.message.reply_text(f"📄 Результат анализа:\n{response.text}")

    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def handle_gemini_request(prompt):
    for attempt in range(5):
        try:
            response = await gemini_model.generate(prompt)
            return response
        except GoogleAPIError as e:
            if e.code == 403:
                logging.warning("Blocked IP detected! Renewing...")
                success = await verify_tor_ip()
                if not success:
                    raise
                await asyncio.sleep(30)
            else:
                raise

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    handlers = [
        CommandHandler("start", start),
        CommandHandler("ip", check_ip),
        CommandHandler("process_doc", process_document),
        MessageHandler(filters.ALL, handle_message)
    ]

    for handler in handlers:
        app.add_handler(handler)

    app.run_polling()

if __name__ == "__main__":
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )
    main()