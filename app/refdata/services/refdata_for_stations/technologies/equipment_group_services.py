"""Сервисный модуль: Типы групп оборудования."""

import uuid
from collections import defaultdict

from app.extensions import db
from sqlalchemy import func as sa_func, text
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 
from config import SCHEMA_REFDATA
        
# Модели
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroupType
from app.refdata.models.refdata_for_stations.technologies.technology_type_model import TechnologyType
from app.refdata.models.refdata_for_stations.technologies.technology_availability_model import TechnologyAvailability
from app.generation.models.machine.machine_model import Machine
from app.fuel.models.external_mapping.fue_em_equipment_group_model import (
    EquipmentGroupExternalMapping,
)
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation

# Сервисы
from app.common.services.get_services.refdata_for_stations.technologies.technology_type_get_services import (
    get_technology_type_name,
)
from app.common.services.get_services.refdata_for_stations.technologies.technology_availability_get_services import (
    get_technology_availability_name,
)
from app.common.services.help_services import (
    _dash,
    _to_int_or_none,
)
from app.common.services.tranzaction_services import (
    _commit_with_retry,
    _locked_get,
    no_autoflush,
    quick_fix_seq,
)

# Фильтрация по версиям
from app.common.models.database_version_model import DatabaseVersion
from app.common.services.database_version_filter import (
    apply_version_filter,
    filter_by_explicit_db_version,
    set_db_version_on_create,
)

# Логирование
from app.logs.services.logging_service import log_to_db
from app.logs.services.field_names_ru import format_field_change, get_field_name_ru


def _equipment_group_dup_query(name, technology_type_id, exclude_id=None):
    """Возвращает запрос для проверки дубликатов по паре (name, technology_type)."""
    query = apply_version_filter(EquipmentGroupType.query, EquipmentGroupType).filter(EquipmentGroupType.name == name)
    if technology_type_id is None:
        query = query.filter(EquipmentGroupType.id_technology_type.is_(None))
    else:
        query = query.filter(EquipmentGroupType.id_technology_type == technology_type_id)
    if exclude_id is not None:
        query = query.filter(EquipmentGroupType.id != exclude_id)
    return query


def _equipment_group_dup_query_for_version(name, technology_type_id, version_id, exclude_id=None):
    """Проверка дубликатов (name, technology_type) в пределах одной версии БД."""
    query = filter_by_explicit_db_version(EquipmentGroupType.query, EquipmentGroupType, version_id)
    query = query.filter(EquipmentGroupType.name == name)
    if technology_type_id is None:
        query = query.filter(EquipmentGroupType.id_technology_type.is_(None))
    else:
        query = query.filter(EquipmentGroupType.id_technology_type == technology_type_id)
    if exclude_id is not None:
        query = query.filter(EquipmentGroupType.id != exclude_id)
    return query


def _all_database_version_ids_for_refdata() -> list[int]:
    """Все зарегистрированные id версий БД (для синхронной записи справочника по версиям)."""
    return [
        v.id
        for v in DatabaseVersion.query.order_by(DatabaseVersion.version_number).all()
        if v.id is not None
    ]


def _merge_equipment_group_type_into_canonical(*, from_id: int, to_id: int, user) -> None:
    """
    Переносит все ссылки с типа группы оборудования from_id на to_id и удаляет строку from_id.
    Используется при сохранении, когда редактируемая запись дублирует пару (name, id_technology_type).
    """
    if from_id == to_id:
        return

    from_obj = db.session.get(EquipmentGroupType, from_id)
    to_obj = db.session.get(EquipmentGroupType, to_id)
    if not from_obj or not to_obj:
        raise ValueError(f"Слияние типов групп: запись from_id={from_id} или to_id={to_id} не найдена.")

    Machine.query.filter(Machine.id_equipment_group == from_id).update(
        {Machine.id_equipment_group: to_id},
        synchronize_session=False,
    )

    # По одной строке + flush: при нескольких записях с (station, from_id, NULL) в UNIQUE
    # подзапрос «уже есть to_id» не видит только что обновлённые строки до flush.
    while True:
        old_link = (
            EquipmentGroupSetStation.query.filter_by(
                equipment_group_type_id=from_id
            ).first()
        )
        if old_link is None:
            break

        q = EquipmentGroupSetStation.query.filter(
            EquipmentGroupSetStation.station_id == old_link.station_id,
            EquipmentGroupSetStation.equipment_group_type_id == to_id,
        )
        if old_link.database_version_id is None:
            q = q.filter(EquipmentGroupSetStation.database_version_id.is_(None))
        else:
            q = q.filter(
                EquipmentGroupSetStation.database_version_id == old_link.database_version_id
            )
        new_link = q.first()

        if new_link is None:
            old_link.equipment_group_type_id = to_id
        else:
            old_link_id = old_link.id
            for egs in EquipmentGroupSet.query.filter_by(
                equipment_group_set_station_id=old_link_id
            ).all():
                conflict = EquipmentGroupSet.query.filter_by(
                    equipment_group_id=egs.equipment_group_id,
                    equipment_group_set_station_id=new_link.id,
                ).first()
                if conflict:
                    db.session.delete(egs)
                else:
                    egs.equipment_group_set_station_id = new_link.id

            db.session.flush()

            if (
                EquipmentGroupSet.query.filter_by(
                    equipment_group_set_station_id=old_link_id
                ).count()
                > 0
            ):
                raise ValueError(
                    f"Слияние типов групп: остались связи gs_fue_equipment_group_sets "
                    f"на station_link id={old_link_id} после переноса на id={new_link.id}."
                )

            # Не db.session.delete(old_link): по backref ORM может обнулить
            # equipment_group_set_station_id у gs_fue_equipment_group_sets (NOT NULL).
            db.session.expunge(old_link)
            deleted_sl = (
                db.session.query(EquipmentGroupSetStation)
                .filter(EquipmentGroupSetStation.id == old_link_id)
                .delete(synchronize_session=False)
            )
            if deleted_sl != 1:
                raise ValueError(
                    f"Слияние: ожидалось удалить одну строку gs_fue_equipment_group_type_stations "
                    f"id={old_link_id}, удалено {deleted_sl}."
                )

        db.session.flush()

    # Не db.session.delete(from_obj): по backref SQLAlchemy может обнулить FK у
    # gs_fue_equipment_group_type_stations (equipment_group_type_id NOT NULL) перед DELETE родителя.
    db.session.expunge(from_obj)
    deleted_rows = (
        db.session.query(EquipmentGroupType)
        .filter(EquipmentGroupType.id == from_id)
        .delete(synchronize_session=False)
    )
    if deleted_rows != 1:
        raise ValueError(
            f"Слияние типов групп: ожидалось удалить одну строку id={from_id}, удалено {deleted_rows}."
        )
    db.session.flush()

    log_to_db(
        user,
        "Слияние типов групп оборудования",
        f"Дубликат id={from_id} объединён с id={to_id}; ссылки переназначены, дубликат удалён.",
        entity_type="equipment_group",
        entity_id=to_id,
    )


