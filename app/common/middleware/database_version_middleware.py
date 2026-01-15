# -*- coding: utf-8 -*-
"""
Middleware для управления версиями базы данных.
Устанавливает текущую активную версию в контекст Flask для каждого запроса.
"""

from flask import g, session, current_app
from app.common.models.database_version_model import DatabaseVersion
from app.common.services.database_version_services import get_default_version


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
            print(f"[DEBUG] [VERSION_MIDDLEWARE] Запрос: {request.endpoint}, URL: {request.url}")
        
        # Проверяем, есть ли переопределенная версия в сессии пользователя
        if 'current_db_version' in session:
            g.current_db_version = session['current_db_version']
            if not request.endpoint or not request.endpoint.startswith('static'):
                current_app.logger.debug(f"[VERSION_MIDDLEWARE] Используется версия из сессии: {g.current_db_version}")
                print(f"[DEBUG] [VERSION_MIDDLEWARE] Используется версия из сессии: {g.current_db_version}")
            return
        
        # Если нет, берем активную версию из БД
        active_version = DatabaseVersion.query.filter_by(is_active=True).first()
        if active_version:
            g.current_db_version = active_version.id
            if not request.endpoint or not request.endpoint.startswith('static'):
                current_app.logger.debug(f"[VERSION_MIDDLEWARE] Установлена активная версия: {active_version.id} ({active_version.name})")
                print(f"[DEBUG] [VERSION_MIDDLEWARE] Установлена активная версия: {active_version.id} ({active_version.name})")
        else:
            # Если активной версии нет, используем версию по умолчанию
            default_version = get_default_version()
            if default_version:
                g.current_db_version = default_version.id
                if not request.endpoint or not request.endpoint.startswith('static'):
                    current_app.logger.debug(f"[VERSION_MIDDLEWARE] Установлена версия по умолчанию: {default_version.id} ({default_version.name})")
                    print(f"[DEBUG] [VERSION_MIDDLEWARE] Установлена версия по умолчанию: {default_version.id} ({default_version.name})")
            else:
                # Если версии по умолчанию нет, работаем со всеми данными (None)
                g.current_db_version = None
                if not request.endpoint or not request.endpoint.startswith('static'):
                    current_app.logger.debug(f"[VERSION_MIDDLEWARE] Версия по умолчанию не найдена, установлено: None")
                    print(f"[DEBUG] [VERSION_MIDDLEWARE] Версия по умолчанию не найдена, установлено: None")


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
    if version_id is None:
        session.pop('current_db_version', None)
    else:
        session['current_db_version'] = version_id
    
    # Обновляем текущий контекст
    g.current_db_version = version_id

    # ВАЖНО: многие справочники/маппинги кэшируются через lru_cache(maxsize=1) без учёта версии.
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


