from app import db
from app.models.logs_models import Log
from app.models.territories_models import FederalDistrict, RegionalDistrict
from sqlalchemy import text, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from app.services.logging_service import log_to_db


def get_regional_district_list(page, per_page, regional_district_filter=None, federal_district_filter=None, sort_by="id", sort_dir="asc"):
    """Получает список субъектов РФ с пагинацией, фильтрацией и сортировкой."""

    query = RegionalDistrict.query.options(joinedload(RegionalDistrict.federal_district)).join(FederalDistrict)

    # Фильтрация
    if regional_district_filter:
        query = query.filter(
            or_(
                RegionalDistrict.name.ilike(f"%{regional_district_filter}%"),
                RegionalDistrict.name_full.ilike(f"%{regional_district_filter}%"),
            )
        )

    if federal_district_filter:
        query = query.filter(FederalDistrict.id == int(federal_district_filter))

    # Сортировка
    if sort_by in ["name", "name_full"]:
        sort_field = getattr(RegionalDistrict, sort_by)
        query = query.order_by(sort_field.desc() if sort_dir == "desc" else sort_field.asc())
    elif sort_by == "federal_district":
    
        query = query.order_by(
            FederalDistrict.name.desc() if sort_dir == "desc" else FederalDistrict.name.asc()
        )
    else:
        query = query.order_by(RegionalDistrict.id.desc() if sort_dir == "desc" else RegionalDistrict.id.asc())


    # Пагинация
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return pagination


def get_federal_district_list():
    """Получает список типов энергосистем."""
    return FederalDistrict.query.all()


def update_regional_district(data, user):
    """
    Обновляет запись субъекта РФ в базе данных.
    :param data: Список словарей с данными для обновления. Пример:
                 [{"id": 1, "name": "Белгородская область", "name_full": "Белгородская область", "id_federal_district": 2}, ...]
    :param user: Имя пользователя, инициировавшего обновление.
    :raises ValueError: Если обнаружены ошибки в данных или сохранении.
    """
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    log_to_db(user, "Получены данные для обновления", f"{data}")

    for record in data:
        id_regional_district = record.get("id")
        name = record.get("name")
        name_full = record.get("name_full")
        id_federal_district = record.get("id_federal_district")

        # Проверки на валидность данных
        if not name or not name_full or not id_federal_district:
            raise ValueError("Каждая запись должна содержать 'name', 'name_full' и 'id_federal_district'.")

        if id_regional_district:
            regional_district = RegionalDistrict.query.get(id_regional_district)

            if not regional_district:
                raise ValueError(f"Запись с ID '{id_regional_district}' не найдена.")

            duplicate = RegionalDistrict.query.filter(
                RegionalDistrict.name == name,
                RegionalDistrict.id != id_regional_district
            ).first()
            if duplicate:
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            regional_district.name = name
            regional_district.name_full = name_full
            regional_district.id_federal_district = id_federal_district
        else:
            duplicate = RegionalDistrict.query.filter(RegionalDistrict.name == name).first()
            if duplicate:
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            new_regional_district = RegionalDistrict(
                name=name, 
                name_full=name_full, 
                id_federal_district=id_federal_district
            )
            db.session.add(new_regional_district)

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


