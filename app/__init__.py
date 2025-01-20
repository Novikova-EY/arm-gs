from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():

    app = Flask(__name__)

    # Подключение конфигурации
    app.config.from_object('config.Config')

    # Инициализация базы данных
    db.init_app(app)

    # Инициализация LoginManager
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'  # Путь для перенаправления при неавторизованном доступе
    login_manager.login_message = "Пожалуйста, войдите, чтобы получить доступ к этой странице."
    login_manager.login_message_category = "warning"  # Категория флеш-сообщения

    # Создание таблиц, если они не существуют
    with app.app_context():
        db.create_all()
    
    # Регистрация маршрутов
    from app.routes.auth import auth_bp
    from app.routes.app import app_bp
    from app.routes import start_bp
    from app.routes.log import logs_bp
    app.register_blueprint(start_bp, url_prefix='/')  # Префикс для маршрутов приложения
    app.register_blueprint(app_bp, url_prefix='/app')  # Префикс для общих маршрутов
    app.register_blueprint(auth_bp, url_prefix='/auth')  # Префикс для авторизации
    app.register_blueprint(logs_bp, url_prefix='/log')  # Префикс для просмотра логов
    
    return app

# Функция загрузки пользователя
@login_manager.user_loader
def load_user(user_id):
    from app.models.auth_models import User  # Импортируем модель внутри функции, чтобы избежать циклического импорта
    return User.query.get(int(user_id))
