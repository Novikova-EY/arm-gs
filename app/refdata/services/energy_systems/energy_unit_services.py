"""Сервисный модуль: Энергоузлы."""

from app.extensions import db
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 
from config import SCHEMA_REFDATA

# Модели
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem

from app.refdata.models.territories.regional_district_model import RegionalDistrict

# Сервисы
from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
    get_regional_energy_system_name,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_name,
)
from app.common.services.get_services.energy_systems.energy_unit_get_services import (
    get_energy_unit_name,
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


def energy_unit_query(
        energy_unit_filter=None, 
        regional_district_filter=None, 
        regional_energy_system_filter=None, 
        union_energy_system_filter=None, 
        sort_by="id", 
        sort_dir="asc"):
    """ Базовый запрос для выборки энергоузлов с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id", "name", "regional_district", "regional_energy_system", "union_energy_system"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Безопасная конвертация ID-фильтров
    regional_district_id = _to_int_or_none(regional_district_filter)
    regional_energy_system_id = _to_int_or_none(regional_energy_system_filter)
    union_energy_system_id = _to_int_or_none(union_energy_system_filter)

    # Базовый запрос
    query = (
        EnergyUnit.query
        .options(
            joinedload(EnergyUnit.regional_district)
                .selectinload(RegionalDistrict.regional_energy_systems)
        )
        .filter(EnergyUnit.id > 0)
    )
    query = apply_version_filter(query, EnergyUnit)

    # Фильтрация по названию энергоузла
    if energy_unit_filter:
        query = query.filter(EnergyUnit.name.ilike(f"%{energy_unit_filter}%"))

    # Фильтрация по субъекту РФ
    if regional_district_filter:
        query = query.join(EnergyUnit.regional_district)
        if regional_district_id is not None:
            query = query.filter(RegionalDistrict.id == regional_district_id)
        else:
            query = query.filter(RegionalDistrict.name.ilike(f"%{regional_district_filter}%"))

    # Фильтрация по региональной энергосистеме
    if regional_energy_system_filter:
        query = query.join(EnergyUnit.regional_district).filter(
            RegionalDistrict.regional_energy_systems.any(
                RegionalEnergySystem.id == regional_energy_system_id
                if regional_energy_system_id is not None
                else RegionalEnergySystem.name.ilike(f"%{regional_energy_system_filter}%")
            )
        )

    # Фильтрация по ОЭС
    if union_energy_system_filter:
        query = query.join(EnergyUnit.regional_district).filter(
            RegionalDistrict.regional_energy_systems.any(
                RegionalEnergySystem.union_energy_system.has(
                    UnionEnergySystem.id == union_energy_system_id
                    if union_energy_system_id is not None
                    else UnionEnergySystem.name.ilike(f"%{union_energy_system_filter}%")
                )
            )
        )

    # Сортировка
    if sort_by == "name":
        query = query.order_by(EnergyUnit.name.desc() if sort_dir == "desc" else EnergyUnit.name.asc())

    elif sort_by == "regional_district":
        query = (
            query
            .outerjoin(EnergyUnit.regional_district)
            .order_by(
                RegionalDistrict.name.desc() if sort_dir == "desc" else RegionalDistrict.name.asc(),
                EnergyUnit.id.desc() if sort_dir == "desc" else EnergyUnit.id.asc(),
            )
        )

    elif sort_by == "regional_energy_system":
        res_key_sq = (
            db.session.query(
                RegionalDistrict.id.label("rd_id"),
                func.min(RegionalEnergySystem.name).label("res_sort_key"),
            )
            .select_from(RegionalDistrict)
            .outerjoin(RegionalDistrict.regional_energy_systems)
            .group_by(RegionalDistrict.id)
            .subquery()
        )
        query = (
            query
            .outerjoin(EnergyUnit.regional_district)
            .outerjoin(res_key_sq, res_key_sq.c.rd_id == RegionalDistrict.id)
            .order_by(
                res_key_sq.c.res_sort_key.desc() if sort_dir == "desc" else res_key_sq.c.res_sort_key.asc(),
                EnergyUnit.id.desc() if sort_dir == "desc" else EnergyUnit.id.asc(),
            )
        )

    elif sort_by == "union_energy_system":
        ues_key_sq = (
            db.session.query(
                RegionalDistrict.id.label("rd_id"),
                func.coalesce(func.min(UnionEnergySystem.name), "").label("ues_sort_key"),
            )
            .select_from(RegionalDistrict)
            .outerjoin(RegionalDistrict.regional_energy_systems)
            .outerjoin(RegionalEnergySystem.union_energy_system)
            .group_by(RegionalDistrict.id)
            .subquery()
        )

        query = (
            query
            # нужен доступ к RD, чтобы связать сабквери
            .outerjoin(EnergyUnit.regional_district)
            .outerjoin(ues_key_sq, ues_key_sq.c.rd_id == RegionalDistrict.id)
            .order_by(
                (ues_key_sq.c.ues_sort_key.desc().nulls_last()
                    if sort_dir == "desc"
                    else ues_key_sq.c.ues_sort_key.asc().nulls_first()),
                EnergyUnit.id.desc() if sort_dir == "desc" else EnergyUnit.id.asc(),
            )
        )
        
    else:  # сортировка по id
        query = query.order_by(
            EnergyUnit.id.desc() if sort_dir == "desc" else EnergyUnit.id.asc()
        )

    # Исключаем запись "Не указано" (id=0)
    query = query.filter(EnergyUnit.id.isnot(None), EnergyUnit.id > 0)

    return query


@no_autoflush
def get_energy_unit_list(
    page, 
    per_page, 
    energy_unit_filter=None, 
    regional_district_filter=None, 
    regional_energy_system_filter=None, 
    union_energy_system_filter=None, 
    sort_by="id", 
    sort_dir="asc"):
    """ Получает список энергоузлов с пагинацией, фильтрацией и сортировкой. """
    
    # Базовый запрос
    query = energy_unit_query(
        energy_unit_filter=energy_unit_filter,
        regional_district_filter=regional_district_filter,
        regional_energy_system_filter=regional_energy_system_filter,
        union_energy_system_filter=union_energy_system_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_energy_unit_service(data, user):
    """ Обновление данных по энергоузлам. """

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []
    
    log_to_db(
        user, 
        "Получены данные для обновления списка энергоузлов", 
        f"{data}",
        entity_type="energy_unit")
    
    with db.session.no_autoflush:
        for record in data:
            energy_unit_id = record.get("energy_unit_id")
            name = record.get("name")
            name_rp = (record.get("name_rp") or "").strip() or name
            name_dp = (record.get("name_dp") or "").strip() or name
            regional_district_id = record.get("regional_district_id")
            regional_energy_system_id = record.get("regional_energy_system_id")

            # Проверки на валидность данных
            if not name or not regional_district_id or not regional_energy_system_id:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись: {record}",
                    entity_type="energy_unit",
                    entity_id=energy_unit_id)
                raise ValueError(f"Каждая запись должна содержать 'name' и 'regional_district_id' и 'regional_energy_system_id'. Данные: {record}")

            obj = db.session.get(EnergyUnit, energy_unit_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{energy_unit_id}» не найдена.",
                    entity_type="energy_unit", 
                    entity_id=energy_unit_id)
                raise ValueError(f"Запись с ID «{energy_unit_id}» не найдена.")

            # Проверка уникальности name только если меняется
            if name != (obj.name or ""):
                q = (apply_version_filter(EnergyUnit.query, EnergyUnit)
                     .filter(EnergyUnit.name == name,
                             EnergyUnit.id != energy_unit_id))
                if q.first():
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись с наименованием «{name}» уже существует.",
                        entity_type="energy_unit",
                        entity_id=energy_unit_id)
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
            changes = []

            if name != (obj.name or ""):
                changes.append(format_field_change("name", obj.name or "не указано", name, "energy_unit"))
                obj.name = name
            if name_rp != (obj.name_rp or ""):
                changes.append(format_field_change("name_rp", obj.name_rp or "не указано", name_rp, "energy_unit"))
                obj.name_rp = name_rp
            if name_dp != (obj.name_dp or ""):
                changes.append(format_field_change("name_dp", obj.name_dp or "не указано", name_dp, "energy_unit"))
                obj.name_dp = name_dp

            # Проверка наличия субъекта РФ
            if "regional_district_id" in record:
                new_val = _to_int_or_none(record.get("regional_district_id"), keep_zero=False)
                if new_val != obj.id_regional_district:
                    new_obj = db.session.get(RegionalDistrict, new_val) if new_val is not None else None
                    if new_val is not None and not new_obj:
                        raise ValueError(f"Субъект РФ с id={new_val} не найден.")
                    
                    prev_obj = db.session.get(RegionalDistrict, obj.id_regional_district) if obj.id_regional_district else None
                    old_name = prev_obj.name if prev_obj else "не указано"
                    new_name = new_obj.name if new_obj else "не указано"
                    changes.append(format_field_change("id_regional_district", old_name, new_name, "energy_unit"))
                    obj.id_regional_district = new_val

            # Проверка наличия региональной энергосистемы
            if "regional_energy_system_id" in record:
                new_val = _to_int_or_none(record.get("regional_energy_system_id"), keep_zero=False)
                if new_val != obj.id_regional_energy_system:
                    new_obj = db.session.get(RegionalEnergySystem, new_val) if new_val is not None else None
                    if new_val is not None and not new_obj:
                        raise ValueError(f"Субъект РФ с id={new_val} не найден.")
                    
                    prev_obj = db.session.get(RegionalEnergySystem, obj.id_regional_energy_system) if obj.id_regional_energy_system else None
                    old_name = prev_obj.name if prev_obj else "не указано"
                    new_name = new_obj.name if new_obj else "не указано"
                    changes.append(format_field_change("id_regional_energy_system", old_name, new_name, "energy_unit"))
                    obj.id_regional_energy_system = new_val

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    f"Обновлен энергоузел: {name}", 
                    f"Изменения: {'; '.join(changes)}",
                    entity_type="energy_unit", 
                    entity_id=energy_unit_id)
                updated_ids.append(energy_unit_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по энергоузлам", 
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})",
                entity_type="energy_unit")
        else:
            log_to_db(
                user, 
                "Изменений по энергоузлам не обнаружено", 
                "", 
                entity_type="energy_unit")
            
        return updated_ids

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения энергоузлов (уникальность/целостность)", 
            str(e), 
            entity_type="energy_unit")
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Неизвестная ошибка при сохранении энергоузлов", 
            str(e), 
            entity_type="energy_unit")
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_energy_unit_service(data, user):
    """ Создание новой записи: энергоузел """

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    def _do_insert():
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                name = (record.get("name") or "").strip()
                name_rp = (record.get("name_rp") or name or "").strip()
                name_dp = (record.get("name_dp") or name or "").strip()
                regional_district_id = _to_int_or_none(record.get("regional_district_id"), keep_zero=False)
                regional_energy_system_id = _to_int_or_none(record.get("regional_energy_system_id"), keep_zero=False)

                # Проверка на наличие необходимых данных
                if not (name or regional_district_id or regional_energy_system_id):
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись: {record}",
                        entity_type="energy_unit")
                    raise ValueError(f"Каждая запись должна содержать 'name', 'regional_district_id' и 'regional_energy_system_id'. Данные: {record}")
                
                # Проверяем существование субъекта РФ
                rd_obj = db.session.get(RegionalDistrict, regional_district_id)
                if not rd_obj:
                    raise ValueError(f"Субъект РФ с id={regional_district_id} не найдена.")
                
                # Проверяем существование региональной энергосистемы
                res_obj = db.session.get(RegionalEnergySystem, regional_energy_system_id)
                if not res_obj:
                    raise ValueError(f"Региональная энергосистема с id={regional_energy_system_id} не найдена.")
                
                # Проверяем уникальность name
                dup = (apply_version_filter(EnergyUnit.query, EnergyUnit)
                        .filter(EnergyUnit.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")

                # Создаем новую запись
                obj = EnergyUnit(
                    name=name,
                    name_rp=name_rp,
                    name_dp=name_dp,
                    id_regional_district=rd_obj.id,
                    id_regional_energy_system=res_obj.id,
                )
                set_db_version_on_create(obj)
                db.session.add(obj)
                db.session.flush()  # получить id без полного коммита

                log_to_db(
                    user, 
                    "Создана региональная энергосистема",
                    (
                        f"Наименование: {name}; "
                        f"Субъект РФ: {rd_obj.name}; "
                        f"Региональная энергосистема: {res_obj.name} "
                    ),
                    entity_type="energy_unit", 
                    entity_id=obj.id)

    try:
        _do_insert()
        _commit_with_retry()
        return None

    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "energy_units")
        _do_insert()
        _commit_with_retry()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения нового энергоузла", 
            str(e), 
            entity_type="energy_unit")
        raise ValueError(f"Ошибка сохранения нового энергоузла: {e}")


@no_autoflush
def delete_energy_unit_service(ids, user):
    """Удаляет записи энергоузлов по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")
    
    log_to_db(
        user, 
        "Удаление записей", 
        f"Переданы ID для удаления: {ids}",
        entity_type="energy_unit")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for eu_id in ids:
        try:
            energy_unit_id = _to_int_or_none(eu_id, keep_zero=False)
        except (TypeError, ValueError):
            invalid.append(eu_id)
            log_to_db(
                user, 
                "Ошибка удаления энергоузла", 
                f"Некорректный ID: {eu_id}",
                entity_type="energy_unit",
                entity_id=eu_id)
            continue

        obj = _locked_get(EnergyUnit, energy_unit_id)
        if obj:
            db.session.delete(obj)
            deleted_names.append(get_energy_unit_name(energy_unit_id))
            successful_deletes += 1
            log_to_db(
                user, 
                "Удален энергоузел", 
                f"{get_energy_unit_name(energy_unit_id)}",
                entity_type="energy_unit",
                entity_id=energy_unit_id)
        else:
            not_found.append(energy_unit_id)
            log_to_db(
                user, 
                "Ошибка удаления энергоузла", 
                f"Энергоузел с ID={energy_unit_id} не найден.",
                entity_type="energy_unit",
                entity_id=energy_unit_id)

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
            "Ошибка удаления энергоузлов", 
            str(e), 
            entity_type="energy_unit",
            entity_id=energy_unit_id)
        raise ValueError(f"Ошибка при удалении данных.")


