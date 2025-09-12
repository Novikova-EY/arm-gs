"""Сервисный модуль: Виды топлива."""

from app.extensions import db
from sqlalchemy import or_, text
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 

# Модели
from app.refdata.models.fuels.fuel_type_model import FuelType

# Сервисы
from app.common.services.help_services import (
    _dash,
    _clean_name,
)
from app.common.services.tranzaction_services import (
    _commit_with_retry,
    _locked_get,
    no_autoflush,
)

# Логирование
from app.logs.services.logging_service import log_to_db


def get_fuel_type_query(
        fuel_type_filter=None, 
        sort_by="id", 
        sort_dir="asc"
):
    """ Базовый запрос для выборки видов топлива с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id","name"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Базовый запрос
    query = (
        FuelType.query
        .filter(FuelType.id.isnot(None), FuelType.id > 0)
    )
    
    # Фильтрация
    if fuel_type_filter:
        query = query.filter(FuelType.name.ilike(f"%{fuel_type_filter}%"))

    # Сортировка
    if sort_by == "name":
        sort_col = FuelType.name
        query = query.order_by(sort_col.name.desc() if sort_dir == "desc" else sort_col.name.asc())

    else: # сортировка по id
        sort_col = FuelType.id
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else FuelType.id.asc())

    # Исключаем запись "Не указано" (id=0)
    query = query.filter(FuelType.id.isnot(None), FuelType.id > 0)

    return query


@no_autoflush
def get_fuel_type_list(
    page, 
    per_page, 
    fuel_type_filter=None, 
    sort_by="id", 
    sort_dir="asc"):
    """ Получает список видов топлива с пагинацией, фильтрацией и сортировкой. """
    
    # Базовый запрос
    query = get_fuel_type_query(
        fuel_type_filter=fuel_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_fuel_type_service(data, user):
    """ Обновление данных по видам топлива """

    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []
    
    log_to_db(user, "Получены данные для обновления списка видов топлива", 
              f"{data}")
    
    # Проверки на валидность данных
    with db.session.no_autoflush:
        for record in data:
            fuel_type_id = record.get("fuel_type_id")
            name = (record.get("name") or "").strip()

            if not name:
                log_to_db(user, "Ошибка валидации", 
                          f"Запись: {record}")
                raise ValueError("Поле 'name' обязательно для заполнения.")

            obj = db.session.get(FuelType, fuel_type_id)
            if not obj:
                log_to_db(user, "Ошибка валидации", 
                          f"Запись с ID «{fuel_type_id}» не найдена.")
                raise ValueError(f"Запись с ID «{fuel_type_id}» не найдена.")

            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (FuelType.query
                     .filter(FuelType.name == name,
                             FuelType.id != fuel_type_id))
                if q.first():
                    raise ValueError(f"Запись с именем «{name}» уже существует.")

            changes = {}

            if name != (obj.name or ""):
                changes["Наименование"] = f"{_dash(obj.name)} → {name}"
                obj.name = name

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(user, f"Обновлен вид топлива: {name}", f"Изменения = {changes}")
                updated_ids.append(fuel_type_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(user, "Сохранены изменения по видам топлива", f"Измененных записей: {len(updated_ids)} (id: {updated_ids})")
        else:
            log_to_db(user, "Изменений по видам топлива не обнаружено", "")
            
        return updated_ids
    
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения видов топлива (уникальность/целостность)", str(e))
        raise ValueError("Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка при сохранении видов топлива", str(e))
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_fuel_type_service(data, user):
    """Создание новой записи: вид топлива"""

    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    try:
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                name = (record.get("name") or "").strip()

                if not name:
                    log_to_db(user, "Ошибка валидации", 
                              f"Запись: {record}")
                    raise ValueError("Каждая запись должна содержать 'name'. Данные: {record}")

                # Проверяем уникальность name
                dup = (FuelType.query
                        .filter(FuelType.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
                # Создаем новую запись
                obj = FuelType(
                    name=name,
                )
                db.session.add(obj)
                db.session.flush()  # получить id без полного коммита

                log_to_db(
                    user,
                    "Создан тип топлива",
                    f"Наименование: {name}"
                )

        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        return None

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения нового вида топлива. Возможно, нарушены уникальные ограничения или внешние ключи", str(e))
        raise ValueError("Ошибка сохранения нового вида топлива. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения нового вида топлива", str(e))
        raise ValueError(f"Ошибка сохранения нового вида топлива: {e}")


@no_autoflush
def delete_fuel_type_service(ids, user):
    """Удаляет записи видов топлива по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError("Не переданы ID для удаления.")

    log_to_db(user, "Удаление видов топлива", 
              f"Переданы ID для удаления: {ids}")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for ft_id in ids:
        try:
            fuel_type_id = int(ft_id)
        except (TypeError, ValueError):
            invalid.append(ft_id)
            log_to_db(user, "Ошибка удаления видов топлива", 
                      f"Некорректный ID: {ft_id}")
            continue

        obj = _locked_get(FuelType, fuel_type_id)
        if obj:
            name = obj.name or f"ID={fuel_type_id}"
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            log_to_db(user, "Удален вид топлива", f"{name}")
        else:
            not_found.append(fuel_type_id)
            log_to_db(user, "Ошибка удаления видов топлива", 
                      f"Вид топлива с ID={fuel_type_id} не найден.")

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

        log_to_db(user, "Результат удаления видов топлива", "; ".join(parts))

        return {
            "deleted": successful_deletes,
            "deleted_names": deleted_names,
            "not_found": not_found,
            "invalid": invalid,
        }
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления видов топлива", str(e))
        raise ValueError("Ошибка при удалении данных.")


