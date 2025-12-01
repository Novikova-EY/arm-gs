## Общее описание

Этот документ описывает полный сценарий сборки deb-пакета приложения `generation-app` и его установку на сервер под Astra Linux 1.8.4 (Debian-based). Приведённые команды ожидают, что вы выполняете их от имени пользователя с правами `sudo`.

### ⚠️ Важно: PostgreSQL и Redis

**PostgreSQL и Redis указаны в зависимостях deb-пакета**, поэтому они **установятся автоматически** при выполнении `sudo apt -f install` после установки пакета (если ещё не установлены).

**Однако** настройку этих сервисов (создание базы данных, пользователя, паролей) нужно выполнить **вручную** перед запуском приложения. См. разделы 3 и 4.

**Рекомендуемый порядок:**
1. Установить PostgreSQL и Redis вручную (раздел 2, Вариант А).
2. Настроить их (разделы 3 и 4).
3. Установить deb-пакет приложения (раздел 7).

---

## 1. Требования к серверу

- Astra Linux 1.8.4 (SE или CE) с доступом в интернет.
- Доступ к учётной записи с правами `sudo`.
- Открытые порты:
  - 8000/TCP для самого приложения (при необходимости проксируйте через Nginx).
  - 5432/TCP, если PostgreSQL будет использоваться удалённо.
  - 6379/TCP, если Redis нужен с других хостов (по умолчанию слушает только localhost).

---

## 2. Базовые пакеты

**Важно:** PostgreSQL и Redis можно установить двумя способами:

### Вариант А: Установить вручную (рекомендуется)

Установите базовые пакеты и зависимости приложения заранее:

```bash
sudo apt update
sudo apt install -y \
  python3 python3-venv python3-pip python3-dev \
  build-essential libpq-dev libffi-dev \
  git rsync curl \
  postgresql postgresql-contrib \
  redis-server \
  dpkg-dev fakeroot
```

### Вариант Б: Установить автоматически через зависимости пакета

Если вы устанавливаете только deb-пакет приложения, PostgreSQL и Redis **установятся автоматически** при выполнении `sudo apt -f install` (после `dpkg -i`), так как они указаны в зависимостях пакета.

**Рекомендация:** Используйте Вариант А, чтобы иметь возможность настроить PostgreSQL и Redis **до** установки приложения.

Дополнительно рекомендуется установить `nginx` или другой reverse-proxy, если предполагается публикация во внешнюю сеть.

---

## 3. Настройка PostgreSQL

**Примечание:** Этот шаг нужно выполнить **до** установки deb-пакета приложения, независимо от того, был ли PostgreSQL установлен вручную или через зависимости.

1. Убедитесь, что сервис запущен:
   ```bash
   sudo systemctl enable --now postgresql
   ```
2. Создайте пользователя и базу (пример):
   ```bash
   sudo -u postgres psql <<'SQL'
   CREATE ROLE generation WITH LOGIN PASSWORD 'R7fP9wQk';
   CREATE DATABASE gs_gen OWNER generation ENCODING 'UTF8';
   GRANT ALL PRIVILEGES ON DATABASE arm_generation TO generation;
   SQL
   ```
3. При необходимости скорректируйте `pg_hba.conf`, чтобы разрешить подключение по сети (обычно `/etc/postgresql/*/main/pg_hba.conf`). После изменений перезапустите PostgreSQL.

---

## 4. Настройка Redis

```bash
sudo systemctl enable --now redis-server
sudo systemctl status redis-server
```

По умолчанию Redis слушает `127.0.0.1:6379`, что подходит для локального использования приложением.

---

## 5. Сборка deb-пакета

Выполняется в окружении, где лежит исходный код (можно в отдельном CI или на рабочем месте разработчика под Linux).

1. Установите зависимости (см. раздел 2).
2. Запустите скрипт сборки:
   ```bash
   cd /path/to/fproject
   python3 scripts/build_deb.py --version 1.0.0
   ```
   - Если `--version` не указан, берётся `git describe` или текущая дата.
   - Скрипт создаст staging-директорию в `packaging/build` и финальный пакет `packaging/generation-app_<version>_amd64.deb`.

---

## 6. Передача пакета на сервер

