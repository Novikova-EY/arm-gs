# -*- coding: utf-8 -*-
"""Сервисный модуль: Версии базы данных."""

from app.extensions import db
from sqlalchemy import or_, text
import re
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 
from config import SCHEMA_FUEL, SCHEMA_GENERATION, SCHEMA_REFDATA
import os
from datetime import datetime
from flask import current_app, g

# Модели
from app.common.models.database_version_model import DatabaseVersion

# Сервисы
from app.common.services.help_services import (
    _dash,
    _clean_name,
)
from app.common.services.tranzaction_services import (
    _commit_with_retry,
    no_autoflush,
    quick_fix_seq,
)
from app.common.services.get_services.years.year_version_services import (
    create_year_version_data,
    copy_year_data_from_version,
)
from app.refdata.models.years.year_service_model import YearService
from typing import Optional

# Логирование
from app.logs.services.logging_service import log_to_db
from app.logs.models.log_model import Log


def _is_in_failed_sql_transaction(exc: Exception) -> bool:
    """Проверяет, является ли исключение InFailedSqlTransaction (25P02) PostgreSQL."""
    while exc:
        if getattr(exc, "pgcode", None) == "25P02":
            return True
        if "InFailedSqlTransaction" in type(exc).__name__ or "25P02" in str(exc):
            return True
        exc = getattr(exc, "__cause__", None) or getattr(exc, "orig", None)
    return False


