from app import db
from app.models.logs_models import Log
from app.models.territories_models import FederalDistrict
from sqlalchemy import text, or_
from sqlalchemy.exc import IntegrityError
from app.services.logging_service import log_to_db


def get_federal_district_list(page, per_page, federal_district_filter=None, sort_by="id", sort_dir="asc"):
    """Получает список ФО с пагинацией, фильтрацией и сортировкой."""
    # Фильтрация
    query = FederalDistrict.query

    if federal_district_filter:
        query = query.filter(
            or_(
                FederalDistrict.name.ilike(f"%{federal_district_filter}%"),
                FederalDistrict.name_full.ilike(f"%{federal_district_filter}%"),
                FederalDistrict.name_abr.ilike(f"%{federal_district_filter}%")
            )
        )

    # Сортировка
    if sort_by in ["name", "name_full", "name_abr"]:
        sort_field = getattr(FederalDistrict, sort_by)
        query = query.order_by(sort_field.desc() if sort_dir == "desc" else sort_field.asc())
    else:
        query = query.order_by(FederalDistrict.id.desc() if sort_dir == "desc" else FederalDistrict.id.asc())

    # Пагинация
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return pagination


def update_federal_district(data, user):
    """
    Обновляет записи ФО в базе данных.
    :param data: Список словарей с данными для обновления. Пример:
                 [{"id": 1, "name": "Центральный ФО", "name_full": "Центральный федеральный округ", "name_abr": "ЦФО"}, ...]
    :param user: Имя пользователя, инициировавшего обновление.
    :raises ValueError: Если обнаружены ошибки в данных или сохранении.
    """
    if not isinstance(data, list) or not data:
        raise ValueError("Данные должны быть предоставлены в виде непустого списка словарей.")

    log_to_db(user, "Получены данные для обновления", f"{data}")

    updated_count = 0
    added_count = 0
    no_change_count = 0

    for record in data:
        federal_district_id = record.get("id")
        name = record.get("name", "").strip()
        name_full = record.get("name_full", "").strip()
        name_abr = record.get("name_abr", "").strip()

        if federal_district_id:
            # Обновление существующей записи
            federal_district = FederalDistrict.query.get(federal_district_id)
            if not federal_district:
                raise ValueError(f"Запись с ID {federal_district_id} не найдена.")

            # Проверка на дубликаты
            duplicate = FederalDistrict.query.filter(
                FederalDistrict.name == name,
                FederalDistrict.id != federal_district_id
            ).first()
            if duplicate:
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            # Проверка, изменились ли данные
            if (federal_district.name == name and
                federal_district.name_full == name_full and
                federal_district.name_abr == name_abr):
                no_change_count += 1
            else:
                federal_district.name = name
                federal_district.name_full = name_full
                federal_district.name_abr = name_abr
                updated_count += 1
        else:
            # Добавление новой записи
            duplicate = FederalDistrict.query.filter(FederalDistrict.name == name).first()
            if duplicate:
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            new_federal_district = FederalDistrict(
                name=name,
                name_full=name_full,
                name_abr=name_abr
            )
            db.session.add(new_federal_district)
            added_count += 1

    # Проверка, есть ли изменения для сохранения
    if updated_count == 0 and added_count == 0:
        raise ValueError("Данные для обновления отсутствуют.")

    # Сохранение изменений в базе данных
    try:
        db.session.commit()
        log_to_db(
            user,
            "Обновление записей ФО",
            f"Обновлено записей: {updated_count}, добавлено новых: {added_count}, без изменений: {no_change_count}"
        )
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка обновления ФО", str(e))
        raise ValueError("Ошибка сохранения данных. Возможно, дублируются имена.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка обновления ФО", str(e))
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


