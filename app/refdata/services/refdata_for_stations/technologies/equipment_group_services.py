"""Сервисный модуль: Типы групп оборудования."""

from app.extensions import db
from sqlalchemy import func as sa_func, text
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 
from config import SCHEMA_REFDATA
        
# Модели
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroup
from app.refdata.models.refdata_for_stations.technologies.technology_type_model import TechnologyType
from app.refdata.models.refdata_for_stations.technologies.technology_availability_model import TechnologyAvailability
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet

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
from app.common.services.database_version_filter import (
    apply_version_filter,
    set_db_version_on_create,
)

# Логирование
from app.logs.services.logging_service import log_to_db
from app.logs.services.field_names_ru import format_field_change, get_field_name_ru


def _equipment_group_dup_query(name, technology_type_id, exclude_id=None):
    """Возвращает запрос для проверки дубликатов по паре (name, technology_type)."""
    query = apply_version_filter(EquipmentGroup.query, EquipmentGroup).filter(EquipmentGroup.name == name)
    if technology_type_id is None:
        query = query.filter(EquipmentGroup.id_technology_type.is_(None))
    else:
        query = query.filter(EquipmentGroup.id_technology_type == technology_type_id)
    if exclude_id is not None:
        query = query.filter(EquipmentGroup.id != exclude_id)
    return query


