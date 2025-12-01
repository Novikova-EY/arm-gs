import os
from app.generation.models.boiler import boiler_model
from app.generation.models.machine import machine_tes_type_model
from app.refdata.models.refdata_for_stations.machine import machine_type_model, pgu_tes_machine_type_model, tes_machine_type_model, tes_type_model
from app.refdata.models.refdata_for_stations.station import station_type_model
from app.refdata.models.refdata_for_stations.technologies import equipment_group_model, technology_availability_model, technology_type_model
from app.common.models.database_version_model import DatabaseVersion
from config import SECRET_KEY, DEBUG
from flask import Flask, redirect, request, url_for, flash, g, render_template
from sqlalchemy import event
from sqlalchemy.engine import URL
from app.extensions import db, migrate, login_manager, cache
from config import Config
import logging
from flask_compress import Compress
import redis
from flask_session import Session
from app.common.middleware import ConcurrentUpdateMiddleware

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
    compress = Compress(app)

    # Обработчик для отключения сжатия для определенных маршрутов
    @app.after_request
    def disable_compression_for_files(response):
        # Проверяем флаг отключения сжатия
        if hasattr(g, 'no_compress') and g.no_compress:
            # Удаляем заголовки сжатия
            response.headers.pop('Content-Encoding', None)
            response.headers.pop('Vary', None)
        return response

    # Get database credentials with proper encoding handling
    db_user = os.getenv("DB_USER")
    db_pass = os.getenv("DB_PASS")
    
    # Ensure password is properly decoded if it contains special characters
    if db_pass:
        try:
            # If password is bytes, decode it properly
            if isinstance(db_pass, bytes):
                db_pass = db_pass.decode('utf-8', errors='ignore')
            # Ensure it's a valid UTF-8 string
            db_pass = str(db_pass)
        except Exception as e:
            app.logger.error(f"Error processing database password: {e}")
            raise
    
    db_name = os.getenv("DB_NAME")

    db_uri = URL.create(
        "postgresql+psycopg2",
        username=db_user,
        password=db_pass,
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=db_name,
        query={"client_encoding": "utf8"},
    )

    app.config["SQLALCHEMY_DATABASE_URI"] = db_uri

    # Инициализация Redis для кэширования и сессий
    try:
        # Отдельный Redis‑клиент для сессий с более щадящими таймаутами
        redis_client = redis.from_url(
            app.config.get("REDIS_URL", "redis://localhost:6379/0"),
            socket_connect_timeout=5,  # больше времени на установление соединения
            socket_timeout=5,          # больше времени на операции записи/чтения
            decode_responses=False,
        )
        redis_client.ping()
        app.config['SESSION_REDIS'] = redis_client
        app.config.setdefault("SESSION_TYPE", "redis")
        app.logger.info("Redis connection established successfully")
    except (redis.ConnectionError, redis.TimeoutError, Exception) as e:
        app.logger.warning(f"Redis connection failed: {e}. Using fallback simple cache.")
        app.config['CACHE_TYPE'] = 'SimpleCache'
        app.config['SESSION_TYPE'] = 'filesystem'
        app.config['SESSION_REDIS'] = None
    
    # Инициализация расширений
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Инициализация кэша (с обработкой ошибок)
    try:
        cache.init_app(app)
    except Exception as e:
        app.logger.error(f"Cache initialization failed: {e}. Cache disabled.")
    
    # Инициализация сессий (с обработкой ошибок)
    try:
        Session(app)
    except Exception as e:
        app.logger.error(f"Session initialization failed: {e}. Using default sessions.")
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Пожалуйста, войдите, чтобы получить доступ к этой странице."
    login_manager.login_message_category = "warning"
    
    # Инициализация middleware для управления версиями БД (ПЕРВЫМ!)
    from app.common.middleware.database_version_middleware import init_database_version_middleware
    init_database_version_middleware(app)
    
    # Инициализация middleware для обработки concurrent updates
    ConcurrentUpdateMiddleware(app)
    
    # Инициализация автоматических бэкапов по расписанию
    # ВРЕМЕННО ОТКЛЮЧЕНО из-за отсутствия apscheduler
    # from app.common.services.scheduled_backup_service import scheduled_backup_service
    # scheduled_backup_service.init_app(app)


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
        from app.generation.models.document import (
            document_model,
        )

        # Проброс мапперов
        db.configure_mappers()
        
        # Прогрев кэша станций и запуск периодического обновления (в фоновом режиме)
        try:
            from app.generation.services.station_services.aggregation_cache import (
                warmup_station_cache, 
                start_background_cache_refresh
            )
            import threading
            
            # Запускаем первоначальный прогрев кэша с app context
            def warmup_with_context():
                with app.app_context():
                    warmup_station_cache()
            
            warmup_thread = threading.Thread(target=warmup_with_context, daemon=True)
            warmup_thread.start()
            app.logger.info("[CACHE WARMUP] Запущен прогрев кэша в фоновом режиме")
            
            # Запускаем периодическое обновление кэша каждые 25 минут (за 5 минут до истечения TTL)
            start_background_cache_refresh(app, interval_minutes=25)
            app.logger.info("[CACHE REFRESH] Запущено периодическое обновление кэша")
        except Exception as e:
            app.logger.warning(f"[CACHE] Не удалось запустить кэш: {e}")

    # Фильтр форматирования чисел
    from app.common.services.help_services import format_decimal_for_display

    @app.template_filter("format_decimal")
    def format_decimal_filter(value):
        from flask import request
        digits = request.args.get("rounding_digits", default=None, type=int)
        return format_decimal_for_display(value, digits=digits)
    
    # Фильтр для обработки ссылок на документы в тексте
    @app.template_filter("render_document_links")
    def render_document_links_filter(text):
        """
        Преобразует ссылки формата [DOC:id:название] в HTML-ссылки.
        Пример: [DOC:5:Приказ №123] -> <a href="/generation/stations/view_document/5">Приказ №123</a>
        """
        if not text:
            return ""
        
        import re
        from markupsafe import Markup, escape
        
        # Паттерн для поиска ссылок на документы: [DOC:id:название]
        pattern = r'\[DOC:(\d+):([^\]]+)\]'
        
        def replace_link(match):
            doc_id = match.group(1)
            doc_name = match.group(2)
            # Экранируем название документа для безопасности
            safe_name = escape(doc_name)
            # Создаем HTML-ссылку для просмотра (не скачивания)
            return f'<a href="{url_for("station_bp.view_document_file", document_id=doc_id)}" class="document-link" target="_blank" rel="noopener noreferrer">{safe_name}</a>'
        
        # Разбиваем текст на части: обычный текст и ссылки
        parts = []
        last_end = 0
        
        for match in re.finditer(pattern, text):
            # Добавляем экранированный текст перед ссылкой
            if match.start() > last_end:
                text_part = text[last_end:match.start()]
                # Заменяем переносы строк на <br> для правильного отображения
                text_part = escape(text_part).replace('\n', Markup('<br>'))
                parts.append(text_part)
            # Добавляем ссылку
            parts.append(replace_link(match))
            last_end = match.end()
        
        # Добавляем оставшийся текст после последней ссылки
        if last_end < len(text):
            text_part = text[last_end:]
            # Заменяем переносы строк на <br> для правильного отображения
            text_part = escape(text_part).replace('\n', Markup('<br>'))
            parts.append(text_part)
        
        # Объединяем все части и возвращаем как безопасный HTML
        return Markup(''.join(parts))

    # Контекст-процессор для текущей версии БД и CSRF токена
    @app.context_processor
    def inject_database_version():
        """Добавляет информацию о текущей версии БД и CSRF токен во все шаблоны."""
        from flask import g, session
        from app.common.models.database_version_model import DatabaseVersion
        
        current_version = None
        if hasattr(g, 'current_db_version') and g.current_db_version:
            current_version = DatabaseVersion.query.get(g.current_db_version)
        elif not hasattr(g, 'current_db_version'):
            # Если версия не установлена в middleware, ищем активную
            current_version = DatabaseVersion.query.filter_by(is_active=True).first()
            # Если активной нет, используем версию по умолчанию
            if not current_version:
                from app.common.services.database_version_services import get_default_version
                current_version = get_default_version()
        
        # Получаем CSRF токен
        csrf_token = session.get('csrf_token', '')
        
        return dict(current_db_version=current_version, csrf_token=csrf_token)
    
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
    from app.exports.routes import exports_bp

    app.register_blueprint(start_bp, url_prefix="/")
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(refdata_bp, url_prefix="/refdata")
    app.register_blueprint(generation_bp, url_prefix="/generation")
    app.register_blueprint(station_bp, url_prefix="/generation/stations")
    app.register_blueprint(rational_structure_bp, url_prefix="/rational_structure")
    app.register_blueprint(station_changes_bp, url_prefix="/generation/station_changes")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(logs_bp, url_prefix="/log")
    app.register_blueprint(exports_bp, url_prefix="")

    # Загрузка пользователя для Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from app.auth.models.user_model import User
        return User.query.get(int(user_id))
    
    # Error handlers для детального логирования
    @app.errorhandler(500)
    def internal_error(error):
        """Обработчик Internal Server Error."""
        import traceback
        app.logger.error('='*60)
        app.logger.error('Internal Server Error occurred')
        app.logger.error(f'Error: {error}')
        app.logger.error('Traceback:')
        app.logger.error(traceback.format_exc())
        app.logger.error('='*60)
        
        # Откат транзакции БД при ошибке
        try:
            db.session.rollback()
        except Exception as e:
            app.logger.error(f'Error during rollback: {e}')
        
        if app.debug:
            # В режиме отладки показываем детали
            return f"<pre>{traceback.format_exc()}</pre>", 500
        else:
            # В production показываем общее сообщение
            return render_template('errors/500.html'), 500
    
    @app.errorhandler(Exception)
    def handle_exception(error):
        """Обработчик всех необработанных исключений."""
        import traceback
        app.logger.error('='*60)
        app.logger.error(f'Unhandled Exception: {type(error).__name__}')
        app.logger.error(f'Message: {str(error)}')
        app.logger.error('Traceback:')
        app.logger.error(traceback.format_exc())
        app.logger.error('='*60)
        
        # Откат транзакции БД при ошибке
        try:
            db.session.rollback()
        except Exception as e:
            app.logger.error(f'Error during rollback: {e}')
        
        # Если это HTTP exception, пропускаем
        from werkzeug.exceptions import HTTPException
        if isinstance(error, HTTPException):
            return error
        
        if app.debug:
            return f"<pre>{traceback.format_exc()}</pre>", 500
        else:
            return "An error occurred. Please try again later.", 500

    return app


