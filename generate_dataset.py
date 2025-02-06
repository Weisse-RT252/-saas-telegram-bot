import os
import asyncio
import asyncpg
from dotenv import load_dotenv
from database import Database
from models import (
    TariffFeature, Tariff, TariffUseCase, 
    SupportCategory, SupportGeneralQuestion, SupportTariffQuestion,
    QuestionRelation, TariffCreate, SupportCreate, TariffFeatureRef,
    SUPPORT_TAGS
)
from generation_state import GenerationState
from pydantic_ai import Agent
from google.generativeai import configure
from tqdm import tqdm
from pydantic import TypeAdapter
import json
import re

load_dotenv()
configure(api_key=os.getenv("GEMINI_API_KEY"))

class DataGenerator:
    def __init__(self, db: Database):
        self.db = db
        self.state = GenerationState()
        self.gen_agent = Agent(
            model='google-gla:gemini-2.0-flash-thinking-exp-01-21',
            system_prompt="""Генератор синтетических данных для SaaS-сервиса.
            Генерируй реалистичные, детальные и связанные между собой данные.
            Используй технический язык, но понятный пользователям.""",
            model_settings={
                "temperature": 0.7,
                "max_output_tokens": 2048,
                "top_p": 0.9
            }
        )

    async def initialize(self):
        """Загрузка существующих данных из базы"""
        print("\n=== Загрузка существующих данных ===")
        features = await self.db.load_features()
        for feature in features:
            self.state.add_feature(feature)
        print(f"Загружено {len(features)} фич")

    async def generate_features(self) -> list[TariffFeature]:
        """Генерация фич с учетом уже существующих"""
        remaining = self.state.get_remaining_features()
        if not any(remaining.values()):
            print("Все фичи уже сгенерированы")
            return []

        prompt = f"""Сгенерируй новые фичи для SaaS-сервиса.

ТЕКУЩИЕ ФИЧИ:
{self.state.get_features_summary()}

ТРЕБОВАНИЯ К НОВЫМ ФИЧАМ:
1. НЕ ПОВТОРЯТЬ существующие фичи и их функциональность
2. Каждая фича должна иметь:
   - name: Название фичи (на русском, уникальное)
   - description: Подробное описание функциональности и преимуществ
   - category: Одна из категорий: Security/Analytics/Integration/Automation/UI

3. Количество новых фич по категориям:
{json.dumps(remaining, indent=2, ensure_ascii=False)}

4. Примеры уникальных названий:
   Security: "Многофакторная аутентификация", "Шифрование данных в покое"
   Analytics: "Интерактивные дашборды", "Предиктивная аналитика"
   Integration: "REST API с OAuth 2.0", "Webhooks для событий"
   Automation: "Конструктор бизнес-процессов", "Триггеры и действия"
   UI: "Настраиваемые виджеты", "Адаптивный дизайн"

Формат: JSON-массив объектов с указанными полями."""

        result = await self.gen_agent.run(prompt)
        features = TypeAdapter(list[TariffFeature]).validate_json(self.extract_json(result.data))
        
        # Проверяем и сохраняем только нужные фичи
        valid_features = []
        for feature in features:
            # Пропускаем существующие фичи
            if await self.db.check_feature_exists(feature.name):
                print(f"Пропуск существующей фичи: {feature.name}")
                continue
                
            # Проверяем лимиты по категориям
            if remaining[feature.category] > 0:
                remaining[feature.category] -= 1
                valid_features.append(feature)
            
        print("\nПример сгенерированной фичи:")
        if valid_features:
            print(json.dumps(valid_features[0].model_dump(), indent=2, ensure_ascii=False))
        
        return valid_features

    async def generate_tariffs(self) -> list[TariffCreate]:
        """Генерация тарифов с учетом существующих"""
        if not any(self.state.features.values()):
            print("Нет доступных фич для генерации тарифов")
            return []

        # Создаем список доступных фич с их ID
        available_features = []
        for category, features in self.state.features.items():
            available_features.extend([
                {"id": f.id, "name": f.name, "category": category}
                for f in features if f.id is not None
            ])

        prompt = f"""Сгенерируй тарифные планы для SaaS-сервиса.

ДОСТУПНЫЕ ФИЧИ (ID: название):
{json.dumps([f"{f['id']}: {f['name']} ({f['category']})" for f in available_features], indent=2, ensure_ascii=False)}

СУЩЕСТВУЮЩИЕ ТАРИФЫ:
{self.state.get_tariffs_summary()}

ТРЕБОВАНИЯ К НОВЫМ ТАРИФАМ:
1. НЕ ПОВТОРЯТЬ существующие тарифы
2. Структура данных для каждого тарифа. Примеры:

Базовый тариф:
{{
    "tariff": {{
        "name": "Базовый",
        "price": "1000 руб/мес",
        "user_limit": 10,
        "description": "Базовый тариф для малых команд"
    }},
    "features": [
        {{
            "feature_id": 1,
            "is_premium": false
        }},
        {{
            "feature_id": 2,
            "is_premium": true
        }}
    ],
    "use_cases": [
        {{
            "scenario": "Начало работы малой команды",
            "solution": "Базовый набор инструментов для совместной работы",
            "target_audience": "Стартапы и малые предприятия до 10 человек"
        }}
    ],
    "support_questions": [
        {{
            "question": "Как добавить нового пользователя?",
            "answer": "Перейдите в раздел Управление командой и нажмите кнопку Добавить",
            "feature_id": 1,
            "priority": 3
        }}
    ]
}}

Энтерпрайз тариф:
{{
    "tariff": {{
        "name": "Энтерпрайз",
        "price": "По запросу",
        "user_limit": null,
        "description": "Корпоративный тариф с расширенными возможностями"
    }},
    ...остальные поля аналогично...
}}

3. Тарифы должны быть логически выстроены:
   - Базовый: 2-3 базовые фичи (используйте ID 1-5), лимит 10 пользователей
   - Стандарт: 4-5 фич среднего уровня (используйте ID 6-10), лимит 30 пользователей
   - Бизнес: 6-7 продвинутых фич (используйте ID 11-15), лимит 100 пользователей
   - Энтерпрайз: Все доступные фичи, лимит = null, цена "По запросу"

ВАЖНО: 
- Используйте только существующие ID фич из списка выше!
- Для тарифов с ценой "По запросу" используйте user_limit: null
- Для остальных тарифов user_limit должен быть числом от 1 до 100

Формат: JSON-массив объектов с указанной выше структурой."""

        result = await self.gen_agent.run(prompt)
        tariffs = TypeAdapter(list[TariffCreate]).validate_json(self.extract_json(result.data))
        
        # Проверяем и сохраняем тарифы
        valid_tariffs = []
        for tariff in tariffs:
            # Проверяем, что все указанные фичи существуют
            feature_ids = {f.feature_id for f in tariff.features}
            existing_ids = {f["id"] for f in available_features}
            if not feature_ids.issubset(existing_ids):
                print(f"Пропуск тарифа {tariff.tariff.name}: указаны несуществующие фичи {feature_ids - existing_ids}")
                continue
                
            valid_tariffs.append(tariff)
            self.state.add_tariff(tariff.tariff)
            
        print("\nПример сгенерированного тарифа:")
        if valid_tariffs:
            print(json.dumps(valid_tariffs[0].model_dump(), indent=2, ensure_ascii=False))
            
        return valid_tariffs

    async def generate_support(self) -> list[SupportCreate]:
        """Генерация категорий поддержки с вопросами"""
        prompt = f"""Сгенерируй категории поддержки с вопросами.

ТЕКУЩИЕ ТАРИФЫ И ФИЧИ:
{self.state.get_features_summary()}
{self.state.get_tariffs_summary()}

СУЩЕСТВУЮЩИЕ ВОПРОСЫ:
{self.state.get_support_summary()}

ТРЕБОВАНИЯ К НОВЫМ ВОПРОСАМ:
1. Структура данных (пример):
{{
    "category": {{
        "name": "Getting Started",
        "description": "Начало работы с сервисом, базовая настройка и основные концепции"
    }},
    "questions": [
        {{
            "question": "Как начать работу с сервисом?",
            "answer": "Подробная инструкция по первым шагам...",
            "tags": ["installation", "basic", "ui"],
            "priority": 5
        }},
        {{
            "question": "Как настроить профиль команды?",
            "answer": "Шаги по настройке профиля...",
            "tags": ["configuration", "basic", "ui"],
            "priority": 4
        }}
    ]
}}

2. Категории поддержки (используйте точные названия):
   - Getting Started
   - Security
   - Billing
   - Technical Issues
   - Integration

3. Теги должны быть из следующих групп:
   Тема: {SUPPORT_TAGS["topic"]}
   Сложность: {SUPPORT_TAGS["difficulty"]}
   Компонент: {SUPPORT_TAGS["component"]}

ВАЖНО:
- Каждый вопрос должен иметь 3 тега (по одному из каждой группы)
- Названия категорий должны точно соответствовать списку выше
- Приоритет от 0 до 5
- НЕ ПОВТОРЯТЬ существующие вопросы

Формат: JSON-массив объектов с указанной выше структурой."""

        result = await self.gen_agent.run(prompt)
        categories = TypeAdapter(list[SupportCreate]).validate_json(self.extract_json(result.data))
        
        # Сохраняем категории и вопросы
        for category in categories:
            for question in category.questions:
                self.state.add_support_question(category.category.name, question)
                
        print("\nПример сгенерированной категории:")
        if categories:
            print(json.dumps(categories[0].model_dump(), indent=2, ensure_ascii=False))
            
        return categories

    def extract_json(self, text: str) -> str:
        """Извлечение JSON из Markdown-ответа"""
        match = re.search(r'```(?:json)?\n(.*?)\n```', text, re.DOTALL)
        return match.group(1) if match else text

    async def generate_batch(self, batch_size: int = 5):
        """Пакетная генерация данных с сохранением состояния"""
        print("\n=== Генерация фич ===")
        while any(self.state.get_remaining_features().values()):
            features = await self.generate_features()
            if features:
                # Сохраняем фичи и обновляем их ID в состоянии
                await self.db.save_features(features)
                # После сохранения обновляем состояние с новыми ID
                for feature in features:
                    if feature.id:  # Теперь у фичи должен быть ID после сохранения
                        self.state.add_feature(feature)
                print("\nТекущие фичи в состоянии:")
                print(self.state.get_features_summary())
                
        print("\n=== Генерация тарифов ===")
        while len(self.state.tariffs) < batch_size:
            tariffs = await self.generate_tariffs()
            if tariffs:
                await self.db.save_tariffs(tariffs)
                
        print("\n=== Генерация базы знаний ===")
        categories = await self.generate_support()
        if categories:
            await self.db.save_support(categories)

async def main():
    pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))
    db = Database(pool)
    generator = DataGenerator(db)
    
    try:
        # Инициализация генератора
        await generator.initialize()
        
        print("\n=== Пакетная генерация данных ===")
        await generator.generate_batch(batch_size=5)
        
        print("\nСгенерированные фичи:")
        print(generator.state.get_features_summary())
        
        print("\nСгенерированные тарифы:")
        print(generator.state.get_tariffs_summary())
        
        print("\nСгенерированные вопросы:")
        print(generator.state.get_support_summary())
        
    finally:
        await pool.close()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Генератор синтетических данных')
    parser.add_argument('--type', choices=['all', 'features', 'tariffs', 'support'], default='all')
    parser.add_argument('--count', type=int, default=10)
    asyncio.run(main())
