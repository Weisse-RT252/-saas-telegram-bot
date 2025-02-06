# Импорты необходимых компонентов
from pydantic_graph import Graph, BaseNode, Edge, End
from agents import SalesAgent, SupportAgent
from pydantic_ai import Agent, RunContext
from pydantic import BaseModel
import re
import math


class ClassifierResult(BaseModel):
    """Результат классификации запроса пользователя"""
    intent: str  # Намерение: 'sales' или 'support'


class EndNode(BaseNode):
    """Конечный узел графа, возвращающий результат обработки"""

    def __init__(self, result: str):
        self.result = result

    async def run(self, ctx) -> End:
        return End(self.result)


class SecurityValidator:
    """
    Упрощенный валидатор безопасности.
    Фокусируется на предотвращении только самых опасных инъекций.
    """
    def __init__(self):
        # Паттерны для обнаружения ОЧЕНЬ ЯВНЫХ попыток инъекций кода
        self.injection_patterns = [
            "eval(", "exec(", "system(",  # Выполнение кода
            "subprocess", "os.", "sys.",  # Системные вызовы
            "import ", "require ",         # Импорты/требования (с пробелом, чтобы не ловить слова типа "important")
        ]

        # Список разрешенных команд (остается как есть)
        self.allowed_commands = [
            "/clear",
            "/start",
            "/help"
        ]

    def check_message(self, message: str) -> tuple[bool, str]:
        """Проверяет сообщение на наличие ОЧЕНЬ ЯВНЫХ подозрительных паттернов"""
        # Сначала проверяем, является ли сообщение разрешенной командой
        if message.strip().lower() in self.allowed_commands:
            print(f"[DEBUG] SecurityValidator: Разрешенная команда: {message}")
            return True, ""

        message = message.lower()

        # Проверка на инъекции кода (только самые явные паттерны)
        for pattern in self.injection_patterns:
            if pattern in message: # Упрощенная проверка: простое "in"
                reason = f"Обнаружена явная попытка инъекции кода: {pattern}"
                print(f"[DEBUG] SecurityValidator: {reason}")
                return False, reason

        print(f"[DEBUG] SecurityValidator: Сообщение безопасно (упрощенная проверка): {message}")
        return True, ""


class RouterNode(BaseNode):
    """
    Корневой узел графа.
    Отвечает за проверку безопасности, классификацию намерения пользователя
    и маршрутизацию запроса к соответствующему агенту.
    """
    def __init__(self):
        self.security = SecurityValidator()
        self.last_intent = {}  # Словарь для хранения последнего интента пользователя

    async def run(self, ctx) -> BaseNode:
        print("\n=== RouterNode ===")
        try:
            message = ctx.state["message"]
            user_id = ctx.state["user_id"]
            history = ctx.state["history"]

            print(f"[DEBUG] RouterNode: Входящее сообщение: '{message}'")

            # Проверка безопасности (упрощенная)
            is_safe, reason = self.security.check_message(message)
            if not is_safe:
                print(f"Сообщение отклонено: {reason}")
                return EndNode("Извините, я не могу обработать этот запрос из-за соображений безопасности.")

            # Если это команда, обрабатываем команду и завершаем
            if message.startswith('/'):
                print(f"Обнаружена команда: {message}")
                return EndNode("")  # Пустой ответ, команды обрабатываются отдельно

            # === Улучшенная классификация намерения с учетом контекста ===
            # 1. Анализ истории для определения преобладающей темы (увеличиваем контекст до 10 сообщений)
            # Расширенные ключевые слова для sales - синонимы, общие слова, коммерция
            sales_context_keywords = [
                "тариф", "тарифы", "цена", "цены", "стоимость", "сколько стоит", "оплата", "платить", "купить", "покупка",
                "подписка", "подписаться", "продаж", "продажи", "коммерческий", "коммерция", "выгодный", "выгодно",
                "руб", "доллар", "евро", "скидка", "акция", "дешевле", "дороже", "бесплатно", "бесплатный",
                "возможности", "функции", "особенности", "сравнить", "сравнение", "выбрать", "выбор", "подобрать",
                "интересует", "интересно", "хочу узнать", "расскажите", "подробнее", "детали", "условия", "условие",
                "прайс", "лист", "предложение", "заказать", "заказ", "оформить", "оформление", "подключить", "подключение"
            ]
            # Расширенные ключевые слова для support - синонимы, общие слова, проблемы, помощь
            support_context_keywords = [
                "проблема", "проблемы", "ошибка", "ошибки", "не работает", "недоступно", "сломалось", "помогите", "помощь",
                "поддержка", "поддержите", "вопрос", "вопросы", "как сделать", "что делать", "не получается", "не могу",
                "завис", "тормозит", "лагает", "глючит", "баг", "баги", "технический", "технически", "настройка", "настроить",
                "руководство", "инструкция", "документация", "справка", "консультация", "консультировать", "объясните", "разъясните",
                "почему", "зачем", "где", "куда", "когда", "сколько", "кто", "что", "какой", "какая", "какое", "какие",
                "логин", "пароль", "доступ", "войти", "зайти", "регистрация", "зарегистрироваться", "аккаунт", "личный кабинет",
                "неверный", "ошибка", "неправильно", "некорректно", "сбой", "отказ", "отвалилось", "упало", "лежит", "висит"
            ]

            sales_context_score = sum(1 for msg in history[-10:] for word in sales_context_keywords if word in msg.content.lower()) # Контекст - последние 10 сообщений
            support_context_score = sum(1 for msg in history[-10:] for word in support_context_keywords if word in msg.content.lower()) # Контекст - последние 10 сообщений

            print(f"[DEBUG] RouterNode: Контекстные баллы - Sales: {sales_context_score}, Support: {support_context_score}")

            # 2. Классификация намерения с помощью LLM - **СУПЕР-УПРОЩЕННЫЙ ПРОМПТ**
            classifier_prompt = f"""
**КЛАССИФИЦИРУЙ**:  'sales' или 'support'. **ТОЛЬКО ОДНО СЛОВО**.

**КОНТЕКСТ (ПОСЛЕДНИЕ СООБЩЕНИЯ):**
{[msg.content for msg in history[-10:]]}

**ПОСЛЕДНИЙ ЗАПРОС:**
{message}

**КЛЮЧЕВОЕ: ЕСЛИ КОНТЕКСТ - ТАРИФЫ, А ЗАПРОС КОРОТКИЙ ("Любой", "Ок", "Да"), КЛАССИФИЦИРУЙ КАК 'sales'.**

**ОТВЕТ ('sales' или 'support'):**
""" # Супер-упрощенный промпт

            classifier = Agent(
                'google-gla:gemini-2.0-flash-exp',
                system_prompt=classifier_prompt,
                model_settings={
                    "temperature": 0.1,
                    "candidate_count": 1,
                    "max_output_tokens": 32 # Уменьшаем max_output_tokens, т.к. ответ ожидается очень короткий
                },
                result_type=ClassifierResult
            )

            print("[DEBUG] RouterNode: Запускаем классификатор с УПРОЩЕННЫМ промптом и контекстом...")
            result = await classifier.run(message)
            print(f"[DEBUG] RouterNode: Результат классификации LLM: {result.data}")
            intent = result.data.intent.strip().lower()
            print(f"[DEBUG] RouterNode: Определенный интент от LLM: '{intent}'")

            # 3. Принимаем решение на основе контекста и классификации LLM
            final_intent = intent
            if intent not in ['sales', 'support']:
                print(f"[DEBUG] RouterNode: Неопределенный интент от LLM: '{intent}', проверяем контекст...")
                if sales_context_score > support_context_score:
                    final_intent = 'sales'
                    print(f"[DEBUG] RouterNode: Контекст переопределяет интент на 'sales'")
                else:
                    final_intent = 'support'
                    print(f"[DEBUG] RouterNode: Контекст переопределяет интент на 'support' (по умолчанию)")
            else:
                print(f"[DEBUG] RouterNode: Интент от LLM принят: '{intent}'")

            # === УСИЛЕННОЕ правило-основанное резервное решение для коротких сообщений в контексте продаж ===
            if final_intent == 'support' and len(message.split()) <= 3: # Усиливаем правило: до 3 слов
                if sales_context_score > support_context_score and sales_context_score > 1: # Усиливаем правило: контекст продаж должен быть заметно сильнее (score > 1)
                    final_intent = 'sales' # Переопределяем на sales
                    print(f"!!! УСИЛЕННОЕ ПРАВИЛО-ОСНОВАННОЕ РЕЗЕРВНОЕ РЕШЕНИЕ: Переопределение интента на 'sales' из-за короткого сообщения и контекста продаж")

            print(f"[DEBUG] RouterNode: Финальный интент: '{final_intent}'")
            self.last_intent[user_id] = final_intent # Сохраняем последний интент
            return SalesNode() if final_intent == 'sales' else SupportNode()

        except Exception as e:
            print(f"Ошибка в RouterNode: {str(e)}")
            print(f"Тип ошибки: {type(e)}")
            raise


