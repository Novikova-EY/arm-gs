# Настройка для Windows

## 🪟 Важная информация

Gunicorn **не поддерживает Windows** нативно, так как использует Unix-специфичные модули (fcntl). 

Для Windows мы используем **Waitress** - отличный WSGI-сервер, который:
- ✅ Полностью поддерживает Windows
- ✅ Многопоточный (до 1000+ соединений)
- ✅ Production-ready
- ✅ Простой в настройке

---

## 🚀 Быстрый старт для Windows

### 1. Установка зависимостей

```cmd
# Активация виртуального окружения
venv\Scripts\activate

# Установка зависимостей для Windows
pip install -r requirements-windows.txt
```

### 2. Настройка Redis (опционально)

**Вариант 1: Docker (рекомендуется)**
```cmd
docker run -d -p 6379:6379 --name redis redis:latest
```

**Вариант 2: WSL (Windows Subsystem for Linux)**
```cmd
wsl
sudo service redis-server start
```

**Вариант 3: Redis для Windows**
Скачайте: https://github.com/microsoftarchive/redis/releases

### 3. Настройка переменных окружения

Скопируйте `env.example` в `.env`:
```cmd
copy env.example .env
```

Отредактируйте `.env`, минимальная конфигурация:
```env
DB_USER=your_user
DB_PASS=your_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=your_db

# Waitress configuration
WAITRESS_HOST=0.0.0.0
WAITRESS_PORT=8000
WAITRESS_THREADS=16
WAITRESS_CONNECTION_LIMIT=1000
```

### 4. Применение миграций

```cmd
flask db upgrade
```

### 5. Запуск приложения

**Вариант 1: Скрипт (рекомендуется)**
```cmd
start_production.bat
```

**Вариант 2: Напрямую через Python**
```cmd
python start_waitress.py
```

**Вариант 3: Development режим**
```cmd
python run.py
```

---

## ⚙️ Конфигурация Waitress

### Параметры в `.env`

```env
# Адрес и порт
WAITRESS_HOST=0.0.0.0
WAITRESS_PORT=8000

# Количество потоков (рекомендация: CPU cores * 2)
WAITRESS_THREADS=16

# Максимальное количество соединений
WAITRESS_CONNECTION_LIMIT=1000

# Таймауты
WAITRESS_CHANNEL_TIMEOUT=120
WAITRESS_CLEANUP_INTERVAL=30
```

### Конфигурация для разных нагрузок

**Малая нагрузка (до 50 пользователей)**
```env
WAITRESS_THREADS=8
WAITRESS_CONNECTION_LIMIT=500
SQLALCHEMY_POOL_SIZE=10
SQLALCHEMY_MAX_OVERFLOW=20
```

**Средняя нагрузка (50-200 пользователей)**
```env
WAITRESS_THREADS=16
WAITRESS_CONNECTION_LIMIT=1000
SQLALCHEMY_POOL_SIZE=20
SQLALCHEMY_MAX_OVERFLOW=40
```

**Высокая нагрузка (200+ пользователей)**
```env
WAITRESS_THREADS=32
WAITRESS_CONNECTION_LIMIT=2000
SQLALCHEMY_POOL_SIZE=40
SQLALCHEMY_MAX_OVERFLOW=80
```

---

## 📊 Производительность Waitress

### Характеристики
- 🚀 **До 1000+ одновременных соединений**
- ⚡ **Многопоточная архитектура**
- 💪 **Эффективная обработка HTTP/1.1**
- 🔒 **Безопасность из коробки**

### Сравнение с Gunicorn

| Параметр | Waitress (Windows) | Gunicorn (Linux) |
|----------|-------------------|------------------|
| Многопоточность | ✅ Да | ✅ Да |
| Поддержка Windows | ✅ Да | ❌ Нет |
| Макс. соединений | 1000+ | 1000+ |
| Production-ready | ✅ Да | ✅ Да |

---

## 🔍 Проверка работы

### 1. Проверка запуска
```cmd
# В другом терминале
curl http://localhost:8000
# Или откройте в браузере: http://localhost:8000
```

### 2. Проверка Redis
```cmd
redis-cli ping
# Должно вернуть: PONG
```

