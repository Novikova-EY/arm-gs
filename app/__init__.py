import os
from config import SECRET_KEY
from flask import Flask
from sqlalchemy import event
from sqlalchemy.engine import URL
from app.extensions import db, migrate, login_manager

def create_app():
    app = Flask(__name__)
    app.secret_key = SECRET_KEY
    
    db_uri = URL.create(
        "postgresql+psycopg2",
        username=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME"),
        query={"client_encoding": "utf8"},
    )
    app.config["SQLALCHEMY_DATABASE_URI"] = db_uri

    # Инициализация расширений
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Пожалуйста, войдите, чтобы получить доступ к этой странице."
    login_manager.login_message_category = "warning"

    # Слушатель для установки search_path — РЕГИСТРИРУЕМ ПОСЛЕ init_app И В КОНТЕКСТЕ
    def _set_search_path(dbapi_connection, _):
        search_path = app.config.get("DB_SEARCH_PATH", "public")
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f"SET search_path TO {search_path};")

    with app.app_context():
        event.listen(db.engine, "connect", _set_search_path)

        # Импорт моделей (после db.init_app)
        from app.logs.models import logs_models
        from app.refdata.models import energy_systems_models
        from app.refdata.models import territories_models
        from app.refdata.models import fuels_models
        from app.refdata.models import gen_companies_models
        from app.refdata.models import stations_refdata_models
        from app.refdata.models import territories_models
        from app.refdata.models import years_models
        from app.generation.models import stations_models
        from app.generation.models import machines_models
        from app.generation.models import pgu_machines_models
        from app.generation.models import boilers_models

        # Проброс мапперов
        db.configure_mappers()

    # Фильтр форматирования чисел
    from app.generation.services.station_services.help_services import format_decimal_for_display

    @app.template_filter("format_decimal")
    def format_decimal_filter(value):
        from flask import request
        digits = request.args.get("rounding_digits", default=None, type=int)
        return format_decimal_for_display(value, digits=digits)

    # Регистрация блюпринтов
    from app.auth.routes import auth_bp
    from app.refdata.routes import reference_bp
    from app.generation.routes.stations import station_bp
    from app.generation.routes.generation_routes import generation_bp
    from app.generation.routes.rational_structure import rational_structure_bp
    from app.generation.routes.station_changes import station_changes_bp
    from app.start.routes import start_bp
    from app.logs.routes import logs_bp

    app.register_blueprint(start_bp, url_prefix="/")
    app.register_blueprint(reference_bp, url_prefix="/references")
    app.register_blueprint(generation_bp, url_prefix="/generation")
    app.register_blueprint(station_bp, url_prefix="/stations")
    app.register_blueprint(rational_structure_bp, url_prefix="/rational_structure")
    app.register_blueprint(station_changes_bp, url_prefix="/station_changes")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(logs_bp, url_prefix="/log")

    # Загрузка пользователя для Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from app.auth.models.auth_models import User
        return User.query.get(int(user_id))
    
    return app


