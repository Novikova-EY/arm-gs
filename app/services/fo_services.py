from app import db
from app.models.log_models import Log
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


def get_fo_list(page, per_page, fo_filter=None, sort_by="id", sort_dir="asc"):
    """Получает список ФО с пагинацией, фильтрацией и сортировкой."""
    query = Fo.query

    if fo_filter:
        query = query.filter(Fo.name.ilike(f"%{fo_filter}%"))

    # Сортировка
    if sort_by == "name":
        query = query.order_by(Fo.name.desc() if sort_dir == "desc" else Fo.name.asc())
    else:
        query = query.order_by(Fo.id.desc() if sort_dir == "desc" else Fo.id.asc())

    # Пагинация
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return pagination


def update_fo(data, user):
    """
    Обновляет записи ФО в базе данных.
    :param data: Список словарей с данными для обновления. Пример:
                 [{"id": 1, "name": "Центральный ФО"}, ...]
    :param user: Имя пользователя, инициировавшего обновление.
    :raises ValueError: Если обнаружены ошибки в данных или сохранении.
    """
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    log_to_db(user, "Получены данные для обновления", f"{data}")

    for record in data:
        fo_id = record.get("id")
        name = record.get("name")

        # Проверки на валидность данных
        if not name:
            raise ValueError("Каждая запись должна содержать 'name'.")

        if fo_id:
            fo = Fo.query.get(fo_id)

            duplicate = Fo.query.filter(Fo.name == name, Fo.id != fo_id).first()
            if duplicate:
                raise ValueError(f"Запись с именем '{name}' уже существует.")
            
            fo.name = name
        else:
            duplicate = Fo.query.filter(Fo.name == name, Fo.id != fo_id).first()
            if duplicate:
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            new_fo = Fo(name=name)
            db.session.add(new_fo)

    # Сохранение изменений в базе данных
    try:
        db.session.commit()
        log_to_db(user, "Обновление записей ФО", f"Обновлено записей: {len(data)}")
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка обновления ФО", str(e))
        raise ValueError("Ошибка сохранения данных. Возможно, дублируются имена.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка обновления ФО", str(e))
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


def add_fo(data, user):
    """
    Добавляет или обновляет записи ФО в базе данных.
    :param data: Список словарей с данными ФО. Пример:
                 [{"id": 1, "name": "Центральный ФО"}, ...]
    :param user: Имя пользователя для логирования.
    :raises ValueError: Если возникает ошибка валидации или сохранения.
    """
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    for record in data:
        fo_id = record.get("id")
        name = record.get("name")

        # Проверка на наличие необходимых данных
        if not name:
            log_to_db(user, "Ошибка валидации", f"Запись: {record}")
            raise ValueError("Каждая запись должна содержать 'name'.")

        if fo_id:
            # Обновление существующей записи
            fo = Fo.query.get(fo_id)
            if fo:
                # Проверка на дублирование имени
                duplicate = Fo.query.filter(Fo.name == name, Fo.id != fo_id).first()
                if duplicate:
                    log_to_db(user, "Ошибка дублирования", f"Имя: {name}, ID: {fo_id}")
                    raise ValueError(f"Запись с именем '{name}' уже существует.")
                
                # Обновление полей записи
                fo.name = name
                
                try:
                    # Сохранение изменений в базе данных
                    db.session.commit()
                    log_to_db(user, "Успешное обновление", f"Обновлено ФО с ID: {fo_id}")
                except Exception as e:
                    db.session.rollback()  # Откат транзакции в случае ошибки
                    log_to_db(user, "Ошибка сохранения", f"Ошибка при обновлении ФО с ID: {fo_id}, ошибка: {str(e)}")
                    raise ValueError(f"Ошибка при обновлении записи с ID {fo_id}: {str(e)}")
            else:
                log_to_db(user, "Ошибка обновления", f"ФО с ID {fo_id} не существует.")
                raise ValueError(f"Запись с ID {fo_id} не найдена.")
        else:
            # Добавление новой записи
            duplicate = Fo.query.filter(Fo.name == name).first()
            if duplicate:
                log_to_db(user, "Ошибка дублирования", f"Имя: {name}")
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            new_fo = Fo(name=name)
            db.session.add(new_fo)

            try:
                # Сохранение новой записи в базе данных
                db.session.commit()
                log_to_db(user, "Успешное добавление", f"Добавлено новое ФО: {name}")
            except Exception as e:
                db.session.rollback()  # Откат транзакции в случае ошибки
                log_to_db(user, "Ошибка сохранения", f"Ошибка при добавлении ФО: {name}, ошибка: {str(e)}")
                raise ValueError(f"Ошибка при добавлении новой записи: {str(e)}")

