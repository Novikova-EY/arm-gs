from app.extensions import db
from functools import lru_cache

# Модели
from app.refdata.models.years.year_model import Year
from app.refdata.models.years.year_feature_model import YearFeature

# Сервисы
from app.common.services.database_version_services import get_current_version
from app.common.services.get_services.years.year_feature_services import get_year_feature_dict as get_year_feature_dict_service


@lru_cache(maxsize=1)
def get_year_list_full():
    """Получает полный список годов."""
    current_version = get_current_version()
    query = Year.query
    
    if current_version:
        query = query.filter(Year.database_version_id == current_version)
    
    return (
        query
        .order_by(Year.number.asc())
        .all()
    )


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


@lru_cache(maxsize=1)
def get_year_feature_dict():
    """Возвращает словарь {year_number: year_feature_name}."""
    return get_year_feature_dict_service()