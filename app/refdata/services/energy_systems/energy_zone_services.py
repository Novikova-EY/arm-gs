"""Сервисный модуль: Энергозоны."""

from app.extensions import db
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 

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
)

# Логирование
from app.logs.services.logging_service import log_to_db


def energy_zone_query(
    energy_zone_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """ Базовый запрос для выборки списка энергозон с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id", "name"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Базовый запрос
    query = EnergyZone.query

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
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []

    log_to_db(user, "Получены данные для обновления списка энергозон", 
              f"{data}")

    with db.session.no_autoflush:
        for record in data:
            energy_zone_id = record.get("energy_zone_id")
            number = record.get("number")
            name = record.get("name")
            regional_district_id = _to_int_or_none(record.get("regional_district_id"), keep_zero=False)

            # Проверки на валидность данных
            if not name or not number or not regional_district_id:
                log_to_db(user, "Ошибка валидации", 
                          f"Запись: {record}")
                raise ValueError("Каждая запись должна содержать 'name', 'name_full' и 'regional_district_id'. Данные: {record}")

            obj = db.session.get(EnergyZone, energy_zone_id)
            if not obj:
                raise ValueError(f"Запись с ID «{energy_zone_id}» не найдена.")
            
            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (EnergyZone.query
                     .filter(EnergyZone.name == name,
                             EnergyZone.id != energy_zone_id))
                if q.first():
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
            # Проверка уникальности number
            if number != (obj.number or ""):
                q_full = (EnergyZone.query
                     .filter(EnergyZone.number == number,
                             EnergyZone.id != energy_zone_id))
                if q_full.first():
                    raise ValueError(f"Запись с номером «{number}» уже существует.")

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

            changes = {}

            if name != (obj.name or ""):
                changes["Наименование"] = f"{_dash(obj.name)} → {name}"
                obj.name = name

            if number != (obj.number or ""):
                changes["Номер"] = f"{_dash(obj.number)} → {number}"
                obj.number = number

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(user, f"Обновлена энергозона: {name}", 
                          f"Изменения = {changes}")
                updated_ids.append(energy_zone_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(user, "Сохранены изменения по энергозонам", 
                      f"Измененных записей: {len(updated_ids)} (id: {updated_ids})")
        else:
            log_to_db(user, "Изменений по энергозонам не обнаружено", "")
            
        return updated_ids

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения энергозон (уникальность/целостность)", str(e))
        raise ValueError("Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка при сохранении энергозон", str(e))
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_energy_zone_service(data, user):
    """ Создание новой записи: энергозона """

    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    try:
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                number = (record.get("number") or "").strip()
                name = (record.get("name") or "").strip()
                regional_district_id = _to_int_or_none(record.get("regional_district_id"), keep_zero=False)

                # Проверка на наличие необходимых данных
                if not name or not number or not regional_district_id:
                    log_to_db(user, "Ошибка валидации", f"Запись: {record}")
                    raise ValueError("Каждая запись должна содержать 'number', 'name' и 'regional_district_id'.")

                # Проверяем существование субъекта РФ
                obj = db.session.get(RegionalDistrict, regional_district_id)
                if not obj:
                    raise ValueError(f"Субъект РФ с id={regional_district_id} не найден.")
                
                # Проверяем уникальность name при создании
                dup = (EnergyZone.query
                        .filter(EnergyZone.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
                # Проверяем уникальность number при создании
                dup_full = (EnergyZone.query
                        .filter(EnergyZone.number == number)
                        .with_for_update().first())
                if dup_full:
                    raise ValueError(f"Запись с полным наименованием «{number}» уже существует.")

                # Создаем новую запись
                obj = EnergyZone(
                    name=name,
                    number=number or None,
                    id_regional_district=regional_district_id,
                )
                db.session.add(obj)
                db.session.flush()  # получить id без полного коммита

                log_to_db(user, "Создана энергозона",
                    (
                        f"Номер: {_dash(number)};"
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
        log_to_db(user, "Ошибка сохранения новой энергозоны. Возможно, нарушены уникальные ограничения или внешние ключи.", str(e))
        raise ValueError("Ошибка сохранения новой энергозоны. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения новой энергозоны", str(e))
        raise ValueError(f"Ошибка сохранения новой энергозоны: {e}")


@no_autoflush
def delete_energy_zone_service(ids, user):
    """Удаляет записи энергозон по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError("Не переданы ID для удаления.")

    log_to_db(user, "Удаление списка энергозон", 
              f"Переданы ID для удаления: {ids}")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for ues_id in ids:
        try:
            energy_zone_id = _to_int_or_none(ues_id, keep_zero=False)
        except (TypeError, ValueError):
            invalid.append(ues_id)
            log_to_db(user, "Ошибка удаления энергозон", 
                      f"Некорректный ID: {ues_id}")
            continue

        obj = _locked_get(EnergyZone, energy_zone_id)
        if obj:
            db.session.delete(obj)
            deleted_names.append(get_energy_zone_name(energy_zone_id))
            successful_deletes += 1
            log_to_db(user, "Удалена энергозона", 
                      f"{get_energy_zone_name(energy_zone_id)}")
        else:
            not_found.append(energy_zone_id)
            log_to_db(user, "Ошибка удаления энергозоны", 
                      f"Энергозона с ID={energy_zone_id} не найдена.")

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

        log_to_db(user, "Результат удаления энергозон", "; ".join(parts))

        return {
            "deleted": successful_deletes,
            "deleted_names": deleted_names,
            "not_found": not_found,
            "invalid": invalid,
        }
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления энергозон", str(e))
        raise ValueError("Ошибка при удалении данных.")


def export_energy_zone_service(
        user, 
        energy_zone_filter=None,
        sort_by="id", 
        sort_dir="asc"):
    """ Экспортирует данные списка энергозон в Excel. """

    log_to_db(user, "Начата выгрузка таблицы энергозон из базы данных")
    log_to_db(user, "Параметры экспорта", 
            (
                f"Фильтр по столбцу: Наименование/номер энергозоны = {get_energy_zone_name(energy_zone_filter)},"
                f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
            ),
    )
    
    # Базовый запрос
    query = energy_zone_query(
        energy_zone_filter=energy_zone_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(user, "Получение данных завершено", f"Найдено записей: {len(items)}")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx + 1,
            "Номер энергозоны": _dash(o.number),
            "Наименование энергозоны": _dash(o.name),
        })

    log_to_db(user, "Подготовка данных для экспорта таблицы энергозон в Excel", 
              f"Записей для экспорта: {len(data)}")

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
    log_to_db(user, "Экспорт таблицы энергозон в Excel завершён", 
              f"Экспортировано записей: {len(data)}")

    return output