class SalesNode(BaseNode):
    """Узел для обработки запросов, связанных с продажами"""

    async def run(self, ctx) -> EndNode:
        print("\n=== SalesNode ===")
        try:
            # Получаем историю диалога
            history = ctx.state.get("history", [])
            print(f"История сообщений: {len(history)} записей")

            # Конвертируем историю в формат модели с помощью нового метода
            model_messages = ctx.deps.convert_to_model_messages(history)
            print("История конвертирована в ModelMessages")

            # Создаем и запускаем агента продаж
            agent = SalesAgent(ctx.deps)
            print("Агент продаж создан, запускаем...")

            # Получаем ответ от агента
            result = await agent.agent.run(
                ctx.state["message"],
                message_history=model_messages
            )
            print(f"Получен ответ: {result.data}")

            # Сохраняем ответ в историю
            response = str(result.data)
            await ctx.deps.save_message(ctx.state["user_id"], "assistant", response)
            return EndNode(response)

        except Exception as e:
            print(f"Ошибка в SalesNode: {str(e)}")
            print(f"Тип ошибки: {type(e)}")
            raise


class SupportNode(BaseNode):
    """Узел для обработки запросов в техподдержку"""

    async def run(self, ctx) -> EndNode:
        print("\n=== SupportNode ===")
        try:
            # Получаем историю диалога
            history = ctx.state.get("history", [])
            print(f"История сообщений: {len(history)} записей")

            # Конвертируем историю в формат модели с помощью нового метода
            model_messages = ctx.deps.convert_to_model_messages(history)
            print("История конвертирована в ModelMessages")

            # Создаем и запускаем агента поддержки
            agent = SupportAgent(ctx.deps)
            print("Агент поддержки создан, запускаем...")

            # Получаем ответ от агента
            result = await agent.agent.run(
                ctx.state["message"],
                message_history=model_messages
            )
            print(f"Получен ответ: {result.data}")

            # Сохраняем ответ в историю
            response = str(result.data)
            await ctx.deps.save_message(ctx.state["user_id"], "assistant", response)
            return EndNode(response)

        except Exception as e:
            print(f"Ошибка в SupportNode: {str(e)}")
            print(f"Тип ошибки: {type(e)}")
            raise


# Создаем граф обработки сообщений
service_graph = Graph(nodes=[RouterNode, SalesNode, SupportNode, EndNode]) 