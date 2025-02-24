from app import db
from app.models.logs_models import Log
from app.models.energy_systems_models import UnionEnergySystem, EnergySystemType
from sqlalchemy import text, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

def log_to_db(username, action, details=None):
    """Записывает лог действия пользователя в базу данных."""
    try:
        log_entry = Log(username=username, action=action, details=details)
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка записи лога: {e}")


def get_union_energy_system_list(page, per_page, union_energy_system_filter=None, energy_system_type_filter=None, sort_by="id", sort_dir="asc"):
    """Получает список ОЭС с пагинацией, фильтрацией и сортировкой."""
    
    query = UnionEnergySystem.query.options(joinedload(UnionEnergySystem.energy_system_type)).join(EnergySystemType)

    # Фильтрация
    if union_energy_system_filter:
        query = query.filter(
            or_(
                UnionEnergySystem.name.ilike(f"%{union_energy_system_filter}%"),
                UnionEnergySystem.name_full.ilike(f"%{union_energy_system_filter}%"),
            )
        )

    if energy_system_type_filter:
        query = query.filter(EnergySystemType.id == energy_system_type_filter)

    # Сортировка
    if sort_by in ["name", "name_full"]:
        sort_field = getattr(UnionEnergySystem, sort_by)
        query = query.order_by(sort_field.desc() if sort_dir == "desc" else sort_field.asc())
    elif sort_by == "energy_system_type":
        query = query.order_by(
            EnergySystemType.name.desc() if sort_dir == "desc" else EnergySystemType.name.asc()
        )
    else:
        query = query.order_by(UnionEnergySystem.id.desc() if sort_dir == "desc" else UnionEnergySystem.id.asc())


    # Пагинация
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return pagination

def get_energy_system_types():
    """Получает список типов энергосистем."""
    return EnergySystemType.query.all()


def update_union_energy_system(data, user):
    """
    Обновляет записи ОЭС в базе данных.
    :param data: Список словарей с данными для обновления. Пример:
                 [{"id": 1, "name": "ОЭС Центр", "name_full": "Объединенная энергосистема Центра", "id_energy_system_type": 2}, ...]
    :param user: Имя пользователя, инициировавшего обновление.
    :raises ValueError: Если обнаружены ошибки в данных или сохранении.
    """
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    log_to_db(user, "Получены данные для обновления", f"{data}")

    for record in data:
        id_union_energy_system = record.get("id")
        name = record.get("name")
        name_full = record.get("name_full")
        id_energy_system_type = record.get("id_energy_system_type")

        # Проверки на валидность данных
        if not name or not name_full or not id_energy_system_type:
            raise ValueError("Каждая запись должна содержать 'name', 'name_full' и 'id_energy_system_type'.")

        if id_union_energy_system:
            union_energy_system = UnionEnergySystem.query.get(id_union_energy_system)

            if not union_energy_system:
                raise ValueError(f"Запись с ID '{id_union_energy_system}' не найдена.")
            
            duplicate = UnionEnergySystem.query.filter(
                UnionEnergySystem.name == name, 
                UnionEnergySystem.id != id_union_energy_system
            ).first()
            if duplicate:
                raise ValueError(f"Запись с именем '{name}' уже существует.")
            
            union_energy_system.name = name
            union_energy_system.name_full = name_full
            union_energy_system.id_energy_system_type = id_energy_system_type
        else:
            duplicate = UnionEnergySystem.query.filter(UnionEnergySystem.name == name).first()
            if duplicate:
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            new_union_energy_system = UnionEnergySystem(
                name=name, 
                name_full=name_full, 
                id_energy_system_type=id_energy_system_type
            )
            db.session.add(new_union_energy_system)

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