### 3. Проверка потоков
Откройте Task Manager (Диспетчер задач) → Подробности → python.exe
Вы должны увидеть несколько потоков для процесса Python.

---

## 🐛 Troubleshooting

### Проблема: "ModuleNotFoundError: No module named 'fcntl'"
**Причина:** Попытка запустить Gunicorn на Windows

**Решение:** Используйте Waitress:
```cmd
python start_waitress.py
```

### Проблема: Redis connection refused
**Решение 1:** Запустите Redis через Docker:
```cmd
docker run -d -p 6379:6379 --name redis redis:latest
```

**Решение 2:** Отключите Redis (приложение переключится на SimpleCache):
```env
# Удалите или закомментируйте в .env
# REDIS_URL=redis://localhost:6379/0
```

### Проблема: "Address already in use"
**Решение:** Измените порт в `.env`:
```env
WAITRESS_PORT=8001
```

### Проблема: Медленная работа
**Решение:** Увеличьте количество потоков:
```env
WAITRESS_THREADS=32
```

---

## 🔐 Запуск как Windows Service

### Использование NSSM (Non-Sucking Service Manager)

1. **Скачайте NSSM:** https://nssm.cc/download

2. **Установите сервис:**
```cmd
nssm install FProjectApp "C:\fproject\venv\Scripts\python.exe" "C:\fproject\start_waitress.py"
```

3. **Настройте рабочую директорию:**
```cmd
nssm set FProjectApp AppDirectory C:\fproject
```

4. **Настройте переменные окружения:**
```cmd
nssm set FProjectApp AppEnvironmentExtra WAITRESS_PORT=8000
```

5. **Запустите сервис:**
```cmd
nssm start FProjectApp
```

### Управление сервисом
```cmd
# Запуск
nssm start FProjectApp

# Остановка
nssm stop FProjectApp

# Перезапуск
nssm restart FProjectApp

# Удаление
nssm remove FProjectApp confirm
```

---

## 📝 Дополнительные настройки

### IIS Integration (опционально)

Если вы используете IIS, можно настроить reverse proxy:

1. Установите URL Rewrite и ARR (Application Request Routing)

2. Добавьте в `web.config`:
```xml
<configuration>
  <system.webServer>
    <rewrite>
      <rules>
        <rule name="ReverseProxyInboundRule" stopProcessing="true">
          <match url="(.*)" />
          <action type="Rewrite" url="http://localhost:8000/{R:1}" />
        </rule>
      </rules>
    </rewrite>
  </system.webServer>
</configuration>
```

### Логирование

Для логирования запросов создайте файл `logging_config.py`:
```python
import logging
from logging.handlers import RotatingFileHandler

handler = RotatingFileHandler('logs/app.log', maxBytes=10000000, backupCount=5)
handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
```

---

## 🎯 Best Practices для Windows

1. **Используйте SSD** для базы данных и кэша
2. **Настройте антивирус** - исключите директорию проекта
3. **Оптимизируйте PostgreSQL** - увеличьте shared_buffers
4. **Используйте Docker** для Redis - проще в управлении
5. **Мониторьте память** - Task Manager → Performance → Memory
6. **Регулярные backup'ы** - настройте автоматические backup'ы БД

---

## 📚 Дополнительные ресурсы

- **Waitress Documentation:** https://docs.pylonsproject.org/projects/waitress/
- **Flask on Windows:** https://flask.palletsprojects.com/
- **PostgreSQL Windows:** https://www.postgresql.org/download/windows/
- **Redis on Windows:** https://github.com/microsoftarchive/redis

---

## ✅ Чеклист запуска

- [ ] Установлены зависимости (`requirements-windows.txt`)
- [ ] PostgreSQL запущен и настроен
- [ ] Redis запущен (опционально, но рекомендуется)
- [ ] Файл `.env` настроен
- [ ] Миграции применены (`flask db upgrade`)
- [ ] Приложение запускается (`python start_waitress.py`)
- [ ] Приложение доступно по http://localhost:8000
- [ ] Можно войти в систему
- [ ] Concurrent updates работают корректно

---

**Готово!** Ваше приложение теперь работает на Windows с полной поддержкой параллельной работы пользователей! 🎉

Для получения дополнительной информации см. `QUICK_START.md` и `CONCURRENCY_SETUP.md`.

