# -*- coding: utf-8 -*-
"""
Сервисы для управления текущим годом и годами СиПР.
"""

from app.extensions import db
from flask import current_app

# Модели
from app.refdata.models.years.year_model import Year
from app.refdata.models.years.year_feature_model import YearFeature
from app.refdata.models.years.year_service_model import YearService
from app.common.models.database_version_model import DatabaseVersion

# Сервисы
from app.logs.services.logging_service import log_to_db


def get_current_year_info(version_id):
    """
    Получает информацию о текущем годе для указанной версии БД.
    
    Args:
        version_id: ID версии БД
        
    Returns:
        dict: {
            'current_year': int или None,
            'sipr_start': int или None,
            'sipr_end': int или None
        }
    """
    try:
        # Получаем версию БД
        version = DatabaseVersion.query.get(version_id)
        if not version:
            # Нет версии БД – по ТЗ возвращаем нули по годам
            return {
                'current_year': 0,
                'sipr_start': 0,
                'sipr_end': 0,
                'date_sipr_start': None,
                'date_sipr_end': None
            }
        
        # Получаем признак года "текущий (оценка)" для указанной версии
        current_year_feature = db.session.query(YearFeature).filter_by(
            name="текущий (оценка)",
            database_version_id=version_id
        ).first()
        
        current_year = None
        if current_year_feature:
            current_year_obj = db.session.query(Year).filter_by(
                id_year_feature=current_year_feature.id,
                database_version_id=version_id
            ).first()
            if current_year_obj:
                current_year = current_year_obj.number
        
        # Получаем SIPR годы и даты из таблицы YearService
        year_service = db.session.query(YearService).filter_by(
            database_version_id=version_id
        ).first()
        
        sipr_start = year_service.year_sipr_start if year_service else None
        sipr_end = year_service.year_sipr_end if year_service else None
        date_sipr_start = year_service.date_sipr_start.isoformat() if (year_service and year_service.date_sipr_start) else None
        date_sipr_end = year_service.date_sipr_end.isoformat() if (year_service and year_service.date_sipr_end) else None

        # Если годы СиПР не заданы, но текущий год известен — подставляем дефолтные значения
        if current_year is not None and current_year != 0:
            if sipr_start is None:
                sipr_start = current_year + 1
            if sipr_end is None:
                sipr_end = current_year + 6
        
        # Если по каким‑то причинам данных по годам нет – вернем 0, как требуется
        return {
            'current_year': current_year if current_year is not None else 0,
            'sipr_start': sipr_start if sipr_start is not None else 0,
            'sipr_end': sipr_end if sipr_end is not None else 0,
            'date_sipr_start': date_sipr_start,
            'date_sipr_end': date_sipr_end
        }
    except Exception as e:
        current_app.logger.error(f"Ошибка получения информации о годах для версии {version_id}: {str(e)}")
        return {
            'current_year': 0,
            'sipr_start': 0,
            'sipr_end': 0,
            'date_sipr_start': None,
            'date_sipr_end': None
        }