def add_union_energy_system(data, user):
    """
    Добавляет или обновляет записи ОЭС в базе данных.
    :param data: Список словарей с данными ОЭС. Пример:
                 [{"id": 1, "name": "ОЭС Центр", "name_full": "Объединенная энергосистема Центра", "id_energy_system_type": 2}, ...]
    :param user: Имя пользователя для логирования.
    :raises ValueError: Если возникает ошибка валидации или сохранения.
    """
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    try:
        for record in data:
            id_union_energy_system = record.get("id")
            name = record.get("name")
            name_full = record.get("name_full")
            id_energy_system_type = record.get("id_energy_system_type")

            # Проверка на наличие необходимых данных
            if not name or not name_full or not id_energy_system_type:
                log_to_db(user, "Ошибка валидации", f"Запись: {record}")
                raise ValueError("Каждая запись должна содержать 'name', 'name_full' и 'id_energy_system_type'.")

            if id_union_energy_system:
                # Обновление существующей записи
                union_energy_system = UnionEnergySystem.query.get(id_union_energy_system)
                
                if not union_energy_system:
                    log_to_db(user, "Ошибка обновления", f"Запись с ID {id_union_energy_system} не найдена.")
                    raise ValueError(f"Запись с ID {id_union_energy_system} не найдена.")
            
                # Проверка на дублирование имени
                duplicate = UnionEnergySystem.query.filter(
                    UnionEnergySystem.name == name, 
                    UnionEnergySystem.id != id_union_energy_system
                ).first()
                if duplicate:
                    log_to_db(user, "Ошибка дублирования", f"Имя: {name}, ID: {id_union_energy_system}")
                    raise ValueError(f"Запись с именем '{name}' уже существует.")
                
                # Обновление полей записи
                union_energy_system.name = name
                union_energy_system.name_full = name_full
                union_energy_system.id_energy_system_type = id_energy_system_type
                
            else:
                # Добавление новой записи
                duplicate = UnionEnergySystem.query.filter(UnionEnergySystem.name == name).first()
                if duplicate:
                    log_to_db(user, "Ошибка дублирования", f"Имя: {name}")
                    raise ValueError(f"Запись с именем '{name}' уже существует.")

                new_union_energy_system = UnionEnergySystem(
                    name=name, 
                    name_full=name_full, 
                    id_energy_system_type=id_energy_system_type
                )
                db.session.add(new_union_energy_system)

        # Сохранение всех изменений в базе данных
        db.session.commit()
        log_to_db(user, "Успешное добавление/обновление", f"Обработано записей: {len(data)}")

    except Exception as e:
        db.session.rollback()  # Откат транзакции в случае ошибки
        log_to_db(user, "Ошибка сохранения", f"Ошибка: {str(e)}")
        raise ValueError(f"Ошибка при добавлении/обновлении записей: {str(e)}")

def get_total_union_energy_system_records(union_energy_system_filter, energy_system_type_filter):
    """
    Возвращает общее количество записей ОЭС, соответствующих фильтру.
    :param union_energy_system_filter: Фильтр по имени ОЭС.
    :return: Количество записей.
    """
    query = UnionEnergySystem.query.options(joinedload(UnionEnergySystem.energy_system_type)).join(EnergySystemType)

    # Фильтрация
    if union_energy_system_filter:
        query = query.filter(
            or_(
                UnionEnergySystem.name.ilike(f"%{union_energy_system_filter}%"),
                UnionEnergySystem.name_full.ilike(f"%{union_energy_system_filter}%"),
            )
        )

    if energy_system_type_filter:
        query = query.filter(EnergySystemType.id == energy_system_type_filter)
        
    return query.count()

def delete_union_energy_system_list(ids, user):
    """Удаляет записи ОЭС по переданным ID."""
    log_to_db(user, "Удаление записей", f"Переданы ID для удаления: {ids}")
    
    successful_deletes = 0  # Для подсчета успешных удалений

    for union_energy_system_id in ids:
        try:
            union_energy_system_id = int(union_energy_system_id)  # Приведение к целому числу
            union_energy_system = UnionEnergySystem.query.get(union_energy_system_id)
            if union_energy_system:
                db.session.delete(union_energy_system)
                successful_deletes += 1
                log_to_db(user, "Удаление записи", f"Удален ОЭС ID: {union_energy_system_id}")
            else:
                log_to_db(user, "Ошибка удаления", f"Запись с ID {union_energy_system_id} не найдена.")
        except ValueError:
            log_to_db(user, "Ошибка удаления", f"Некорректный ID: {union_energy_system_id}")

    try:
        db.session.commit()
        log_to_db(user, "Удаление завершено", f"Успешно удалено записей: {successful_deletes}")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления", str(e))
        raise ValueError("Ошибка при удалении данных.")


