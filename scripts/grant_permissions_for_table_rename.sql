-- SQL скрипт для предоставления прав на переименование таблиц в схеме refdata
-- Выполнить этот скрипт от имени суперпользователя PostgreSQL или владельца схемы refdata
-- 
-- Использование:
--   psql -U postgres -d your_database_name -f scripts/grant_permissions_for_table_rename.sql
-- 
-- Или с указанием конкретного пользователя (замените 'ваш_пользователь'):
--   psql -U postgres -d your_database_name -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA refdata TO ваш_пользователь;"
--
-- Или выполните все команды по очереди, заменив 'ваш_пользователь' на имя пользователя из DB_USER

-- ВАЖНО: Замените 'ваш_пользователь' на имя пользователя из переменной окружения DB_USER
-- Для этого можно сначала выполнить: \set db_user 'ваш_пользователь'

-- Если не указан пользователь, используем текущего пользователя
\set db_user :db_user
\if :{?db_user}
\else
  \prompt 'Введите имя пользователя БД: ' db_user
\endif

\echo 'Предоставление прав пользователю: ' :db_user

-- Предоставление прав на существующие таблицы в схеме refdata
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA refdata TO :'db_user';

-- Предоставление прав на будущие таблицы в схеме refdata
ALTER DEFAULT PRIVILEGES IN SCHEMA refdata GRANT ALL ON TABLES TO :'db_user';

-- Предоставление прав на использование схемы
GRANT USAGE ON SCHEMA refdata TO :'db_user';

-- Предоставление прав на создание объектов в схеме
GRANT CREATE ON SCHEMA refdata TO :'db_user';

-- Предоставление прав на все последовательности (sequences)
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA refdata TO :'db_user';
ALTER DEFAULT PRIVILEGES IN SCHEMA refdata GRANT ALL ON SEQUENCES TO :'db_user';

\echo 'Права предоставлены успешно!'

