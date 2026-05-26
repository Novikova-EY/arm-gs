# Быстрый старт: Настройка параллельной работы

Краткая инструкция для запуска приложения с поддержкой параллельной работы нескольких пользователей.

> **⚠️ Важно для пользователей Windows:** Gunicorn не работает на Windows! Используйте `requirements-windows.txt` и Waitress. См. [WINDOWS_SETUP.md](WINDOWS_SETUP.md)

## Шаг 1: Установка зависимостей

### Windows:
```cmd
# Активация виртуального окружения
venv\Scripts\activate

# Установка пакетов для Windows
pip install -r requirements-windows.txt
```

### Linux/Mac:
```bash
# Активация виртуального окружения
source venv/bin/activate

# Установка пакетов для Linux/Mac
pip install -r requirements-linux.txt
```

## Шаг 2: Настройка Redis (опционально, но рекомендуется)

### Windows:
Скачайте Redis для Windows: https://github.com/microsoftarchive/redis/releases

```cmd
# Запуск Redis
redis-server
```

### Linux:
```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

### Docker:
```bash
docker run -d -p 6379:6379 --name redis redis:latest
```

Если Redis недоступен, приложение автоматически переключится на SimpleCache.

## Шаг 3: Настройка переменных окружения

Скопируйте `env.example` в `.env` и настройте:

```bash
copy env.example .env  # Windows
cp env.example .env    # Linux/Mac
```

Минимальная конфигурация в `.env`:

```env
# Database
DB_USER=your_db_user
DB_PASS=your_db_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_db_name

# Redis (если используется)
REDIS_URL=redis://localhost:6379/0

# Gunicorn
GUNICORN_WORKERS=9
GUNICORN_WORKER_CLASS=gevent
```

## Шаг 4: Применение миграций

Добавьте колонки версионирования в базу данных:

```bash
flask db upgrade
# или
alembic upgrade head
```

## Шаг 5: Настройка PostgreSQL

Убедитесь, что PostgreSQL настроен для множественных соединений:

```sql
-- Минимум 100+ соединений для production
SHOW max_connections;
ALTER SYSTEM SET max_connections = 200;
-- Перезапустите PostgreSQL
```

## Шаг 6: Запуск приложения

### Development:
```bash
python run.py
```

### Production (рекомендуется):

**Windows (Waitress):**
```cmd
start_production.bat
# Или напрямую
python start_waitress.py
```

**Linux/Mac (Gunicorn):**
```bash
chmod +x start_production.sh
./start_production.sh
# Или напрямую
gunicorn --config gunicorn_config.py run:app
```

## Проверка работы

1. Откройте браузер: http://localhost:8000
2. Авторизуйтесь в системе
3. Попробуйте открыть одну и ту же страницу в нескольких вкладках
4. Попробуйте одновременно редактировать данные - система должна предупредить о конфликте

## Быстрая диагностика

### Проверка Redis:
```bash
redis-cli ping
# Должно вернуть: PONG
```

### Проверка соединений PostgreSQL:
```sql
SELECT count(*) FROM pg_stat_activity;
```

### Логи Gunicorn:
```bash
# Логи выводятся в консоль
# При использовании systemd:
sudo journalctl -u fproject -f
```

## Конфигурация для разных нагрузок

### Малая (до 50 пользователей):
```env
GUNICORN_WORKERS=5
SQLALCHEMY_POOL_SIZE=10
SQLALCHEMY_MAX_OVERFLOW=20
```

### Средняя (50-200 пользователей):
```env
GUNICORN_WORKERS=9
SQLALCHEMY_POOL_SIZE=20
SQLALCHEMY_MAX_OVERFLOW=40
```

## Что было добавлено?

✅ **Gunicorn (Linux/Mac)** - production WSGI сервер с gevent workers  
✅ **Waitress (Windows)** - production WSGI сервер для Windows  
✅ **Redis** - кэширование и сессии  
✅ **Версионирование** - оптимистическая блокировка для Station и Machine  
✅ **Middleware** - автоматическая обработка concurrent updates  
✅ **Connection Pool** - оптимизированный пул соединений PostgreSQL  
✅ **Декораторы** - для кэширования и retry механизма  

## Дополнительная документация

- **Для Windows**: `WINDOWS_SETUP.md` - **НАЧНИТЕ С ЭТОГО!**
- **Полная инструкция**: `CONCURRENCY_SETUP.md`
- **Примеры интеграции**: `INTEGRATION_EXAMPLES.md`

## Помощь

При возникновении проблем смотрите раздел "Troubleshooting" в `CONCURRENCY_SETUP.md`.

---

**Важно**: В production обязательно измените `SECRET_KEY` в `.env` на случайное значение!