Используйте любой удобный способ (scp, rsync, artifact registry):

```bash
scp C:\fproject\packaging\generation-app_1.0.0_amd64.deb novikova-eyu@10.31.205.27:/tmp/
```
---

## 7. Установка пакета

На целевом сервере:

```bash
cd /tmp
sudo dpkg -i generation-app_1.0.0_amd64.deb || sudo apt -f install
```

**Что происходит при установке:**

1. **Автоматическая установка зависимостей:** Если PostgreSQL и Redis не были установлены ранее, команда `apt -f install` установит их автоматически (так как они указаны в зависимостях пакета).

2. **Создание системных объектов:**
   - Созданы системный пользователь `generation-app` и каталог `/opt/generation-app`.
   - Развёрнут virtualenv и установлены Python-зависимости из `requirements-linux.txt`.
   - Скопирован unit-файл `generation-app.service`.

**Важно:** Если PostgreSQL и Redis были установлены автоматически на этом этапе, обязательно вернитесь к разделам 3 и 4, чтобы настроить базу данных и пользователя **перед** запуском приложения.

---

## 8. Конфигурация окружения

После установки появится файл `/etc/generation-app/app.env` (создаётся из шаблона, если его не было). Отредактируйте его под своё окружение:

```bash
sudo nano /etc/generation-app/app.env
```

Минимальный набор параметров:

```ini
SECRET_KEY=<random>
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=gs_gen
DB_USER=generation
DB_PASS=ваш_пароль
SQLALCHEMY_DATABASE_URI=postgresql+psycopg2://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}
REDIS_URL=redis://127.0.0.1:6379/0
```

**Важно:** Пароль базы данных (`DB_PASS` и `DB_PASSWORD`) можно изменить в любое время после установки пакета. Просто отредактируйте файл `/etc/generation-app/app.env` и перезапустите сервис. Изменения в конфигурации не требуют пересборки deb-пакета.

После правок обязательно перезапустите сервис:

```bash
sudo systemctl restart generation-app
```

---

## 9. Миграции БД и проверка

1. Выполните миграции (если используются Alembic/Flask-Migrate):
   ```bash
   sudo -u generation-app -s
   
   cd /opt/generation-app/app
   
   DB_USER=generation \
   DB_PASS='R7fP9wQk' \
   DB_NAME='gs_gen' \
   DB_HOST=localhost \
   DB_PORT=5432 \
   FLASK_APP=run.py \
     /opt/generation-app/venv/bin/flask db upgrade
   ```
   Убедитесь, что переменные окружения из `/etc/generation-app/app.env` доступны (systemd unit подхватывает их автоматически, но для ручной команды можно экспортировать через `set -a; source /etc/generation-app/app.env; ...`).

2. Проверьте сервис:
   ```bash
   sudo systemctl status generation-app
   sudo journalctl -u generation-app -f
   curl -I http://127.0.0.1:8000/health
   ```

---

## 10. Обновление и откат

- Для обновления соберите новый пакет с версией `1.0.1`, скопируйте его на сервер и выполните `sudo dpkg -i generation-app_1.0.1_amd64.deb`.
- Сервис автоматически перезапустится (через `postinst`). При необходимости можно вручную выполнить `sudo systemctl restart generation-app`.
- Возврат к предыдущей версии возможен командой `sudo apt install ./generation-app_1.0.0_amd64.deb`.

---

## 11. Частые проблемы

- **dpkg ругается на зависимости** — выполните `sudo apt -f install`, чтобы подтянуть недостающие пакеты. PostgreSQL и Redis установятся автоматически, но их нужно будет настроить (разделы 3 и 4).
- **pip не собирает psycopg2** — проверьте, что установлены `build-essential` и `libpq-dev`.
- **Приложение не стартует** — смотрите логи `journalctl -u generation-app -b` и убедитесь, что `app.env` содержит корректный DSN и секреты.
- **Ошибка подключения к БД** — убедитесь, что PostgreSQL запущен (`sudo systemctl status postgresql`), база данных создана, и параметры в `/etc/generation-app/app.env` соответствуют реальным.
- **Ошибка подключения к Redis** — проверьте, что Redis запущен (`sudo systemctl status redis-server`) и слушает на `127.0.0.1:6379`.


