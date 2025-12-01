"""Сервисный модуль: Энергозоны."""

from app.extensions import db
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 
from config import SCHEMA_REFDATA

# Модели
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone

from app.refdata.models.territories.regional_district_model import RegionalDistrict

# Сервисы
from app.common.services.get_services.energy_systems.energy_zone_get_services import (
    get_energy_zone_name,
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


def energy_zone_query(
    energy_zone_filter=None,
    sort_by="id",
    sort_dir="asc"):
    """ Базовый запрос для выборки списка энергозон с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id", "name"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Базовый запрос
    query = EnergyZone.query
    query = apply_version_filter(query, EnergyZone)

    # Фильтрация по названию энергозон
    if energy_zone_filter:
        query = query.filter(
            or_(
                EnergyZone.number.ilike(f"%{energy_zone_filter}%"),
                EnergyZone.name.ilike(f"%{energy_zone_filter}%"),
            )
        )

    # Сортировка
    if sort_by in ["number", "name"]:
        sort_field = getattr(EnergyZone, sort_by)
        query = query.order_by(
            sort_field.desc() if sort_dir == "desc" else sort_field.asc()
        )

    else:  # сортировка по id
        query = query.order_by(
            EnergyZone.id.desc() if sort_dir == "desc" else EnergyZone.id.asc()
        )

    # Исключаем запись "Не указано" (id=0)
    query = query.filter(EnergyZone.id.isnot(None), EnergyZone.id > 0)

    return query


@no_autoflush
def get_energy_zone_list(
    page, 
    per_page, 
    energy_zone_filter=None,
    sort_by="id", 
    sort_dir="asc"):
    """ Получает список энергозон с пагинацией, фильтрацией и сортировкой. """
    
    # Базовый запрос
    query = energy_zone_query(
        energy_zone_filter=energy_zone_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_energy_zone_service(data, user):
    """Обновление данных по энергозонам."""

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []

    log_to_db(
        user, 
        "Получены данные для обновления списка энергозон", 
        f"{data}",
        entity_type="energy_zone")

    with db.session.no_autoflush:
        for record in data:
            energy_zone_id = record.get("energy_zone_id")
            number = record.get("number")
            name = record.get("name")

            # Проверки на валидность данных
            if not name or not number:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись: {record}",
                    entity_type="energy_zone",
                    entity_id=energy_zone_id)
                raise ValueError(f"Каждая запись должна содержать 'name', 'number'. Данные: {record}")

            obj = db.session.get(EnergyZone, energy_zone_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{energy_zone_id}» не найдена.", 
                    entity_type="energy_zone", 
                    entity_id=energy_zone_id)
                raise ValueError(f"Запись с ID «{energy_zone_id}» не найдена.")
            
            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (apply_version_filter(EnergyZone.query, EnergyZone)
                     .filter(EnergyZone.name == name,
                             EnergyZone.id != energy_zone_id))
                if q.first():
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
            # Проверка уникальности number
            if number != (obj.number or ""):
                q_full = (apply_version_filter(EnergyZone.query, EnergyZone)
                     .filter(EnergyZone.number == number,
                             EnergyZone.id != energy_zone_id))
                if q_full.first():
                    raise ValueError(f"Запись с номером «{number}» уже существует.")

            changes = []

            if name != (obj.name or ""):
                changes.append(format_field_change("name", obj.name or "не указано", name, "energy_zone"))
                obj.name = name

            if number != (obj.number or ""):
                old_val = obj.number if obj.number is not None else "не указано"
                new_val = number if number is not None else "не указано"
                changes.append(f"Номер: {old_val} → {new_val}")
                obj.number = number

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    f"Обновлена энергозона: {name}", 
                    f"Изменения: {'; '.join(changes)}",
                    entity_type="energy_zone", 
                    entity_id=energy_zone_id)
                updated_ids.append(energy_zone_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по энергозонам", 
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})",
                entity_type="energy_zone")
        else:
            log_to_db(
                user, 
                "Изменений по энергозонам не обнаружено", 
                "", 
                entity_type="energy_zone")
            
        return updated_ids

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения энергозон (уникальность/целостность)", 
            str(e), 
            entity_type="energy_zone")
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, "Неизвестная ошибка при сохранении энергозон", 
            str(e), 
            entity_type="energy_zone")
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_energy_zone_service(data, user):
    """ Создание новой записи: энергозона """

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    def _do_insert():
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                number = (record.get("number") or "").strip()
                name = (record.get("name") or "").strip()

                # Проверка на наличие необходимых данных
                if not name or not number:
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись: {record}", 
                        entity_type="energy_zone")
                    raise ValueError(f"Каждая запись должна содержать 'number' и 'name'.")

                # Проверяем уникальность name при создании
                dup = (apply_version_filter(EnergyZone.query, EnergyZone)
                        .filter(EnergyZone.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
                # Проверяем уникальность number при создании
                dup_full = (apply_version_filter(EnergyZone.query, EnergyZone)
                        .filter(EnergyZone.number == number)
                        .with_for_update().first())
                if dup_full:
                    raise ValueError(f"Запись с полным наименованием «{number}» уже существует.")

                # Создаем новую запись
                obj = EnergyZone(
                    name=name,
                    number=number or None,
                )
                set_db_version_on_create(obj)
                db.session.add(obj)
                db.session.flush()  # получить id без полного коммита

                log_to_db(
                    user, 
                    "Создана энергозона",
                    (
                        f"Номер: {_dash(number)};"
                        f"Наименование: {name}. "
                    ),
                    entity_type="energy_zone", 
                    entity_id=obj.id)

    try:
        _do_insert()
        _commit_with_retry()
        return None

    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "energy_zones")
        _do_insert()
        _commit_with_retry()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, "Ошибка сохранения новой энергозоны", 
            str(e), 
            entity_type="energy_zone")
        raise ValueError(f"Ошибка сохранения новой энергозоны: {e}")


@no_autoflush
def delete_energy_zone_service(ids, user):
    """Удаляет записи энергозон по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")

    log_to_db(
        user, 
        "Удаление списка энергозон", 
        f"Переданы ID для удаления: {ids}",
        entity_type="energy_zone")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for ues_id in ids:
        try:
            energy_zone_id = _to_int_or_none(ues_id, keep_zero=False)
        except (TypeError, ValueError):
            invalid.append(ues_id)
            log_to_db(
                user, 
                "Ошибка удаления энергозон", 
                f"Некорректный ID: {ues_id}",
                entity_type="energy_zone",
                entity_id=ues_id)
            continue

        obj = _locked_get(EnergyZone, energy_zone_id)
        if obj:
            db.session.delete(obj)
            deleted_names.append(get_energy_zone_name(energy_zone_id))
            successful_deletes += 1
            log_to_db(
                user, 
                "Удалена энергозона", 
                f"{get_energy_zone_name(energy_zone_id)}",
                entity_type="energy_zone", 
                entity_id=energy_zone_id    ) 
        else:
            not_found.append(energy_zone_id)
            log_to_db(
                user, 
                "Ошибка удаления энергозоны", 
                f"Энергозона с ID={energy_zone_id} не найдена.",
                entity_type="energy_zone",
                entity_id=energy_zone_id)

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
            "Ошибка удаления энергозон", 
            str(e), 
            entity_type="energy_zone",
            entity_id=energy_zone_id)
        raise ValueError(f"Ошибка при удалении данных.")


def export_energy_zone_service(
        user, 
        sort_by="id", 
        sort_dir="asc",
        energy_zone_filter=None,
        ):
    """ Экспортирует данные списка энергозон в Excel. """

    log_to_db(user, "Начата выгрузка таблицы энергозон. Параметры экспорта", 
            (
                f"Фильтр по столбцу: Наименование/номер энергозоны = {get_energy_zone_name(energy_zone_filter)},"
                f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
            ),
        entity_type="energy_zone")
    
    # Базовый запрос
    query = energy_zone_query(
        energy_zone_filter=energy_zone_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(
        user, 
        "Получение данных завершено", 
        f"Найдено записей: {len(items)}", 
        entity_type="energy_zone")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Номер энергозоны": _dash(o.number),
            "Наименование энергозоны": _dash(o.name),
        })

    log_to_db(
        user, 
        "Подготовка данных для экспорта таблицы энергозон в Excel", 
        f"Записей для экспорта: {len(data)}",
        entity_type="energy_zone")

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)
    
    # Создание Excel-файла
    output = BytesIO()
    sheet_name = "Энергозоны"
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
        "Экспорт таблицы энергозон в Excel завершен", 
        f"Экспортировано записей: {len(data)}",
        entity_type="energy_zone")

    return output