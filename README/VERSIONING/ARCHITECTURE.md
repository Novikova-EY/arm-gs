# 🏗️ Архитектура системы версионирования

## Обзор

Система версионирования построена по модульному принципу с четкой ответственностью каждого компонента.

---

## 📐 Общая архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                         Пользователь                             │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Веб-интерфейс (Flask)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Управление  │  │  Сравнение   │  │   Снимки    │          │
│  │   версиями   │  │   версий     │  │   версий    │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Middleware Layer                             │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │   database_version_middleware.py                         │  │
│  │   • before_request: Загрузка активной версии в g         │  │
│  │   • Установка g.current_db_version                       │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Services Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  database_   │  │  version_    │  │  scheduled_  │          │
│  │  version_    │  │  comparison_ │  │  backup_     │          │
│  │  services.py │  │  service.py  │  │  service.py  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │   database_version_filter.py                             │  │
│  │   • apply_version_filter(query, Model)                   │  │
│  │   • set_db_version_on_create(instance)                   │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        Models Layer                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  database_   │  │  database_   │  │  Модели с    │          │
│  │  version_    │  │  version_    │  │  поддержкой  │          │
│  │  model.py    │  │  mixin.py    │  │  версий      │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    База данных PostgreSQL                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  refdata.database_versions                            │  │
│  │  • id (PK)                                              │  │
│  │  • version_number (UNIQUE)                              │  │
│  │  • name (UNIQUE)                                        │  │
│  │  • is_active                                            │  │
│  │  • snapshot_path                                        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Таблицы данных (stations, machines, и т.д.)            │  │
│  │  • database_version_id (FK) → database_versions.id      │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔄 Поток данных

### 1. Запрос пользователя

```
Пользователь → HTTP Request → Flask App
```

### 2. Установка версии (Middleware)

```python
@app.before_request
def load_current_version():
    """Загружает текущую активную версию БД перед каждым запросом."""
    
    # 1. Проверяем сессию пользователя
    if 'current_db_version' in session:
        g.current_db_version = session['current_db_version']
        return
    
    # 2. Если нет в сессии, берем активную версию из БД
    active_version = DatabaseVersion.query.filter_by(is_active=True).first()
    if active_version:
        g.current_db_version = active_version.id
    else:
        g.current_db_version = None
```

### 3. Фильтрация данных (Service)

```python
def station_query(filters...):
    # 1. Базовый запрос
    query = Station.query.filter(...)
    
    # 2. Применение фильтра версий
    query = apply_version_filter(query, Station)
    
    # 3. Остальные фильтры
    query = query.filter(...)
    
    return query


def apply_version_filter(query, model_class):
    """Добавляет фильтр по текущей версии БД к запросу."""
    
    # Получаем ID текущей версии из контекста
    current_version_id = getattr(g, 'current_db_version', None)
    
    if current_version_id is not None:
        # Фильтруем:
        # - Записи текущей версии ИЛИ
        # - Записи без версии (доступны во всех версиях)
        query = query.filter(
            (model_class.database_version_id == current_version_id) |
            (model_class.database_version_id.is_(None))
        )
    
    return query
```

### 4. Возврат данных

```
Filtered Data → Service → View → Template → HTTP Response → Пользователь
```

---

## 🗂️ Структура модулей

### Модели (Models)

#### `database_version_model.py`
```python
class DatabaseVersion(db.Model):
    """Модель версии базы данных."""
    
    __tablename__ = 'database_versions'
    __table_args__ = {"schema": SCHEMA_GENERATION}
    
    id = db.Column(db.Integer, primary_key=True)
    version_number = db.Column(db.Integer, unique=True, nullable=False)
    name = db.Column(db.String(255), unique=True, nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=False)
    
    # Снимок версии
    snapshot_path = db.Column(db.String(500))
    snapshot_size = db.Column(db.BigInteger)
    
    # Временные метки
    created_at = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(db.DateTime(timezone=True))
```

#### `database_version_mixin.py`
```python
class DatabaseVersionMixin:
    """Миксин для добавления поля database_version_id к моделям."""
    
    database_version_id = Column(
        Integer,
        ForeignKey(f"{SCHEMA_GENERATION}.database_versions.id", 
                   ondelete="SET NULL"),
        nullable=True,
        index=True
    )
```

**Использование:**
```python
class Station(db.Model, DatabaseVersionMixin):
    __tablename__ = 'stations'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    # database_version_id добавляется автоматически из миксина
```

### Middleware

#### `database_version_middleware.py`

**Функции:**
- `init_database_version_middleware(app)` - Инициализация middleware
- `load_current_version()` - Загрузка версии перед запросом
- `get_current_version_id()` - Получение ID текущей версии
- `set_session_version(version_id)` - Установка версии для сессии

