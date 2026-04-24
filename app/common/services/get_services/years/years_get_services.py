from app.extensions import db
from functools import lru_cache

from sqlalchemy import func

# Модели
from app.refdata.models.years.year_model import Year
from app.refdata.models.years.year_feature_model import YearFeature
from app.refdata.models.years.year_service_model import YearService

# Сервисы
from app.common.services.database_version_services import get_current_version
from app.common.services.get_services.years.year_feature_services import (
    get_year_feature_dict as get_year_feature_dict_service,
    get_year_feature_dict_for_version as get_year_feature_dict_for_version_service,
)
from config import Config


def get_year_list_full():
    """
    Полный список годов текущей версии БД.

    Не кэшируем результат: список ORM-объектов нельзя безопасно хранить в lru_cache —
    после завершения запроса сессия закрывается, и повторное обращение к атрибутам
    даёт DetachedInstanceError.
    """
    current_version = get_current_version()
    query = Year.query

    if current_version:
        query = query.filter(Year.database_version_id == current_version)

    return query.order_by(Year.number.asc()).all()


def get_current_year():
    """Получает текущий год."""
    current_version = get_current_version()
    
    # Получаем признак года "текущий (оценка)" для текущей версии
    current_year_feature = db.session.query(YearFeature).filter_by(
        name="текущий (оценка)",
        database_version_id=current_version
    ).first()
    
    if not current_year_feature:
        return None
    
    query = db.session.query(Year).filter_by(
        id_year_feature=current_year_feature.id,
        database_version_id=current_version
    )
    
    current_year_obj = query.first()
    current_year = current_year_obj.number - 1 if current_year_obj else None
    return current_year


@lru_cache(maxsize=64)
def _get_filter_start_year_for_version(version_id: int | None) -> int:
    """
    Возвращает стартовый год для фильтров как (YearService.year_sipr_start - 2)
    для указанной версии БД.

    Fallback: Config.START_YEAR.
    """
    if not version_id:
        return Config.START_YEAR

    # NOTE:
    # YearService должен быть 1 запись на версию, но в БД иногда встречаются дубликаты.
    # Чтобы корректно работать "в привязке к version_id" и не падать на дубликатах,
    # берем агрегат (одна строка) по текущей версии.
    year_sipr_start = (
        db.session.query(func.min(YearService.year_sipr_start))
        .filter(YearService.database_version_id == version_id)
        .scalar()
    )
    if year_sipr_start is None:
        return Config.START_YEAR

    try:
        return int(year_sipr_start) - 2
    except Exception:
        return Config.START_YEAR


def get_filter_start_year() -> int:
    """
    Возвращает стартовый год для фильтров текущей версии БД:
    year_start = year_sipr_start - 2 (из модели YearService).
    """
    return _get_filter_start_year_for_version(get_current_version())


@lru_cache(maxsize=64)
def _get_filter_end_year_for_version(version_id: int | None) -> int:
    """
    Возвращает конечный год для фильтров как YearService.year_sipr_end
    для указанной версии БД.

    Fallback: Config.END_YEAR.
    """
    if not version_id:
        return Config.END_YEAR

    year_sipr_end = (
        db.session.query(func.max(YearService.year_sipr_end))
        .filter(YearService.database_version_id == version_id)
        .scalar()
    )
    if year_sipr_end is None:
        return Config.END_YEAR

    try:
        return int(year_sipr_end)
    except Exception:
        return Config.END_YEAR


def get_filter_end_year() -> int:
    """
    Возвращает конечный год для фильтров текущей версии БД:
    year_end = year_sipr_end (из модели YearService).
    """
    return _get_filter_end_year_for_version(get_current_version())


@lru_cache(maxsize=64)
def _get_sipr_start_year_for_version(version_id: int | None) -> int:
    """
    Возвращает год начала СиПР (YearService.year_sipr_start) для указанной версии БД.
    Fallback: Config.START_YEAR_SIPR.
    """
    if not version_id:
        return Config.START_YEAR_SIPR

    value = (
        db.session.query(func.min(YearService.year_sipr_start))
        .filter(YearService.database_version_id == version_id)
        .scalar()
    )
    if value is None:
        return Config.START_YEAR_SIPR
    try:
        return int(value)
    except Exception:
        return Config.START_YEAR_SIPR


def get_sipr_start_year() -> int:
    """Возвращает год начала СиПР для текущей версии БД (из YearService)."""
    return _get_sipr_start_year_for_version(get_current_version())


@lru_cache(maxsize=64)
def _get_sipr_end_year_for_version(version_id: int | None) -> int:
    """
    Возвращает год конца СиПР (YearService.year_sipr_end) для указанной версии БД.
    Fallback: Config.END_YEAR_SIPR.
    """
    if not version_id:
        return Config.END_YEAR_SIPR

    value = (
        db.session.query(func.max(YearService.year_sipr_end))
        .filter(YearService.database_version_id == version_id)
        .scalar()
    )
    if value is None:
        return Config.END_YEAR_SIPR
    try:
        return int(value)
    except Exception:
        return Config.END_YEAR_SIPR


def get_sipr_end_year() -> int:
    """Возвращает год конца СиПР для текущей версии БД (из YearService)."""
    return _get_sipr_end_year_for_version(get_current_version())


def get_year_feature_dict():
    """Возвращает словарь {year_number: year_feature_name}."""
    return get_year_feature_dict_service()

def get_year_feature_dict_for_version(version_id: int | None):
    """Возвращает словарь {year_number: year_feature_name} для указанной версии."""
    return get_year_feature_dict_for_version_service(version_id)


def get_year_number_for_year_feature_name_current_version(feature_name: str) -> int | None:
    """
    Календарный год (Year.number) для признака года с заданным именем в текущей версии БД.
    Если записей несколько — берётся год с минимальным number.
    """
    current_version = get_current_version()
    if not current_version:
        return None
    yf = (
        db.session.query(YearFeature)
        .filter(
            YearFeature.name == feature_name,
            YearFeature.database_version_id == current_version,
        )
        .first()
    )
    if not yf:
        return None
    y = (
        db.session.query(Year)
        .filter(
            Year.id_year_feature == yf.id,
            Year.database_version_id == current_version,
        )
        .order_by(Year.number.asc())
        .first()
    )
    if y is None or y.number is None:
        return None
    return int(y.number)


def get_ges_tep_current_price_year_number() -> int | None:
    """
    Год для подписи «в ценах текущего года» на ТЭП ГЭС:
    сначала признак «текущий», иначе «текущий (оценка)» (как в справочнике годов).
    """
    n = get_year_number_for_year_feature_name_current_version("текущий")
    if n is not None:
        return n
    return get_year_number_for_year_feature_name_current_version("текущий (оценка)")
