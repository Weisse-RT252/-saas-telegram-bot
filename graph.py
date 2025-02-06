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
    Валидатор безопасности для проверки входящих сообщений.
    Реализует многоуровневую защиту от различных видов атак и манипуляций.
    """
    def __init__(self):
        # Базовые паттерны для обнаружения попыток манипуляции
        self.basic_patterns = [
            "userprompt:", "userinput:", "userquery:", 
            "newresponseformat:", "responseformat:",
            "{", "}", "<|", "|>", "test:", 
            "rule:", "remember:", "output:", 
            "leetspeak", "unfiltered", "liberated",
            "upgraded", "geneva convention"
        ]
        
        # Паттерны для обнаружения попыток взлома и эксплойтов
        self.security_patterns = [
            "script", "keylogger", "hack", "exploit", 
            "vulnerability", "backdoor", "malware", 
            "virus", "trojan", "rootkit", "spyware",
            "sql", "injection", "overflow", "bypass",
            "authentication", "authorization", "token",
            "password", "credential", "admin", "root"
        ]
        
        # Паттерны для обнаружения попыток инжекта и обхода защиты
        self.injection_patterns = [
            "игнорируй", "забудь", "отключи", "проигнорируй",
            "инструкция", "новая роль", "теперь ты", 
            "ты больше не", "без ограничений", "режим бога",
            "system prompt", "new prompt", "override",
            "настройки", "установки", "конфигурация",
            "gpt-4", "chatgpt", "assistant", "ai model",
            "дай код", "напиши код", "покажи код",
            "алгоритм", "реализация", "implementation",
            "binary search", "поиск", "сортировка",
            "бинарный", "линейный", "алгоритм"
        ]
        
        # Регулярные выражения для обнаружения подозрительных конструкций
        self.suspicious_constructs = [
            r"инструкция[_\s]*\d+",  # Инструкция_1, Инструкция 1
            r"шаг[_\s]*\d+",         # Шаг_1, Шаг 1
            r"правило[_\s]*\d+",     # Правило_1, Правило 1
            r"этап[_\s]*\d+",        # Этап_1, Этап 1
            r"команда[_\s]*\d+",     # Команда_1, Команда 1
            r"\d+\s*\)",             # 1), 2)
            r"\d+\s*\.",             # 1., 2.
            r"[a-zA-Z]+\s*=",        # NewRole=, Format=
            r"\{[^}]*\}",           # {любой текст}
            r"<[^>]*>",             # <любой текст>
            r"def\s+\w+",           # def function
            r"class\s+\w+",         # class Name
            r"while\s*\(",          # while loops
            r"for\s+\w+\s+in",      # for loops
            r"import\s+\w+",        # imports
            r"from\s+\w+\s+import"  # from imports
        ]
        
        # Паттерны для обнаружения попыток использования метафор и скрытых намерений
        self.metaphor_patterns = [
            "представь что", "вообрази что", "допустим что",
            "в ролевой игре", "в сценарии", "в истории",
            "как будто", "словно", "как если бы",
            "в параллельной вселенной", "в другом мире",
            "в гипотетической ситуации", "теоретически",
            "давай поиграем", "притворись что", "сделай вид",
            "ты теперь", "ты сейчас", "твоя задача"
        ]
        
        # Паттерны для обнаружения попыток получения программного кода
        self.coding_patterns = [
            "алгоритм", "код", "функция", "метод",
            "класс", "структура данных", "массив",
            "список", "дерево", "граф", "поиск",
            "сортировка", "рекурсия", "итерация",
            "цикл", "условие", "переменная", "константа",
            "binary", "search", "sort", "find", "array",
            "list", "tree", "graph", "queue", "stack",
            "heap", "hash", "table", "map", "set"
        ]
        
        # Паттерны для обнаружения форматированных промптов
        self.format_patterns = [
            r"\{[^}]*\}",           # {переменные}
            r"<[^>]*>",             # <теги>
            r"\[[^\]]*\]",          # [скобки]
            r"\$[^$]*\$",           # $переменные$
            r"@[^@]*@",             # @метки@
            r"\|\|[^|]*\|\|",       # ||разделители||
            r"\/[^\/]*\/",          # /пути/
            r"#[^#]*#",             # #хэштеги#
            r"\(\([^)]*\)\)",       # ((группы))
            r"``[^`]*``"           # ``кодовые блоки``
        ]
        
        # Паттерны для обнаружения попыток обхода защиты
        self.evasion_patterns = [
            r"[А-Яа-я]\s*=\s*{",    # Присваивания переменных
            r"[A-Za-z]\s*=\s*{",    # Присваивания на англ
            r"input\s*=",           # Переопределение input
            r"output\s*=",          # Переопределение output
            r"format\s*=",          # Переопределение format
            r"response\s*=",        # Переопределение response
            r"\w+_\d+",            # Переменные с цифрами
            r"\d+_\w+",            # Цифры с переменными
            r"[^\w\s](\w+)[^\w\s]", # Слова в спецсимволах
            r"\\[nrt]"             # Экранированные символы
        ]
        
        # Паттерны для обнаружения leet speak и обфускации
        self.obfuscation_patterns = [
            r"\d+[\W_]+\d+",        # Числа с разделителями
            r"[A-Za-z][\W_]+[A-Za-z]", # Буквы с разделителями
            r"[А-Яа-я][\W_]+[А-Яа-я]", # Русские буквы с разделителями
            r"[^\w\s]{2,}",         # Последовательности спецсимволов
            r"(.)\1{2,}",           # Повторяющиеся символы
            r"[A-Z][a-z]*\d+",      # CamelCase с цифрами
            r"\d+[A-Z][a-z]*",      # Цифры с CamelCase
            r"[!@#$%^&*()]{2,}",    # Последовательности символов
            r"[0-9o]{2,}",          # Замена O на 0
            r"[1il|]{2,}"           # Замена I на 1 или l
        ]

    def check_message(self, message: str) -> tuple[bool, str]:
        """
        Проверяет сообщение на наличие подозрительных паттернов
        
        Args:
            message: Текст сообщения для проверки
            
        Returns:
            tuple[bool, str]: (is_safe, reason)
            - is_safe: True если сообщение безопасно, False если обнаружены подозрительные паттерны
            - reason: Причина отклонения сообщения (пустая строка если сообщение безопасно)
        """
        message = message.lower()
        
        # Проверка на форматированные промпты
        for pattern in self.format_patterns:
            if re.search(pattern, message):
                return False, "Обнаружен форматированный промпт"
        
        # Проверка на попытки обхода
        for pattern in self.evasion_patterns:
            if re.search(pattern, message):
                return False, "Обнаружена попытка обхода защиты"
        
        # Проверка на leet speak и обфускацию
        for pattern in self.obfuscation_patterns:
            if re.search(pattern, message):
                return False, "Обнаружена попытка обфускации"
        
        # Проверка на энтропию текста (выявление зашифрованных сообщений)
        if self._calculate_entropy(message) > 4.5:  # Пороговое значение можно настроить
            return False, "Подозрительно высокая энтропия текста"
        
        # Проверка на равномерность распределения символов
        if self._check_char_distribution(message):
            return False, "Подозрительное распределение символов"
        
        # Проверка на программный код
        code_indicators = [
            "def ", "class ", "while", "for ", "if ", 
            "return ", "print(", "import ", "from ",
            "{", "}", "[", "]", "==", "!=", ">=", "<="
        ]
        if any(indicator in message for indicator in code_indicators):
            return False, "Обнаружен программный код"
        
        # Проверка базовых паттернов
        for pattern in self.basic_patterns:
            if pattern.lower() in message:
                return False, f"Обнаружен подозрительный паттерн: {pattern}"
        
        # Проверка паттернов безопасности
        for pattern in self.security_patterns:
            if pattern.lower() in message:
                return False, f"Обнаружен запрещенный паттерн: {pattern}"
        
        # Проверка инжектов
        for pattern in self.injection_patterns:
            if pattern.lower() in message:
                return False, f"Обнаружена попытка инжекта: {pattern}"
        
        # Проверка подозрительных конструкций
        for pattern in self.suspicious_constructs:
            if re.search(pattern, message, re.IGNORECASE):
                return False, f"Обнаружена подозрительная конструкция"
        
        # Проверка метафор
        for pattern in self.metaphor_patterns:
            if pattern.lower() in message:
                return False, f"Обнаружена попытка использования метафоры: {pattern}"
        
        # Проверка на паттерны программирования
        for pattern in self.coding_patterns:
            if pattern.lower() in message:
                return False, f"Обнаружен паттерн программирования: {pattern}"
        
        # Проверка на последовательность инструкций
        lines = message.split('\n')
        instruction_count = sum(1 for line in lines if any(p in line.lower() for p in ["инструкция", "шаг", "правило", "этап"]))
        if instruction_count >= 2:
            return False, "Обнаружена последовательность инструкций"
        
        # Проверка на длинные сообщения (возможно, сложные промпты)
        if len(message) > 500:  # Можно настроить лимит
            return False, "Сообщение слишком длинное"
        
        # Проверка на повторяющиеся паттерны
        words = message.split()
        if len(words) > 3:
            word_pairs = zip(words, words[1:])
            for pair in word_pairs:
                if words.count(' '.join(pair)) > 2:
                    return False, "Обнаружен повторяющийся паттерн"
            
        return True, ""
    
    def _calculate_entropy(self, text: str) -> float:
        """
        Вычисляет энтропию текста для обнаружения зашифрованных сообщений
        
        Args:
            text: Текст для анализа
            
        Returns:
            float: Значение энтропии
        """
        if not text:
            return 0
        
        # Считаем частоты символов
        freq = {}
        for char in text:
            freq[char] = freq.get(char, 0) + 1
        
        # Вычисляем энтропию
        length = len(text)
        entropy = 0
        for count in freq.values():
            probability = count / length
            entropy -= probability * (math.log2(probability) if probability > 0 else 0)
        
        return entropy
    
    def _check_char_distribution(self, text: str) -> bool:
        """
        Проверяет равномерность распределения символов для обнаружения обфускации
        
        Args:
            text: Текст для анализа
            
        Returns:
            bool: True если распределение подозрительно равномерное
        """
        if not text:
            return False
        
        # Считаем частоты символов
        freq = {}
        for char in text:
            freq[char] = freq.get(char, 0) + 1
        
        # Вычисляем стандартное отклонение
        values = list(freq.values())
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        std_dev = math.sqrt(variance)
        
        # Если стандартное отклонение слишком маленькое - подозрительно
        return std_dev < 1.5  # Пороговое значение можно настроить

class RouterNode(BaseNode):
    """
    Корневой узел графа, который проверяет безопасность сообщения
    и направляет его к соответствующему агенту (продажи или поддержка)
    """
    def __init__(self):
        self.security = SecurityValidator()
    
    async def run(self, ctx) -> BaseNode:
        print("\n=== RouterNode ===")
        try:
            message = ctx.state["message"]
            
            # Проверка безопасности
            is_safe, reason = self.security.check_message(message)
            if not is_safe:
                print(f"Сообщение отклонено: {reason}")
                return EndNode("Я не могу обработать этот запрос. Пожалуйста, задайте вопрос о наших тарифах или обратитесь в техподдержку.")
            
            # Классификация намерения пользователя
            classifier = Agent(
                'google-gla:gemini-2.0-flash-exp',
                system_prompt="""Ты - классификатор запросов пользователей. Твоя задача - определить намерение пользователя.