**Порядок работы:**
```
1. Запрос → Flask
2. before_request → load_current_version()
3. Проверка session['current_db_version']
4. Если нет → Запрос активной версии из БД
5. Установка g.current_db_version
6. Обработка запроса с установленной версией
```

### Services

#### `database_version_services.py`

**CRUD операции:**
- `version_query()` - Базовый запрос с фильтрацией
- `get_version_list()` - Список версий с пагинацией
- `add_version_service()` - Создание версии
- `update_version_service()` - Обновление версии
- `delete_version_service()` - Удаление версии
- `export_version_service()` - Экспорт в Excel

**Операции со снимками:**
- `save_version_snapshot()` - Создание снимка (pg_dump)
- `load_version_snapshot()` - Загрузка снимка (pg_restore)

**Управление версиями:**
- `set_active_version()` - Активация версии
- `get_current_version()` - Получение текущей версии

#### `database_version_filter.py`

**Функции фильтрации:**
- `apply_version_filter(query, model_class)` - Применить фильтр к query
- `set_db_version_on_create(instance)` - Установить версию при создании
- `filter_by_db_version()` - Внутренняя функция фильтрации
- `get_current_db_version_id()` - Получить ID версии

#### `version_comparison_service.py`

**Сравнение версий:**
- `compare_versions(v1_id, v2_id)` - Сравнить две версии
- `export_comparison_to_excel()` - Экспорт сравнения в Excel
- `_get_table_counts()` - Подсчет записей по таблицам
- `_calculate_differences()` - Расчет различий

#### `scheduled_backup_service.py`

**Автоматические бэкапы:**
- `ScheduledBackupService` - Класс сервиса
- `init_app(app)` - Инициализация с Flask
- `_run_backup()` - Создание бэкапа
- `_cleanup_old_backups()` - Очистка старых бэкапов
- `_find_pg_binary()` - Поиск pg_dump

### Routes

#### `database_versions_routes.py`

**Маршруты:**
```python
# Управление версиями
GET/POST  /database_versions              # Список версий
GET/POST  /add_database_version           # Добавить версию
GET       /export_database_versions       # Экспорт в Excel

# Операции с версиями
POST      /set_active_version/<id>        # Активировать версию
POST      /save_version_snapshot/<id>     # Создать снимок
POST      /load_version_snapshot/<id>     # Загрузить снимок

# Сравнение версий
GET/POST  /compare_versions               # Сравнить версии
GET       /export_comparison/<id1>/<id2>  # Экспорт сравнения
```

---

## 🔐 Безопасность и транзакции

### Уровни безопасности

#### 1. Авторизация
```python
@station_bp.route("/database_versions")
@login_required  # ← Требуется авторизация
def database_versions():
    ...
```

#### 2. Валидация данных
```python
# Проверка уникальности
if DatabaseVersion.query.filter_by(name=name).first():
    raise ValueError(f"Версия с названием «{name}» уже существует.")

# Проверка активной версии
if obj.is_active:
    raise ValueError("Невозможно удалить активную версию")
```

#### 3. Транзакции
```python
@no_autoflush
def update_version_service(data, user):
    with db.session.no_autoflush:
        # Все изменения в одной транзакции
        for record in data:
            obj = db.session.get(DatabaseVersion, version_id)
            obj.name = name
            # ...
        
        db.session.flush()
    
    # Коммит с retry
    _commit_with_retry()
```

#### 4. Автоматический бэкап
```python
def load_version_snapshot(version_id, user):
    """Перед загрузкой снимка создается автоматический бэкап."""
    
    # 1. Создать автобэкап текущего состояния
    auto_backup_file = create_auto_backup()
    
    # 2. Загрузить снимок
    pg_restore(version.snapshot_path)
    
    # 3. Если ошибка → можно восстановить из автобэкапа
```

### Обработка ошибок

```python
try:
    # Операция
    result = operation()
    db.session.commit()
    
except IntegrityError as e:
    # Ошибка уникальности/целостности
    db.session.rollback()
    log_to_db(user, "Ошибка целостности", str(e))
    raise ValueError("Нарушены ограничения БД")

except Exception as e:
    # Общая ошибка
    db.session.rollback()
    log_to_db(user, "Ошибка операции", str(e))
    raise ValueError(f"Ошибка: {e}")
```

---

## 📊 База данных

### Схема таблиц

#### Таблица `database_versions`

```sql
CREATE TABLE refdata.database_versions (
    id                  SERIAL PRIMARY KEY,
    version_number      INTEGER NOT NULL UNIQUE,
    name                VARCHAR(255) NOT NULL UNIQUE,
    description         TEXT,
    is_active           BOOLEAN DEFAULT FALSE NOT NULL,
    snapshot_path       VARCHAR(500),
    snapshot_size       BIGINT,
    created_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    updated_at          TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- Индексы
CREATE INDEX idx_database_versions_version_number 
    ON refdata.database_versions(version_number);
CREATE INDEX idx_database_versions_is_active 
    ON refdata.database_versions(is_active);
```

