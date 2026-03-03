"""Сервисный модуль: Объединенные энергосистемы."""

from app.extensions import db
from sqlalchemy import or_, case, cast, Integer
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO
from types import SimpleNamespace
from config import SCHEMA_REFDATA

# Модели
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.fuel.models.external_mapping.fue_em_union_energy_system_model import (
    UnionEnergySystemExternalMapping,
)
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType

# Сервисы
from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
    get_energy_system_type_name,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_name,
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

# Логирование
from app.logs.services.logging_service import log_to_db
from app.logs.services.field_names_ru import format_field_change, get_field_name_ru

# Фильтрация по версиям
from app.common.services.database_version_filter import apply_version_filter, set_db_version_on_create


def union_energy_system_query(
    union_energy_system_filter=None,
    energy_system_type_filter=None,
    sort_by="display_order",
    sort_dir="asc"):
    """ Базовый запрос для выборки списка ОЭС с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {
        "id",
        "name",
        "name_full",
        "energy_system_type",
        "display_order",
        "number",
        "ref_uuid",
        "external_id",
        "external_name",
        "external_nameoes",
        "external_abbr",
    }
    sort_by = sort_by if sort_by in allowed_sort_by else "display_order"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Безопасная конвертация ID-фильтров
    energy_system_type_id = _to_int_or_none(energy_system_type_filter)

    # Базовый запрос
    query = (
        UnionEnergySystem.query
        .options(
            joinedload(UnionEnergySystem.energy_system_type)
        )
        .join(EnergySystemType)
    )
    
    # Применяем фильтрацию по версии БД
    query = apply_version_filter(query, UnionEnergySystem)

    # Фильтрация по названию ОЭС
    if union_energy_system_filter:
        query = query.filter(
            or_(
                UnionEnergySystem.name.ilike(f"%{union_energy_system_filter}%"),
                UnionEnergySystem.name_full.ilike(f"%{union_energy_system_filter}%"),
            )
        )

    # Фильтрация по типу энергосистемы
    if energy_system_type_filter:
        query = query.filter(EnergySystemType.id == energy_system_type_id)

    if sort_by in {"external_id", "external_name", "external_nameoes", "external_abbr"}:
        query = query.outerjoin(
            UnionEnergySystemExternalMapping,
            UnionEnergySystem.ref_uuid == UnionEnergySystemExternalMapping.union_energy_system_ref_uuid,
        )

    # Сортировка
    if sort_by in ["name", "name_full"]:
        sort_field = getattr(UnionEnergySystem, sort_by)
        query = query.order_by(
            sort_field.desc() if sort_dir == "desc" else sort_field.asc()
        )

    elif sort_by == "ref_uuid":
        query = query.order_by(
            UnionEnergySystem.ref_uuid.desc()
            if sort_dir == "desc"
            else UnionEnergySystem.ref_uuid.asc()
        )

    elif sort_by == "external_id":
        sort_field = UnionEnergySystemExternalMapping.external_id
        numeric_sort = case(
            (sort_field.op("~")("^[0-9]+$"), cast(sort_field, Integer)),
            else_=None,
        )
        query = query.order_by(
            numeric_sort.desc().nullslast()
            if sort_dir == "desc"
            else numeric_sort.asc().nullslast(),
            sort_field.asc().nullslast(),
        )

    elif sort_by == "external_name":
        sort_field = UnionEnergySystemExternalMapping.external_name
        query = query.order_by(
            sort_field.desc().nullslast()
            if sort_dir == "desc"
            else sort_field.asc().nullslast()
        )

    elif sort_by == "external_nameoes":
        sort_field = UnionEnergySystemExternalMapping.external_nameoes
        query = query.order_by(
            sort_field.desc().nullslast()
            if sort_dir == "desc"
            else sort_field.asc().nullslast()
        )

    elif sort_by == "external_abbr":
        sort_field = UnionEnergySystemExternalMapping.external_abbr
        query = query.order_by(
            sort_field.desc().nullslast()
            if sort_dir == "desc"
            else sort_field.asc().nullslast()
        )

    elif sort_by == "energy_system_type":
        query = query.order_by(
            EnergySystemType.name.desc() if sort_dir == "desc" else EnergySystemType.name.asc()
        )

    elif sort_by == "display_order":
        if sort_dir == "desc":
            query = query.order_by(
                (UnionEnergySystem.display_order.is_(None)),
                UnionEnergySystem.display_order.desc()
            )
        else:
            query = query.order_by(
                (UnionEnergySystem.display_order.is_(None)),
                UnionEnergySystem.display_order.asc()
            )

    else:
        query = query.order_by(
            UnionEnergySystem.id.desc() if sort_dir == "desc" else UnionEnergySystem.id.asc()
        )

    # Исключаем запись "Не указано" (id=0)
    query = query.filter(UnionEnergySystem.id.isnot(None), UnionEnergySystem.id > 0)

    return query


@no_autoflush
def get_union_energy_system_list(
    page, 
    per_page, 
    union_energy_system_filter=None, 
    energy_system_type_filter=None, 
    sort_by="display_order", 
    sort_dir="asc"):
    """ Получает список ОЭС с пагинацией, фильтрацией и сортировкой. """
    
    # Базовый запрос
    query = union_energy_system_query(
        union_energy_system_filter=union_energy_system_filter,
        energy_system_type_filter=energy_system_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_union_energy_system_service(data, user):
    """Обновление данных по ОЭС."""

    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []

    log_to_db(
        user, 
        "Получены данные для обновления списка ОЭС", 
        f"{data}", 
        entity_type="union_energy_system")

    with db.session.no_autoflush:
        for record in data:
            union_energy_system_id = record.get("union_energy_system_id")
            display_order = record.get("display_order")
            name = record.get("name")
            name_full = record.get("name_full")
            energy_system_type_id = _to_int_or_none(record.get("energy_system_type_id"), keep_zero=False)

            # Проверки на валидность данных
            if not name or not name_full or not energy_system_type_id:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись: {record}", 
                    entity_type="union_energy_system",
                    entity_id=union_energy_system_id)
                raise ValueError("Каждая запись должна содержать 'name', 'name_full' и 'energy_system_type_id'. Данные: {record}")

            obj = db.session.get(UnionEnergySystem, union_energy_system_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{union_energy_system_id}» не найдена.", 
                    entity_type="union_energy_system", 
                    entity_id=union_energy_system_id)
                raise ValueError(f"Запись с ID «{union_energy_system_id}» не найдена.")
            
            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (apply_version_filter(UnionEnergySystem.query, UnionEnergySystem)
                     .filter(UnionEnergySystem.name == name,
                             UnionEnergySystem.id != union_energy_system_id))
                if q.first():
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
            # Проверка уникальности name_full
            if name_full != (obj.name_full or ""):
                q_full = (apply_version_filter(UnionEnergySystem.query, UnionEnergySystem)
                     .filter(UnionEnergySystem.name_full == name_full,
                             UnionEnergySystem.id != union_energy_system_id))
                if q_full.first():
                    raise ValueError(f"Запись с полным наименованием «{name_full}» уже существует.")

            # Проверка уникальности display_order
            if display_order != obj.display_order:
                if display_order is not None:
                    q_display = (apply_version_filter(UnionEnergySystem.query, UnionEnergySystem)
                                .filter(UnionEnergySystem.display_order == display_order,
                                        UnionEnergySystem.id != union_energy_system_id))
                    if q_display.first():
                        raise ValueError(f"Запись с порядком отображения «{display_order}» уже существует.")


            changes = []

            if name != (obj.name or ""):
                changes.append(format_field_change("name", obj.name or "не указано", name, "union_energy_system"))
                obj.name = name

            if name_full != (obj.name_full or None):
                old_val = obj.name_full or "не указано"
                new_val = name_full or "не указано"
                changes.append(f"Полное наименование: {old_val} → {new_val}")
                obj.name_full = name_full

            if display_order != obj.display_order:
                old_val = obj.display_order if obj.display_order is not None else "не указано"
                new_val = display_order if display_order is not None else "не указано"
                changes.append(f"Порядок отображения: {old_val} → {new_val}")
                obj.display_order = display_order

            # Проверка наличия части энергосистемы
            if "energy_system_type_id" in record:
                new_val = _to_int_or_none(record.get("energy_system_type_id"), keep_zero=False)
                if new_val != obj.id_energy_system_type:
                    new_obj = db.session.get(EnergySystemType, new_val) if new_val is not None else None
                    if new_val is not None and not new_obj:
                        raise ValueError(f"Часть энергосистемы России с id={new_val} не найдена.")
                    
                    prev_obj = db.session.get(EnergySystemType, obj.id_energy_system_type) if obj.id_energy_system_type else None
                    old_name = prev_obj.name if prev_obj else "не указано"
                    new_name = new_obj.name if new_obj else "не указано"
                    changes.append(format_field_change("id_energy_system_type", old_name, new_name, "union_energy_system"))
                    obj.id_energy_system_type = new_val

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    f"Обновлена ОЭС: {name}", 
                    f"Изменения: {'; '.join(changes)}", 
                    entity_type="union_energy_system", 
                    entity_id=union_energy_system_id)
                updated_ids.append(union_energy_system_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по ОЭС", 
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})", 
                entity_type="union_energy_system")
        else:
            log_to_db(
                user, 
                "Изменений по ОЭС не обнаружено", 
                "", 
                entity_type="union_energy_system")
            
        return updated_ids

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения ОЭС (уникальность/целостность)", 
            str(e), 
            entity_type="union_energy_system")
        raise ValueError("Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Неизвестная ошибка при сохранении ОЭС", 
            str(e), 
            entity_type="union_energy_system")
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_union_energy_system_service(data, user):
    """ Создание новой записи: ОЭС """

    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    def _do_insert():
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                display_order = record.get("display_order")
                name = (record.get("name") or "").strip()
                name_full = (record.get("name_full") or "").strip()
                energy_system_type_id = _to_int_or_none(record.get("energy_system_type_id"), keep_zero=False)

                # Проверка на наличие необходимых данных
                if not name or not name_full or not energy_system_type_id:
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись: {record}",
                        entity_type="union_energy_system")
                    raise ValueError("Каждая запись должна содержать 'name', 'name_full' и 'energy_system_type_id'.")

                # Проверяем существование части энергосистемы России
                est_obj = db.session.get(EnergySystemType, energy_system_type_id)
                if not est_obj:
                    raise ValueError(f"Часть энергосистемы России с id={energy_system_type_id} не найдена.")

                # Проверяем уникальность name при создании
                dup = (apply_version_filter(UnionEnergySystem.query, UnionEnergySystem)
                        .filter(UnionEnergySystem.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
                # Проверяем уникальность name_full при создании
                dup_full = (apply_version_filter(UnionEnergySystem.query, UnionEnergySystem)
                        .filter(UnionEnergySystem.name_full == name_full)
                        .with_for_update().first())
                if dup_full:
                    raise ValueError(f"Запись с полным наименованием «{name_full}» уже существует.")

                # Проверяем уникальность display_order при создании
                if display_order is not None:
                    dup_display = (apply_version_filter(UnionEnergySystem.query, UnionEnergySystem)
                            .filter(UnionEnergySystem.display_order == display_order)
                            .with_for_update().first())
                    if dup_display:
                        raise ValueError(f"Запись с порядком отображения «{display_order}» уже существует.")

                # Создаем новую запись
                obj = UnionEnergySystem(
                    display_order=display_order,
                    name=name,
                    name_full=name_full or None,
                    id_energy_system_type=energy_system_type_id,
                )
                set_db_version_on_create(obj)
                db.session.add(obj)
                db.session.flush()  # получить id без полного коммита

                log_to_db(
                    user, 
                    "Создана ОЭС",
                    (
                        f"Порядок отображения: {display_order};"
                        f"Наименование: {name}; "
                        f"Полное наименование: {_dash(name_full)};"
                        f"Часть энергосистемы России: {get_energy_system_type_name(energy_system_type_id)}"
                    ),
                    entity_type="union_energy_system", 
                    entity_id=obj.id)

    try:
        _do_insert()
        _commit_with_retry()
        return None

    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "union_energy_systems")
        _do_insert()
        _commit_with_retry()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, "Ошибка сохранения новой ОЭС", 
            str(e), 
            entity_type="union_energy_system")
        raise ValueError(f"Ошибка сохранения новой ОЭС: {e}")


@no_autoflush
def delete_union_energy_system_service(ids, user):
    """Удаляет записи ОЭС по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError("Не переданы ID для удаления.")

    log_to_db(
        user, 
        "Удаление списка ОЭС", 
        f"Переданы ID для удаления: {ids}",
        entity_type="union_energy_system")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for ues_id in ids:
        try:
            union_energy_system_id = int(ues_id)
        except (TypeError, ValueError):
            invalid.append(ues_id)
            log_to_db(user, 
            "Ошибка удаления ОЭС", 
                f"Некорректный ID: {ues_id}",
                entity_type="union_energy_system",
                entity_id=ues_id)
            continue

        obj = _locked_get(UnionEnergySystem, union_energy_system_id)
        if obj:
            db.session.delete(obj)
            deleted_names.append(get_union_energy_system_name(union_energy_system_id))
            successful_deletes += 1
            log_to_db(
                user, 
                "Удалена ОЭС", 
                f"{get_union_energy_system_name(union_energy_system_id)}",
                entity_type="union_energy_system",
                entity_id=union_energy_system_id)
        else:
            not_found.append(union_energy_system_id)
            log_to_db(
                user, 
                "Ошибка удаления ОЭС", 
                f"ОЭС с ID={union_energy_system_id} не найдена.",
                entity_type="union_energy_system",
                entity_id=union_energy_system_id)

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
            "Ошибка удаления ОЭС", 
            str(e), 
            entity_type="union_energy_system",
            entity_id=union_energy_system_id)
        raise ValueError("Ошибка при удалении данных.")