def equipment_group_query(
        equipment_group_filter=None, 
        technology_type_filter=None, 
        technology_availability_filter=None, 
        sort_by="id", 
        sort_dir="asc"):
    """ Базовый запрос для выборки типов групп оборудования с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id", "name", "technology_type", "technology_availability", "display_order", "number"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Безопасная конвертация ID-фильтров
    technology_type_id = _to_int_or_none(technology_type_filter)
    technology_availability_id = _to_int_or_none(technology_availability_filter)

    # Базовый запрос
    query = EquipmentGroup.query.filter(EquipmentGroup.id.isnot(None), EquipmentGroup.id > 0)
    query = apply_version_filter(query, EquipmentGroup)

    # Загрузка связанных данных
    query = query.options(
        joinedload(EquipmentGroup.technology_type),
        joinedload(EquipmentGroup.technology_availability)
    )

    # Отслеживание примененных JOIN'ов для избежания дублирования
    joined_tech_type = False
    joined_tech_avail = False

    # Фильтрация
    if equipment_group_filter:
        query = query.filter(EquipmentGroup.name.ilike(f"%{equipment_group_filter}%"))

    # Фильтр по типу технологии:
    # - если передан ID (из выпадающего списка) — фильтруем по EquipmentGroup.id_technology_type
    # - если передана строка (ручной ввод) — фильтруем по имени типа технологии
    if technology_type_id is not None:
        query = query.filter(EquipmentGroup.id_technology_type == technology_type_id)
    elif technology_type_filter:
        query = query.join(
            TechnologyType,
            EquipmentGroup.id_technology_type == TechnologyType.id,
            isouter=True,
        )
        query = query.filter(TechnologyType.name.ilike(f"%{technology_type_filter}%"))
        joined_tech_type = True

    # Фильтр по доступности технологии (аналогично типу технологии)
    if technology_availability_id is not None:
        query = query.filter(EquipmentGroup.id_technology_availability == technology_availability_id)
    elif technology_availability_filter:
        query = query.join(
            TechnologyAvailability,
            EquipmentGroup.id_technology_availability == TechnologyAvailability.id,
            isouter=True,
        )
        query = query.filter(TechnologyAvailability.name.ilike(f"%{technology_availability_filter}%"))
        joined_tech_avail = True

    # Сортировка
    if sort_by == "name":
        sort_col = EquipmentGroup.name
    elif sort_by == "technology_type":
        if not joined_tech_type:
            query = query.join(TechnologyType, EquipmentGroup.id_technology_type == TechnologyType.id, isouter=True)
        sort_col = TechnologyType.name
    elif sort_by == "technology_availability":
        if not joined_tech_avail:
            query = query.join(TechnologyAvailability, EquipmentGroup.id_technology_availability == TechnologyAvailability.id, isouter=True)
        sort_col = TechnologyAvailability.name
    elif sort_by == "display_order":
        if sort_dir == "desc":
            query = query.order_by(
                (EquipmentGroup.display_order.is_(None)),
                EquipmentGroup.display_order.desc()
            )
        else:
            query = query.order_by(
                (EquipmentGroup.display_order.is_(None)),
                EquipmentGroup.display_order.asc()
            )
    else:
        sort_col = EquipmentGroup.id

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
    sort_by="id", 
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
    
    log_to_db(
        user, 
        "Получены данные для обновления списка типов групп оборудования", 
        f"{data}", 
        entity_type="equipment_group")
    
    # Проверки на валидность данных
    with db.session.no_autoflush:
        for record in data:
            equipment_group_id = record.get("equipment_group_id")
            display_order = record.get("display_order")
            name = (record.get("name") or "").strip()
            new_technology_type_id = _to_int_or_none(record.get("technology_type_id"), keep_zero=False)

            # Проверка наличия наименования
            if not name:
                raise ValueError(f"Поле 'name' обязательно для заполнения.")

            obj = db.session.get(EquipmentGroup, equipment_group_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{equipment_group_id}» не найдена.", 
                    entity_type="equipment_group", 
                    entity_id=equipment_group_id)
                raise ValueError(f"Запись с ID «{equipment_group_id}» не найдена.")

            # Проверка уникальности пары (name, technology_type)
            if name != (obj.name or "") or new_technology_type_id != obj.id_technology_type:
                dup = (_equipment_group_dup_query(name, new_technology_type_id, exclude_id=equipment_group_id)
                       .with_for_update()
                       .first())
                if dup:
                    tech_name = get_technology_type_name(new_technology_type_id) or "не указано"
                    raise ValueError(
                        f"Запись с наименованием «{name}» и типом технологии «{tech_name}» уже существует."
                    )

            # Проверка уникальности display_order
            if display_order != obj.display_order:
                if display_order is not None:
                    q_display = (apply_version_filter(EquipmentGroup.query, EquipmentGroup)
                                .filter(EquipmentGroup.display_order == display_order,
                                        EquipmentGroup.id != equipment_group_id))
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

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по типам групп оборудования", 
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})", 
                entity_type="equipment_group",
                entity_id=equipment_group_id)
        else:
            log_to_db(
                user, 
                "Изменений по типам групп оборудования не обнаружено", 
                "", 
                entity_type="equipment_group")
            
        return updated_ids
    
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения типов групп оборудования (уникальность/целостность)", 
            str(e), 
            entity_type="equipment_group",
            entity_id=equipment_group_id)
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Неизвестная ошибка при сохранении типов групп оборудования", 
            str(e), 
            entity_type="equipment_group",
            entity_id=equipment_group_id)
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


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
                    dup_display = (apply_version_filter(EquipmentGroup.query, EquipmentGroup)
                            .filter(EquipmentGroup.display_order == display_order)
                            .with_for_update().first())
                    if dup_display:
                        raise ValueError(f"Запись с порядком отображения «{display_order}» уже существует.")

                obj = EquipmentGroup(
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

        obj = _locked_get(EquipmentGroup, equipment_group_id)
        if obj:
            has_group_sets = (
                db.session.query(EquipmentGroupSet.id)
                .filter(EquipmentGroupSet.id_equipment_group == equipment_group_id)
                .first()
                is not None
            )
            if has_group_sets:
                name = obj.name or f"ID={equipment_group_id}"
                blocked_ids.append(equipment_group_id)
                blocked_names.append(name)
                log_to_db(
                    user,
                    "Запрещено удаление типа группы оборудования",
                    f"Используется в сборных группах оборудования: {name}",
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
    sort_by="id",
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