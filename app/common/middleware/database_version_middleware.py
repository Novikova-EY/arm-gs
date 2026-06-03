# -*- coding: utf-8 -*-
"""
Middleware для управления версиями базы данных.
Устанавливает текущую активную версию в контекст Flask для каждого запроса.
"""

from flask import g, session, current_app
from flask_login import current_user
from app.common.models.database_version_model import DatabaseVersion
from app.common.services.database_version_services import get_default_version
from app.extensions import db


def init_database_version_middleware(app):
    """
    Инициализирует middleware для управления версиями БД.
    
    Args:
        app: Flask приложение
    """
    
    @app.before_request
    def load_current_version():
        """
        Загружает текущую активную версию БД перед каждым запросом.
        Сохраняет ID активной версии в контекст Flask (g.current_db_version).
        """
        from flask import request
        from flask import current_app
        
        # Логируем только для основных страниц (не статических файлов)
        if not request.endpoint or not request.endpoint.startswith('static'):
            current_app.logger.debug(f"[VERSION_MIDDLEWARE] Запрос: {request.endpoint}, URL: {request.url}")
        
        # Проверяем, есть ли переопределенная версия в сессии пользователя
        if 'current_db_version' in session:
            session_version_id = session['current_db_version']
            # Проверяем, что версия из сессии все еще существует в БД
            if session_version_id is not None:
                version_exists = DatabaseVersion.query.filter_by(id=session_version_id).first()
                if not version_exists:
                    # Версия была удалена, очищаем сессию
                    current_app.logger.warning(
                        f"[VERSION_MIDDLEWARE] Версия {session_version_id} из сессии не найдена в БД, очищаем сессию"
                    )
                    session.pop('current_db_version', None)
                    session.modified = True
                else:
                    g.current_db_version = session_version_id
                    if not request.endpoint or not request.endpoint.startswith('static'):
                        current_app.logger.debug(
                            f"[VERSION_MIDDLEWARE] Используется версия из сессии: {g.current_db_version}"
                        )
                    return
            else:
                # Версия None в сессии - это валидное значение
                g.current_db_version = None
                if not request.endpoint or not request.endpoint.startswith('static'):
                    current_app.logger.debug("[VERSION_MIDDLEWARE] Используется версия None из сессии")
                return
        
        # Если нет, берем активную версию из БД
        active_version = DatabaseVersion.query.filter_by(is_active=True).first()
        if active_version:
            g.current_db_version = active_version.id
            if not request.endpoint or not request.endpoint.startswith('static'):
                current_app.logger.debug(f"[VERSION_MIDDLEWARE] Установлена активная версия: {active_version.id} (v{active_version.version_number})")
        else:
            # Если активной версии нет, используем версию по умолчанию
            default_version = get_default_version()
            if default_version:
                g.current_db_version = default_version.id
                if not request.endpoint or not request.endpoint.startswith('static'):
                    current_app.logger.debug(f"[VERSION_MIDDLEWARE] Установлена версия по умолчанию: {default_version.id} (v{default_version.version_number})")
            else:
                # Если версии по умолчанию нет, работаем со всеми данными (None)
                g.current_db_version = None
                if not request.endpoint or not request.endpoint.startswith('static'):
                    current_app.logger.debug(f"[VERSION_MIDDLEWARE] Версия по умолчанию не найдена, установлено: None")

        # Всегда синхронизируем последнюю версию с пользователем (если авторизован)
        _sync_user_last_version()


def _sync_user_last_version():
    """Сохраняет текущую версию БД в профиле пользователя, если нужно."""
    try:
        if not current_user or not current_user.is_authenticated:
            return

        current_version_id = getattr(g, 'current_db_version', None)
        if current_user.last_database_version_id == current_version_id:
            return

        current_user.last_database_version_id = current_version_id
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(
            f"[VERSION_MIDDLEWARE] Ошибка сохранения последней версии БД: {e}",
            exc_info=True,
        )


def get_current_version_id():
    """
    Получает ID текущей активной версии БД из контекста Flask.
    
    Returns:
        int or None: ID активной версии или None, если версия не установлена
    """
    return getattr(g, 'current_db_version', None)


