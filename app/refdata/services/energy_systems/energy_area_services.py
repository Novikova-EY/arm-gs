"""Сервисный модуль: Энергозоны"""

from app.extensions import db
from sqlalchemy import or_, text, func
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 

# Модели
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.energy_area_model import EnergyArea

from app.refdata.models.territories.regional_district_model import RegionalDistrict

# Сервисы
from app.common.services.get_services.territories.regional_district_get_services import (
    get_regional_district_name,
)
from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
    get_regional_energy_system_name,
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
)

# Логирование
from app.logs.services.logging_service import log_to_db


def energy_area_query(
    energy_area_filter=None,
    regional_district_filter=None,
    regional_energy_system_filter=None,
    union_energy_system_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """ Базовый запрос для выборки ОЭС с фильтрацией и сортировкой. """

    # Валидные поля сортировки
    allowed_sort_by = {"id", "name", "regional_district", "regional_energy_system", "union_energy_system"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = "desc" if (sort_dir or "asc").lower() == "desc" else "asc"
    desc_order = (sort_dir == "desc")

    # Безопасная конвертация ID-фильтров
    regional_district_id = _to_int_or_none(regional_district_filter)
    regional_energy_system_id = _to_int_or_none(regional_energy_system_filter)
    union_energy_system_id = _to_int_or_none(union_energy_system_filter)

    # Базовый запрос
    query = (
        EnergyArea.query
        .options(
            joinedload(EnergyArea.regional_district)
        )
        .filter(EnergyArea.id > 0)
    )

    # Фильтрация по названию/ID энергорайона (ИЛИ)
    if energy_area_filter:
        query = query.filter(
            or_(
                EnergyArea.name.ilike(f"%{energy_area_filter}%"),
            )
        )

    # Фильтр по субъекту РФ (через прямую связь)
    if regional_district_filter:
        query = query.join(EnergyArea.regional_district)
        if regional_district_id is not None:
            query = query.filter(RegionalDistrict.id == regional_district_id)
        else:
            query = query.filter(RegionalDistrict.name.ilike(f"%{regional_district_filter}%"))

    # Фильтр по региональной энергосистеме (через прямую связь)
    if regional_energy_system_filter:
        query = query.join(EnergyArea.regional_district)
        if regional_energy_system_id is not None:
            query = query.filter(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.id == regional_energy_system_id
                )
            )
        else:
            query = query.filter(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.name.ilike(f"%{regional_energy_system_filter}%")
                )
            )

    # Фильтр по ОЭС (через РЭС -> ОЭС)
    if union_energy_system_filter:
        query = query.join(EnergyArea.regional_district)
        if union_energy_system_id is not None:
            query = query.filter(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.union_energy_system.has(
                        UnionEnergySystem.id == union_energy_system_id
                    )
                )
            )
        else:
            query = query.filter(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.union_energy_system.has(
                        UnionEnergySystem.name.ilike(f"%{union_energy_system_filter}%")
                    )
                )
            )
        
    # Сортировка
    if sort_by == "name":
        query = query.order_by(EnergyArea.name.desc() if desc_order else EnergyArea.name.asc())

    elif sort_by == "regional_district":
        query = (
            query.outerjoin(EnergyArea.regional_district)
                 .order_by(
                     RegionalDistrict.name.desc() if desc_order else RegionalDistrict.name.asc(),
                     EnergyArea.id.desc() if desc_order else EnergyArea.id.asc()
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
            .outerjoin(EnergyArea.regional_district)
            .outerjoin(res_key_sq, res_key_sq.c.rd_id == RegionalDistrict.id)
            .order_by(
                res_key_sq.c.res_sort_key.desc() if desc_order else res_key_sq.c.res_sort_key.asc(),
                EnergyArea.id.desc() if desc_order else EnergyArea.id.asc(),
            )
        )

    elif sort_by == "union_energy_system":
        ues_key_sq = (
            db.session.query(
                RegionalDistrict.id.label("rd_id"),
                func.min(UnionEnergySystem.name).label("ues_sort_key"),
            )
            .select_from(RegionalDistrict)
            .outerjoin(RegionalDistrict.regional_energy_systems)
            .outerjoin(RegionalEnergySystem.union_energy_system)
            .group_by(RegionalDistrict.id)
            .subquery()
        )
        query = (
            query
            .outerjoin(EnergyArea.regional_district)
            .outerjoin(ues_key_sq, ues_key_sq.c.rd_id == RegionalDistrict.id)
            .order_by(
                ues_key_sq.c.ues_sort_key.desc() if desc_order else ues_key_sq.c.ues_sort_key.asc(),
                EnergyArea.id.desc() if desc_order else EnergyArea.id.asc(),
            )
        )
    
    else:  # "id"
        query = query.order_by(EnergyArea.id.desc() if desc_order else EnergyArea.id.asc())

    # Исключаем запись "Не указано" (id=0)
    query = query.filter(EnergyArea.id.isnot(None), EnergyArea.id > 0)

    return query


@no_autoflush
def get_energy_area_list(
        page, 
        per_page, 
        energy_area_filter=None, 
        regional_district_filter=None, 
        regional_energy_system_filter=None, 
        union_energy_system_filter=None, 
        sort_by="id", 
        sort_dir="asc"
):
    """ Получает список энергорайонов с пагинацией, фильтрацией и сортировкой. """

    # Базовый запрос
    query = energy_area_query(
        energy_area_filter=energy_area_filter,
        regional_district_filter=regional_district_filter,
        regional_energy_system_filter=regional_energy_system_filter,
        union_energy_system_filter=union_energy_system_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_energy_area_service(data, user):
    """ Обновление данных по энергорайонам. """
        
    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []

    log_to_db(user, "Получены данные для обновления списка энергорайонов")

    with db.session.no_autoflush:
        for record in data:
            energy_area_id = record.get("energy_area_id")
            name = record.get("name")
            regional_district_id = record.get("regional_district_id")

           # Проверки на валидность данных
            if not name or not regional_district_id:
                log_to_db(user, "Ошибка валидации", f"Запись: {record}")
                raise ValueError(f"Каждая запись должна содержать 'name' и 'regional_district'. Данные: {record}")
            
            obj = db.session.get(EnergyArea, energy_area_id)
            if not obj:
                log_to_db(user, "Ошибка валидации", f"Запись с ID «{energy_area_id}» не найдена.")
                raise ValueError(f"Запись с ID «{energy_area_id}» не найдена.")

            # Проверка уникальности name только если меняется
            if name != (obj.name or ""):
                q = (EnergyArea.query
                     .filter(EnergyArea.name == name,
                             EnergyArea.id != energy_area_id))
                if q.first():
                    log_to_db(user, "Ошибка валидации", f"Запись с наименованием «{name}» уже существует.")
                    raise ValueError(f"Запись с именем «{name}» уже существует.")
            
            changes = {}

            if name != (obj.name or ""):
                changes["Наименование"] = f"{_dash(obj.name)} → {name}"
                obj.name = name
            
            # Проверка наличия субъекта РФ
            if "regional_district_id" in record:
                new_val = _to_int_or_none(record.get("regional_district_id"), keep_zero=False)
                if new_val != obj.id_regional_district:
                    new_obj = db.session.get(RegionalDistrict, new_val) if new_val is not None else None
                    if new_val is not None and not new_obj:
                        raise ValueError(f"Субъект РФ с id={new_val} не найден.")
                    
                    prev_obj = db.session.get(RegionalDistrict, obj.id_regional_district) if obj.id_regional_district else None
                    changes["Субъект РФ"] = f"{_dash(prev_obj.name if prev_obj else None)} → {_dash(new_obj.name if new_obj else None)}"
                    obj.id_regional_district = new_val
            
            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(user, f"Обновлен энергорайон: {name}", f"Изменения = {changes}")
                updated_ids.append(energy_area_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(user, "Сохранены изменения по энергорайонам", f"Измененных записей: {len(updated_ids)} (id: {updated_ids})")
        else:
            log_to_db(user, "Изменений по энергорайонам не обнаружено", "")
            
        return updated_ids

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения энергорайона(уникальность/целостность)", str(e))
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка при сохранении энергорайонов", str(e))
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_energy_area_service(data, user):
    """ Создание новой записи: энергорайон """
        
    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    try:
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                name = record.get("name")
                regional_district_id = _to_int_or_none(record.get("regional_district_id"), keep_zero=False)

                if not name or not regional_district_id:
                    log_to_db(user, "Ошибка валидации", f"Запись: {record}")
                    raise ValueError(f"Каждая запись должна содержать 'name' и 'regional_district_id'. Данные: {record}")

                # Проверяем существование субъекта РФ
                rd_obj = db.session.get(RegionalDistrict, regional_district_id)
                if not rd_obj:
                    raise ValueError(f"Субъект РФ с id={regional_district_id} не найден.")

                # Проверяем уникальность name
                dup = (EnergyArea.query
                        .filter(EnergyArea.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с именем «{name}» уже существует.")

                # Создаем новую запись
                ea_obj = EnergyArea(
                    name=name,
                    id_regional_district=regional_district_id,
                )
                db.session.add(ea_obj)
                db.session.flush()  # получить id без полного коммита

                log_to_db(user, "Создан энергорайон",
                    (
                        f"Наименование: {name}; "
                        f"Субъект РФ: {get_regional_district_name(regional_district_id)}"
                    )
                )

        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        return None

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения энергорайонв (уникальность/целостность)", str(e))
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения энергорайонв", str(e))
        raise ValueError(f"Ошибка при добавлении/обновлении записей: {e}")


@no_autoflush
def delete_energy_area_service(ids, user):
    """Удаляет записи энергорайонов по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")

    log_to_db(user, "Удаление энергорайонов", 
              f"Переданы ID для удаления: {ids}")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for ea_id in ids:
        try:
            energy_area_id = _to_int_or_none(ea_id, keep_zero=False)
        except (TypeError, ValueError):
            invalid.append(ea_id)
            log_to_db(user, "Ошибка удаления энергорайона'", 
                      f"Некорректный ID: {ea_id}")
            continue

        obj = _locked_get(EnergyArea, energy_area_id)
        if obj:
            name = obj.name or f"ID={energy_area_id}"
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            log_to_db(user, "Удален энергорайон", 
                      f"{name}")
        else:
            not_found.append(energy_area_id)
            log_to_db(user, "Ошибка удаления энергорайона", 
                      f"Энергорайон с ID={energy_area_id} не найден.")

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

        log_to_db(user, "Результат удаления энергорайонов", "; ".join(parts))

        return {
            "deleted": successful_deletes,
            "deleted_names": deleted_names,
            "not_found": not_found,
            "invalid": invalid,
        }
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления энергорайонов", str(e))
        raise ValueError(f"Ошибка при удалении данных.")

    
def export_energy_area_service(
        user, 
        energy_area_filter=None, 
        regional_district_filter=None, 
        regional_energy_system_filter=None, 
        union_energy_system_filter=None, 
        sort_by="id", 
        sort_dir="asc"
):
    """ Экспортирует данные списка энергорайонов в Excel. """

    log_to_db(user, "Начата выгрузка таблицы энергорайонов из базы данных")
    log_to_db(user, "Параметры экспорта",
        (
            f"Фильтр по столбцу: Наименование энергорайона = {energy_area_filter},"
            f"Фильтр по столбцу: Субъект РФ = {get_regional_district_name(regional_district_filter)},"
            f"Фильтр по столбцу: Региональная энергосистема = {get_regional_energy_system_name(regional_energy_system_filter)},"
            f"Фильтр по столбцу: ОЭС = {get_union_energy_system_name(union_energy_system_filter)},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        ),
    )

    # Базовый запрос
    query = energy_area_query(
        energy_area_filter=energy_area_filter,
        regional_district_filter=regional_district_filter,
        regional_energy_system_filter=regional_energy_system_filter,
        union_energy_system_filter=union_energy_system_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    
    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Наименование": _dash(o.name),
            "Субъект РФ": getattr(o.regional_district.name, "name", "Не указан") or "Не указан",
            "Региональная энергосистема": getattr(o.regional_energy_system.name, "name", "Не указана") or "Не указана",
            "ОЭС": getattr(o.union_energy_system.name, "name", "Не указана") or "Не указана",
        })

    log_to_db(user, "Подготовка данных для экспорта таблицы энергорайонов в Excel",
              f"Записей для экспорта: {len(data)}")

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)

    # Создание Excel и авто-ширина столбцов
    output = BytesIO()
    sheet_name = "Энергорайоны"
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]

        # Автоподбор ширины с аккуратным лимитом
        for i, col in enumerate(df.columns):
            max_len = max(len(str(col)), *(len(str(v)) for v in df[col].values)) if not df.empty else len(str(col))
            ws.set_column(i, i, min(max_len + 2, 60))

    output.seek(0)
    log_to_db(user, "Экспорт таблицы энергорайонов в Excel завершен", 
              f"Экспортировано записей: {len(data)}")

    return output