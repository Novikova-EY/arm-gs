FROM ubuntu:22.04

# Базовые зависимости для сборки deb-пакета и работы Python
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y \
        python3 python3-venv python3-pip \
        build-essential dpkg-dev git && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Рабочая директория внутри контейнера
WORKDIR /app

# По умолчанию запускаем скрипт сборки,
# а сам проект будем монтировать с хоста (через -v)
ENTRYPOINT ["python3", "scripts/build_deb.py"]
