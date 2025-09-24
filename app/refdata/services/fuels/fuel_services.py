"""Сервисный модуль: Типы топлива."""

from app.extensions import db
from sqlalchemy import or_, text
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 

# Модели
from app.refdata.models.fuels.fuel_model import Fuel
from app.refdata.models.fuels.fuel_type_model import FuelType

# Сервисы
from app.common.services.get_services.fuels.fuel_type_get_services import (
    get_fuel_type_name,
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


def fuel_query(
    fuel_filter=None,
    fuel_type_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """Базовый запрос для выборки топлива с фильтрацией и сортировкой."""

    # Валидация сортировки
    allowed_sort_by = {"id", "name", "fuel_type"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Безопасная конвертация ID-фильтров
    fuel_type_id = _to_int_or_none(fuel_type_filter)

    # Базовый запрос
    query = Fuel.query.filter(Fuel.id > 0)

    # Фильтрация
    need_join = False
    ff = (fuel_filter or "").strip()
    if ff:
        need_join = True
        query = query.outerjoin(FuelType, Fuel.id_fuel_type == FuelType.id)
        query = query.filter(or_(
            Fuel.name.ilike(f"%{ff}%"),
            FuelType.name.ilike(f"%{ff}%"),
        ))

    # Фильтр по конкретному типу топлива (id)
    if fuel_type_id is not None:
        query = query.filter(Fuel.id_fuel_type == fuel_type_id)

    # Сортировка
    if sort_by == "name":
        sort_col = Fuel.name
    elif sort_by == "fuel_type":
        if not ff:
            query = query.outerjoin(FuelType, Fuel.id_fuel_type == FuelType.id)
        sort_col = FuelType.name
    else:
        sort_col = Fuel.id

    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    return query


@no_autoflush
def get_fuel_list(
    page, 
    per_page, 
    fuel_filter=None, 
    fuel_type_filter=None, 
    sort_by="id", 
    sort_dir="asc"):
    """ Получает список типов топлива с пагинацией, фильтрацией и сортировкой. """

    # Базовый запрос
    query = fuel_query(
        fuel_filter=fuel_filter,
        fuel_type_filter=fuel_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_fuel_service(data, user):
    """ Обновление данных по типам топлива """

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []
    
    log_to_db(user, "Получены данные для обновления списка типов топлива", 
              f"{data}")
    
    with db.session.no_autoflush:
        for record in data:
            fuel_id = record.get("fuel_id")
            name = (record.get("name") or "").strip()
            fuel_type_id = _to_int_or_none(record.get("fuel_type_id"), keep_zero=False)

            # Проверки на валидность данных
            if not name:
                raise ValueError(f"Поле 'name' обязательно для заполнения.")

            obj = db.session.get(Fuel, fuel_id)
            if not obj:
                log_to_db(user, "Ошибка валидации", 
                          f"Запись: {record}")
                raise ValueError(f"Запись с ID «{fuel_id}» не найдена.")

            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (Fuel.query
                     .filter(Fuel.name == name,
                             Fuel.id != fuel_id))
                if q.first():
                    raise ValueError(f"Запись с именем «{name}» уже существует.")

            changes = {}

            if name != (obj.name or ""):
                changes["Наименование"] = f"{_dash(obj.name)} → {name}"
                obj.name = name

            # Проверка наличия вида топлива
            if "fuel_type_id" in record:
                new_val = _to_int_or_none(record.get("fuel_type_id"), keep_zero=False)
                if new_val != obj.id_fuel_type:
                    new_obj = db.session.get(FuelType, new_val) if new_val is not None else None
                    if new_val is not None and not new_obj:
                        raise ValueError(f"Вид топлива с id={new_val} не найден.")
                    
                    prev_obj = db.session.get(FuelType, obj.id_fuel_type) if obj.id_fuel_type else None
                    changes["Вид топлива"] = f"{_dash(prev_obj.name if prev_obj else None)} → {_dash(new_obj.name if new_obj else None)}"
                    obj.id_fuel_type = new_val

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(user, f"Обновлен тип топлива: {name}", f"Изменения = {changes}")
                updated_ids.append(fuel_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(user, "Сохранены изменения по типам топлива", f"Измененных записей: {len(updated_ids)} (id: {updated_ids})")
        else:
            log_to_db(user, "Изменений по типам топлива не обнаружено", "")
            
        return updated_ids
    
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения типов топлива (уникальность/целостность)", str(e))
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка при сохранении типов топлива", str(e))
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_fuel_service(data, user):
    """Создание новой записи: тип топлива"""

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    try:
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                name = (record.get("name") or "").strip()
                fuel_type_id = _to_int_or_none(record.get("fuel_type_id"), keep_zero=False)

                if not name and not fuel_type_id:
                    log_to_db(user, "Ошибка валидации", 
                              f"Запись: {record}")
                    raise ValueError(f"Каждая запись должна содержать 'name' и 'fuel_type_id'. Данные: {record}")

                # Проверяем существование вида топлива
                obj = db.session.get(FuelType, fuel_type_id)
                if not obj:
                    raise ValueError(f"Вид топлива с id={fuel_type_id} не найден.")

                # Проверяем уникальность name
                dup = (Fuel.query
                        .filter(Fuel.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
                # Создаем новую запись
                obj = Fuel(
                    name=name,
                    id_fuel_type=fuel_type_id,
                )
                db.session.add(obj)
                db.session.flush()  # получить id без полного коммита

                log_to_db(
                    user,
                    "Создан тип топлива",
                    f"Наименование: {name};"
                    f"Вид топлива: {get_fuel_type_name(fuel_type_id)} "
                )

        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        return None

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения нового типа топлива. Возможно, нарушены уникальные ограничения или внешние ключи.", str(e))
        raise ValueError(f"Ошибка сохранения нового типа топлива. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения нового вида топлива", str(e))
        raise ValueError(f"Ошибка сохранения нового вида топлива: {e}")


@no_autoflush
def delete_fuel_service(ids, user):
    """Удаляет записи типов топлива по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")

    log_to_db(user, "Удаление типов топлива", 
              f"Переданы ID для удаления: {ids}")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for rd_id in ids:
        try:
            fuel_id = int(rd_id)
        except (TypeError, ValueError):
            invalid.append(rd_id)
            log_to_db(user, "Ошибка удаления типов топлива", 
                      f"Некорректный ID: {rd_id}")
            continue

        obj = _locked_get(Fuel, fuel_id)
        if obj:
            name = obj.name or f"ID={fuel_id}"
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            log_to_db(user, "Удален тип топлива", f"{name}")
        else:
            not_found.append(fuel_id)
            log_to_db(user, "Ошибка удаления типов топлива", 
                      f"Тип топлива с ID={fuel_id} не найден.")

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

        log_to_db(user, "Результат удаления типов топлива", "; ".join(parts))

        return {
            "deleted": successful_deletes,
            "deleted_names": deleted_names,
            "not_found": not_found,
            "invalid": invalid,
        }
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления типов топлива", str(e))
        raise ValueError(f"Ошибка при удалении данных.")


@no_autoflush
def import_fuel_service(file, user):
    """Импортирует данные типов топлива из Excel-файла в базу данных."""

    try:
        data = pd.read_excel(file)

        if 'name' not in data.columns or 'id_fuel_type' not in data.columns:
            raise ValueError(f"Неверный формат файла. Отсутствуют необходимые столбцы.")

        db.session.query(Fuel).delete()
        db.session.commit()

        db.session.execute(text("ALTER TABLE fuel AUTO_INCREMENT = 1"))
        db.session.commit()

        records = [Fuel(name=row['name'], id_fuel_type=row['id_fuel_type']) for _, row in data.iterrows()]
        db.session.bulk_save_objects(records)
        db.session.commit()

        log_to_db(user, "Импорт завершен", f"Импортировано записей: {len(records)}")
        return len(records)
    except Exception as e:
        log_to_db(user, "Ошибка импорта", str(e))
        raise ValueError(f"Ошибка при импорте данных: {e}")


def export_fuel_service(
    user,
    fuel_filter=None,
    fuel_type_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """ Экспортирует данные типов топлива в Excel. """

    log_to_db(user, "Начата выгрузка таблицы типов топлива из базы данных")
    log_to_db(user, "Параметры экспорта",
        (
            f"Фильтр по столбцу: Наименование типа топлива = {fuel_filter},"
            f"Фильтр по столбцу: Вид топлива = {get_fuel_type_name(fuel_type_filter)},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        ),
    )

    # Базовый запрос
    query = fuel_query(
        fuel_filter=fuel_filter,
        fuel_type_filter=fuel_type_filter,
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
            "№": idx,
            "Наименование": _dash(o.name),
            "Вид топлива": getattr(o.fuel_type, "name", "Не указан") or "Не указан",
        })

    log_to_db(user, "Подготовка данных для экспорта таблицы типов топлива в Excel",
              f"Записей для экспорта: {len(data)}")

    df = pd.DataFrame(data)

    # Создание Excel и авто-ширина столбцов
    output = BytesIO()
    sheet_name = "Типы топлива"
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]

        # Автоподбор ширины с аккуратным лимитом
        for i, col in enumerate(df.columns):
            max_len = max(len(str(col)), *(len(str(v)) for v in df[col].values)) if not df.empty else len(str(col))
            ws.set_column(i, i, min(max_len + 2, 60))

    output.seek(0)
    log_to_db(user, "Экспорт таблицы типов топлива в Excel завершен", f"Экспортировано записей: {len(data)}")
    return output