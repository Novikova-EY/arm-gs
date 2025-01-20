from app import db
from app.models.log_models import Log
from app.models.oes_models import Oes, OesType
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


def get_oes_list(page, per_page, oes_filter=None, sort_by="id", sort_dir="asc"):
    """Получает список ОЭС с пагинацией, фильтрацией и сортировкой."""
    query = Oes.query

    if oes_filter:
        query = query.filter(Oes.name.ilike(f"%{oes_filter}%"))

    # Сортировка
    if sort_by == "name":
        query = query.order_by(Oes.name.desc() if sort_dir == "desc" else Oes.name.asc())
    elif sort_by == "oes_type":
        query = query.join(OesType).order_by(
            OesType.name.desc() if sort_dir == "desc" else OesType.name.asc()
        )
    else:
        query = query.order_by(Oes.id.desc() if sort_dir == "desc" else Oes.id.asc())

    # Пагинация
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return pagination


def get_oes_types():
    """Получает список типов энергосистем."""
    return OesType.query.all()


def update_oes(data, user):
    """
    Обновляет записи ОЭС в базе данных.
    :param data: Список словарей с данными для обновления. Пример:
                 [{"id": 1, "name": "ОЭС Центр", "oes_type_id": 2}, ...]
    :param user: Имя пользователя, инициировавшего обновление.
    :raises ValueError: Если обнаружены ошибки в данных или сохранении.
    """
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    log_to_db(user, "Получены данные для обновления", f"{data}")

    for record in data:
        oes_id = record.get("id")
        name = record.get("name")
        oes_type_id = record.get("oes_type_id")

        # Проверки на валидность данных
        if not name or not oes_type_id:
            raise ValueError("Каждая запись должна содержать 'name' и 'oes_type_id'.")

        if oes_id:
            oes = Oes.query.get(oes_id)

            duplicate = Oes.query.filter(Oes.name == name, Oes.id != oes_id).first()
            if duplicate:
                raise ValueError(f"Запись с именем '{name}' уже существует.")
            
            oes.name = name
            oes.id_oes_type = oes_type_id
        else:
            duplicate = Oes.query.filter(Oes.name == name, Oes.id != oes_id).first()
            if duplicate:
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            new_oes = Oes(name=name, id_oes_type=oes_type_id)
            db.session.add(new_oes)

    # Сохранение изменений в базе данных
    try:
        db.session.commit()
        log_to_db(user, "Обновление записей ОЭС", f"Обновлено записей: {len(data)}")
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка обновления ОЭС", str(e))
        raise ValueError("Ошибка сохранения данных. Возможно, дублируются имена.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка обновления ОЭС", str(e))
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


def add_oes(data, user):
    """
    Добавляет или обновляет записи ОЭС в базе данных.
    :param data: Список словарей с данными ОЭС. Пример:
                 [{"id": 1, "name": "ОЭС Центр", "oes_type_id": 2}, ...]
    :param user: Имя пользователя для логирования.
    :raises ValueError: Если возникает ошибка валидации или сохранения.
    """
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    for record in data:
        oes_id = record.get("id")
        name = record.get("name")
        oes_type_id = record.get("oes_type_id")

        # Проверка на наличие необходимых данных
        if not name or not oes_type_id:
            log_to_db(user, "Ошибка валидации", f"Запись: {record}")
            raise ValueError("Каждая запись должна содержать 'name' и 'oes_type_id'.")

        if oes_id:
            # Обновление существующей записи
            oes = Oes.query.get(oes_id)
            if oes:
                # Проверка на дублирование имени
                duplicate = Oes.query.filter(Oes.name == name, Oes.id != oes_id).first()
                if duplicate:
                    log_to_db(user, "Ошибка дублирования", f"Имя: {name}, ID: {oes_id}")
                    raise ValueError(f"Запись с именем '{name}' уже существует.")
                
                # Обновление полей записи
                oes.name = name
                oes.id_oes_type = oes_type_id
                
                try:
                    # Сохранение изменений в базе данных
                    db.session.commit()
                    log_to_db(user, "Успешное обновление", f"Обновлено ОЭС с ID: {oes_id}")
                except Exception as e:
                    db.session.rollback()  # Откат транзакции в случае ошибки
                    log_to_db(user, "Ошибка сохранения", f"Ошибка при обновлении ОЭС с ID: {oes_id}, ошибка: {str(e)}")
                    raise ValueError(f"Ошибка при обновлении записи с ID {oes_id}: {str(e)}")
            else:
                log_to_db(user, "Ошибка обновления", f"ОЭС с ID {oes_id} не существует.")
                raise ValueError(f"Запись с ID {oes_id} не найдена.")
        else:
            # Добавление новой записи
            duplicate = Oes.query.filter(Oes.name == name).first()
            if duplicate:
                log_to_db(user, "Ошибка дублирования", f"Имя: {name}")
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            new_oes = Oes(name=name, id_oes_type=oes_type_id)
            db.session.add(new_oes)

            try:
                # Сохранение новой записи в базе данных
                db.session.commit()
                log_to_db(user, "Успешное добавление", f"Добавлено новое ОЭС: {name}")
            except Exception as e:
                db.session.rollback()  # Откат транзакции в случае ошибки
                log_to_db(user, "Ошибка сохранения", f"Ошибка при добавлении ОЭС: {name}, ошибка: {str(e)}")
                raise ValueError(f"Ошибка при добавлении новой записи: {str(e)}")

