from app import db
from app.models.log_models import Log
from app.models.oes_models import Oes
from app.models.res_models import Res, ResRegion
from app.models.region_models import Region
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


def get_res_list(page, per_page, res_filter=None, oes_filter=None, sort_by="id", sort_dir="asc"):
    """Получает список субъектов РФ с пагинацией, фильтрацией и сортировкой."""
    query = Res.query

    # Фильтрация по названию региональной энергосистемы
    if res_filter:
        query = query.filter(Res.name.ilike(f"%{res_filter}%"))

    # Фильтрация по ОЭС (строго по ID)
    if oes_filter:
        query = query.filter(Res.id_oes == oes_filter)  # Используем строгое сравнение ID

    # Сортировка
    if sort_by == "name":
        query = query.order_by(Res.name.desc() if sort_dir == "desc" else Res.name.asc())
    elif sort_by == "oes":
        query = query.join(Oes).order_by(
            Oes.name.desc() if sort_dir == "desc" else Oes.name.asc()
        )
    else:
        query = query.order_by(Res.id.desc() if sort_dir == "desc" else Res.id.asc())

    # Пагинация
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return pagination


def get_total_with_filter(res_filter, oes_filter):
    """
    Возвращает общее количество записей региональных энергосистем, соответствующих фильтру.
    :param res_filter: Фильтр по имени региональные энергосистемы.
    :return: Количество записей.
    """
    query = Res.query
    if res_filter:
        query = query.filter(Res.name.ilike(f"%{res_filter}%"))

    if oes_filter:
        query = query.join(Res.oes).filter(Oes.name.ilike(f"%{oes_filter}%"))
    
    return query.count()


def get_oes():
    """Получает список типов энергосистем."""
    return Oes.query.all()


def get_regions():
    """Получает список субъектов."""
    return Region.query.all()


def update_res(data, user):
    """
    Обновляет записи субъектов РФ в базе данных и связанные с ними регионы.
    :param data: Список словарей с данными для обновления. Пример:
                 [{"id": 1, "name": "Белгородская область", "oes_id": 2, "regions": [1, 2, 3]}, ...]
    :param user: Имя пользователя, инициировавшего обновление.
    :raises ValueError: Если обнаружены ошибки в данных или сохранении.
    """
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    log_to_db(user, "Получены данные для обновления", f"{data}")

    try:
        for record in data:
            res_id = record.get("id")
            name = record.get("name")
            oes_id = record.get("oes_id")
            region_ids = record.get("regions", [])  # Список ID регионов
            print(res_id, name, oes_id,region_ids)

            # Проверки на валидность данных
            if not name or oes_id is None:
                raise ValueError(f"Каждая запись должна содержать 'name' и 'oes_id'. Данные: {record}")

            # Проверка на существующий дубликат
            duplicate = Res.query.filter(Res.name == name).filter(Res.id != res_id).first()
            if duplicate:
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            if res_id:
                # Обновление существующей записи
                res = Res.query.get(res_id)
                if res:
                    res.name = name
                    res.id_oes = oes_id

                    # Удаление старых связей с регионами
                    db.session.query(ResRegion).filter_by(id_res=res.id).delete()

                    # Добавление новых связей с регионами
                    for region_id in region_ids:
                        db.session.add(ResRegion(id_res=res.id, id_region=region_id))
            else:
                # Создание новой записи
                new_res = Res(name=name, id_oes=oes_id)
                db.session.add(new_res)
                db.session.flush()  # Получение ID новой записи

                # Добавление связей с регионами для новой записи
                for region_id in region_ids:
                    db.session.add(ResRegion(id_res=new_res.id, id_region=region_id))

        # Сохранение изменений в базе данных
        db.session.commit()
        log_to_db(user, "Обновление записей списка субъектов РФ", f"Обновлено записей: {len(data)}")
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка обновления списка субъектов РФ", str(e))
        raise ValueError("Ошибка сохранения данных. Возможно, дублируются имена или другие уникальные ограничения.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка обновления списка субъектов РФ", str(e))
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