ПРАВИЛА:
1. Отвечай ТОЛЬКО одним словом: 'sales' или 'support'
2. Используй следующие критерии:

SALES (если пользователь):
- Спрашивает о ценах, тарифах, демо
- Интересуется покупкой или условиями
- Хочет узнать о возможностях продукта
- Сравнивает тарифы
- Спрашивает об акциях или скидках

SUPPORT (если пользователь):
- Сообщает об ошибке или проблеме
- Просит помощи с настройкой
- Не может выполнить какое-то действие
- Жалуется на работу сервиса
- Спрашивает как пользоваться функцией

При неопределенности - классифицируй как 'support'""",
                model_settings={
                    "temperature": 0.1,
                    "candidate_count": 1,
                    "max_output_tokens": 128
                },
                result_type=ClassifierResult
            )
            
            print("Классификатор создан, запускаем...")
            result = await classifier.run(message)
            print(f"Результат классификации: {result.data}")
            
            intent = result.data.intent.strip().lower()
            print(f"Определен интент: {intent}")
            
            if intent not in ['sales', 'support']:
                print(f"Неопределенный интент: {intent}, используем support")
                return SupportNode()
                
            return SalesNode() if intent == 'sales' else SupportNode()
            
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
            
            # Конвертируем историю в формат модели
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
            
            # Конвертируем историю в формат модели
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