def version_query(
        version_filter=None, 
        sort_by="version_number", 
        sort_dir="desc"):
    """ Базовый запрос для выборки версий с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id", "version_number", "created_at", "updated_at"}
    sort_by = sort_by if sort_by in allowed_sort_by else "version_number"

    sort_dir = (sort_dir or "desc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Базовый запрос с загрузкой родительской версии
    query = DatabaseVersion.query.options(
        joinedload(DatabaseVersion.parent_version)
    ).filter(DatabaseVersion.id.isnot(None), DatabaseVersion.id > 0)

    # Фильтрация
    if version_filter:
        query = query.filter(
            or_(
                DatabaseVersion.version_number.ilike(f"%{version_filter}%"),
                DatabaseVersion.description.ilike(f"%{version_filter}%")
            )
        )

    # Сортировка
    if sort_by == "version_number":
        sort_col = DatabaseVersion.version_number
    elif sort_by == "created_at":
        sort_col = DatabaseVersion.created_at
    elif sort_by == "updated_at":
        sort_col = DatabaseVersion.updated_at
    elif sort_by == "id":
        sort_col = DatabaseVersion.id
    else:
        sort_col = DatabaseVersion.version_number

    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    return query


@no_autoflush
def get_version_list(
    page, 
    per_page, 
    version_filter=None, 
    sort_by="version_number", 
    sort_dir="desc"):
    """ Получает список версий с пагинацией, фильтрацией и сортировкой. """
    
    # Базовый запрос
    query = version_query(
        version_filter=version_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_version_service(data, user):
    """ Обновление данных по версиям """

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []
    
    log_to_db(
        user, 
        "Получены данные для обновления списка версий БД", 
        f"{data}",
        entity_type="database_version")
    
    def _validate_version_number(raw_value):
        version_number = (raw_value or "").strip()
        if not version_number:
            raise ValueError("Поле «Номер версии» обязательно.")
        if len(version_number) > 30:
            raise ValueError("Длина номера версии не должна превышать 30 символов.")
        if not re.fullmatch(r"[A-Za-zА-Яа-я0-9 ()\-]+", version_number):
            raise ValueError("Номер версии должен содержать только буквы, цифры, пробелы, дефисы и круглые скобки.")
        return version_number

    # Проверки на валидность данных
    with db.session.no_autoflush:
        for record in data:
            version_id = record.get("version_id")
            version_number = _validate_version_number(record.get("version_number"))
            description = (record.get("description") or "").strip()

            obj = db.session.get(DatabaseVersion, version_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{version_id}» не найдена.", 
                    entity_type="database_version", 
                    entity_id=version_id)
                raise ValueError(f"Запись с ID «{version_id}» не найдена.")

            # Проверка уникальности version_number
            if version_number != obj.version_number:
                q = (DatabaseVersion.query
                     .filter(DatabaseVersion.version_number == version_number,
                             DatabaseVersion.id != version_id))
                if q.first():
                    raise ValueError(f"Версия с номером «{version_number}» уже существует.")

            changes = {}

            if version_number != obj.version_number:
                changes["Номер версии"] = f"{obj.version_number} → {version_number}"
                obj.version_number = version_number

            if description != (obj.description or ""):
                changes["Описание"] = f"{_dash(obj.description)} → {description}"
                obj.description = description

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    f"Обновлена версия: {version_number}",
                    f"Изменения = {changes}", 
                    entity_type="database_version", 
                    entity_id=version_id)
                updated_ids.append(version_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по версиям БД", 
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})", 
                entity_type="database_version")
        else:
            log_to_db(
                user, 
                "Изменений по версиям БД не обнаружено", 
                "", 
                entity_type="database_version")
            
        return updated_ids
    
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения версий БД (уникальность/целостность)", 
            str(e), 
            entity_type="database_version")
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Неизвестная ошибка при сохранении версий БД", 
            str(e), 
            entity_type="database_version")
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_version_service(data, user):
    """Создание новой записи: версия БД"""
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    created_ids = []
    parent_version_ids = []  # Список parent_version_id для копирования
    refdata_source_version_ids = []  # Список версий, из которых копируем только справочники
    extend_years_list = []  # Список лет продления (только для сценария parent_version_id)
    
    def _validate_version_number(raw_value):
        version_number = (raw_value or "").strip()
        if not version_number:
            raise ValueError("Поле «Номер версии» обязательно.")
        if len(version_number) > 30:
            raise ValueError("Длина номера версии не должна превышать 30 символов.")
        if not re.fullmatch(r"[A-Za-zА-Яа-я0-9 ()\-]+", version_number):
            raise ValueError("Номер версии должен содержать только буквы, цифры, пробелы, дефисы и круглые скобки.")
        return version_number

    def _do_insert():
        with db.session.no_autoflush:
            for record in data:
                version_number = _validate_version_number(record.get("version_number"))
                description = (record.get("description") or "").strip()
                parent_version_id = record.get("parent_version_id")
                refdata_source_version_id = record.get("refdata_source_version_id")
                extend_years = record.get("extend_years")

                dup_number = (DatabaseVersion.query
                              .filter(DatabaseVersion.version_number == version_number)
                              .with_for_update().first())
                if dup_number:
                    raise ValueError(f"Версия с номером «{version_number}» уже существует.")

                if parent_version_id and refdata_source_version_id:
                    raise ValueError("Нельзя одновременно копировать полную версию и только справочники.")

                if refdata_source_version_id in (None, '', 'None', 'none'):
                    refdata_source_version_id = None
                elif not isinstance(refdata_source_version_id, int):
                    try:
                        refdata_source_version_id = int(refdata_source_version_id)
                    except (TypeError, ValueError) as exc:
                        raise ValueError("Некорректный идентификатор версии для копирования справочников.") from exc

                obj = DatabaseVersion(
                    version_number=version_number,
                    description=description if description else None,
                    parent_version_id=parent_version_id if parent_version_id else None
                )
                obj.created_by = user
                db.session.add(obj)
                db.session.flush()
                
                created_ids.append(obj.id)
                parent_version_ids.append(parent_version_id)
                refdata_source_version_ids.append(refdata_source_version_id)

                # Нормализуем extend_years в int (или None)
                if extend_years in (None, "", "None", "none"):
                    extend_years_norm = None
                else:
                    try:
                        extend_years_norm = int(extend_years)
                    except (TypeError, ValueError) as exc:
                        raise ValueError("Некорректное значение поля «Продлить период (лет)».") from exc
                extend_years_list.append(extend_years_norm)

                log_to_db(
                    user, 
                    "Создана версия БД", 
                    f"Номер: {version_number}, ID: {obj.id}, Родительская версия: {parent_version_id or 'Нет'}",
                    entity_type="database_version", 
                    entity_id=obj.id)

    try:
        _do_insert()
        # НЕ делаем commit здесь! Сначала копируем данные, потом commit всей операции
        
        # Копирование данных, если указана родительская версия
        for idx, new_version_id in enumerate(created_ids):
            parent_id = parent_version_ids[idx]
            refdata_source_id = refdata_source_version_ids[idx]
            extend_years = extend_years_list[idx] if idx < len(extend_years_list) else None
            if parent_id:
                try:
                    # Копируем данные годов первыми — до массового копирования справочников.
                    # Если _copy_version_data_staged падает на одной из таблиц (несмотря на SAVEPOINT),
                    # транзакция может оказаться в состоянии aborted, и последующие запросы
                    # получают InFailedSqlTransaction. Копирование year_features до этого устраняет проблему.
                    copy_year_data_from_version(parent_id, new_version_id, user, do_commit=False)
                    _copy_version_data_staged(parent_id, new_version_id, user, do_commit=False)

                    # При необходимости — продлеваем период и размножаем данные последнего года на новые годы
                    if extend_years is not None and extend_years > 0:
                        extend_version_period_by_copying_last_year(
                            source_version_id=parent_id,
                            target_version_id=new_version_id,
                            years_to_extend=extend_years,
                            user=user,
                            do_commit=False,
                        )
                except Exception as e:
                    log_to_db(
                        user,
                        f"Ошибка копирования данных из версии {parent_id} в версию {new_version_id}",
                        str(e),
                        entity_type="database_version",
                        entity_id=new_version_id
                    )
                    # Откатываем всю операцию при ошибке копирования
                    db.session.rollback()
                    raise ValueError(f"Ошибка копирования данных: {e}") from e
            elif refdata_source_id:
                try:
                    copy_year_data_from_version(refdata_source_id, new_version_id, user, do_commit=False)
                    _copy_version_data_staged(
                        refdata_source_id,
                        new_version_id,
                        user,
                        do_commit=False,
                        copy_mode="refdata_only"
                    )
                except Exception as e:
                    log_to_db(
                        user,
                        f"Ошибка копирования справочников из версии {refdata_source_id} в версию {new_version_id}",
                        str(e),
                        entity_type="database_version",
                        entity_id=new_version_id
                    )
                    db.session.rollback()
                    raise ValueError(f"Ошибка копирования справочников: {e}") from e
            else:
                # Если нет родительской версии, создаем базовые данные годов
                # Получаем текущий год из названия версии или используем текущий год системы
                target_year = 2023  # По умолчанию
                if "2025" in str(data[0].get("name", "")):
                    target_year = 2025
                elif "2024" in str(data[0].get("name", "")):
                    target_year = 2024
                
                if not create_year_version_data(new_version_id, target_year, user):
                    db.session.rollback()
                    raise ValueError(
                        "Не удалось создать базовые данные годов для пустой версии. "
                        "Проверьте логи."
                    )
        
        # Исторический снимок территорий для каждой созданной версии (в рамках общей транзакции)
        from app.refdata.services.history.refdata_history_services import (
            snapshot_energy_systems_for_version,
            snapshot_fuels_for_version,
            snapshot_station_machine_types_for_version,
            snapshot_territories_for_version,
        )
        snapshot_stats = {}
        for idx, new_version_id in enumerate(created_ids):
            parent_id = parent_version_ids[idx]
            refdata_source_id = refdata_source_version_ids[idx]
            if not parent_id and not refdata_source_id:
                # Пустая версия: справочники не копируются, снимки не создаем.
                continue
            snapshot_stats[new_version_id] = {}
            snapshot_source_version_id = refdata_source_id if refdata_source_id else None
            snapshot_stats[new_version_id]["territories"] = snapshot_territories_for_version(
                database_version_id=new_version_id,
                user=user,
                do_commit=False,
                source_version_id=snapshot_source_version_id,
            )
            snapshot_stats[new_version_id]["energy_systems"] = snapshot_energy_systems_for_version(
                database_version_id=new_version_id,
                user=user,
                do_commit=False,
                source_version_id=snapshot_source_version_id,
            )
            snapshot_stats[new_version_id]["station_machine_types"] = snapshot_station_machine_types_for_version(
                database_version_id=new_version_id,
                user=user,
                do_commit=False,
                source_version_id=snapshot_source_version_id,
            )
            snapshot_stats[new_version_id]["fuels"] = snapshot_fuels_for_version(
                database_version_id=new_version_id,
                user=user,
                do_commit=False,
                source_version_id=snapshot_source_version_id,
            )

        # Коммитим ВСЁ разом: и создание версии, и копирование данных
        _commit_with_retry()
        
        # Теперь логируем результаты копирования (после успешного commit)
        for idx, new_version_id in enumerate(created_ids):
            parent_id = parent_version_ids[idx]
            refdata_source_id = refdata_source_version_ids[idx]
            if parent_id:
                log_to_db(
                    user,
                    "Копирование данных версии завершено",
                    f"Из версии {parent_id} в версию {new_version_id}",
                    entity_type="database_version",
                    entity_id=new_version_id
                )
            elif refdata_source_id:
                log_to_db(
                    user,
                    "Справочники скопированы",
                    f"Из версии {refdata_source_id} в версию {new_version_id}",
                    entity_type="database_version",
                    entity_id=new_version_id
                )
            if new_version_id in snapshot_stats:
                log_to_db(
                    user,
                    "Исторические снимки справочников созданы",
                    f"{snapshot_stats[new_version_id]}",
                    entity_type="database_version",
                    entity_id=new_version_id,
                )
        
        return created_ids[0] if len(created_ids) == 1 else created_ids

    except IntegrityError:
        db.session.rollback()
        created_ids.clear()
        parent_version_ids.clear()
        refdata_source_version_ids.clear()
        extend_years_list.clear()
        # После миграции e0f1a2b3c4d5 физическая таблица может называться
        # gs_sys_database_versions, а legacy-имя gs_database_versions может быть VIEW.
        # Для выравнивания sequence выбираем именно физическую таблицу.
        version_table_for_seq = "gs_database_versions"
        try:
            new_table_exists = bool(
                db.session.execute(
                    text("SELECT to_regclass(:tbl) IS NOT NULL"),
                    {"tbl": f"{SCHEMA_REFDATA}.gs_sys_database_versions"},
                ).scalar()
            )
            if new_table_exists:
                version_table_for_seq = "gs_sys_database_versions"
        except Exception:
            version_table_for_seq = "gs_database_versions"

        quick_fix_seq(SCHEMA_REFDATA, version_table_for_seq)
        _do_insert()
        
        # Копирование данных после retry
        for idx, new_version_id in enumerate(created_ids):
            parent_id = parent_version_ids[idx]
            refdata_source_id = refdata_source_version_ids[idx]
            extend_years = extend_years_list[idx] if idx < len(extend_years_list) else None
            if parent_id:
                try:
                    copy_year_data_from_version(parent_id, new_version_id, user, do_commit=False)
                    _copy_version_data_staged(parent_id, new_version_id, user, do_commit=False)

                    if extend_years is not None and extend_years > 0:
                        extend_version_period_by_copying_last_year(
                            source_version_id=parent_id,
                            target_version_id=new_version_id,
                            years_to_extend=extend_years,
                            user=user,
                            do_commit=False,
                        )
                except Exception as e:
                    log_to_db(
                        user,
                        f"Ошибка копирования данных из версии {parent_id} в версию {new_version_id}",
                        str(e),
                        entity_type="database_version",
                        entity_id=new_version_id
                    )
                    db.session.rollback()
                    raise ValueError(f"Ошибка копирования данных: {e}") from e
            elif refdata_source_id:
                try:
                    copy_year_data_from_version(refdata_source_id, new_version_id, user, do_commit=False)
                    _copy_version_data_staged(
                        refdata_source_id,
                        new_version_id,
                        user,
                        do_commit=False,
                        copy_mode="refdata_only"
                    )
                except Exception as e:
                    log_to_db(
                        user,
                        f"Ошибка копирования справочников из версии {refdata_source_id} в версию {new_version_id}",
                        str(e),
                        entity_type="database_version",
                        entity_id=new_version_id
                    )
                    db.session.rollback()
                    raise ValueError(f"Ошибка копирования справочников: {e}") from e
            else:
                # Если нет родительской версии, создаем базовые данные годов
                target_year = 2023  # По умолчанию
                if "2025" in str(data[0].get("name", "")):
                    target_year = 2025
                elif "2024" in str(data[0].get("name", "")):
                    target_year = 2024
                
                if not create_year_version_data(new_version_id, target_year, user):
                    db.session.rollback()
                    raise ValueError(
                        "Не удалось создать базовые данные годов для пустой версии. "
                        "Проверьте логи."
                    )
        
        # Исторический снимок территорий для каждой созданной версии (в рамках общей транзакции)
        from app.refdata.services.history.refdata_history_services import (
            snapshot_energy_systems_for_version,
            snapshot_fuels_for_version,
            snapshot_station_machine_types_for_version,
            snapshot_territories_for_version,
        )
        snapshot_stats = {}
        for idx, new_version_id in enumerate(created_ids):
            parent_id = parent_version_ids[idx]
            refdata_source_id = refdata_source_version_ids[idx]
            if not parent_id and not refdata_source_id:
                # Пустая версия: справочники не копируются, снимки не создаем.
                continue
            snapshot_stats[new_version_id] = {}
            snapshot_source_version_id = refdata_source_id if refdata_source_id else None
            snapshot_stats[new_version_id]["territories"] = snapshot_territories_for_version(
                database_version_id=new_version_id,
                user=user,
                do_commit=False,
                source_version_id=snapshot_source_version_id,
            )
            snapshot_stats[new_version_id]["energy_systems"] = snapshot_energy_systems_for_version(
                database_version_id=new_version_id,
                user=user,
                do_commit=False,
                source_version_id=snapshot_source_version_id,
            )
            snapshot_stats[new_version_id]["station_machine_types"] = snapshot_station_machine_types_for_version(
                database_version_id=new_version_id,
                user=user,
                do_commit=False,
                source_version_id=snapshot_source_version_id,
            )
            snapshot_stats[new_version_id]["fuels"] = snapshot_fuels_for_version(
                database_version_id=new_version_id,
                user=user,
                do_commit=False,
                source_version_id=snapshot_source_version_id,
            )

        # Коммитим все разом после retry
        _commit_with_retry()
        
        # Логируем результаты копирования после успешного commit
        for idx, new_version_id in enumerate(created_ids):
            parent_id = parent_version_ids[idx]
            refdata_source_id = refdata_source_version_ids[idx]
            if parent_id:
                log_to_db(
                    user,
                    "Копирование данных версии завершено",
                    f"Из версии {parent_id} в версию {new_version_id}",
                    entity_type="database_version",
                    entity_id=new_version_id
                )
            elif refdata_source_id:
                log_to_db(
                    user,
                    "Справочники скопированы",
                    f"Из версии {refdata_source_id} в версию {new_version_id}",
                    entity_type="database_version",
                    entity_id=new_version_id
                )
            if new_version_id in snapshot_stats:
                log_to_db(
                    user,
                    "Исторические снимки справочников созданы",
                    f"{snapshot_stats[new_version_id]}",
                    entity_type="database_version",
                    entity_id=new_version_id,
                )
        
        return created_ids[0] if len(created_ids) == 1 else created_ids
    except Exception as e:
        db.session.rollback()
        err_msg = str(e)
        # InFailedSqlTransaction (25P02) — симптом: транзакция уже прервана более ранней ошибкой
        if _is_in_failed_sql_transaction(e):
            log_to_db(
                user,
                "Ошибка сохранения новой версии БД (транзакция прервана ранее)",
                f"{err_msg}. Проверьте логи — первая ошибка могла возникнуть при копировании таблиц.",
                entity_type="database_version")
            raise ValueError(
                f"Ошибка сохранения новой версии БД: транзакция прервана на предыдущем шаге. "
                f"Исходная ошибка: {err_msg}. Проверьте логи и целостность данных версии-источника."
            ) from e
        log_to_db(
            user, 
            "Ошибка сохранения новой версии БД", 
            err_msg, 
            entity_type="database_version")
        raise ValueError(f"Ошибка сохранения новой версии БД: {e}") from e


def _get_sipr_end_year(version_id: int) -> Optional[int]:
    """
    Возвращает год конца СиПР (year_sipr_end) для версии, если он задан.
    """
    try:
        ys = YearService.query.filter_by(database_version_id=version_id).first()
        if ys and ys.year_sipr_end:
            return int(ys.year_sipr_end)
    except Exception:
        return None
    return None


def _get_max_generation_data_year(version_id: int) -> Optional[int]:
    """
    Фоллбэк: пытается определить "последний год с данными" по годовым таблицам generation-схемы.
    Используется, если YearService.year_sipr_end отсутствует.
    """
    q = text(f"""
        SELECT GREATEST(
            COALESCE((SELECT MAX(year_number) FROM {SCHEMA_GENERATION}.gs_gen_station_powers     WHERE database_version_id = :vid), 0),
            COALESCE((SELECT MAX(year_number) FROM {SCHEMA_GENERATION}.gs_gen_machine_powers     WHERE database_version_id = :vid), 0),
            COALESCE((SELECT MAX(year_number) FROM {SCHEMA_GENERATION}.gs_gen_pgu_machine_powers WHERE database_version_id = :vid), 0),
            COALESCE((SELECT MAX(year_number) FROM {SCHEMA_GENERATION}.gs_gen_machine_fuels      WHERE database_version_id = :vid), 0),
            COALESCE((SELECT MAX(year_number) FROM {SCHEMA_GENERATION}.gs_gen_machine_tes_types  WHERE database_version_id = :vid), 0),
            COALESCE((SELECT MAX(year_number) FROM {SCHEMA_GENERATION}.gs_gen_machine_names     WHERE database_version_id = :vid), 0)
        ) AS max_year
    """)
    try:
        res = db.session.execute(q, {"vid": version_id}).scalar()
        max_year = int(res) if res else 0
        return max_year or None
    except Exception:
        return None


def extend_version_period_by_copying_last_year(
    source_version_id: int,
    target_version_id: int,
    years_to_extend: int,
    user: str,
    do_commit: bool = True,
) -> None:
    """
    Продлевает период в целевой версии на N лет и заполняет новые годы
    копией данных последнего года исходной версии (мощности/топливо/тип ТЭС).

    Примечание: функция рассчитана на сценарий "создать версию на основе существующей".
    Предполагается, что исходные данные уже скопированы в target_version_id.
    """
    try:
        years_to_extend = int(years_to_extend)
    except (TypeError, ValueError) as exc:
        raise ValueError("Некорректное значение количества лет для продления.") from exc

    if years_to_extend < 0:
        raise ValueError("Количество лет для продления не может быть отрицательным.")
    if years_to_extend == 0:
        return

    base_end_year = _get_sipr_end_year(source_version_id) or _get_max_generation_data_year(source_version_id)
    if not base_end_year:
        raise ValueError("Не удалось определить последний год исходной версии (year_sipr_end/max(year_number)).")

    new_end_year = base_end_year + years_to_extend

    log_to_db(
        user,
        "Продление периода версии и копирование данных последнего года",
        f"source_version_id={source_version_id}, target_version_id={target_version_id}, "
        f"base_end_year={base_end_year}, new_end_year={new_end_year}",
        entity_type="database_version",
        entity_id=target_version_id,
    )

    # 1) Обновляем YearService в целевой версии (если нет — создаем)
    target_service = (
        YearService.query
        .filter_by(database_version_id=target_version_id)
        .with_for_update()
        .first()
    )
    if not target_service:
        target_service = YearService(database_version_id=target_version_id)
        db.session.add(target_service)

    target_service.year_sipr_end = new_end_year
    db.session.flush()

    # 2) Гарантируем наличие записей годов (gs_sys_years) для новых лет (чтобы не ломались FK по year_number)
    ensure_year_sql = text(f"""
        INSERT INTO {SCHEMA_REFDATA}.gs_sys_years (number, database_version_id)
        SELECT :year_number, :target_version_id
        WHERE NOT EXISTS (
            SELECT 1
            FROM {SCHEMA_REFDATA}.gs_sys_years
            WHERE number = :year_number
              AND database_version_id = :target_version_id
        )
    """)

    for y in range(base_end_year + 1, new_end_year + 1):
        db.session.execute(
            ensure_year_sql,
            {"year_number": y, "target_version_id": target_version_id},
        )
    db.session.flush()

    # 3) Копируем данные последнего года (base_end_year) на каждый новый год
    copy_specs = [
        # station_powers: мощности станции
        {
            "table": f"{SCHEMA_GENERATION}.gs_gen_station_powers",
            "key_cols": ["id_station"],
            "select_cols": ["id_station", "p_ust", "p_ogr", "p_rasp"],
            "insert_cols": ["year_number", "id_station", "p_ust", "p_ogr", "p_rasp", "database_version_id"],
        },
        # machine_powers: мощности агрегатов
        {
            "table": f"{SCHEMA_GENERATION}.gs_gen_machine_powers",
            "key_cols": ["id_machine"],
            "select_cols": ["id_machine", "p_ust", "p_ogr", "p_rasp"],
            "insert_cols": ["year_number", "id_machine", "p_ust", "p_ogr", "p_rasp", "database_version_id"],
        },
        # pgu_machine_powers: мощности ПГУ-компонентов
        {
            "table": f"{SCHEMA_GENERATION}.gs_gen_pgu_machine_powers",
            "key_cols": ["id_pgu_machine"],
            "select_cols": ["id_pgu_machine", "p_ust"],
            "insert_cols": ["year_number", "id_pgu_machine", "p_ust", "database_version_id"],
        },
        # machine_fuels: топливо агрегата
        {
            "table": f"{SCHEMA_GENERATION}.gs_gen_machine_fuels",
            "key_cols": ["id_machine", "id_fuel"],
            "select_cols": ["id_machine", "id_fuel"],
            "insert_cols": ["year_number", "id_machine", "id_fuel", "database_version_id"],
        },
        # machine_tes_types: тип ТЭС агрегата
        {
            "table": f"{SCHEMA_GENERATION}.gs_gen_machine_tes_types",
            "key_cols": ["id_machine", "id_tes_type"],
            "select_cols": ["id_machine", "id_tes_type"],
            "insert_cols": ["year_number", "id_machine", "id_tes_type", "database_version_id"],
        },
        # machine_names: названия агрегатов по годам
        {
            "table": f"{SCHEMA_GENERATION}.gs_gen_machine_names",
            "key_cols": ["id_machine"],
            "select_cols": ["id_machine", "name"],
            "insert_cols": ["year_number", "id_machine", "name", "database_version_id"],
        },
    ]

    for y in range(base_end_year + 1, new_end_year + 1):
        for spec in copy_specs:
            table_name = spec["table"]
            key_conditions = " AND ".join([f"t2.{c} = t1.{c}" for c in spec["key_cols"]])

            insert_cols_sql = ", ".join(spec["insert_cols"])
            select_cols_sql = ", ".join([f"t1.{c}" for c in spec["select_cols"]])

            sql = text(f"""
                INSERT INTO {table_name} ({insert_cols_sql})
                SELECT
                    :new_year AS year_number,
                    {select_cols_sql},
                    :target_version_id AS database_version_id
                FROM {table_name} t1
                WHERE t1.database_version_id = :target_version_id
                  AND t1.year_number = :base_year
                  AND NOT EXISTS (
                      SELECT 1
                      FROM {table_name} t2
                      WHERE t2.database_version_id = :target_version_id
                        AND t2.year_number = :new_year
                        AND {key_conditions}
                  )
            """)

            db.session.execute(
                sql,
                {
                    "target_version_id": target_version_id,
                    "base_year": base_end_year,
                    "new_year": y,
                },
            )

    if do_commit:
        db.session.commit()

    log_to_db(
        user,
        "Продление периода версии завершено",
        f"Добавлены годы: {base_end_year + 1}..{new_end_year} (копия данных {base_end_year} года)",
        entity_type="database_version",
        entity_id=target_version_id,
    )

def _copy_association_tables(source_version_id, target_version_id, id_mappings, user):
    """
    Копирует ассоциативные таблицы (many-to-many) из одной версии в другую.
    Эти таблицы СОДЕРЖАТ поле database_version_id и связывают записи с ID.
    
    Args:
        source_version_id: ID версии-источника (или None для данных без версии)
        target_version_id: ID целевой версии
        id_mappings: Словарь соответствий старых и новых ID для каждой таблицы
        user: Пользователь для логирования
    """
    log_to_db(
        user,
        f"Начало копирования ассоциативных таблиц из версии {source_version_id} в версию {target_version_id}",
        "",
        entity_type="database_version",
        entity_id=target_version_id
    )
    
    # Список ассоциативных таблиц С database_version_id
    association_tables = [
        (SCHEMA_REFDATA, 'gs_sys_regional_district_regional_energy_system'),
        # Добавьте сюда другие ассоциативные таблицы при необходимости
    ]
    
    for schema, table in association_tables:
        try:
            # Получаем структуру таблицы
            structure_query = text("""
                SELECT column_name, data_type
                FROM information_schema.columns 
                WHERE table_schema = :schema_name 
                  AND table_name = :table_name
                  AND column_name != 'database_version_id'
                ORDER BY ordinal_position
            """)
            
            result = db.session.execute(structure_query, {"schema_name": schema, "table_name": table})
            columns = [(row[0], row[1]) for row in result]
            
            if not columns:
                current_app.logger.warning(f"Таблица {schema}.{table}: не найдена")
                continue
            
            column_names = [col[0] for col in columns]
            
            # Определяем, какие колонки нужно перепривязать
            # Обычно это колонки *_id
            columns_to_map = []
            for col_name in column_names:
                # Определяем, в какую таблицу ссылается эта колонка
                if col_name == 'regional_district_id':
                    mapping_key = f"{SCHEMA_REFDATA}.gs_sys_regional_districts"
                    columns_to_map.append((col_name, mapping_key))
                elif col_name == 'regional_energy_system_id':
                    mapping_key = f"{SCHEMA_REFDATA}.gs_sys_regional_energy_systems"
                    columns_to_map.append((col_name, mapping_key))
                # Добавьте другие колонки при необходимости
            
            # Определяем WHERE условие для источника
            if source_version_id is None:
                where_clause = "database_version_id IS NULL"
            else:
                where_clause = f"database_version_id = {source_version_id}"
            
            # Загружаем исходные данные для текущей версии
            source_query = text(f"""
                SELECT {', '.join(column_names)}
                FROM {schema}.{table}
                WHERE {where_clause}
            """)
            
            result = db.session.execute(source_query)
            source_rows = [dict(row._mapping) for row in result]
            
            if not source_rows:
                current_app.logger.info(f"Таблица {schema}.{table}: нет данных для копирования (WHERE {where_clause})")
                continue
            
            # Перепривязываем ID и вставляем новые записи с новым database_version_id
            copied_count = 0
            for row in source_rows:
                try:
                    # Перепривязываем ID согласно маппингу
                    for col_name, mapping_key in columns_to_map:
                        old_id = row[col_name]
                        if mapping_key in id_mappings and old_id in id_mappings[mapping_key]:
                            row[col_name] = id_mappings[mapping_key][old_id]
                    
                    # Добавляем новый database_version_id
                    row['database_version_id'] = target_version_id
                    
                    # Формируем INSERT запрос с database_version_id
                    columns_str = ", ".join(column_names + ['database_version_id'])
                    values_str = ", ".join([f":{col}" for col in column_names + ['database_version_id']])
                    
                    insert_query = text(f"""
                        INSERT INTO {schema}.{table} ({columns_str})
                        VALUES ({values_str})
                        ON CONFLICT DO NOTHING
                    """)
                    # Каждую вставку делаем в SAVEPOINT: ошибка на одной строке не должна
                    # "ломать" транзакцию целиком (иначе получим InFailedSqlTransaction).
                    with db.session.begin_nested():
                        db.session.execute(insert_query, row)
                        copied_count += 1
                except Exception as e:
                    current_app.logger.error(f"Ошибка при копировании записи из {schema}.{table}: {e}")
                    continue
            
            db.session.flush()
            current_app.logger.info(f"Таблица {schema}.{table}: скопировано {copied_count} записей")
            
            log_to_db(
                user,
                f"Скопированы данные ассоциативной таблицы {schema}.{table}",
                f"Из версии {source_version_id} в версию {target_version_id}: {copied_count} записей",
                entity_type="database_version",
                entity_id=target_version_id
            )
        except Exception as e:
            log_to_db(
                user,
                f"Ошибка копирования ассоциативной таблицы {schema}.{table}",
                f"Из версии {source_version_id} в версию {target_version_id}: {str(e)}",
                entity_type="database_version",
                entity_id=target_version_id
            )
            current_app.logger.error(f"Ошибка при копировании ассоциативной таблицы {schema}.{table}: {e}")
            continue
    
    log_to_db(
        user,
        f"Копирование ассоциативных таблиц завершено",
        f"Из версии {source_version_id} в версию {target_version_id}",
        entity_type="database_version",
        entity_id=target_version_id
    )


def _copy_version_data_staged(source_version_id, target_version_id, user, do_commit=True, copy_mode="full"):
    """
    ПОЭТАПНАЯ логика копирования данных версии с правильным порядком операций.
    
    НОВАЯ ЛОГИКА:
    1. Сначала копируем ТОЛЬКО таблицы БЕЗ взаимосвязей (полностью независимые)
    2. Затем поэтапно копируем таблицы с зависимостями, используя новые ID
    3. Каждый этап зависит от предыдущих этапов
    
    Args:
        source_version_id: ID версии-источника (или None для данных без версии)
        target_version_id: ID целевой версии
        user: Пользователь для логирования
        do_commit: Выполнять ли commit после копирования (по умолчанию True)
        copy_mode: Режим копирования: "full" (по умолчанию) или "refdata_only"
    """
    log_to_db(
        user,
        f"Начало ПОЭТАПНОГО копирования данных из версии {source_version_id} в версию {target_version_id}",
        "",
        entity_type="database_version",
        entity_id=target_version_id
    )
    
    copy_mode = (copy_mode or "full").lower()
    if copy_mode not in {"full", "refdata_only"}:
        raise ValueError(f"Неизвестный режим копирования данных: {copy_mode}")
    refdata_only = copy_mode == "refdata_only"
    log_to_db(
        user,
        "Выбран режим копирования данных версии",
        "только справочники refdata" if refdata_only else "полное копирование generation+refdata",
        entity_type="database_version",
        entity_id=target_version_id
    )
    
    id_mappings = {}
    total_copied = 0

    # В проекте схема справочников может отличаться от "refdata" (по умолчанию gs_sys),
    # а таблицы в ней имеют префикс gs_. Используем значения из config.
    ref_schema = SCHEMA_REFDATA
    gen_schema = SCHEMA_GENERATION
    fuel_schema = SCHEMA_FUEL
    
    # ЭТАП 1: Полностью независимые таблицы (без внешних ключей на другие таблицы)
    log_to_db(
        user,
        "ЭТАП 1: Копирование полностью независимых таблиц",
        f"Из версии {source_version_id} в версию {target_version_id}",
        entity_type="database_version",
        entity_id=target_version_id
    )
    
    # Полностью независимые таблицы (справочники без внешних ключей)
    completely_independent_tables = [
        (ref_schema, 'gs_sys_station_types'),
        (ref_schema, 'gs_sys_machine_types'),
        (ref_schema, 'gs_sys_tes_types'),
        (ref_schema, 'gs_sys_tes_machine_types'),
        (ref_schema, 'gs_sys_pgu_tes_machine_types'),
        (ref_schema, 'gs_sys_condition_types'),
        (ref_schema, 'gs_sys_technology_types'),
        (ref_schema, 'gs_sys_technology_availabilities'),
        (ref_schema, 'gs_sys_energy_system_types'),
        (ref_schema, 'gs_sys_fuel_categories'),
        (ref_schema, 'gs_sys_fuel_types'),
        (ref_schema, 'gs_sys_fuels'),
        (ref_schema, 'gs_sys_companies'),
        (gen_schema, 'gs_gen_station_groups'),
        (gen_schema, 'gs_gen_documents_kommod')
    ]
    
    # Копируем полностью независимые таблицы
    for schema, table in completely_independent_tables:
        try:
            # Важно: если копирование конкретной таблицы падает, не "ломаем" всю транзакцию.
            # Используем SAVEPOINT, чтобы последующие операции не падали с InFailedSqlTransaction.
            with db.session.begin_nested():
                copied, mapping = _copy_table_with_mapping(schema, table, source_version_id, target_version_id, user)
                total_copied += copied
                if mapping:
                    id_mappings[f"{schema}.{table}"] = mapping
                    current_app.logger.info(f"✅ Скопирована таблица {schema}.{table}: {copied} записей")
        except Exception as e:
            current_app.logger.error(f"Ошибка копирования таблицы {schema}.{table}: {e}")
            log_to_db(
                user,
                f"Ошибка копирования таблицы {schema}.{table}",
                str(e),
                entity_type="database_version",
                entity_id=target_version_id
            )
    
    # ЭТАП 2: Таблицы с зависимостями от ЭТАПА 1
    log_to_db(
        user,
        "ЭТАП 2: Копирование таблиц с зависимостями от ЭТАПА 1",
        f"Из версии {source_version_id} в версию {target_version_id}",
        entity_type="database_version",
        entity_id=target_version_id
    )
    
    # Таблицы, зависящие только от таблиц ЭТАПА 1
    stage2_tables = [
        {
            'schema': ref_schema,
            'table': 'gs_sys_equipment_groups',
            'dependencies': [
                {'fk': 'id_technology_availability', 'ref_table': f'{ref_schema}.gs_sys_technology_availabilities'},
                {'fk': 'id_technology_type', 'ref_table': f'{ref_schema}.gs_sys_technology_types'}
            ]
        },
        {
            'schema': ref_schema,
            'table': 'gs_sys_union_energy_systems',
            'dependencies': []  # Независимая, но копируем во 2 этапе для логической группировки
        },
        {
            'schema': ref_schema,
            'table': 'gs_sys_synchronous_areas',
            'dependencies': []
        },
        {
            'schema': ref_schema,
            'table': 'gs_sys_energy_zones',
            'dependencies': []
        },
        {
            'schema': ref_schema,
            'table': 'gs_sys_federal_districts',
            'dependencies': []
        }
    ]
    
    # Копируем таблицы ЭТАПА 2
    for table_info in stage2_tables:
        schema = table_info['schema']
        table = table_info['table']
        dependencies = table_info.get('dependencies', [])
        
        try:
            with db.session.begin_nested():
                copied, mapping = _copy_table_with_mapping(schema, table, source_version_id, target_version_id, user)
                total_copied += copied
                if mapping:
                    id_mappings[f"{schema}.{table}"] = mapping
                    current_app.logger.info(f"✅ Скопирована таблица {schema}.{table}: {copied} записей")
                
                # Обновляем foreign key согласно зависимостям
                for dep in dependencies:
                    fk_column = dep['fk']
                    ref_table = dep['ref_table']
                    if ref_table in id_mappings:
                        ref_mapping = id_mappings[ref_table]
                        _update_foreign_keys_in_table(
                            schema, table, fk_column, ref_mapping, target_version_id, user
                        )
                        current_app.logger.info(f"🔄 Обновлены FK {schema}.{table}.{fk_column} -> {ref_table}")
        except Exception as e:
            current_app.logger.error(f"Ошибка копирования таблицы {schema}.{table}: {e}")
            log_to_db(
                user,
                f"Ошибка копирования таблицы {schema}.{table}",
                str(e),
                entity_type="database_version",
                entity_id=target_version_id
            )
    
    # ЭТАП 3: Таблицы с зависимостями от ЭТАПОВ 1-2
    log_to_db(
        user,
        "ЭТАП 3: Копирование таблиц с зависимостями от ЭТАПОВ 1-2",
        f"Из версии {source_version_id} в версию {target_version_id}",
        entity_type="database_version",
        entity_id=target_version_id
    )
    
    stage3_tables = [
        {
            'schema': ref_schema,
            'table': 'gs_sys_regional_districts',
            'dependencies': [
                {'fk': 'id_federal_district', 'ref_table': f'{ref_schema}.gs_sys_federal_districts'},
                {'fk': 'id_energy_zone', 'ref_table': f'{ref_schema}.gs_sys_energy_zones'},
                {'fk': 'id_synchronous_area', 'ref_table': f'{ref_schema}.gs_sys_synchronous_areas'}
            ]
        },
        {
            'schema': ref_schema,
            'table': 'gs_sys_regional_energy_systems',
            'dependencies': [
                {'fk': 'id_union_energy_system', 'ref_table': f'{ref_schema}.gs_sys_union_energy_systems'}
            ]
        }
    ]
    
    # Копируем таблицы ЭТАПА 3
    for table_info in stage3_tables:
        schema = table_info['schema']
        table = table_info['table']
        
        try:
            with db.session.begin_nested():
                # Копируем данные таблицы (пока со старыми FK)
                copied, mapping = _copy_table_with_mapping(schema, table, source_version_id, target_version_id, user)
                total_copied += copied
                if mapping:
                    id_mappings[f"{schema}.{table}"] = mapping
                    current_app.logger.info(f"✅ Скопирована таблица {schema}.{table}: {copied} записей")
                
                # Обновляем foreign key согласно зависимостям
                for dep in table_info['dependencies']:
                    fk_column = dep['fk']
                    ref_table = dep['ref_table']
                    
                    if ref_table in id_mappings:
                        ref_mapping = id_mappings[ref_table]
                        _update_foreign_keys_in_table(
                            schema, table, fk_column, ref_mapping, target_version_id, user
                        )
                        current_app.logger.info(f"🔄 Обновлены FK {schema}.{table}.{fk_column} -> {ref_table}")
                    
        except Exception as e:
            current_app.logger.error(f"Ошибка копирования таблицы {schema}.{table}: {e}")
            log_to_db(
                user,
                f"Ошибка копирования таблицы {schema}.{table}",
                str(e),
                entity_type="database_version",
                entity_id=target_version_id
            )
    
    # ЭТАП 4: Таблицы с зависимостями от ЭТАПОВ 1-3
    log_to_db(
        user,
        "ЭТАП 4: Копирование таблиц с зависимостями от ЭТАПОВ 1-3",
        f"Из версии {source_version_id} в версию {target_version_id}",
        entity_type="database_version",
        entity_id=target_version_id
    )
    
    stage4_tables = [
        {
            'schema': ref_schema,
            'table': 'gs_sys_energy_areas',
            'dependencies': [
                {'fk': 'id_regional_district', 'ref_table': f'{ref_schema}.gs_sys_regional_districts'}
            ]
        },
        {
            'schema': ref_schema,
            'table': 'gs_sys_energy_units',
            'dependencies': [
                {'fk': 'id_regional_district', 'ref_table': f'{ref_schema}.gs_sys_regional_districts'},
                {'fk': 'id_regional_energy_system', 'ref_table': f'{ref_schema}.gs_sys_regional_energy_systems'}
            ]
        }
    ]
    
    # Копируем таблицы ЭТАПА 4
    for table_info in stage4_tables:
        schema = table_info['schema']
        table = table_info['table']
        
        try:
            with db.session.begin_nested():
                # Копируем данные таблицы (пока со старыми FK)
                copied, mapping = _copy_table_with_mapping(schema, table, source_version_id, target_version_id, user)
                total_copied += copied
                if mapping:
                    id_mappings[f"{schema}.{table}"] = mapping
                    current_app.logger.info(f"✅ Скопирована таблица {schema}.{table}: {copied} записей")
                
                # Обновляем foreign key согласно зависимостям
                for dep in table_info['dependencies']:
                    fk_column = dep['fk']
                    ref_table = dep['ref_table']
                    
                    if ref_table in id_mappings:
                        ref_mapping = id_mappings[ref_table]
                        _update_foreign_keys_in_table(
                            schema, table, fk_column, ref_mapping, target_version_id, user
                        )
                        current_app.logger.info(f"🔄 Обновлены FK {schema}.{table}.{fk_column} -> {ref_table}")
                    
        except Exception as e:
            current_app.logger.error(f"Ошибка копирования таблицы {schema}.{table}: {e}")
            log_to_db(
                user,
                f"Ошибка копирования таблицы {schema}.{table}",
                str(e),
                entity_type="database_version",
                entity_id=target_version_id
            )
    
    if refdata_only:
        log_to_db(
            user,
            "Режим «только refdata» активен",
            "Этапы копирования generation (5-8) пропущены",
            entity_type="database_version",
            entity_id=target_version_id
        )
    else:
        # ЭТАП 5: Таблицы generation с зависимостями от всех предыдущих этапов
        log_to_db(
            user,
            "ЭТАП 5: Копирование таблиц generation с зависимостями",
            f"Из версии {source_version_id} в версию {target_version_id}",
            entity_type="database_version",
            entity_id=target_version_id
        )
        
        stage5_tables = [
            {
                'schema': gen_schema,
                'table': 'gs_gen_stations',
                'dependencies': [
                    {'fk': 'id_station_group', 'ref_table': f'{gen_schema}.gs_gen_station_groups'},
                    {'fk': 'id_regional_district', 'ref_table': f'{ref_schema}.gs_sys_regional_districts'},
                    {'fk': 'id_regional_energy_system', 'ref_table': f'{ref_schema}.gs_sys_regional_energy_systems'},
                    {'fk': 'id_energy_unit', 'ref_table': f'{ref_schema}.gs_sys_energy_units'},
                    {'fk': 'id_station_type', 'ref_table': f'{ref_schema}.gs_sys_station_types'},
                    {'fk': 'id_condition_type', 'ref_table': f'{ref_schema}.gs_sys_condition_types'}
                ]
            }
        ]
        
        # Копируем таблицы ЭТАПА 5
        for table_info in stage5_tables:
            schema = table_info['schema']
            table = table_info['table']
            
            try:
                with db.session.begin_nested():
                    # Копируем данные таблицы (пока со старыми FK)
                    copied, mapping = _copy_table_with_mapping(schema, table, source_version_id, target_version_id, user)
                    total_copied += copied
                    if mapping:
                        id_mappings[f"{schema}.{table}"] = mapping
                        current_app.logger.info(f"✅ Скопирована таблица {schema}.{table}: {copied} записей")
                    
                    # Обновляем foreign key согласно зависимостям
                    for dep in table_info['dependencies']:
                        fk_column = dep['fk']
                        ref_table = dep['ref_table']
                        
                        if ref_table in id_mappings:
                            ref_mapping = id_mappings[ref_table]
                            _update_foreign_keys_in_table(
                                schema, table, fk_column, ref_mapping, target_version_id, user
                            )
                            current_app.logger.info(f"🔄 Обновлены FK {schema}.{table}.{fk_column} -> {ref_table}")
                        
            except Exception as e:
                current_app.logger.error(f"Ошибка копирования таблицы {schema}.{table}: {e}")
                log_to_db(
                    user,
                    f"Ошибка копирования таблицы {schema}.{table}",
                    str(e),
                    entity_type="database_version",
                    entity_id=target_version_id
                )
        
        # ЭТАП 6: Таблицы, зависящие от stations
        log_to_db(
            user,
            "ЭТАП 6: Копирование таблиц, зависящих от stations",
            f"Из версии {source_version_id} в версию {target_version_id}",
            entity_type="database_version",
            entity_id=target_version_id
        )
        
        stage6_tables = [
            {
                'schema': gen_schema,
                'table': 'gs_gen_station_powers',
                'dependencies': [
                    {'fk': 'id_station', 'ref_table': f'{gen_schema}.gs_gen_stations'}
                ]
            },
            {
                'schema': gen_schema,
                'table': 'gs_gen_machines',
                'dependencies': [
                    {'fk': 'id_station', 'ref_table': f'{gen_schema}.gs_gen_stations'},
                    {'fk': 'id_machine_type', 'ref_table': f'{ref_schema}.gs_sys_machine_types'},
                    {'fk': 'id_tes_machine_type', 'ref_table': f'{ref_schema}.gs_sys_tes_machine_types'},
                    {'fk': 'id_condition_type', 'ref_table': f'{ref_schema}.gs_sys_condition_types'},
                    {'fk': 'id_gen_company', 'ref_table': f'{ref_schema}.gs_sys_companies'},
                    {'fk': 'id_energy_area', 'ref_table': f'{ref_schema}.gs_sys_energy_areas'},
                    {'fk': 'id_technology_availability', 'ref_table': f'{ref_schema}.gs_sys_technology_availabilities'},
                    {'fk': 'id_technology_type', 'ref_table': f'{ref_schema}.gs_sys_technology_types'},
                    {'fk': 'id_equipment_group', 'ref_table': f'{ref_schema}.gs_sys_equipment_groups'}
                ]
            },
            {
                'schema': gen_schema,
                'table': 'gs_gen_boilers',
                'dependencies': [
                    {'fk': 'id_station', 'ref_table': f'{gen_schema}.gs_gen_stations'}
                ]
            }
        ]
        
        # Копируем таблицы ЭТАПА 6
        for table_info in stage6_tables:
            schema = table_info['schema']
            table = table_info['table']
            
            try:
                with db.session.begin_nested():
                    # Копируем данные таблицы (пока со старыми FK)
                    copied, mapping = _copy_table_with_mapping(schema, table, source_version_id, target_version_id, user)
                    total_copied += copied
                    if mapping:
                        id_mappings[f"{schema}.{table}"] = mapping
                        current_app.logger.info(f"✅ Скопирована таблица {schema}.{table}: {copied} записей")
                    
                    # Обновляем foreign key согласно зависимостям
                    for dep in table_info['dependencies']:
                        fk_column = dep['fk']
                        ref_table = dep['ref_table']
                        
                        if ref_table in id_mappings:
                            ref_mapping = id_mappings[ref_table]
                            _update_foreign_keys_in_table(
                                schema, table, fk_column, ref_mapping, target_version_id, user
                            )
                            current_app.logger.info(f"🔄 Обновлены FK {schema}.{table}.{fk_column} -> {ref_table}")
                        
            except Exception as e:
                current_app.logger.error(f"Ошибка копирования таблицы {schema}.{table}: {e}")
                log_to_db(
                    user,
                    f"Ошибка копирования таблицы {schema}.{table}",
                    str(e),
                    entity_type="database_version",
                    entity_id=target_version_id
                )
        
        # ЭТАП 7: Таблицы, зависящие от machines
        log_to_db(
            user,
            "ЭТАП 7: Копирование таблиц, зависящих от machines",
            f"Из версии {source_version_id} в версию {target_version_id}",
            entity_type="database_version",
            entity_id=target_version_id
        )
        
        stage7_tables = [
            {
                'schema': gen_schema,
                'table': 'gs_gen_machine_powers',
                'dependencies': [
                    {'fk': 'id_machine', 'ref_table': f'{gen_schema}.gs_gen_machines'}
                ]
            },
            {
                'schema': gen_schema,
                'table': 'gs_gen_machine_fuels',
                'dependencies': [
                    {'fk': 'id_machine', 'ref_table': f'{gen_schema}.gs_gen_machines'},
                    {'fk': 'id_fuel', 'ref_table': f'{ref_schema}.gs_sys_fuels'}
                ]
            },
            {
                'schema': gen_schema,
                'table': 'gs_gen_machine_tes_types',
                'dependencies': [
                    {'fk': 'id_machine', 'ref_table': f'{gen_schema}.gs_gen_machines'},
                    {'fk': 'id_tes_type', 'ref_table': f'{ref_schema}.gs_sys_tes_types'}
                ]
            },
            {
                'schema': gen_schema,
                'table': 'gs_gen_machine_names',
                'dependencies': [
                    {'fk': 'id_machine', 'ref_table': f'{gen_schema}.gs_gen_machines'}
                ]
            },
            {
                'schema': gen_schema,
                'table': 'gs_gen_pgu_machines',
                'dependencies': [
                    {'fk': 'id_parent_machine', 'ref_table': f'{gen_schema}.gs_gen_machines'},
                    {'fk': 'id_pgu_tes_machine_type', 'ref_table': f'{ref_schema}.gs_sys_pgu_tes_machine_types'},
                    {'fk': 'id_condition_type', 'ref_table': f'{ref_schema}.gs_sys_condition_types'}
                ]
            }
        ]
        
        # Копируем таблицы ЭТАПА 7
        for table_info in stage7_tables:
            schema = table_info['schema']
            table = table_info['table']
            
            try:
                with db.session.begin_nested():
                    # Копируем данные таблицы (пока со старыми FK)
                    copied, mapping = _copy_table_with_mapping(schema, table, source_version_id, target_version_id, user)
                    total_copied += copied
                    if mapping:
                        id_mappings[f"{schema}.{table}"] = mapping
                        current_app.logger.info(f"✅ Скопирована таблица {schema}.{table}: {copied} записей")
                    
                    # Обновляем foreign key согласно зависимостям
                    for dep in table_info['dependencies']:
                        fk_column = dep['fk']
                        ref_table = dep['ref_table']
                        
                        if ref_table in id_mappings:
                            ref_mapping = id_mappings[ref_table]
                            _update_foreign_keys_in_table(
                                schema, table, fk_column, ref_mapping, target_version_id, user
                            )
                            current_app.logger.info(f"🔄 Обновлены FK {schema}.{table}.{fk_column} -> {ref_table}")
                        
            except Exception as e:
                current_app.logger.error(f"Ошибка копирования таблицы {schema}.{table}: {e}")
                log_to_db(
                    user,
                    f"Ошибка копирования таблицы {schema}.{table}",
                    str(e),
                    entity_type="database_version",
                    entity_id=target_version_id
                )
        
        # ЭТАП 8: Таблицы, зависящие от pgu_machines
        log_to_db(
            user,
            "ЭТАП 8: Копирование таблиц, зависящих от pgu_machines",
            f"Из версии {source_version_id} в версию {target_version_id}",
            entity_type="database_version",
            entity_id=target_version_id
        )
        
        stage8_tables = [
            {
                'schema': gen_schema,
                'table': 'gs_gen_pgu_machine_powers',
                'dependencies': [
                    {'fk': 'id_pgu_machine', 'ref_table': f'{gen_schema}.gs_gen_pgu_machines'}
                ]
            }
        ]
        
        # Копируем таблицы ЭТАПА 8
        for table_info in stage8_tables:
            schema = table_info['schema']
            table = table_info['table']
            
            try:
                with db.session.begin_nested():
                    # Копируем данные таблицы (пока со старыми FK)
                    copied, mapping = _copy_table_with_mapping(schema, table, source_version_id, target_version_id, user)
                    total_copied += copied
                    if mapping:
                        id_mappings[f"{schema}.{table}"] = mapping
                        current_app.logger.info(f"✅ Скопирована таблица {schema}.{table}: {copied} записей")
                    
                    # Обновляем foreign key согласно зависимостям
                    for dep in table_info['dependencies']:
                        fk_column = dep['fk']
                        ref_table = dep['ref_table']
                        
                        if ref_table in id_mappings:
                            ref_mapping = id_mappings[ref_table]
                            _update_foreign_keys_in_table(
                                schema, table, fk_column, ref_mapping, target_version_id, user
                            )
                            current_app.logger.info(f"🔄 Обновлены FK {schema}.{table}.{fk_column} -> {ref_table}")
                        
            except Exception as e:
                current_app.logger.error(f"Ошибка копирования таблицы {schema}.{table}: {e}")
                log_to_db(
                    user,
                    f"Ошибка копирования таблицы {schema}.{table}",
                    str(e),
                    entity_type="database_version",
                    entity_id=target_version_id
                )
    
    # Копирование ассоциативных таблиц (связей many-to-many)
    _copy_association_tables(source_version_id, target_version_id, id_mappings, user)
    
    # Доп. шаги перепривязки FK в справочниках после поэтапного копирования.
    # Важно: выполняем в SAVEPOINT, чтобы единичная ошибка не переводила всю транзакцию
    # в состояние aborted (и не приводила к InFailedSqlTransaction на следующих шагах).
    try:
        from sqlalchemy import text as _text
        with db.session.begin_nested():
            # fuels.id_fuel_type -> fuel_types (сначала по ID-мэппингу, затем резерв по name)
            updated_rows_total = 0
            ft_mapping = id_mappings.get(f'{ref_schema}.gs_sys_fuel_types') or {}
            if ft_mapping:
                current_app.logger.info("🔧 [STAGED] Перепривязка fuels по маппингу ID fuel_types...")
                temp_tbl = f"tmp_map_ft_{target_version_id}"
                db.session.execute(_text(f"DROP TABLE IF EXISTS {temp_tbl}"))
                db.session.execute(_text(
                    f"CREATE TEMP TABLE {temp_tbl} (old_id INTEGER PRIMARY KEY, new_id INTEGER NOT NULL)"
                ))
                rows = [(old_id, new_id) for old_id, new_id in ft_mapping.items()]
                batch_size = 1000
                for i in range(0, len(rows), batch_size):
                    batch = rows[i:i+batch_size]
                    db.session.execute(
                        _text(f"INSERT INTO {temp_tbl} (old_id, new_id) VALUES (:old_id, :new_id) ON CONFLICT (old_id) DO NOTHING"),
                        [{"old_id": o, "new_id": n} for o, n in batch]
                    )
                result = db.session.execute(_text(
                    f"""
                    UPDATE {ref_schema}.gs_sys_fuels f
                    SET id_fuel_type = m.new_id
                    FROM {temp_tbl} m
                    WHERE f.database_version_id = :target_version_id
                      AND f.id_fuel_type = m.old_id
                      AND f.id_fuel_type IS DISTINCT FROM m.new_id
                    """
                ), {"target_version_id": target_version_id})
                updated_rows_total += result.rowcount or 0
                db.session.execute(_text(f"DROP TABLE IF EXISTS {temp_tbl}"))
            if updated_rows_total == 0:
                current_app.logger.info("🔧 [STAGED] Перепривязка fuels по name fuel_types (резервный путь)...")
                relink_sql = _text(
                    f"""
                    WITH map AS (
                        SELECT f.id AS fuel_id, ft_new.id AS new_ft_id
                        FROM {ref_schema}.gs_sys_fuels f
                        JOIN {ref_schema}.gs_sys_fuel_types ft_old ON ft_old.id = f.id_fuel_type
                        JOIN {ref_schema}.gs_sys_fuel_types ft_new
                          ON ft_new.name = ft_old.name
                         AND ft_new.database_version_id = f.database_version_id
                        WHERE f.database_version_id = :target_version_id
                    )
                    UPDATE {ref_schema}.gs_sys_fuels f
                    SET id_fuel_type = m.new_ft_id
                    FROM map m
                    WHERE f.id = m.fuel_id
                      AND f.id_fuel_type IS DISTINCT FROM m.new_ft_id;
                    """
                )
                result = db.session.execute(relink_sql, {"target_version_id": target_version_id})
                updated_rows_total += result.rowcount or 0
            current_app.logger.info(f"  ✓ [STAGED] Обновлено связей fuels.id_fuel_type: {updated_rows_total}")
            # Контрольная проверка
            check_sql = _text(
                f"""
                SELECT COUNT(*)
                FROM {ref_schema}.gs_sys_fuels f
                LEFT JOIN {ref_schema}.gs_sys_fuel_types ft
                  ON ft.id = f.id_fuel_type
                 AND ft.database_version_id = f.database_version_id
                WHERE f.database_version_id = :target_version_id
                  AND ft.id IS NULL;
                """
            )
            not_mapped_cnt = db.session.execute(check_sql, {"target_version_id": target_version_id}).scalar()
            if not_mapped_cnt and not_mapped_cnt > 0:
                current_app.logger.warning(f"  ⚠️ [STAGED] Осталось непривязанных строк в {ref_schema}.gs_sys_fuels: {not_mapped_cnt}")
            
            # union_energy_systems.id_energy_system_type -> energy_system_types (ID-мэппинг, затем резерв по name)
            updated_ues_rows_total = 0
            est_mapping = id_mappings.get(f'{ref_schema}.gs_sys_energy_system_types') or {}
            if est_mapping:
                current_app.logger.info("🔧 [STAGED] Перепривязка UES по маппингу ID energy_system_types...")
                temp_tbl2 = f"tmp_map_est_{target_version_id}"
                db.session.execute(_text(f"DROP TABLE IF EXISTS {temp_tbl2}"))
                db.session.execute(_text(
                    f"CREATE TEMP TABLE {temp_tbl2} (old_id INTEGER PRIMARY KEY, new_id INTEGER NOT NULL)"
                ))
                rows2 = [(old_id, new_id) for old_id, new_id in est_mapping.items()]
                batch_size = 1000
                for i in range(0, len(rows2), batch_size):
                    batch2 = rows2[i:i+batch_size]
                    db.session.execute(
                        _text(f"INSERT INTO {temp_tbl2} (old_id, new_id) VALUES (:old_id, :new_id) ON CONFLICT (old_id) DO NOTHING"),
                        [{"old_id": o, "new_id": n} for o, n in batch2]
                    )
                result2 = db.session.execute(_text(
                    f"""
                    UPDATE {ref_schema}.gs_sys_union_energy_systems ues
                    SET id_energy_system_type = m.new_id
                    FROM {temp_tbl2} m
                    WHERE ues.database_version_id = :target_version_id
                      AND ues.id_energy_system_type = m.old_id
                      AND ues.id_energy_system_type IS DISTINCT FROM m.new_id
                    """
                ), {"target_version_id": target_version_id})
                updated_ues_rows_total += result2.rowcount or 0
                db.session.execute(_text(f"DROP TABLE IF EXISTS {temp_tbl2}"))
            if updated_ues_rows_total == 0:
                current_app.logger.info("🔧 [STAGED] Перепривязка UES по name energy_system_types (резервный путь)...")
                relink_ues_sql = _text(
                    f"""
                    WITH map AS (
                        SELECT ues.id AS ues_id, est_new.id AS new_type_id
                        FROM {ref_schema}.gs_sys_union_energy_systems ues
                        JOIN {ref_schema}.gs_sys_energy_system_types est_old ON est_old.id = ues.id_energy_system_type
                        JOIN {ref_schema}.gs_sys_energy_system_types est_new
                          ON est_new.name = est_old.name
                         AND est_new.database_version_id = ues.database_version_id
                        WHERE ues.database_version_id = :target_version_id
                    )
                    UPDATE {ref_schema}.gs_sys_union_energy_systems ues
                    SET id_energy_system_type = m.new_type_id
                    FROM map m
                    WHERE ues.id = m.ues_id
                      AND ues.id_energy_system_type IS DISTINCT FROM m.new_type_id;
                    """
                )
                result2 = db.session.execute(relink_ues_sql, {"target_version_id": target_version_id})
                updated_ues_rows_total += result2.rowcount or 0
            current_app.logger.info(f"  ✓ [STAGED] Обновлено связей union_energy_systems.id_energy_system_type: {updated_ues_rows_total}")
            # Контрольная проверка
            check_ues_sql = _text(
                f"""
                SELECT COUNT(*)
                FROM {ref_schema}.gs_sys_union_energy_systems ues
                LEFT JOIN {ref_schema}.gs_sys_energy_system_types est
                  ON est.id = ues.id_energy_system_type
                 AND est.database_version_id = ues.database_version_id
                WHERE ues.database_version_id = :target_version_id
                  AND est.id IS NULL;
                """
            )
            not_mapped_cnt2 = db.session.execute(check_ues_sql, {"target_version_id": target_version_id}).scalar()
            if not_mapped_cnt2 and not_mapped_cnt2 > 0:
                current_app.logger.warning(
                    f"  ⚠️ [STAGED] Осталось непривязанных строк в {ref_schema}.gs_sys_union_energy_systems: {not_mapped_cnt2}"
                )
    except Exception as e:
        current_app.logger.error(f"  ❌ [STAGED] Ошибка доп. перепривязки FK в справочниках: {e}")
    
    # Коммитим только если do_commit=True
    if do_commit:
        db.session.commit()
        current_app.logger.info(f"✅ Commit выполнен после ПОЭТАПНОГО копирования данных")
        log_to_db(
            user,
            "ПОЭТАПНОЕ копирование данных версии завершено",
            f"Из версии {source_version_id} в версию {target_version_id}: всего скопировано {total_copied} записей",
            entity_type="database_version",
            entity_id=target_version_id
        )
    else:
        current_app.logger.info(f"ℹ️  Commit отложен, будет выполнен на уровне выше")


def _copy_version_data_fixed(source_version_id, target_version_id, user, do_commit=True):
    """
    НОВАЯ ЛОГИКА копирования данных версии с правильным порядком операций.
    
    НОВАЯ ЛОГИКА:
    1. Сначала копируем таблицы БЕЗ зависимостей (справочники и независимые таблицы)
    2. Затем копируем таблицы С зависимостями, обновляя foreign key на новые ID
    3. Порядок: сначала все для refdata, потом для generation
    
    Args:
        source_version_id: ID версии-источника (или None для данных без версии)
        target_version_id: ID целевой версии
        user: Пользователь для логирования
        do_commit: Выполнять ли commit после копирования (по умолчанию True)
    """
    log_to_db(
        user,
        f"Начало НОВОГО копирования данных из версии {source_version_id} в версию {target_version_id}",
        "",
        entity_type="database_version",
        entity_id=target_version_id
    )
    
    id_mappings = {}
    total_copied = 0
    
    # ЭТАП 1: Копируем таблицы refdata БЕЗ зависимостей
    log_to_db(
        user,
        "ЭТАП 1: Копирование таблиц refdata без зависимостей",
        f"Из версии {source_version_id} в версию {target_version_id}",
        entity_type="database_version",
        entity_id=target_version_id
    )
    
    # Независимые таблицы refdata (справочники без внешних ключей на другие таблицы refdata)
    independent_refdata_tables = [
        'station_types', 'machine_types', 'tes_types', 'tes_machine_types',
        'pgu_tes_machine_types', 'condition_types', 'technology_types',
        'technology_availabilities', 'equipment_groups', 'energy_system_types',
        'union_energy_systems', 'synchronous_areas', 'energy_zones', 
        'federal_districts', 'gs_sys_companies', 'fuel_categories', 'fuel_types', 'fuels'
    ]
    
    # Копируем независимые таблицы refdata
    for table in independent_refdata_tables:
        try:
            copied, mapping = _copy_table_with_mapping('refdata', table, source_version_id, target_version_id, user)
            total_copied += copied
            if mapping:
                id_mappings[f"refdata.{table}"] = mapping
        except Exception as e:
            current_app.logger.error(f"Ошибка копирования таблицы refdata.{table}: {e}")
            log_to_db(
                user,
                f"Ошибка копирования таблицы refdata.{table}",
                str(e),
                entity_type="database_version",
                entity_id=target_version_id
            )
    
    # ЭТАП 2: Копируем таблицы refdata С зависимостями
    log_to_db(
        user,
        "ЭТАП 2: Копирование таблиц refdata с зависимостями",
        f"Из версии {source_version_id} в версию {target_version_id}",
        entity_type="database_version",
        entity_id=target_version_id
    )
    
    # Таблицы refdata с зависимостями в порядке иерархии
    dependent_refdata_tables = [
        {
            'table': 'regional_districts',
            'dependencies': [
                {'fk': 'id_federal_district', 'ref_table': 'refdata.federal_districts'},
                {'fk': 'id_energy_zone', 'ref_table': 'refdata.energy_zones'},
                {'fk': 'id_synchronous_area', 'ref_table': 'refdata.synchronous_areas'}
            ]
        },
        {
            'table': 'regional_energy_systems',
            'dependencies': [
                {'fk': 'id_union_energy_system', 'ref_table': 'refdata.union_energy_systems'}
            ]
        },
        {
            'table': 'energy_areas',
            'dependencies': [
                {'fk': 'id_regional_district', 'ref_table': 'refdata.regional_districts'}
            ]
        },
        {
            'table': 'energy_units',
            'dependencies': [
                {'fk': 'id_regional_district', 'ref_table': 'refdata.regional_districts'},
                {'fk': 'id_regional_energy_system', 'ref_table': 'refdata.regional_energy_systems'}
            ]
        }
    ]
    
    # Копируем таблицы refdata с зависимостями
    for table_info in dependent_refdata_tables:
        table = table_info['table']
        
        try:
            # Копируем данные таблицы (пока со старыми FK)
            copied, mapping = _copy_table_with_mapping('refdata', table, source_version_id, target_version_id, user)
            total_copied += copied
            if mapping:
                id_mappings[f"refdata.{table}"] = mapping
            
            # Обновляем foreign key согласно зависимостям
            for dep in table_info['dependencies']:
                fk_column = dep['fk']
                ref_table = dep['ref_table']
                
                if ref_table in id_mappings:
                    ref_mapping = id_mappings[ref_table]
                    _update_foreign_keys_in_table(
                        'refdata', table, fk_column, ref_mapping, target_version_id, user
                    )
                    
        except Exception as e:
            current_app.logger.error(f"Ошибка копирования таблицы refdata.{table}: {e}")
            log_to_db(
                user,
                f"Ошибка копирования таблицы refdata.{table}",
                str(e),
                entity_type="database_version",
                entity_id=target_version_id
            )
    
    # ЭТАП 3: Копируем независимые таблицы generation
    log_to_db(
        user,
        "ЭТАП 3: Копирование независимых таблиц generation",
        f"Из версии {source_version_id} в версию {target_version_id}",
        entity_type="database_version",
        entity_id=target_version_id
    )
    
    # Независимые таблицы generation
    independent_generation_tables = [
        'gs_gen_station_groups',      # Группы станций - независимы
        'gs_gen_documents_kommod'     # Документы - независимы
    ]
    
    # Копируем независимые таблицы generation
    for table in independent_generation_tables:
        try:
            copied, mapping = _copy_table_with_mapping('generation', table, source_version_id, target_version_id, user)
            total_copied += copied
            if mapping:
                id_mappings[f"gs_gen.{table}"] = mapping
        except Exception as e:
            current_app.logger.error(f"Ошибка копирования таблицы gs_gen.{table}: {e}")
            log_to_db(
                user,
                f"Ошибка копирования таблицы gs_gen.{table}",
                str(e),
                entity_type="database_version",
                entity_id=target_version_id
            )
            # ВАЖНО: если произошла ошибка, откатываем транзакцию, чтобы не зависнуть в aborted state
            try:
                db.session.rollback()
            except Exception:
                pass
    
    # ЭТАП 4: Копируем таблицы generation С зависимостями
    log_to_db(
        user,
        "ЭТАП 4: Копирование таблиц generation с зависимостями",
        f"Из версии {source_version_id} в версию {target_version_id}",
        entity_type="database_version",
        entity_id=target_version_id
    )
    
    # Таблицы generation с зависимостями в порядке иерархии
    dependent_generation_tables = [
        {
            'schema': gen_schema,
            'table': 'gs_gen_stations',
            'dependencies': [
                {'fk': 'id_station_group', 'ref_table': f'{gen_schema}.gs_gen_station_groups'},
                {'fk': 'id_regional_district', 'ref_table': 'refdata.regional_districts'},
                {'fk': 'id_energy_unit', 'ref_table': 'refdata.energy_units'},
                {'fk': 'id_station_type', 'ref_table': 'refdata.station_types'},
                {'fk': 'id_condition_type', 'ref_table': 'refdata.condition_types'}
            ]
        },
        {
            'schema': gen_schema,
            'table': 'gs_gen_station_powers',
            'dependencies': [
                {'fk': 'id_station', 'ref_table': f'{gen_schema}.gs_gen_stations'}
            ]
        },
        {
            'schema': gen_schema,
            'table': 'gs_gen_machines',
            'dependencies': [
                {'fk': 'id_station', 'ref_table': f'{gen_schema}.gs_gen_stations'},
                {'fk': 'id_machine_type', 'ref_table': 'refdata.machine_types'},
                {'fk': 'id_tes_machine_type', 'ref_table': 'refdata.tes_machine_types'},
                {'fk': 'id_condition_type', 'ref_table': 'refdata.condition_types'},
                {'fk': 'id_gen_company', 'ref_table': 'refdata.gs_sys_companies'},
                {'fk': 'id_energy_area', 'ref_table': 'refdata.energy_areas'},
                {'fk': 'id_technology_availability', 'ref_table': 'refdata.technology_availabilities'},
                {'fk': 'id_technology_type', 'ref_table': 'refdata.technology_types'},
                {'fk': 'id_equipment_group', 'ref_table': 'refdata.equipment_groups'}
            ]
        },
        {
            'schema': gen_schema,
            'table': 'gs_gen_machine_powers',
            'dependencies': [
                {'fk': 'id_machine', 'ref_table': f'{gen_schema}.gs_gen_machines'}
            ]
        },
        {
            'schema': gen_schema,
            'table': 'gs_gen_machine_fuels',
            'dependencies': [
                {'fk': 'id_machine', 'ref_table': f'{gen_schema}.gs_gen_machines'},
                {'fk': 'id_fuel', 'ref_table': 'refdata.fuels'}
            ]
        },
        {
            'schema': gen_schema,
            'table': 'gs_gen_machine_tes_types',
            'dependencies': [
                {'fk': 'id_machine', 'ref_table': f'{gen_schema}.gs_gen_machines'},
                {'fk': 'id_tes_type', 'ref_table': 'refdata.tes_types'}
            ]
        },
        {
            'schema': gen_schema,
            'table': 'gs_gen_machine_names',
            'dependencies': [
                {'fk': 'id_machine', 'ref_table': f'{gen_schema}.gs_gen_machines'}
            ]
        },
        {
            'schema': gen_schema,
            'table': 'gs_gen_pgu_machines',
            'dependencies': [
                {'fk': 'id_parent_machine', 'ref_table': f'{gen_schema}.gs_gen_machines'},
                {'fk': 'id_pgu_tes_machine_type', 'ref_table': 'refdata.pgu_tes_machine_types'},
                {'fk': 'id_condition_type', 'ref_table': 'refdata.condition_types'}
            ]
        },
        {
            'schema': gen_schema,
            'table': 'gs_gen_pgu_machine_powers',
            'dependencies': [
                {'fk': 'id_pgu_machine', 'ref_table': f'{gen_schema}.gs_gen_pgu_machines'}
            ]
        },
        {
            'schema': gen_schema,
            'table': 'gs_gen_boilers',
            'dependencies': [
                {'fk': 'id_station', 'ref_table': f'{gen_schema}.gs_gen_stations'}
            ]
        }
    ]
    
    # Копируем таблицы generation с зависимостями
    for table_info in dependent_generation_tables:
        schema = table_info.get('schema', gen_schema)
        table = table_info['table']
        
        try:
            with db.session.begin_nested():
                # Копируем данные таблицы (пока со старыми FK)
                copied, mapping = _copy_table_with_mapping(schema, table, source_version_id, target_version_id, user)
                total_copied += copied
                if mapping:
                    id_mappings[f"{schema}.{table}"] = mapping
                
                # Обновляем foreign key согласно зависимостям
                for dep in table_info['dependencies']:
                    fk_column = dep['fk']
                    ref_table = dep['ref_table']
                    
                    if ref_table in id_mappings:
                        ref_mapping = id_mappings[ref_table]
                        _update_foreign_keys_in_table(
                            schema, table, fk_column, ref_mapping, target_version_id, user
                        )
                    
        except Exception as e:
            current_app.logger.error(f"Ошибка копирования таблицы gs_gen.{table}: {e}")
            log_to_db(
                user,
                f"Ошибка копирования таблицы gs_gen.{table}",
                str(e),
                entity_type="database_version",
                entity_id=target_version_id
            )
            # rollback() здесь делать нельзя: эта функция вызывается с do_commit=False
            # в рамках общей транзакции создания версии, и полный rollback откатит создание версии.
            # Используем begin_nested() выше, чтобы сбросить только неудачный этап.
    
    # Копирование ассоциативных таблиц (связей many-to-many)
    _copy_association_tables(source_version_id, target_version_id, id_mappings, user)
    
    # Коммитим только если do_commit=True
    if do_commit:
        db.session.commit()
        current_app.logger.info(f"✅ Commit выполнен после НОВОГО копирования данных")
        log_to_db(
            user,
            "НОВОЕ копирование данных версии завершено",
            f"Из версии {source_version_id} в версию {target_version_id}: всего скопировано {total_copied} записей",
            entity_type="database_version",
            entity_id=target_version_id
        )
    else:
        current_app.logger.info(f"ℹ️  Commit отложен, будет выполнен на уровне выше")


def _copy_table_with_mapping(schema, table, source_version_id, target_version_id, user):
    """
    Копирует данные из таблицы и создает соответствие старых и новых ID.
    
    Returns:
        tuple: (количество_скопированных_записей, словарь_соответствия_ID)
    """
    try:
        current_app.logger.info(f"Копирование таблицы {schema}.{table} из версии {source_version_id} в версию {target_version_id}")
        
        # Получаем список колонок (кроме id и database_version_id)
        columns_query = text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = :schema_name 
              AND table_name = :table_name
              AND column_name NOT IN ('id', 'database_version_id')
            ORDER BY ordinal_position
        """)
        
        result = db.session.execute(columns_query, {"schema_name": schema, "table_name": table})
        columns = [row[0] for row in result]
        
        if not columns:
            current_app.logger.warning(f"Таблица {schema}.{table}: нет колонок для копирования")
            return 0, {}
        
        columns_str = ", ".join(columns)
        
        # Определяем WHERE условие для источника
        if source_version_id is None:
            where_clause = "database_version_id IS NULL"
        else:
            where_clause = f"database_version_id = {source_version_id}"
        
        # Копируем данные с возвратом ID для создания соответствия
        # Важно: используем CTID для сохранения порядка
        copy_query = text(f"""
            WITH source_data AS (
                SELECT {columns_str}, id as old_id
                FROM {schema}.{table}
                WHERE {where_clause}
                ORDER BY id
            )
            INSERT INTO {schema}.{table} ({columns_str}, database_version_id)
            SELECT {columns_str}, :target_version_id
            FROM source_data
            ORDER BY old_id
            RETURNING id
        """)
        
        current_app.logger.info(f"Выполнение запроса копирования для таблицы {schema}.{table}")
        result = db.session.execute(copy_query, {"target_version_id": target_version_id})
        new_ids = [row[0] for row in result]
        db.session.flush()
        
        # Получаем старые ID в том же порядке
        old_ids_query = text(f"""
            SELECT id FROM {schema}.{table} WHERE {where_clause} ORDER BY id
        """)
        old_ids_result = db.session.execute(old_ids_query)
        old_ids = [row[0] for row in old_ids_result]
        
        # Создаем соответствие старых и новых ID
        mapping = {}
        if len(old_ids) == len(new_ids):
            mapping = dict(zip(old_ids, new_ids))
            current_app.logger.info(f"Создано соответствие для {schema}.{table}: {len(mapping)} записей")
        else:
            current_app.logger.warning(f"Несоответствие количества ID для {schema}.{table}: старых={len(old_ids)}, новых={len(new_ids)}")
            # Создаем частичное соответствие
            min_len = min(len(old_ids), len(new_ids))
            if min_len > 0:
                mapping = dict(zip(old_ids[:min_len], new_ids[:min_len]))
                current_app.logger.warning(f"Создано частичное соответствие для {schema}.{table}: {len(mapping)} записей")
        
        copied = len(new_ids)
        
        current_app.logger.info(f"Таблица {schema}.{table}: скопировано {copied} записей")
        
        if copied > 0:
            log_to_db(
                user,
                f"Скопированы данные таблицы {schema}.{table}",
                f"Из версии {source_version_id} в версию {target_version_id}: {copied} записей",
                entity_type="database_version",
                entity_id=target_version_id
            )
        else:
            current_app.logger.info(f"Таблица {schema}.{table}: нет данных для копирования (WHERE {where_clause})")
        
        return copied, mapping
        
    except Exception as e:
        current_app.logger.error(f"Ошибка копирования таблицы {schema}.{table}: {e}")
        raise