@no_autoflush
def import_union_energy_system_service(file, user):
    """Импортирует данные ОЭС из Excel-файла в базу данных с проверкой уникальности."""

    try:
        # Чтение данных из файла Excel
        data = pd.read_excel(file)

        # Проверка наличия обязательных столбцов
        required_columns = {'name', 'name_full', 'energy_system_type'}
        if not required_columns.issubset(data.columns):
            raise ValueError("Неверный формат файла. Отсутствуют обязательные столбцы: 'name', 'name_full', 'energy_system_type'.")

        # Очистка данных (удаление пустых строк)
        data = data.dropna(subset=['name', 'name_full', 'energy_system_type'])

        if data.empty:
            raise ValueError("Файл не содержит данных для обновления.")

        # Удаление лишних пробелов
        data['name'] = data['name'].str.strip()
        data['name_full'] = data['name_full'].str.strip()
        data['energy_system_type'] = data['energy_system_type'].str.strip()

        # Счетчики для статистики
        updated_count = 0
        added_count = 0
        deleted_count = 0

        # Получение всех текущих записей из базы данных
        existing_records = db.session.query(UnionEnergySystem).all()
        existing_names = {record.name.strip() for record in existing_records}

        # Список всех имен из загружаемой таблицы
        imported_names = set(data['name'])

        # Удаление лишних записей (которые отсутствуют в загружаемой таблице)
        names_to_delete = existing_names - imported_names
        if names_to_delete:
            db.session.query(UnionEnergySystem).filter(UnionEnergySystem.name.in_(names_to_delete)).delete(synchronize_session=False)
            deleted_count = len(names_to_delete)

        energy_system_types = {
            energy_system_type.name: energy_system_type.id
            for energy_system_type in db.session.query(EnergySystemType).all()
        }

        # Обновление существующих записей и добавление новых
        for _, row in data.iterrows():
            name = row['name']
            name_full = row['name_full']
            energy_system_type = row['energy_system_type']

            # Проверка существования федерального округа
            if energy_system_type not in energy_system_types:
                raise ValueError(f"Тип энергосистемы '{energy_system_type}' не найден в базе данных.")

            id_energy_system_type = energy_system_types[energy_system_type]

            # Проверка существования записи
            existing_record = db.session.query(UnionEnergySystem).filter_by(name=name).first()

            if existing_record:
                # Проверяем, есть ли изменения в записи
                if existing_record.name_full != name_full or existing_record.id_energy_system_type != id_energy_system_type:
                    existing_record.name_full = name_full
                    existing_record.id_energy_system_type = id_energy_system_type
                    updated_count += 1
            else:
                # Проверяем дубликаты перед добавлением
                duplicate = db.session.query(UnionEnergySystem).filter_by(
                    name=name,
                    id_energy_system_type=id_energy_system_type
                ).first()
                if duplicate:
                    raise ValueError(f"Запись с наименованием '{name}' и федеральным округом '{energy_system_type}' уже существует.")

                # Добавляем новую запись
                new_record = UnionEnergySystem(
                    name=name,
                    name_full=name_full,
                    id_energy_system_type=id_energy_system_type
                )
                set_db_version_on_create(new_record)
                db.session.add(new_record)
                added_count += 1

        # Если нет изменений, данных для обновления нет
        if updated_count == 0 and added_count == 0 and deleted_count == 0:
            raise ValueError("Данные для обновления отсутствуют.")

        # Сохранение изменений в базе данных
        _commit_with_retry()

        # Логирование результата
        log_to_db(
            user,
            "Импорт завершен",
            f"Обновлено записей: {updated_count}, добавлено новых: {added_count}, удалено лишних: {deleted_count}",
            entity_type="union_energy_system")
        return {
            "updated": updated_count,
            "added": added_count,
            "deleted": deleted_count
        }
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка импорта данных (IntegrityError)", 
            str(e), 
            entity_type="union_energy_system")
        raise ValueError("Ошибка целостности данных при импорте. Проверьте уникальность записей.")
    except ValueError as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка импорта данных (ValueError)", 
            str(e), 
            entity_type="union_energy_system")
        raise
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка импорта данных", 
            str(e), 
            entity_type="union_energy_system")
        raise ValueError(f"Ошибка при импорте данных: {e}")


