import os
from app.generation.models.boiler import boiler_model
from app.generation.models.machine import machine_tes_type_model
from app.refdata.models.refdata_for_stations.machine import machine_type_model, pgu_tes_machine_type_model, tes_machine_type_model, tes_type_model
from app.refdata.models.refdata_for_stations.station import station_type_model
from app.refdata.models.refdata_for_stations.technologies import equipment_group_model, technology_availability_model, technology_type_model
from config import SECRET_KEY, DEBUG
from flask import Flask, redirect, request, url_for, flash
from sqlalchemy import event
from sqlalchemy.engine import URL
from app.extensions import db, migrate, login_manager
from config import Config
import logging
from flask_compress import Compress

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config) 
    app.secret_key = SECRET_KEY
    app.debug = app.config.get("DEBUG", False)
    # Обновление шаблонов без перезапуска (особенно важно в разработке)
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.jinja_env.auto_reload = True
    app.config['SQLALCHEMY_ECHO'] = False
    app.logger.setLevel(logging.DEBUG)
    # Включаем сжатие ответов (gzip, br, zstd)
    Compress(app)

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
        from app.auth.models import (
            user_model,
            role_model,
            user_role_model,
        )
        from app.logs.models import (
            log_model,
        )
        from app.refdata.models.energy_systems import (
            regional_energy_system_model, 
            regional_district_regional_energy_system_model, 
            union_energy_system_model, 
            energy_system_type_model, 
            energy_unit_model, 
            energy_zone_model, 
            energy_area_model,
            )
        from app.refdata.models.territories import (
            regional_district_model,
            federal_district_model,
            )
        from app.refdata.models.fuels import (
            fuel_model, 
            fuel_type_model, 
            fuel_category_model,
            )
        from app.refdata.models.gen_companies import (
            gen_company_model,
        )
        from app.refdata.models.refdata_for_stations import (
            condition_type_model,
        )
        from app.refdata.models.refdata_for_stations.station import (
            station_type_model,
        )
        from app.refdata.models.refdata_for_stations.machine import (
            machine_type_model,
            pgu_tes_machine_type_model,
            tes_type_model,
            tes_machine_type_model,
        )
        from app.refdata.models.refdata_for_stations.technologies import (
            equipment_group_model,
        )
        from app.refdata.models.refdata_for_stations import (
            condition_type_model,
        )
        from app.refdata.models.years import (
            year_model,
            year_feature_model,
        )
        from app.generation.models.station import (
            station_model,
            station_group_model,
            station_power_model,
        )
        from app.generation.models.machine import (
            machine_fuel_model,
            machine_model,
            machine_power_model,
        )
        from app.generation.models.pgu_machine import (
            pgu_machine_model,
            pgu_machine_power_model,
        )
        from app.generation.models.boiler import (
            boiler_model,
        )

        # Проброс мапперов
        db.configure_mappers()

    # Фильтр форматирования чисел
    from app.common.services.help_services import format_decimal_for_display

    @app.template_filter("format_decimal")
    def format_decimal_filter(value):
        from flask import request
        digits = request.args.get("rounding_digits", default=None, type=int)
        return format_decimal_for_display(value, digits=digits)

    # Регистрация блюпринтов
    from app.auth.routes import auth_bp
    from app.auth.routes import users_bp
    from app.refdata.routes import refdata_bp
    from app.generation.routes.stations import station_bp
    from app.generation.routes.generation_routes import generation_bp
    from app.generation.routes.rational_structure import rational_structure_bp
    from app.generation.routes.station_changes import station_changes_bp
    from app.start.routes import start_bp
    from app.logs.routes import logs_bp

    app.register_blueprint(start_bp, url_prefix="/")
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(refdata_bp, url_prefix="/refdata")
    app.register_blueprint(generation_bp, url_prefix="/generation")
    app.register_blueprint(station_bp, url_prefix="/generation/stations")
    app.register_blueprint(rational_structure_bp, url_prefix="/rational_structure")
    app.register_blueprint(station_changes_bp, url_prefix="/generation/station_changes")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(logs_bp, url_prefix="/log")

    # Загрузка пользователя для Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from app.auth.models.user_model import User
        return User.query.get(int(user_id))

    return app