def _update_foreign_keys_in_table(schema, table, fk_column, ref_mapping, target_version_id, user):
    """
    Обновляет foreign key в таблице согласно соответствию ID.
    
    Args:
        schema: Схема таблицы
        table: Имя таблицы
        fk_column: Имя колонки с foreign key
        ref_mapping: Словарь соответствия {старый_id: новый_id}
        target_version_id: ID целевой версии
        user: Пользователь для логирования
    """
    try:
        if not ref_mapping:
            return
        
        # Создаем временную таблицу с маппингом
        temp_table_name = f"fk_mapping_{abs(hash(f'{schema}.{table}.{fk_column}')) % 100000}"
        
        try:
            # Создаем временную таблицу
            create_temp = text(f"""
                CREATE TEMP TABLE {temp_table_name} (
                    old_fk INTEGER PRIMARY KEY,
                    new_fk INTEGER
                )
            """)
            db.session.execute(create_temp)
            
            # Индекс для ускорения поиска
            create_index = text(f"""
                CREATE INDEX idx_{temp_table_name}_old_fk 
                ON {temp_table_name} (old_fk)
            """)
            db.session.execute(create_index)
            
            # Вставляем данные о соответствии FK
            insert_data = [(old_fk, new_fk) for old_fk, new_fk in ref_mapping.items()]
            
            if insert_data:
                # Вставляем данные батчами
                batch_size = 1000
                for i in range(0, len(insert_data), batch_size):
                    batch = insert_data[i:i + batch_size]
                    # Используем executemany для вставки батчей
                    insert_query = text(f"""
                        INSERT INTO {temp_table_name} (old_fk, new_fk) 
                        VALUES (:old_fk, :new_fk)
                        ON CONFLICT (old_fk) DO NOTHING
                    """)
                    # Преобразуем список кортежей в список словарей
                    param_rows = [{"old_fk": old_fk, "new_fk": new_fk} for old_fk, new_fk in batch]
                    db.session.execute(insert_query, param_rows)
                
                # Обновляем foreign key
                update_query = text(f"""
                    UPDATE {schema}.{table} 
                    SET {fk_column} = t.new_fk
                    FROM {temp_table_name} t
                    WHERE {schema}.{table}.database_version_id = :target_version_id
                      AND {schema}.{table}.{fk_column} = t.old_fk
                """)
                result = db.session.execute(update_query, {"target_version_id": target_version_id})
                updated_count = result.rowcount
                
                current_app.logger.info(
                    f"Обновлено {updated_count} foreign key {fk_column} в таблице {schema}.{table}"
                )
        
        finally:
            # Удаляем временную таблицу
            try:
                drop_temp = text(f"DROP TABLE IF EXISTS {temp_table_name}")
                db.session.execute(drop_temp)
            except:
                pass
        
    except Exception as e:
        current_app.logger.error(
            f"Ошибка обновления foreign key {fk_column} в таблице {schema}.{table}: {e}"
        )
        log_to_db(
            user,
            f"Ошибка обновления foreign key {fk_column} в таблице {schema}.{table}",
            str(e),
            entity_type="database_version",
            entity_id=target_version_id
        )
        # Важно: пробрасываем исключение, иначе транзакция остается в состоянии aborted
        # и последующие запросы падают с InFailedSqlTransaction
        raise


