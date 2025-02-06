#!/bin/bash

# Загрузка переменных окружения
set -a
source .env
set +a

echo "Инициализация базы данных..."

# Параметры подключения
DB_NAME="gemini_bot"
DB_USER="gemini_user"
DB_PASSWORD="gemini_pass"

# Удаление пользователя и БД, если они существуют
sudo -u postgres psql << EOF
DROP DATABASE IF EXISTS $DB_NAME;
DROP USER IF EXISTS $DB_USER;

CREATE USER $DB_USER WITH LOGIN PASSWORD '$DB_PASSWORD';
CREATE DATABASE $DB_NAME WITH OWNER $DB_USER;
\connect $DB_NAME

-- Создание таблиц
CREATE TABLE chat_history (
    user_id BIGINT PRIMARY KEY,
    history JSONB NOT NULL
);

-- Тарифы и фичи
CREATE TABLE tariff_features (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    category TEXT NOT NULL CHECK (category IN ('Security', 'Analytics', 'Integration', 'Automation', 'UI')),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE sales_tariffs (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    price TEXT NOT NULL CHECK (price ~ '^(\d+ руб/мес|По запросу)$'),
    user_limit INTEGER NULL CHECK (user_limit IS NULL OR (user_limit BETWEEN 1 AND 100)),
    description TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE tariff_feature_relations (
    tariff_id INTEGER REFERENCES sales_tariffs(id) ON DELETE CASCADE,
    feature_id INTEGER REFERENCES tariff_features(id) ON DELETE CASCADE,
    is_premium BOOLEAN DEFAULT false,
    PRIMARY KEY (tariff_id, feature_id)
);

CREATE TABLE tariff_use_cases (
    id SERIAL PRIMARY KEY,
    tariff_id INTEGER REFERENCES sales_tariffs(id) ON DELETE CASCADE,
    scenario TEXT NOT NULL,
    solution TEXT NOT NULL,
    target_audience TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Поддержка
CREATE TABLE support_categories (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE CHECK (name IN ('Getting Started', 'Security', 'Billing', 'Technical Issues', 'Integration')),
    description TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Создаем перечисления для тегов по категориям
CREATE TYPE topic_tag AS ENUM ('installation', 'configuration', 'usage', 'error', 'billing');
CREATE TYPE difficulty_tag AS ENUM ('basic', 'intermediate', 'advanced');
CREATE TYPE component_tag AS ENUM ('ui', 'api', 'database', 'security', 'integration');

CREATE TABLE support_general (
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

CREATE TABLE support_tariff_specific (
    id SERIAL PRIMARY KEY,
    tariff_id INTEGER REFERENCES sales_tariffs(id) ON DELETE CASCADE,
    feature_id INTEGER REFERENCES tariff_features(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    priority INTEGER CHECK (priority BETWEEN 0 AND 5),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tariff_id, question)
);

CREATE TABLE support_question_relations (
    source_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL CHECK (relation_type IN ('related', 'prerequisite', 'followup')),
    source_type TEXT NOT NULL CHECK (source_type IN ('general', 'tariff')),
    target_type TEXT NOT NULL CHECK (target_type IN ('general', 'tariff')),
    PRIMARY KEY (source_id, target_id)
);

CREATE TABLE user_actions (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    action_type TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Индексы
CREATE INDEX idx_tariff_name ON sales_tariffs(name);
CREATE INDEX idx_feature_category ON tariff_features(category);
CREATE INDEX idx_feature_name ON tariff_features(name);
CREATE INDEX idx_support_category ON support_general(category_id);
CREATE INDEX idx_support_priority ON support_general(priority);
CREATE INDEX idx_support_tariff_priority ON support_tariff_specific(priority);

-- Полнотекстовый поиск
CREATE INDEX idx_tariff_fts ON sales_tariffs USING GIN(to_tsvector('russian', name || ' ' || description));
CREATE INDEX idx_feature_fts ON tariff_features USING GIN(to_tsvector('russian', name || ' ' || description));
CREATE INDEX idx_usecase_fts ON tariff_use_cases USING GIN(to_tsvector('russian', scenario || ' ' || solution || ' ' || target_audience));
CREATE INDEX idx_support_general_fts ON support_general USING GIN(to_tsvector('russian', question || ' ' || answer));
CREATE INDEX idx_support_tariff_fts ON support_tariff_specific USING GIN(to_tsvector('russian', question || ' ' || answer));

-- Права
GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $DB_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $DB_USER;
GRANT USAGE ON SCHEMA public TO $DB_USER;

-- Изменение владельца таблиц
ALTER TABLE chat_history OWNER TO $DB_USER;
ALTER TABLE tariff_features OWNER TO $DB_USER;
ALTER TABLE sales_tariffs OWNER TO $DB_USER;
ALTER TABLE tariff_feature_relations OWNER TO $DB_USER;
ALTER TABLE tariff_use_cases OWNER TO $DB_USER;
ALTER TABLE support_categories OWNER TO $DB_USER;
ALTER TABLE support_general OWNER TO $DB_USER;
ALTER TABLE support_tariff_specific OWNER TO $DB_USER;
ALTER TABLE support_question_relations OWNER TO $DB_USER;
ALTER TABLE user_actions OWNER TO $DB_USER;

EOF

echo "Создание индексов..."
psql -U ${DB_USER} -d ${DB_NAME} -f sql/create_indexes.sql

echo "Инициализация базы данных завершена!" 