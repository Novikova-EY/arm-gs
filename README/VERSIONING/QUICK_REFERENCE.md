# ⚡ Быстрая шпаргалка по работе с версиями

## 🎯 Основные операции

### Создать новую версию
```
Меню → Управление версиями БД → ➕ Добавить версию
├─ Номер версии: 3
├─ Название: Версия 3.0
└─ Описание: Описание версии
```

### Активировать версию
```
Управление версиями БД → Найти версию → ✅ Установить активной
```

### Создать снимок
```
Управление версиями БД → Найти версию → 💾 Создать снимок
Результат: backups/versions/version_X_YYYYMMDD_HHMMSS.dump
```

### Загрузить снимок
```
⚠️ ВНИМАНИЕ: Заменит все данные!
Управление версиями БД → Найти версию → 📥 Загрузить снимок
```

### Сравнить версии
```
Управление версиями БД → 📊 Сравнить версии
├─ Выбрать Версию 1
├─ Выбрать Версию 2
└─ Нажать "Сравнить"
```

### Скопировать данные в новую версию
```bash
python copy_version_data.py
# Выбрать исходную версию (откуда)
# Выбрать целевую версию (куда)
# Подтвердить копирование
```

---

## 📍 Где что находится

| Что | Где |
|-----|-----|
| Управление версиями | Меню → электростанции → Управление версиями БД |
| Индикатор версии | Верхняя панель каждой страницы |
| Снимки версий | `backups/versions/` |
| Автоматические бэкапы | `backups/auto/` |
| Бэкапы перед восстановлением | `backups/auto_before_restore/` |
| Логи | `logs/app.log` |

---

## ⚙️ Настройка автоматических бэкапов

### Файл .env
```bash
# Включить бэкапы
ENABLE_SCHEDULED_BACKUPS=True

# Директория
AUTO_BACKUP_DIR=backups/auto

# Сколько хранить (дней)
KEEP_AUTO_BACKUPS=7

# Время (час и минута)
BACKUP_SCHEDULE_HOUR=2
BACKUP_SCHEDULE_MINUTE=0
```

### Проверка работы
```bash
# Просмотр файлов
ls -lh backups/auto/

# Просмотр логов
grep "Автоматический бэкап" logs/app.log
```

---

## 🗂️ Структура файлов

```
backups/
├── auto/                              # Автоматические (7 последних)
│   └── auto_backup_20251021_020000.dump
├── versions/                          # Снимки версий
│   └── version_3_20251021_123615.dump
└── auto_before_restore/               # Перед восстановлением
    └── auto_backup_before_restore_*.dump
```

---

## 💻 Полезные SQL-запросы

### Просмотр версий
```sql
-- Все версии
SELECT * FROM refdata.database_versions
ORDER BY version_number;

-- Активная версия
SELECT * FROM refdata.database_versions
WHERE is_active = true;
```

### Статистика по версиям
```sql
-- Количество записей по версиям (stations)
SELECT 
    COALESCE(database_version_id::text, 'NULL') AS version,
    COUNT(*) AS count
FROM gs_gen.stations
GROUP BY database_version_id
ORDER BY database_version_id;
```

### Ручная активация
```sql
-- Деактивировать все
UPDATE refdata.database_versions SET is_active = false;

-- Активировать версию 3
UPDATE refdata.database_versions
SET is_active = true WHERE version_number = 3;
```

---

## 🛠️ Команды администратора

### Создать бэкап вручную
```bash
pg_dump -h localhost -U postgres -F c -b \
  -f backups/manual_$(date +%Y%m%d_%H%M%S).dump \
  arm_gs
```

### Восстановить из бэкапа
```bash
pg_restore -h localhost -U postgres -d arm_gs \
  --clean --if-exists \
  backups/versions/version_3_20251021_123615.dump
```

### Просмотреть содержимое бэкапа
```bash
pg_restore -l backups/versions/version_3_20251021_123615.dump
```

