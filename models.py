from pydantic import BaseModel, Field, ConfigDict, field_validator
from datetime import datetime
from typing import Literal, List, Dict, Optional
import json
from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart

class Message(BaseModel):
    """
    Базовая модель для сообщений в диалоге между пользователем и ботом
    """
    id: Optional[int] = None  # ID сообщения в базе данных
    role: Literal["user", "assistant"]  # Роль отправителя сообщения
    content: str  # Текст сообщения
    timestamp: datetime = Field(default_factory=datetime.now)  # Время отправки
    parent_message_id: Optional[int] = None  # ID родительского сообщения

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},  # Настройка сериализации datetime
        json_schema_extra = {
            "examples": [
                {
                    "id": 1,
                    "role": "user",
                    "content": "Привет!",
                    "timestamp": "2024-02-20T12:00:00",
                    "parent_message_id": None
                }
            ]
        }
    )

# Константы для тегов поддержки
SUPPORT_TAGS = {
    "topic": ["installation", "configuration", "usage", "error", "billing"],  # Тема вопроса
    "difficulty": ["basic", "intermediate", "advanced"],  # Сложность вопроса
    "component": ["ui", "api", "database", "security", "integration"]  # Компонент системы
}

# Модели для тарифов и функций
class TariffFeature(BaseModel):
    """Модель для описания функции/возможности тарифа"""
    id: Optional[int] = None  # ID функции в базе данных
    name: str  # Название функции
    description: str  # Описание функции
    category: Literal["Security", "Analytics", "Integration", "Automation", "UI"]  # Категория
    created_at: Optional[datetime] = None  # Время создания

class TariffFeatureRef(BaseModel):
    """Ссылка на функцию в тарифе с дополнительными параметрами"""
    feature_id: int  # ID связанной функции
    is_premium: bool = False  # Флаг премиум-функции

class Tariff(BaseModel):
    """Модель тарифного плана"""
    id: Optional[int] = None  # ID тарифа
    name: str  # Название тарифа
    price: str  # Стоимость (в формате "X руб/мес" или "По запросу")
    user_limit: Optional[int] = Field(None, ge=1, le=100, description="Лимит пользователей (null для тарифов 'По запросу')")
    description: str  # Описание тарифа
    created_at: Optional[datetime] = None  # Время создания

class TariffUseCase(BaseModel):
    """Модель примера использования тарифа"""
    id: Optional[int] = None
    tariff_id: Optional[int] = None  # ID связанного тарифа
    scenario: str  # Сценарий использования
    solution: str  # Решение, которое предоставляет тариф
    target_audience: str  # Целевая аудитория
    created_at: Optional[datetime] = None

# Модели для системы поддержки
class SupportCategory(BaseModel):
    """Модель категории вопросов поддержки"""
    id: Optional[int] = None
    name: str  # Название категории
    description: str  # Описание категории
    created_at: Optional[datetime] = None

class SupportGeneralQuestion(BaseModel):
    """Модель общего вопроса поддержки"""
    id: Optional[int] = None
    category_id: Optional[int] = None  # ID категории
    question: str  # Текст вопроса
    answer: str  # Текст ответа
    tags: List[str] = []  # Теги для классификации
    priority: int = Field(ge=0, le=5)  # Приоритет вопроса
    created_at: Optional[datetime] = None

    @field_validator('tags')
    def validate_tags(cls, v):
        """Проверка корректности тегов"""
        valid_tags = set(sum(SUPPORT_TAGS.values(), []))
        if not all(tag in valid_tags for tag in v):
            raise ValueError(f"Invalid tags. Must be from: {valid_tags}")
        return v

class SupportTariffQuestion(BaseModel):
    """Модель вопроса, специфичного для конкретного тарифа"""
    id: Optional[int] = None
    tariff_id: Optional[int] = None  # ID тарифа
    feature_id: Optional[int] = None  # ID функции
    question: str  # Текст вопроса
    answer: str  # Текст ответа
    priority: int = Field(ge=0, le=5)  # Приоритет вопроса
    created_at: Optional[datetime] = None

class QuestionRelation(BaseModel):
    """Модель связи между вопросами"""
    source_id: int  # ID исходного вопроса
    target_id: int  # ID связанного вопроса
    relation_type: str  # Тип связи
    source_type: Literal["general", "tariff"]  # Тип исходного вопроса
    target_type: Literal["general", "tariff"]  # Тип связанного вопроса

# Вспомогательные модели для генерации данных
class TariffCreate(BaseModel):
    """Модель для создания тарифа со всеми связанными данными"""
    tariff: Tariff  # Основная информация о тарифе
    features: List[TariffFeatureRef]  # Список функций
    use_cases: List[TariffUseCase]  # Примеры использования
    support_questions: List[SupportTariffQuestion]  # Вопросы поддержки

class SupportCreate(BaseModel):
    """Модель для создания категории поддержки со всеми вопросами"""
    category: SupportCategory  # Информация о категории
    questions: List[SupportGeneralQuestion]  # Список вопросов
    relations: List[QuestionRelation] = []  # Связи между вопросами

# Модели для RAG (Retrieval-Augmented Generation)
class SearchResult(BaseModel):
    """Результат поиска в базе знаний"""
    content: str  # Найденный контент
    source_type: Literal["tariff", "feature", "use_case", "general", "specific"]  # Тип источника
    source_id: int  # ID источника
    relevance: float  # Релевантность результата
    metadata: Dict = Field(default_factory=dict)  # Дополнительные метаданные

class SupportCase(BaseModel):
    """Модель кейса поддержки"""
    problem: str  # Описание проблемы
    causes: List[str]  # Возможные причины
    steps: List[str]  # Шаги решения
    example: Dict[str, str]  # Пример решения 