def _copy_version_data(source_version_id, target_version_id, user, do_commit=True):
    """
    Копирует все данные из source_version_id в target_version_id с правильным обновлением связей.
    
    Args:
        source_version_id: ID версии-источника (или None для данных без версии)
        target_version_id: ID целевой версии
        user: Пользователь для логирования
        do_commit: Выполнять ли commit после копирования (по умолчанию True)
    """
    log_to_db(
        user,
        f"Начало копирования данных из версии {source_version_id} в версию {target_version_id}",
        "",
        entity_type="database_version",
        entity_id=target_version_id
    )
    
    gen_schema = SCHEMA_GENERATION
    fuel_schema = SCHEMA_FUEL

    # Таблицы для копирования из схемы generation (в порядке зависимостей)
    # ВАЖНО: Порядок должен соответствовать иерархии зависимостей!
    generation_tables = [
        'gs_gen_station_groups',            # 1. Сначала группы станций (независимые)
        'gs_gen_stations',                  # 2. Затем станции (зависят от групп станций)
        'gs_gen_station_powers',            # 5. Мощности станций (зависят от станций)
        'gs_gen_machines',                  # 6. Машины (зависят от станций)
        'gs_gen_machine_powers',            # 7. Мощности машин (зависят от машин)
        'gs_gen_machine_fuels',             # 8. Топливо машин (зависят от машин)
        'gs_gen_machine_tes_types',         # 9. Типы ТЭС машин (зависят от машин)
        'gs_gen_machine_names',             # 9a. Названия агрегатов по годам (зависят от машин)
        'gs_gen_pgu_machines',              # 10. ПГУ машины (зависят от машин)
        'gs_gen_pgu_machine_powers',        # 11. Мощности ПГУ машин (зависят от ПГУ машин)
        'gs_gen_boilers',                   # 12. Котлы (зависят от станций)
        'gs_gen_documents_kommod'           # 13. Документы (независимые)
    ]

    fuel_tables = []
    
    # Таблицы для копирования из схемы refdata
    refdata_tables = [
        #  Справочники для станций
        'station_types',
        'machine_types',
        'tes_types',
        'tes_machine_types',
        'pgu_tes_machine_types',
        'condition_types',
        'technology_types',
        'technology_availabilities',
        'equipment_groups',
        # Энергосистемы
        'energy_system_types',
        'union_energy_systems',
        'synchronous_areas',
        'energy_areas',
        'energy_zones',
        'energy_units',
        'regional_energy_systems',
        # Территории
        'federal_districts',
        'regional_districts',
        # Генерирующие компании
        'gs_sys_companies',
        # Топливо
        'fuel_categories',
        'fuel_types',
        'fuels',
        # Годы и год features теперь версионируются
        'year_features',
        'years',
    ]
    
    # Объединяем списки таблиц со схемами
    tables_to_copy = (
        [(gen_schema, table) for table in generation_tables]
        + [(fuel_schema, table) for table in fuel_tables]
        + [("refdata", table) for table in refdata_tables]
    )
    
    total_copied = 0
    
    # Словарь для хранения соответствий старых и новых ID
    id_mappings = {}
    
    for schema, table in tables_to_copy:
        try:
            current_app.logger.info(f"Копирование таблицы {schema}.{table} из версии {source_version_id} в версию {target_version_id}")
            
            # Получаем список колонок (кроме id и database_version_id)
            columns_query = text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_schema = :schema_name 
                  AND table_name = :table_name
                  AND column_name NOT IN ('id', 'database_version_id')
                ORDER BY ordinal_position
            """)
            
            result = db.session.execute(columns_query, {"schema_name": schema, "table_name": table})
            columns = [row[0] for row in result]
            
            if not columns:
                current_app.logger.warning(f"Таблица {schema}.{table}: нет колонок для копирования")
                continue
            
            columns_str = ", ".join(columns)
            
            # Определяем WHERE условие для источника
            if source_version_id is None:
                where_clause = "database_version_id IS NULL"
            else:
                where_clause = f"database_version_id = {source_version_id}"
            
            # Копируем данные с возвратом ID для обновления связей
            copy_query = text(f"""
                INSERT INTO {schema}.{table} ({columns_str}, database_version_id)
                SELECT {columns_str}, :target_version_id
                FROM {schema}.{table}
                WHERE {where_clause}
                RETURNING id
            """)
            
            current_app.logger.info(f"Выполнение запроса копирования для таблицы {schema}.{table}")
            result = db.session.execute(copy_query, {"target_version_id": target_version_id})
            new_ids = [row[0] for row in result]
            db.session.flush()
            
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Получаем старые ID в том же порядке, что и новые
            # Используем тот же запрос с RETURNING, но без RETURNING для получения старых ID
            old_ids_query = text(f"""
                SELECT id FROM {schema}.{table} WHERE {where_clause} ORDER BY id
            """)
            old_ids_result = db.session.execute(old_ids_query)
            old_ids = [row[0] for row in old_ids_result]
            
            # Создаем соответствие старых и новых ID
            if len(old_ids) == len(new_ids):
                table_mapping = dict(zip(old_ids, new_ids))
                id_mappings[f"{schema}.{table}"] = table_mapping
                current_app.logger.info(f"Создано соответствие для {schema}.{table}: {len(table_mapping)} записей")
                
                # Дополнительная проверка для отладки
                if len(table_mapping) > 0:
                    sample_old_id = list(table_mapping.keys())[0]
                    sample_new_id = table_mapping[sample_old_id]
                    current_app.logger.info(f"Пример соответствия {schema}.{table}: {sample_old_id} -> {sample_new_id}")
            else:
                current_app.logger.warning(f"Несоответствие количества ID для {schema}.{table}: старых={len(old_ids)}, новых={len(new_ids)}")
                # Создаем частичное соответствие
                min_len = min(len(old_ids), len(new_ids))
                if min_len > 0:
                    table_mapping = dict(zip(old_ids[:min_len], new_ids[:min_len]))
                    id_mappings[f"{schema}.{table}"] = table_mapping
                    current_app.logger.warning(f"Создано частичное соответствие для {schema}.{table}: {len(table_mapping)} записей")
            
            copied = len(new_ids)
            total_copied += copied
            
            current_app.logger.info(f"Таблица {schema}.{table}: скопировано {copied} записей")
            
            if copied > 0:
                log_to_db(
                    user,
                    f"Скопированы данные таблицы {schema}.{table}",
                    f"Из версии {source_version_id} в версию {target_version_id}: {copied} записей",
                    entity_type="database_version",
                    entity_id=target_version_id
                )
            else:
                current_app.logger.info(f"Таблица {schema}.{table}: нет данных для копирования (WHERE {where_clause})")
        except Exception as e:
            log_to_db(
                user,
                f"Ошибка копирования таблицы {schema}.{table}",
                f"Из версии {source_version_id} в версию {target_version_id}: {str(e)}",
                entity_type="database_version",
                entity_id=target_version_id
            )
            # Откатываем транзакцию и продолжаем копирование других таблиц
            try:
                db.session.rollback()
            except Exception:
                pass
    
    # Обновляем связи между таблицами (используем молниеносную версию)
    _update_version_relationships_lightning_fast(id_mappings, target_version_id, user)
    
    # Доп. шаг: перепривязка refdata.fuels.id_fuel_type к fuel_types целевой версии
    # 1) по маппингу ID (если есть), 2) резервно по name
    try:
        from sqlalchemy import text as _text
        updated_rows_total = 0

        ft_mapping = id_mappings.get(('refdata', 'fuel_types')) or {}
        if ft_mapping:
            current_app.logger.info("🔧 Перепривязка fuels по маппингу ID fuel_types...")
            temp_tbl = f"tmp_map_ft_{target_version_id}"
            db.session.execute(_text(f"DROP TABLE IF EXISTS {temp_tbl}"))
            db.session.execute(_text(
                f"CREATE TEMP TABLE {temp_tbl} (old_id INTEGER PRIMARY KEY, new_id INTEGER NOT NULL)"
            ))
            rows = [(old_id, new_id) for old_id, new_id in ft_mapping.items()]
            batch_size = 1000
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i+batch_size]
                db.session.execute(
                    _text(f"INSERT INTO {temp_tbl} (old_id, new_id) VALUES (:old_id, :new_id) ON CONFLICT (old_id) DO NOTHING"),
                    [{"old_id": o, "new_id": n} for o, n in batch]
                )
            result = db.session.execute(_text(
                f"""
                UPDATE refdata.fuels f
                SET id_fuel_type = m.new_id
                FROM {temp_tbl} m
                WHERE f.database_version_id = :target_version_id
                  AND f.id_fuel_type = m.old_id
                  AND f.id_fuel_type IS DISTINCT FROM m.new_id
                """
            ), {"target_version_id": target_version_id})
            updated_rows_total += result.rowcount or 0
            db.session.execute(_text(f"DROP TABLE IF EXISTS {temp_tbl}"))

        if updated_rows_total == 0:
            current_app.logger.info("🔧 Перепривязка fuels по name fuel_types (резервный путь)...")
            relink_sql = _text(
                """
                WITH map AS (
                    SELECT f.id AS fuel_id, ft_new.id AS new_ft_id
                    FROM refdata.fuels f
                    JOIN refdata.fuel_types ft_old ON ft_old.id = f.id_fuel_type
                    JOIN refdata.fuel_types ft_new
                      ON ft_new.name = ft_old.name
                     AND ft_new.database_version_id = f.database_version_id
                    WHERE f.database_version_id = :target_version_id
                )
                UPDATE refdata.fuels f
                SET id_fuel_type = m.new_ft_id
                FROM map m
                WHERE f.id = m.fuel_id
                  AND f.id_fuel_type IS DISTINCT FROM m.new_ft_id;
                """
            )
            result = db.session.execute(relink_sql, {"target_version_id": target_version_id})
            updated_rows_total += result.rowcount or 0

        current_app.logger.info(f"  ✓ Обновлено связей fuels.id_fuel_type: {updated_rows_total}")

        check_sql = _text(
            """
            SELECT COUNT(*)
            FROM refdata.fuels f
            LEFT JOIN refdata.fuel_types ft
              ON ft.id = f.id_fuel_type
             AND ft.database_version_id = f.database_version_id
            WHERE f.database_version_id = :target_version_id
              AND ft.id IS NULL;
            """
        )
        not_mapped_cnt = db.session.execute(check_sql, {"target_version_id": target_version_id}).scalar()
        if not_mapped_cnt and not_mapped_cnt > 0:
            current_app.logger.warning(f"  ⚠️ Осталось непривязанных строк в refdata.fuels: {not_mapped_cnt}")
        else:
            current_app.logger.info("  ✓ Все строки refdata.fuels корректно привязаны к fuel_types целевой версии")
    except Exception as e:
        current_app.logger.error(f"  ❌ Ошибка перепривязки fuels.id_fuel_type: {e}")

    # Доп. шаг: перепривязка refdata.union_energy_systems.id_energy_system_type к energy_system_types целевой версии
    # 1) Пытаемся использовать точный маппинг ID из процесса копирования (надежнее и быстрее)
    # 2) Если маппинга нет, резервно используем сопоставление по name
    try:
        from sqlalchemy import text as _text
        updated_rows_total = 0

        est_mapping = id_mappings.get(('refdata', 'energy_system_types')) or {}
        if est_mapping:
            current_app.logger.info("🔧 Перепривязка UES по маппингу ID energy_system_types...")
            # Создаем временную таблицу для маппинга
            temp_tbl = f"tmp_map_est_{target_version_id}"
            db.session.execute(_text(f"DROP TABLE IF EXISTS {temp_tbl}"))
            db.session.execute(_text(
                f"CREATE TEMP TABLE {temp_tbl} (old_id INTEGER PRIMARY KEY, new_id INTEGER NOT NULL)"
            ))
            # Вставляем батчами
            if est_mapping:
                rows = [(old_id, new_id) for old_id, new_id in est_mapping.items()]
                batch_size = 1000
                for i in range(0, len(rows), batch_size):
                    batch = rows[i:i+batch_size]
                    db.session.execute(
                        _text(f"INSERT INTO {temp_tbl} (old_id, new_id) VALUES (:old_id, :new_id) ON CONFLICT (old_id) DO NOTHING"),
                        [{"old_id": o, "new_id": n} for o, n in batch]
                    )
            # Обновляем FK в union_energy_systems
            result = db.session.execute(_text(
                f"""
                UPDATE refdata.union_energy_systems ues
                SET id_energy_system_type = m.new_id
                FROM {temp_tbl} m
                WHERE ues.database_version_id = :target_version_id
                  AND ues.id_energy_system_type = m.old_id
                  AND ues.id_energy_system_type IS DISTINCT FROM m.new_id
                """
            ), {"target_version_id": target_version_id})
            updated_rows_total += result.rowcount or 0
            db.session.execute(_text(f"DROP TABLE IF EXISTS {temp_tbl}"))

        # Резервный путь по name (на случай отсутствия маппинга)
        if updated_rows_total == 0:
            current_app.logger.info("🔧 Перепривязка UES по name energy_system_types (резервный путь)...")
            relink_ues_sql = _text(
                """
                WITH map AS (
                    SELECT ues.id AS ues_id, est_new.id AS new_type_id
                    FROM refdata.union_energy_systems ues
                    JOIN refdata.energy_system_types est_old ON est_old.id = ues.id_energy_system_type
                    JOIN refdata.energy_system_types est_new
                      ON est_new.name = est_old.name
                     AND est_new.database_version_id = ues.database_version_id
                    WHERE ues.database_version_id = :target_version_id
                )
                UPDATE refdata.union_energy_systems ues
                SET id_energy_system_type = m.new_type_id
                FROM map m
                WHERE ues.id = m.ues_id
                  AND ues.id_energy_system_type IS DISTINCT FROM m.new_type_id;
                """
            )
            result = db.session.execute(relink_ues_sql, {"target_version_id": target_version_id})
            updated_rows_total += result.rowcount or 0

        current_app.logger.info(f"  ✓ Обновлено связей union_energy_systems.id_energy_system_type: {updated_rows_total}")

        check_ues_sql = _text(
            """
            SELECT COUNT(*)
            FROM refdata.union_energy_systems ues
            LEFT JOIN refdata.energy_system_types est
              ON est.id = ues.id_energy_system_type
             AND est.database_version_id = ues.database_version_id
            WHERE ues.database_version_id = :target_version_id
              AND est.id IS NULL;
            """
        )
        not_mapped_cnt = db.session.execute(check_ues_sql, {"target_version_id": target_version_id}).scalar()
        if not_mapped_cnt and not_mapped_cnt > 0:
            current_app.logger.warning(f"  ⚠️ Осталось непривязанных строк в refdata.union_energy_systems: {not_mapped_cnt}")
        else:
            current_app.logger.info("  ✓ Все строки refdata.union_energy_systems корректно привязаны к energy_system_types целевой версии")
    except Exception as e:
        current_app.logger.error(f"  ❌ Ошибка перепривязки union_energy_systems.id_energy_system_type: {e}")

    # Коммитим только если do_commit=True
    if do_commit:
        db.session.commit()
        current_app.logger.info(f"✅ Commit выполнен после копирования данных")
        # Логируем ПОСЛЕ commit, когда транзакция завершена
        log_to_db(
            user,
            "Копирование данных версии завершено",
            f"Из версии {source_version_id} в версию {target_version_id}: всего скопировано {total_copied} записей",
            entity_type="database_version",
            entity_id=target_version_id
        )
    else:
        current_app.logger.info(f"ℹ️  Commit отложен, будет выполнен на уровне выше")
        # НЕ логируем в БД, пока транзакция не завершена - это вызовет конфликт!


def _update_version_relationships(id_mappings, target_version_id, user):
    """
    Обновляет связи между таблицами после копирования версии.
    ОПТИМИЗИРОВАННАЯ ВЕРСИЯ: использует батчинг и CASE WHEN для улучшения производительности.
    
    Args:
        id_mappings: Словарь соответствий старых и новых ID по таблицам
        target_version_id: ID целевой версии
        user: Пользователь для логирования
    """
    current_app.logger.info("Начало обновления связей между таблицами (оптимизированная версия)")
    
    # Определяем связи, которые нужно обновить в правильном порядке
    relationships = [
        # 1. machines -> stations
        {
            'table': 'gs_gen.gs_gen_machines',
            'foreign_key': 'id_station',
            'reference_table': 'gs_gen.gs_gen_stations'
        },
        # 2. machine_powers -> machines
        {
            'table': 'gs_gen.gs_gen_machine_powers',
            'foreign_key': 'id_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 3. machine_fuels -> machines
        {
            'table': 'gs_gen.gs_gen_machine_fuels',
            'foreign_key': 'id_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 4. machine_tes_types -> machines
        {
            'table': 'gs_gen.gs_gen_machine_tes_types',
            'foreign_key': 'id_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 5. pgu_machines -> machines (используем id_parent_machine)
        {
            'table': 'gs_gen.gs_gen_pgu_machines',
            'foreign_key': 'id_parent_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 6. pgu_machine_powers -> pgu_machines
        {
            'table': 'gs_gen.gs_gen_pgu_machine_powers',
            'foreign_key': 'id_pgu_machine',
            'reference_table': 'gs_gen.gs_gen_pgu_machines'
        },
        # 7. stations -> station_groups
        {
            'table': 'gs_gen.gs_gen_stations',
            'foreign_key': 'id_station_group',
            'reference_table': 'gs_gen.gs_gen_station_groups'
        },
        # 8. station_powers -> stations
        {
            'table': 'gs_gen.gs_gen_station_powers',
            'foreign_key': 'id_station',
            'reference_table': 'gs_gen.gs_gen_stations'
        },
        # 9. boilers -> stations
        {
            'table': 'gs_gen.gs_gen_boilers',
            'foreign_key': 'id_station',
            'reference_table': 'gs_gen.gs_gen_stations'
        }
    ]
    
    total_updated = 0
    
    for rel in relationships:
        try:
            table_key = rel['table']
            if table_key not in id_mappings:
                current_app.logger.warning(f"Таблица {table_key} не найдена в соответствиях ID")
                continue
            
            ref_table_key = rel['reference_table']
            if ref_table_key not in id_mappings:
                current_app.logger.warning(f"Справочная таблица {ref_table_key} не найдена в соответствиях ID")
                continue
            
            table_mapping = id_mappings[table_key]
            ref_table_mapping = id_mappings[ref_table_key]
            
            # ОПТИМИЗАЦИЯ: Используем один запрос с CASE WHEN вместо множественных UPDATE
            if not table_mapping or not ref_table_mapping:
                current_app.logger.info(f"Пропуск таблицы {table_key}: нет данных для обновления")
                continue
            
            # Строим CASE WHEN для обновления foreign_key
            case_statements = []
            id_list = list(table_mapping.keys())
            
            # Получаем все записи одной таблицы одним запросом
            get_records_query = text(f"""
                SELECT id, {rel['foreign_key']} 
                FROM {rel['table']} 
                WHERE database_version_id = :target_version_id
            """)
            result = db.session.execute(get_records_query, {"target_version_id": target_version_id})
            records = result.fetchall()
            
            if not records:
                current_app.logger.info(f"Таблица {table_key}: нет записей для обновления")
                continue
            
            # Строим CASE WHEN для массового обновления
            case_when_parts = []
            update_ids = []
            
            for record_id, old_fk_value in records:
                if old_fk_value and old_fk_value in ref_table_mapping:
                    new_fk_value = ref_table_mapping[old_fk_value]
                    case_when_parts.append(f"WHEN id = {record_id} THEN {new_fk_value}")
                    update_ids.append(record_id)
            
            if not case_when_parts:
                current_app.logger.info(f"Таблица {table_key}: нет связей для обновления")
                continue
            
            # Выполняем массовое обновление одним запросом
            case_when_sql = " ".join(case_when_parts)
            ids_sql = ",".join(map(str, update_ids))
            
            batch_update_query = text(f"""
                UPDATE {rel['table']} 
                SET {rel['foreign_key']} = CASE 
                    {case_when_sql}
                END
                WHERE id IN ({ids_sql}) AND database_version_id = :target_version_id
            """)
            
            result = db.session.execute(batch_update_query, {"target_version_id": target_version_id})
            updated_count = result.rowcount
            total_updated += updated_count
            
            current_app.logger.info(f"Таблица {table_key}: обновлено {updated_count} связей одним запросом")
            
        except Exception as e:
            current_app.logger.error(f"Ошибка обновления связей для {rel['table']}: {str(e)}")
            log_to_db(
                user,
                f"Ошибка обновления связей для {rel['table']}",
                str(e),
                entity_type="database_version",
                entity_id=target_version_id
            )
    
    current_app.logger.info(f"Обновление связей завершено: {total_updated} связей обновлено")
    log_to_db(
        user,
        "Обновление связей между таблицами завершено (оптимизированная версия)",
        f"Обновлено связей: {total_updated}",
        entity_type="database_version",
        entity_id=target_version_id
    )


def _update_version_relationships_ultra_fast(id_mappings, target_version_id, user):
    """
    УЛЬТРА-БЫСТРАЯ версия обновления связей между таблицами.
    Использует временные таблицы и JOIN для максимальной производительности.
    
    Args:
        id_mappings: Словарь соответствий старых и новых ID по таблицам
        target_version_id: ID целевой версии
        user: Пользователь для логирования
    """
    current_app.logger.info("Начало обновления связей между таблицами (ультра-быстрая версия)")
    
    # Определяем связи, которые нужно обновить в правильном порядке
    relationships = [
        # 1. machines -> stations
        {
            'table': 'gs_gen.gs_gen_machines',
            'foreign_key': 'id_station',
            'reference_table': 'gs_gen.gs_gen_stations'
        },
        # 2. machine_powers -> machines
        {
            'table': 'gs_gen.gs_gen_machine_powers',
            'foreign_key': 'id_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 3. machine_fuels -> machines
        {
            'table': 'gs_gen.gs_gen_machine_fuels',
            'foreign_key': 'id_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 4. machine_tes_types -> machines
        {
            'table': 'gs_gen.gs_gen_machine_tes_types',
            'foreign_key': 'id_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 5. pgu_machines -> machines (используем id_parent_machine)
        {
            'table': 'gs_gen.gs_gen_pgu_machines',
            'foreign_key': 'id_parent_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 6. pgu_machine_powers -> pgu_machines
        {
            'table': 'gs_gen.gs_gen_pgu_machine_powers',
            'foreign_key': 'id_pgu_machine',
            'reference_table': 'gs_gen.gs_gen_pgu_machines'
        },
        # 7. stations -> station_groups
        {
            'table': 'gs_gen.gs_gen_stations',
            'foreign_key': 'id_station_group',
            'reference_table': 'gs_gen.gs_gen_station_groups'
        },
        # 8. station_powers -> stations
        {
            'table': 'gs_gen.gs_gen_station_powers',
            'foreign_key': 'id_station',
            'reference_table': 'gs_gen.gs_gen_stations'
        },
        # 9. boilers -> stations
        {
            'table': 'gs_gen.gs_gen_boilers',
            'foreign_key': 'id_station',
            'reference_table': 'gs_gen.gs_gen_stations'
        }
    ]
    
    total_updated = 0
    
    for rel in relationships:
        try:
            table_key = rel['table']
            if table_key not in id_mappings:
                continue
            
            ref_table_key = rel['reference_table']
            if ref_table_key not in id_mappings:
                continue
            
            table_mapping = id_mappings[table_key]
            ref_table_mapping = id_mappings[ref_table_key]
            
            if not table_mapping or not ref_table_mapping:
                continue
            
            # Создаем временную таблицу с маппингом ID
            temp_table_name = f"temp_id_mapping_{hash(table_key) % 10000}"
            
            # Создаем временную таблицу
            create_temp_table = text(f"""
                CREATE TEMP TABLE {temp_table_name} (
                    old_id INTEGER,
                    new_id INTEGER,
                    old_fk INTEGER,
                    new_fk INTEGER
                )
            """)
            db.session.execute(create_temp_table)
            
            # Заполняем временную таблицу данными для обновления
            insert_data = []
            for old_id, new_id in table_mapping.items():
                # Получаем old_fk из исходных данных
                if old_id in ref_table_mapping:
                    old_fk = old_id
                    new_fk = ref_table_mapping[old_id]
                    insert_data.append((old_id, new_id, old_fk, new_fk))
            
            if insert_data:
                # Вставляем данные в временную таблицу
                insert_query = text(f"""
                    INSERT INTO {temp_table_name} (old_id, new_id, old_fk, new_fk) 
                    VALUES {','.join(['(%s, %s, %s, %s)'] * len(insert_data))}
                """)
                db.session.execute(insert_query, [item for sublist in insert_data for item in sublist])
                
                # Выполняем массовое обновление через JOIN с временной таблицей
                update_query = text(f"""
                    UPDATE {rel['table']} 
                    SET {rel['foreign_key']} = t.new_fk
                    FROM {temp_table_name} t
                    WHERE {rel['table']}.id = t.new_id 
                      AND {rel['table']}.database_version_id = :target_version_id
                      AND {rel['table']}.{rel['foreign_key']} = t.old_fk
                """)
                
                result = db.session.execute(update_query, {"target_version_id": target_version_id})
                updated_count = result.rowcount
                total_updated += updated_count
                
                current_app.logger.info(f"Таблица {table_key}: обновлено {updated_count} связей через временную таблицу")
            
            # Удаляем временную таблицу
            drop_temp_table = text(f"DROP TABLE {temp_table_name}")
            db.session.execute(drop_temp_table)
            
        except Exception as e:
            current_app.logger.error(f"Ошибка обновления связей для {rel['table']}: {str(e)}")
            log_to_db(
                user,
                f"Ошибка обновления связей для {rel['table']}",
                str(e),
                entity_type="database_version",
                entity_id=target_version_id
            )
    
    current_app.logger.info(f"Ультра-быстрое обновление связей завершено: {total_updated} связей обновлено")
    log_to_db(
        user,
        "Ультра-быстрое обновление связей между таблицами завершено",
        f"Обновлено связей: {total_updated}",
        entity_type="database_version",
        entity_id=target_version_id
    )


def _update_version_relationships_ultra_optimized(id_mappings, target_version_id, user):
    """
    УЛЬТРА-ОПТИМИЗИРОВАННАЯ версия обновления связей.
    Использует минимальное количество запросов и исправляет ошибки схемы.
    
    Args:
        id_mappings: Словарь соответствий старых и новых ID по таблицам
        target_version_id: ID целевой версии
        user: Пользователь для логирования
    """
    current_app.logger.info("Начало ультра-оптимизированного обновления связей между таблицами")
    
    # Определяем связи с правильными именами колонок в правильном порядке
    relationships = [
        # 1. machines -> stations
        {
            'table': 'gs_gen.gs_gen_machines',
            'foreign_key': 'id_station',
            'reference_table': 'gs_gen.gs_gen_stations'
        },
        # 2. machine_powers -> machines
        {
            'table': 'gs_gen.gs_gen_machine_powers',
            'foreign_key': 'id_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 3. machine_fuels -> machines
        {
            'table': 'gs_gen.gs_gen_machine_fuels',
            'foreign_key': 'id_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 4. machine_tes_types -> machines
        {
            'table': 'gs_gen.gs_gen_machine_tes_types',
            'foreign_key': 'id_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 5. pgu_machines -> machines (используем id_parent_machine)
        {
            'table': 'gs_gen.gs_gen_pgu_machines',
            'foreign_key': 'id_parent_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 6. pgu_machine_powers -> pgu_machines
        {
            'table': 'gs_gen.gs_gen_pgu_machine_powers',
            'foreign_key': 'id_pgu_machine',
            'reference_table': 'gs_gen.gs_gen_pgu_machines'
        },
        # 7. stations -> station_groups
        {
            'table': 'gs_gen.gs_gen_stations',
            'foreign_key': 'id_station_group',
            'reference_table': 'gs_gen.gs_gen_station_groups'
        },
        # 8. station_powers -> stations
        {
            'table': 'gs_gen.gs_gen_station_powers',
            'foreign_key': 'id_station',
            'reference_table': 'gs_gen.gs_gen_stations'
        },
        # 9. boilers -> stations
        {
            'table': 'gs_gen.gs_gen_boilers',
            'foreign_key': 'id_station',
            'reference_table': 'gs_gen.gs_gen_stations'
        }
    ]
    
    total_updated = 0
    
    for rel in relationships:
        try:
            table_key = rel['table']
            if table_key not in id_mappings:
                current_app.logger.info(f"Пропуск таблицы {table_key}: нет данных в id_mappings")
                continue
            
            ref_table_key = rel['reference_table']
            if ref_table_key not in id_mappings:
                current_app.logger.info(f"Пропуск таблицы {table_key}: нет справочной таблицы {ref_table_key}")
                continue
            
            table_mapping = id_mappings[table_key]
            ref_table_mapping = id_mappings[ref_table_key]
            
            if not table_mapping or not ref_table_mapping:
                current_app.logger.info(f"Пропуск таблицы {table_key}: пустые маппинги")
                continue
            
            # УЛЬТРА-ОПТИМИЗАЦИЯ: Один запрос с JOIN для обновления всех связей
            # Создаем временную таблицу с маппингом
            temp_table_name = f"temp_mapping_{abs(hash(table_key)) % 100000}"
            
            try:
                # Создаем временную таблицу
                create_temp = text(f"""
                    CREATE TEMP TABLE {temp_table_name} (
                        old_id INTEGER,
                        new_id INTEGER,
                        old_fk INTEGER,
                        new_fk INTEGER
                    )
                """)
                db.session.execute(create_temp)
                
                # Подготавливаем данные для вставки
                insert_data = []
                for old_id, new_id in table_mapping.items():
                    if old_id in ref_table_mapping:
                        old_fk = old_id
                        new_fk = ref_table_mapping[old_id]
                        insert_data.append((old_id, new_id, old_fk, new_fk))
                
                if not insert_data:
                    current_app.logger.info(f"Таблица {table_key}: нет связей для обновления")
                    continue
                
                # Вставляем данные батчами по 1000 записей
                batch_size = 1000
                for i in range(0, len(insert_data), batch_size):
                    batch = insert_data[i:i + batch_size]
                    placeholders = ','.join(['(%s, %s, %s, %s)'] * len(batch))
                    insert_query = text(f"""
                        INSERT INTO {temp_table_name} (old_id, new_id, old_fk, new_fk) 
                        VALUES {placeholders}
                    """)
                    flat_data = [item for sublist in batch for item in sublist]
                    db.session.execute(insert_query, flat_data)
                
                # Один запрос для обновления всех связей через JOIN
                update_query = text(f"""
                    UPDATE {rel['table']} 
                    SET {rel['foreign_key']} = t.new_fk
                    FROM {temp_table_name} t
                    WHERE {rel['table']}.id = t.new_id 
                      AND {rel['table']}.database_version_id = :target_version_id
                      AND {rel['table']}.{rel['foreign_key']} = t.old_fk
                """)
                
                result = db.session.execute(update_query, {"target_version_id": target_version_id})
                updated_count = result.rowcount
                total_updated += updated_count
                
                current_app.logger.info(f"Таблица {table_key}: обновлено {updated_count} связей одним JOIN запросом")
                
            finally:
                # Удаляем временную таблицу
                try:
                    drop_temp = text(f"DROP TABLE IF EXISTS {temp_table_name}")
                    db.session.execute(drop_temp)
                except:
                    pass  # Игнорируем ошибки удаления
            
        except Exception as e:
            current_app.logger.error(f"Ошибка обновления связей для {rel['table']}: {str(e)}")
            log_to_db(
                user,
                f"Ошибка обновления связей для {rel['table']}",
                str(e),
                entity_type="database_version",
                entity_id=target_version_id
            )
    
    current_app.logger.info(f"Ультра-оптимизированное обновление связей завершено: {total_updated} связей обновлено")
    log_to_db(
        user,
        "Ультра-оптимизированное обновление связей между таблицами завершено",
        f"Обновлено связей: {total_updated}",
        entity_type="database_version",
        entity_id=target_version_id
    )


def _update_version_relationships_fixed(id_mappings, target_version_id, user):
    """
    ИСПРАВЛЕННАЯ версия обновления связей между таблицами.
    Использует правильную логику обновления foreign key с учетом иерархии зависимостей.
    
    Args:
        id_mappings: Словарь соответствий старых и новых ID по таблицам
        target_version_id: ID целевой версии
        user: Пользователь для логирования
    """
    current_app.logger.info("Начало ИСПРАВЛЕННОГО обновления связей между таблицами")
    
    # ПРАВИЛЬНЫЙ порядок обновления связей согласно иерархии зависимостей
    relationships = [
        # 1. stations -> station_groups (станции ссылаются на группы)
        {
            'table': 'gs_gen.gs_gen_stations',
            'foreign_key': 'id_station_group',
            'reference_table': 'gs_gen.gs_gen_station_groups'
        },
        # 2. station_powers -> stations (мощности станций ссылаются на станции)
        {
            'table': 'gs_gen.gs_gen_station_powers',
            'foreign_key': 'id_station',
            'reference_table': 'gs_gen.gs_gen_stations'
        },
        # 3. machines -> stations (машины ссылаются на станции)
        {
            'table': 'gs_gen.gs_gen_machines',
            'foreign_key': 'id_station',
            'reference_table': 'gs_gen.gs_gen_stations'
        },
        # 4. boilers -> stations (котлы ссылаются на станции)
        {
            'table': 'gs_gen.gs_gen_boilers',
            'foreign_key': 'id_station',
            'reference_table': 'gs_gen.gs_gen_stations'
        },
        # 5. machine_powers -> machines (мощности машин ссылаются на машины)
        {
            'table': 'gs_gen.gs_gen_machine_powers',
            'foreign_key': 'id_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 6. machine_fuels -> machines (топливо машин ссылается на машины)
        {
            'table': 'gs_gen.gs_gen_machine_fuels',
            'foreign_key': 'id_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 7. machine_tes_types -> machines (типы ТЭС машин ссылаются на машины)
        {
            'table': 'gs_gen.gs_gen_machine_tes_types',
            'foreign_key': 'id_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 8. pgu_machines -> machines (ПГУ машины ссылаются на машины)
        {
            'table': 'gs_gen.gs_gen_pgu_machines',
            'foreign_key': 'id_parent_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 9. pgu_machine_powers -> pgu_machines (мощности ПГУ машин ссылаются на ПГУ машины)
        {
            'table': 'gs_gen.gs_gen_pgu_machine_powers',
            'foreign_key': 'id_pgu_machine',
            'reference_table': 'gs_gen.gs_gen_pgu_machines'
        }
    ]
    
    total_updated = 0
    
    for rel in relationships:
        try:
            table_key = rel['table']
            if table_key not in id_mappings:
                current_app.logger.info(f"Пропуск таблицы {table_key}: нет данных в id_mappings")
                continue
            
            ref_table_key = rel['reference_table']
            if ref_table_key not in id_mappings:
                current_app.logger.info(f"Пропуск таблицы {table_key}: нет справочной таблицы {ref_table_key}")
                continue
            
            table_mapping = id_mappings[table_key]
            ref_table_mapping = id_mappings[ref_table_key]
            
            if not table_mapping or not ref_table_mapping:
                current_app.logger.info(f"Пропуск таблицы {table_key}: пустые маппинги")
                continue
            
            # ИСПРАВЛЕННАЯ логика обновления связей
            temp_table_name = f"fixed_mapping_{abs(hash(table_key)) % 100000}"
            
            try:
                # Создаем временную таблицу с маппингом
                create_temp = text(f"""
                    CREATE TEMP TABLE {temp_table_name} (
                        old_fk INTEGER PRIMARY KEY,
                        new_fk INTEGER
                    )
                """)
                db.session.execute(create_temp)
                
                # Индекс для ускорения поиска
                create_index = text(f"""
                    CREATE INDEX idx_{temp_table_name}_old_fk 
                    ON {temp_table_name} (old_fk)
                """)
                db.session.execute(create_index)
                
                # Подготавливаем данные: пары соответствий FK из родительской таблицы
                insert_data = [(old_fk, new_fk) for old_fk, new_fk in ref_table_mapping.items()]
                
                if not insert_data:
                    current_app.logger.info(f"Таблица {table_key}: нет связей для обновления")
                    continue
                
                # Вставляем данные через executemany
                insert_query = text(f"""
                    INSERT INTO {temp_table_name} (old_fk, new_fk) 
                    VALUES (:old_fk, :new_fk)
                    ON CONFLICT (old_fk) DO NOTHING
                """)
                param_rows = [
                    {"old_fk": old_fk, "new_fk": new_fk}
                    for (old_fk, new_fk) in insert_data
                ]
                db.session.execute(insert_query, param_rows)
                
                # ИСПРАВЛЕННЫЙ UPDATE: обновляем foreign key в дочерней таблице
                update_query = text(f"""
                    UPDATE {rel['table']} 
                    SET {rel['foreign_key']} = t.new_fk
                    FROM {temp_table_name} t
                    WHERE {rel['table']}.database_version_id = :target_version_id
                      AND {rel['table']}.{rel['foreign_key']} = t.old_fk
                """)
                
                result = db.session.execute(update_query, {"target_version_id": target_version_id})
                updated_count = result.rowcount
                total_updated += updated_count
                
                current_app.logger.info(f"ИСПРАВЛЕНО: Таблица {table_key}: обновлено {updated_count} связей")
                
                # Дополнительная проверка для отладки
                if updated_count > 0:
                    current_app.logger.info(f"Обновление связи {rel['foreign_key']} в таблице {table_key} с {ref_table_key}")
                else:
                    current_app.logger.warning(f"НЕ ОБНОВЛЕНО ни одной связи {rel['foreign_key']} в таблице {table_key}")
                
            finally:
                # Удаляем временную таблицу
                try:
                    drop_temp = text(f"DROP TABLE IF EXISTS {temp_table_name}")
                    db.session.execute(drop_temp)
                except:
                    pass
            
        except Exception as e:
            current_app.logger.error(f"Ошибка ИСПРАВЛЕННОГО обновления для {rel['table']}: {str(e)}")
            log_to_db(
                user,
                f"Ошибка ИСПРАВЛЕННОГО обновления для {rel['table']}",
                str(e),
                entity_type="database_version",
                entity_id=target_version_id
            )
    
    current_app.logger.info(f"ИСПРАВЛЕННОЕ обновление связей завершено: {total_updated} связей обновлено")
    
    log_to_db(
        user,
        "ИСПРАВЛЕННОЕ обновление связей между таблицами завершено",
        f"Обновлено связей: {total_updated}",
        entity_type="database_version",
        entity_id=target_version_id
    )


def _update_version_relationships_lightning_fast(id_mappings, target_version_id, user):
    """
    МОЛНИЕНОСНАЯ версия обновления связей.
    Использует прямые SQL запросы без ORM для максимальной скорости.
    
    Args:
        id_mappings: Словарь соответствий старых и новых ID по таблицам
        target_version_id: ID целевой версии
        user: Пользователь для логирования
    """
    current_app.logger.info("Начало молниеносного обновления связей между таблицами")
    
    # ВСЕ критичные связи в правильном порядке обновления согласно требованиям
    critical_relationships = [
        # 1. machines -> stations
        {
            'table': 'gs_gen.gs_gen_machines',
            'foreign_key': 'id_station',
            'reference_table': 'gs_gen.gs_gen_stations'
        },
        # 2. machine_powers -> machines
        {
            'table': 'gs_gen.gs_gen_machine_powers',
            'foreign_key': 'id_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 3. machine_fuels -> machines
        {
            'table': 'gs_gen.gs_gen_machine_fuels',
            'foreign_key': 'id_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 4. machine_tes_types -> machines
        {
            'table': 'gs_gen.gs_gen_machine_tes_types',
            'foreign_key': 'id_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 5. pgu_machines -> machines (используем id_parent_machine)
        {
            'table': 'gs_gen.gs_gen_pgu_machines',
            'foreign_key': 'id_parent_machine',
            'reference_table': 'gs_gen.gs_gen_machines'
        },
        # 6. pgu_machine_powers -> pgu_machines
        {
            'table': 'gs_gen.gs_gen_pgu_machine_powers',
            'foreign_key': 'id_pgu_machine',
            'reference_table': 'gs_gen.gs_gen_pgu_machines'
        },
        # 7. stations -> station_groups
        {
            'table': 'gs_gen.gs_gen_stations',
            'foreign_key': 'id_station_group',
            'reference_table': 'gs_gen.gs_gen_station_groups'
        },
        # 8. station_powers -> stations
        {
            'table': 'gs_gen.gs_gen_station_powers',
            'foreign_key': 'id_station',
            'reference_table': 'gs_gen.gs_gen_stations'
        },
        # 9. boilers -> stations
        {
            'table': 'gs_gen.gs_gen_boilers',
            'foreign_key': 'id_station',
            'reference_table': 'gs_gen.gs_gen_stations'
        }
    ]
    
    total_updated = 0
    
    for rel in critical_relationships:
        try:
            table_key = rel['table']
            if table_key not in id_mappings:
                continue
            
            ref_table_key = rel['reference_table']
            if ref_table_key not in id_mappings:
                continue
            
            table_mapping = id_mappings[table_key]
            ref_table_mapping = id_mappings[ref_table_key]
            
            if not table_mapping or not ref_table_mapping:
                continue
            
            # МОЛНИЕНОСНАЯ ОПТИМИЗАЦИЯ: Прямой SQL с минимальными блокировками
            temp_table_name = f"lightning_mapping_{abs(hash(table_key)) % 100000}"
            
            try:
                # Создаем временную таблицу с парами соответствий FK
                create_temp = text(f"""
                    CREATE TEMP TABLE {temp_table_name} (
                        old_fk INTEGER PRIMARY KEY,
                        new_fk INTEGER
                    )
                """)
                db.session.execute(create_temp)

                # Индекс для ускорения поиска по старому FK
                create_index = text(f"""
                    CREATE INDEX idx_{temp_table_name}_old_fk 
                    ON {temp_table_name} (old_fk)
                """)
                db.session.execute(create_index)

                # Подготавливаем данные: пары соответствий FK из родительской таблицы
                insert_data = [(old_fk, new_fk) for old_fk, new_fk in ref_table_mapping.items()]

                if insert_data:
                    # Вставляем данные через executemany с именованными параметрами
                    insert_query = text(f"""
                        INSERT INTO {temp_table_name} (old_fk, new_fk) 
                        VALUES (:old_fk, :new_fk)
                        ON CONFLICT (old_fk) DO NOTHING
                    """)
                    param_rows = [
                        {"old_fk": old_fk, "new_fk": new_fk}
                        for (old_fk, new_fk) in insert_data
                    ]
                    db.session.execute(insert_query, param_rows)

                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: МОЛНИЕНОСНЫЙ UPDATE по совпадению FK
                    # Обновляем foreign key в дочерней таблице, используя соответствие из родительской таблицы
                    update_query = text(f"""
                        UPDATE {rel['table']} 
                        SET {rel['foreign_key']} = t.new_fk
                        FROM {temp_table_name} t
                        WHERE {rel['table']}.database_version_id = :target_version_id
                          AND {rel['table']}.{rel['foreign_key']} = t.old_fk
                    """)
                    
                    result = db.session.execute(update_query, {"target_version_id": target_version_id})
                    updated_count = result.rowcount
                    total_updated += updated_count
                    
                    current_app.logger.info(f"МОЛНИЕНОСНО: Таблица {table_key}: обновлено {updated_count} связей")
                    
                    # Дополнительная проверка для отладки
                    if updated_count > 0:
                        current_app.logger.info(f"Обновление связи {rel['foreign_key']} в таблице {table_key} с {ref_table_key}")
                    else:
                        current_app.logger.warning(f"НЕ ОБНОВЛЕНО ни одной связи {rel['foreign_key']} в таблице {table_key}")
                
            finally:
                # Удаляем временную таблицу
                try:
                    drop_temp = text(f"DROP TABLE IF EXISTS {temp_table_name}")
                    db.session.execute(drop_temp)
                except:
                    pass
            
        except Exception as e:
            current_app.logger.error(f"Ошибка молниеносного обновления для {rel['table']}: {str(e)}")
            log_to_db(
                user,
                f"Ошибка молниеносного обновления для {rel['table']}",
                str(e),
                entity_type="database_version",
                entity_id=target_version_id
            )
            # Откатываем транзакцию для этой таблицы и продолжаем с другими
            try:
                db.session.rollback()
                # Начинаем новую транзакцию
                db.session.begin()
            except:
                pass
    
    current_app.logger.info(f"МОЛНИЕНОСНОЕ обновление связей завершено: {total_updated} связей обновлено")
    
    # Проверяем целостность данных после обновления связей
    # _verify_version_data_integrity(target_version_id, user)  # Временно отключено
    
    log_to_db(
        user,
        "МОЛНИЕНОСНОЕ обновление связей между таблицами завершено",
        f"Обновлено связей: {total_updated}",
        entity_type="database_version",
        entity_id=target_version_id
    )


def _delete_version_data_staged(version_id, user):
    """
    Удаляет все данные, связанные с указанной версией, используя ПОЭТАПНУЮ логику в ОБРАТНОМ порядке.
    
    Логика удаления:
    1. Сначала удаляем таблицы GENERATION с максимальными зависимостями (ЭТАП 8-5)
    2. Затем удаляем таблицы REFDATA с зависимостями (ЭТАП 4-2)
    3. В конце удаляем полностью независимые таблицы (ЭТАП 1)
    
    Порядок: GENERATION -> REFDATA (так как generation зависит от refdata)
    Это предотвращает ошибки нарушения внешних ключей.
    
    Args:
        version_id: ID версии для удаления данных
        user: Пользователь для логирования
    """
    log_to_db(
        user,
        f"Начало ПОЭТАПНОГО удаления данных версии БД ID={version_id}",
        "Применяется обратная логика: сначала GENERATION, затем REFDATA",
        entity_type="database_version",
        entity_id=version_id
    )
    
    # ЭТАП 8: Таблицы с максимальными зависимостями (удаляем первыми)
    stage8_tables = [
        (SCHEMA_GENERATION, 'gs_gen_pgu_machine_powers')
    ]
    
    # ЭТАП 7: Таблицы, зависящие от machines
    stage7_tables = [
        (SCHEMA_GENERATION, 'gs_gen_machine_powers'),
        (SCHEMA_GENERATION, 'gs_gen_machine_fuels'),
        (SCHEMA_GENERATION, 'gs_gen_machine_tes_types'),
        (SCHEMA_GENERATION, 'gs_gen_machine_names'),
        (SCHEMA_GENERATION, 'gs_gen_pgu_machines'),
        (SCHEMA_FUEL, 'gs_fue_machine_fuel_param'),  # Топливные параметры агрегатов
    ]
    
    # ЭТАП 6: Таблицы, зависящие от stations
    stage6_tables = [
        (SCHEMA_GENERATION, 'gs_gen_machines'),
        (SCHEMA_FUEL, 'gs_fue_equipment_group_fuel_param'),  # Параметры топлива групп оборудования
        (SCHEMA_GENERATION, 'gs_gen_station_powers'),
        (SCHEMA_GENERATION, 'gs_gen_boilers')
    ]
    
    # ЭТАП 5: Таблицы generation с зависимостями
    stage5_tables = [
        (SCHEMA_GENERATION, 'gs_gen_stations')
    ]
    
    # ЭТАП 4: Таблицы с зависимостями от ЭТАПОВ 1-3
    # Таблицы refdata после миграции ff9f0f8940c8 имеют префикс gs_
    stage4_tables = [
        (SCHEMA_REFDATA, 'gs_sys_energy_areas'),
        (SCHEMA_REFDATA, 'gs_sys_energy_units')
    ]
    
    # ЭТАП 3: Таблицы с зависимостями от ЭТАПОВ 1-2
    stage3_tables = [
        (SCHEMA_REFDATA, 'gs_sys_regional_districts'),
        (SCHEMA_REFDATA, 'gs_sys_regional_energy_systems')
    ]
    
    # ЭТАП 2: Таблицы с зависимостями от ЭТАПА 1
    stage2_tables = [
        (SCHEMA_REFDATA, 'gs_sys_union_energy_systems'),
        (SCHEMA_REFDATA, 'gs_sys_synchronous_areas'),
        (SCHEMA_REFDATA, 'gs_sys_energy_zones'),
        (SCHEMA_REFDATA, 'gs_sys_federal_districts')
    ]
    
    # ЭТАП 1: Полностью независимые таблицы (удаляем последними)
    stage1_tables = [
        (SCHEMA_REFDATA, 'gs_sys_station_types'),
        (SCHEMA_REFDATA, 'gs_sys_machine_types'),
        (SCHEMA_REFDATA, 'gs_sys_tes_types'),
        (SCHEMA_REFDATA, 'gs_sys_tes_machine_types'),
        (SCHEMA_REFDATA, 'gs_sys_pgu_tes_machine_types'),
        (SCHEMA_REFDATA, 'gs_sys_condition_types'),
        (SCHEMA_REFDATA, 'gs_sys_technology_types'),
        (SCHEMA_REFDATA, 'gs_sys_technology_availabilities'),
        (SCHEMA_REFDATA, 'gs_sys_equipment_groups'),
        (SCHEMA_REFDATA, 'gs_sys_energy_system_types'),
        (SCHEMA_REFDATA, 'gs_sys_fuel_categories'),
        (SCHEMA_REFDATA, 'gs_sys_fuel_types'),
        (SCHEMA_REFDATA, 'gs_sys_fuels'),
        (SCHEMA_REFDATA, 'gs_sys_companies'),
        (SCHEMA_REFDATA, 'gs_sys_year_features'),
        (SCHEMA_REFDATA, 'gs_sys_years'),
        (SCHEMA_REFDATA, 'gs_sys_year_service'),  # Сервис управления годами СиПР
        (SCHEMA_REFDATA, 'gs_sys_refdata_entity_years'),  # История справочников — годы
        (SCHEMA_REFDATA, 'gs_sys_refdata_entities'),  # История справочников — сущности
        (SCHEMA_REFDATA, 'gs_sys_departments'),  # Подразделения
        (SCHEMA_REFDATA, 'gs_sys_business_units'),  # Бизнес-единицы
        (SCHEMA_GENERATION, 'gs_gen_station_groups'),
        (SCHEMA_GENERATION, 'gs_gen_documents_kommod')
    ]
    
    # Объединяем все этапы в обратном порядке (от 8 к 1)
    # Сначала удаляем generation, затем refdata
    all_stages = [
        ("ЭТАП 8", stage8_tables),  # gs_gen.gs_gen_pgu_machine_powers
        ("ЭТАП 7", stage7_tables),  # gs_gen.gs_gen_machine_powers, machine_fuels, machine_tes_types, pgu_machines
        ("ЭТАП 6", stage6_tables),  # gs_gen.gs_gen_station_powers, machines, boilers
        ("ЭТАП 5", stage5_tables),  # gs_gen.gs_gen_stations
        ("ЭТАП 4", stage4_tables),  # refdata.energy_areas, energy_units
        ("ЭТАП 3", stage3_tables),  # refdata.regional_districts, regional_energy_systems
        ("ЭТАП 2", stage2_tables),  # refdata.union_energy_systems, synchronous_areas, energy_zones, federal_districts
        ("ЭТАП 1", stage1_tables)   # refdata.station_types, machine_types, etc. + gs_gen.gs_gen_station_groups, documents_kommod
    ]
    
    total_deleted = 0

    # Удаляем таблицы поэтапно
    for stage_name, tables in all_stages:
        current_app.logger.info(f"🔄 {stage_name}: Удаление таблиц с зависимостями")
        
        for schema, table in tables:
            # Каждая таблица обрабатывается в отдельной транзакции
            try:
                current_app.logger.info(f"🗑️ Удаление данных из таблицы {schema}.{table} для версии {version_id}")
                
                # Проверяем, существует ли таблица и есть ли в ней поле database_version_id
                check_table_query = text("""
                    SELECT COUNT(*) 
                    FROM information_schema.columns 
                    WHERE table_schema = :schema_name 
                      AND table_name = :table_name
                      AND column_name = 'database_version_id'
                """)
                
                result = db.session.execute(check_table_query, {"schema_name": schema, "table_name": table})
                has_version_column = result.scalar() > 0
                
                if not has_version_column:
                    current_app.logger.info(f"⚠️ Таблица {schema}.{table} не имеет поля database_version_id, пропускаем")
                    continue
                
                # Подсчитываем количество записей для удаления
                count_query = text(f"""
                    SELECT COUNT(*) FROM {schema}.{table} 
                    WHERE database_version_id = :version_id
                """)
                
                count_result = db.session.execute(count_query, {"version_id": version_id})
                records_count = count_result.scalar()
                
                if records_count == 0:
                    current_app.logger.info(f"📋 Таблица {schema}.{table}: нет данных для удаления")
                    continue
                
                # Удаляем записи в отдельной транзакции
                try:
                    delete_query = text(f"""
                        DELETE FROM {schema}.{table} 
                        WHERE database_version_id = :version_id
                    """)
                    
                    result = db.session.execute(delete_query, {"version_id": version_id})
                    deleted_count = result.rowcount
                    total_deleted += deleted_count
                    
                    # Коммитим изменения для этой таблицы
                    db.session.commit()
                    current_app.logger.info(f"✅ Удалено {deleted_count} записей из таблицы {schema}.{table}")
                    
                except Exception as delete_error:
                    # Откатываем транзакцию для этой таблицы
                    try:
                        db.session.rollback()
                        current_app.logger.warning(f"🔄 Rollback выполнен для таблицы {schema}.{table} из-за ошибки: {delete_error}")
                    except Exception as rollback_error:
                        current_app.logger.error(f"❌ Ошибка при rollback для таблицы {schema}.{table}: {rollback_error}")
                    
                    # Логируем ошибку, но продолжаем с другими таблицами
                    log_to_db(
                        user,
                        f"Ошибка удаления данных из таблицы {schema}.{table}",
                        f"Версия {version_id}: {str(delete_error)}",
                        entity_type="database_version",
                        entity_id=version_id
                    )
                    continue
                
            except Exception as e:
                # Ошибка на уровне проверки таблицы
                current_app.logger.error(f"❌ Ошибка при проверке таблицы {schema}.{table}: {e}")
                log_to_db(
                    user,
                    f"Ошибка проверки таблицы {schema}.{table}",
                    f"Версия {version_id}: {str(e)}",
                    entity_type="database_version",
                    entity_id=version_id
                )
                continue
        
        current_app.logger.info(f"✅ {stage_name} завершен")
    
    # Удаляем ассоциативные таблицы (если есть)
    current_app.logger.info("🔄 Удаление ассоциативных таблиц")
    
    try:
        # Таблица many-to-many (миграция b8c9d0e1f2a3): gs_sys_regional_district_regional_energy_system
        assoc_table = 'gs_sys_regional_district_regional_energy_system'
        check_assoc_query = text("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = :schema_name
              AND table_name = :table_name
        """)
        
        result = db.session.execute(check_assoc_query, {"schema_name": SCHEMA_REFDATA, "table_name": assoc_table})
        if result.scalar() > 0:
            # Проверяем наличие поля database_version_id
            check_column_query = text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_schema = :schema_name
                  AND table_name = :table_name
                  AND column_name = 'database_version_id'
            """)
            
            result = db.session.execute(check_column_query, {"schema_name": SCHEMA_REFDATA, "table_name": assoc_table})
            if result.scalar() > 0:
                # Подсчитываем записи
                count_query = text(f"""
                    SELECT COUNT(*) FROM {SCHEMA_REFDATA}.{assoc_table} 
                    WHERE database_version_id = :version_id
                """)
                
                count_result = db.session.execute(count_query, {"version_id": version_id})
                records_count = count_result.scalar()
                
                if records_count > 0:
                    # Удаляем записи в отдельной транзакции
                    try:
                        delete_query = text(f"""
                            DELETE FROM {SCHEMA_REFDATA}.{assoc_table} 
                            WHERE database_version_id = :version_id
                        """)
                        
                        result = db.session.execute(delete_query, {"version_id": version_id})
                        deleted_count = result.rowcount
                        total_deleted += deleted_count
                        
                        # Коммитим изменения
                        db.session.commit()
                        current_app.logger.info(
                            f"✅ Удалено {deleted_count} записей из ассоциативной таблицы {SCHEMA_REFDATA}.{assoc_table}"
                        )
                        
                    except Exception as delete_error:
                        # Откатываем транзакцию
                        try:
                            db.session.rollback()
                            current_app.logger.warning(f"🔄 Rollback выполнен для ассоциативной таблицы из-за ошибки: {delete_error}")
                        except Exception as rollback_error:
                            current_app.logger.error(f"❌ Ошибка при rollback для ассоциативной таблицы: {rollback_error}")
                        
                        # Логируем ошибку
                        log_to_db(
                            user,
                            f"Ошибка удаления ассоциативной таблицы {assoc_table}",
                            f"Версия {version_id}: {str(delete_error)}",
                            entity_type="database_version",
                            entity_id=version_id
                        )
                else:
                    current_app.logger.info(f"📋 Ассоциативная таблица {SCHEMA_REFDATA}.{assoc_table}: нет данных для удаления")
            else:
                current_app.logger.info(f"⚠️ Ассоциативная таблица {assoc_table} не имеет поля database_version_id")
        else:
            current_app.logger.info(f"📋 Ассоциативная таблица {assoc_table} не существует")
            
    except Exception as e:
        current_app.logger.error(f"❌ Ошибка при проверке ассоциативных таблиц: {e}")
        log_to_db(
            user,
            f"Ошибка проверки ассоциативных таблиц",
            f"Версия {version_id}: {str(e)}",
            entity_type="database_version",
            entity_id=version_id
        )
    
    log_to_db(
        user,
        f"✅ ПОЭТАПНОЕ удаление данных версии БД ID={version_id} завершено",
        f"Всего удалено записей: {total_deleted}",
        entity_type="database_version",
        entity_id=version_id
    )
    
    current_app.logger.info(f"✅ ПОЭТАПНОЕ удаление данных версии БД ID={version_id} завершено. Удалено записей: {total_deleted}")
    
    return total_deleted


def _delete_version_data(version_id, user):
    """
    Удаляет все данные, связанные с указанной версией.
    
    Args:
        version_id: ID версии для удаления данных
        user: Пользователь для логирования
    """
    log_to_db(
        user,
        f"Начало удаления данных версии БД ID={version_id}",
        "",
        entity_type="database_version",
        entity_id=version_id
    )
    
    gen_schema = SCHEMA_GENERATION
    fuel_schema = SCHEMA_FUEL

    # Таблицы для удаления из схемы generation (в порядке зависимостей - сначала дочерние)
    # ВАЖНО: Порядок имеет значение из-за внешних ключей!
    generation_tables = [
        # Сначала удаляем все дочерние записи
        'gs_gen_machine_powers',      # Мощности машин (зависят от машин)
        'gs_gen_machine_fuels',       # Топливо машин (зависят от машин)
        'gs_gen_machine_tes_types',   # Типы ТЭС машин (зависят от машин)
        'gs_gen_machine_names',      # Названия агрегатов по годам (зависят от машин)
        'gs_gen_pgu_machine_powers',  # Мощности ПГУ машин (зависят от ПГУ машин)
        'gs_gen_pgu_machines',        # ПГУ машины (зависят от машин)
        'gs_gen_machines',            # Машины (зависят от станций)
        'gs_gen_station_powers',      # Мощности станций (зависят от станций)
        'gs_gen_boilers',             # Котлы (зависят от станций)
        'gs_gen_stations',            # Станции (зависят от групп станций)
        'gs_gen_station_groups',      # Группы станций
        'gs_gen_documents_kommod'     # Документы
    ]

    fuel_tables = []
    
    # Таблицы для удаления из схемы refdata
    refdata_tables = [
        #  Справочники для станций
        'station_types',
        'machine_types',
        'tes_types',
        'tes_machine_types',
        'pgu_tes_machine_types',
        'condition_types',
        'technology_types',
        'technology_availabilities',
        'equipment_groups',
        # Энергосистемы
        'energy_system_types',
        'union_energy_systems',
        'synchronous_areas',
        'energy_areas',
        'energy_zones',
        'energy_units',
        'regional_energy_systems',
        # Территории
        'federal_districts',
        'gs_sys_regional_districts',
        # Генерирующие компании
        'gs_sys_companies',
        # Топливо
        'fuel_categories',
        'fuel_types',
        'fuels',
        # Годы и год features теперь версионируются
        'year_features',
        'years',
    ]
    
    # Объединяем списки таблиц со схемами
    tables_to_delete = (
        [(gen_schema, table) for table in generation_tables]
        + [(fuel_schema, table) for table in fuel_tables]
        + [(SCHEMA_REFDATA, table) for table in refdata_tables]
    )
    
    total_deleted = 0
    
    for schema, table in tables_to_delete:
        try:
            current_app.logger.info(f"Удаление данных из таблицы {schema}.{table} для версии {version_id}")
            
            # Проверяем, существует ли таблица и есть ли в ней поле database_version_id
            check_table_query = text("""
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_schema = :schema_name 
                  AND table_name = :table_name
                  AND column_name = 'database_version_id'
            """)
            
            result = db.session.execute(check_table_query, {"schema_name": schema, "table_name": table})
            has_version_column = result.scalar() > 0
            
            if not has_version_column:
                current_app.logger.info(f"Таблица {schema}.{table} не имеет поля database_version_id, пропускаем")
                continue
            
            # Подсчитываем количество записей для удаления
            count_query = text(f"""
                SELECT COUNT(*) FROM {schema}.{table} 
                WHERE database_version_id = :version_id
            """)
            result = db.session.execute(count_query, {"version_id": version_id})
            count_to_delete = result.scalar()
            
            if count_to_delete == 0:
                current_app.logger.info(f"Таблица {schema}.{table}: нет данных для удаления")
                continue
            
            # Удаляем данные
            delete_query = text(f"""
                DELETE FROM {schema}.{table} 
                WHERE database_version_id = :version_id
            """)
            
            result = db.session.execute(delete_query, {"version_id": version_id})
            deleted_count = result.rowcount
            total_deleted += deleted_count
            
            current_app.logger.info(f"Таблица {schema}.{table}: удалено {deleted_count} записей")
            
            if deleted_count > 0:
                log_to_db(
                    user,
                    f"Удалены данные из таблицы {schema}.{table}",
                    f"Версия {version_id}: {deleted_count} записей",
                    entity_type="database_version",
                    entity_id=version_id
                )
                
        except Exception as e:
            # Откатываем транзакцию для этой таблицы и продолжаем
            try:
                db.session.rollback()
                current_app.logger.warning(f"Откат транзакции для таблицы {schema}.{table}")
            except:
                pass
            
            log_to_db(
                user,
                f"Ошибка удаления данных из таблицы {schema}.{table}",
                f"Версия {version_id}: {str(e)}",
                entity_type="database_version",
                entity_id=version_id
            )
            current_app.logger.error(f"Ошибка удаления данных из {schema}.{table}: {str(e)}")
            # Продолжаем удаление других таблиц
    
    log_to_db(
        user,
        f"Завершено удаление данных версии БД ID={version_id}",
        f"Всего удалено записей: {total_deleted}",
        entity_type="database_version",
        entity_id=version_id
    )
    
    return total_deleted


@no_autoflush
def delete_version_service(ids, user):
    """Удаляет записи версий по переданным ID и все связанные с ними данные."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")

    log_to_db(
        user, 
        "Удаление версий БД", 
        f"Переданы ID для удаления: {ids}", 
        entity_type="database_version")

    successful_deletes = 0
    deleted_version_numbers = []
    not_found = []
    invalid = []
    active_versions = []
    total_data_deleted = 0
    deleted_version_ids = []

    for version_id in ids:
        try:
            vid = int(version_id)
        except (TypeError, ValueError):
            invalid.append(version_id)
            log_to_db(
                user, 
                "Ошибка удаления версий БД", 
                f"Некорректный ID: {version_id}", 
                entity_type="database_version",
                entity_id=version_id)
            continue

        # Не используем _locked_get (FOR UPDATE) - при удалении блокировка может вызывать зависание
        # из-за ожидания других транзакций. Достаточно обычного получения записи.
        obj = DatabaseVersion.query.filter_by(id=vid).first()
        if obj:
            # Проверка, не является ли версия активной
            if obj.is_active:
                active_versions.append(f"v{obj.version_number}")
                log_to_db(
                    user, 
                    "Попытка удаления активной версии БД", 
                    f"Версия v{obj.version_number} является активной и не может быть удалена.", 
                    entity_type="database_version", 
                    entity_id=vid)
                continue
            
            version_display = obj.version_number or f"ID={vid}"
            
            # Сначала удаляем все данные, связанные с этой версией
            try:
                data_deleted = _delete_version_data_staged(vid, user)
                total_data_deleted += data_deleted
                log_to_db(
                    user, 
                    f"Удалены данные версии БД: v{version_display}", 
                    f"ID={vid}, удалено записей: {data_deleted}", 
                    entity_type="database_version", 
                    entity_id=vid)
            except Exception as e:
                log_to_db(
                    user, 
                    f"Ошибка удаления данных версии БД: v{version_display}", 
                    f"ID={vid}, ошибка: {str(e)}", 
                    entity_type="database_version", 
                    entity_id=vid)
                current_app.logger.error(f"Ошибка удаления данных версии {vid}: {e}")
                # Продолжаем удаление записи версии даже если не удалось удалить все данные
            
            # Удаляем файл снимка, если он существует
            if obj.snapshot_path:
                snapshot_path = obj.snapshot_path
                # Проверяем абсолютный и относительный путь
                if not os.path.isabs(snapshot_path):
                    # Если путь относительный, проверяем от корня проекта
                    from pathlib import Path
                    project_root = Path(__file__).parent.parent.parent.parent
                    snapshot_path = str(project_root / snapshot_path)
                
                if os.path.exists(snapshot_path):
                    try:
                        file_size = os.path.getsize(snapshot_path)
                        os.remove(snapshot_path)
                        log_to_db(
                            user, 
                            f"Удален файл снимка версии БД ID={vid}", 
                            f"Путь: {snapshot_path}, Размер: {file_size / 1024 / 1024:.2f} МБ", 
                            entity_type="database_version", 
                            entity_id=vid)
                        current_app.logger.info(f"Удален dump-файл: {snapshot_path} ({file_size / 1024 / 1024:.2f} МБ)")
                    except Exception as e:
                        log_to_db(
                            user, 
                            f"Ошибка удаления файла снимка версии БД ID={vid}", 
                            f"Путь: {snapshot_path}, Ошибка: {str(e)}", 
                            entity_type="database_version", 
                            entity_id=vid)
                        current_app.logger.error(f"Не удалось удалить dump-файл {snapshot_path}: {e}")
                else:
                    log_to_db(
                        user, 
                        f"Файл снимка версии БД ID={vid} не найден", 
                        f"Путь: {snapshot_path}", 
                        entity_type="database_version", 
                        entity_id=vid)
                    current_app.logger.warning(f"Dump-файл не найден: {snapshot_path}")
            
            # Удаляем саму запись версии
            db.session.delete(obj)
            successful_deletes += 1
            deleted_version_numbers.append(version_display)
            deleted_version_ids.append(vid)
            log_to_db(
                user, 
                "Удалена версия БД", 
                f"v{version_display}", 
                entity_type="database_version", 
                entity_id=vid)
        else:
            not_found.append(vid)
            log_to_db(
                user, 
                "Ошибка удаления версий БД", 
                f"Версия с ID={vid} не найдена.", 
                entity_type="database_version", 
                entity_id=vid)

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        parts = [f"Удалено версий: {successful_deletes}"]
        if deleted_version_numbers:
            parts.append(f"Номера версий: {deleted_version_numbers}")
        if total_data_deleted > 0:
            parts.append(f"Удалено записей данных: {total_data_deleted}")
        if not_found:
            parts.append(f"Не найдены ID: {not_found}")
        if invalid:
            parts.append(f"Некорректные ID: {invalid}")
        if active_versions:
            raise ValueError(f"Невозможно удалить активные версии: {', '.join(active_versions)}")

        # Логируем общий результат
        log_to_db(
            user, 
            "Завершено удаление версий БД", 
            f"Удалено версий: {successful_deletes}, удалено записей данных: {total_data_deleted}", 
            entity_type="database_version")

        # Удаляем логи, привязанные к удаленным версиям
        if deleted_version_ids:
            Log.query.filter(Log.database_version_id.in_(deleted_version_ids)).delete(
                synchronize_session=False
            )
            _commit_with_retry()

        return {
            "deleted": successful_deletes,
            "deleted_version_numbers": deleted_version_numbers,
            "total_data_deleted": total_data_deleted,
            "not_found": not_found,
            "invalid": invalid,
            "active_versions": active_versions,
        }
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка удаления версий БД", 
            str(e), 
            entity_type="database_version")
        raise ValueError(f"Ошибка при удалении данных: {e}")


