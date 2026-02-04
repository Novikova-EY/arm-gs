import os
from dotenv import load_dotenv
# Загрузка переменных окружения из .env
load_dotenv()

_SCHEMA_RENAMES = {
    # legacy -> new
    "generation": "gs_gen",
    "auth": "gs_auth",
    "logs": "gs_logs",
    "fuel": "gs_fue",
}

def _normalize_schema_name(value: str | None, default: str) -> str:
    """
    Нормализует имя схемы БД.
    - Если пришло legacy-имя (generation/auth/logs) — автоматически маппим на новое.
    - Если значение пустое/None — используем default.
    """
    if value is None:
        return default
    v = str(value).strip()
    if not v:
        return default
    return _SCHEMA_RENAMES.get(v, v)

def _normalize_search_path(value: str | None, default: str) -> str:
    """
    Нормализует DB_SEARCH_PATH, применяя rename-map к каждому элементу пути.
    """
    raw = default if value is None else str(value)
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    parts = [_SCHEMA_RENAMES.get(p, p) for p in parts]
    return ",".join(parts)

def _parse_int_set(value: str | None) -> set[int]:
    if value is None:
        return set()
    parts = [p.strip() for p in str(value).split(",") if p.strip()]
    result = set()
    for part in parts:
        try:
            result.add(int(part))
        except ValueError:
            continue
    return result

def _parse_str_set(value: str | None) -> set[str]:
    if value is None:
        return set()
    return {p.strip() for p in str(value).split(",") if p.strip()}

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME")
DB_DRIVER = os.getenv("DB_DRIVER", "psycopg2")
SECRET_KEY = os.getenv('SECRET_KEY', 'cVX84FQ5P0!mXnUwZ@sRek#bLgdpN9Yz')
SCHEMA_AUTH = _normalize_schema_name(os.getenv("SCHEMA_AUTH"), "gs_auth")
SCHEMA_LOGS = _normalize_schema_name(os.getenv("SCHEMA_LOGS"), "gs_logs")
# После миграции 7e4b6c9f1a23 схема refdata была переименована в gs_sys.
# Поэтому значение по умолчанию изменено на gs_sys.
SCHEMA_REFDATA = os.getenv("SCHEMA_REFDATA", "gs_sys")
SCHEMA_GENERATION = _normalize_schema_name(os.getenv("SCHEMA_GENERATION"), "gs_gen")
SCHEMA_FUEL = _normalize_schema_name(os.getenv("SCHEMA_FUEL"), "gs_fue")
SCHEMA_FUE_EM = _normalize_schema_name(os.getenv("SCHEMA_FUE_EM"), "gs_fue_em")
DB_SEARCH_PATH = _normalize_search_path(
    os.getenv("DB_SEARCH_PATH"),
    "gs_auth,gs_logs,gs_sys,gs_gen,gs_fue,gs_fue_em",
)
STATION_UNIQUE_EXCLUDED_DISTRICT_IDS = _parse_int_set(
    os.getenv("STATION_UNIQUE_EXCLUDED_DISTRICT_IDS", "")
)
STATION_UNIQUE_EXCLUDED_DISTRICT_NAMES = _parse_str_set(
    os.getenv("STATION_UNIQUE_EXCLUDED_DISTRICT_NAMES", "Амурская область")
)
STATION_UNIQUE_EXCLUDED_DISTRICT_UUIDS = _parse_str_set(
    os.getenv("STATION_UNIQUE_EXCLUDED_DISTRICT_UUIDS", "")
)
UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
ALLOWED_EXTENSIONS = os.getenv("ALLOWED_EXTENSIONS", "xls,xlsx").split(",")
# DEBUG определяется по FLASK_ENV или явной переменной DEBUG.
# Важно: пустое/не заданное DEBUG НЕ должно принудительно выключать debug —
# тогда dev-режим (FLASK_ENV=development) сможет включать автообновление шаблонов.
def _resolve_debug() -> bool:
    flask_env = (os.getenv("FLASK_ENV") or "").lower()
    explicit_raw = os.getenv("DEBUG")

    if explicit_raw is not None:
        explicit = explicit_raw.strip().lower()
        if explicit in ("true", "1", "yes"):
            return True
        if explicit in ("false", "0", "no"):
            return False
        # если переменная есть, но пустая/невалидная — считаем как "не задано"

    if flask_env == "development":
        return True

    # По умолчанию production (безопаснее)
    return False

DEBUG = _resolve_debug()
START_YEAR_SIPR = 2026
START_YEAR = 2024
END_YEAR = 2031
END_YEAR_SIPR = 2031

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'cVX84FQ5P0!mXnUwZ@sRek#bLgdpN9Yz')
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')
    SCHEMA_AUTH = _normalize_schema_name(os.getenv("SCHEMA_AUTH"), "gs_auth")
    SCHEMA_LOGS = _normalize_schema_name(os.getenv("SCHEMA_LOGS"), "gs_logs")
    # Значение по умолчанию соответствует новой схеме gs_sys
    SCHEMA_REFDATA = os.getenv("SCHEMA_REFDATA", "gs_sys")
    SCHEMA_GENERATION = _normalize_schema_name(os.getenv("SCHEMA_GENERATION"), "gs_gen")
    SCHEMA_FUEL = _normalize_schema_name(os.getenv("SCHEMA_FUEL"), "gs_fue")
    SCHEMA_FUE_EM = _normalize_schema_name(os.getenv("SCHEMA_FUE_EM"), "gs_fue_em")
    DB_SEARCH_PATH = _normalize_search_path(
        os.getenv("DB_SEARCH_PATH"),
        f"{SCHEMA_AUTH},{SCHEMA_LOGS},{SCHEMA_REFDATA},{SCHEMA_GENERATION},{SCHEMA_FUEL},{SCHEMA_FUE_EM},public",
    )
    STATION_UNIQUE_EXCLUDED_DISTRICT_IDS = _parse_int_set(
        os.getenv("STATION_UNIQUE_EXCLUDED_DISTRICT_IDS", "")
    )
    STATION_UNIQUE_EXCLUDED_DISTRICT_NAMES = _parse_str_set(
        os.getenv("STATION_UNIQUE_EXCLUDED_DISTRICT_NAMES", "Амурская область")
    )
    STATION_UNIQUE_EXCLUDED_DISTRICT_UUIDS = _parse_str_set(
        os.getenv("STATION_UNIQUE_EXCLUDED_DISTRICT_UUIDS", "")
    )
    
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
    # DEBUG берём из вычисленного значения выше (см. _resolve_debug()).
    DEBUG = DEBUG
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
    
    # Настройки версии базы данных по умолчанию
    # Для новых пользователей будет выбрана версия БД по умолчанию
    # Если не указано, будет использована последняя версия по номеру версии
    DEFAULT_DATABASE_VERSION_ID = os.getenv('DEFAULT_DATABASE_VERSION_ID', None)  # ID версии или None для автоопределения
    DEFAULT_DATABASE_VERSION_NUMBER = os.getenv('DEFAULT_DATABASE_VERSION_NUMBER', None)  # Номер версии или None