#### Поле в таблицах данных

```sql
-- Пример: таблица stations
ALTER TABLE generation.stations
ADD COLUMN database_version_id INTEGER;

-- Foreign key
ALTER TABLE generation.stations
ADD CONSTRAINT fk_stations_database_version
FOREIGN KEY (database_version_id)
REFERENCES refdata.database_versions(id)
ON DELETE SET NULL;

-- Индекс
CREATE INDEX idx_stations_database_version_id
ON generation.stations(database_version_id);
```

### SQL запросы системы

#### Получение активной версии
```sql
SELECT * FROM refdata.database_versions
WHERE is_active = TRUE
LIMIT 1;
```

#### Фильтрация данных по версии
```sql
-- Пример для stations
SELECT * FROM generation.stations
WHERE (
    database_version_id = :current_version_id OR
    database_version_id IS NULL
);
```

#### Статистика по версиям
```sql
SELECT 
    dv.version_number,
    dv.name,
    COUNT(s.id) as station_count
FROM refdata.database_versions dv
LEFT JOIN generation.stations s ON s.database_version_id = dv.id
GROUP BY dv.id, dv.version_number, dv.name
ORDER BY dv.version_number;
```

---

## ⚙️ Конфигурация

### Переменные окружения (.env)

```bash
# === База данных ===
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_NAME=arm_gs
DB_PASS=your_password

# === Автоматические бэкапы ===
ENABLE_SCHEDULED_BACKUPS=True
AUTO_BACKUP_DIR=backups/auto
KEEP_AUTO_BACKUPS=7
BACKUP_SCHEDULE_HOUR=2
BACKUP_SCHEDULE_MINUTE=0
```

### Настройки в config.py

```python
# Схемы БД
SCHEMA_GENERATION = "generation"
SCHEMA_REFDATA = "refdata"

# Бэкапы
ENABLE_SCHEDULED_BACKUPS = os.getenv('ENABLE_SCHEDULED_BACKUPS', 'False').lower() == 'true'
AUTO_BACKUP_DIR = os.getenv('AUTO_BACKUP_DIR', 'backups/auto')
KEEP_AUTO_BACKUPS = int(os.getenv('KEEP_AUTO_BACKUPS', 7))

# Расписание бэкапов
BACKUP_SCHEDULE = {
    'hour': int(os.getenv('BACKUP_SCHEDULE_HOUR', 2)),
    'minute': int(os.getenv('BACKUP_SCHEDULE_MINUTE', 0))
}
```

---

## 🔄 Жизненный цикл версии

```
┌─────────────────────────────────────────────────────────────┐
│                  Создание версии                            │
│  • Номер версии (уникальный)                               │
│  • Название (уникальное)                                   │
│  • Описание                                                │
│  • Статус: is_active = False                               │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  Активация версии                           │
│  • set_active_version(id)                                  │
│  • Деактивация других версий                               │
│  • Установка is_active = True                              │
│  • Обновление g.current_db_version                         │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Работа с данными версии                        │
│  • Фильтрация данных по database_version_id                │
│  • Создание новых записей с версией                        │
│  • Редактирование данных версии                            │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  Создание снимка                            │
│  • save_version_snapshot(id)                               │
│  • Выполнение pg_dump                                      │
│  • Сохранение пути и размера                               │
│  • snapshot_path = "backups/versions/version_X.dump"       │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Сравнение с другими версиями                   │
│  • compare_versions(id1, id2)                              │
│  • Подсчет записей по таблицам                             │
│  • Визуализация различий                                   │
│  • Экспорт в Excel                                         │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                Восстановление снимка                        │
│  • load_version_snapshot(id)                               │
│  • Автоматический бэкап текущего состояния                 │
│  • Выполнение pg_restore                                   │
│  • Автоактивация восстановленной версии                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  Удаление версии                            │
│  • delete_version_service([id])                            │
│  • Проверка: not is_active                                 │
│  • Удаление файла снимка                                   │
│  • Удаление записи БД                                      │
│  • database_version_id → NULL для данных                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Производительность

### Оптимизации

#### 1. Индексы
```sql
-- Индекс на is_active для быстрого поиска активной версии
CREATE INDEX idx_database_versions_is_active 
    ON refdata.database_versions(is_active);

-- Индекс на database_version_id в каждой таблице
CREATE INDEX idx_stations_database_version_id
    ON generation.stations(database_version_id);
