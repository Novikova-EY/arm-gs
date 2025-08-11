from app.extensions import db
from app.logs.models.logs_models import Log
from app.refdata.models.fuels_models import Fuel, FuelType
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.logs.services.logging_service import log_to_db


def get_fuel_list(page, per_page, fuel_filter=None, fuel_type_filter=None, sort_by="id", sort_dir="asc"):
    """Получает список типов топлива с пагинацией, фильтрацией и сортировкой."""
    # Фильтрация
    query = Fuel.query

    if fuel_filter:
        query = query.filter(Fuel.name.ilike(f"%{fuel_filter}%"))

    if fuel_type_filter:
        query = query.filter(Fuel.id_fuel_type == fuel_type_filter)

    # Сортировка
    if sort_by == "name":
        query = query.order_by(Fuel.name.desc() if sort_dir == "desc" else Fuel.name.asc())
    elif sort_by == "fuel_type":
        query = query.join(FuelType).order_by(
            FuelType.name.desc() if sort_dir == "desc" else FuelType.name.asc()
        )
    else:
        query = query.order_by(Fuel.id.desc() if sort_dir == "desc" else Fuel.id.asc())

    # Пагинация
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return pagination


def get_fuel_types():
    """Получает список типов энергосистем."""
    return FuelType.query.all()


def update_fuel(data, user):
    """
    Обновляет записи типов топлива в базе данных.
    :param data: Список словарей с данными для обновления. Пример:
                 [{"id": 1, "name": "газ естественный природный", "fuel_type_id": 1}, ...]
    :param user: Имя пользователя, инициировавшего обновление.
    :raises ValueError: Если обнаружены ошибки в данных или сохранении.
    """
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    log_to_db(user, "Получены данные для обновления", f"{data}")

    for record in data:
        fuel_id = record.get("id")
        name = record.get("name")
        fuel_type_id = record.get("fuel_type_id")

        # Проверки на валидность данных
        if not name or not fuel_type_id:
            raise ValueError("Каждая запись должна содержать 'name' и 'fuel_type_id'.")

        if fuel_id:
            fuel = Fuel.query.get(fuel_id)

            duplicate = Fuel.query.filter(Fuel.name == name, Fuel.id != fuel_id).first()
            if duplicate:
                raise ValueError(f"Запись с именем '{name}' уже существует.")
            
            fuel.name = name
            fuel.id_fuel_type = fuel_type_id
        else:
            duplicate = Fuel.query.filter(Fuel.name == name, Fuel.id != fuel_id).first()
            if duplicate:
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            new_fuel = Fuel(name=name, id_fuel_type=fuel_type_id)
            db.session.add(new_fuel)

    # Сохранение изменений в базе данных
    try:
        db.session.commit()
        log_to_db(user, "Обновление записей типов топлива", f"Обновлено записей: {len(data)}")
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка обновления типов топлива", str(e))
        raise ValueError("Ошибка сохранения данных. Возможно, дублируются имена.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка обновления типов топлива", str(e))
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


def add_fuel(data, user):
    """
    Добавляет или обновляет записи ОЭС в базе данных.
    :param data: Список словарей с данными ОЭС. Пример:
                 [{"id": 1, "name": "газ естественный природный", "fuel_type_id": 1}, ...]
    :param user: Имя пользователя для логирования.
    :raises ValueError: Если возникает ошибка валидации или сохранения.
    """
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    for record in data:
        fuel_id = record.get("id")
        name = record.get("name")
        fuel_type_id = record.get("fuel_type_id")

        # Проверка на наличие необходимых данных
        if not name or not fuel_type_id:
            log_to_db(user, "Ошибка валидации", f"Запись: {record}")
            raise ValueError("Каждая запись должна содержать 'name' и 'fuel_type_id'.")

        if fuel_id:
            # Обновление существующей записи
            fuel = Fuel.query.get(fuel_id)
            if fuel:
                # Проверка на дублирование имени
                duplicate = Fuel.query.filter(Fuel.name == name, Fuel.id != fuel_id).first()
                if duplicate:
                    log_to_db(user, "Ошибка дублирования", f"Имя: {name}, ID: {fuel_id}")
                    raise ValueError(f"Запись с именем '{name}' уже существует.")
                
                # Обновление полей записи
                fuel.name = name
                fuel.id_fuel_type = fuel_type_id
                
                try:
                    # Сохранение изменений в базе данных
                    db.session.commit()
                    log_to_db(user, "Успешное обновление", f"Обновлен тип топлива с ID: {fuel_id}")
                except Exception as e:
                    db.session.rollback()  # Откат транзакции в случае ошибки
                    log_to_db(user, "Ошибка сохранения", f"Ошибка при обновлении типа топлива с ID: {fuel_id}, ошибка: {str(e)}")
                    raise ValueError(f"Ошибка при обновлении записи с ID {fuel_id}: {str(e)}")
            else:
                log_to_db(user, "Ошибка обновления", f"тип топлива с ID {fuel_id} не существует.")
                raise ValueError(f"Запись с ID {fuel_id} не найдена.")
        else:
            # Добавление новой записи
            duplicate = Fuel.query.filter(Fuel.name == name).first()
            if duplicate:
                log_to_db(user, "Ошибка дублирования", f"Имя: {name}")
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            new_fuel = Fuel(name=name, id_fuel_type=fuel_type_id)
            db.session.add(new_fuel)

            try:
                # Сохранение новой записи в базе данных
                db.session.commit()
                log_to_db(user, "Успешное добавление", f"Добавлен новый тип топлива: {name}")
            except Exception as e:
                db.session.rollback()  # Откат транзакции в случае ошибки
                log_to_db(user, "Ошибка сохранения", f"Ошибка при добавлении типа топлива: {name}, ошибка: {str(e)}")
                raise ValueError(f"Ошибка при добавлении новой записи: {str(e)}")