def _merge_submitted_batch_duplicates(
    data: list,
    user,
    merged_away_ids: set[int],
    updated_ids: list,
) -> None:
    """
    В одной форме несколько строк с одинаковой парой (name, technology_type_id).
    Оставляем запись с минимальным id, остальные сливаем в неё.
    Иначе при уже совпадающих в БД полях не срабатывала ветка «изменение → дубликат».
    """
    groups = defaultdict(list)
    for record in data:
        name = (record.get("name") or "").strip()
        if not name:
            continue
        tid = _to_int_or_none(record.get("technology_type_id"), keep_zero=False)
        try:
            eg_id_int = int(record.get("equipment_group_id"))
        except (TypeError, ValueError):
            continue
        groups[(name, tid)].append(eg_id_int)

    for _key, ids in groups.items():
        uniq = sorted(set(ids))
        if len(uniq) <= 1:
            continue
        canonical = uniq[0]
        for other in uniq[1:]:
            if other in merged_away_ids:
                continue
            _merge_equipment_group_type_into_canonical(
                from_id=other,
                to_id=canonical,
                user=user,
            )
            merged_away_ids.add(other)
            if canonical not in updated_ids:
                updated_ids.append(canonical)


def _find_replacement_equipment_group(obj, exclude_id):
    """
    Ищет дубликат по названию для переназначения ссылок.
    Берем любую другую запись с таким же name (во всех версиях),
    с минимальным id.
    """
    return (
        EquipmentGroupType.query
        .filter(
            EquipmentGroupType.name == obj.name,
            EquipmentGroupType.id != exclude_id,
        )
        .order_by(EquipmentGroupType.id.asc())
        .first()
    )