def export_version_service(
    user,
    version_filter=None,
    sort_by="version_number",
    sort_dir="desc",):
    """ Экспортирует данные версий в Excel. """

    log_to_db(user, "Начата выгрузка таблицы версий БД из базы данных", entity_type="database_version")
    log_to_db(user, "Параметры экспорта",
        (
            f"Фильтр: {version_filter},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        ), entity_type="database_version"
    )

    # Базовый запрос
    query = version_query(
        version_filter=version_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(user, "Получение данных завершено", f"Найдено записей: {len(items)}", entity_type="database_version")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        # Информация о родительской версии
        parent_info = "-"
        if o.parent_version:
            parent_info = f"Версия {o.parent_version.version_number}"
        
        data.append({
            "№": idx,
            "Номер версии": o.version_number,
            "Описание": _dash(o.description),
            "Создана на основе": parent_info,
            "Активна": "Да" if o.is_active else "Нет",
            "Дата создания": o.created_at.strftime("%Y-%m-%d %H:%M:%S") if o.created_at else "-",
            "Дата обновления": o.updated_at.strftime("%Y-%m-%d %H:%M:%S") if o.updated_at else "-",
        })

    log_to_db(user, "Подготовка данных для экспорта таблицы версий БД в Excel",
              f"Записей для экспорта: {len(data)}", entity_type="database_version")

    df = pd.DataFrame(data)

    # Создание Excel и авто-ширина столбцов
    output = BytesIO()
    sheet_name = "Версии БД"
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]

        # Автоподбор ширины с аккуратным лимитом
        for i, col in enumerate(df.columns):
            max_len = max(len(str(col)), *(len(str(v)) for v in df[col].values)) if not df.empty else len(str(col))
            ws.set_column(i, i, min(max_len + 2, 60))

    output.seek(0)
    log_to_db(user, "Экспорт таблицы версий БД в Excel завершен", f"Экспортировано записей: {len(data)}", entity_type="database_version")
    return output


def get_default_version():
    """
    Получает версию базы данных по умолчанию.
    Проверяет настройки из конфига, затем выбирает последнюю версию по номеру.
    
    Returns:
        DatabaseVersion or None: Версия БД по умолчанию или None, если версий нет
    """
    from config import Config
    
    # Сначала пытаемся найти версию по ID из конфига
    if Config.DEFAULT_DATABASE_VERSION_ID:
        try:
            version = DatabaseVersion.query.get(int(Config.DEFAULT_DATABASE_VERSION_ID))
            if version:
                return version
        except (ValueError, TypeError):
            pass
    
    # Затем пытаемся найти версию по номеру из конфига
    if Config.DEFAULT_DATABASE_VERSION_NUMBER:
        try:
            version_number = str(Config.DEFAULT_DATABASE_VERSION_NUMBER).strip()
            if version_number:
                version = DatabaseVersion.query.filter_by(
                    version_number=version_number
                ).first()
                if version:
                    return version
        except (ValueError, TypeError):
            pass
    
    # Если не указано в конфиге, выбираем последнюю версию по номеру версии
    default_version = DatabaseVersion.query.order_by(
        DatabaseVersion.version_number.desc()
    ).first()
    
    return default_version


def _get_default_version_id():
    """
    Получает ID версии базы данных по умолчанию.
    
    Returns:
        int or None: ID версии БД по умолчанию или None, если версий нет
    """
    default_version = get_default_version()
    return default_version.id if default_version else None


def get_current_version():
    """Получает текущую активную версию БД из контекста запроса или из БД."""
    # Сначала проверяем контекст Flask
    if hasattr(g, 'current_db_version'):
        return g.current_db_version
    
    # Если не найдено в контексте, берем из БД
    active_version = DatabaseVersion.query.filter_by(is_active=True).first()
    if active_version:
        g.current_db_version = active_version.id
        return active_version.id
    
    # Если активной версии нет, используем версию по умолчанию
    default_version_id = _get_default_version_id()
    if default_version_id:
        g.current_db_version = default_version_id
        return default_version_id
    
    # Если версии по умолчанию нет, возвращаем None (работаем со всеми данными)
    return None


def get_current_version_year_range_from_name():
    """
    Пытается извлечь диапазон годов (start_year, end_year) из названия
    текущей версии БД, например:
    - "СиПР 2025-2031"
    - "ГС 2025-2042"
    Возвращает кортеж (start_year, end_year) или (None, None), если распарсить не удалось.
    """
    from flask import g  # безопасно, функция используется в контексте запроса

    # Используем тот же механизм, что и фильтры данных,
    # чтобы учитывать выбранную пользователем версию (из сессии/контекста).
    from app.common.services.database_version_filter import get_current_db_version_id
    version_id = get_current_db_version_id()
    if not version_id:
        print("[DB_VERSION] get_current_version_year_range_from_name: version_id is None")
        return None, None

    try:
        version = db.session.get(DatabaseVersion, version_id)
        if not version:
            print(f"[DB_VERSION] get_current_version_year_range_from_name: version missing for id={version_id}")
            return None, None

        # 1) Пытаемся распарсить годы из НОМЕРА версии (version_number) — там они зашиты явно.
        raw_version_number = (version.version_number or "").strip()
        print(f"[DB_VERSION] Parsing years from version_number: id={version_id}, version_number={raw_version_number!r}")

        dash_class = r"-\u2010-\u2015\u2212"
        m = re.search(r"(\d{4})\s*[" + dash_class + r"]\s*(\d{4})", raw_version_number)

        y1 = y2 = None

        if m:
            y1 = int(m.group(1))
            y2 = int(m.group(2))
            print(f"[DB_VERSION] Matched explicit range in version_number: {y1}-{y2}")
        else:
            years = re.findall(r"\d{4}", raw_version_number)
            print(f"[DB_VERSION] Fallback years from version_number: {years}")
            if len(years) >= 2:
                try:
                    y1 = int(years[0])
                    y2 = int(years[1])
                    print(f"[DB_VERSION] Using fallback years from version_number: {y1}, {y2}")
                except ValueError:
                    y1 = y2 = None

        # 2) Если из version_number не получилось, пробуем description.
        if y1 is None or y2 is None:
            fallback_text = str(version.description or "").strip()
            print(f"[DB_VERSION] Parsing years from description as fallback: id={version_id}")
            m = re.search(r"(\d{4})\s*[" + dash_class + r"]\s*(\d{4})", fallback_text)
            if m:
                y1 = int(m.group(1))
                y2 = int(m.group(2))
                print(f"[DB_VERSION] Matched explicit range in description: {y1}-{y2}")
            else:
                years = re.findall(r"\d{4}", fallback_text)
                print(f"[DB_VERSION] Fallback years from description: {years}")
                if len(years) >= 2:
                    try:
                        y1 = int(years[0])
                        y2 = int(years[1])
                        print(f"[DB_VERSION] Using fallback years from description: {y1}, {y2}")
                    except ValueError:
                        y1 = y2 = None

        if y1 is None or y2 is None:
            print(f"[DB_VERSION] Failed to parse years for version id={version_id}")
            return None, None

        if y1 < 1900 or y2 < 1900:
            print(f"[DB_VERSION] Parsed years out of range: {y1}, {y2}")
            return None, None

        start_year = min(y1, y2)
        end_year = max(y1, y2)
        print(f"[DB_VERSION] Final year range: {start_year}-{end_year}")
        return start_year, end_year
    except Exception as exc:
        import traceback
        print(f"[DB_VERSION] Exception in get_current_version_year_range_from_name: {exc}")
        traceback.print_exc()
        return None, None


def set_active_version(version_id, user):
    """Устанавливает версию как активную."""
    from flask import session
    
    version = db.session.get(DatabaseVersion, version_id)
    if not version:
        raise ValueError(f"Версия с ID {version_id} не найдена.")
    
    # Деактивируем только те версии, которые активны (чтобы не обновлять updated_at у всех)
    currently_active = DatabaseVersion.query.filter_by(is_active=True).all()
    for active_version in currently_active:
        if active_version.id != version_id:
            active_version.is_active = False
    
    # Активируем выбранную версию
    version.is_active = True
    
    db.session.flush()
    _commit_with_retry()
    
    # Устанавливаем в контекст текущего запроса ДО очистки кэша
    g.current_db_version = version_id
    
    # Очищаем переопределение версии из сессии пользователя,
    # чтобы middleware начал использовать активную версию из БД
    session.pop('current_db_version', None)
    
    # ВАЖНО: Очищаем все кэши ПОСЛЕ установки версии в контекст
    try:
        from app.generation.services.station_services.aggregation_cache import clear_aggregation_cache
        from app.common.services.cache_services import CacheService
        from app.common.services.choices_cache_service import ChoicesCacheService
        from app.common.services.get_services.territories.regional_district_get_services import (
            get_regional_districts_map, get_rd_to_fd_id_map
        )
        from app.common.services.get_services.territories.federal_district_get_services import (
            get_federal_districts_map, get_fd_to_rd_ids_map, get_regional_district_to_fd_id_map
        )
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
        from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
            get_regional_energy_systems_map, get_res_to_ues_id_map as get_res_to_ues_id_map_res, 
            get_ues_to_res_ids_map as get_ues_to_res_ids_map_res
        )
        
        # ВАЖНО: Очищаем кэш агрегаций станций ПЕРВЫМ, чтобы очистить Redis и memory кэши
        clear_aggregation_cache()
        
        # Очищаем базовые кэши справочников
        CacheService.clear_cache()
        
        # Очищаем кэш выборок
        ChoicesCacheService.clear_cache()
        
        # Очищаем кэши территорий
        if hasattr(get_regional_districts_map, 'cache_clear'):
            get_regional_districts_map.cache_clear()
        if hasattr(get_rd_to_fd_id_map, 'cache_clear'):
            get_rd_to_fd_id_map.cache_clear()
        if hasattr(get_federal_districts_map, 'cache_clear'):
            get_federal_districts_map.cache_clear()
        if hasattr(get_fd_to_rd_ids_map, 'cache_clear'):
            get_fd_to_rd_ids_map.cache_clear()
        if hasattr(get_regional_district_to_fd_id_map, 'cache_clear'):
            get_regional_district_to_fd_id_map.cache_clear()
        
        # Очищаем кэши энергосистем
        if hasattr(get_union_energy_system_list_full, 'cache_clear'):
            get_union_energy_system_list_full.cache_clear()
        if hasattr(get_union_energy_system_list, 'cache_clear'):
            get_union_energy_system_list.cache_clear()
        if hasattr(get_union_energy_systems_map, 'cache_clear'):
            get_union_energy_systems_map.cache_clear()
        if hasattr(get_ues_to_res_ids_map, 'cache_clear'):
            get_ues_to_res_ids_map.cache_clear()
        if hasattr(get_res_to_ues_id_map, 'cache_clear'):
            get_res_to_ues_id_map.cache_clear()
        if hasattr(get_ues_to_est_id_map, 'cache_clear'):
            get_ues_to_est_id_map.cache_clear()
        if hasattr(get_ues_to_rd_ids_map, 'cache_clear'):
            get_ues_to_rd_ids_map.cache_clear()
        if hasattr(get_ues_to_fd_ids_map, 'cache_clear'):
            get_ues_to_fd_ids_map.cache_clear()
        if hasattr(get_regional_energy_systems_map, 'cache_clear'):
            get_regional_energy_systems_map.cache_clear()
        if hasattr(get_res_to_ues_id_map_res, 'cache_clear'):
            get_res_to_ues_id_map_res.cache_clear()
        if hasattr(get_ues_to_res_ids_map_res, 'cache_clear'):
            get_ues_to_res_ids_map_res.cache_clear()
        
        # ДОПОЛНИТЕЛЬНО: Очищаем кэш агрегаций ЕЩЕ РАЗ для надежности
        clear_aggregation_cache()
        
        current_app.logger.info(f"Все кэши очищены после активации версии {version_id}")
    except Exception as e:
        current_app.logger.error(f"Ошибка при очистке кэшей после активации версии: {e}")
    
    log_to_db(
        user, 
        f"Установлена активная версия БД: v{version.version_number}",
        f"ID: {version_id}",
        entity_type="database_version",
        entity_id=version_id
    )
    
    return version


