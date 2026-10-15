Где смотреть логи

Flask + Gunicorn (твой код)

sudo journalctl -u generation-app -f


Nginx

sudo tail -n 200 /var/log/nginx/error.log
sudo tail -n 200 /var/log/nginx/access.log


PostgreSQL

sudo tail -n 200 /var/log/postgresql/*.log


Redis

sudo tail -n 200 /var/log/redis/redis-server.log


Проблемы с восстановлением БД (pg_restore зависает)

Если процесс восстановления версии БД завис:

1. Проверить активные соединения к БД:
   sudo -u postgres psql -c "SELECT pid, usename, application_name, state, query FROM pg_stat_activity WHERE datname = 'your_db_name';"

2. Проверить блокировки:
   sudo -u postgres psql -c "SELECT * FROM pg_locks WHERE NOT granted;"

3. Если нужно убить зависший процесс pg_restore:
   # Найти PID процесса
   ps aux | grep pg_restore
   # Убить процесс
   kill -9 <PID>

4. Проверить логи PostgreSQL на ошибки:
   sudo tail -n 500 /var/log/postgresql/*.log | grep -i error

5. Если процесс завис из-за блокировок, можно принудительно завершить активные соединения:
   sudo -u postgres psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'your_db_name' AND pid <> pg_backend_pid();"

ВАЖНО: После принудительного завершения соединений восстановление может продолжиться автоматически,
но лучше перезапустить процесс восстановления заново.