from app import db
from app.models.log_models import Log
from app.models.region_models import Region
from app.models.fo_models import Fo
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

def log_to_db(username, action, details=None):
    """Записывает лог действия пользователя в базу данных."""
    try:
        log_entry = Log(username=username, action=action, details=details)
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка записи лога: {e}")


def get_region_list(page, per_page, name_filter=None, sort_by="id", sort_dir="asc"):
    """Получает список субъектов РФ с пагинацией, фильтрацией и сортировкой."""
    query = Region.query

    if name_filter:
        query = query.filter(Region.name.ilike(f"%{name_filter}%"))

    # Сортировка
    if sort_by == "name":
        query = query.order_by(Region.name.desc() if sort_dir == "desc" else Region.name.asc())
    elif sort_by == "fo":
        query = query.join(Fo).order_by(
            Fo.name.desc() if sort_dir == "desc" else Fo.name.asc()
        )
    else:
        query = query.order_by(Region.id.desc() if sort_dir == "desc" else Region.id.asc())

    # Пагинация
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return pagination


def get_fos():
    """Получает список типов энергосистем."""
    return Fo.query.all()


def update_region(data, user):
    """
    Обновляет запись субъекта РФ в базе данных.
    :param data: Список словарей с данными для обновления. Пример:
                 [{"id": 1, "name": "Белгородская область", "fo_id": 2}, ...]
    :param user: Имя пользователя, инициировавшего обновление.
    :raises ValueError: Если обнаружены ошибки в данных или сохранении.
    """
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    log_to_db(user, "Получены данные для обновления", f"{data}")

    for record in data:
        region_id = record.get("id")
        name = record.get("name")
        fo_id = record.get("fo_id")

        # Проверки на валидность данных
        if not name or not fo_id:
            raise ValueError("Каждая запись должна содержать 'name' и 'fo_id'.")

        if region_id:
            region = Region.query.get(region_id)

            duplicate = Region.query.filter(Region.name == name, Region.id != region_id).first()
            if duplicate:
                raise ValueError(f"Запись с именем '{name}' уже существует.")
            
            region.name = name
            region.id_fo = fo_id
        else:
            duplicate = Region.query.filter(Region.name == name, Region.id != region_id).first()
            if duplicate:
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            new_region = Region(name=name, id_fo=fo_id)
            db.session.add(new_region)

    # Сохранение изменений в базе данных
    try:
        db.session.commit()
        log_to_db(user, "Обновление записей списка субъектов РФ", f"Обновлено записей: {len(data)}")
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка обновления списка субъектов РФ", str(e))
        raise ValueError("Ошибка сохранения данных. Возможно, дублируются имена.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка обновления списка субъектов РФ", str(e))
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


def add_region(data, user):
    """
    Добавляет запись субъекта РФ в базе данных.
    :param data: Список словарей с данными субъектов РФ. Пример:
                 [{"id": 1, "name": "Белгородская область", "fo_id": 2}, ...]
    :param user: Имя пользователя для логирования.
    :raises ValueError: Если возникает ошибка валидации или сохранения.
    """
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    for record in data:
        region_id = record.get("id")
        name = record.get("name")
        fo_id = record.get("fo_id")

        # Проверка на наличие необходимых данных
        if not name or not fo_id:
            log_to_db(user, "Ошибка валидации", f"Запись: {record}")
            raise ValueError("Каждая запись должна содержать 'name' и 'fo_id'.")

        if region_id:
            # Обновление существующей записи
            region = Region.query.get(region_id)
            if region:
                # Проверка на дублирование имени
                duplicate = Region.query.filter(Region.name == name, Region.id != region_id).first()
                if duplicate:
                    log_to_db(user, "Ошибка дублирования", f"Имя: {name}, ID: {region_id}")
                    raise ValueError(f"Запись с именем '{name}' уже существует.")
                
                # Обновление полей записи
                region.name = name
                region.id_fo = fo_id
                
                try:
                    # Сохранение изменений в базе данных
                    db.session.commit()
                    log_to_db(user, "Успешное обновление", f"Обновлено субъектов РФ ID: {region_id}")
                except Exception as e:
                    db.session.rollback()  # Откат транзакции в случае ошибки
                    log_to_db(user, "Ошибка сохранения", f"Ошибка при обновлении списка субъектов РФ ID: {region_id}, ошибка: {str(e)}")
                    raise ValueError(f"Ошибка при обновлении записи с ID {region_id}: {str(e)}")
            else:
                log_to_db(user, "Ошибка обновления", f"субъектов РФ с ID {region_id} не существует.")
                raise ValueError(f"Запись с ID {region_id} не найдена.")
        else:
            # Добавление новой записи
            duplicate = Region.query.filter(Region.name == name).first()
            if duplicate:
                log_to_db(user, "Ошибка дублирования", f"Имя: {name}")
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            new_region = Region(name=name, id_fo=fo_id)  # предполагается, что Region имеет такие атрибуты
            db.session.add(new_region)

            try:
                # Сохранение новой записи в базе данных
                db.session.commit()
                log_to_db(user, "Успешное добавление", f"Добавлен новый субъект РФ: {name}")
            except Exception as e:
                db.session.rollback()  # Откат транзакции в случае ошибки
                log_to_db(user, "Ошибка сохранения", f"Ошибка при добавлении субъекта РФ: {name}, ошибка: {str(e)}")
                raise ValueError(f"Ошибка при добавлении новой записи: {str(e)}")

