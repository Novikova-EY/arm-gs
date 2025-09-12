"""Сервисный модуль: Синхронные зоны."""

from app.extensions import db
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 

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
)

# Логирование
from app.logs.services.logging_service import log_to_db


def synchronous_area_query(
    synchronous_area_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """ Базовый запрос для выборки частей энергосистемы России с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id","name"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Базовый запрос
    query = SynchronousArea.query

    # Фильтрация
    if synchronous_area_filter:
        query = query.filter(
            or_(
                SynchronousArea.name.ilike(f"%{synchronous_area_filter}%"),
            )
        )

    # Сортировка
    if sort_by in ["name"]:
        sort_field = getattr(SynchronousArea, sort_by)
        query = query.order_by(sort_field.desc() if sort_dir == "desc" else sort_field.asc())

    else:
        query = query.order_by(SynchronousArea.id.desc() if sort_dir == "desc" else SynchronousArea.id.asc())

    # Исключаем запись "Не указано" (id=0)
    query = query.filter(SynchronousArea.id.isnot(None), SynchronousArea.id > 0)

    return query


@no_autoflush
def get_synchronous_area_list(
    page, 
    per_page, 
    synchronous_area_filter=None, 
    sort_by="id", 
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
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []

    log_to_db(user, "Получены данные для обновления списка синхронных зон", 
              f"{data}")

    with db.session.no_autoflush:
        for record in data:
            synchronous_area_id = record.get("synchronous_area_id")
            number = record.get("number")
            name = record.get("name")

            # Проверки на валидность данных
            if not name or not number:
                log_to_db(user, "Ошибка валидации", 
                          f"Запись: {record}")
                raise ValueError("Каждая запись должна содержать 'name', 'name_full'. Данные: {record}")

            obj = db.session.get(SynchronousArea, synchronous_area_id)
            if not obj:
                raise ValueError(f"Запись с ID «{synchronous_area_id}» не найдена.")
            
            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (SynchronousArea.query
                     .filter(SynchronousArea.name == name,
                             SynchronousArea.id != synchronous_area_id))
                if q.first():
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")

            # Проверка уникальности number
            if number != (obj.number or ""):
                q = (SynchronousArea.query
                     .filter(SynchronousArea.number == number,
                             SynchronousArea.id != synchronous_area_id))
                if q.first():
                    raise ValueError(f"Запись с номером «{number}» уже существует.")

            changes = {}
                
            if name != (obj.name or ""):
                changes["Наименование"] = f"{_dash(obj.name)} → {name}"
                obj.name = name

            if number != (obj.number or ""):
                changes["Номер"] = f"{_dash(obj.number)} → {number}"
                obj.number = number

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(user, f"Обновлена синхронная зона: {name}", 
                          f"Изменения = {changes}")
                updated_ids.append(synchronous_area_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(user, "Сохранены изменения по синхронным зонам", 
                      f"Измененных записей: {len(updated_ids)} (id: {updated_ids})")
        else:
            log_to_db(user, "Изменений по синхронным зонам не обнаружено", "")
            
        return updated_ids

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения синхронных зон (уникальность/целостность)", str(e))
        raise ValueError("Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка при сохранении синхронных зон", str(e))
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")

        
@no_autoflush
def add_synchronous_area_service(data, user):
    """ Создание новой записи: синхронная зона """

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
                    log_to_db(user, "Ошибка валидации", 
                              f"Запись: {record}")
                    raise ValueError("Каждая запись должна содержать 'number', 'name' и 'regional_district_id'.")

                # Проверяем существование субъекта РФ
                obj = db.session.get(RegionalDistrict, regional_district_id)
                if not obj:
                    raise ValueError(f"Субъект РФ с id={regional_district_id} не найден.")
                
                # Проверяем уникальность name при создании
                dup = (SynchronousArea.query
                        .filter(SynchronousArea.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
                # Проверяем уникальность number при создании
                dup_full = (SynchronousArea.query
                        .filter(SynchronousArea.number == number)
                        .with_for_update().first())
                if dup_full:
                    raise ValueError(f"Запись с полным наименованием «{number}» уже существует.")

                # Создаем новую запись
                obj = SynchronousArea(
                    name=name,
                    number=number or None,
                    id_regional_district=regional_district_id,
                )
                db.session.add(obj)
                db.session.flush()  # получить id без полного коммита

                log_to_db(user, "Создана синхронная зона",
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
        log_to_db(user, "Ошибка сохранения новой синхронной зоны. Возможно, нарушены уникальные ограничения или внешние ключи.", str(e))
        raise ValueError("Ошибка сохранения новой синхронной зоны. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения новой синхронной зоны", str(e))
        raise ValueError(f"Ошибка сохранения новой синхронной зоны: {e}")
    

@no_autoflush
def delete_synchronous_area_service(ids, user):
    """Удаляет записи синхронных зон по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError("Не переданы ID для удаления.")

    log_to_db(user, "Удаление списка синхронных зон", f"Переданы ID для удаления: {ids}")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for sz_id in ids:
        try:
            synchronous_area_id = _to_int_or_none(sz_id, keep_zero=False)
        except (TypeError, ValueError):
            invalid.append(sz_id)
            log_to_db(user, "Ошибка удаления синхронной зоны", f"Некорректный ID: {sz_id}")
            continue

        obj = _locked_get(SynchronousArea, synchronous_area_id)
        if obj:
            db.session.delete(obj)
            deleted_names.append(get_synchronous_area_name(synchronous_area_id))
            successful_deletes += 1
            log_to_db(user, "Удалена синхронная зона", 
                      f"{get_synchronous_area_name(synchronous_area_id)}")
        else:
            not_found.append(synchronous_area_id)
            log_to_db(user, "Ошибка удаления синхронной зоны", 
                      f"Синхронная зона с ID={synchronous_area_id} не найдена.")

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

        log_to_db(user, "Результат удаления синхронных зон", "; ".join(parts))

        return {
            "deleted": successful_deletes,
            "deleted_names": deleted_names,
            "not_found": not_found,
            "invalid": invalid,
        }
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления синхронных зон", str(e))
        raise ValueError("Ошибка при удалении данных.")
    

def export_synchronous_area_service(
        user, 
        synchronous_area_filter=None, 
        sort_by="id", 
        sort_dir="asc"):
    """ Экспортирует данные списка синхронных зон в Excel. """

    log_to_db(user, "Начата выгрузка таблицы синхронных зон из базы данных")
    log_to_db(user, "Параметры экспорта", 
            (
                f"Фильтр по столбцу: Наименование синхронной зоны = {synchronous_area_filter},"
                f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
            ),
    )
    
    # Базовый запрос
    query = synchronous_area_query(
        synchronous_area_filter=synchronous_area_filter,
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
            "Наименование синхронной зоны": _dash(o.name),
        })

    log_to_db(user, "Подготовка данных для экспорта таблицы синхронных зон в Excel", 
              f"Записей для экспорта: {len(data)}")

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
    log_to_db(user, "Экспорт таблицы синхронных зон в Excel завершён", 
              f"Экспортировано записей: {len(data)}")

    return output

