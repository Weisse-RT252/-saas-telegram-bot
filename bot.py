from telegram import Update
from telegram.ext import Application, MessageHandler, filters
from database import Database
from graph import service_graph, RouterNode
import asyncpg
import os
import logging
from pydantic_ai.messages import ModelMessage, UserPromptPart

class TelegramBot:
    """
    Основной класс Telegram бота, который обрабатывает сообщения пользователей
    и управляет взаимодействием с базой данных и графом обработки сообщений
    """
    
    def __init__(self, db_pool: asyncpg.Pool):
        # Инициализация компонентов бота
        self.db = Database(db_pool)  # Объект для работы с базой данных
        # Создаем приложение Telegram бота с использованием токена из переменных окружения
        self.app = Application.builder().token(os.getenv("TELEGRAM_TOKEN")).build()
        # Добавляем обработчик текстовых сообщений
        self.app.add_handler(MessageHandler(filters.TEXT, self.handle_message))
        # Настраиваем логирование
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Добавляем метод отправки уведомлений в объект базы данных
        # Это нужно для уведомления операторов о важных событиях
        self.db.send_telegram_alert = self.send_telegram_alert

    async def initialize(self):
        """Инициализация базы данных при запуске бота"""
        await self.db.init_db()

    async def handle_message(self, update: Update, _):
        """
        Основной метод обработки входящих сообщений
        
        Процесс обработки:
        1. Проверка ограничения частоты сообщений
        2. Сохранение сообщения пользователя
        3. Загрузка истории диалога
        4. Обработка сообщения через граф
        5. Отправка и сохранение ответа
        """
        try:
            # Проверяем, не превышен ли лимит сообщений
            if not await self.db.check_rate_limit(update.effective_user.id):
                await update.message.reply_text("⚠️ Слишком много запросов. Подождите 1 минуту.")
                return
            
            user_id = update.effective_user.id
            message = update.message.text
            
            # Логируем информацию о новом сообщении
            self.logger.info(f"\n=== Новое сообщение ===")
            self.logger.info(f"User ID: {user_id}")
            self.logger.info(f"Текст сообщения: {message}")
            
            # Сохраняем сообщение пользователя в историю
            await self.db.save_message(user_id, "user", message)
            
            # Получаем последние 20 сообщений из истории диалога
            history = (await self.db.get_history(user_id))[-20:]
            self.logger.info(f"Загружено {len(history)} сообщений из истории")
            
            # Запускаем обработку через граф сервиса
            self.logger.info("Запуск графа обработки...")
            response, _ = await service_graph.run(
                start_node=RouterNode(),
                state={
                    "user_id": user_id,
                    "message": message,
                    "history": history
                },
                deps=self.db
            )
            
            self.logger.info(f"Ответ от графа: {response}")
            
            # Сохраняем ответ бота и отправляем его пользователю
            await self.db.save_message(user_id, "assistant", response)
            await update.message.reply_text(response)

        except Exception as e:
            # В случае ошибки логируем её и уведомляем пользователя
            self.logger.error(f"Ошибка: {str(e)}", exc_info=True)
            await self.db.log_error(update.effective_user.id, str(e))
            await update.message.reply_text("🔧 Произошла ошибка. Оператор уже уведомлен.")

    async def send_telegram_alert(self, message: str):
        """
        Отправка уведомлений операторам в специальный чат
        Используется для важных системных сообщений и запросов на связь с оператором
        """
        await self.app.bot.send_message(
            chat_id=os.getenv("OPERATOR_CHAT_ID"),
            text=message
        ) 