def add_federal_district(data, user):
    """
    Добавляет или обновляет записи ФО в базе данных.
    :param data: Список словарей с данными ФО. Пример:
                 [{"id": 1, "name": "Центральный ФО", "name_full": "Центральный федеральный округ", "name_abr": "ЦФО"}, ...]
    :param user: Имя пользователя для логирования.
    :raises ValueError: Если возникает ошибка валидации или сохранения.
    """
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    for record in data:
        federal_district_id = record.get("id")
        name = record.get("name", "").strip()
        name_full = record.get("name_full", "").strip()
        name_abr = record.get("name_abr", "").strip()

        # Проверка на наличие необходимых данных
        if not name or not name_full or not name_abr:
            log_to_db(user, "Ошибка валидации", f"Запись: {record}")
            raise ValueError("Каждая запись должна содержать 'name', 'name_full' и 'name_abr'.")

        if federal_district_id:
            # Обновление существующей записи
            federal_district = FederalDistrict.query.get(federal_district_id)
            if federal_district:
                # Проверка на дублирование имени
                duplicate = FederalDistrict.query.filter(
                    FederalDistrict.name == name,
                    FederalDistrict.id != federal_district_id
                ).first()
                if duplicate:
                    log_to_db(user, "Ошибка дублирования", f"Имя: {name}, ID: {federal_district_id}")
                    raise ValueError(f"Запись с именем '{name}' уже существует.")

                # Обновление полей записи
                federal_district.name = name
                federal_district.name_full = name_full
                federal_district.name_abr = name_abr

                try:
                    # Сохранение изменений в базе данных
                    db.session.commit()
                    log_to_db(user, "Успешное обновление", f"Обновлено ФО с ID: {federal_district_id}")
                except Exception as e:
                    db.session.rollback()  # Откат транзакции в случае ошибки
                    log_to_db(user, "Ошибка сохранения", f"Ошибка при обновлении ФО с ID: {federal_district_id}, ошибка: {str(e)}")
                    raise ValueError(f"Ошибка при обновлении записи с ID {federal_district_id}: {str(e)}")
            else:
                log_to_db(user, "Ошибка обновления", f"ФО с ID {federal_district_id} не существует.")
                raise ValueError(f"Запись с ID {federal_district_id} не найдена.")
        else:
            # Добавление новой записи
            duplicate = FederalDistrict.query.filter(FederalDistrict.name == name).first()
            if duplicate:
                log_to_db(user, "Ошибка дублирования", f"Имя: {name}")
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            new_federal_district = FederalDistrict(
                name=name,
                name_full=name_full,
                name_abr=name_abr
            )
            db.session.add(new_federal_district)

            try:
                # Сохранение новой записи в базе данных
                db.session.commit()
                log_to_db(user, "Успешное добавление", f"Добавлено новое ФО: {name}")
            except Exception as e:
                db.session.rollback()  # Откат транзакции в случае ошибки
                log_to_db(user, "Ошибка сохранения", f"Ошибка при добавлении ФО: {name}, ошибка: {str(e)}")
                raise ValueError(f"Ошибка при добавлении новой записи: {str(e)}")


def get_total_federal_district_records(federal_district_filter):
    """
    Возвращает общее количество записей ФО, соответствующих фильтру.
    :param federal_district_filter: Фильтр по имени ФО.
    :return: Количество записей.
    """
    query = FederalDistrict.query

    if federal_district_filter:
        query = query.filter(FederalDistrict.name.ilike(f"%{federal_district_filter}%"))
        
    return query.count()

def delete_federal_district_list(ids, user):
    """Удаляет записи ФО по переданным ID."""
    log_to_db(user, "Удаление записей", f"Переданы ID для удаления: {ids}")
    
    successful_deletes = 0  # Для подсчета успешных удалений

    for federal_district_id in ids:
        try:
            federal_district_id = int(federal_district_id)  # Приведение к целому числу
            federal_district = FederalDistrict.query.get(federal_district_id)
            if federal_district:
                db.session.delete(federal_district)
                successful_deletes += 1
                log_to_db(user, "Удаление записи", f"Удален ФО ID: {federal_district_id}")
            else:
                log_to_db(user, "Ошибка удаления", f"Запись с ID {federal_district_id} не найдена.")
        except ValueError:
            log_to_db(user, "Ошибка удаления", f"Некорректный ID: {federal_district_id}")

    try:
        db.session.commit()
        log_to_db(user, "Удаление завершено", f"Успешно удалено записей: {successful_deletes}")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления", str(e))
        raise ValueError("Ошибка при удалении данных.")


