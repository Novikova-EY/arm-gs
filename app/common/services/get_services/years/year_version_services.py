# -*- coding: utf-8 -*-
"""
Сервисы для работы с версиями годов.
"""

from app.extensions import db
from sqlalchemy import text
from flask import current_app
from config import SCHEMA_REFDATA

# Модели
from app.refdata.models.years.year_model import Year
from app.refdata.models.years.year_feature_model import YearFeature
from app.refdata.models.years.year_service_model import YearService
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


def copy_year_data_from_version(source_version_id, target_version_id, user, do_commit: bool = True):
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
        # ВАЖНО: не используем commit() внутри по умолчанию — вызывающий код может
        # собирать всю операцию создания версии в одну транзакцию.
        #
        # Также важно сохранить порядок соответствия old_id -> new_id:
        # используем CTE с ORDER BY old_id и вставляем в том же порядке.
        year_features_query = text(f"""
            WITH source_data AS (
                SELECT id AS old_id, name
                FROM {SCHEMA_REFDATA}.gs_year_features
                WHERE database_version_id = :source_version_id
                ORDER BY id
            )
            INSERT INTO {SCHEMA_REFDATA}.gs_year_features (name, database_version_id)
            SELECT name, :target_version_id
            FROM source_data
            ORDER BY old_id
            RETURNING id
        """)

        result = db.session.execute(
            year_features_query,
            {"source_version_id": source_version_id, "target_version_id": target_version_id},
        )
        new_feature_ids = [row[0] for row in result]
        db.session.flush()

        old_feature_ids_query = text(f"""
            SELECT id
            FROM {SCHEMA_REFDATA}.gs_year_features
            WHERE database_version_id = :source_version_id
            ORDER BY id
        """)

        result = db.session.execute(old_feature_ids_query, {"source_version_id": source_version_id})
        old_feature_ids = [row[0] for row in result]

        feature_id_mapping = dict(zip(old_feature_ids, new_feature_ids))

        # Копируем годы в любом случае: с маппингом id_year_feature (если есть) или без
        if feature_id_mapping:
            values_clause = ", ".join(
                f"(:old_id_{idx}, :new_id_{idx})"
                for idx, _ in enumerate(feature_id_mapping.items())
            )
            params = {
                "source_version_id": source_version_id,
                "target_version_id": target_version_id,
            }
            for idx, (old_id, new_id) in enumerate(feature_id_mapping.items()):
                params[f"old_id_{idx}"] = old_id
                params[f"new_id_{idx}"] = new_id

            # LEFT JOIN: годы с NULL id_year_feature тоже копируются (id_year_feature остаётся NULL)
            years_query = text(f"""
                WITH feature_map(old_id, new_id) AS (
                    VALUES {values_clause}
                ),
                source_years AS (
                    SELECT y.number, y.id_year_feature
                    FROM {SCHEMA_REFDATA}.gs_years y
                    WHERE y.database_version_id = :source_version_id
                ),
                ranked_years AS (
                    SELECT
                        sy.number,
                        sy.id_year_feature,
                        ROW_NUMBER() OVER (
                            PARTITION BY sy.number
                            ORDER BY sy.id_year_feature ASC NULLS LAST
                        ) AS rn
                    FROM source_years sy
                )
                INSERT INTO {SCHEMA_REFDATA}.gs_years (number, id_year_feature, database_version_id)
                SELECT
                    ry.number,
                    fm.new_id,
                    :target_version_id
                FROM ranked_years ry
                LEFT JOIN feature_map fm ON fm.old_id = ry.id_year_feature
                WHERE ry.rn = 1
                  AND NOT EXISTS (
                      SELECT 1
                      FROM {SCHEMA_REFDATA}.gs_years y_glob
                      WHERE y_glob.number = ry.number
                        AND y_glob.database_version_id = :target_version_id
                  )
            """)

            db.session.execute(years_query, params)
        else:
            # Исходная версия без year_features — копируем годы с id_year_feature=NULL
            # (старый id_year_feature указывал бы на чужую версию)
            years_no_features_query = text(f"""
                INSERT INTO {SCHEMA_REFDATA}.gs_years (number, id_year_feature, database_version_id)
                SELECT y.number, NULL, :target_version_id
                FROM {SCHEMA_REFDATA}.gs_years y
                WHERE y.database_version_id = :source_version_id
                  AND NOT EXISTS (
                      SELECT 1
                      FROM {SCHEMA_REFDATA}.gs_years y_glob
                      WHERE y_glob.number = y.number
                        AND y_glob.database_version_id = :target_version_id
                  )
            """)
            db.session.execute(
                years_no_features_query,
                {"source_version_id": source_version_id, "target_version_id": target_version_id},
            )

        # Копируем YearService (период СиПР) для указанной версии
        source_service = (
            YearService.query.filter_by(database_version_id=source_version_id).first()
        )
        if source_service:
            new_service = YearService(
                year_sipr_start=source_service.year_sipr_start,
                year_sipr_end=source_service.year_sipr_end,
                date_sipr_start=source_service.date_sipr_start,
                date_sipr_end=source_service.date_sipr_end,
                database_version_id=target_version_id,
            )
            db.session.add(new_service)

        if do_commit:
            db.session.commit()

        log_to_db(
            user,
            f"Успешно скопированы данные годов из версии {source_version_id} в версию {target_version_id}",
            f"Скопировано: {len(feature_id_mapping)} признаков годов, соответствующие годы и запись YearService (если была в исходной версии)",
            entity_type="database_version",
            entity_id=target_version_id,
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
        # Важно: пробрасываем исключение вверх, чтобы создание версии не продолжало
        # выполняться и не логировало "успех" после частичного отката.
        raise


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