def equipment_group_query(
        equipment_group_filter=None, 
        technology_type_filter=None, 
        technology_availability_filter=None, 
        sort_by="display_order", 
        sort_dir="asc"):
    """ Базовый запрос для выборки типов групп оборудования с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id", "name", "technology_type", "technology_availability", "display_order", "number"}
    sort_by = sort_by if sort_by in allowed_sort_by else "display_order"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Безопасная конвертация ID-фильтров
    technology_type_id = _to_int_or_none(technology_type_filter)
    technology_availability_id = _to_int_or_none(technology_availability_filter)

    # Базовый запрос
    query = EquipmentGroupType.query.filter(EquipmentGroupType.id.isnot(None), EquipmentGroupType.id > 0)
    query = apply_version_filter(query, EquipmentGroupType)

    # Загрузка связанных данных
    query = query.options(
        joinedload(EquipmentGroupType.technology_type),
        joinedload(EquipmentGroupType.technology_availability)
    )

    # Отслеживание примененных JOIN'ов для избежания дублирования
    joined_tech_type = False
    joined_tech_avail = False

    # Фильтрация
    if equipment_group_filter:
        query = query.filter(EquipmentGroupType.name.ilike(f"%{equipment_group_filter}%"))

    # Фильтр по типу технологии:
    # - если передан ID (из выпадающего списка) — фильтруем по EquipmentGroupType.id_technology_type
    # - если передана строка (ручной ввод) — фильтруем по имени типа технологии
    if technology_type_id is not None:
        query = query.filter(EquipmentGroupType.id_technology_type == technology_type_id)
    elif technology_type_filter:
        query = query.join(
            TechnologyType,
            EquipmentGroupType.id_technology_type == TechnologyType.id,
            isouter=True,
        )
        query = query.filter(TechnologyType.name.ilike(f"%{technology_type_filter}%"))
        joined_tech_type = True

    # Фильтр по доступности технологии (аналогично типу технологии)
    if technology_availability_id is not None:
        query = query.filter(EquipmentGroupType.id_technology_availability == technology_availability_id)
    elif technology_availability_filter:
        query = query.join(
            TechnologyAvailability,
            EquipmentGroupType.id_technology_availability == TechnologyAvailability.id,
            isouter=True,
        )
        query = query.filter(TechnologyAvailability.name.ilike(f"%{technology_availability_filter}%"))
        joined_tech_avail = True

    # Сортировка
    if sort_by == "name":
        sort_col = EquipmentGroupType.name
    elif sort_by == "technology_type":
        if not joined_tech_type:
            query = query.join(TechnologyType, EquipmentGroupType.id_technology_type == TechnologyType.id, isouter=True)
        sort_col = TechnologyType.name
    elif sort_by == "technology_availability":
        if not joined_tech_avail:
            query = query.join(TechnologyAvailability, EquipmentGroupType.id_technology_availability == TechnologyAvailability.id, isouter=True)
        sort_col = TechnologyAvailability.name
    elif sort_by == "display_order":
        if sort_dir == "desc":
            query = query.order_by(
                (EquipmentGroupType.display_order.is_(None)),
                EquipmentGroupType.display_order.desc()
            )
        else:
            query = query.order_by(
                (EquipmentGroupType.display_order.is_(None)),
                EquipmentGroupType.display_order.asc()
            )
    else:
        sort_col = EquipmentGroupType.id

    if sort_by != "display_order":
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    return query


@no_autoflush
def get_equipment_group_list(
    page, 
    per_page, 
    equipment_group_filter=None,
    technology_type_filter=None,
    technology_availability_filter=None,
    sort_by="display_order", 
    sort_dir="asc"):
    """ Получает список типов групп оборудования с пагинацией, фильтрацией и сортировкой. """
    
    # Базовый запрос
    query = equipment_group_query(
        equipment_group_filter=equipment_group_filter,
        technology_type_filter=technology_type_filter,
        technology_availability_filter=technology_availability_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_equipment_group_service(data, user):
    """ Обновление данных по типам групп оборудования """

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []
    merged_away_ids: set[int] = set()

    log_to_db(
        user, 
        "Получены данные для обновления списка типов групп оборудования", 
        f"{data}", 
        entity_type="equipment_group")
    
    last_entity_id = None

    # flush() может выбросить IntegrityError до commit — ловим в том же try, что и _commit_with_retry()
    try:
        with db.session.no_autoflush:
            _merge_submitted_batch_duplicates(data, user, merged_away_ids, updated_ids)

            for record in data:
                equipment_group_id = record.get("equipment_group_id")
                last_entity_id = equipment_group_id
                display_order = record.get("display_order")
                name = (record.get("name") or "").strip()
                new_technology_type_id = _to_int_or_none(record.get("technology_type_id"), keep_zero=False)

                # Проверка наличия наименования
                if not name:
                    raise ValueError(f"Поле 'name' обязательно для заполнения.")

                try:
                    eg_id_int = int(equipment_group_id)
                except (TypeError, ValueError):
                    raise ValueError(f"Некорректный ID типа группы оборудования: {equipment_group_id!r}")
                if eg_id_int in merged_away_ids:
                    continue

                obj = db.session.get(EquipmentGroupType, equipment_group_id)
                if not obj:
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись с ID «{equipment_group_id}» не найдена.", 
                        entity_type="equipment_group", 
                        entity_id=equipment_group_id)
                    raise ValueError(f"Запись с ID «{equipment_group_id}» не найдена.")

                # Пара (name, technology_type): при дубле с уже существующей записью — сливаем с неё
                if name != (obj.name or "") or new_technology_type_id != obj.id_technology_type:
                    dup = (
                        _equipment_group_dup_query(name, new_technology_type_id, exclude_id=equipment_group_id)
                        .order_by(EquipmentGroupType.id.asc())
                        .with_for_update()
                        .first()
                    )
                    if dup:
                        # Редактируемая строка (equipment_group_id) удаляется, ссылки переносятся на dup
                        _merge_equipment_group_type_into_canonical(
                            from_id=eg_id_int,
                            to_id=dup.id,
                            user=user,
                        )
                        merged_away_ids.add(eg_id_int)
                        updated_ids.append(dup.id)
                        continue

                # Проверка уникальности display_order
                if display_order != obj.display_order:
                    if display_order is not None:
                        q_display = (apply_version_filter(EquipmentGroupType.query, EquipmentGroupType)
                                    .filter(EquipmentGroupType.display_order == display_order,
                                            EquipmentGroupType.id != equipment_group_id))
                        if q_display.first():
                            raise ValueError(f"Запись с порядком отображения «{display_order}» уже существует.")

                changes = []

                if name != (obj.name or ""):
                    changes.append(format_field_change("name", obj.name or "не указано", name, "equipment_group"))
                    obj.name = name

                if display_order != obj.display_order:
                    old_val = obj.display_order if obj.display_order is not None else "не указано"
                    new_val = display_order if display_order is not None else "не указано"
                    changes.append(f"Порядок отображения: {old_val} → {new_val}")
                    obj.display_order = display_order

                # Проверка наличия типа технологии
                if "technology_type_id" in record:
                    new_val = new_technology_type_id
                    if new_val != obj.id_technology_type:
                        new_obj = db.session.get(TechnologyType, new_val) if new_val is not None else None
                        if new_val is not None and not new_obj:
                            raise ValueError(f"Тип технологии с id={new_val} не найден.")
                        
                        prev_obj = db.session.get(TechnologyType, obj.id_technology_type) if obj.id_technology_type else None
                        old_name = prev_obj.name if prev_obj else "не указано"
                        new_name = new_obj.name if new_obj else "не указано"
                        changes.append(format_field_change("id_technology_type", old_name, new_name, "equipment_group"))
                        obj.id_technology_type = new_val

                # Проверка наличия типа доступности технологии
                if "technology_availability_id" in record:
                    new_val = _to_int_or_none(record.get("technology_availability_id"), keep_zero=False)
                    if new_val != obj.id_technology_availability:
                        new_obj = db.session.get(TechnologyAvailability, new_val) if new_val is not None else None
                        if new_val is not None and not new_obj:
                            raise ValueError(f"Тип доступности технологии с id={new_val} не найден.")
                        
                        prev_obj = db.session.get(TechnologyAvailability, obj.id_technology_availability) if obj.id_technology_availability else None
                        old_name = prev_obj.name if prev_obj else "не указано"
                        new_name = new_obj.name if new_obj else "не указано"
                        changes.append(format_field_change("id_technology_availability", old_name, new_name, "equipment_group"))
                        obj.id_technology_availability = new_val

                # Если есть реальные изменения — лог и добавление в список
                if changes:
                    log_to_db(
                        user, 
                        f"Обновлена группа оборудования: {name}", 
                        f"Изменения: {'; '.join(changes)}", 
                        entity_type="equipment_group", 
                        entity_id=equipment_group_id)
                    updated_ids.append(equipment_group_id)

            db.session.flush()

        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по типам групп оборудования", 
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})", 
                entity_type="equipment_group",
                entity_id=last_entity_id)
        else:
            log_to_db(
                user, 
                "Изменений по типам групп оборудования не обнаружено", 
                "", 
                entity_type="equipment_group")
            
        return updated_ids
    
    except IntegrityError as e:
        db.session.rollback()
        detail = getattr(e, "orig", None) or e
        log_to_db(
            user, 
            "Ошибка сохранения типов групп оборудования (уникальность/целостность)", 
            str(detail), 
            entity_type="equipment_group",
            entity_id=last_entity_id)
        raise ValueError(
            f"Ошибка сохранения: ограничение базы данных ({detail}). "
            f"Часто это дублирующееся наименование или порядок отображения."
        ) from e
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Неизвестная ошибка при сохранении типов групп оборудования", 
            str(e), 
            entity_type="equipment_group",
            entity_id=last_entity_id)
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}") from e


@no_autoflush
def add_equipment_group_service(data, user):
    """Создание новой записи: тип группы оборудования"""
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    def _do_insert():
        with db.session.no_autoflush:
            for record in data:
                display_order = record.get("display_order")
                name = (record.get("name") or "").strip()
                technology_type_id = _to_int_or_none(record.get("technology_type_id"), keep_zero=False)
                technology_availability_id = _to_int_or_none(record.get("technology_availability_id"), keep_zero=False)

                if not name:
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись: {record}", 
                        entity_type="equipment_group")
                    raise ValueError("Каждая запись должна содержать 'name'.")

                # Проверяем существование типа технологии (если указан)
                if technology_type_id is not None:
                    obj = db.session.get(TechnologyType, technology_type_id)
                    if not obj:
                        raise ValueError(f"Тип технологии с id={technology_type_id} не найден.")
                
                # Проверяем существование типа доступности технологии (если указан)
                if technology_availability_id is not None:
                    obj = db.session.get(TechnologyAvailability, technology_availability_id)
                    if not obj:
                        raise ValueError(f"Тип доступности технологии с id={technology_availability_id} не найден.")

                dup = (_equipment_group_dup_query(name, technology_type_id)
                       .with_for_update()
                       .first())
                if dup:
                    tech_name = get_technology_type_name(technology_type_id) or "не указано"
                    raise ValueError(
                        f"Запись с наименованием «{name}» и типом технологии «{tech_name}» уже существует."
                    )

                # Проверяем уникальность display_order при создании
                if display_order is not None:
                    dup_display = (apply_version_filter(EquipmentGroupType.query, EquipmentGroupType)
                            .filter(EquipmentGroupType.display_order == display_order)
                            .with_for_update().first())
                    if dup_display:
                        raise ValueError(f"Запись с порядком отображения «{display_order}» уже существует.")

                obj = EquipmentGroupType(
                    display_order=display_order,
                    name=name,
                    id_technology_type=technology_type_id,
                    id_technology_availability=technology_availability_id
                )
                set_db_version_on_create(obj)
                db.session.add(obj)
                db.session.flush()

                log_to_db(
                    user, 
                    "Создан тип группы оборудования", 
                    f"Порядок отображения: {_dash(display_order)}; "
                    f"Тип технологии: {get_technology_type_name(technology_type_id)} "
                    f"Тип доступности технологии: {get_technology_availability_name(technology_availability_id)} ",
                    entity_type="equipment_group", 
                    entity_id=obj.id)

    try:
        _do_insert()
        _commit_with_retry()
        return None

    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "equipment_groups")
        _do_insert()
        _commit_with_retry()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения нового типа группы оборудования", 
            str(e), 
            entity_type="equipment_group")
        raise ValueError(f"Ошибка сохранения нового типа группы оборудования: {e}") from e


@no_autoflush
def add_equipment_group_all_versions_service(data, user):
    """
    Создаёт по одной записи типа группы в каждой зарегистрированной версии БД
    с общим ref_uuid.
    """
    if not isinstance(data, list) or not data:
        raise ValueError("Данные должны быть предоставлены в виде непустого списка словарей.")

    version_ids = _all_database_version_ids_for_refdata()
    if not version_ids:
        raise ValueError(
            "В системе нет зарегистрированных версий БД — нельзя выполнить добавление «во всех версиях»."
        )
    shared_ref = str(uuid.uuid4())

    def _do_inserts():
        with db.session.no_autoflush:
            for record in data:
                display_order = record.get("display_order")
                name = (record.get("name") or "").strip()
                technology_type_id = _to_int_or_none(record.get("technology_type_id"), keep_zero=False)
                technology_availability_id = _to_int_or_none(
                    record.get("technology_availability_id"), keep_zero=False
                )

                if not name:
                    log_to_db(
                        user,
                        "Ошибка валидации (добавление во всех версиях)",
                        f"Запись: {record}",
                        entity_type="equipment_group",
                    )
                    raise ValueError("Каждая запись должна содержать 'name'.")

                if technology_type_id is not None:
                    obj = db.session.get(TechnologyType, technology_type_id)
                    if not obj:
                        raise ValueError(f"Тип технологии с id={technology_type_id} не найден.")

                if technology_availability_id is not None:
                    obj = db.session.get(TechnologyAvailability, technology_availability_id)
                    if not obj:
                        raise ValueError(
                            f"Тип доступности технологии с id={technology_availability_id} не найден."
                        )

                for vid in version_ids:
                    vlabel = f"версия БД id={vid}"

                    dup = _equipment_group_dup_query_for_version(
                        name, technology_type_id, vid, exclude_id=None
                    )
                    if dup.with_for_update().first():
                        tech_name = get_technology_type_name(technology_type_id) or "не указано"
                        raise ValueError(
                            f"В {vlabel} уже есть запись с наименованием «{name}» "
                            f"и типом технологии «{tech_name}»."
                        )

                    if display_order is not None:
                        q_display = (
                            filter_by_explicit_db_version(
                                EquipmentGroupType.query, EquipmentGroupType, vid
                            )
                            .filter(EquipmentGroupType.display_order == display_order)
                            .with_for_update()
                        )
                        if q_display.first():
                            raise ValueError(
                                f"Порядок отображения «{display_order}» уже занят в {vlabel}."
                            )

                    obj = EquipmentGroupType(
                        display_order=display_order,
                        name=name,
                        id_technology_type=technology_type_id,
                        id_technology_availability=technology_availability_id,
                    )
                    obj.ref_uuid = shared_ref
                    obj.database_version_id = vid
                    db.session.add(obj)
                    db.session.flush()

                    log_to_db(
                        user,
                        "Создан тип группы оборудования (во всех версиях БД)",
                        f"Наименование: {name}; {vlabel}; "
                        f"Порядок: {_dash(display_order)}; "
                        f"Тип технологии: {get_technology_type_name(technology_type_id)}; "
                        f"Тип доступности: {get_technology_availability_name(technology_availability_id)}",
                        entity_type="equipment_group",
                        entity_id=obj.id,
                    )

    try:
        _do_inserts()
        _commit_with_retry()
        return None
    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "equipment_groups")
        _do_inserts()
        _commit_with_retry()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user,
            "Ошибка сохранения нового типа группы (во всех версиях БД)",
            str(e),
            entity_type="equipment_group",
        )
        raise ValueError(
            f"Ошибка сохранения нового типа группы оборудования во всех версиях: {e}"
        ) from e


@no_autoflush
def update_equipment_group_all_versions_service(data, user):
    """
    Повторяет пакетное обновление для всех копий с тем же ref_uuid.

    При сохранении "во всех версиях" переносит текущее состояние строки во все копии
    с тем же ref_uuid, включая display_order. Если целевой порядок отображения уже
    занят в одной из версий, операция отклоняется целиком.
    """
    if not isinstance(data, list) or not data:
        raise ValueError("Данные должны быть непустым списком словарей.")

    all_updated: list = []
    last_entity_id = None

    try:
        with db.session.no_autoflush:
            for record in data:
                equipment_group_id = record.get("equipment_group_id")
                last_entity_id = equipment_group_id
                try:
                    eg_id_int = int(equipment_group_id)
                except (TypeError, ValueError):
                    raise ValueError(
                        f"Некорректный ID типа группы оборудования: {equipment_group_id!r}"
                    )

                anchor = db.session.get(EquipmentGroupType, eg_id_int)
                if not anchor:
                    raise ValueError(
                        f"Запись с ID «{equipment_group_id}» не найдена (обновление во всех версиях БД)."
                    )
                if not anchor.ref_uuid:
                    raise ValueError(
                        f"У записи id={eg_id_int} нет ref_uuid: синхронизация между версиями невозможна."
                    )

                target_rows = (
                    EquipmentGroupType.query
                    .filter(EquipmentGroupType.ref_uuid == anchor.ref_uuid)
                    .order_by(EquipmentGroupType.id)
                    .with_for_update()
                    .all()
                )

                requested_display_order = record.get("display_order")
                requested_name = (record.get("name") or "").strip()
                requested_technology_type_id = _to_int_or_none(
                    record.get("technology_type_id"), keep_zero=False
                )
                requested_technology_availability_id = _to_int_or_none(
                    record.get("technology_availability_id"), keep_zero=False
                )

                if not requested_name:
                    raise ValueError("Поле 'name' обязательно для заполнения.")

                if requested_technology_type_id is not None:
                    tech_obj = db.session.get(TechnologyType, requested_technology_type_id)
                    if not tech_obj:
                        raise ValueError(
                            f"Тип технологии с id={requested_technology_type_id} не найден."
                        )

                if requested_technology_availability_id is not None:
                    avail_obj = db.session.get(
                        TechnologyAvailability, requested_technology_availability_id
                    )
                    if not avail_obj:
                        raise ValueError(
                            f"Тип доступности технологии с id={requested_technology_availability_id} не найден."
                        )

                for obj in target_rows:
                    target_version_id = obj.database_version_id
                    target_display_order = requested_display_order

                    dup = (
                        _equipment_group_dup_query_for_version(
                            requested_name,
                            requested_technology_type_id,
                            target_version_id,
                            exclude_id=obj.id,
                        )
                        .order_by(EquipmentGroupType.id.asc())
                        .with_for_update()
                        .first()
                    )
                    if dup:
                        raise ValueError(
                            f"В версии БД id={target_version_id} уже есть запись с наименованием "
                            f"«{requested_name}» и выбранным типом технологии."
                        )

                    if target_display_order != obj.display_order and target_display_order is not None:
                        q_display = (
                            filter_by_explicit_db_version(
                                EquipmentGroupType.query, EquipmentGroupType, target_version_id
                            )
                            .filter(
                                EquipmentGroupType.display_order == target_display_order,
                                EquipmentGroupType.id != obj.id,
                            )
                            .with_for_update()
                        )
                        if q_display.first():
                            raise ValueError(
                                f"В версии БД id={target_version_id} порядок отображения "
                                f"«{target_display_order}» уже занят."
                            )

                    changes = []

                    if requested_name != (obj.name or ""):
                        changes.append(
                            format_field_change("name", obj.name or "не указано", requested_name, "equipment_group")
                        )
                        obj.name = requested_name

                    if target_display_order != obj.display_order:
                        old_val = obj.display_order if obj.display_order is not None else "не указано"
                        new_val = target_display_order if target_display_order is not None else "не указано"
                        changes.append(f"Порядок отображения: {old_val} → {new_val}")
                        obj.display_order = target_display_order

                    if requested_technology_type_id != obj.id_technology_type:
                        prev_obj = (
                            db.session.get(TechnologyType, obj.id_technology_type)
                            if obj.id_technology_type
                            else None
                        )
                        new_obj = (
                            db.session.get(TechnologyType, requested_technology_type_id)
                            if requested_technology_type_id is not None
                            else None
                        )
                        old_name = prev_obj.name if prev_obj else "не указано"
                        new_name = new_obj.name if new_obj else "не указано"
                        changes.append(
                            format_field_change("id_technology_type", old_name, new_name, "equipment_group")
                        )
                        obj.id_technology_type = requested_technology_type_id

                    if requested_technology_availability_id != obj.id_technology_availability:
                        prev_obj = (
                            db.session.get(TechnologyAvailability, obj.id_technology_availability)
                            if obj.id_technology_availability
                            else None
                        )
                        new_obj = (
                            db.session.get(
                                TechnologyAvailability, requested_technology_availability_id
                            )
                            if requested_technology_availability_id is not None
                            else None
                        )
                        old_name = prev_obj.name if prev_obj else "не указано"
                        new_name = new_obj.name if new_obj else "не указано"
                        changes.append(
                            format_field_change(
                                "id_technology_availability", old_name, new_name, "equipment_group"
                            )
                        )
                        obj.id_technology_availability = requested_technology_availability_id

                    if changes:
                        log_to_db(
                            user,
                            f"Обновлена группа оборудования во всех версиях: {requested_name}",
                            f"Версия БД id={target_version_id}; Изменения: {'; '.join(changes)}",
                            entity_type="equipment_group",
                            entity_id=obj.id,
                        )
                        all_updated.append(obj.id)

            db.session.flush()

        _commit_with_retry()
        return all_updated

    except IntegrityError as e:
        db.session.rollback()
        detail = getattr(e, "orig", None) or e
        log_to_db(
            user,
            "Ошибка сохранения типов групп оборудования во всех версиях БД",
            str(detail),
            entity_type="equipment_group",
            entity_id=last_entity_id,
        )
        raise ValueError(
            f"Ошибка сохранения во всех версиях: ограничение базы данных ({detail})."
        ) from e
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user,
            "Неизвестная ошибка при сохранении типов групп оборудования во всех версиях БД",
            str(e),
            entity_type="equipment_group",
            entity_id=last_entity_id,
        )
        raise ValueError(
            f"Произошла ошибка при обновлении данных во всех версиях: {e}"
        ) from e


@no_autoflush
def delete_equipment_group_service(ids, user):
    """Удаляет записи типов групп оборудования по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")

    log_to_db(
        user, 
        "Удаление типов групп оборудования", 
        f"Переданы ID для удаления: {ids}", 
        entity_type="equipment_group")

    successful_deletes = 0
    deleted_names = []
    deleted_ids = []
    blocked_ids = []
    blocked_names = []
    not_found = []
    invalid = []

    for ft_id in ids:
        try:
            equipment_group_id = int(ft_id)
        except (TypeError, ValueError):
            invalid.append(ft_id)
            log_to_db(
                user, 
                "Ошибка удаления типов групп оборудования", 
                f"Некорректный ID: {ft_id}", 
                entity_type="equipment_group",
                entity_id=ft_id)
            continue

        obj = _locked_get(EquipmentGroupType, equipment_group_id)
        if obj:
            has_machines = (
                db.session.query(Machine.id)
                .filter(Machine.id_equipment_group == equipment_group_id)
                .first()
                is not None
            )
            if has_machines:
                replacement = _find_replacement_equipment_group(obj, equipment_group_id)
                if replacement:
                    # Переназначаем ссылки на дубликат и удаляем
                    n_machines = (
                        db.session.query(Machine)
                        .filter(Machine.id_equipment_group == equipment_group_id)
                        .update({"id_equipment_group": replacement.id})
                    )
                    name = obj.name or f"ID={equipment_group_id}"
                    log_to_db(
                        user,
                        "Удаление с переназначением на дубликат",
                        f"{name} (id={equipment_group_id}): переназначено {n_machines} машин на id={replacement.id}",
                        entity_type="equipment_group",
                        entity_id=equipment_group_id)
                    db.session.delete(obj)
                    successful_deletes += 1
                    deleted_names.append(name)
                    deleted_ids.append(equipment_group_id)
                else:
                    name = obj.name or f"ID={equipment_group_id}"
                    blocked_ids.append(equipment_group_id)
                    blocked_names.append(name)
                    log_to_db(
                        user,
                        "Запрещено удаление типа группы оборудования",
                        f"Используется в агрегатах: {name}",
                        entity_type="equipment_group",
                        entity_id=equipment_group_id)
                continue

            name = obj.name or f"ID={equipment_group_id}"
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            deleted_ids.append(equipment_group_id)
            log_to_db(
                user, 
                "Удален тип группы оборудования", 
                f"{name}", 
                entity_type="equipment_group", 
                entity_id=equipment_group_id)
        else:
            not_found.append(equipment_group_id)
            log_to_db(
                user, 
                "Ошибка удаления типов групп оборудования", 
                f"Тип агрегата с ID={equipment_group_id} не найден.", 
                entity_type="equipment_group", 
                entity_id=equipment_group_id)

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        parts = [f"Удалено: {successful_deletes}"]
        if deleted_names:
            parts.append(f"Наименование: {deleted_names}")
        if blocked_names:
            parts.append(f"Не удалены (используются в группах): {blocked_names}")
        if not_found:
            parts.append(f"Не найдены ID: {not_found}")
        if invalid:
            parts.append(f"Некорректные ID: {invalid}")

        return {
            "deleted": successful_deletes,
            "deleted_names": deleted_names,
            "deleted_ids": deleted_ids,
            "blocked": blocked_ids,
            "blocked_names": blocked_names,
            "not_found": not_found,
            "invalid": invalid,
        }
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка удаления типов групп оборудования", 
            str(e), 
            entity_type="equipment_group",
            entity_id=equipment_group_id)
        raise ValueError(f"Ошибка при удалении данных.")