def export_energy_unit_service(
        user, 
        energy_unit_filter=None, 
        regional_district_filter=None, 
        regional_energy_system_filter=None,
        union_energy_system_filter=None, 
        sort_by="id", 
        sort_dir="asc"):
    """ Экспортирует данные списка энергозулов в Excel. """

    log_to_db(
        user, 
        "Начата выгрузка таблицы энергозулов. Параметры экспорта", 
        (
            f"Фильтр по столбцу: Наименование энергоузла = {energy_unit_filter},"
            f"Фильтр по столбцу: Субъект РФ = {get_regional_district_name(regional_district_filter)},"
            f"Фильтр по столбцу: Региональная энергосистема = {get_regional_energy_system_name(regional_energy_system_filter)},"
            f"Фильтр по столбцу: ОЭС = {get_union_energy_system_name(union_energy_system_filter)},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        ),
        entity_type="energy_unit")
    
    # Базовый запрос
    query = energy_unit_query(
        energy_unit_filter=energy_unit_filter,
        regional_district_filter=regional_district_filter,
        regional_energy_system_filter=regional_energy_system_filter,
        union_energy_system_filter=union_energy_system_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(
        user, 
        "Получение данных завершено", 
        f"Найдено записей: {len(items)}", 
        entity_type="energy_unit")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Энергорайон": o.name,
            "Энергорайон (род. пад.)": o.name_rp or "",
            "Энергорайон (предл. пад.)": o.name_dp or "",
            "Субъект РФ": o.regional_district.name if o.regional_district else "Не указан",
            "Региональная энергосистема": o.regional_energy_system.name if o.regional_energy_system else "Не указана",
            "ОЭС": o.union_energy_system.name if o.union_energy_system else "Не указана",
        })

    log_to_db(
        user, 
        "Подготовка данных для экспорта таблицы энергозулов в Excel", 
        f"Записей для экспорта: {len(data)}",
        entity_type="energy_unit")

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)
    
    # Создание Excel-файла
    output = BytesIO()
    sheet_name = "Энергозулы"
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
        "Экспорт таблицы энергозулов в Excel завершен", 
        f"Экспортировано записей: {len(data)}",
        entity_type="energy_unit")

    return output

