import os
import json
import datetime as dt
from pathlib import Path
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
    # #region agent log
    log_path = Path(__file__).resolve().parents[1] / ".cursor" / "debug.log"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "debug-session",
                "runId": "pre-fix",
                "hypothesisId": "B",
                "location": "app/__init__.py:20",
                "message": "Создание приложения - начало",
                "data": {"DEBUG_env": os.getenv("DEBUG"), "FLASK_ENV": os.getenv("FLASK_ENV")},
                "timestamp": int(dt.datetime.now().timestamp() * 1000)
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    # В production deb-пакет раскладывает статику в /usr/share/generation-app/static,
    # а старую папку /opt/generation-app/app/app/static может удалять postinst.
    # Чтобы /static/* продолжал работать даже без nginx-alias, используем shared static,
    # если каталог существует (иначе — дефолтный app/static для dev/Windows).
    shared_static_dir = os.getenv("GENERATION_APP_STATIC_DIR") or "/usr/share/generation-app/static"
    if Path(shared_static_dir).is_dir():
        app = Flask(__name__, static_folder=shared_static_dir, static_url_path="/static")
    else:
        app = Flask(__name__)
    app.config.from_object(Config) 
    app.secret_key = SECRET_KEY
    app.debug = app.config.get("DEBUG", False)
    # #region agent log
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "debug-session",
                "runId": "pre-fix",
                "hypothesisId": "B",
                "location": "app/__init__.py:24",
                "message": "DEBUG режим установлен",
                "data": {"app_debug": app.debug, "config_debug": app.config.get("DEBUG")},
                "timestamp": int(dt.datetime.now().timestamp() * 1000)
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
    # Обновление шаблонов без перезапуска (только в режиме разработки)
    app.config['TEMPLATES_AUTO_RELOAD'] = app.debug
    app.jinja_env.auto_reload = app.debug
    app.config['SQLALCHEMY_ECHO'] = False
    # Возвращаем JSON в читаемом виде и с порядком полей как задано
    app.config["JSON_AS_ASCII"] = False
    app.config["JSON_SORT_KEYS"] = False
    try:
        app.json.ensure_ascii = False  # Flask 2.2+
        app.json.sort_keys = False
    except Exception:
        pass
    # Уровень логирования зависит от режима DEBUG
    if app.debug:
        app.logger.setLevel(logging.DEBUG)
    else:
        app.logger.setLevel(logging.INFO)
    # #region agent log
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "debug-session",
                "runId": "pre-fix",
                "hypothesisId": "B",
                "location": "app/__init__.py:35",
                "message": "Настройки приложения установлены",
                "data": {
                    "templates_auto_reload": app.config.get('TEMPLATES_AUTO_RELOAD'),
                    "jinja_auto_reload": app.jinja_env.auto_reload,
                    "logger_level": app.logger.level
                },
                "timestamp": int(dt.datetime.now().timestamp() * 1000)
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion
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
        # Отдельный Redis‑клиент для сессий с более щадящими таймаутами и ретраями
        redis_client = redis.from_url(
            app.config.get("REDIS_URL", "redis://localhost:6379/0"),
            # Даём больше времени на установление соединения
            socket_connect_timeout=10,
            # Увеличенный таймаут на операции чтения/записи,
            # чтобы кратковременные задержки сети не приводили к ошибкам
            socket_timeout=30,
            # Автоматически повторяем операции при таймауте сокета
            retry_on_timeout=True,
            # Периодические health‑check'и, чтобы соединения не "застаивались"
            health_check_interval=30,
            # Держим соединения живыми на уровне TCP
            socket_keepalive=True,
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
        from app.refdata.services.history import refdata_history_listeners  # noqa: F401
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
        from app.refdata.models.organizations import Department, BusinessUnit  # noqa: F401
        from app.fuel.models import (
            fue_equipment_group_set_model,
            fue_equipment_group_set_station_model,
            external_mapping,
        )

        # Проброс мапперов
        db.configure_mappers()

        # Авто-инвалидация кэшей справочников при изменениях в refdata.
        # Цель: после CRUD/импорта в разделе /refdata кэш должен обновляться сразу,
        # чтобы формы/страницы не показывали устаревшие значения.
        if not getattr(db, "_refdata_cache_events_registered", False):
            def _clear_module_lru_caches(module) -> None:
                """Очищает все functools.lru_cache функции в модуле (best-effort)."""
                try:
                    for obj in module.__dict__.values():
                        if hasattr(obj, "cache_clear"):
                            try:
                                obj.cache_clear()
                            except Exception:
                                pass
                except Exception:
                    pass

            def _invalidate_refdata_caches(reason: str = "refdata_change") -> None:
                """Инвалидирует серверные кэши, используемые справочниками."""
                # Кэш choices (выпадающие списки) + небольшой кэш справочников для форм
                try:
                    from app.common.services.choices_cache_service import ChoicesCacheService
                    from app.common.services.cache_services import CacheService
                    ChoicesCacheService.clear_cache()
                    CacheService.clear_cache()
                except Exception:
                    pass

                # Кэши get_services (почти все справочники используют @lru_cache(maxsize=1))
                try:
                    from app.common.services.get_services.territories import (
                        regional_district_get_services,
                        federal_district_get_services,
                    )
                    _clear_module_lru_caches(regional_district_get_services)
                    _clear_module_lru_caches(federal_district_get_services)
                except Exception:
                    pass

                try:
                    from app.common.services.get_services.energy_systems import (
                        union_energy_system_get_services,
                        regional_energy_system_get_services,
                        energy_system_type_get_services,
                        energy_unit_get_services,
                        energy_zone_get_services,
                        energy_area_get_services,
                        synchronous_area_get_services,
                    )
                    _clear_module_lru_caches(union_energy_system_get_services)
                    _clear_module_lru_caches(regional_energy_system_get_services)
                    _clear_module_lru_caches(energy_system_type_get_services)
                    _clear_module_lru_caches(energy_unit_get_services)
                    _clear_module_lru_caches(energy_zone_get_services)
                    _clear_module_lru_caches(energy_area_get_services)
                    _clear_module_lru_caches(synchronous_area_get_services)
                except Exception:
                    pass

                try:
                    from app.common.services.get_services.fuels import (
                        fuel_get_services,
                        fuel_type_get_services,
                    )
                    _clear_module_lru_caches(fuel_get_services)
                    _clear_module_lru_caches(fuel_type_get_services)
                except Exception:
                    pass

                try:
                    from app.common.services.get_services.gen_companies import gen_company_get_services
                    _clear_module_lru_caches(gen_company_get_services)
                except Exception:
                    pass

                try:
                    from app.common.services.get_services.years import (
                        years_get_services,
                        year_feature_services,
                    )
                    _clear_module_lru_caches(years_get_services)
                    _clear_module_lru_caches(year_feature_services)
                except Exception:
                    pass

                # refdata_for_stations (технологии/типовые справочники для форм)
                try:
                    from app.common.services.get_services.refdata_for_stations.technologies import (
                        technology_type_get_services,
                        technology_availability_get_services,
                    )
                    _clear_module_lru_caches(technology_type_get_services)
                    _clear_module_lru_caches(technology_availability_get_services)
                except Exception:
                    pass

                # Справочники "для станций" тоже находятся в refdata и участвуют в choices
                try:
                    from app.common.services.get_services.stations import (
                        station_type_get_services,
                        station_group_get_services,
                        tes_type_get_services,
                        tes_machine_type_get_services,
                        pgu_tes_machine_type_get_services,
                        machine_type_get_services,
                        condition_type_get_services,
                    )
                    _clear_module_lru_caches(station_type_get_services)
                    _clear_module_lru_caches(station_group_get_services)
                    _clear_module_lru_caches(tes_type_get_services)
                    _clear_module_lru_caches(tes_machine_type_get_services)
                    _clear_module_lru_caches(pgu_tes_machine_type_get_services)
                    _clear_module_lru_caches(machine_type_get_services)
                    _clear_module_lru_caches(condition_type_get_services)
                except Exception:
                    pass

                try:
                    app.logger.info(f"[REFDATA_CACHE] invalidated ({reason})")
                except Exception:
                    pass

            def _mark_refdata_changed(session, _flush_context) -> None:
                """Помечает транзакцию как затрагивающую refdata (для не-/refdata запросов)."""
                changed = False
                try:
                    # new / deleted всегда считаем изменениями
                    for obj in list(getattr(session, "new", []) or []):
                        cls = getattr(obj, "__class__", None)
                        if cls and getattr(cls, "__module__", "").startswith("app.refdata.models"):
                            changed = True
                            break
                    if not changed:
                        for obj in list(getattr(session, "deleted", []) or []):
                            cls = getattr(obj, "__class__", None)
                            if cls and getattr(cls, "__module__", "").startswith("app.refdata.models"):
                                changed = True
                                break
                    # dirty проверяем на реальные изменения
                    if not changed:
                        for obj in list(getattr(session, "dirty", []) or []):
                            cls = getattr(obj, "__class__", None)
                            if not (cls and getattr(cls, "__module__", "").startswith("app.refdata.models")):
                                continue
                            try:
                                if session.is_modified(obj, include_collections=False):
                                    changed = True
                                    break
                            except Exception:
                                changed = True
                                break
                except Exception:
                    changed = False

                if changed:
                    session.info["_refdata_changed"] = True

            def _after_commit(session) -> None:
                """После коммита при изменениях справочников — очищаем refdata-кэши."""
                force = False
                try:
                    from flask import has_request_context, request
                    if has_request_context():
                        # В refdata много bulk-операций/импортов, которые не всегда попадают в session.dirty.
                        # Но на GET страницы часто пишутся логи (commit) — их нельзя превращать в инвалидацию кэша.
                        # Поэтому "force" делаем только для изменяющих запросов.
                        is_refdata = (request.path or "").startswith("/refdata")
                        is_mutation = (request.method or "").upper() in {"POST", "PUT", "PATCH", "DELETE"}
                        force = is_refdata and is_mutation
                except Exception:
                    force = False

                if force or session.info.pop("_refdata_changed", False):
                    _invalidate_refdata_caches(reason="commit:/refdata" if force else "commit:refdata_models")
                else:
                    # подчистим флаг на всякий случай
                    session.info.pop("_refdata_changed", None)

            def _after_rollback(session) -> None:
                session.info.pop("_refdata_changed", None)

            try:
                from sqlalchemy.orm import Session as _SASession
                event.listen(_SASession, "after_flush", _mark_refdata_changed)
                event.listen(_SASession, "after_commit", _after_commit)
                event.listen(_SASession, "after_rollback", _after_rollback)
                db._refdata_cache_events_registered = True
                app.logger.info("[REFDATA_CACHE] SQLAlchemy session listeners registered")
            except Exception as e:
                app.logger.warning(f"[REFDATA_CACHE] failed to register listeners: {e}")
        
        # Прогрев кэша станций и запуск периодического обновления (в фоновом режиме)
        # Пропускаем прогрев кэша при запуске миграций
        import sys
        skip_cache_warmup = (
            'db' in sys.argv or 
            'migrate' in sys.argv or
            'alembic' in sys.argv or
            os.getenv('SKIP_CACHE_WARMUP', 'false').lower() == 'true'
        )
        
        if not skip_cache_warmup:
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

    @app.template_filter("get_attr")
    def get_attr_filter(obj, attr):
        """Возвращает getattr(obj, attr, None) для динамического доступа к атрибутам в шаблонах."""
        return getattr(obj, attr, None)

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
    from app.fuel.routes import fuel_bp
    from app.generation.routes.station_changes import station_changes_bp
    from app.start.routes import start_bp
    from app.logs.routes import logs_bp
    from app.history.routes import history_bp

    app.register_blueprint(start_bp, url_prefix="/")
    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(refdata_bp, url_prefix="/refdata")
    app.register_blueprint(generation_bp, url_prefix="/generation")
    app.register_blueprint(station_bp, url_prefix="/generation/stations")
    app.register_blueprint(rational_structure_bp, url_prefix="/rational_structure")
    app.register_blueprint(station_changes_bp, url_prefix="/generation/station_changes")
    app.register_blueprint(fuel_bp, url_prefix="/fuel")
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(logs_bp, url_prefix="/log")
    app.register_blueprint(history_bp, url_prefix="/history")

    # Обработчик для Chrome DevTools (чтобы не логировать 404 ошибки)
    @app.route('/.well-known/appspecific/com.chrome.devtools.json')
    def chrome_devtools_config():
        """Обработчик для Chrome DevTools - возвращает пустой ответ."""
        return '', 204  # 204 No Content

    # Загрузка пользователя для Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        from app.auth.models.user_model import User
        # Используем современный API SQLAlchemy 2.x: Session.get вместо Query.get
        return db.session.get(User, int(user_id))
    
    # Error handlers для детального логирования
    @app.errorhandler(404)
    def not_found(error):
        """Логирование 404 для отладки (например, при загрузке из Excel)."""
        from flask import has_request_context
        if has_request_context():
            app.logger.warning(
                "404 Not Found: %s %s (Referer: %s)",
                request.method,
                request.url,
                request.referrer or "(none)",
            )
        return error

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
        from flask import has_request_context

        app.logger.error('='*60)
        app.logger.error(f'Unhandled Exception: {type(error).__name__}')
        app.logger.error(f'Message: {str(error)}')
        if has_request_context():
            app.logger.error(f'Request URL: {request.method} {request.url}')
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


