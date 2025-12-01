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