```

#### 2. Кеширование
```python
# Версия устанавливается один раз в начале запроса
@app.before_request
def load_current_version():
    # Один запрос к БД
    active_version = DatabaseVersion.query.filter_by(is_active=True).first()
    
    # Кешируется в g для всего запроса
    g.current_db_version = active_version.id
```

#### 3. Эффективные запросы
```python
# Фильтрация на уровне БД, а не в Python
query = query.filter(
    (Model.database_version_id == current_version_id) |
    (Model.database_version_id.is_(None))
)
```

### Метрики производительности

| Операция | Время | Нагрузка на БД |
|----------|-------|----------------|
| Загрузка активной версии | <10ms | 1 SELECT |
| Фильтрация данных | +0ms | Индексированный WHERE |
| Создание снимка | 1-5 мин | pg_dump (не блокирует) |
| Загрузка снимка | 2-10 мин | pg_restore (блокирует) |
| Сравнение версий | 5-30 сек | COUNT по таблицам |

---

## 📝 Примеры использования

### Пример 1: Создание версии в коде

```python
from app.common.services.database_version_services import add_version_service

# Создать версию
data = [{
    "version_number": 3,
    "name": "Версия 3.0",
    "description": "Тестовая версия"
}]

new_version_id = add_version_service(data, user="admin")
```

### Пример 2: Фильтрация в service

```python
from app.common.services.database_version_filter import apply_version_filter

def station_query(filters...):
    # Базовый запрос
    query = Station.query.filter(Station.id > 0)
    
    # Применить фильтр версий
    query = apply_version_filter(query, Station)
    
    # Дополнительные фильтры
    if name_filter:
        query = query.filter(Station.name.ilike(f"%{name_filter}%"))
    
    return query
```

### Пример 3: Использование миксина в модели

```python
from app.common.models.database_version_mixin import DatabaseVersionMixin
from config import SCHEMA_GENERATION

class Machine(db.Model, DatabaseVersionMixin):
    __tablename__ = 'machines'
    __table_args__ = {"schema": SCHEMA_GENERATION}
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255))
    
    # database_version_id добавляется автоматически из миксина
```

### Пример 4: Установка версии при создании

```python
from app.common.services.database_version_filter import set_db_version_on_create

def add_station_service(data, user):
    # Создать станцию
    station = Station(name=data['name'])
    
    # Автоматически установить текущую версию
    set_db_version_on_create(station)
    
    db.session.add(station)
    db.session.commit()
    
    return station
```

---

## 🔍 Мониторинг и логирование

### Логирование

Все операции с версиями логируются:

```python
from app.logs.services.logging_service import log_to_db

# Создание версии
log_to_db(
    user, 
    "Создана версия БД", 
    f"Номер: {version_number}, Название: {name}",
    entity_type="database_version", 
    entity_id=version_id
)

# Активация версии
log_to_db(
    user,
    f"Установлена активная версия БД: {version.name}",
    f"ID: {version_id}",
    entity_type="database_version",
    entity_id=version_id
)
```

### Просмотр логов

```bash
# Все операции с версиями
grep "database_version" logs/app.log

# Автоматические бэкапы
grep "Автоматический бэкап" logs/app.log

# Создание снимков
grep "снимок" logs/app.log
```

---

## 🧪 Тестирование

### Unit-тесты

```python
# Тест фильтрации
def test_version_filter():
    # Создать тестовую версию
    version = DatabaseVersion(version_number=99, name="Test")
    db.session.add(version)
    db.session.commit()
    
    # Установить как активную
    g.current_db_version = version.id
    
    # Создать станцию с версией
    station = Station(name="Test Station", database_version_id=version.id)
    db.session.add(station)
    db.session.commit()
    
    # Проверить фильтрацию
    query = Station.query
    query = apply_version_filter(query, Station)
    
    assert query.count() == 1
    assert query.first().name == "Test Station"
```

### Интеграционные тесты

```python
# Тест создания и загрузки снимка
def test_snapshot_lifecycle():
    # 1. Создать версию
    version = create_version("Test Version")
    
    # 2. Создать снимок
    save_version_snapshot(version.id, "test_user")
    
    # 3. Проверить файл
    assert os.path.exists(version.snapshot_path)
    
    # 4. Загрузить снимок
    load_version_snapshot(version.id, "test_user")
    
    # 5. Проверить активацию
    assert version.is_active == True
```

---

## 📚 Дополнительные материалы

### Связанные технологии

- **Flask** - Web framework
- **SQLAlchemy** - ORM
- **PostgreSQL** - База данных
- **pg_dump/pg_restore** - Утилиты бэкапов
- **APScheduler** - Планировщик задач
- **XlsxWriter** - Экспорт в Excel

### Полезные ссылки

- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/)

---

**Версия документа:** 1.0  
**Дата:** 21 октября 2025