def _find_pg_binary(binary_name):
    """
    Ищет исполняемый файл PostgreSQL (pg_dump, pg_restore) в стандартных местах.
    Возвращает полный путь к файлу или просто имя, если найдено в PATH.
    """
    import shutil
    import glob
    import platform
    
    # Сначала проверяем PATH
    if shutil.which(binary_name):
        return binary_name
    
    # Для Windows ищем в стандартных местах установки PostgreSQL
    if platform.system() == 'Windows':
        # Возможные пути установки PostgreSQL на Windows
        search_paths = [
            r"C:\Program Files\PostgreSQL\*\bin",
            r"C:\Program Files (x86)\PostgreSQL\*\bin",
            r"C:\PostgreSQL\*\bin",
        ]
        
        for pattern in search_paths:
            for path in glob.glob(pattern):
                binary_path = os.path.join(path, f"{binary_name}.exe")
                if os.path.exists(binary_path):
                    return binary_path
    
    # Для Linux/Mac ищем в стандартных местах
    else:
        search_paths = [
            "/usr/bin",
            "/usr/local/bin",
            "/opt/postgresql/bin",
            "/usr/lib/postgresql/*/bin",
        ]
        
        for pattern in search_paths:
            for path in glob.glob(pattern):
                binary_path = os.path.join(path, binary_name)
                if os.path.exists(binary_path):
                    return binary_path
    
    # Если не найдено, возвращаем просто имя (может быть в PATH)
    return binary_name


