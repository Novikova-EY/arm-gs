"""Сервисный модуль: Синхронные зоны."""

from app.extensions import db
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 
from config import SCHEMA_REFDATA

# Модели
from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea

from app.refdata.models.territories.regional_district_model import RegionalDistrict

# Сервисы
from app.common.services.get_services.energy_systems.synchronous_area_get_services import (
    get_synchronous_area_name,
)
from app.common.services.get_services.territories.regional_district_get_services import (
    get_regional_district_name,
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


def synchronous_area_query(
    synchronous_area_filter=None,
    sort_by="display_order",
    sort_dir="asc"):
    """ Базовый запрос для выборки частей энергосистемы России с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id", "name", "name_full", "display_order", "number"}
    sort_by = sort_by if sort_by in allowed_sort_by else "display_order"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Базовый запрос
    query = SynchronousArea.query
    query = apply_version_filter(query, SynchronousArea)

    # Фильтрация
    if synchronous_area_filter:
        query = query.filter(
            or_(
                SynchronousArea.name.ilike(f"%{synchronous_area_filter}%"),
                SynchronousArea.name_full.ilike(f"%{synchronous_area_filter}%"),
            )
        )

    # Сортировка
    if sort_by in {"name", "name_full"}:
        sort_field = SynchronousArea.name_full if sort_by == "name_full" else SynchronousArea.name
        query = query.order_by(sort_field.desc() if sort_dir == "desc" else sort_field.asc())
    elif sort_by == "display_order":
        # Сортируем по порядку отображения, значения NULL в конце
        if sort_dir == "desc":
            query = query.order_by(
                (SynchronousArea.display_order.is_(None)),
                SynchronousArea.display_order.desc(),
            )
        else:
            query = query.order_by(
                (SynchronousArea.display_order.is_(None)),
                SynchronousArea.display_order.asc(),
            )
    else:
        # sort_by == "id" или "number"
        query = query.order_by(SynchronousArea.id.desc() if sort_dir == "desc" else SynchronousArea.id.asc())

    # Исключаем запись "Не указано" (id=0)
    query = query.filter(SynchronousArea.id.isnot(None), SynchronousArea.id > 0)

    return query


@no_autoflush
def get_synchronous_area_list(
    page, 
    per_page, 
    synchronous_area_filter=None, 
    sort_by="display_order", 
    sort_dir="asc"):
    """ Получает список синхронных зон с пагинацией, фильтрацией и сортировкой."""
    
    # Базовый запрос
    query = synchronous_area_query(
        synchronous_area_filter=synchronous_area_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_synchronous_area_service(data, user):
    """Обновление данных по синхронным зонам."""

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []

    log_to_db(
        user, 
        "Получены данные для обновления списка синхронных зон", 
        f"{data}",
        entity_type="synchronous_area")

    with db.session.no_autoflush:
        for record in data:
            synchronous_area_id = record.get("synchronous_area_id")
            number = record.get("number")
            name = record.get("name")
            name_full = (record.get("name_full") or "").strip() or None
            display_order = record.get("display_order")

            # Проверки на валидность данных
            if not name:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись: {record}",
                    entity_type="synchronous_area",
                    entity_id=synchronous_area_id)
                raise ValueError(f"Каждая запись должна содержать 'name'. Данные: {record}")

            obj = db.session.get(SynchronousArea, synchronous_area_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{synchronous_area_id}» не найдена.", 
                    entity_type="synchronous_area", 
                    entity_id=synchronous_area_id)
                raise ValueError(f"Запись с ID «{synchronous_area_id}» не найдена.")
            
            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (apply_version_filter(SynchronousArea.query, SynchronousArea)
                     .filter(SynchronousArea.name == name,
                             SynchronousArea.id != synchronous_area_id))
                if q.first():
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")

            # Проверка уникальности number
            if number != (obj.number or ""):
                q = (apply_version_filter(SynchronousArea.query, SynchronousArea)
                     .filter(SynchronousArea.number == number,
                             SynchronousArea.id != synchronous_area_id))
                if q.first():
                    raise ValueError(f"Запись с номером «{number}» уже существует.")

            # Проверка уникальности name_full
            if name_full and name_full != (obj.name_full or ""):
                q = (apply_version_filter(SynchronousArea.query, SynchronousArea)
                     .filter(SynchronousArea.name_full == name_full,
                             SynchronousArea.id != synchronous_area_id))
                if q.first():
                    raise ValueError(f"Запись с полным наименованием «{name_full}» уже существует.")

            # Проверка уникальности display_order
            if display_order is not None and display_order != obj.display_order:
                q_display = (
                    apply_version_filter(SynchronousArea.query, SynchronousArea)
                    .filter(
                        SynchronousArea.display_order == display_order,
                        SynchronousArea.id != synchronous_area_id,
                    )
                )
                if q_display.first():
                    raise ValueError(
                        f"Запись с порядком отображения «{display_order}» уже существует."
                    )

            changes = []
                
            if name != (obj.name or ""):
                changes.append(format_field_change("name", obj.name or "не указано", name, "synchronous_area"))
                obj.name = name

            if name_full != (obj.name_full or None):
                changes.append(format_field_change(
                    "name_full",
                    obj.name_full or "не указано",
                    name_full or "не указано",
                    "synchronous_area",
                ))
                obj.name_full = name_full

            if number != (obj.number or ""):
                old_val = obj.number if obj.number is not None else "не указано"
                new_val = number if number is not None else "не указано"
                changes.append(f"Номер: {old_val} → {new_val}")
                obj.number = number

            if display_order != obj.display_order:
                old_val = obj.display_order if obj.display_order is not None else "не указано"
                new_val = display_order if display_order is not None else "не указано"
                changes.append(f"Порядок отображения: {old_val} → {new_val}")
                obj.display_order = display_order

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    f"Обновлена синхронная зона: {name}", 
                    f"Изменения: {'; '.join(changes)}",
                    entity_type="synchronous_area", 
                    entity_id=synchronous_area_id)
                updated_ids.append(synchronous_area_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по синхронным зонам", 
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})",
                entity_type="synchronous_area")
        else:
            log_to_db(
                user, 
                "Изменений по синхронным зонам не обнаружено", 
                "", 
                entity_type="synchronous_area")
            
        return updated_ids

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения синхронных зон (уникальность/целостность)", 
            str(e), 
            entity_type="synchronous_area")  
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Неизвестная ошибка при сохранении синхронных зон", 
            str(e), 
            entity_type="synchronous_area")
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")

        
@no_autoflush
def add_synchronous_area_service(data, user):
    """ Создание новой записи: синхронная зона """

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    def _do_insert():
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                number = (record.get("number") or "").strip()
                name = (record.get("name") or "").strip()
                name_full = (record.get("name_full") or "").strip() or name or None
                display_order = record.get("display_order")

                # Проверка на наличие необходимых данных
                if not name:
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись: {record}",
                        entity_type="synchronous_area")
                    raise ValueError(f"Каждая запись должна содержать 'name'.")

                # Проверяем уникальность name при создании
                dup = (apply_version_filter(SynchronousArea.query, SynchronousArea)
                        .filter(SynchronousArea.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
                # Проверяем уникальность number при создании
                if number:
                    dup_number = (apply_version_filter(SynchronousArea.query, SynchronousArea)
                            .filter(SynchronousArea.number == number)
                            .with_for_update().first())
                    if dup_number:
                        raise ValueError(f"Запись с номером «{number}» уже существует.")

                # Проверяем уникальность name_full при создании
                if name_full:
                    dup_full = (apply_version_filter(SynchronousArea.query, SynchronousArea)
                            .filter(SynchronousArea.name_full == name_full)
                            .with_for_update().first())
                    if dup_full:
                        raise ValueError(f"Запись с полным наименованием «{name_full}» уже существует.")

                # Проверяем уникальность display_order при создании
                if display_order is not None:
                    dup_display = (
                        apply_version_filter(SynchronousArea.query, SynchronousArea)
                        .filter(SynchronousArea.display_order == display_order)
                        .with_for_update()
                        .first()
                    )
                    if dup_display:
                        raise ValueError(
                            f"Запись с порядком отображения «{display_order}» уже существует."
                        )

                # Создаем новую запись
                obj = SynchronousArea(
                    name=name,
                    name_full=name_full,
                    number=number or None,
                    display_order=display_order,
                )
                set_db_version_on_create(obj)
                db.session.add(obj)
                db.session.flush()  # получить id без полного коммита

                log_to_db(
                    user, 
                    "Создана синхронная зона",
                    (
                        f"Номер: {_dash(number)}; "
                        f"Наименование: {name}; "
                        f"Полное наименование: {_dash(name_full)}; "
                    ),
                    entity_type="synchronous_area", 
                    entity_id=obj.id)

    try:
        _do_insert()
        _commit_with_retry()
        return None

    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "synchronous_areas")
        _do_insert()
        _commit_with_retry()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения новой синхронной зоны", 
            str(e), 
            entity_type="synchronous_area")
        raise ValueError(f"Ошибка сохранения новой синхронной зоны: {e}")
    

@no_autoflush
def delete_synchronous_area_service(ids, user):
    """Удаляет записи синхронных зон по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")

    log_to_db(
        user, 
        "Удаление списка синхронных зон", 
        f"Переданы ID для удаления: {ids}", 
        entity_type="synchronous_area")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for sz_id in ids:
        try:
            synchronous_area_id = _to_int_or_none(sz_id, keep_zero=False)
        except (TypeError, ValueError):
            invalid.append(sz_id)
            log_to_db(
                user, 
                "Ошибка удаления синхронной зоны", 
                f"Некорректный ID: {sz_id}", 
                entity_type="synchronous_area",
                entity_id=sz_id)
            continue

        obj = _locked_get(SynchronousArea, synchronous_area_id)
        if obj:
            db.session.delete(obj)
            deleted_names.append(get_synchronous_area_name(synchronous_area_id))
            successful_deletes += 1
            log_to_db(
                user, 
                "Удалена синхронная зона", 
                f"{get_synchronous_area_name(synchronous_area_id)}",
                entity_type="synchronous_area", 
                entity_id=synchronous_area_id)
        else:
            not_found.append(synchronous_area_id)
            log_to_db(
                user, 
                "Ошибка удаления синхронной зоны", 
                f"Синхронная зона с ID={synchronous_area_id} не найдена.",
                entity_type="synchronous_area", 
                entity_id=synchronous_area_id)
    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        parts = [f"Удалено: {successful_deletes}"]
        if deleted_names:
            parts.append(f"Наименование: {deleted_names}")
        if not_found:
            parts.append(f"Не найдены ID: {not_found}")
        if invalid:
            parts.append(f"Некорректные ID: {invalid}")

        return {
            "deleted": successful_deletes,
            "deleted_names": deleted_names,
            "not_found": not_found,
            "invalid": invalid,
        }
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка удаления синхронных зон", 
            str(e), 
            entity_type="synchronous_area",
            entity_id=synchronous_area_id)
        raise ValueError(f"Ошибка при удалении данных.")
    

