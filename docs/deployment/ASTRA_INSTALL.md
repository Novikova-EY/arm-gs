## Общее описание

Этот документ описывает полный сценарий сборки deb-пакета приложения `generation-app` и его установку на сервер под Astra Linux 1.8.4 (Debian-based). Приведенные команды ожидают, что вы выполняете их от имени пользователя с правами `sudo`.

### ⚠️ Важно: PostgreSQL и Redis

**PostgreSQL и Redis указаны в зависимостях deb-пакета**, поэтому они **установятся автоматически** при выполнении `sudo apt -f install` после установки пакета (если еще не установлены).

**Однако** настройку этих сервисов (создание базы данных, пользователя, паролей) нужно выполнить **вручную** перед запуском приложения. См. разделы 3 и 4.

**Рекомендуемый порядок:**
1. Установить PostgreSQL и Redis вручную (раздел 2, Вариант А).
2. Настроить их (разделы 3 и 4).
3. Установить deb-пакет приложения (раздел 7).

---

## 1. Требования к серверу

- Astra Linux 1.8.4 (SE или CE) с доступом в интернет.
- Доступ к учетной записи с правами `sudo`.
- Открытые порты:
  - 8000/TCP для самого приложения (при необходимости проксируйте через Nginx).
  - 5432/TCP, если PostgreSQL будет использоваться удаленно.
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
   GRANT ALL PRIVILEGES ON DATABASE gs_gen TO generation;
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

## 2. Сборка `.deb`
1. Собираем Docker-образ

```bash
cd C:\arm_gs
docker build -t arm-gs-deb .
```
Точка в конце — это «контекст сборки» = текущий каталог (C:\arm_gs).

2. Запускаем сборку .deb из Docker

```bash
docker run --rm -v "C:\arm_gs:/app" arm-gs-deb --version 1.0.181
```

-v "C:\fproject:/app" — монтируем твой проект внутрь контейнера в /app.
Соответственно, внутри контейнера путь к скрипту scripts/build_deb.py совпадает с тем, что ты указала в ENTRYPOINT.
arm-gs-deb — имя образа, который ты собрала.
--version 1.0.181 — это аргументы, которые передаются в build_deb.py (добавляются к ENTRYPOINT).

## 6. Передача пакета на сервер

```bash
scp C:\arm_gs\packaging\generation-app_1.0.181_amd64.deb novikova-eyu@10.31.205.27:/tmp/
# (введите пароль при запросе или используйте ssh-copy-id для входа по ключу)
```
---

## 7. Установка пакета

На целевом сервере:

```bash
cd /tmp
sudo dpkg -i generation-app_1.0.181_amd64.deb || sudo apt -f install
GnT8xs!
cd /opt/generation-app/
source venv/bin/activate
cd /opt/generation-app/app
export FLASK_APP=run.py
export FLASK_ENV=production
eval "$(sudo systemctl show generation-app -p Environment --value | tr ' ' '\n' | sed 's/^/export /')"
flask db heads
flask db merge heads -m "merge heads" 2>/dev/null || true
flask db upgrade

sudo systemctl restart generation-app
sudo nginx -t && sudo systemctl reload nginx
sudo journalctl -u generation-app -f
```

**Что происходит при установке:**

1. **Автоматическая установка зависимостей:** Если PostgreSQL и Redis не были установлены ранее, команда `apt -f install` установит их автоматически (так как они указаны в зависимостях пакета).

2. **Создание системных объектов:**
   - Созданы системный пользователь `generation-app` и каталог `/opt/generation-app`.
   - Развернут virtualenv и установлены Python-зависимости из `requirements-linux.txt`.
   - Скопирован unit-файл `generation-app.service`.

**Важно:** Если PostgreSQL и Redis были установлены автоматически на этом этапе, обязательно вернитесь к разделам 3 и 4, чтобы настроить базу данных и пользователя **перед** запуском приложения.

---

## 8. Автоматизация деплоя

Полный цикл (сборка + передача + установка) можно выполнить одной командой.

### Настройка (один раз)

1. Создайте файл `.env.deploy` в корне проекта (см. `.env.deploy.example`):
   ```bash
   DEPLOY_SERVER=10.31.205.27
   DEPLOY_USER=novikova-eyu
   DEPLOY_PATH=/tmp
   ```

2. Убедитесь, что SSH-ключ добавлен на сервер (`ssh-copy-id` или вручную), чтобы не вводить пароль при каждом деплое.

