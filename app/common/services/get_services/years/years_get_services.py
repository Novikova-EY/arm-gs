from app.extensions import db
from functools import lru_cache

# Модели
from app.refdata.models.years.year_model import Year
from app.refdata.models.years.year_feature_model import YearFeature


@lru_cache(maxsize=1)
def get_year_list_full():
    """Получает полный годов."""
    return (
        Year.query
        .order_by(Year.number.asc())
        .all()
    )


def get_current_year():
    """Получает текущий год."""
    current_year_obj = db.session.query(Year).filter_by(id_year_feature=2).first()
    current_year = current_year_obj.number - 1 if current_year_obj else None
    return current_year


@lru_cache(maxsize=1)
def get_year_feature_dict():
    """ Возвращает словарь {year_number: year_feature_name}. """
    rows = (
        db.session.query(Year.number, YearFeature.name)
        .join(YearFeature, Year.id_year_feature == YearFeature.id)
        .all()
    )
    return {number: name for number, name in rows}