def add_regional_district(data, user):
    """
    Добавляет запись субъекта РФ в базе данных.
    :param data: Список словарей с данными субъектов РФ. Пример:
                 [{"id": 1, "name": "Белгородская область", "name_full": "Белгородская область", "id_federal_district": 2}, ...]
    :param user: Имя пользователя для логирования.
    :raises ValueError: Если возникает ошибка валидации или сохранения.
    """
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    log_to_db(user, "Получены данные для добавления", f"{data}")

    try:
        for record in data:
            id_regional_district = record.get("id")
            name = record.get("name")
            name_full = record.get("name_full")
            id_federal_district = record.get("id_federal_district")

            # Проверка на наличие необходимых данных
            if not name or not name_full or not id_federal_district:
                log_to_db(user, "Ошибка валидации", f"Запись: {record}")
                raise ValueError("Каждая запись должна содержать 'name', 'name_full' и 'id_federal_district'.")

            if id_regional_district:
                # Обновление существующей записи
                regional_district = RegionalDistrict.query.get(id_regional_district)

                if not regional_district:
                    log_to_db(user, "Ошибка обновления", f"Запись с ID {id_regional_district} не найдена.")
                    raise ValueError(f"Запись с ID {id_regional_district} не найдена.")

                # Проверка на дублирование имени
                duplicate = RegionalDistrict.query.filter(
                    RegionalDistrict.name == name,
                    RegionalDistrict.id != id_regional_district
                ).first()
                if duplicate:
                    log_to_db(user, "Ошибка дублирования", f"Имя: {name}, ID: {id_regional_district}")
                    raise ValueError(f"Запись с именем '{name}' уже существует.")

                # Обновление полей
                regional_district.name = name
                regional_district.name_full = name_full
                regional_district.id_federal_district = id_federal_district
            else:
                # Добавление новой записи
                duplicate = RegionalDistrict.query.filter(RegionalDistrict.name == name).first()
                if duplicate:
                    log_to_db(user, "Ошибка дублирования", f"Имя: {name}")
                    raise ValueError(f"Запись с именем '{name}' уже существует.")

                new_regional_district = RegionalDistrict(
                    name=name, 
                    name_full=name_full, 
                    id_federal_district=id_federal_district
                )
                db.session.add(new_regional_district)

        # Сохранение всех изменений в базе данных
        db.session.commit()
        log_to_db(user, "Успешное добавление/обновление", f"Обработано записей: {len(data)}")

    except Exception as e:
        db.session.rollback()  # Откат транзакции в случае ошибки
        log_to_db(user, "Ошибка сохранения", f"Ошибка: {str(e)}")
        raise ValueError(f"Ошибка при добавлении/обновлении записей: {str(e)}")


def get_total_regional_district_records(regional_district_filter, federal_district_filter):
    """
    Возвращает общее количество записей субъектов РФ, соответствующих фильтру.
    :param regional_district_filter: Фильтр по имени субъекта РФ.
    :return: Количество записей.
    """
    query = RegionalDistrict.query.options(joinedload(RegionalDistrict.federal_district)).join(FederalDistrict)

    # Фильтрация
    if regional_district_filter:
        query = query.filter(
            or_(
                RegionalDistrict.name.ilike(f"%{regional_district_filter}%"),
                RegionalDistrict.name_full.ilike(f"%{regional_district_filter}%"),
            )
        )

    if federal_district_filter:
        query = query.filter(
            or_(
                FederalDistrict.name.ilike(f"%{federal_district_filter}%"),
                FederalDistrict.name_full.ilike(f"%{federal_district_filter}%"),
                FederalDistrict.name_abr.ilike(f"%{federal_district_filter}%")
            )
        )

    return query.count()

def delete_regional_district_list(ids, user):
    """Удаляет записи субъектов РФ по переданным ID."""
    log_to_db(user, "Удаление записей", f"Переданы ID для удаления: {ids}")
    
    successful_deletes = 0  # Для подсчета успешных удалений

    for id_regional_district in ids:
        try:
            id_regional_district = int(id_regional_district)  # Приведение к целому числу
            regional_district = RegionalDistrict.query.get(id_regional_district)
            if regional_district:
                db.session.delete(regional_district)
                successful_deletes += 1
                log_to_db(user, "Удаление записи", f"Удалён субъект РФ с ID: {id_regional_district}")
            else:
                log_to_db(user, "Ошибка удаления", f"Запись с ID {id_regional_district} не найдена.")
        except ValueError:
            log_to_db(user, "Ошибка удаления", f"Некорректный ID: {id_regional_district}")

    try:
        db.session.commit()
        log_to_db(user, "Удаление завершено", f"Успешно удалено записей: {successful_deletes}")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления", str(e))
        raise ValueError("Ошибка при удалении данных.")


