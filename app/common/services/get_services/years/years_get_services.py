from app.extensions import db
from functools import lru_cache

from sqlalchemy import func

# Модели
from app.refdata.models.years.year_model import Year
from app.refdata.models.years.year_feature_model import YearFeature
from app.refdata.models.years.year_service_model import YearService
from app.common.models.database_version_model import DatabaseVersion

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


def get_year_numbers_sorted_for_current_db_version() -> list[int]:
    """
    Все календарные годы (Year.number) из справочника Year для текущей версии БД,
    по возрастанию, без дубликатов.

    При отсутствии привязки к версии (get_current_version() is None) — все годы в таблице.
    """
    current_version = get_current_version()
    q = db.session.query(Year.number)
    if current_version is not None:
        q = q.filter(Year.database_version_id == current_version)
    return sorted({int(n) for (n,) in q.all() if n is not None})


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


def _planning_scheme_from_version_number(version_number: str | None) -> str | None:
    """
    Определяет период планирования по номеру версии БД (как на /refdata/).
    «СиПР» — период СиПР; «ГС» — генеральная схема.
    """
    name = (version_number or "").strip().upper()
    if not name:
        return None
    if "ГС" in name:
        return "gs"
    if "СИПР" in name:
        return "sipr"
    return None


def _year_service_sipr_bounds(version_id: int) -> tuple[int | None, int | None]:
    """Границы СиПР из YearService (агрегаты на случай дубликатов строк)."""
    year_sipr_start = (
        db.session.query(func.min(YearService.year_sipr_start))
        .filter(YearService.database_version_id == version_id)
        .scalar()
    )
    year_sipr_end = (
        db.session.query(func.max(YearService.year_sipr_end))
        .filter(YearService.database_version_id == version_id)
        .scalar()
    )
    return year_sipr_start, year_sipr_end


def _filter_start_year_from_sipr_start(sipr_start: int | None) -> int:
    """Стартовый год фильтров: на 2 года раньше начала СиПР (year_sipr_start - 2)."""
    if sipr_start is None:
        return Config.START_YEAR
    try:
        return int(sipr_start) - 2
    except Exception:
        return Config.START_YEAR


def _parse_year_range_from_version_text(version_number: str | None, description: str | None) -> tuple[int | None, int | None]:
    """Пытается извлечь диапазон лет из номера/описания версии (например «СиПР 2026-2031»)."""
    import re

    dash_class = r"-\u2010-\u2015\u2212"
    for raw in ((version_number or "").strip(), (description or "").strip()):
        if not raw:
            continue
        m = re.search(rf"(\d{{4}})\s*[{dash_class}]\s*(\d{{4}})", raw)
        if m:
            y1, y2 = int(m.group(1)), int(m.group(2))
            return min(y1, y2), max(y1, y2)
        years = re.findall(r"\d{4}", raw)
        if len(years) >= 2:
            y1, y2 = int(years[0]), int(years[1])
            return min(y1, y2), max(y1, y2)
    return None, None


@lru_cache(maxsize=64)
def _get_planning_period_years_for_version(version_id: int | None) -> tuple[int, int]:
    """
    Период для фильтров страниц генерации:
    - start_year = year_sipr_start - 2;
    - end_year: «СиПР» → year_sipr_end; «ГС» → END_YEAR_GENERAL_SCHEME (2042).
    """
    if not version_id:
        return Config.START_YEAR, Config.END_YEAR

    version = db.session.get(DatabaseVersion, version_id)
    version_number = version.version_number if version else None
    description = version.description if version else None

    sipr_start, sipr_end = _year_service_sipr_bounds(version_id)
    if sipr_start is None or sipr_end is None:
        from app.refdata.services.year_management_services import get_current_year_info

        info = get_current_year_info(version_id)
        if sipr_start is None:
            sipr_start = info.get("sipr_start") or None
        if sipr_end is None:
            sipr_end = info.get("sipr_end") or None
        if sipr_start in (None, 0):
            sipr_start = None
        if sipr_end in (None, 0):
            sipr_end = None

    effective_sipr_start = int(sipr_start) if sipr_start else None

    scheme = _planning_scheme_from_version_number(version_number)
    if scheme == "sipr":
        start = _filter_start_year_from_sipr_start(
            effective_sipr_start if effective_sipr_start is not None else Config.START_YEAR_SIPR
        )
        end = int(sipr_end) if sipr_end else Config.END_YEAR_SIPR
        return start, end

    if scheme == "gs":
        start = _filter_start_year_from_sipr_start(
            effective_sipr_start if effective_sipr_start is not None else Config.START_YEAR_SIPR
        )
        end = int(getattr(Config, "END_YEAR_GENERAL_SCHEME", 2042))
        return start, end

    parsed_start, parsed_end = _parse_year_range_from_version_text(version_number, description)
    if parsed_start is not None and parsed_end is not None:
        start = _filter_start_year_from_sipr_start(effective_sipr_start or parsed_start)
        return start, parsed_end

    if sipr_start is not None and sipr_end is not None:
        return _filter_start_year_from_sipr_start(effective_sipr_start), int(sipr_end)

    return Config.START_YEAR, Config.END_YEAR


@lru_cache(maxsize=64)
def _get_filter_start_year_for_version(version_id: int | None) -> int:
    """Стартовый год фильтров = year_sipr_start - 2 для текущей версии."""
    start, _ = _get_planning_period_years_for_version(version_id)
    return start


def get_filter_start_year() -> int:
    """Стартовый год фильтров для текущей версии БД (year_sipr_start - 2)."""
    return _get_filter_start_year_for_version(get_current_version())


@lru_cache(maxsize=64)
def _get_filter_end_year_for_version(version_id: int | None) -> int:
    """Конечный год фильтров = конец периода планирования текущей версии."""
    _, end = _get_planning_period_years_for_version(version_id)
    return end


def get_filter_end_year() -> int:
    """Конечный год фильтров для текущей версии БД (период планирования на /refdata/)."""
    return _get_filter_end_year_for_version(get_current_version())


def get_planning_period_years() -> tuple[int, int]:
    """Диапазон (start_year, end_year) периода планирования для текущей версии БД."""
    return _get_planning_period_years_for_version(get_current_version())


def clear_planning_period_year_caches() -> None:
    """Сброс lru_cache периодов планирования (смена версии / правка YearService)."""
    for fn in (
        _get_planning_period_years_for_version,
        _get_filter_start_year_for_version,
        _get_filter_end_year_for_version,
        _get_sipr_start_year_for_version,
        _get_sipr_end_year_for_version,
    ):
        if hasattr(fn, "cache_clear"):
            fn.cache_clear()


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
