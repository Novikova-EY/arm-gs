# Настройка параллельной работы пользователей

Этот документ описывает настройку и использование функций параллельной работы нескольких пользователей в приложении.

## Оглавление

1. [Обзор](#обзор)
2. [Требования](#требования)
3. [Установка зависимостей](#установка-зависимостей)
4. [Настройка](#настройка)
5. [Запуск приложения](#запуск-приложения)
6. [Использование возможностей](#использование-возможностей)
7. [Мониторинг и отладка](#мониторинг-и-отладка)
8. [Лучшие практики](#лучшие-практики)

---

## Обзор

Приложение поддерживает параллельную работу нескольких пользователей благодаря следующим компонентам:

### 1. **Production WSGI Server (Gunicorn)**
- Многопроцессная архитектура с использованием gevent workers
- Поддержка до 1000+ одновременных соединений на worker
- Автоматическое масштабирование на основе количества CPU

### 2. **Оптимизированный пул соединений PostgreSQL**
- Настройка pool_size и max_overflow для обработки множественных запросов
- Pool pre-ping для проверки жизнеспособности соединений
- Автоматическое переиспользование соединений

### 3. **Оптимистическая блокировка (Optimistic Locking)**
- Версионирование записей в БД
- Предотвращение конфликтов при одновременном редактировании
- Graceful обработка ошибок concurrent updates

### 4. **Redis для кэширования и сессий**
- Быстрое кэширование часто используемых данных
- Распределенные сессии пользователей
- Снижение нагрузки на БД

### 5. **Middleware для обработки concurrent updates**
- Автоматическая обработка конфликтов версий
- Retry механизм для временных ошибок
- Информативные сообщения для пользователей

---

## Требования

### Системные требования
- Python 3.8+
- PostgreSQL 12+
- Redis 6+ (опционально, но рекомендуется)
- 4+ CPU cores (рекомендуется для production)
- 8+ GB RAM (рекомендуется для production)

### Python пакеты
Все зависимости указаны в `requirements.txt`:
```
gunicorn==21.2.0
redis==5.0.1
Flask-Caching==2.1.0
Flask-Session==0.6.0
gevent==24.2.1
```

---

## Установка зависимостей

### 1. Активация виртуального окружения

**Windows:**
```cmd
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 2. Установка Python пакетов

```bash
pip install -r requirements.txt
```

### 3. Установка и настройка Redis (опционально, но рекомендуется)

**Windows:**
Скачайте Redis для Windows: https://github.com/microsoftarchive/redis/releases
```cmd
# Запуск Redis
redis-server
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install redis-server
sudo systemctl start redis
sudo systemctl enable redis
```

**Docker:**
```bash
docker run -d -p 6379:6379 --name redis redis:latest
```

### 4. Настройка PostgreSQL

Убедитесь, что PostgreSQL настроен для поддержки множественных соединений:

```sql
-- Проверка максимального количества соединений
SHOW max_connections;

-- Рекомендуется установить как минимум 100+ для production
ALTER SYSTEM SET max_connections = 200;

-- Перезапуск PostgreSQL для применения изменений
```

---

## Настройка

### 1. Переменные окружения

Создайте или обновите файл `.env`:

```env
# Database configuration
DB_USER=your_db_user
DB_PASS=your_db_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_db_name

# Connection pool settings
SQLALCHEMY_POOL_SIZE=20
SQLALCHEMY_MAX_OVERFLOW=40
SQLALCHEMY_POOL_TIMEOUT=30
SQLALCHEMY_POOL_RECYCLE=280
SQLALCHEMY_POOL_PRE_PING=True

# Redis configuration
REDIS_URL=redis://localhost:6379/0
CACHE_TYPE=RedisCache
CACHE_DEFAULT_TIMEOUT=300

# Gunicorn configuration
GUNICORN_WORKERS=9  # (CPU cores * 2) + 1
GUNICORN_WORKER_CLASS=gevent
GUNICORN_THREADS=4
GUNICORN_WORKER_CONNECTIONS=1000
GUNICORN_TIMEOUT=120
GUNICORN_BIND=0.0.0.0:8000

# Application settings
DEBUG=False
SECRET_KEY=your_secret_key_here
```

### 2. Применение миграций БД

Добавьте колонки версионирования в таблицы:

```bash
# Применить миграцию
flask db upgrade

# Или использовать alembic напрямую
alembic upgrade head
```

### 3. Настройка Gunicorn

Файл `gunicorn_config.py` уже настроен. При необходимости можно изменить параметры:

```python
# Количество worker процессов
workers = 9  # Рекомендуется: (CPU cores * 2) + 1

# Класс worker'а
worker_class = "gevent"  # Для асинхронной обработки

# Количество потоков на worker
threads = 4

# Максимальное количество соединений на worker
worker_connections = 1000
```

---

## Запуск приложения

### Development режим

```bash
python run.py
```

### Production режим

**Windows:**
```cmd
start_production.bat
```

**Linux/Mac:**
```bash
chmod +x start_production.sh
./start_production.sh
```

**Или напрямую через Gunicorn:**
```bash
gunicorn --config gunicorn_config.py run:app
```

### Запуск с systemd (Linux)

Создайте файл `/etc/systemd/system/fproject.service`:

```ini
[Unit]
Description=FProject Flask Application
After=network.target postgresql.service redis.service

[Service]
Type=notify
User=your_user
Group=your_group
WorkingDirectory=/path/to/fproject
Environment="PATH=/path/to/fproject/venv/bin"
ExecStart=/path/to/fproject/venv/bin/gunicorn --config gunicorn_config.py run:app
Restart=always

[Install]
WantedBy=multi-user.target
```

Запуск:
```bash
sudo systemctl daemon-reload
sudo systemctl start fproject
sudo systemctl enable fproject
sudo systemctl status fproject
```

---

## Использование возможностей

### 1. Оптимистическая блокировка в моделях

Модели `Station` и `Machine` уже поддерживают версионирование. Для добавления к другим моделям:

```python
from app.common.models.versioned_model import VersionedModelMixin

class MyModel(db.Model, VersionedModelMixin):
    __tablename__ = 'my_table'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    # version колонка добавляется автоматически
```

### 2. Обработка concurrent updates в маршрутах

```python
from app.common.middleware import handle_stale_data, with_db_retry

@app.route('/station/<int:id>/update', methods=['POST'])
@handle_stale_data
def update_station(id):
    station = Station.query.get_or_404(id)
    station.name = request.form['name']
    db.session.commit()
    flash('Станция обновлена успешно', 'success')
    return redirect(url_for('station_details', id=id))
```

### 3. Использование кэширования

```python
from app.common.services.cache_decorator import cached_route, cached_query, invalidate_cache

# Кэширование маршрута
@app.route('/stations')
@cached_route(timeout=600, key_prefix='stations_list')
def list_stations():
    stations = Station.query.all()
    return render_template('stations.html', stations=stations)

# Кэширование запроса
@cached_query(timeout=300, key_prefix='station')
def get_station_by_id(station_id):
    return Station.query.get(station_id)

# Инвалидация кэша после обновления
@app.route('/station/<int:id>/update', methods=['POST'])
def update_station(id):
    station = Station.query.get_or_404(id)
    station.name = request.form['name']
    db.session.commit()
    
    # Инвалидация кэша
    invalidate_cache('station', station_id=id)
    invalidate_cache('stations_list')
    
    return redirect(url_for('station_details', id=id))
```

### 4. Retry механизм для критичных операций

```python
from app.common.middleware import with_db_retry

@with_db_retry(max_attempts=3, backoff_factor=0.5)
def critical_operation(data):
    # Операция, которая может столкнуться с temporary locks
    result = process_data(data)
    db.session.commit()
    return result
```

---

## Мониторинг и отладка

### 1. Логирование

Gunicorn автоматически логирует запросы. Для просмотра логов:

```bash
# Логи Gunicorn выводятся в stdout/stderr
# При использовании systemd:
sudo journalctl -u fproject -f
```

### 2. Мониторинг Redis

```bash
# Подключение к Redis CLI
redis-cli

# Просмотр статистики
INFO

# Просмотр ключей кэша
KEYS *

# Очистка всего кэша (осторожно!)
FLUSHDB
```

### 3. Мониторинг PostgreSQL

```sql
-- Активные соединения
SELECT count(*) FROM pg_stat_activity;

-- Детали соединений
SELECT pid, usename, application_name, client_addr, state, query
FROM pg_stat_activity;

-- Блокировки
SELECT * FROM pg_locks;
```

### 4. Мониторинг производительности приложения

```bash
# Установка tools для мониторинга
pip install flask-monitor

# В коде приложения
from flask_monitor import Monitor
Monitor(app)
```

---

## Лучшие практики

### 1. Масштабирование

- **Вертикальное**: Увеличьте `GUNICORN_WORKERS` пропорционально CPU cores
- **Горизонтальное**: Запустите несколько инстансов за load balancer (nginx, HAProxy)

### 2. Оптимизация кэша

- Кэшируйте только часто используемые данные
- Устанавливайте разумные timeout'ы (300-600 секунд для списков, 60-120 для деталей)
- Инвалидируйте кэш сразу после изменения данных

### 3. Работа с БД

- Используйте `with_db_retry` для критичных операций
- Минимизируйте время транзакций
- Избегайте N+1 queries (используйте `joinedload`, `subqueryload`)

### 4. Обработка ошибок

- Всегда обрабатывайте `StaleDataError` в критичных маршрутах
- Показывайте информативные сообщения пользователям
- Логируйте все ошибки concurrent updates для анализа

### 5. Тестирование

- Проводите нагрузочное тестирование с помощью Apache JMeter, Locust или wrk
- Симулируйте concurrent updates для проверки версионирования
- Мониторьте использование памяти и CPU под нагрузкой

### 6. Безопасность

- Используйте Redis authentication в production
- Настройте firewall для ограничения доступа к Redis и PostgreSQL
- Регулярно обновляйте зависимости

### 7. Backup и восстановление

- Настройте автоматические backup'ы PostgreSQL
- Сохраняйте Redis persistence (RDB + AOF) для критичных данных
- Тестируйте процедуры восстановления

---

## Примеры конфигурации для различных нагрузок

### Малая нагрузка (до 50 одновременных пользователей)

```env
GUNICORN_WORKERS=5
GUNICORN_WORKER_CONNECTIONS=500
SQLALCHEMY_POOL_SIZE=10
SQLALCHEMY_MAX_OVERFLOW=20
```

### Средняя нагрузка (50-200 одновременных пользователей)

```env
GUNICORN_WORKERS=9
GUNICORN_WORKER_CONNECTIONS=1000
SQLALCHEMY_POOL_SIZE=20
SQLALCHEMY_MAX_OVERFLOW=40
```

При необходимости использовать несколько серверов за load balancer.

---

## Troubleshooting

### Проблема: "Too many connections" в PostgreSQL

**Решение:**
```sql
ALTER SYSTEM SET max_connections = 300;
-- Перезапустить PostgreSQL
```

Или уменьшите `SQLALCHEMY_POOL_SIZE` и `SQLALCHEMY_MAX_OVERFLOW`.

### Проблема: Redis connection refused

**Решение:**
1. Убедитесь, что Redis запущен: `redis-cli ping`
2. Проверьте `REDIS_URL` в `.env`
3. Если Redis недоступен, приложение автоматически переключится на SimpleCache

### Проблема: Worker timeout

**Решение:**
Увеличьте `GUNICORN_TIMEOUT` в `.env`:
```env
GUNICORN_TIMEOUT=180
```

### Проблема: Частые StaleDataError

**Решение:**
- Используйте `with_db_retry` для автоматических повторов
- Оптимизируйте код для более быстрых транзакций
- Рассмотрите использование пессимистической блокировки для критичных участков

---

## Дополнительные ресурсы

- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Flask-Caching Documentation](https://flask-caching.readthedocs.io/)
- [SQLAlchemy Optimistic Locking](https://docs.sqlalchemy.org/en/14/orm/versioning.html)
- [Redis Documentation](https://redis.io/documentation)
- [PostgreSQL Connection Pooling](https://www.postgresql.org/docs/current/runtime-config-connection.html)

---

## Контакты и поддержка

При возникновении проблем или вопросов обращайтесь к команде разработки.