### Размер базы данных
```sql
SELECT pg_size_pretty(pg_database_size('arm_gs'));
```

---

## ❗ Частые проблемы и решения

### pg_dump не найден (Windows)
```cmd
# Добавить в PATH
C:\Program Files\PostgreSQL\15\bin

# Проверить
pg_dump --version
```

### pg_dump не найден (Linux)
```bash
# Установить
sudo apt-get install postgresql-client

# Проверить
which pg_dump
```

### Автобэкапы не создаются
```bash
# 1. Проверить настройки
grep BACKUP .env

# 2. Проверить логи
grep -i backup logs/app.log

# 3. Создать директорию
mkdir -p backups/auto
chmod 755 backups/auto

# 4. Перезапустить приложение
```

### Снимок не загружается
```bash
# 1. Проверить файл
ls -lh backups/versions/version_*.dump

# 2. Проверить содержимое
pg_restore -l backups/versions/version_3_20251021_123615.dump

# 3. Восстановить вручную
pg_restore -h localhost -U postgres -d arm_gs \
  --clean --if-exists -v \
  backups/versions/version_3_20251021_123615.dump
```

### Данные не фильтруются
```python
# Проверить service - должна быть строка:
from app.common.services.database_version_filter import apply_version_filter

query = apply_version_filter(query, Model)
```

### Недостаточно места
```bash
# Проверить место
df -h

# Удалить старые бэкапы (>30 дней)
find backups/auto/ -name "*.dump" -mtime +30 -delete

# Уменьшить в .env
KEEP_AUTO_BACKUPS=3
```

---

## 🔑 Ключевые правила

✅ **МОЖНО:**
- Создавать сколько угодно версий
- Переключаться между версиями
- Создавать снимки перед изменениями
- Сравнивать любые версии
- Экспортировать сравнения

❌ **НЕЛЬЗЯ:**
- Удалить активную версию (сначала активируйте другую)
- Иметь две активные версии одновременно
- Восстановить снимок без автобэкапа

⚠️ **ОСТОРОЖНО:**
- Загрузка снимка заменяет ВСЕ данные
- Перед загрузкой создается автоматический бэкап
- Удаление версии обнуляет связи данных

---

## 📊 Цифры и лимиты

| Параметр | Значение |
|----------|----------|
| Размер снимка | 50-200 МБ (сжатый) |
| Время создания снимка | 1-5 минут |
| Время загрузки снимка | 2-10 минут |
| Таймаут операций | 1 час |
| Хранимых автобэкапов | 7 (настраивается) |
| Место для 7 бэкапов | ~500-1400 МБ |

---

## 🎓 Быстрые сценарии

### Сценарий: Создать годовую версию
```
1. ➕ Создать версию: "Данные 2026"
2. ✅ Активировать
3. ✏️ Заполнить данные
4. 💾 Создать снимок
```

### Сценарий: Тестировать изменения
```
1. 💾 Создать снимок текущей версии
2. ➕ Создать тестовую версию (v99)
3. ✅ Активировать тестовую
4. 🧪 Провести тесты
5. 🔄 Откат: активировать старую + загрузить снимок
```

### Сценарий: Восстановить после ошибки
```
1. 🔍 Найти последний снимок
2. 📥 Загрузить снимок
3. ✅ Проверить данные
4. 💡 Автобэкап старого состояния в auto_before_restore/
```

---

## 📱 Контакты и помощь

- 📖 Полное руководство: `README/VERSIONING/USER_GUIDE.md`
- ⚙️ Технические детали: `README/VERSIONING/REFDATA_SERVICES_VERSIONING.md`
- 🤖 Автобэкапы: `README/VERSIONING/AUTOMATIC_BACKUPS.md`
- 🔧 Обновление моделей: `README/VERSIONING/UPDATE_REMAINING_MODELS.md`

---

**Совет дня:** Всегда создавайте снимок перед массовыми изменениями! 💡