def import_union_energy_system_from_excel(file, user):
    """Импортирует данные ОЭС из Excel-файла в базу данных с проверкой уникальности."""
    import pandas as pd
    from sqlalchemy.exc import IntegrityError

    try:
        # Чтение данных из файла Excel
        data = pd.read_excel(file)

        # Проверка наличия обязательных столбцов
        required_columns = {'name', 'name_full', 'energy_system_type'}
        if not required_columns.issubset(data.columns):
            raise ValueError("Неверный формат файла. Отсутствуют обязательные столбцы: 'name', 'name_full', 'energy_system_type'.")

        # Очистка данных (удаление пустых строк)
        data = data.dropna(subset=['name', 'name_full', 'energy_system_type'])

        if data.empty:
            raise ValueError("Файл не содержит данных для обновления.")

        # Удаление лишних пробелов
        data['name'] = data['name'].str.strip()
        data['name_full'] = data['name_full'].str.strip()
        data['energy_system_type'] = data['energy_system_type'].str.strip()

        # Счетчики для статистики
        updated_count = 0
        added_count = 0
        deleted_count = 0

        # Получение всех текущих записей из базы данных
        existing_records = db.session.query(UnionEnergySystem).all()
        existing_names = {record.name.strip() for record in existing_records}

        # Список всех имен из загружаемой таблицы
        imported_names = set(data['name'])

        # Удаление лишних записей (которые отсутствуют в загружаемой таблице)
        names_to_delete = existing_names - imported_names
        if names_to_delete:
            db.session.query(UnionEnergySystem).filter(UnionEnergySystem.name.in_(names_to_delete)).delete(synchronize_session=False)
            deleted_count = len(names_to_delete)

        energy_system_types = {
            energy_system_type.name: energy_system_type.id
            for energy_system_type in db.session.query(EnergySystemType).all()
        }

        # Обновление существующих записей и добавление новых
        for _, row in data.iterrows():
            name = row['name']
            name_full = row['name_full']
            energy_system_type = row['energy_system_type']

            # Проверка существования федерального округа
            if energy_system_type not in energy_system_types:
                raise ValueError(f"Тип энергосистемы '{energy_system_type}' не найден в базе данных.")

            id_energy_system_type = energy_system_types[energy_system_type]

            # Проверка существования записи
            existing_record = db.session.query(UnionEnergySystem).filter_by(name=name).first()

            if existing_record:
                # Проверяем, есть ли изменения в записи
                if existing_record.name_full != name_full or existing_record.id_energy_system_type != id_energy_system_type:
                    existing_record.name_full = name_full
                    existing_record.id_energy_system_type = id_energy_system_type
                    updated_count += 1
            else:
                # Проверяем дубликаты перед добавлением
                duplicate = db.session.query(UnionEnergySystem).filter_by(
                    name=name,
                    id_energy_system_type=id_energy_system_type
                ).first()
                if duplicate:
                    raise ValueError(f"Запись с именем '{name}' и федеральным округом '{energy_system_type}' уже существует.")

                # Добавляем новую запись
                new_record = UnionEnergySystem(
                    name=name,
                    name_full=name_full,
                    id_energy_system_type=id_energy_system_type
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


def export_union_energy_system_to_excel(user, union_energy_system_filter=None, energy_system_type_filter=None, sort_by="id", sort_dir="asc"):
    """Экспортирует данные ОЭС в Excel и возвращает бинарный поток."""

    import pandas as pd
    from io import BytesIO  

    log_to_db(user, "Начата выгрузка таблицы ОЭС из базы данных")
    log_to_db(user, "Параметры экспорта", f"union_energy_system_filter={union_energy_system_filter}, sort_by={sort_by}, sort_dir={sort_dir}")
    
    query = UnionEnergySystem.query.options(joinedload(UnionEnergySystem.energy_system_type)).join(EnergySystemType)

    # Фильтрация
    if union_energy_system_filter:
        query = query.filter(
            or_(
                UnionEnergySystem.name.ilike(f"%{union_energy_system_filter}%"),
                UnionEnergySystem.name_full.ilike(f"%{union_energy_system_filter}%"),
            )
        )

    if energy_system_type_filter:
        query = query.filter(EnergySystemType.id == energy_system_type_filter)

    # Сортировка
    if sort_by in ["name", "name_full"]:
        sort_field = getattr(UnionEnergySystem, sort_by)
        query = query.order_by(sort_field.desc() if sort_dir == "desc" else sort_field.asc())
    elif sort_by == "energy_system_type":
    
        query = query.order_by(
            EnergySystemType.name.desc() if sort_dir == "desc" else EnergySystemType.name.asc()
        )
    else:
        query = query.order_by(UnionEnergySystem.id.desc() if sort_dir == "desc" else UnionEnergySystem.id.asc())

    union_energy_system_items = query.all()
    data = [{
        "ID": index + 1,
        "Наименование ОЭС": o.name,
        "Полное наименование ОЭС": o.name_full,
        "Тип энергосистемы": o.energy_system_type.name if o.energy_system_type else "Не указан"
    } for index, o in enumerate(union_energy_system_items)]

    log_to_db(user, "Подготовка данных для экспорта таблицы ОЭС в Excel", f"Записей для экспорта: {len(data)}")

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)
    
    # Создание Excel-файла
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="ОЭС")

    # Возврат файла в ответе
    output.seek(0)
    log_to_db(user, "Экспорт таблицы ОЭС в Excel завершён", f"Экспортировано записей: {len(data)}")
    return output