def update_current_year(version_id, new_year, user):
    """
    Обновляет текущий год для указанной версии БД.
    
    Args:
        version_id: ID версии БД
        new_year: Новый текущий год
        user: Пользователь для логирования
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Проверяем, что версия существует
        version = DatabaseVersion.query.get(version_id)
        if not version:
            return False, "Версия БД не найдена"

        # Получаем признаки годов для указанной версии
        fact_feature = db.session.query(YearFeature).filter_by(
            name="факт",
            database_version_id=version_id,
        ).first()
        current_year_feature = db.session.query(YearFeature).filter_by(
            name="текущий (оценка)",
            database_version_id=version_id,
        ).first()
        plan_feature = db.session.query(YearFeature).filter_by(
            name="план",
            database_version_id=version_id,
        ).first()

        missing = []
        if not fact_feature:
            missing.append("факт")
        if not current_year_feature:
            missing.append("текущий (оценка)")
        if not plan_feature:
            missing.append("план")
        if missing:
            return False, f"Не найдены признаки года для данной версии: {', '.join(missing)}"

        # Находим или создаем год с новым номером (в рамках указанной версии БД)
        new_year_obj = db.session.query(Year).filter_by(
            number=new_year,
            database_version_id=version_id,
        ).first()
        if not new_year_obj:
            new_year_obj = Year(number=new_year, database_version_id=version_id)
            db.session.add(new_year_obj)
            db.session.flush()

        # Правило: меньше текущего -> факт, текущий -> текущий (оценка), больше -> план
        years = (
            db.session.query(Year)
            .filter(Year.database_version_id == version_id)
            .all()
        )
        for y in years:
            if y.number < new_year:
                y.id_year_feature = fact_feature.id
            elif y.number > new_year:
                y.id_year_feature = plan_feature.id
            else:
                y.id_year_feature = current_year_feature.id
        
        # Автоматически обновляем SIPR годы в таблице YearService
        year_service = db.session.query(YearService).filter_by(
            database_version_id=version_id
        ).first()
        
        if not year_service:
            # Создаем новую запись YearService
            year_service = YearService(
                database_version_id=version_id,
                year_sipr_start=new_year + 1,
                year_sipr_end=new_year + 6
            )
            db.session.add(year_service)
        else:
            # Обновляем существующую запись
            year_service.year_sipr_start = new_year + 1
            year_service.year_sipr_end = new_year + 6
        
        db.session.commit()

        # Сбрасываем кэши справочных get-сервисов, чтобы обновления признаков сразу отражались в UI
        try:
            from app.common.services.get_services.years.year_feature_services import (
                get_year_feature_dict_for_version,
            )
            from app.common.services.get_services.years.years_get_services import (
                get_year_list_full,
                _get_filter_start_year_for_version,
                _get_filter_end_year_for_version,
                _get_sipr_start_year_for_version,
                _get_sipr_end_year_for_version,
            )

            get_year_feature_dict_for_version.cache_clear()
            get_year_list_full.cache_clear()
            _get_filter_start_year_for_version.cache_clear()
            _get_filter_end_year_for_version.cache_clear()
            _get_sipr_start_year_for_version.cache_clear()
            _get_sipr_end_year_for_version.cache_clear()
        except Exception:
            # Кэш — оптимизация, не должен ломать основную операцию
            pass
        
        log_to_db(
            user,
            f"Обновлен текущий год для версии БД {version_id} на {new_year}",
            f"Признаки годов проставлены автоматически: <{new_year} -> факт, {new_year} -> текущий (оценка), >{new_year} -> план. "
            f"Установлены SIPR_START={new_year + 1}, SIPR_END={new_year + 6}",
            entity_type="database_version",
            entity_id=version_id
        )
        
        return True, "Текущий год успешно обновлен"
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Ошибка обновления текущего года для версии {version_id}: {str(e)}")
        log_to_db(
            user,
            f"Ошибка обновления текущего года для версии БД {version_id}",
            str(e),
            entity_type="database_version",
            entity_id=version_id
        )
        return False, f"Ошибка обновления текущего года: {str(e)}"


def update_sipr_years(version_id, sipr_start, sipr_end, user):
    """
    Обновляет годы СиПР для указанной версии БД.
    
    Args:
        version_id: ID версии БД
        sipr_start: Год начала СиПР
        sipr_end: Год конца СиПР
        user: Пользователь для логирования
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        # Проверяем, что версия существует
        version = DatabaseVersion.query.get(version_id)
        if not version:
            return False, "Версия БД не найдена"
        
        # Валидация
        if sipr_start >= sipr_end:
            return False, "Год начала СиПР должен быть меньше года конца"
        
        # Получаем или создаем запись YearService
        year_service = db.session.query(YearService).filter_by(
            database_version_id=version_id
        ).first()
        
        if not year_service:
            # Создаем новую запись YearService
            year_service = YearService(
                database_version_id=version_id,
                year_sipr_start=sipr_start,
                year_sipr_end=sipr_end
            )
            db.session.add(year_service)
        else:
            # Обновляем существующую запись
            year_service.year_sipr_start = sipr_start
            year_service.year_sipr_end = sipr_end
        
        db.session.commit()

        # Сбрасываем кэш вычисления стартового года для фильтров
        try:
            from app.common.services.get_services.years.years_get_services import (
                _get_filter_start_year_for_version,
                _get_filter_end_year_for_version,
                _get_sipr_start_year_for_version,
                _get_sipr_end_year_for_version,
            )
            _get_filter_start_year_for_version.cache_clear()
            _get_filter_end_year_for_version.cache_clear()
            _get_sipr_start_year_for_version.cache_clear()
            _get_sipr_end_year_for_version.cache_clear()
        except Exception:
            pass
        
        log_to_db(
            user,
            f"Обновлены годы СиПР для версии БД {version_id}",
            f"SIPR_START={sipr_start}, SIPR_END={sipr_end}",
            entity_type="database_version",
            entity_id=version_id
        )
        
        return True, "Годы СиПР успешно обновлены"
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Ошибка обновления годов СиПР для версии {version_id}: {str(e)}")
        log_to_db(
            user,
            f"Ошибка обновления годов СиПР для версии БД {version_id}",
            str(e),
            entity_type="database_version",
            entity_id=version_id
        )
        return False, f"Ошибка обновления годов СиПР: {str(e)}"