def add_res(data, user):
    """
    Добавляет запись субъекта РФ в базе данных.
    :param data: Список словарей с данными субъектов РФ. Пример:
                 [{"id": 1, "name": "Белгородская область", "oes_id": 2}, ...]
    :param user: Имя пользователя для логирования.
    :raises ValueError: Если возникает ошибка валидации или сохранения.
    """
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    for record in data:
        res_id = record.get("id")
        name = record.get("name")
        oes_id = record.get("oes_id")
        region_ids = record.get("regions", [])
        print(region_ids)

        # Проверка на наличие необходимых данных
        if not name or not oes_id or not region_ids:
            log_to_db(user, "Ошибка валидации", f"Запись: {record}")
            raise ValueError("Каждая запись должна содержать 'name', 'oes_id' и 'region_ids'.")

        if res_id:
            # Обновление существующей записи
            res = Res.query.get(res_id)
            if res:
                # Проверка на дублирование имени
                duplicate = Res.query.filter(Res.name == name, Res.id != res_id).first()
                if duplicate:
                    log_to_db(user, "Ошибка дублирования", f"Имя: {name}, ID: {res_id}")
                    raise ValueError(f"Запись с именем '{name}' уже существует.")
                
                # Обновление полей записи
                res.name = name
                res.id_oes = oes_id
                
                # Удаление старых связей с регионами
                db.session.query(ResRegion).filter_by(id_res=res.id).delete()
                
                # Добавление новых связей с регионами
                for region_id in region_ids:
                    db.session.add(ResRegion(id_res=res.id, id_region=region_id))
                
                try:
                    # Сохранение изменений в базе данных
                    db.session.commit()
                    log_to_db(user, "Успешное обновление", f"Обновлено субъектов РФ ID: {res_id}")
                except Exception as e:
                    db.session.rollback()  # Откат транзакции в случае ошибки
                    log_to_db(user, "Ошибка сохранения", f"Ошибка при обновлении списка субъектов РФ ID: {res_id}, ошибка: {str(e)}")
                    raise ValueError(f"Ошибка при обновлении записи с ID {res_id}: {str(e)}")
            else:
                log_to_db(user, "Ошибка обновления", f"субъектов РФ с ID {res_id} не существует.")
                raise ValueError(f"Запись с ID {res_id} не найдена.")
        else:
            new_res = Res(name=name, id_oes=oes_id)
                       
            db.session.add(new_res)

            try:
                # Сохранение новой записи в базе данных
                db.session.commit()
                
                # Добавление новых связей с регионами
                res = Res.query.get(new_res)
                for region_id in region_ids:
                    db.session.add(ResRegion(id_res=new_res.id, id_region=region_id))
                db.session.commit()

                log_to_db(user, "Успешное добавление", f"Добавлен новый субъект РФ: {name}")
            except Exception as e:
                db.session.rollback()  # Откат транзакции в случае ошибки
                log_to_db(user, "Ошибка сохранения", f"Ошибка при добавлении субъекта РФ: {name}, ошибка: {str(e)}")
                raise ValueError(f"Ошибка при добавлении новой записи: {str(e)}")

def delete_res_list(ids, user):
    """Удаляет записи субъектов РФ по переданным ID."""
    log_to_db(user, "Удаление записей", f"Переданы ID для удаления: {ids}")
    print(ids)

    successful_deletes = 0  # Для подсчета успешных удалений

    try:
        for res_id in ids:
            try:
                res_id = int(res_id)  # Приведение к целому числу
                res = Res.query.get(res_id)
                print(res)
                if res:
                    db.session.delete(res)
                    log_to_db(user, "Удаление записи", f"Удалён субъект РФ с ID: {res_id}")
            except ValueError:
                log_to_db(user, "Ошибка удаления", f"Некорректный ID: {res_id}")
                continue  # Пропустить ошибочные значения ID

        # Пытаемся выполнить коммит только после всех удалений
        db.session.commit()
        log_to_db(user, "Удаление завершено", f"Успешно удалено записей: {successful_deletes}")
    except Exception as e:
        # Откат всех изменений при возникновении ошибки
        db.session.rollback()
        log_to_db(user, "Ошибка удаления", str(e))
        raise ValueError("Ошибка при удалении данных.")