def import_federal_district_from_excel(file, user):
    """Импортирует данные ФО из Excel-файла в базу данных с проверкой отсутствия данных для обновления."""
    import pandas as pd
    from sqlalchemy.exc import IntegrityError

    try:
        # Чтение данных из файла Excel
        data = pd.read_excel(file)

        # Проверка наличия обязательных столбцов
        required_columns = {'name', 'name_full', 'name_abr'}
        if not required_columns.issubset(data.columns):
            raise ValueError("Неверный формат файла. Отсутствуют необходимые столбцы: 'name', 'name_full', 'name_abr'.")

        # Очистка данных (удаление пустых строк)
        data = data.dropna(subset=['name', 'name_full', 'name_abr'])

        if data.empty:
            raise ValueError("Файл не содержит данных для обновления.")

        # Счетчики для статистики
        updated_count = 0
        added_count = 0
        deleted_count = 0

        # Список всех имен из загружаемой таблицы
        imported_names = set(data['name'].str.strip())

        # Получение всех текущих записей из базы данных
        existing_records = db.session.query(FederalDistrict).all()
        existing_names = {record.name for record in existing_records}

        # Удаление лишних записей (которые отсутствуют в загружаемой таблице)
        names_to_delete = existing_names - imported_names
        if names_to_delete:
            db.session.query(FederalDistrict).filter(FederalDistrict.name.in_(names_to_delete)).delete(synchronize_session=False)
            deleted_count = len(names_to_delete)

        # Обновление существующих записей и добавление новых
        for _, row in data.iterrows():
            federal_district = db.session.query(FederalDistrict).filter_by(name=row['name'].strip()).first()

            if federal_district:
                # Проверяем, есть ли изменения в записи
                if (
                    federal_district.name_full != row['name_full'].strip()
                    or federal_district.name_abr != row['name_abr'].strip()
                ):
                    federal_district.name_full = row['name_full'].strip()
                    federal_district.name_abr = row['name_abr'].strip()
                    updated_count += 1
            else:
                # Добавляем новую запись
                new_record = FederalDistrict(
                    name=row['name'].strip(),
                    name_full=row['name_full'].strip(),
                    name_abr=row['name_abr'].strip()
                )
                db.session.add(new_record)
                added_count += 1

        # Если нет изменений, данных для обновления нет
        if updated_count == 0 and added_count == 0 and deleted_count == 0:
            raise ValueError("Данные для обновления отсутствуют.")

        # Сохранение изменений в базе данных
        db.session.commit()

        # Логирование результата
        log_to_db(
            user,
            "Импорт завершён",
            f"Обновлено записей: {updated_count}, добавлено новых: {added_count}, удалено лишних: {deleted_count}"
        )
        return {
            "updated": updated_count,
            "added": added_count,
            "deleted": deleted_count
        }
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка импорта данных (IntegrityError)", str(e))
        raise ValueError("Ошибка целостности данных при импорте. Проверьте уникальность записей.")
    except ValueError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка импорта данных (ValueError)", str(e))
        raise
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка импорта данных", str(e))
        raise ValueError(f"Ошибка при импорте данных: {e}")


import pandas as pd
from io import BytesIO

def export_federal_district_to_excel(user, federal_district_filter=None, sort_by="id", sort_dir="asc"):
    """Экспортирует данные ФО в Excel и возвращает бинарный поток."""

    log_to_db(user, "Начата выгрузка таблицы ФО из базы данных")
    log_to_db(user, "Параметры экспорта", f"filter={federal_district_filter}, sort_by={sort_by}, sort_dir={sort_dir}")
    
   # Фильтрация
    query = FederalDistrict.query

    if federal_district_filter:
        query = query.filter(
            or_(
                FederalDistrict.name.ilike(f"%{federal_district_filter}%"),
                FederalDistrict.name_full.ilike(f"%{federal_district_filter}%"),
                FederalDistrict.name_abr.ilike(f"%{federal_district_filter}%")
            )
        )

    # Сортировка
    if sort_by in ["name", "name_full", "name_abr"]:
        sort_field = getattr(FederalDistrict, sort_by)
        query = query.order_by(sort_field.desc() if sort_dir == "desc" else sort_field.asc())
    else:
        query = query.order_by(FederalDistrict.id.desc() if sort_dir == "desc" else FederalDistrict.id.asc())

    federal_district_items = query.all()
    data = [{
        "№": index + 1,
        "Наименование": o.name,
        "Наименование полное": o.name_full,
        "Наименование сокращенное": o.name_abr
    } for index, o in enumerate(federal_district_items)]

    log_to_db(user, "Подготовка данных для экспорта таблицы ФО в Excel", f"Записей для экспорта: {len(data)}")

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)
    
    # Создание Excel-файла
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="ФО")

    # Возврат файла в ответе
    output.seek(0)
    log_to_db(user, "Экспорт таблицы ФО в Excel завершён", f"Экспортировано записей: {len(data)}")
    return output
