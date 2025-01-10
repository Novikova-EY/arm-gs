import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret_key')  # Значение по умолчанию
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_recycle': int(os.getenv('SQLALCHEMY_POOL_RECYCLE', 280))}  # Используем значение по умолчанию, если не указано
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    ALLOWED_EXTENSIONS = set(os.getenv('ALLOWED_EXTENSIONS', '').split(','))
    DEBUG = os.getenv('DEBUG', 'False').lower() in ['true', '1']