def get_total_fuel_records(fuel_filter, fuel_type_filter):
    """
    Возвращает общее количество записей типов топлива, соответствующих фильтру.
    :param fuel_filter: Фильтр по имени типа топлива.
    :return: Количество записей.
    """
    query = Fuel.query

    if fuel_filter:
        query = query.filter(Fuel.name.ilike(f"%{fuel_filter}%"))

    if fuel_type_filter:
        query = query.filter(Fuel.id_fuel_type == fuel_type_filter)
        
    return query.count()

def delete_fuel_list(ids, user):
    """Удаляет записи типов топлива по переданным ID."""
    log_to_db(user, "Удаление записей", f"Переданы ID для удаления: {ids}")
    
    successful_deletes = 0  # Для подсчета успешных удалений

    for fuel_id in ids:
        try:
            fuel_id = int(fuel_id)  # Приведение к целому числу
            fuel = Fuel.query.get(fuel_id)
            if fuel:
                db.session.delete(fuel)
                successful_deletes += 1
                log_to_db(user, "Удаление записи", f"Удален тип топлива с ID: {fuel_id}")
            else:
                log_to_db(user, "Ошибка удаления", f"Запись с ID {fuel_id} не найдена.")
        except ValueError:
            log_to_db(user, "Ошибка удаления", f"Некорректный ID: {fuel_id}")

    try:
        db.session.commit()
        log_to_db(user, "Удаление завершено", f"Успешно удалено записей: {successful_deletes}")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления", str(e))
        raise ValueError("Ошибка при удалении данных.")


def import_fuel_from_excel(file, user):
    """Импортирует данные типов топлива из Excel-файла в базу данных."""
    import pandas as pd

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

import pandas as pd
from io import BytesIO

def export_fuel_to_excel(user, fuel_filter=None, fuel_type_filter=None, sort_by="id", sort_dir="asc"):
    """Экспортирует данные типов топлива в Excel и возвращает бинарный поток."""

    log_to_db(user, "Начата выгрузка таблицы типов топлива из базы данных")
    log_to_db(user, "Параметры экспорта", f"filter={fuel_filter, fuel_type_filter}, sort_by={sort_by}, sort_dir={sort_dir}")
    
    query = Fuel.query
    
    if fuel_filter:
        query = query.filter(Fuel.name.ilike(f"%{fuel_filter}%"))

    if fuel_type_filter:
        query = query.filter(Fuel.id_fuel_type == fuel_type_filter)

    # Сортировка
    if sort_by == "id":
        query = query.order_by(Fuel.id.desc() if sort_dir == "desc" else Fuel.id.asc())
    elif sort_by == "name":
        query = query.order_by(Fuel.name.desc() if sort_dir == "desc" else Fuel.name.asc())
    elif sort_by == "fuel_type":
        query = query.join(FuelType).order_by(
            FuelType.name.desc() if sort_dir == "desc" else FuelType.name.asc()
        )

    fuel_items = query.all()
    data = [{
        "ID": o.id,
        "Тип топлива": o.name,
        "Вид топлива": o.fuel_type.name if o.fuel_type else "Не указан"
    } for o in fuel_items]

    log_to_db(user, "Подготовка данных для экспорта таблицы типов топлива в Excel", f"Записей для экспорта: {len(data)}")

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)
    
    # Создание Excel-файла
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Типы топлива")

    # Возврат файла в ответе
    output.seek(0)
    log_to_db(user, "Экспорт таблицы типов топлива в Excel завершён", f"Экспортировано записей: {len(data)}")
    return output