### Запуск

Из корня проекта (`C:\arm_gs`):


```powershell
# Полный деплой с указанной версией
cd C:\arm_gs
.\scripts\deploy.ps1 -Version 1.0.182

# Версия из git describe (тег или коммит)
.\scripts\deploy.ps1

# Только передать на сервер, установку выполнить вручную
.\scripts\deploy.ps1 -Version 1.0.181 -NoInstall

# Пакет уже собран — только передать и установить
.\scripts\deploy.ps1 -Version 1.0.181 -DeployOnly

# Пропустить пересборку образа (быстрее при повторных деплоях)
.\scripts\deploy.ps1 -Version 1.0.181 -SkipBuild
```

### Важно

- SSH-команды выполняются на сервере от вашего пользователя (`sudo` запрашивает пароль).
- Для полностью безпарольного деплоя выполните шаги из раздела ниже.

### Полностью безпарольный деплой

Выполните **один раз** на сервере под пользователем с правами sudo:

1. **SSH по ключу** — с вашей рабочей электростанции скопируйте ключ на сервер:
   ```bash
   ssh-copy-id novikova-eyu@10.31.205.27
   ```
   (Подставьте свои `DEPLOY_USER` и `DEPLOY_SERVER` из `.env.deploy`.)

2. **sudo без пароля для команд деплоя** — обязательно, иначе скрипт выдаст «sudo: a password is required» и миграции БД завершатся ошибкой «no password supplied».

   На сервере создайте файл:
   ```bash
   sudo visudo -f /etc/sudoers.d/deploy-generation-app
   ```
   Содержимое (замените `novikova-eyu` на ваш `DEPLOY_USER`):
   ```
   novikova-eyu ALL=(ALL) NOPASSWD: /usr/bin/dpkg, /usr/bin/apt, /usr/bin/apt-get, /usr/bin/systemctl, /usr/sbin/nginx, /usr/bin/bash
   ```
   (`/usr/bin/bash` нужен для выполнения миграций под пользователем generation-app.)

   Сохраните и закройте редактор. Проверьте:
   ```bash
   sudo -n dpkg --version
   sudo -n systemctl status generation-app
   ```
   Если команды выполнились без запроса пароля — настройка верна.

После этого скрипт `deploy.ps1` будет выполняться без ввода пароля.

---

## 10. Обновление миграций

Вручную (на сервере). Вариант с загрузкой env из systemd:

```bash
cd /opt/generation-app/app
source /opt/generation-app/venv/bin/activate
export FLASK_APP=run.py FLASK_ENV=production
eval "$(sudo systemctl show generation-app -p Environment --value | tr ' ' '\n' | sed 's/^/export /')"
flask db heads
flask db merge heads -m "merge heads"
flask db upgrade
```

Вариант с прямым чтением app.env (под пользователем generation-app):

```bash
sudo -u generation-app bash -c 'set -a; . /etc/generation-app/app.env; set +a; cd /opt/generation-app/app && source ../venv/bin/activate && export FLASK_APP=run.py FLASK_ENV=production && flask db upgrade'
```

- Для обновления соберите новый пакет с версией `1.0.181`, скопируйте его на сервер и выполните `sudo dpkg -i /opt/generation-app/generation-app_1.0.181_amd64.deb`.
- Сервис автоматически перезапустится (через `postinst`). При необходимости можно вручную выполнить `sudo systemctl restart generation-app`.
- Возврат к предыдущей версии возможен командой `sudo apt install ./generation-app_1.0.0_amd64.deb`.

---

✅ 1. Проверяем, есть ли сервис

Выполни:
```bash
systemctl status generation-app
```

Если он есть, ты увидишь:
активен или не активен
ошибки, если они есть
логи последних запусков

✅ 2. Запуск вручную
```bash
sudo systemctl start generation-app
```

⚙️ 3. Включить автозапуск (один раз)
```bash
sudo systemctl enable generation-app
```

📜 4. Смотреть логи приложения

Flask + Gunicorn (твой код)

```bash
sudo journalctl -u generation-app -f
```

Если нужно сохранить логи в файл:
```bash
sudo journalctl -u generation-app --no-pager > ~/generation-app.log
```

Если нужно писать в файл в реальном времени:
```bash
sudo journalctl -u generation-app -f --no-pager | tee -a ~/generation-app.log
```