# === all_versions_energy_unit start ===
@no_autoflush
def add_energy_unit_all_versions_service(data, user):
    from app.refdata.services.refdata_all_versions_common import add_all_versions_records, update_all_versions_records, fk_id_for_version
    from app.refdata.models.territories.regional_district_model import RegionalDistrict
    from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem

    def normalize_record(record):
        name = (record.get("name") or "").strip()
        name_rp = (record.get("name_rp") or "").strip() or name
        name_dp = (record.get("name_dp") or "").strip() or name
        regional_district_id = _to_int_or_none(record.get("regional_district_id"), keep_zero=False)
        regional_energy_system_id = _to_int_or_none(record.get("regional_energy_system_id"), keep_zero=False)
        if not name or not regional_district_id or not regional_energy_system_id:
            raise ValueError("Каждая запись должна содержать 'name', 'regional_district_id' и 'regional_energy_system_id'.")
        return {
            "name": name,
            "name_rp": name_rp,
            "name_dp": name_dp,
            "regional_district_id": regional_district_id,
            "regional_energy_system_id": regional_energy_system_id,
        }

    def resolve_for_version(clean, version_id):
        return {
            "name": clean["name"],
            "name_rp": clean["name_rp"],
            "name_dp": clean["name_dp"],
            "id_regional_district": fk_id_for_version(RegionalDistrict, clean["regional_district_id"], version_id),
            "id_regional_energy_system": fk_id_for_version(RegionalEnergySystem, clean["regional_energy_system_id"], version_id),
        }

    return add_all_versions_records(
        data=data,
        user=user,
        model_cls=EnergyUnit,
        entity_type="energy_unit",
        normalize_record=normalize_record,
        resolve_for_version=resolve_for_version,
        unique_fields=['name']
    )


