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
from app.refdata.services.common_services.help_services import (
    _dash,
    _to_int_or_none,
)
from app.refdata.services.common_services.tranzaction_services import (
    _commit_with_retry,
    _locked_get,
    no_autoflush,
)

# Логирование
from app.logs.services.logging_service import log_to_db

@no_autoflush
def get_fuel_list(
    page, 
    per_page, 
    fuel_filter=None, 
    fuel_type_filter=None, 
    sort_by="id", 
    sort_dir="asc"):
    """Получает список типов топлива с пагинацией, фильтрацией и сортировкой."""

    # Валидация сортировки
    allowed_sort_by = {"id","name","fuel_type"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Безопасная конвертация ID-фильтров
    fuel_type_id = _to_int_or_none(fuel_type_filter)

    # Базовый запрос
    query = (
        Fuel.query
        .filter(Fuel.id.isnot(None), Fuel.id > 0)
    )

    # Фильтрация
    ff = (fuel_filter or "").strip()
    if ff:
        query = query.outerjoin(FuelType, Fuel.id_fuel_type == FuelType.id)
        query = query.filter(or_(
            Fuel.name.ilike(f"%{ff}%"),
            FuelType.name.ilike(f"%{ff}%"),
        ))

    if fuel_type_id is not None:
        query = query.filter(Fuel.id_fuel_type == fuel_type_id)
    
    # Сортировка
    if sort_by == "name":
        sort_col = Fuel.name
        query = query.order_by(sort_col.name.desc() if sort_dir == "desc" else sort_col.name.asc())

    elif sort_by == "fuel_type":
        query = query.join(FuelType, isouter=True)
        sort_col = FuelType.name
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    else: # "id" (по умолчанию)
        sort_col = Fuel.id
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else Fuel.id.asc())

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_fuel_service(data, user):
    """ Обновление данных по типам топлива """

    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []
    
    # Итерация по входным данным (валидация/применение)
    with db.session.no_autoflush:
        for record in data:
            fuel_id = record.get("id")
            name = (record.get("name") or "").strip()
            id_fuel_type = _to_int_or_none(record.get("id_fuel_type"), keep_zero=False)

            if not name:
                raise ValueError("Поле 'name' обязательно для заполнения.")

            obj = db.session.get(Fuel, fuel_id)
            if not obj:
                raise ValueError(f"Запись с ID «{fuel_id}» не найдена.")

            # Проверка уникальности name только если меняется
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

            # Вид топлива (если ключ присутствует во входе)
            if "id_fuel_type" in record:
                new_ft_id = _to_int_or_none(record.get("id_fuel_type"), keep_zero=False)
                if new_ft_id != obj.id_fuel_type:
                    new_fd = db.session.get(FuelType, new_ft_id) if new_ft_id is not None else None
                    if new_ft_id is not None and not new_fd:
                        raise ValueError(f"Федеральный округ с id={new_ft_id} не найден.")
                    prev_ft = db.session.get(FuelType, obj.id_fuel_type) if obj.id_fuel_type else None
                    changes["Вид топлива"] = f"{_dash(prev_ft.name if prev_ft else None)} → {_dash(new_fd.name if new_fd else None)}"
                    obj.id_fuel_type = new_ft_id

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
        raise ValueError("Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка при сохранении типов топлива", str(e))
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_fuel_service(data, user):
    """Создание/обновление типов топлива"""

    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    log_to_db(user, "Получены данные для добавления/обновления типов топлива", f"Кол-во записей: {len(data)}")

    created_ids = []
    updated_count = 0

    try:
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                fuel_id = record.get("id")
                name = (record.get("name") or "").strip()
                id_fuel_type = _to_int_or_none(record.get("id_fuel_type"), keep_zero=False)

                if not name and not id_fuel_type:
                    log_to_db(user, "Ошибка валидации", f"Запись: {record}")
                    raise ValueError("Каждая запись должна содержать 'name' и 'id_fuel_type'.")

                # Проверяем существование вида топлива
                ft_obj = db.session.get(FuelType, id_fuel_type)
                if not ft_obj:
                    raise ValueError(f"Вид топлива с id={id_fuel_type} не найден.")
                ft_name = ft_obj.name

                #----- ОБНОВЛЕНИЕ-----
                if fuel_id:
                    obj = _locked_get(Fuel, fuel_id)
                    if not obj:
                        log_to_db(user, "Ошибка обновления типа топлива", f"Запись с ID={fuel_id} не найдена")
                        raise ValueError(f"Запись с ID {fuel_id} не найдена.")

                    # Уникальность name — только если меняется
                    if (obj.name or "") != name:
                        dup = (Fuel.query
                               .filter(Fuel.name == name,
                                       Fuel.id != fuel_id)
                               .with_for_update().first())
                        if dup:
                            raise ValueError(f"Запись с именем «{name}» уже существует.")

                    изменения = {}

                    if (obj.name or "") != name:
                        изменения["Наименование"] = f"{_dash(obj.name)} → {name}"
                        obj.name = name

                    if obj.id_fuel_type != id_fuel_type:
                        prev_fd = db.session.get(FuelType, obj.id_fuel_type) if obj.id_fuel_type else None
                        prev_ft_name = prev_fd.name if prev_fd else "—"
                        изменения["Вид топлива"] = f"{prev_ft_name} → {ft_name}"
                        obj.id_fuel_type = id_fuel_type

                    if изменения:
                        updated_count += 1
                        log_to_db(user, "Обновлен тип топлива", f"Наименование = {name}. Изменения = {изменения}")

                #----- СОЗДАНИЕ-----
                else:
                    # Уникальность name при создании
                    dup = (Fuel.query
                           .filter(Fuel.name == name)
                           .with_for_update().first())
                    if dup:
                        raise ValueError(f"Запись с именем «{name}» уже существует.")

                    obj = Fuel(
                        name=name,
                        id_fuel_type=id_fuel_type,
                    )
                    db.session.add(obj)
                    db.session.flush()  # получить id без полного коммита
                    created_ids.append(obj.id)

                    log_to_db(
                        user,
                        "Создан тип топлива",
                        f"Наименование: {name}; Вид топлива: {ft_name}"
                    )

        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        # Итоговый лог
        tail = []
        if created_ids:
            tail.append(f"создано: {len(created_ids)} (id: {created_ids})")
        if updated_count:
            tail.append(f"обновлено: {updated_count}")
        log_to_db(user, "Сохранение типов топлива завершено", "; ".join(tail) or "Изменений нет")

        if len(created_ids) == 1:
            return created_ids[0]
        if created_ids:
            return created_ids
        return None

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения типов топлива (уникальность/целостность)", str(e))
        raise ValueError("Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения типов топлива", str(e))
        raise ValueError(f"Ошибка при добавлении/обновлении записей: {e}")