def set_session_version(version_id):
    """
    Устанавливает версию БД для текущей сессии пользователя.
    
    Args:
        version_id: ID версии БД или None для сброса
    """
    try:
        # Проверяем, что версия существует в БД (если не None)
        if version_id is not None:
            version = DatabaseVersion.query.filter_by(id=version_id).first()
            if not version:
                current_app.logger.error(
                    f"[VERSION_MIDDLEWARE] Попытка установить несуществующую версию {version_id}"
                )
                raise ValueError(f"Версия БД с ID {version_id} не найдена")
        
        # Устанавливаем версию в сессии
        if version_id is None:
            session.pop('current_db_version', None)
            current_app.logger.info("[VERSION_MIDDLEWARE] Версия БД сброшена в сессии")
        else:
            session['current_db_version'] = version_id
            current_app.logger.info(
                f"[VERSION_MIDDLEWARE] Версия БД {version_id} установлена в сессии"
            )
        
        # ВАЖНО: Помечаем сессию как измененную, чтобы Flask сохранил изменения
        # Это критично для многопользовательской работы, чтобы версия не сбивалась
        session.modified = True
        session.permanent = True
        
        # Обновляем текущий контекст
        g.current_db_version = version_id

        # Очищаем все кэши: агрегации, отсортированные списки, позиции страниц
        # Иначе возможны данные от предыдущей версии БД
        try:
            from app.generation.services.station_services.aggregation_cache import clear_aggregation_cache
            clear_aggregation_cache()
        except Exception as e:
            current_app.logger.warning(
                f"[VERSION_MIDDLEWARE] Ошибка при очистке кэшей агрегации: {e}"
            )

        try:
            from app.common.services.get_services.years.years_get_services import (
                clear_planning_period_year_caches,
            )
            from app.generation.services.station_services.generation_year_filter_services import (
                GENERATION_YEARS_VERSION_SESSION_KEY,
                STATION_LIST_FILTERS_SESSION_KEY,
            )

            clear_planning_period_year_caches()
            session.pop(GENERATION_YEARS_VERSION_SESSION_KEY, None)
            saved_filters = session.get(STATION_LIST_FILTERS_SESSION_KEY)
            if isinstance(saved_filters, dict):
                for key in ("start_year", "end_year"):
                    saved_filters.pop(key, None)
                session[STATION_LIST_FILTERS_SESSION_KEY] = saved_filters
        except Exception as e:
            current_app.logger.warning(
                f"[VERSION_MIDDLEWARE] Ошибка при сбросе годов фильтров генерации: {e}"
            )

        # Дополнительная проверка: убеждаемся, что значение действительно сохранилось
        if version_id is not None and session.get('current_db_version') != version_id:
            current_app.logger.error(
                f"[VERSION_MIDDLEWARE] КРИТИЧЕСКАЯ ОШИБКА: версия не сохранилась в сессии! "
                f"Ожидалось: {version_id}, получено: {session.get('current_db_version')}"
            )
    except Exception as e:
        current_app.logger.error(
            f"[VERSION_MIDDLEWARE] Ошибка при установке версии в сессию: {e}",
            exc_info=True
        )
        raise

    # ВАЖНО: многие справочники/маппинги кэшируются через lru_cache(maxsize=1) без учета версии.
    # При смене версии в сессии нужно очистить эти кэши, иначе JS-фильтры получат маппинги от другой версии
    # (например, ues_to_rd_mapping с ключами не из текущей версии) и взаимные ограничения "перестают работать".
    try:
        from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
            get_union_energy_system_list_full,
            get_union_energy_system_list,
            get_union_energy_systems_map,
            get_ues_to_res_ids_map,
            get_res_to_ues_id_map,
            get_ues_to_est_id_map,
            get_ues_to_rd_ids_map,
            get_ues_to_fd_ids_map,
        )

        for fn in (
            get_union_energy_system_list_full,
            get_union_energy_system_list,
            get_union_energy_systems_map,
            get_ues_to_res_ids_map,
            get_res_to_ues_id_map,
            get_ues_to_est_id_map,
            get_ues_to_rd_ids_map,
            get_ues_to_fd_ids_map,
        ):
            if hasattr(fn, "cache_clear"):
                fn.cache_clear()
    except Exception as e:
        # не ломаем запрос из-за очистки кэша
        current_app.logger.error(f"[VERSION_MIDDLEWARE] Ошибка при очистке кэшей энергосистем: {e}")


