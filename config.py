import os
from dotenv import load_dotenv
# Загрузка переменных окружения из .env
load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_DRIVER = os.getenv("DB_DRIVER", "psycopg2")
SECRET_KEY = os.getenv('SECRET_KEY', 'cVX84FQ5P0!mXnUwZ@sRek#bLgdpN9Yz')
SCHEMA_AUTH = os.getenv("SCHEMA_AUTH", "auth")
SCHEMA_LOGS = os.getenv("SCHEMA_LOGS", "logs")
SCHEMA_REFDATA = os.getenv("SCHEMA_REFDATA", "refdata")
SCHEMA_GENERATION = os.getenv("SCHEMA_GENERATION", "generation")
DB_SEARCH_PATH = os.getenv("DB_SEARCH_PATH", "auth,logs,refdata,generation")
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
ALLOWED_EXTENSIONS = os.getenv("ALLOWED_EXTENSIONS", "xls,xlsx").split(",")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
START_YEAR_SIPR = 2026
START_YEAR = 2024
END_YEAR = 2031
END_YEAR_SIPR = 2031

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'cVX84FQ5P0!mXnUwZ@sRek#bLgdpN9Yz')
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')
    SCHEMA_AUTH = os.getenv("SCHEMA_AUTH", "auth")
    SCHEMA_LOGS = os.getenv("SCHEMA_LOGS", "logs")
    SCHEMA_REFDATA = os.getenv("SCHEMA_REFDATA", "refdata")
    SCHEMA_GENERATION = os.getenv("SCHEMA_GENERATION", "generation")
    DB_SEARCH_PATH = os.getenv("DB_SEARCH_PATH", f"{SCHEMA_AUTH},{SCHEMA_LOGS},{SCHEMA_REFDATA},{SCHEMA_GENERATION},public")
    
    # Оптимизированные настройки пула соединений для параллельной работы
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': int(os.getenv('SQLALCHEMY_POOL_SIZE', 20)),  # Базовый размер пула
        'max_overflow': int(os.getenv('SQLALCHEMY_MAX_OVERFLOW', 40)),  # Дополнительные соединения при пиковой нагрузке
        'pool_timeout': int(os.getenv('SQLALCHEMY_POOL_TIMEOUT', 30)),  # Таймаут ожидания свободного соединения
        'pool_recycle': int(os.getenv('SQLALCHEMY_POOL_RECYCLE', 280)),  # Переиспользование соединений
        'pool_pre_ping': os.getenv('SQLALCHEMY_POOL_PRE_PING', 'True').lower() == 'true',  # Проверка соединения перед использованием
        'echo_pool': os.getenv('SQLALCHEMY_ECHO_POOL', 'False').lower() == 'true',  # Логирование пула (для отладки)
    }
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    ALLOWED_EXTENSIONS = set(os.getenv('ALLOWED_EXTENSIONS', '').split(','))
    DEBUG=os.getenv("DEBUG", "False").lower() == "true"
    START_YEAR_SIPR = 2026
    START_YEAR = 2024
    END_YEAR = 2031
    END_YEAR_SIPR = 2031
    
    # Redis configuration для кэширования и сессий
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_TYPE = os.getenv('CACHE_TYPE', 'RedisCache')
    CACHE_REDIS_URL = os.getenv('CACHE_REDIS_URL', REDIS_URL)
    CACHE_DEFAULT_TIMEOUT = int(os.getenv('CACHE_DEFAULT_TIMEOUT', 300))
    SESSION_TYPE = 'redis'
    SESSION_REDIS = None  # Будет установлен в create_app
    
    # Настройки автоматических бэкапов
    ENABLE_SCHEDULED_BACKUPS = os.getenv('ENABLE_SCHEDULED_BACKUPS', 'False').lower() == 'true'
    AUTO_BACKUP_DIR = os.getenv('AUTO_BACKUP_DIR', 'backups/auto')
    KEEP_AUTO_BACKUPS = int(os.getenv('KEEP_AUTO_BACKUPS', 7))  # Количество хранимых бэкапов
    # Расписание бэкапов (по умолчанию: каждый день в 2:00)
    BACKUP_SCHEDULE = {
        'hour': int(os.getenv('BACKUP_SCHEDULE_HOUR', 2)),
        'minute': int(os.getenv('BACKUP_SCHEDULE_MINUTE', 0))
    }