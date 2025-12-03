# Инструкция по предоставлению прав для миграции переименования таблиц

Перед выполнением миграции `ff9f0f8940c8_add_gs_prefix_to_refdata_tables.py` необходимо предоставить права на переименование таблиц в схеме `refdata`.

## Способ 1: Использование Python-скрипта (рекомендуется)

Скрипт автоматически определит пользователя из переменных окружения:

```bash
python scripts/grant_permissions_for_table_rename.py
```

Или указать пользователя явно:

```bash
python scripts/grant_permissions_for_table_rename.py --user ваш_пользователь
```

## Способ 2: Использование SQL-скриптов через psql

### Вариант 2.1: Простой SQL-скрипт для схемы `refdata`

1. Откройте файл `scripts/grant_permissions_simple.sql`
2. Замените `'ваш_пользователь'` на имя пользователя из переменной окружения `DB_USER`
3. Выполните скрипт от имени суперпользователя:

```bash
psql -U postgres -d your_database_name -f scripts/grant_permissions_simple.sql
```

### Вариант 2.2: Простой SQL-скрипт для новой схемы `gs_sys`

После выполнения миграции переименования схемы (`7e4b6c9f1a23_rename_refdata_schema_to_gs_sys.py`)
права нужно выдать уже на новую схему `gs_sys`:

1. Откройте файл `scripts/grant_permissions_gs_sys_simple.sql`
2. При необходимости замените пользователя `generation` на имя пользователя из переменной окружения `DB_USER`
3. Выполните скрипт от имени суперпользователя:

```bash
psql -U postgres -d your_database_name -f scripts/grant_permissions_gs_sys_simple.sql
```

### Вариант 2.3: Через psql напрямую

```bash
# Подключитесь к БД от имени суперпользователя
psql -U postgres -d your_database_name

# Выполните следующие команды (замените 'ваш_пользователь' на имя пользователя):
-- для старой схемы refdata
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA refdata TO ваш_пользователь;
ALTER DEFAULT PRIVILEGES IN SCHEMA refdata GRANT ALL ON TABLES TO ваш_пользователь;
GRANT USAGE ON SCHEMA refdata TO ваш_пользователь;
GRANT CREATE ON SCHEMA refdata TO ваш_пользователь;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA refdata TO ваш_пользователь;
ALTER DEFAULT PRIVILEGES IN SCHEMA refdata GRANT ALL ON SEQUENCES TO ваш_пользователь;

-- для новой схемы gs_sys (после миграции переименования схемы)
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA gs_sys TO ваш_пользователь;
ALTER DEFAULT PRIVILEGES IN SCHEMA gs_sys GRANT ALL ON TABLES TO ваш_пользователь;
GRANT USAGE ON SCHEMA gs_sys TO ваш_пользователь;
GRANT CREATE ON SCHEMA gs_sys TO ваш_пользователь;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA gs_sys TO ваш_пользователь;
ALTER DEFAULT PRIVILEGES IN SCHEMA gs_sys GRANT ALL ON SEQUENCES TO ваш_пользователь;
```

## Способ 3: Через переменные окружения

Если у вас есть доступ к переменным окружения, выполните:

```bash
# Узнайте имя пользователя БД
echo $DB_USER  # Linux/Mac
echo %DB_USER%  # Windows CMD
$env:DB_USER   # Windows PowerShell

# Затем выполните SQL-команды с этим пользователем
```

## После предоставления прав

После успешного предоставления прав выполните миграцию:

```bash
flask db upgrade
```

## Проверка прав

Чтобы проверить, что права предоставлены, выполните в psql:

```sql
\dp refdata.*
```

Вы должны увидеть права доступа для вашего пользователя.

