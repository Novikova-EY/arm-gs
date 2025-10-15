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
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_recycle': int(os.getenv('SQLALCHEMY_POOL_RECYCLE', 280))}  # Используем значение по умолчанию, если не указано
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    ALLOWED_EXTENSIONS = set(os.getenv('ALLOWED_EXTENSIONS', '').split(','))
    DEBUG=os.getenv("DEBUG", "False").lower() == "true"
    START_YEAR_SIPR = 2026
    START_YEAR = 2024
    END_YEAR = 2031
    END_YEAR_SIPR = 2031