def import_res_from_excel(file, user):
    """Импортирует данные списка субъектов РФ из Excel-файла в базу данных."""
    import pandas as pd

    try:
        # Читаем данные из файла
        data = pd.read_excel(file)

        # Проверяем наличие необходимых столбцов
        if 'name' not in data.columns or 'id_oes' not in data.columns:
            raise ValueError("Неверный формат файла. Отсутствуют необходимые столбцы 'name' или 'id_oes'.")

        # Удаляем лишние пробелы в именах столбцов (на случай, если они есть)
        data.columns = data.columns.str.strip()

        # Обновляем или добавляем записи
        for _, row in data.iterrows():
            record = db.session.query(Res).filter_by(name=row['name']).first()
            if record:
                # Обновляем существующую запись
                record.id_oes = row['id_oes']
            else:
                # Создаем новую запись
                new_record = Res(name=row['name'], id_oes=row['id_oes'])
                db.session.add(new_record)

        # Сохраняем изменения
        db.session.commit()

        # Логируем результат
        log_to_db(user, "Импорт завершён", f"Обработано записей: {len(data)}")
        return len(data)

    except Exception as e:
        # Откат транзакции в случае ошибки
        db.session.rollback()
        log_to_db(user, "Ошибка импорта", str(e))
        raise ValueError(f"Ошибка при импорте данных: {e}")


import pandas as pd
from io import BytesIO

def export_res_to_excel(user, res_filter=None, oes_filter=None, sort_by="id", sort_dir="asc"):
    """Экспортирует данные списка субъектов РФ в Excel и возвращает бинарный поток."""
    log_to_db(user, "Начата выгрузка таблицы субъектов РФ из базы данных")
    log_to_db(user, "Параметры экспорта", f"res_filter={res_filter, oes_filter}, sort_by={sort_by}, sort_dir={sort_dir}")
    
    query = Res.query

    if res_filter:
        query = query.filter(Res.name.ilike(f"%{res_filter}%"))

    if oes_filter:
        query = query.join(Res.oes).filter(Oes.id.ilike(f"%{oes_filter}%"))

    # Сортировка
    if sort_by == "name":
        query = query.order_by(Res.name.desc() if sort_dir == "desc" else Res.name.asc())
    elif sort_by == "oes":
        query = query.join(Oes).order_by(
            Oes.name.desc() if sort_dir == "desc" else Oes.name.asc()
        )
    else:
        query = query.order_by(Res.id.desc() if sort_dir == "desc" else Res.id.asc())

    # Выполнение запроса
    res_items = query.all()
    log_to_db(user, "Получение данных завершено", f"Найдено записей: {len(res_items)}")
    
    print(res_items)
    
    # Преобразование данных
    data = [{
        "Порядковый номер": idx + 1,  # Добавляем порядковый номер (начиная с 1)
        "Региональная энергосистема": o.name,
        "ОЭС": o.oes.name if o.oes else "Не указан",
        "Субъекты РФ": ", ".join([region.region.name for region in o.regions]) if o.regions else "Не указан"
    } for idx, o in enumerate(res_items)]


    if not data:
        log_to_db(user, "Экспорт завершён", "Нет данных для экспорта.")
        return None

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)
    output = BytesIO()

    try:
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name="Региональные энергосистемы")
    except Exception as e:
        log_to_db(user, "Ошибка создания Excel-файла", str(e))
        raise ValueError("Ошибка при создании Excel-файла.")

    output.seek(0)
    log_to_db(user, "Экспорт таблицы субъектов РФ в Excel завершён", f"Экспортировано записей: {len(data)}")
    return output