@no_autoflush
def update_energy_unit_all_versions_service(data, user):
    from app.refdata.services.refdata_all_versions_common import add_all_versions_records, update_all_versions_records, fk_id_for_version
    from app.refdata.models.territories.regional_district_model import RegionalDistrict
    from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem

    def normalize_record(record):
        energy_unit_id = record.get("energy_unit_id")
        name = (record.get("name") or "").strip()
        name_rp = (record.get("name_rp") or "").strip() or name
        name_dp = (record.get("name_dp") or "").strip() or name
        regional_district_id = _to_int_or_none(record.get("regional_district_id"), keep_zero=False)
        regional_energy_system_id = _to_int_or_none(record.get("regional_energy_system_id"), keep_zero=False)
        if not name or not regional_district_id or not regional_energy_system_id:
            raise ValueError("Каждая запись должна содержать 'name', 'regional_district_id' и 'regional_energy_system_id'.")
        return {
            "energy_unit_id": energy_unit_id,
            "name": name,
            "name_rp": name_rp,
            "name_dp": name_dp,
            "regional_district_id": regional_district_id,
            "regional_energy_system_id": regional_energy_system_id,
        }

    def resolve_for_version(clean, version_id):
        return {
            "name": clean["name"],
            "name_rp": clean["name_rp"],
            "name_dp": clean["name_dp"],
            "id_regional_district": fk_id_for_version(RegionalDistrict, clean["regional_district_id"], version_id),
            "id_regional_energy_system": fk_id_for_version(RegionalEnergySystem, clean["regional_energy_system_id"], version_id),
        }

    return update_all_versions_records(
        data=data,
        user=user,
        model_cls=EnergyUnit,
        entity_type="energy_unit",
        pk_field="energy_unit_id",
        normalize_record=normalize_record,
        resolve_for_version=resolve_for_version,
        tracked_fields=['name', 'name_rp', 'name_dp', 'id_regional_district', 'id_regional_energy_system'],
        unique_fields=['name'],
        temp_fields=['name'],
        clear_fields=[]
    )
# === all_versions_energy_unit end ===