def update_sipr_dates(version_id, date_sipr_start, date_sipr_end, user):
    """
    Обновляет даты СиПР для указанной версии БД.
    
    Args:
        version_id: ID версии БД
        date_sipr_start: Дата начала СиПР (строка в формате YYYY-MM-DD или None)
        date_sipr_end: Дата конца СиПР (строка в формате YYYY-MM-DD или None)
        user: Пользователь для логирования
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        from datetime import datetime
        
        # Проверяем, что версия существует
        version = DatabaseVersion.query.get(version_id)
        if not version:
            return False, "Версия БД не найдена"
        
        # Преобразуем строки в даты, если они переданы
        start_date = None
        end_date = None
        
        if date_sipr_start:
            try:
                start_date = datetime.strptime(date_sipr_start, '%Y-%m-%d').date()
            except ValueError:
                return False, "Некорректный формат даты начала (ожидается YYYY-MM-DD)"
        
        if date_sipr_end:
            try:
                end_date = datetime.strptime(date_sipr_end, '%Y-%m-%d').date()
            except ValueError:
                return False, "Некорректный формат даты конца (ожидается YYYY-MM-DD)"
        
        # Валидация дат
        if start_date and end_date and start_date >= end_date:
            return False, "Дата начала СиПР должна быть меньше даты конца"
        
        # Получаем или создаем запись YearService
        year_service = db.session.query(YearService).filter_by(
            database_version_id=version_id
        ).first()
        
        if not year_service:
            # Создаем новую запись YearService
            year_service = YearService(
                database_version_id=version_id,
                date_sipr_start=start_date,
                date_sipr_end=end_date
            )
            db.session.add(year_service)
        else:
            # Обновляем существующую запись
            year_service.date_sipr_start = start_date
            year_service.date_sipr_end = end_date
        
        db.session.commit()
        
        log_to_db(
            user,
            f"Обновлены даты СиПР для версии БД {version_id}",
            f"DATE_SIPR_START={start_date}, DATE_SIPR_END={end_date}",
            entity_type="database_version",
            entity_id=version_id
        )
        
        return True, "Даты СиПР успешно обновлены"
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Ошибка обновления дат СиПР для версии {version_id}: {str(e)}")
        log_to_db(
            user,
            f"Ошибка обновления дат СиПР для версии БД {version_id}",
            str(e),
            entity_type="database_version",
            entity_id=version_id
        )
        return False, f"Ошибка обновления дат СиПР: {str(e)}"

