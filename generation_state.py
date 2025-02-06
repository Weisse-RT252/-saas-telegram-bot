# Импорты необходимых компонентов
from pydantic import BaseModel, Field
from typing import Dict, List
from models import TariffFeature, Tariff, SupportGeneralQuestion

class GenerationState(BaseModel):
    """
    Класс для отслеживания состояния генерации тестовых данных.
    Хранит информацию о сгенерированных фичах, тарифах и вопросах поддержки.
    Используется для контроля процесса генерации и предотвращения дубликатов.
    """
    # Словарь фич по категориям
    features: Dict[str, List[TariffFeature]] = Field(default_factory=lambda: {
        "Security": [], "Analytics": [], "Integration": [], 
        "Automation": [], "UI": []
    })
    
    # Список всех сгенерированных тарифов
    tariffs: List[Tariff] = Field(default_factory=list)
    
    # Словарь вопросов поддержки по категориям
    support_categories: Dict[str, List[SupportGeneralQuestion]] = Field(
        default_factory=lambda: {
            "Getting Started": [], "Security": [], "Billing": [],
            "Technical Issues": [], "Integration": []
        }
    )
    
    def add_feature(self, feature: TariffFeature):
        """
        Добавляет новую фичу в соответствующую категорию
        
        Args:
            feature: Объект фичи для добавления
            
        Raises:
            ValueError: Если у фичи нет ID (не сохранена в БД)
        """
        if not feature.id:
            raise ValueError("Нельзя добавить фичу без ID в состояние")
        self.features[feature.category].append(feature)
    
    def add_tariff(self, tariff: Tariff):
        """
        Добавляет новый тариф в список
        
        Args:
            tariff: Объект тарифа для добавления
        """
        self.tariffs.append(tariff)
        
    def add_support_question(self, category: str, question: SupportGeneralQuestion):
        """
        Добавляет новый вопрос в категорию поддержки
        
        Args:
            category: Название категории
            question: Объект вопроса для добавления
        """
        self.support_categories[category].append(question)
        
    def get_features_summary(self) -> str:
        """
        Формирует текстовое описание всех сгенерированных фич по категориям
        
        Returns:
            str: Форматированный текст с описанием фич или сообщение об их отсутствии
        """
        summary = []
        for category, features in self.features.items():
            if features:
                summary.append(f"\n{category}:")
                for f in features:
                    summary.append(f"- {f.name}: {f.description[:100]}...")
        return "\n".join(summary) if summary else "Фичи еще не сгенерированы"
    
    def get_tariffs_summary(self) -> str:
        """
        Формирует текстовое описание всех сгенерированных тарифов
        
        Returns:
            str: Форматированный текст с описанием тарифов или сообщение об их отсутствии
        """
        if not self.tariffs:
            return "Тарифы еще не сгенерированы"
        summary = []
        for t in self.tariffs:
            summary.append(f"\n{t.name} ({t.price}):")
            summary.append(f"- Лимит пользователей: {t.user_limit}")
            summary.append(f"- Описание: {t.description[:100]}...")
        return "\n".join(summary)
    
    def get_support_summary(self) -> str:
        """
        Формирует текстовое описание всех сгенерированных вопросов поддержки
        
        Returns:
            str: Форматированный текст с описанием вопросов или сообщение об их отсутствии
        """
        summary = []
        for category, questions in self.support_categories.items():
            if questions:
                summary.append(f"\n{category}:")
                for q in questions:
                    summary.append(f"- Q: {q.question[:100]}...")
        return "\n".join(summary) if summary else "Вопросы поддержки еще не сгенерированы"
    
    def get_features_count(self) -> Dict[str, int]:
        """
        Подсчитывает количество сгенерированных фич по категориям
        
        Returns:
            Dict[str, int]: Словарь {категория: количество_фич}
        """
        return {category: len(features) for category, features in self.features.items()}
    
    def get_remaining_features(self, target_per_category: int = 3) -> Dict[str, int]:
        """
        Вычисляет, сколько фич осталось сгенерировать в каждой категории
        
        Args:
            target_per_category: Целевое количество фич в каждой категории
            
        Returns:
            Dict[str, int]: Словарь {категория: осталось_сгенерировать}
        """
        counts = self.get_features_count()
        return {category: target_per_category - count for category, count in counts.items()} 