-- Индексы для таблицы chat_history
CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON chat_history(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_created_at ON chat_history(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_history_message_type ON chat_history(message_type);

-- Полнотекстовый поиск для сообщений
CREATE INDEX IF NOT EXISTS idx_chat_history_message_text_fts ON chat_history 
USING gin(to_tsvector('russian', message_text));

-- Индексы для тарифов
CREATE INDEX IF NOT EXISTS idx_sales_tariffs_price ON sales_tariffs(price);
CREATE INDEX IF NOT EXISTS idx_sales_tariffs_name ON sales_tariffs(name);
CREATE INDEX IF NOT EXISTS idx_sales_tariffs_created_at ON sales_tariffs(created_at);

-- Индексы для фич тарифов
CREATE INDEX IF NOT EXISTS idx_tariff_features_category ON tariff_features(category);
CREATE INDEX IF NOT EXISTS idx_tariff_features_name ON tariff_features(name);

-- Индексы для категорий поддержки
CREATE INDEX IF NOT EXISTS idx_support_categories_name ON support_categories(name);
CREATE INDEX IF NOT EXISTS idx_support_categories_priority ON support_categories(priority);

-- Полнотекстовый поиск для вопросов поддержки
CREATE INDEX IF NOT EXISTS idx_support_questions_fts ON support_general_questions 
USING gin(to_tsvector('russian', question || ' ' || answer));

-- Индексы для действий пользователей
CREATE INDEX IF NOT EXISTS idx_user_actions_user_id ON user_actions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_actions_action_type ON user_actions(action_type);
CREATE INDEX IF NOT EXISTS idx_user_actions_created_at ON user_actions(created_at);

-- Составные индексы для часто используемых запросов
CREATE INDEX IF NOT EXISTS idx_chat_history_user_date ON chat_history(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_user_actions_user_date ON user_actions(user_id, created_at);

-- Индексы для связей между таблицами
CREATE INDEX IF NOT EXISTS idx_tariff_features_tariff_id ON tariff_features(tariff_id);
CREATE INDEX IF NOT EXISTS idx_support_questions_category_id ON support_general_questions(category_id);

-- Индексы для таблицы messages
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_user_created ON messages(user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_messages_parent ON messages(parent_message_id);

-- Полнотекстовый поиск для сообщений
CREATE INDEX IF NOT EXISTS idx_messages_content_fts ON messages 
USING gin(to_tsvector('russian', content)); 