def export_union_energy_system_service(
        user, 
        union_energy_system_filter=None, 
        energy_system_type_filter=None, 
        sort_by="display_order", 
        sort_dir="asc"):
    """ Экспортирует данные списка ОЭС в Excel. """

    log_to_db(
        user, 
        "Начата выгрузка таблицы ОЭС. Параметры экспорта", 
        (
            f"Фильтр по столбцу: Наименование ОЭС = {union_energy_system_filter},"
            f"Фильтр по столбцу: Часть энергосистемы России = {get_energy_system_type_name(energy_system_type_filter)},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        ),
        entity_type="union_energy_system")
    
    # Базовый запрос
    query = union_energy_system_query(
        union_energy_system_filter=union_energy_system_filter,
        energy_system_type_filter=energy_system_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(
        user, 
        "Получение данных завершено", 
        f"Найдено записей: {len(items)}", 
        entity_type="union_energy_system")

    # Подготовка данных для Excel
    def _normalize_external_id(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value)
        raw = str(value).strip()
        try:
            as_float = float(raw.replace(",", "."))
            if as_float.is_integer():
                return str(int(as_float))
        except ValueError:
            pass
        return raw

    mapping_sort_fields = {"external_id", "external_name", "external_nameoes", "external_abbr"}
    mappings = UnionEnergySystemExternalMapping.query.order_by(
        UnionEnergySystemExternalMapping.id.desc()
    ).all()
    mapping_by_uuid = {}
    unmatched_mappings = []
    for mapping in mappings:
        if mapping.union_energy_system_ref_uuid:
            if mapping.union_energy_system_ref_uuid not in mapping_by_uuid:
                mapping_by_uuid[mapping.union_energy_system_ref_uuid] = mapping
        else:
            unmatched_mappings.append(mapping)

    rows = [
        SimpleNamespace(ues=ues, mapping=mapping_by_uuid.get(ues.ref_uuid))
        for ues in items
    ]

    if sort_by in mapping_sort_fields:
        rows.extend([SimpleNamespace(ues=None, mapping=m) for m in unmatched_mappings])

        def _sort_key(row):
            mapping = row.mapping
            value = getattr(mapping, sort_by, None) if mapping else None
            if value is None or str(value).strip() == "":
                return (2, "")
            text = str(value).strip()
            if text.isdigit():
                return (0, int(text))
            return (1, text.lower())

        rows.sort(key=_sort_key, reverse=(sort_dir == "desc"))
    else:
        rows.extend([SimpleNamespace(ues=None, mapping=m) for m in unmatched_mappings])

    data = []
    for row in rows:
        mapping = row.mapping
        ues = row.ues
        data.append({
            "Номер (oes)": _dash(_normalize_external_id(mapping.external_id) if mapping else None),
            "Название (name)": _dash(mapping.external_name if mapping else None),
            "Наименование (nameoes)": _dash(mapping.external_nameoes if mapping else None),
            "Сокр. ОЭС (abbr)": _dash(mapping.external_abbr if mapping else None),
            "UUID": _dash(ues.ref_uuid if ues else None),
            "ID ОЭС": _dash(ues.id if ues else None),
            "Наименование": _dash(ues.name if ues else None),
        })

    log_to_db(
        user, 
        "Подготовка данных для экспорта таблицы ОЭС в Excel", 
        f"Записей для экспорта: {len(data)}",
        entity_type="union_energy_system")

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)
    
    # Создание Excel-файла
    output = BytesIO()
    sheet_name = "ОЭС"
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
        "Экспорт таблицы ОЭС в Excel завершен", 
        f"Экспортировано записей: {len(data)}",
        entity_type="union_energy_system")

    return output