def import_regional_district_from_excel(file, user):
    """Импортирует данные субъектов РФ из Excel-файла в базу данных с проверкой уникальности."""
    import pandas as pd
    from sqlalchemy.exc import IntegrityError

    try:
        # Чтение данных из файла Excel
        data = pd.read_excel(file)

        # Проверка наличия обязательных столбцов
        required_columns = {'name', 'name_full', 'federal_district_name'}
        if not required_columns.issubset(data.columns):
            raise ValueError("Неверный формат файла. Отсутствуют обязательные столбцы: 'name', 'name_full', 'federal_district_name'.")

        # Очистка данных (удаление пустых строк)
        data = data.dropna(subset=['name', 'name_full', 'federal_district_name'])

        if data.empty:
            raise ValueError("Файл не содержит данных для обновления.")

        # Удаление лишних пробелов
        data['name'] = data['name'].str.strip()
        data['name_full'] = data['name_full'].str.strip()
        data['federal_district_name'] = data['federal_district_name'].str.strip()

        # Счетчики для статистики
        updated_count = 0
        added_count = 0
        deleted_count = 0

        # Получение всех текущих записей из базы данных
        existing_records = db.session.query(RegionalDistrict).all()
        existing_names = {record.name.strip() for record in existing_records}

        # Список всех имен из загружаемой таблицы
        imported_names = set(data['name'])

        # Удаление лишних записей (которые отсутствуют в загружаемой таблице)
        names_to_delete = existing_names - imported_names
        if names_to_delete:
            db.session.query(RegionalDistrict).filter(RegionalDistrict.name.in_(names_to_delete)).delete(synchronize_session=False)
            deleted_count = len(names_to_delete)

        # Получение словаря {federal_district_name: id_federal_district}
        federal_districts = {
            district.name: district.id
            for district in db.session.query(FederalDistrict).all()
        }

        # Обновление существующих записей и добавление новых
        for _, row in data.iterrows():
            name = row['name']
            name_full = row['name_full']
            federal_district_name = row['federal_district_name']

            # Проверка существования федерального округа
            if federal_district_name not in federal_districts:
                raise ValueError(f"Федеральный округ '{federal_district_name}' не найден в базе данных.")

            id_federal_district = federal_districts[federal_district_name]

            # Проверка существования записи
            existing_record = db.session.query(RegionalDistrict).filter_by(name=name).first()

            if existing_record:
                # Проверяем, есть ли изменения в записи
                if existing_record.name_full != name_full or existing_record.id_federal_district != id_federal_district:
                    existing_record.name_full = name_full
                    existing_record.id_federal_district = id_federal_district
                    updated_count += 1
            else:
                # Проверяем дубликаты перед добавлением
                duplicate = db.session.query(RegionalDistrict).filter_by(
                    name=name,
                    id_federal_district=id_federal_district
                ).first()
                if duplicate:
                    raise ValueError(f"Запись с именем '{name}' и федеральным округом '{federal_district_name}' уже существует.")

                # Добавляем новую запись
                new_record = RegionalDistrict(
                    name=name,
                    name_full=name_full,
                    id_federal_district=id_federal_district
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


def export_regional_district_to_excel(user, regional_district_filter=None, federal_district_filter=None, sort_by="id", sort_dir="asc"):
    """Экспортирует данные списка субъектов РФ в Excel и возвращает бинарный поток."""

    import pandas as pd
    from io import BytesIO  

    log_to_db(user, "Начата выгрузка таблицы субъектов РФ из базы данных")
    log_to_db(user, "Параметры экспорта", f"regional_district_filter={regional_district_filter}, sort_by={sort_by}, sort_dir={sort_dir}")
    
    query = RegionalDistrict.query.options(joinedload(RegionalDistrict.federal_district)).join(FederalDistrict)

    # Фильтрация
    if regional_district_filter:
        query = query.filter(
            or_(
                RegionalDistrict.name.ilike(f"%{regional_district_filter}%"),
                RegionalDistrict.name_full.ilike(f"%{regional_district_filter}%"),
            )
        )

    if federal_district_filter:
        query = query.filter(FederalDistrict.id == int(federal_district_filter))

    # Сортировка
    if sort_by in ["name", "name_full"]:
        sort_field = getattr(RegionalDistrict, sort_by)
        query = query.order_by(sort_field.desc() if sort_dir == "desc" else sort_field.asc())
    elif sort_by == "federal_district":
    
        query = query.order_by(
            FederalDistrict.name.desc() if sort_dir == "desc" else FederalDistrict.name.asc()
        )
    else:
        query = query.order_by(RegionalDistrict.id.desc() if sort_dir == "desc" else RegionalDistrict.id.asc())

    regional_district_items = query.all()
    data = [{
        "№": index + 1,
        "Наименование субъекта РФ": o.name,
        "Полное наименование субъекта РФ": o.name_full,
        "Наименование ФО": o.federal_district.name if o.federal_district else "Не указан"
    } for index, o in enumerate(regional_district_items)]

    log_to_db(user, "Подготовка данных для экспорта таблицы субъектов РФ в Excel", f"Записей для экспорта: {len(data)}")

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)
    
    # Создание Excel-файла
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Cубъекты РФ")

    # Возврат файла в ответе
    output.seek(0)
    log_to_db(user, "Экспорт таблицы субъектов РФ в Excel завершён", f"Экспортировано записей: {len(data)}")
    return output
