
ALTER DEFAULT PRIVILEGES IN SCHEMA gs_sys GRANT ALL ON TABLES TO generation;

-- Предоставление прав на использование схемы
GRANT USAGE ON SCHEMA gs_sys TO generation;

-- Предоставление прав на создание объектов в схеме
GRANT CREATE ON SCHEMA gs_sys TO generation;

-- Предоставление прав на все последовательности (sequences)
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA gs_sys TO generation;
ALTER DEFAULT PRIVILEGES IN SCHEMA gs_sys GRANT ALL ON SEQUENCES TO generation;



-- Простой SQL скрипт для предоставления прав на работу со схемой gs_sys
-- Выполнить от имени суперпользователя PostgreSQL (например, postgres)
--
-- Использование:
--   1. При необходимости замените имя пользователя (сейчас: generation)
--   2. Выполните скрипт:
--      psql -U postgres -d your_database_name -f scripts/grant_permissions_gs_sys_simple.sql
--
-- Или выполните команды напрямую через psql:
--   psql -U postgres -d your_database_name
--   GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA gs_sys TO ваш_пользователь;

-- ============================================================
-- ВАЖНО: При необходимости замените 'generation' на имя пользователя БД
-- ============================================================

-- Предоставление прав на существующие таблицы в схеме gs_sys
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA gs_sys TO generation;

-- Предоставление прав на будущие таблицы в схеме gs_sys