def save_version_snapshot(version_id, user):
    """
    Сохраняет снимок данных для указанной версии через pg_dump.
    """
    import subprocess
    import os
    from datetime import datetime
    from flask import current_app
    
    version = db.session.get(DatabaseVersion, version_id)
    if not version:
        raise ValueError(f"Версия с ID {version_id} не найдена.")
    
    log_to_db(
        user,
        f"Начало сохранения снимка версии БД: v{version.version_number}",
        f"ID: {version_id}",
        entity_type="database_version",
        entity_id=version_id
    )
    
    try:
        # Путь к директории бэкапов
        backup_dir = "backups/versions"
        os.makedirs(backup_dir, exist_ok=True)
        
        # Формирование имени файла
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(backup_dir, f"version_{version.version_number}_{timestamp}.dump")
        
        # Получение параметров подключения к БД
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_user = os.getenv("DB_USER")
        db_name = os.getenv("DB_NAME")
        db_pass = os.getenv("DB_PASS")
        
        if not all([db_user, db_name]):
            raise ValueError("Не указаны параметры подключения к БД (DB_USER, DB_NAME)")
        
        # Поиск pg_dump
        pg_dump_path = _find_pg_binary("pg_dump")
        current_app.logger.info(f"Используется pg_dump: {pg_dump_path}")
        
        # Проверка существования pg_dump
        import shutil
        if not shutil.which(pg_dump_path) and not os.path.exists(pg_dump_path):
            raise ValueError(
                "Утилита pg_dump не найдена. "
                "Убедитесь, что PostgreSQL установлен и директория bin добавлена в PATH. "
                f"Поиск выполнялся: {pg_dump_path}"
            )
        
        # Команда pg_dump
        cmd = [
            pg_dump_path,
            "-h", db_host,
            "-p", db_port,
            "-U", db_user,
            "-w",  # do not prompt for password; fail fast if missing
            "-F", "c",  # custom format (сжатый)
            "-b",  # include blobs
            "-v",  # verbose
            "-f", backup_file,
            db_name
        ]
        
        # Подготовка окружения с паролем
        env = os.environ.copy()
        if db_pass:
            env["PGPASSWORD"] = db_pass
        
        # Выполнение pg_dump
        current_app.logger.info(f"Запуск pg_dump для версии {version.version_number}")
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=3600  # таймаут 1 час
        )
        
        if result.returncode != 0:
            error_msg = result.stderr or result.stdout or "Unknown error"
            raise Exception(f"pg_dump завершился с ошибкой: {error_msg}")
        
        # Проверка, что файл создан
        if not os.path.exists(backup_file):
            raise Exception(f"Файл бэкапа не найден: {backup_file}")
        
        # Сохранение информации о снимке
        version.snapshot_path = backup_file
        version.snapshot_size = os.path.getsize(backup_file)
        db.session.flush()
        _commit_with_retry()
        
        size_mb = version.snapshot_size / (1024 * 1024)
        log_to_db(
            user,
            f"Снимок версии БД успешно создан: v{version.version_number}",
            f"Файл: {backup_file}, Размер: {size_mb:.2f} МБ",
            entity_type="database_version",
            entity_id=version_id
        )
        
        return version
        
    except subprocess.TimeoutExpired:
        error_msg = "Превышено время ожидания создания бэкапа (>1 час)"
        log_to_db(
            user,
            f"Ошибка создания снимка версии БД: {version.version_number}",
            error_msg,
            entity_type="database_version",
            entity_id=version_id
        )
        raise ValueError(error_msg)
    except Exception as e:
        error_msg = str(e)
        log_to_db(
            user,
            f"Ошибка создания снимка версии БД: {version.version_number}",
            error_msg,
            entity_type="database_version",
            entity_id=version_id
        )
        # Удаляем частично созданный файл
        if 'backup_file' in locals() and os.path.exists(backup_file):
            try:
                os.remove(backup_file)
            except:
                pass
        raise ValueError(f"Ошибка создания снимка: {error_msg}")