@no_autoflush
def delete_fuel_service(ids, user):
    """Удаляет записи типов топлива по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError("Не переданы ID для удаления.")

    log_to_db(user, "Удаление типов топлива", f"Переданы ID для удаления: {ids}")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for rd_id in ids:
        try:
            fuel_id = int(rd_id)
        except (TypeError, ValueError):
            invalid.append(rd_id)
            log_to_db(user, "Ошибка удаления типов топлива", f"Некорректный ID: {rd_id}")
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
            log_to_db(user, "Ошибка удаления типов топлива", f"Тип топлива с ID={fuel_id} не найден.")

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
        raise ValueError("Ошибка при удалении данных.")


@no_autoflush
def import_fuel_service(file, user):
    """Импортирует данные типов топлива из Excel-файла в базу данных."""

    try:
        data = pd.read_excel(file)

        if 'name' not in data.columns or 'id_fuel_type' not in data.columns:
            raise ValueError("Неверный формат файла. Отсутствуют необходимые столбцы.")

        db.session.query(Fuel).delete()
        db.session.commit()

        db.session.execute(text("ALTER TABLE fuel AUTO_INCREMENT = 1"))
        db.session.commit()

        records = [Fuel(name=row['name'], id_fuel_type=row['id_fuel_type']) for _, row in data.iterrows()]
        db.session.bulk_save_objects(records)
        db.session.commit()

        log_to_db(user, "Импорт завершён", f"Импортировано записей: {len(records)}")
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
    """ Экспортирует данные типов топлива в Excel и возвращает BytesIO. """

    # Нормализация входов
    sort_dir = "desc" if (sort_dir or "").lower() == "desc" else "asc"
    sort_by = (sort_by or "id").lower()
    allowed_sort = {"id", "name", "fuel_type"}
    if sort_by not in allowed_sort:
        sort_by = "id"

    fuel_type_id = _to_int_or_none(fuel_type_filter)
    ff = (fuel_filter or "").strip()

    log_to_db(user, "Начата выгрузка таблицы типов топлива из базы данных")
    log_to_db(
        user,
        "Параметры экспорта",
        (
            f"fuel_filter={ff!r}, "
            f"fuel_type_id={fuel_type_id}, "
            f"sort_by={sort_by}, sort_dir={sort_dir}"
        ),
    )

    # Базовый запрос
    query = (
        Fuel.query
        .filter(Fuel.id.isnot(None), Fuel.id > 0)
    )

    # Фильтрация
    ff = (fuel_filter or "").strip()
    if ff:
        query = query.outerjoin(FuelType, Fuel.id_fuel_type == FuelType.id)
        query = query.filter(or_(
            Fuel.name.ilike(f"%{ff}%"),
            FuelType.name.ilike(f"%{ff}%"),
        ))

    if fuel_type_id is not None:
        query = query.filter(Fuel.id_fuel_type == fuel_type_id)
    
    # Сортировка
    if sort_by == "name":
        sort_col = Fuel.name
        query = query.order_by(sort_col.name.desc() if sort_dir == "desc" else sort_col.name.asc())

    elif sort_by == "fuel_type":
        query = query.join(FuelType, isouter=True)
        sort_col = FuelType.name
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    else: # "id" (по умолчанию)
        sort_col = Fuel.id
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else Fuel.id.asc())

    items = query.all()

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Наименование": o.name or "",
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