def get_total_fo_records(fo_filter):
    """
    Возвращает общее количество записей ФО, соответствующих фильтру.
    :param fo_filter: Фильтр по имени ФО.
    :return: Количество записей.
    """
    query = Fo.query
    if fo_filter:
        query = query.filter(Fo.name.ilike(f"%{fo_filter}%"))
    return query.count()

def delete_fo_list(ids, user):
    """Удаляет записи ФО по переданным ID."""
    log_to_db(user, "Удаление записей", f"Переданы ID для удаления: {ids}")
    
    successful_deletes = 0  # Для подсчета успешных удалений

    for fo_id in ids:
        try:
            fo_id = int(fo_id)  # Приведение к целому числу
            fo = Fo.query.get(fo_id)
            if fo:
                db.session.delete(fo)
                successful_deletes += 1
                log_to_db(user, "Удаление записи", f"Удален ФО ID: {fo_id}")
            else:
                log_to_db(user, "Ошибка удаления", f"Запись с ID {fo_id} не найдена.")
        except ValueError:
            log_to_db(user, "Ошибка удаления", f"Некорректный ID: {fo_id}")

    try:
        db.session.commit()
        log_to_db(user, "Удаление завершено", f"Успешно удалено записей: {successful_deletes}")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления", str(e))
        raise ValueError("Ошибка при удалении данных.")


def import_fo_from_excel(file, user):
    """Импортирует данные ФО из Excel-файла в базу данных."""
    import pandas as pd

    try:
        data = pd.read_excel(file)

        if 'name' not in data.columns not in data.columns:
            raise ValueError("Неверный формат файла. Отсутствуют необходимые столбцы.")

        db.session.query(Fo).delete()
        db.session.commit()

        db.session.execute(text("ALTER TABLE fo AUTO_INCREMENT = 1"))
        db.session.commit()

        records = [Fo(name=row['name']) for _, row in data.iterrows()]
        db.session.bulk_save_objects(records)
        db.session.commit()

        log_to_db(user, "Импорт завершён", f"Импортировано записей: {len(records)}")
        return len(records)
    except Exception as e:
        log_to_db(user, "Ошибка импорта", str(e))
        raise ValueError(f"Ошибка при импорте данных: {e}")

import pandas as pd
from io import BytesIO

def export_fo_to_excel(user, fo_filter=None, sort_by="id", sort_dir="asc"):
    """Экспортирует данные ФО в Excel и возвращает бинарный поток."""

    log_to_db(user, "Начата выгрузка таблицы ФО из базы данных")
    log_to_db(user, "Параметры экспорта", f"fo_filter={fo_filter}, sort_by={sort_by}, sort_dir={sort_dir}")
    
    query = Fo.query
    if fo_filter:
        query = query.filter(Fo.name.ilike(f"%{fo_filter}%"))

    # Сортировка
    if sort_by == "id":
        query = query.order_by(Fo.id.desc() if sort_dir == "desc" else Fo.id.asc())
    elif sort_by == "name":
        query = query.order_by(Fo.name.desc() if sort_dir == "desc" else Fo.name.asc())

    fo_items = query.all()
    data = [{
        "ID": o.id,
        "Наименование": o.name
    } for o in fo_items]

    log_to_db(user, "Подготовка данных для экспорта таблицы субъектов РФ в Excel", f"Записей для экспорта: {len(data)}")

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)
    
    # Создание Excel-файла
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="ФО")

    # Возврат файла в ответе
    output.seek(0)
    log_to_db(user, "Экспорт таблицы субъектов РФ в Excel завершён", f"Экспортировано записей: {len(data)}")
    return output