def export_equipment_group_service(
    user,
    equipment_group_filter=None,
    technology_type_filter=None,
    technology_availability_filter=None,
    sort_by="display_order",
    sort_dir="asc",):
    """ Экспортирует данные типов групп оборудования в Excel. """

    log_to_db(
        user, "Начата выгрузка таблицы типов групп оборудования. Параметры экспорта",
        (
            f"Фильтр по столбцу: Наименование типа группы оборудования = {equipment_group_filter}, "
            f"Тип технологии = {technology_type_filter}, "
            f"Доступность технологии = {technology_availability_filter}, "
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        )
        , entity_type="equipment_group"
    )

    # Базовый запрос
    query = equipment_group_query(
        equipment_group_filter=equipment_group_filter,
        technology_type_filter=technology_type_filter,
        technology_availability_filter=technology_availability_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(
        user, 
        "Получение данных завершено", 
        f"Найдено записей: {len(items)}", 
        entity_type="equipment_group")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "ID": o.id,
            "Порядок отображения": _dash(o.display_order),
            "Наименование": _dash(o.name),
            "Тип технологии": _dash(o.technology_type.name if o.technology_type else None),
            "Доступность технологии": _dash(o.technology_availability.name if o.technology_availability else None),
        })

    log_to_db(
        user, 
        "Подготовка данных для экспорта таблицы типов групп оборудования в Excel",
        f"Записей для экспорта: {len(data)}", 
        entity_type="equipment_group")

    df = pd.DataFrame(data)

    # Создание Excel и авто-ширина столбцов
    output = BytesIO()
    sheet_name = "Типы групп оборудования"
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]

        # Автоподбор ширины с аккуратным лимитом
        for i, col in enumerate(df.columns):
            max_len = max(len(str(col)), *(len(str(v)) for v in df[col].values)) if not df.empty else len(str(col))
            ws.set_column(i, i, min(max_len + 2, 60))

    output.seek(0)
    log_to_db(
        user, 
        "Экспорт таблицы типов групп оборудования в Excel завершен", 
        f"Экспортировано записей: {len(data)}", 
        entity_type="equipment_group")
    return output