def export_synchronous_area_service(
        user, 
        sort_by="display_order", 
        sort_dir="asc",
        synchronous_area_filter=None, 
        ):
    """ Экспортирует данные списка синхронных зон в Excel. """

    log_to_db(
        user, 
        "Начата выгрузка таблицы синхронных зон. Параметры экспорта", 
        (
            f"Фильтр по столбцу: Наименование синхронной зоны = {synchronous_area_filter},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        ),
        entity_type="synchronous_area")
    
    # Базовый запрос
    query = synchronous_area_query(
        synchronous_area_filter=synchronous_area_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(
        user, 
        "Получение данных завершено", 
        f"Найдено записей: {len(items)}", 
        entity_type="synchronous_area")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx + 1,
            "Порядок отображения": o.display_order if o.display_order is not None else "",
            "Наименование синхронной зоны": _dash(o.name),
            "Полное наименование синхронной зоны": _dash(o.name_full),
        })

    log_to_db(
        user, 
        "Подготовка данных для экспорта таблицы синхронных зон в Excel", 
        f"Записей для экспорта: {len(data)}",
        entity_type="synchronous_area")

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)
    
    # Создание Excel-файла
    output = BytesIO()
    sheet_name = "Синхронные зоны"
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]

        # Автоподбор ширины с аккуратным лимитом
        for i, col in enumerate(df.columns):
            max_len = max(len(str(col)), *(len(str(v)) for v in df[col].values)) if not df.empty else len(str(col))
            ws.set_column(i, i, min(max_len + 2, 60))

    # Возврат файла в ответе
    output.seek(0)
    log_to_db(
        user, 
        "Экспорт таблицы синхронных зон в Excel завершен", 
        f"Экспортировано записей: {len(data)}",
        entity_type="synchronous_area")

    return output

