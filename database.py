import asyncpg
from pydantic import TypeAdapter
from models import (
    Message, Tariff, SupportCase, TariffFeature, 
    TariffCreate, SupportCreate, SupportGeneralQuestion,
    TariffFeatureRef
)
from lru import LRU
from sqlalchemy import create_engine
import pandas as pd
import os
import json
from pydantic_ai.messages import ModelRequest, ModelResponse, UserPromptPart, TextPart, ModelMessage
from typing import Optional

class Database:
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.cache = LRU(1000)  # Кэш на 1000 запросов
        self.engine = create_engine(os.getenv("DATABASE_URL"))

    async def rag_search(self, collection: str, query: str):
        cache_key = f"{collection}:{query}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        async with self.pool.acquire() as conn:
            results = await conn.fetch(
                """SELECT content 
                FROM knowledge_base 
                WHERE collection = $1 
                AND to_tsvector('russian', content) @@ to_tsquery('russian', $2)
                ORDER BY ts_rank_cd(to_tsvector('russian', content), to_tsquery('russian', $2)) DESC
                LIMIT 3""",
                collection, query.replace(' ', ' | ')
            )
        
        self.cache[cache_key] = results
        return results

    async def get_history(self, user_id: int, limit: int = 5) -> list[Message]:
        """
        Получает историю сообщений пользователя
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество сообщений
            
        Returns:
            list[Message]: Список сообщений в хронологическом порядке
        """
        async with self.pool.acquire() as conn:
            messages = await conn.fetch(
                """
                SELECT id, role, content, created_at, parent_message_id
                FROM messages 
                WHERE user_id = $1 
                ORDER BY created_at DESC 
                LIMIT $2
                """,
                user_id, limit
            )
            
            return [Message(
                id=msg['id'],
                role=msg['role'],
                content=msg['content'],
                timestamp=msg['created_at'],
                parent_message_id=msg['parent_message_id']
            ) for msg in reversed(messages)]

    async def save_message(self, user_id: int, role: str, content: str):
        """Сохранение сообщения с дополнительными проверками"""
        # Проверка на наличие скрытых инструкций
        if any(tag in content for tag in ["{Z}", "<|vq_", "LIBERATED_ASSISTANT"]):
            self.logger.warning(f"Блокировка сообщения с тегами: {content}")
            return
        
        # Ограничение длины сохраняемых сообщений
        cleaned_content = content[:2000]  # Обрезаем слишком длинные сообщения
        
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO messages (user_id, role, content) VALUES ($1, $2, $3)",
                user_id, role, cleaned_content
            )

    async def log_action(self, user_id: int, action_type: str, details: str):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO user_actions (user_id, action_type, details) VALUES ($1, $2, $3)",
                user_id, action_type, details
            )

    async def log_error(self, user_id: int, error_message: str):
        # Логируем ошибку как действие с типом "error"
        await self.log_action(user_id, "error", error_message)

    async def init_db(self):
        """Инициализация базы данных и создание необходимых таблиц"""
        async with self.pool.acquire() as conn:
            # Сначала создаем ENUM типы
            await conn.execute("""
                DO $$ 
                BEGIN
                    -- Создаем ENUM типы если они не существуют
                    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'topic_tag') THEN
                        CREATE TYPE topic_tag AS ENUM ('installation', 'configuration', 'usage', 'error', 'billing');
                    END IF;
                    
                    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'difficulty_tag') THEN
                        CREATE TYPE difficulty_tag AS ENUM ('basic', 'intermediate', 'advanced');
                    END IF;
                    
                    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'component_tag') THEN
                        CREATE TYPE component_tag AS ENUM ('ui', 'api', 'database', 'security', 'integration');
                    END IF;
                END $$;
            """)
            
            # Затем создаем таблицы
            await conn.execute("""
                -- Основные таблицы
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    parent_message_id INTEGER REFERENCES messages(id)
                );

                CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
                CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
                CREATE INDEX IF NOT EXISTS idx_messages_user_created ON messages(user_id, created_at);
                
                -- Тарифы и фичи
                CREATE TABLE IF NOT EXISTS tariff_features (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL,
                    category TEXT NOT NULL CHECK (category IN ('Security', 'Analytics', 'Integration', 'Automation', 'UI')),
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS sales_tariffs (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    price TEXT NOT NULL CHECK (price ~ '^(\d+ руб/мес|По запросу)$'),
                    user_limit INTEGER NULL CHECK (user_limit IS NULL OR (user_limit BETWEEN 1 AND 100)),
                    description TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS tariff_feature_relations (
                    tariff_id INTEGER REFERENCES sales_tariffs(id) ON DELETE CASCADE,
                    feature_id INTEGER REFERENCES tariff_features(id) ON DELETE CASCADE,
                    is_premium BOOLEAN DEFAULT false,
                    PRIMARY KEY (tariff_id, feature_id)
                );

                CREATE TABLE IF NOT EXISTS tariff_use_cases (
                    id SERIAL PRIMARY KEY,
                    tariff_id INTEGER REFERENCES sales_tariffs(id) ON DELETE CASCADE,
                    scenario TEXT NOT NULL,
                    solution TEXT NOT NULL,
                    target_audience TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                -- Поддержка
                CREATE TABLE IF NOT EXISTS support_categories (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE CHECK (name IN ('Getting Started', 'Security', 'Billing', 'Technical Issues', 'Integration')),
                    description TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS support_general (
                    id SERIAL PRIMARY KEY,
                    category_id INTEGER REFERENCES support_categories(id) ON DELETE CASCADE,
                    question TEXT NOT NULL UNIQUE,
                    answer TEXT NOT NULL,
                    topic_tags topic_tag[] NOT NULL CHECK (array_length(topic_tags, 1) BETWEEN 1 AND 3),
                    difficulty difficulty_tag NOT NULL,
                    component_tags component_tag[] NOT NULL CHECK (array_length(component_tags, 1) BETWEEN 1 AND 3),
                    priority INTEGER CHECK (priority BETWEEN 0 AND 5),
                    created_at TIMESTAMP DEFAULT NOW()
                );

                CREATE TABLE IF NOT EXISTS support_tariff_specific (
                    id SERIAL PRIMARY KEY,
                    tariff_id INTEGER REFERENCES sales_tariffs(id) ON DELETE CASCADE,
                    feature_id INTEGER REFERENCES tariff_features(id) ON DELETE CASCADE,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    priority INTEGER CHECK (priority BETWEEN 0 AND 5),
                    created_at TIMESTAMP DEFAULT NOW(),
                    UNIQUE(tariff_id, question)
                );

                CREATE TABLE IF NOT EXISTS support_question_relations (
                    source_id INTEGER NOT NULL,
                    target_id INTEGER NOT NULL,
                    relation_type TEXT NOT NULL CHECK (relation_type IN ('related', 'prerequisite', 'followup')),
                    source_type TEXT NOT NULL CHECK (source_type IN ('general', 'tariff')),
                    target_type TEXT NOT NULL CHECK (target_type IN ('general', 'tariff')),
                    PRIMARY KEY (source_id, target_id)
                );

                -- Действия пользователей
                CREATE TABLE IF NOT EXISTS user_actions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    action_type TEXT NOT NULL,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                );

                -- Индексы
                CREATE INDEX IF NOT EXISTS idx_tariff_name ON sales_tariffs(name);
                CREATE INDEX IF NOT EXISTS idx_feature_category ON tariff_features(category);
                CREATE INDEX IF NOT EXISTS idx_feature_name ON tariff_features(name);
                CREATE INDEX IF NOT EXISTS idx_support_category ON support_general(category_id);
                CREATE INDEX IF NOT EXISTS idx_support_priority ON support_general(priority);
                CREATE INDEX IF NOT EXISTS idx_support_tariff_priority ON support_tariff_specific(priority);

                -- Полнотекстовый поиск
                CREATE INDEX IF NOT EXISTS idx_tariff_fts ON sales_tariffs USING GIN(to_tsvector('russian', name || ' ' || description));
                CREATE INDEX IF NOT EXISTS idx_feature_fts ON tariff_features USING GIN(to_tsvector('russian', name || ' ' || description));
                CREATE INDEX IF NOT EXISTS idx_usecase_fts ON tariff_use_cases USING GIN(to_tsvector('russian', scenario || ' ' || solution || ' ' || target_audience));
                CREATE INDEX IF NOT EXISTS idx_support_general_fts ON support_general USING GIN(to_tsvector('russian', question || ' ' || answer));
                CREATE INDEX IF NOT EXISTS idx_support_tariff_fts ON support_tariff_specific USING GIN(to_tsvector('russian', question || ' ' || answer));
            """)

    async def check_rate_limit(self, user_id: int):
        async with self.pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM user_actions WHERE user_id = $1 AND created_at > NOW() - INTERVAL '1 minute'",
                user_id
            )
            return count < 10  # 10 запросов в минуту 

    async def insert_tariff(self, name, price, user_limit, features, example):
        await self.pool.execute(
            "INSERT INTO sales_tariffs (name, price, user_limit, features, examples) "
            "VALUES ($1, $2, $3, $4, $5) "
            "ON CONFLICT (name) DO NOTHING",
            name, price, user_limit, features, example
        )

    async def insert_support(self, problem, causes, steps, example):
        await self.pool.execute(
            "INSERT INTO support_solutions (problem, causes, steps, examples) "
            "VALUES ($1, $2, $3, $4::jsonb) "
            "ON CONFLICT (problem) DO NOTHING",
            problem, causes, steps, json.dumps(example)
        )

    async def bulk_insert_tariffs(self, tariffs: list[Tariff]):
        await self.pool.executemany(
            "INSERT INTO sales_tariffs (name, price, user_limit, features, examples) "
            "VALUES ($1, $2, $3, $4, $5::jsonb) "
            "ON CONFLICT (name) DO NOTHING",
            [(t.name, t.price, t.user_limit, t.features, json.dumps(t.example, ensure_ascii=False)) for t in tariffs]
        )

    def export_to_dataframe(self, table_name: str) -> pd.DataFrame:
        """Экспорт таблицы в DataFrame"""
        return pd.read_sql_table(
            table_name,
            self.engine,
            schema='public'
        )

    async def insert_knowledge(self, item: dict):
        await self.pool.execute(
            "INSERT INTO knowledge_base (collection, metadata, content) VALUES ($1, $2, $3)",
            item['collection'], json.dumps(item['metadata']), item['content']
        )

    def convert_to_model_messages(self, history: list[Message]) -> list[ModelMessage]:
        """
        Конвертирует список объектов Message в список объектов ModelMessage для pydantic-ai.
        """
        model_messages = []
        print("\n=== convert_to_model_messages ===")
        print(f"Исходная история ({len(history)} сообщений)")

        for msg in history:
            try:
                if msg.role == "user":
                    # Создаем ModelRequest для сообщений пользователя
                    model_message = ModelRequest(
                        parts=[UserPromptPart(
                            content=msg.content,
                            timestamp=msg.timestamp
                        )],
                        kind="request"
                    )
                elif msg.role == "assistant":
                    # Создаем ModelResponse для ответов ассистента
                    model_message = ModelResponse(
                        parts=[TextPart(
                            content=msg.content
                        )],
                        kind="response",
                        model_name="assistant",
                        timestamp=msg.timestamp
                    )
                else:
                    print(f"Неизвестная роль сообщения: {msg.role}. Пропускаем.")
                    continue

                model_messages.append(model_message)
                print(f"Успешно сконвертировано сообщение: {msg.role}")

            except Exception as e:
                print(f"Ошибка при конвертации сообщения: {str(e)}")
                continue

        print(f"Сконвертировано {len(model_messages)} сообщений")
        return model_messages

    async def save_features(self, features: list[TariffFeature]):
        """Сохранение фич тарифов"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for feature in features:
                    feature.id = await conn.fetchval(
                        """INSERT INTO tariff_features (name, description, category)
                        VALUES ($1, $2, $3)
                        RETURNING id""",
                        feature.name, feature.description, feature.category
                    )
                    print(f"Сохранена фича: {feature.name} (ID: {feature.id})")

    async def save_tariffs(self, tariffs: list[TariffCreate]):
        """Сохранение тарифов со всеми связанными данными"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for tc in tariffs:
                    # Сохраняем тариф
                    tariff_id = await conn.fetchval(
                        """INSERT INTO sales_tariffs (name, price, user_limit, description)
                        VALUES ($1, $2, $3, $4)
                        RETURNING id""",
                        tc.tariff.name, tc.tariff.price, tc.tariff.user_limit, tc.tariff.description
                    )
                    print(f"Сохранен тариф: {tc.tariff.name} (ID: {tariff_id})")

                    # Связываем с фичами
                    for feature_ref in tc.features:
                        await conn.execute(
                            """INSERT INTO tariff_feature_relations (tariff_id, feature_id, is_premium)
                            VALUES ($1, $2, $3)""",
                            tariff_id, feature_ref.feature_id, feature_ref.is_premium
                        )
                        print(f"Связана фича {feature_ref.feature_id} с тарифом {tariff_id}")

                    # Сохраняем примеры использования
                    for use_case in tc.use_cases:
                        await conn.execute(
                            """INSERT INTO tariff_use_cases (tariff_id, scenario, solution, target_audience)
                            VALUES ($1, $2, $3, $4)""",
                            tariff_id, use_case.scenario, use_case.solution, use_case.target_audience
                        )

                    # Сохраняем вопросы по тарифу
                    for question in tc.support_questions:
                        await conn.execute(
                            """INSERT INTO support_tariff_specific 
                            (tariff_id, feature_id, question, answer, priority)
                            VALUES ($1, $2, $3, $4, $5)""",
                            tariff_id, question.feature_id, question.question, 
                            question.answer, question.priority
                        )

    async def save_support(self, categories: list[SupportCreate]):
        """Сохранение категорий поддержки с вопросами"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for sc in categories:
                    # Сохраняем категорию
                    category_id = await conn.fetchval(
                        """INSERT INTO support_categories (name, description)
                        VALUES ($1, $2)
                        RETURNING id""",
                        sc.category.name, sc.category.description
                    )
                    print(f"Сохранена категория: {sc.category.name} (ID: {category_id})")

                    # Сохраняем вопросы
                    for question in sc.questions:
                        # Разделяем теги по категориям
                        topic_tags = [tag for tag in question.tags if tag in ['installation', 'configuration', 'usage', 'error', 'billing']]
                        difficulty = next((tag for tag in question.tags if tag in ['basic', 'intermediate', 'advanced']), 'basic')
                        component_tags = [tag for tag in question.tags if tag in ['ui', 'api', 'database', 'security', 'integration']]
                        
                        await conn.execute(
                            """INSERT INTO support_general 
                            (category_id, question, answer, topic_tags, difficulty, component_tags, priority)
                            VALUES ($1, $2, $3, $4, $5::difficulty_tag, $6, $7)""",
                            category_id, question.question, question.answer,
                            topic_tags, difficulty, component_tags, question.priority
                        )
                        print(f"Сохранен вопрос для категории {sc.category.name}")

                    # Сохраняем связи между вопросами
                    for relation in sc.relations:
                        await conn.execute(
                            """INSERT INTO support_question_relations 
                            (source_id, target_id, relation_type, source_type, target_type)
                            VALUES ($1, $2, $3, $4, $5)""",
                            relation.source_id, relation.target_id,
                            relation.relation_type, relation.source_type,
                            relation.target_type
                        ) 

    async def load_features(self) -> list[TariffFeature]:
        """Загрузка существующих фич из базы данных"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT id, name, description, category, created_at 
                FROM tariff_features 
                ORDER BY id"""
            )
            return [TariffFeature(
                id=row['id'],
                name=row['name'],
                description=row['description'],
                category=row['category'],
                created_at=row['created_at']
            ) for row in rows]

    async def check_feature_exists(self, name: str) -> bool:
        """Проверка существования фичи по имени"""
        async with self.pool.acquire() as conn:
            exists = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM tariff_features WHERE name = $1)",
                name
            )
            return exists 

    async def get_all_tariffs(self) -> list[dict]:
        """Получение всех тарифов с их фичами и примерами использования"""
        async with self.pool.acquire() as conn:
            # Сначала получаем базовую информацию о тарифах
            tariffs = await conn.fetch("""
                SELECT 
                    id, name, price, user_limit, description
                FROM sales_tariffs
                ORDER BY 
                    CASE 
                        WHEN price = 'По запросу' THEN 999999
                        ELSE CAST(regexp_replace(price, '[^0-9]', '', 'g') AS INTEGER)
                    END;
            """)
            
            result = []
            for tariff in tariffs:
                # Получаем фичи для тарифа
                features = await conn.fetch("""
                    SELECT 
                        f.id, f.name, f.description, f.category, tfr.is_premium
                    FROM tariff_features f
                    JOIN tariff_feature_relations tfr ON f.id = tfr.feature_id
                    WHERE tfr.tariff_id = $1
                """, tariff['id'])
                
                # Получаем примеры использования
                use_cases = await conn.fetch("""
                    SELECT scenario, solution, target_audience
                    FROM tariff_use_cases
                    WHERE tariff_id = $1
                """, tariff['id'])
                
                result.append({
                    "id": tariff['id'],
                    "name": tariff['name'],
                    "price": tariff['price'],
                    "user_limit": tariff['user_limit'],
                    "description": tariff['description'],
                    "features": [dict(f) for f in features],
                    "use_cases": [dict(u) for u in use_cases]
                })
            
            return result

    async def get_tariff_by_name(self, name: str) -> Optional[dict]:
        """Получение тарифа по имени"""
        async with self.pool.acquire() as conn:
            return await conn.fetchrow("""
                WITH tariff_features AS (
                    SELECT 
                        t.id as tariff_id,
                        json_agg(json_build_object(
                            'id', f.id,
                            'name', f.name,
                            'description', f.description,
                            'category', f.category,
                            'is_premium', tf.is_premium
                        )) as features
                    FROM sales_tariffs t
                    LEFT JOIN tariff_feature_relations tf ON t.id = tf.tariff_id
                    LEFT JOIN tariff_features f ON tf.feature_id = f.id
                    WHERE t.name = $1
                    GROUP BY t.id
                ),
                tariff_use_cases AS (
                    SELECT 
                        tariff_id,
                        json_agg(json_build_object(
                            'scenario', scenario,
                            'solution', solution,
                            'target_audience', target_audience
                        )) as use_cases
                    FROM tariff_use_cases
                    WHERE tariff_id IN (SELECT id FROM sales_tariffs WHERE name = $1)
                    GROUP BY tariff_id
                )
                SELECT 
                    t.id,
                    t.name,
                    t.price,
                    t.user_limit,
                    t.description,
                    COALESCE(tf.features, '[]'::json) as features,
                    COALESCE(tuc.use_cases, '[]'::json) as use_cases
                FROM sales_tariffs t
                LEFT JOIN tariff_features tf ON t.id = tf.tariff_id
                LEFT JOIN tariff_use_cases tuc ON t.id = tuc.tariff_id
                WHERE t.name = $1;
            """, name)

    async def search_features(self, query: str) -> list[dict]:
        """Поиск фич по текстовому запросу"""
        async with self.pool.acquire() as conn:
            return await conn.fetch("""
                SELECT 
                    id, name, description, category,
                    ts_rank_cd(to_tsvector('russian', name || ' ' || description), 
                             plainto_tsquery('russian', $1)) as relevance
                FROM tariff_features
                WHERE to_tsvector('russian', name || ' ' || description) @@ 
                      plainto_tsquery('russian', $1)
                ORDER BY relevance DESC
                LIMIT 5;
            """, query)

    async def get_support_questions(self, category: Optional[str] = None) -> list[dict]:
        """Получение вопросов поддержки по категории"""
        async with self.pool.acquire() as conn:
            if category:
                return await conn.fetch("""
                    SELECT 
                        q.id, q.question, q.answer, q.priority,
                        q.topic_tags, q.difficulty, q.component_tags,
                        c.name as category
                    FROM support_general q
                    JOIN support_categories c ON q.category_id = c.id
                    WHERE c.name = $1
                    ORDER BY q.priority DESC;
                """, category)
            else:
                return await conn.fetch("""
                    SELECT 
                        q.id, q.question, q.answer, q.priority,
                        q.topic_tags, q.difficulty, q.component_tags,
                        c.name as category
                    FROM support_general q
                    JOIN support_categories c ON q.category_id = c.id
                    ORDER BY c.name, q.priority DESC;
                """) 

    async def clear_history(self, user_id: int):
        """Очистка всей истории пользователя"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Очищаем сообщения
                await conn.execute(
                    "DELETE FROM messages WHERE user_id = $1",
                    user_id
                )
                
                # Очищаем действия пользователя
                await conn.execute(
                    "DELETE FROM user_actions WHERE user_id = $1",
                    user_id
                )
                
                # Очищаем кэш
                self.cache.clear()
                
                print(f"История пользователя {user_id} полностью очищена") 