Если лог пишется в файл ~/generation-app.log, посмотреть так:
```bash
less ~/generation-app.log
```

Другие варианты:
последние строки: 
```bash
tail -n 200 ~/generation-app.log
```
следить в реальном времени: 
```bash
tail -f ~/generation-app.log
```

Nginx

sudo tail -n 200 /var/log/nginx/error.log
sudo tail -n 200 /var/log/nginx/access.log


PostgreSQL

sudo tail -n 200 /var/log/postgresql/*.log


Redis

sudo tail -n 200 /var/log/redis/redis-server.log

(будет показывать логи в реальном времени)

🌐 5. Проверяем, слушает ли оно порт

Например, если у тебя Flask через Gunicorn работает на 8000:

```bash
sudo ss -tulpn | grep 8000
```
или если через nginx на порту 80:
```bash
sudo ss -tulpn | grep :80
```

## 11. Частые проблемы

- **`cd: $'/tmp\r': Нет такого файла или каталога`**, **`Error: No such command 'upgrade\r'`**, **`Invalid unit name "generation-app\x0d"`** — скрипт деплоя содержал Windows-переносы (CRLF). Обновите `scripts/deploy.ps1` до версии с нормализацией переносов. При необходимости выполните `git pull` и перезапустите деплой.
- **`/etc/generation-app/app.env: строка N: область,Еврейская: команда не найдена`** — в `app.env` есть значения с запятыми без кавычек. При `source` bash исполняет их как команды. 
- **`bash: cd: команда не найдена`** — исправлено в актуальном deploy.ps1 (использование BOM при передаче скрипта по SSH).
- **`sudo: a password is required`** и **`fe_sendauth: no password supplied`** — скрипт деплоя выполняет `sudo` без TTY; настройте NOPASSWD (раздел 8, шаг 2). Без этого переменные окружения для БД не подхватываются, и миграции падают.
- **dpkg ругается на зависимости** — выполните `sudo apt -f install`, чтобы подтянуть недостающие пакеты. PostgreSQL и Redis установятся автоматически, но их нужно будет настроить (разделы 3 и 4).
- **pip не собирает psycopg2** — проверьте, что установлены `build-essential` и `libpq-dev`.
- **Приложение не стартует** — смотрите логи `journalctl -u generation-app -b` и убедитесь, что `app.env` содержит корректный DSN и секреты.
- **Ошибка подключения к БД** — убедитесь, что PostgreSQL запущен (`sudo systemctl status postgresql`), база данных создана, и параметры в `/etc/generation-app/app.env` соответствуют реальным.
- **Ошибка подключения к Redis** — проверьте, что Redis запущен (`sudo systemctl status redis-server`) и слушает на `127.0.0.1:6379`.

### 504 Gateway Timeout / WORKER TIMEOUT при импорте Excel

При загрузке больших файлов через кнопку «Импорт» на странице station_list Gunicorn и Nginx могут прерывать запрос по таймауту.

**1. Увеличьте таймаут Gunicorn** в `/etc/generation-app/app.env` (или в переменных окружения systemd):

```bash
GUNICORN_TIMEOUT=600
```

Перезапустите приложение: `sudo systemctl restart generation-app`.

**2. Увеличьте таймаут Nginx** (если используется reverse proxy). В конфигурации location для proxy_pass добавьте:

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_read_timeout 600s;
    proxy_connect_timeout 600s;
    proxy_send_timeout 600s;
}
```

Проверьте конфиг: `sudo nginx -t`, затем: `sudo systemctl reload nginx`.


sudo mkdir -p /etc/systemd/system/generation-app.service.d
sudo systemctl daemon-reload
sudo systemctl restart generation-app

SELECT id, name, name_full
FROM gs_sys.gs_regional_districts
WHERE name IN ('Амурская область', 'Еврейская автономная область', 'Пензенская область', 'Республика Карелия')
   OR name_full IN ('Амурская область', 'Еврейская автономная область', 'Пензенская область', 'Республика Карелия');

-- Ограничение uq_station_name_district_version удалено (миграция q4r5s6t7u8v9).
-- Дубликаты (name, id_regional_district, database_version_id) допускаются.

sudo systemctl restart generation-app


python scripts/fill_machine_commission_year_from_exploitation.py
python scripts/fix_alembic_version.py


$env:PGPASSWORD = '***'
.\scripts\sync_postgres_remote_to_local.ps1 -RemoteHost 10.31.205.27 -Force