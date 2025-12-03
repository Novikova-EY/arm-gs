-- Простой SQL скрипт для предоставления прав на переименование таблиц
-- Выполнить от имени суперпользователя PostgreSQL (например, postgres)
--
-- Использование:
--   1. Замените 'ваш_пользователь' на имя пользователя из переменной окружения DB_USER
--   2. Выполните скрипт:
--      psql -U postgres -d your_database_name -f scripts/grant_permissions_simple.sql
--
-- Или выполните команды напрямую через psql:
--   psql -U postgres -d your_database_name
--   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA refdata TO ваш_пользователь;

-- ============================================================
-- ВАЖНО: Замените 'ваш_пользователь' на имя пользователя БД
-- ============================================================

-- Предоставление прав на существующие таблицы в схеме refdata
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA refdata TO generation;

-- Предоставление прав на будущие таблицы в схеме refdata
ALTER DEFAULT PRIVILEGES IN SCHEMA refdata GRANT ALL ON TABLES TO generation;

-- Предоставление прав на использование схемы
GRANT USAGE ON SCHEMA refdata TO generation;

-- Предоставление прав на создание объектов в схеме
GRANT CREATE ON SCHEMA refdata TO generation;

-- Предоставление прав на все последовательности (sequences)
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA refdata TO generation;
ALTER DEFAULT PRIVILEGES IN SCHEMA refdata GRANT ALL ON SEQUENCES TO generation;