@no_autoflush
def import_fuel_type_service(file, user):
    """Импортирует данные видов топлива из Excel-файла в базу данных."""

    try:
        data = pd.read_excel(file)

        if 'name' not in data.columns or 'id_fuel_type' not in data.columns:
            raise ValueError("Неверный формат файла. Отсутствуют необходимые столбцы.")

        db.session.query(FuelType).delete()
        db.session.commit()

        db.session.execute(text("ALTER TABLE fuel_types AUTO_INCREMENT = 1"))
        db.session.commit()

        records = [FuelType(name=row['name']) for _, row in data.iterrows()]
        db.session.bulk_save_objects(records)
        db.session.commit()

        log_to_db(user, "Импорт завершён", f"Импортировано записей: {len(records)}")
        return len(records)
    except Exception as e:
        log_to_db(user, "Ошибка импорта", str(e))
        raise ValueError(f"Ошибка при импорте данных: {e}")


def export_fuel_type_service(
    user,
    fuel_type_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """ Экспортирует данные видов топлива в Excel. """

    log_to_db(user, "Начата выгрузка таблицы видов топлива из базы данных")
    log_to_db(user, "Параметры экспорта",
        (
            f"Фильтр по столбцу: Наименование вида топлива = {fuel_type_filter},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        ),
    )

    # Базовый запрос
    query = get_fuel_type_query(
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
        })

    log_to_db(user, "Подготовка данных для экспорта таблицы видов топлива в Excel",
              f"Записей для экспорта: {len(data)}")

    df = pd.DataFrame(data)

    # Создание Excel и авто-ширина столбцов
    output = BytesIO()
    sheet_name = "Виды топлива"
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]

        # Автоподбор ширины с аккуратным лимитом
        for i, col in enumerate(df.columns):
            max_len = max(len(str(col)), *(len(str(v)) for v in df[col].values)) if not df.empty else len(str(col))
            ws.set_column(i, i, min(max_len + 2, 60))

    output.seek(0)
    log_to_db(user, "Экспорт таблицы видов топлива в Excel завершен", f"Экспортировано записей: {len(data)}")
    return output