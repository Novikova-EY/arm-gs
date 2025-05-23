from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate


db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()


def create_app():
    app = Flask(__name__)

    # Подключение конфигурации
    app.config.from_object('config.Config')

    # Инициализация базы данных
    db.init_app(app)

    # Импорт моделей
    from app.models.energy_systems_models import (
        EnergySystemType,
        EnergyArea,
        RegionalEnergySystem,
        UnionEnergySystem,
    )
    from app.models.territories_models import (
        FederalDistrict,
        RegionalDistrict,
    )    
    from app.models.fuels_models import Fuel, FuelType, FuelCategory
    from app.models.gen_companies_models import GenCompany
    from app.models.stations_models import (
        ConditionType,
        StationType,
        TesType,
        StationGroup,
        Station,
        Machine,
        MachineType,
        Boiler,
    )

    # Настройка мапперов
    db.configure_mappers()

    # Инициализация миграций
    migrate.init_app(app, db)

    # Инициализация LoginManager
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'  # Путь для перенаправления при неавторизованном доступе
    login_manager.login_message = "Пожалуйста, войдите, чтобы получить доступ к этой странице."
    login_manager.login_message_category = "warning"  # Категория флеш-сообщения

    # Создание таблиц, если они не существуют
    with app.app_context():
        db.create_all()  # Создаем все таблицы, если они ещё не созданы

    from app.services.station_services.help_services import format_decimal_for_display
    @app.template_filter('format_decimal')
    def format_decimal_filter(value):
        from flask import request
        digits = request.args.get("rounding_digits", default=None, type=int)
        return format_decimal_for_display(value, digits=digits)


    # Регистрация маршрутов
    from app.routes.auth import auth_bp
    from app.routes.references import reference_bp
    from app.routes.stations import station_bp
    from app.routes import start_bp
    from app.routes.log import logs_bp
    app.register_blueprint(start_bp, url_prefix='/')  # Префикс для маршрутов приложения
    app.register_blueprint(reference_bp, url_prefix='/references')  # Префикс для общих маршрутов
    app.register_blueprint(station_bp, url_prefix='/stations')  # Префикс для общих маршрутов
    app.register_blueprint(auth_bp, url_prefix='/auth')  # Префикс для авторизации
    app.register_blueprint(logs_bp, url_prefix='/log')  # Префикс для просмотра логов

    return app


# Функция загрузки пользователя
@login_manager.user_loader
def load_user(user_id):
    from app.models.auth_models import User  # Импортируем модель внутри функции, чтобы избежать циклического импорта
    return User.query.get(int(user_id))