def get_total_oes_records(oes_filter):
    """
    Возвращает общее количество записей ОЭС, соответствующих фильтру.
    :param oes_filter: Фильтр по имени ОЭС.
    :return: Количество записей.
    """
    query = Oes.query
    if oes_filter:
        query = query.filter(Oes.name.ilike(f"%{oes_filter}%"))
    return query.count()

def delete_oes_list(ids, user):
    """Удаляет записи ОЭС по переданным ID."""
    log_to_db(user, "Удаление записей", f"Переданы ID для удаления: {ids}")
    
    successful_deletes = 0  # Для подсчета успешных удалений

    for oes_id in ids:
        try:
            oes_id = int(oes_id)  # Приведение к целому числу
            oes = Oes.query.get(oes_id)
            if oes:
                db.session.delete(oes)
                successful_deletes += 1
                log_to_db(user, "Удаление записи", f"Удален ОЭС ID: {oes_id}")
            else:
                log_to_db(user, "Ошибка удаления", f"Запись с ID {oes_id} не найдена.")
        except ValueError:
            log_to_db(user, "Ошибка удаления", f"Некорректный ID: {oes_id}")

    try:
        db.session.commit()
        log_to_db(user, "Удаление завершено", f"Успешно удалено записей: {successful_deletes}")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления", str(e))
        raise ValueError("Ошибка при удалении данных.")


def import_oes_from_excel(file, user):
    """Импортирует данные ОЭС из Excel-файла в базу данных."""
    import pandas as pd

    try:
        data = pd.read_excel(file)

        if 'name' not in data.columns or 'id_oes_type' not in data.columns:
            raise ValueError("Неверный формат файла. Отсутствуют необходимые столбцы.")

        db.session.query(Oes).delete()
        db.session.commit()

        db.session.execute(text("ALTER TABLE oes AUTO_INCREMENT = 1"))
        db.session.commit()

        records = [Oes(name=row['name'], id_oes_type=row['id_oes_type']) for _, row in data.iterrows()]
        db.session.bulk_save_objects(records)
        db.session.commit()

        log_to_db(user, "Импорт завершён", f"Импортировано записей: {len(records)}")
        return len(records)
    except Exception as e:
        log_to_db(user, "Ошибка импорта", str(e))
        raise ValueError(f"Ошибка при импорте данных: {e}")

import pandas as pd
from io import BytesIO

def export_oes_to_excel(user, oes_filter=None, sort_by="id", sort_dir="asc"):
    """Экспортирует данные ОЭС в Excel и возвращает бинарный поток."""

    log_to_db(user, "Начата выгрузка таблицы ОЭС из базы данных")
    log_to_db(user, "Параметры экспорта", f"oes_filter={oes_filter}, sort_by={sort_by}, sort_dir={sort_dir}")
    
    query = Oes.query
    if oes_filter:
        query = query.filter(Oes.name.ilike(f"%{oes_filter}%"))

    # Сортировка
    if sort_by == "id":
        query = query.order_by(Oes.id.desc() if sort_dir == "desc" else Oes.id.asc())
    elif sort_by == "name":
        query = query.order_by(Oes.name.desc() if sort_dir == "desc" else Oes.name.asc())
    elif sort_by == "oes_type":
        query = query.join(OesType).order_by(
            OesType.name.desc() if sort_dir == "desc" else OesType.name.asc()
        )

    oes_items = query.all()
    data = [{
        "ID": o.id,
        "Наименование": o.name,
        "Тип энергосистемы": o.oes_type.name if o.oes_type else "Не указан"
    } for o in oes_items]

    log_to_db(user, "Подготовка данных для экспорта таблицы субъектов РФ в Excel", f"Записей для экспорта: {len(data)}")

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)
    
    # Создание Excel-файла
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="ОЭС")

    # Возврат файла в ответе
    output.seek(0)
    log_to_db(user, "Экспорт таблицы субъектов РФ в Excel завершён", f"Экспортировано записей: {len(data)}")
    return output