def fix_version_relationships(version_id, user):
    """
    Исправляет связи между таблицами для существующей версии.
    Используется для исправления версий, которые были созданы без правильного обновления связей.
    
    Args:
        version_id: ID версии для исправления
        user: Пользователь для логирования
    """
    version = db.session.get(DatabaseVersion, version_id)
    if not version:
        raise ValueError(f"Версия с ID {version_id} не найдена.")
    
    log_to_db(
        user,
        f"Начало исправления связей для версии: v{version.version_number}",
        f"ID: {version_id}",
        entity_type="database_version",
        entity_id=version_id
    )
    
    try:
        # Получаем соответствия ID между версиями
        id_mappings = _build_version_id_mappings(version_id, user)
        
        # Обновляем связи (используем молниеносную версию)
        _update_version_relationships_lightning_fast(id_mappings, version_id, user)
        
        db.session.commit()
        
        log_to_db(
            user,
            f"Исправление связей для версии завершено: v{version.version_number}",
            f"ID: {version_id}",
            entity_type="database_version",
            entity_id=version_id
        )
        
        return version
        
    except Exception as e:
        db.session.rollback()
        error_msg = str(e)
        log_to_db(
            user,
            f"Ошибка исправления связей для версии: {version.version_number}",
            error_msg,
            entity_type="database_version",
            entity_id=version_id
        )
        raise ValueError(f"Ошибка исправления связей: {error_msg}")


def _build_version_id_mappings(version_id, user):
    """
    Строит соответствия ID между версиями для исправления связей.
    
    Args:
        version_id: ID версии
        user: Пользователь для логирования
        
    Returns:
        dict: Словарь соответствий ID по таблицам
    """
    current_app.logger.info(f"Построение соответствий ID для версии {version_id}")
    
    # Таблицы для обработки
    tables = [
        'gs_gen.gs_gen_station_groups',
        'gs_gen.gs_gen_stations', 
        'gs_gen.gs_gen_machines',
        'gs_gen.gs_gen_machine_powers',
        'gs_gen.gs_gen_machine_fuels',
        'gs_gen.gs_gen_machine_tes_types',
        'gs_gen.gs_gen_station_powers',
        'gs_gen.gs_gen_pgu_machines',
        'gs_gen.gs_gen_pgu_machine_powers',
        'gs_gen.gs_gen_boilers'
    ]
    
    id_mappings = {}
    
    for table in tables:
        try:
            # Получаем записи версии, отсортированные по имени для соответствия
            if 'stations' in table:
                # Для станций сортируем по имени
                query = text(f"""
                    SELECT id, name FROM {table} 
                    WHERE database_version_id = :version_id 
                    ORDER BY name
                """)
            elif 'machines' in table:
                # Для машин сортируем по id_station и номеру
                query = text(f"""
                    SELECT id, id_station, machine_number FROM {table} 
                    WHERE database_version_id = :version_id 
                    ORDER BY id_station, machine_number
                """)
            else:
                # Для остальных таблиц сортируем по ID
                query = text(f"""
                    SELECT id FROM {table} 
                    WHERE database_version_id = :version_id 
                    ORDER BY id
                """)
            
            result = db.session.execute(query, {"version_id": version_id})
            version_records = [row for row in result]
            
            # Получаем соответствующие записи из родительской версии или NULL версии
            parent_version = DatabaseVersion.query.get(version_id)
            source_version_id = parent_version.parent_version_id if parent_version else None
            
            if source_version_id:
                if 'stations' in table:
                    source_query = text(f"""
                        SELECT id, name FROM {table} 
                        WHERE database_version_id = :source_version_id 
                        ORDER BY name
                    """)
                elif 'machines' in table:
                    source_query = text(f"""
                        SELECT id, id_station, machine_number FROM {table} 
                        WHERE database_version_id = :source_version_id 
                        ORDER BY id_station, machine_number
                    """)
                else:
                    source_query = text(f"""
                        SELECT id FROM {table} 
                        WHERE database_version_id = :source_version_id 
                        ORDER BY id
                    """)
            else:
                if 'stations' in table:
                    source_query = text(f"""
                        SELECT id, name FROM {table} 
                        WHERE database_version_id IS NULL 
                        ORDER BY name
                    """)
                elif 'machines' in table:
                    source_query = text(f"""
                        SELECT id, id_station, machine_number FROM {table} 
                        WHERE database_version_id IS NULL 
                        ORDER BY id_station, machine_number
                    """)
                else:
                    source_query = text(f"""
                        SELECT id FROM {table} 
                        WHERE database_version_id IS NULL 
                        ORDER BY id
                    """)
            
            source_result = db.session.execute(source_query, {"source_version_id": source_version_id})
            source_records = [row for row in source_result]
            
            # Создаем соответствие
            if len(version_records) == len(source_records):
                mapping = {}
                for i, (version_record, source_record) in enumerate(zip(version_records, source_records)):
                    source_id = source_record[0]
                    version_id_new = version_record[0]
                    mapping[source_id] = version_id_new
                
                id_mappings[table] = mapping
                current_app.logger.info(f"Создано соответствие для {table}: {len(mapping)} записей")
            else:
                current_app.logger.warning(f"Количество записей не совпадает для {table}: версия={len(version_records)}, источник={len(source_records)}")
                
        except Exception as e:
            current_app.logger.error(f"Ошибка построения соответствий для {table}: {str(e)}")
    
    return id_mappings


def load_version_snapshot(version_id, user):
    """
    Загружает данные из снимка указанной версии через pg_restore.
    ВНИМАНИЕ: Эта операция заменит все данные в БД!
    """
    import subprocess
    import os
    from datetime import datetime
    from flask import current_app
    
    version = db.session.get(DatabaseVersion, version_id)
    if not version:
        raise ValueError(f"Версия с ID {version_id} не найдена.")
    
    if not version.snapshot_path:
        raise ValueError(f"У версии {version.version_number} нет сохраненного снимка.")
    
    if not os.path.exists(version.snapshot_path):
        raise ValueError(f"Файл снимка не найден: {version.snapshot_path}")
    
    log_to_db(
        user,
        f"Начало загрузки снимка версии БД: v{version.version_number}",
        f"ВНИМАНИЕ: Все данные в БД будут заменены! Файл: {version.snapshot_path}",
        entity_type="database_version",
        entity_id=version_id
    )
    
    try:
        # Получение параметров подключения к БД
        db_host = os.getenv("DB_HOST", "localhost")
        db_port = os.getenv("DB_PORT", "5432")
        db_user = os.getenv("DB_USER")
        db_name = os.getenv("DB_NAME")
        db_pass = os.getenv("DB_PASS")
        
        if not all([db_user, db_name]):
            raise ValueError("Не указаны параметры подключения к БД (DB_USER, DB_NAME)")
        
        # ВАЖНО: Создаем автоматический бэкап текущего состояния перед восстановлением
        current_app.logger.info("Создание автоматического бэкапа перед восстановлением...")
        try:
            backup_dir = "backups/auto_before_restore"
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            auto_backup_file = os.path.join(backup_dir, f"auto_backup_before_restore_{timestamp}.dump")
            
            # Поиск pg_dump
            pg_dump_path = _find_pg_binary("pg_dump")
            
            cmd_backup = [
                pg_dump_path,
                "-h", db_host,
                "-p", db_port,
                "-U", db_user,
                "-F", "c",
                "-f", auto_backup_file,
                db_name
            ]
            
            env = os.environ.copy()
            if db_pass:
                env["PGPASSWORD"] = db_pass
            
            result_backup = subprocess.run(
                cmd_backup,
                env=env,
                capture_output=True,
                text=True,
                timeout=3600
            )
            
            if result_backup.returncode == 0:
                current_app.logger.info(f"Автоматический бэкап создан: {auto_backup_file}")
                log_to_db(
                    user,
                    "Создан автоматический бэкап перед восстановлением",
                    f"Файл: {auto_backup_file}",
                    entity_type="database_version"
                )
            else:
                current_app.logger.warning(f"Не удалось создать автобэкап: {result_backup.stderr}")
        except Exception as e:
            current_app.logger.warning(f"Ошибка создания автобэкапа: {e}")
            # Продолжаем восстановление даже если автобэкап не удался
        
        # Проверка активных соединений к БД (может вызвать проблемы при восстановлении)
        try:
            from sqlalchemy import text
            result = db.session.execute(text("""
                SELECT COUNT(*) as active_connections 
                FROM pg_stat_activity 
                WHERE datname = current_database() 
                AND pid <> pg_backend_pid()
                AND state = 'active'
            """))
            active_count = result.scalar()
            if active_count > 0:
                current_app.logger.warning(
                    f"Обнаружено {active_count} активных соединений к БД. "
                    "Это может вызвать блокировки при восстановлении. "
                    "Рекомендуется закрыть активные соединения перед восстановлением."
                )
        except Exception as e:
            current_app.logger.warning(f"Не удалось проверить активные соединения: {e}")
        
        # Поиск pg_restore
        pg_restore_path = _find_pg_binary("pg_restore")
        current_app.logger.info(f"Используется pg_restore: {pg_restore_path}")
        
        # Проверка существования pg_restore
        import shutil
        if not shutil.which(pg_restore_path) and not os.path.exists(pg_restore_path):
            raise ValueError(
                "Утилита pg_restore не найдена. "
                "Убедитесь, что PostgreSQL установлен и директория bin добавлена в PATH. "
                f"Поиск выполнялся: {pg_restore_path}"
            )
        
        # Команда pg_restore
        # Используем --clean для очистки существующих объектов
        # --if-exists чтобы не выдавать ошибки если объект не существует
        # ВАЖНО: --single-transaction убран, т.к. с --clean может вызывать deadlock
        # и зависания при активных соединениях к БД
        cmd = [
            pg_restore_path,
            "-h", db_host,
            "-p", db_port,
            "-U", db_user,
            "-d", db_name,
            "-w",                  # do not prompt for password; fail fast if missing
            "--clean",              # Удалить существующие объекты
            "--if-exists",          # Не выдавать ошибки если объект не существует
            "--no-owner",           # Не пытаться восстанавливать владельцев
            "--no-privileges",      # Не восстанавливать права
            "-j", "1",              # Использовать 1 поток (избегаем проблем с блокировками)
            "-v",                   # verbose
            version.snapshot_path
        ]
        
        # Подготовка окружения с паролем
        env = os.environ.copy()
        if db_pass:
            env["PGPASSWORD"] = db_pass
        
        # Выполнение pg_restore со streaming вывода, чтобы избежать блокировки буфера
        current_app.logger.info(f"Запуск pg_restore для версии {version.version_number}")
        process = subprocess.Popen(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1  # Line buffered
        )
        
        try:
            import threading
            from queue import Queue, Empty
            
            # Используем очередь для неблокирующего чтения stdout
            output_queue = Queue()
            read_timeout = 300  # 5 минут без вывода = возможное зависание
            
            def read_output():
                """Читает вывод процесса в отдельном потоке"""
                try:
                    for line in iter(process.stdout.readline, ''):  # type: ignore[attr-defined]
                        if not line:
                            break
                        output_queue.put(line.rstrip())
                except Exception as e:
                    current_app.logger.error(f"Ошибка чтения вывода pg_restore: {e}")
                finally:
                    output_queue.put(None)  # Сигнал окончания
            
            # Запускаем чтение в отдельном потоке
            reader_thread = threading.Thread(target=read_output, daemon=True)
            reader_thread.start()
            
            last_output_time = datetime.now()
            lines_read = 0
            
            # Читаем вывод с таймаутом
            while True:
                try:
                    line = output_queue.get(timeout=60)  # Ждем максимум 60 секунд
                    if line is None:  # Сигнал окончания
                        break
                    
                    if line:
                        current_app.logger.info(f"pg_restore: {line}")
                        last_output_time = datetime.now()
                        lines_read += 1
                    
                    # Проверяем, не завис ли процесс (нет вывода более 5 минут)
                    if (datetime.now() - last_output_time).total_seconds() > read_timeout:
                        current_app.logger.error(
                            f"pg_restore не выводит данные более {read_timeout} секунд. "
                            "Возможно зависание. Проверьте активные соединения к БД."
                        )
                        # Проверяем, жив ли процесс
                        if process.poll() is None:
                            current_app.logger.warning("Процесс pg_restore все еще работает, но не выводит данные")
                            # Продолжаем ждать, но логируем предупреждение
                            last_output_time = datetime.now()  # Сбрасываем таймер
                    
                except Empty:
                    # Таймаут очереди - проверяем статус процесса
                    if process.poll() is not None:
                        # Процесс завершился
                        break
                    # Если процесс еще работает, продолжаем ждать
                    if (datetime.now() - last_output_time).total_seconds() > read_timeout:
                        current_app.logger.warning(
                            f"pg_restore не выводит данные более {read_timeout} секунд, "
                            "но процесс все еще работает"
                        )
            
            # Ждем завершения процесса с таймаутом
            return_code = process.wait(timeout=3600)
            current_app.logger.info(f"pg_restore завершился с кодом {return_code}, прочитано строк: {lines_read}")
            
        except subprocess.TimeoutExpired:
            current_app.logger.error("Превышен таймаут ожидания pg_restore (>1 час)")
            process.kill()
            process.wait()
            raise
        
        if return_code not in [0, 1]:  # 1 - warning, 0 - success
            raise Exception(f"pg_restore завершился с ошибкой (код {return_code}). См. логи приложения для деталей.")
        
        log_to_db(
            user,
            f"Снимок версии БД успешно загружен: v{version.version_number}",
            f"Файл: {version.snapshot_path}",
            entity_type="database_version",
            entity_id=version_id
        )
        
        # Активируем восстановленную версию
        try:
            set_active_version(version_id, user)
        except:
            pass  # Игнорируем ошибки активации
        
        return version
        
    except subprocess.TimeoutExpired:
        error_msg = "Превышено время ожидания восстановления из бэкапа (>1 час)"
        log_to_db(
            user,
            f"Ошибка загрузки снимка версии БД: {version.version_number}",
            error_msg,
            entity_type="database_version",
            entity_id=version_id
        )
        raise ValueError(error_msg)
    except Exception as e:
        error_msg = str(e)
        log_to_db(
            user,
            f"Ошибка загрузки снимка версии БД: {version.version_number}",
            error_msg,
            entity_type="database_version",
            entity_id=version_id
        )
        raise ValueError(f"Ошибка загрузки снимка: {error_msg}")


def _verify_version_data_integrity(version_id, user):
    """
    Проверяет целостность данных после копирования версии.
    
    Args:
        version_id: ID версии для проверки
        user: Пользователь для логирования
    """
    current_app.logger.info(f"Начало проверки целостности данных версии {version_id}")
    
    integrity_issues = []
    
    # Проверяем основные связи
    integrity_checks = [
        {
            'name': 'Станции -> Группы станций',
            'query': text("""
                SELECT COUNT(*) as broken_links
                FROM gs_gen.gs_gen_stations s
                LEFT JOIN gs_gen.gs_gen_station_groups sg ON s.id_station_group = sg.id
                WHERE s.database_version_id = :version_id 
                  AND s.id_station_group IS NOT NULL 
                  AND sg.id IS NULL
            """)
        },
        {
            'name': 'Машины -> Станции',
            'query': text("""
                SELECT COUNT(*) as broken_links
                FROM gs_gen.gs_gen_machines m
                LEFT JOIN gs_gen.gs_gen_stations s ON m.id_station = s.id
                WHERE m.database_version_id = :version_id 
                  AND m.id_station IS NOT NULL 
                  AND s.id IS NULL
            """)
        },
        {
            'name': 'Мощности машин -> Машины',
            'query': text("""
                SELECT COUNT(*) as broken_links
                FROM gs_gen.gs_gen_machine_powers mp
                LEFT JOIN gs_gen.gs_gen_machines m ON mp.id_machine = m.id
                WHERE mp.database_version_id = :version_id 
                  AND mp.id_machine IS NOT NULL 
                  AND m.id IS NULL
            """)
        },
        {
            'name': 'ПГУ машины -> Машины',
            'query': text("""
                SELECT COUNT(*) as broken_links
                FROM gs_gen.gs_gen_pgu_machines pm
                LEFT JOIN gs_gen.gs_gen_machines m ON pm.id_machine = m.id
                WHERE pm.database_version_id = :version_id 
                  AND pm.id_machine IS NOT NULL 
                  AND m.id IS NULL
            """)
        }
    ]
    
    for check in integrity_checks:
        try:
            result = db.session.execute(check['query'], {"version_id": version_id})
            broken_links = result.scalar()
            
            if broken_links > 0:
                integrity_issues.append(f"{check['name']}: {broken_links} битых связей")
                current_app.logger.warning(f"Проблема целостности: {check['name']}: {broken_links} битых связей")
            else:
                current_app.logger.info(f"Проверка целостности пройдена: {check['name']}")
                
        except Exception as e:
            current_app.logger.error(f"Ошибка проверки целостности {check['name']}: {e}")
            integrity_issues.append(f"{check['name']}: ошибка проверки - {str(e)}")
    
    # Логируем результаты проверки
    if integrity_issues:
        issues_text = "; ".join(integrity_issues)
        log_to_db(
            user,
            f"Обнаружены проблемы целостности данных версии {version_id}",
            issues_text,
            entity_type="database_version",
            entity_id=version_id
        )
        current_app.logger.warning(f"Проблемы целостности данных версии {version_id}: {issues_text}")
    else:
        log_to_db(
            user,
            f"Проверка целостности данных версии {version_id} пройдена успешно",
            "Все связи корректны",
            entity_type="database_version",
            entity_id=version_id
        )
        current_app.logger.info(f"Проверка целостности данных версии {version_id} пройдена успешно")
    
    return len(integrity_issues) == 0

