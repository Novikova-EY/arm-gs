# -*- coding: utf-8 -*-
"""
Сервисы для работы с версиями годов.
"""

from app.extensions import db
from sqlalchemy import text
from flask import current_app

# Модели
from app.refdata.models.years.year_model import Year
from app.refdata.models.years.year_feature_model import YearFeature
from app.common.models.database_version_model import DatabaseVersion

# Сервисы
from app.logs.services.logging_service import log_to_db


def create_year_version_data(target_version_id, target_year, user):
    """
    Создает данные годов для новой версии базы данных.
    
    Args:
        target_version_id: ID целевой версии
        target_year: Год, который будет текущим в новой версии
        user: Пользователь для логирования
    """
    log_to_db(
        user,
        f"Создание данных годов для версии {target_version_id} с текущим годом {target_year}",
        "",
        entity_type="database_version",
        entity_id=target_version_id
    )
    
    try:
        # Создаем признаки годов для новой версии
        year_features = [
            {"name": "Предыдущий", "id": 1},
            {"name": "Текущий", "id": 2},
            {"name": "Следующий", "id": 3},
            {"name": "Плановый", "id": 4}
        ]
        
        # Создаем YearFeature записи
        feature_id_mapping = {}
        for feature_data in year_features:
            year_feature = YearFeature(
                name=feature_data["name"],
                database_version_id=target_version_id
            )
            db.session.add(year_feature)
            db.session.flush()  # Получаем ID
            
            feature_id_mapping[feature_data["id"]] = year_feature.id
        
        # Создаем Year записи
        years_data = [
            {"number": target_year - 1, "feature_id": 1},  # Предыдущий
            {"number": target_year, "feature_id": 2},       # Текущий
            {"number": target_year + 1, "feature_id": 3},   # Следующий
            {"number": target_year + 2, "feature_id": 4}    # Плановый
        ]
        
        for year_data in years_data:
            year = Year(
                number=year_data["number"],
                id_year_feature=feature_id_mapping[year_data["feature_id"]],
                database_version_id=target_version_id
            )
            db.session.add(year)
        
        db.session.commit()
        
        log_to_db(
            user,
            f"Успешно созданы данные годов для версии {target_version_id}",
            f"Создано: {len(year_features)} признаков годов, {len(years_data)} записей годов",
            entity_type="database_version",
            entity_id=target_version_id
        )
        
        return True
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Ошибка создания данных годов для версии {target_version_id}: {str(e)}")
        log_to_db(
            user,
            f"Ошибка создания данных годов для версии {target_version_id}",
            str(e),
            entity_type="database_version",
            entity_id=target_version_id
        )
        return False


def copy_year_data_from_version(source_version_id, target_version_id, user):
    """
    Копирует данные годов из одной версии в другую.
    
    Args:
        source_version_id: ID версии-источника
        target_version_id: ID целевой версии
        user: Пользователь для логирования
    """
    log_to_db(
        user,
        f"Копирование данных годов из версии {source_version_id} в версию {target_version_id}",
        "",
        entity_type="database_version",
        entity_id=target_version_id
    )
    
    try:
        # Копируем YearFeature
        year_features_query = text("""
            INSERT INTO refdata.year_features (name, database_version_id)
            SELECT name, :target_version_id
            FROM refdata.year_features
            WHERE database_version_id = :source_version_id
            RETURNING id
        """)
        
        result = db.session.execute(
            year_features_query, 
            {"source_version_id": source_version_id, "target_version_id": target_version_id}
        )
        new_feature_ids = [row[0] for row in result]
        db.session.flush()
        
        # Получаем старые ID признаков годов
        old_feature_ids_query = text("""
            SELECT id FROM refdata.year_features
            WHERE database_version_id = :source_version_id
            ORDER BY id
        """)
        
        result = db.session.execute(old_feature_ids_query, {"source_version_id": source_version_id})
        old_feature_ids = [row[0] for row in result]
        
        # Создаем маппинг старых и новых ID
        feature_id_mapping = dict(zip(old_feature_ids, new_feature_ids))
        
        # Копируем Year с обновленными связями
        years_query = text("""
            INSERT INTO refdata.years (number, id_year_feature, database_version_id)
            SELECT 
                y.number,
                :new_feature_id,
                :target_version_id
            FROM refdata.years y
            JOIN refdata.year_features yf ON y.id_year_feature = yf.id
            WHERE y.database_version_id = :source_version_id
              AND yf.id = :old_feature_id
        """)
        
        for old_id, new_id in feature_id_mapping.items():
            db.session.execute(
                years_query,
                {
                    "source_version_id": source_version_id,
                    "target_version_id": target_version_id,
                    "old_feature_id": old_id,
                    "new_feature_id": new_id
                }
            )
        
        db.session.commit()
        
        log_to_db(
            user,
            f"Успешно скопированы данные годов из версии {source_version_id} в версию {target_version_id}",
            f"Скопировано: {len(feature_id_mapping)} признаков годов и соответствующих годов",
            entity_type="database_version",
            entity_id=target_version_id
        )
        
        return True
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Ошибка копирования данных годов: {str(e)}")
        log_to_db(
            user,
            f"Ошибка копирования данных годов из версии {source_version_id} в версию {target_version_id}",
            str(e),
            entity_type="database_version",
            entity_id=target_version_id
        )
        return False


def get_years_for_version(version_id):
    """
    Получает все годы для указанной версии.
    
    Args:
        version_id: ID версии
        
    Returns:
        List[Year]: Список годов
    """
    return (
        Year.query
        .filter(Year.database_version_id == version_id)
        .order_by(Year.number.asc())
        .all()
    )


def get_current_year_for_version(version_id):
    """
    Получает текущий год для указанной версии.
    
    Args:
        version_id: ID версии
        
    Returns:
        int: Номер текущего года или None
    """
    current_year_obj = (
        db.session.query(Year)
        .join(YearFeature, Year.id_year_feature == YearFeature.id)
        .filter(
            Year.database_version_id == version_id,
            YearFeature.name == "Текущий"
        )
        .first()
    )
    
    return current_year_obj.number if current_year_obj else None