# === all_versions_synchronous_area start ===
@no_autoflush
def add_synchronous_area_all_versions_service(data, user):
    from app.refdata.services.refdata_all_versions_common import add_all_versions_records, update_all_versions_records, fk_id_for_version

    def normalize_record(record):
        display_order = record.get("display_order")
        number = (record.get("number") or "").strip() or None
        name = (record.get("name") or "").strip()
        name_full = (record.get("name_full") or "").strip() or name or None
        if not name:
            raise ValueError("Каждая запись должна содержать 'name'.")
        return {
            "name": name,
            "name_full": name_full,
            "number": number,
            "display_order": display_order,
        }

    def resolve_for_version(clean, version_id):
        return {
            "name": clean["name"],
            "name_full": clean["name_full"],
            "number": clean["number"],
            "display_order": clean["display_order"],
        }

    return add_all_versions_records(
        data=data,
        user=user,
        model_cls=SynchronousArea,
        entity_type="synchronous_area",
        normalize_record=normalize_record,
        resolve_for_version=resolve_for_version,
        unique_fields=['name', 'name_full', 'number', 'display_order']
    )


@no_autoflush
def update_synchronous_area_all_versions_service(data, user):
    from app.refdata.services.refdata_all_versions_common import add_all_versions_records, update_all_versions_records, fk_id_for_version

    def normalize_record(record):
        synchronous_area_id = record.get("synchronous_area_id")
        display_order = record.get("display_order")
        number = (record.get("number") or "").strip() or None
        name = (record.get("name") or "").strip()
        name_full = (record.get("name_full") or "").strip() or None
        if not name:
            raise ValueError("Поле 'name' обязательно для заполнения.")
        return {
            "synchronous_area_id": synchronous_area_id,
            "name": name,
            "name_full": name_full,
            "number": number,
            "display_order": display_order,
        }

    def resolve_for_version(clean, version_id):
        return {
            "name": clean["name"],
            "name_full": clean["name_full"],
            "number": clean["number"],
            "display_order": clean["display_order"],
        }

    return update_all_versions_records(
        data=data,
        user=user,
        model_cls=SynchronousArea,
        entity_type="synchronous_area",
        pk_field="synchronous_area_id",
        normalize_record=normalize_record,
        resolve_for_version=resolve_for_version,
        tracked_fields=['name', 'name_full', 'number', 'display_order'],
        unique_fields=['name', 'name_full', 'number', 'display_order'],
        temp_fields=['name', 'name_full', 'number'],
        clear_fields=['display_order']
    )
# === all_versions_synchronous_area end ===