def export_equipment_group_mappings_service(
        user,
        equipment_group_filter=None,
        sort_by="id",
        sort_dir="asc"):
    """Экспортирует сопоставления типов групп оборудования с БД Топливо в Excel (по принципу gen_company)."""
    log_to_db(
        user,
        "Начата выгрузка сопоставлений типов групп оборудования (Топливо)",
        entity_type="equipment_group",
    )
    log_to_db(
        user,
        "Параметры экспорта",
        (
            f"Фильтр по типам групп оборудования = {equipment_group_filter}, "
            f"Сортировка = {sort_by}, направление = {sort_dir}."
        ),
        entity_type="equipment_group",
    )

    query = equipment_group_query(
        equipment_group_filter=equipment_group_filter,
        technology_type_filter=None,
        technology_availability_filter=None,
        sort_by=sort_by if sort_by in {"id", "name", "display_order"} else "id",
        sort_dir=sort_dir,
    )
    items = query.all()

    mapping_sort_fields = {
        "code", "name_topl", "type_", "tm", "n1", "n2", "p1", "p2", "gruppa_oborud"
    }
    mappings = EquipmentGroupExternalMapping.query.order_by(
        EquipmentGroupExternalMapping.id.desc()
    ).all()
    mapping_by_uuid = {}
    unmatched_mappings = []
    for mapping in mappings:
        if mapping.equipment_group_ref_uuid:
            if mapping.equipment_group_ref_uuid not in mapping_by_uuid:
                mapping_by_uuid[mapping.equipment_group_ref_uuid] = mapping
        else:
            unmatched_mappings.append(mapping)

    rows = [
        {"eg": eg, "mapping": mapping_by_uuid.get(eg.ref_uuid)}
        for eg in items
    ]

    if sort_by in mapping_sort_fields:
        rows.extend([{"eg": None, "mapping": m} for m in unmatched_mappings])

        def _sort_key(row):
            mapping = row["mapping"]
            value = getattr(mapping, sort_by, None) if mapping else None
            if value is None or str(value).strip() == "":
                return (2, "")
            text = str(value).strip()
            if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
                return (0, int(text))
            return (1, text.lower())

        rows.sort(key=_sort_key, reverse=(sort_dir == "desc"))

    data = []
    for row in rows:
        mapping = row["mapping"]
        eg = row["eg"]
        data.append({
            "Код (code)": _dash(mapping.code if mapping else None),
            "Название (Топливо) (name_topl)": _dash(mapping.name_topl if mapping else None),
            "Тип (type_)": _dash(mapping.type_ if mapping else None),
            "Типы турбин (tm)": _dash(mapping.tm if mapping else None),
            "Мощность блока (вар. 1) (n1)": _dash(mapping.n1 if mapping else None),
            "Мощность блока (вар. 2) (n2)": _dash(mapping.n2 if mapping else None),
            "Давление пара (вар. 1) (p1)": _dash(mapping.p1 if mapping else None),
            "Давление пара (вар. 2) (p2)": _dash(mapping.p2 if mapping else None),
            "Группа оборудования (gruppa_oborud)": _dash(mapping.gruppa_oborud if mapping else None),
            "UUID (ref_uuid)": _dash(eg.ref_uuid if eg else None),
            "ID (id)": _dash(eg.id if eg else None),
            "Наименование (name)": _dash(eg.name if eg else None),
        })

    log_to_db(
        user,
        "Подготовка данных для экспорта сопоставлений типов групп оборудования",
        f"Записей для экспорта: {len(data)}",
        entity_type="equipment_group",
    )

    df = pd.DataFrame(data)
    output = BytesIO()
    sheet_name = "EquipmentGroupType"
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)

    output.seek(0)
    log_to_db(
        user,
        "Экспорт сопоставлений типов групп оборудования завершен",
        f"Экспортировано записей: {len(data)}",
        entity_type="equipment_group",
    )
    return output