def get_total_region_records(name_filter):
    """
    Возвращает общее количество записей субъектов РФ, соответствующих фильтру.
    :param name_filter: Фильтр по имени субъекта РФ.
    :return: Количество записей.
    """
    query = Region.query
    if name_filter:
        query = query.filter(Region.name.ilike(f"%{name_filter}%"))
    return query.count()

def delete_region_list(ids, user):
    """Удаляет записи субъектов РФ по переданным ID."""
    log_to_db(user, "Удаление записей", f"Переданы ID для удаления: {ids}")
    
    successful_deletes = 0  # Для подсчета успешных удалений

    for region_id in ids:
        try:
            region_id = int(region_id)  # Приведение к целому числу
            region = Region.query.get(region_id)
            if region:
                db.session.delete(region)
                successful_deletes += 1
                log_to_db(user, "Удаление записи", f"Удалён субъект РФ с ID: {region_id}")
            else:
                log_to_db(user, "Ошибка удаления", f"Запись с ID {region_id} не найдена.")
        except ValueError:
            log_to_db(user, "Ошибка удаления", f"Некорректный ID: {region_id}")

    try:
        db.session.commit()
        log_to_db(user, "Удаление завершено", f"Успешно удалено записей: {successful_deletes}")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления", str(e))
        raise ValueError("Ошибка при удалении данных.")


def import_region_from_excel(file, user):
    """Импортирует данные списка субъектов РФ из Excel-файла в базу данных."""
    import pandas as pd

    try:
        data = pd.read_excel(file)

        if 'name' not in data.columns or 'id_fo' not in data.columns:
            raise ValueError("Неверный формат файла. Отсутствуют необходимые столбцы.")

        db.session.query(Region).delete()
        db.session.commit()

        db.session.execute(text("ALTER TABLE region AUTO_INCREMENT = 1"))
        db.session.commit()

        records = [Region(name=row['name'], id_fo=row['id_fo']) for _, row in data.iterrows()]
        db.session.bulk_save_objects(records)
        db.session.commit()

        log_to_db(user, "Импорт завершён", f"Импортировано записей: {len(records)}")
        return len(records)
    except Exception as e:
        log_to_db(user, "Ошибка импорта", str(e))
        raise ValueError(f"Ошибка при импорте данных: {e}")

import pandas as pd
from io import BytesIO

def export_region_to_excel(user, name_filter=None, sort_by="id", sort_dir="asc"):
    """Экспортирует данные списка субъектов РФ в Excel и возвращает бинарный поток."""

    log_to_db(user, "Начата выгрузка таблицы субъектов РФ из базы данных")
    log_to_db(user, "Параметры экспорта", f"name_filter={name_filter}, sort_by={sort_by}, sort_dir={sort_dir}")
    
    query = Region.query
    if name_filter:
        query = query.filter(Region.name.ilike(f"%{name_filter}%"))

    # Сортировка
    if sort_by == "id":
        query = query.order_by(Region.id.desc() if sort_dir == "desc" else Region.id.asc())
    elif sort_by == "name":
        query = query.order_by(Region.name.desc() if sort_dir == "desc" else Region.name.asc())
    elif sort_by == "fo":
        query = query.join(Fo).order_by(
            Fo.name.desc() if sort_dir == "desc" else Fo.name.asc()
        )

    region_items = query.all()
    data = [{
        "ID": o.id,
        "Субъект РФ": o.name,
        "ФО": o.fo.name if o.fo else "Не указан"
    } for o in region_items]

    log_to_db(user, "Подготовка данных для экспорта таблицы субъектов РФ в Excel", f"Записей для экспорта: {len(data)}")

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)
    
    # Создание Excel-файла
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="субъектов РФ")

    # Возврат файла в ответе
    output.seek(0)
    log_to_db(user, "Экспорт таблицы субъектов РФ в Excel завершён", f"Экспортировано записей: {len(data)}")
    return output
