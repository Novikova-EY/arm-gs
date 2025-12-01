# Установка приложения через `.deb` пакет

Документ описывает полный цикл упаковки приложения в `.deb`, перенос пакета на сервер Astra Linux (Debian-based) и последующую установку.

## 1. Подготовка окружения разработчика

1. Используйте Linux/WSL с доступом к bash.
2. Установите системные зависимости:
   ```bash
   sudo apt update
   sudo apt install build-essential fakeroot rsync git python3 python3-venv python3-pip
   ```
3. Клонируйте репозиторий и перейдите в корень:
   ```bash
   git clone <repo-url> fproject && cd fproject
   ```

## 2. Сборка `.deb`

Скрипт `scripts/build_deb.sh` формирует пакет с версией из аргумента (или из `git describe`, если аргумент не задан).

```bash
chmod +x scripts/build_deb.sh
./scripts/build_deb.sh 1.0.0
```

В результате появится файл `build/deb/generation-app_1.0.0.deb`.

> Примечание: скрипт копирует весь проект в `/opt/generation-app/app`, добавляет сервис systemd и шаблон `.env`.

## 3. Требования на сервере Astra Linux

На целевом сервере должны быть установлены:

```bash
sudo apt install python3 python3-venv python3-pip python3-distutils python3-wheel \
                 postgresql-client redis-server nginx
```

- PostgreSQL и Redis могут располагаться на отдельных узлах, но доступ из приложения должен быть настроен.
- Nginx необходим, если планируется проксирование HTTP (рекомендуется).

## 4. Установка пакета

1. Передайте `.deb` на сервер (scp, rsync и т.д.).
2. Установите пакет:
   ```bash
   sudo apt install ./generation-app_1.0.0.deb
   ```
   Во время `postinst`:
   - создаётся пользователь `generation-app`;
   - разворачивается каталог `/opt/generation-app`;
   - формируется виртуальное окружение и устанавливаются Python-зависимости;
   - создаётся `/etc/generation-app/app.env` (если отсутствует) из шаблона.
3. Проверьте/отредактируйте `/etc/generation-app/app.env`, задав реальные параметры БД, Redis, секреты и опции Gunicorn.

## 5. Инициализация базы данных

1. Создайте схему и пользователя в PostgreSQL (пример):
   ```sql
   CREATE DATABASE arm_generation;
   CREATE USER arm_user WITH ENCRYPTED PASSWORD '***';
   GRANT ALL PRIVILEGES ON DATABASE arm_generation TO arm_user;
   ```
2. Примените миграции (выполняется на сервере):
   ```bash
   sudo -u generation-app bash -c '
       source /opt/generation-app/venv/bin/activate
       export $(grep -v "^#" /etc/generation-app/app.env | xargs)
       flask db upgrade
   '
   ```

## 6. Управление сервисом

Сервис создаётся как `generation-app.service`.

```bash
sudo systemctl start generation-app
sudo systemctl status generation-app
sudo systemctl enable generation-app
```

Логи:
- приложение: `/var/log/generation-app/*.log` (каталог создаётся через `tmpfiles.d`);
- systemd: `journalctl -u generation-app`.

## 7. Интеграция с Nginx (пример)

```
server {
    listen 80;
    server_name generation.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Перезапустите Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/generation /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

## 8. Обновление пакета

1. Соберите новую версию: `./scripts/build_deb.sh 1.1.0`.
2. На сервере выполните:
   ```bash
   sudo apt install ./generation-app_1.1.0.deb
   ```
   Скрипт `prerm` остановит сервис, `postinst` обновит окружение и зависимости, при этом файл `/etc/generation-app/app.env` сохранится.

## 9. Удаление

```bash
sudo apt remove generation-app          # оставляет данные и конфиг
sudo apt purge generation-app           # дополнительно удаляет /opt/generation-app и пользователя
```

## 10. Тест проверочного запуска

После установки выполните:

```bash
curl -f http://127.0.0.1:8000/health || journalctl -u generation-app -n 200
```

Добавьте реальный health-роут при необходимости.

---

Пакет и документация рассчитаны на Astra Linux (Debian 11/12). Для других систем потребуются незначительные изменения путей и зависимостей.





