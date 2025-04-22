from app import db
from app.models.logs_models import Log
from app.models.energy_systems_models import UnionEnergySystem, RegionalEnergySystem
from app.models.territories_models import RegionalDistrict
from sqlalchemy import text
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from app.services.logging_service import log_to_db


def get_regional_energy_system_list(page, per_page, regional_energy_system_filter=None, union_energy_system_filter=None, sort_by="id", sort_dir="asc"):
    """Получает список региональных энергосистем с пагинацией, фильтрацией и сортировкой, загружая связи с субъектами РФ."""
    query = RegionalEnergySystem.query.options(
        joinedload(RegionalEnergySystem.regional_districts),  # Загружаем связи с субъектами РФ
        joinedload(RegionalEnergySystem.union_energy_system)  # Загружаем связь с ОЭС
    )

    # Фильтрация по названию региональной энергосистемы
    if regional_energy_system_filter:
        query = query.filter(RegionalEnergySystem.name.ilike(f"%{regional_energy_system_filter}%"))

    # Фильтрация по ОЭС (строго по ID)
    if union_energy_system_filter:
        query = query.filter(RegionalEnergySystem.id_union_energy_system == union_energy_system_filter)

    # Сортировка
    if sort_by == "name":
        query = query.order_by(RegionalEnergySystem.name.desc() if sort_dir == "desc" else RegionalEnergySystem.name.asc())
    elif sort_by == "name_full":
        query = query.order_by(RegionalEnergySystem.name_full.desc() if sort_dir == "desc" else RegionalEnergySystem.name_full.asc())
    elif sort_by == "union_energy_system":
        query = query.join(UnionEnergySystem).order_by(
            UnionEnergySystem.name.desc() if sort_dir == "desc" else UnionEnergySystem.name.asc()
        )
    else:
        query = query.order_by(RegionalEnergySystem.id.desc() if sort_dir == "desc" else RegionalEnergySystem.id.asc())

    # Пагинация
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return pagination


def get_total_with_filter(regional_energy_system_filter, union_energy_system_filter):
    """
    Возвращает общее количество записей региональных энергосистем, соответствующих фильтру.
    :param regional_energy_system_filter: Фильтр по имени региональные энергосистемы.
    :return: Количество записей.
    """
    query = RegionalEnergySystem.query
    if regional_energy_system_filter:
        query = query.filter(RegionalEnergySystem.name.ilike(f"%{regional_energy_system_filter}%"))

    if union_energy_system_filter:
        query = query.join(RegionalEnergySystem.union_energy_system).filter(UnionEnergySystem.name.ilike(f"%{union_energy_system_filter}%"))
    
    return query.count()


def get_union_energy_system():
    """Получает список типов энергосистем."""
    return UnionEnergySystem.query.all()


def get_regional_districts():
    """Получает список субъектов."""
    return RegionalDistrict.query.all()


def update_regional_energy_system(data, user):
    """
    Обновляет записи субъектов РФ в базе данных и связанные с ними регионы.
    :param data: Список словарей с данными для обновления. Пример:
                 [{"id": 1, "name": "Белгородская область", "union_energy_system_id": 2, "regional_districts": [1, 2, 3]}, ...]
    :param user: Имя пользователя, инициировавшего обновление.
    :raises ValueError: Если обнаружены ошибки в данных или сохранении.
    """
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    log_to_db(user, "Получены данные для обновления", f"{data}")
    try:
        for record in data:
            regional_energy_system_id = record.get("id")
            name = record.get("name")
            name_full = record.get("name_full")
            union_energy_system_id = record.get("union_energy_system_id")
            regional_district_ids = record.get("regional_districts", [])  # Список ID регионов

            # Проверки на валидность данных
            if not name or union_energy_system_id is None:
                raise ValueError(f"Каждая запись должна содержать 'name' и 'union_energy_system_id'. Данные: {record}")

            # Проверка на существующий дубликат
            duplicate = RegionalEnergySystem.query.filter(RegionalEnergySystem.name == name).filter(RegionalEnergySystem.id != regional_energy_system_id).first()
            if duplicate:
                raise ValueError(f"Запись с именем '{name}' уже существует.")

            if regional_energy_system_id:
                # Обновление существующей записи
                regional_energy_system = RegionalEnergySystem.query.get(regional_energy_system_id)
                if regional_energy_system:
                    regional_energy_system.name = name
                    regional_energy_system.name_full = name_full
                    regional_energy_system.id_union_energy_system = union_energy_system_id

                    # Обновление связей «многие ко многим»
                    existing_districts = {district.id for district in regional_energy_system.regional_districts}
                    new_districts = set(regional_district_ids)

                    # Добавить новые связи
                    for district_id in new_districts - existing_districts:
                        district = RegionalDistrict.query.get(district_id)
                        if district:
                            regional_energy_system.regional_districts.append(district)

                    # Удалить устаревшие связи
                    for district_id in existing_districts - new_districts:
                        district = RegionalDistrict.query.get(district_id)
                        if district:
                            regional_energy_system.regional_districts.remove(district)
            else:
                # Создание новой записи
                new_regional_energy_system = RegionalEnergySystem(name=name, name_full=name_full, id_union_energy_system=union_energy_system_id)
                db.session.add(new_regional_energy_system)
                db.session.flush()  # Получение ID новой записи


                # Установить связи с субъектами
                for district_id in regional_district_ids:
                    district = RegionalDistrict.query.get(district_id)
                    if district:
                        new_regional_energy_system.regional_districts.append(district)

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


def add_regional_energy_system(data, user):
    """
    Добавляет запись субъекта РФ в базе данных.
    :param data: Список словарей с данными субъектов РФ. Пример:
                 [{"id": 1, "name": "Белгородская область", "union_energy_system_id": 2}, ...]
    :param user: Имя пользователя для логирования.
    :raises ValueError: Если возникает ошибка валидации или сохранения.
    """
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    for record in data:
        regional_energy_system_id = record.get("id")
        name = record.get("name")
        name_full = record.get("name_full")
        union_energy_system_id = record.get("union_energy_system_id")
        regional_district_ids = record.get("regional_districts", [])

        # Проверка на наличие необходимых данных
        if not name or not union_energy_system_id or not regional_district_ids:
            log_to_db(user, "Ошибка валидации", f"Запись: {record}")
            raise ValueError("Каждая запись должна содержать 'name', 'union_energy_system_id' и 'regional_district_ids'.")

        if regional_energy_system_id:
            # Обновление существующей записи
            regional_energy_system = RegionalEnergySystem.query.get(regional_energy_system_id)
            if regional_energy_system:
                # Проверка на дублирование имени
                duplicate = RegionalEnergySystem.query.filter(RegionalEnergySystem.name == name, RegionalEnergySystem.id != regional_energy_system_id).first()
                if duplicate:
                    log_to_db(user, "Ошибка дублирования", f"Имя: {name}, ID: {regional_energy_system_id}")
                    raise ValueError(f"Запись с именем '{name}' уже существует.")
                
                # Обновление полей записи
                regional_energy_system.name = name
                regional_energy_system.name_full = name_full
                regional_energy_system.id_union_energy_system = union_energy_system_id
                
                # Обновление связей «многие ко многим»
                existing_districts = {district.id for district in regional_energy_system.regional_districts}
                new_districts = set(regional_district_ids)

                # Добавить новые связи
                for district_id in new_districts - existing_districts:
                    district = RegionalDistrict.query.get(district_id)
                    if district:
                        regional_energy_system.regional_districts.append(district)

                # Удалить устаревшие связи
                for district_id in existing_districts - new_districts:
                    district = RegionalDistrict.query.get(district_id)
                    if district:
                        regional_energy_system.regional_districts.remove(district)
                
                try:
                    # Сохранение изменений в базе данных
                    db.session.commit()
                    log_to_db(user, "Успешное обновление", f"Обновлено субъектов РФ ID: {regional_energy_system_id}")
                except Exception as e:
                    db.session.rollback()  # Откат транзакции в случае ошибки
                    log_to_db(user, "Ошибка сохранения", f"Ошибка при обновлении списка субъектов РФ ID: {regional_energy_system_id}, ошибка: {str(e)}")
                    raise ValueError(f"Ошибка при обновлении записи с ID {regional_energy_system_id}: {str(e)}")
            else:
                log_to_db(user, "Ошибка обновления", f"субъектов РФ с ID {regional_energy_system_id} не существует.")
                raise ValueError(f"Запись с ID {regional_energy_system_id} не найдена.")
        else:
            new_regional_energy_system = RegionalEnergySystem(name=name, name_full=name_full, id_union_energy_system=union_energy_system_id)
                       
            db.session.add(new_regional_energy_system)

            try:
                # Сохранение новой записи в базе данных
                db.session.commit()
                
                # Установить связи с субъектами
                for district_id in regional_district_ids:
                    district = RegionalDistrict.query.get(district_id)
                    if district:
                        new_regional_energy_system.regional_districts.append(district)
                db.session.commit()

                log_to_db(user, "Успешное добавление", f"Добавлен новый субъект РФ: {name}")
            except Exception as e:
                db.session.rollback()  # Откат транзакции в случае ошибки
                log_to_db(user, "Ошибка сохранения", f"Ошибка при добавлении субъекта РФ: {name}, ошибка: {str(e)}")
                raise ValueError(f"Ошибка при добавлении новой записи: {str(e)}")

def delete_regional_energy_system_list(ids, user):
    """Удаляет записи субъектов РФ по переданным ID."""
    log_to_db(user, "Удаление записей", f"Переданы ID для удаления: {ids}")

    successful_deletes = 0  # Для подсчета успешных удалений

    try:
        for regional_energy_system_id in ids:
            try:
                regional_energy_system_id = int(regional_energy_system_id)  # Приведение к целому числу
                regional_energy_system = RegionalEnergySystem.query.get(regional_energy_system_id)
                if regional_energy_system:
                    db.session.delete(regional_energy_system)
                    log_to_db(user, "Удаление записи", f"Удалён субъект РФ с ID: {regional_energy_system_id}")
            except ValueError:
                log_to_db(user, "Ошибка удаления", f"Некорректный ID: {regional_energy_system_id}")
                continue  # Пропустить ошибочные значения ID

        # Пытаемся выполнить коммит только после всех удалений
        db.session.commit()
        log_to_db(user, "Удаление завершено", f"Успешно удалено записей: {successful_deletes}")
    except Exception as e:
        # Откат всех изменений при возникновении ошибки
        db.session.rollback()
        log_to_db(user, "Ошибка удаления", str(e))
        raise ValueError("Ошибка при удалении данных.")


import pandas as pd
from sqlalchemy.exc import IntegrityError
from io import BytesIO

import pandas as pd
from sqlalchemy.exc import IntegrityError
from io import BytesIO

def import_regional_energy_system_from_excel(file, user):
    """Импортирует данные региональных энергосистем из Excel с текстовым названием ОЭС и обновляет существующие записи."""

    try:
        # Читаем данные из файла
        data = pd.read_excel(file)

        # Проверяем наличие необходимых столбцов
        required_columns = {'id', 'name', 'union_energy_system'}
        if not required_columns.issubset(data.columns):
            raise ValueError(f"Неверный формат файла. Отсутствуют необходимые столбцы: {required_columns - set(data.columns)}")

        # Удаляем пробелы в названиях столбцов (если есть)
        data.columns = data.columns.str.strip()

        imported_count = 0  # Количество успешно импортированных записей
        updated_count = 0  # Количество обновленных записей

        # Создаем словарь соответствий названия ОЭС → ID (кэш для ускорения запросов)
        oes_mapping = {oes.name: oes.id for oes in db.session.query(UnionEnergySystem).all()}

        # Обрабатываем каждую запись
        for _, row in data.iterrows():
            oes_name = row['union_energy_system'].strip()  # Название ОЭС
            oes_id = oes_mapping.get(oes_name)

            if not oes_id:
                log_to_db(user, "Предупреждение", f"ОЭС '{oes_name}' не найден в базе. Запись '{row['name']}' пропущена.")
                continue  # Пропускаем запись, если ОЭС не найден

            # Проверяем, существует ли уже такая энергосистема в БД
            record = db.session.query(RegionalEnergySystem).filter_by(id=row['id']).first()

            if record:
                # Логирование изменений перед обновлением
                old_data = f"Старая ОЭС: {record.id_union_energy_system}, Старое имя: {record.name}"
                new_data = f"Новая ОЭС: {oes_id}, Новое имя: {row['name']}"

                # Обновляем существующую запись
                record.name = row['name']
                record.id_union_energy_system = oes_id

                log_to_db(user, "Обновление записи", f"Обновлена энергосистема ID {row['id']}. {old_data} → {new_data}")
                updated_count += 1
            else:
                # Создаем новую запись
                new_record = RegionalEnergySystem(
                    id=row['id'],
                    name=row['name'],
                    id_union_energy_system=oes_id
                )
                db.session.add(new_record)
                log_to_db(user, "Добавление новой записи", f"Добавлена новая энергосистема: {row['name']} (ОЭС: {oes_name})")
                imported_count += 1  # Увеличиваем счетчик новых записей

        # Сохраняем изменения
        db.session.commit()
        log_to_db(user, "Импорт завершён", f"Добавлено записей: {imported_count}, Обновлено: {updated_count}")

        return {"imported": imported_count, "updated": updated_count}

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка импорта (IntegrityError)", str(e))
        raise ValueError("Ошибка целостности данных. Возможно, дублируются ID или имена.")

    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка импорта", str(e))
        raise ValueError(f"Ошибка при импорте данных: {e}")


import pandas as pd
from io import BytesIO

def export_regional_energy_system_to_excel(user, regional_energy_system_filter=None, union_energy_system_filter=None, sort_by="id", sort_dir="asc"):
    """Экспортирует данные списка субъектов РФ в Excel и возвращает бинарный поток."""
    log_to_db(user, "Начата выгрузка таблицы субъектов РФ из базы данных")
    log_to_db(user, "Параметры экспорта", f"regional_energy_system_filter={regional_energy_system_filter}, union_energy_system_filter={union_energy_system_filter}, sort_by={sort_by}, sort_dir={sort_dir}")

    query = RegionalEnergySystem.query

    if regional_energy_system_filter:
        query = query.filter(RegionalEnergySystem.name.ilike(f"%{regional_energy_system_filter}%"))

    if union_energy_system_filter:
        query = query.join(RegionalEnergySystem.union_energy_system).filter(UnionEnergySystem.id.ilike(f"%{union_energy_system_filter}%"))

    # Сортировка
    if sort_by == "name":
        query = query.order_by(RegionalEnergySystem.name.desc() if sort_dir == "desc" else RegionalEnergySystem.name.asc())
    elif sort_by == "union_energy_system":
        query = query.join(UnionEnergySystem).order_by(
            UnionEnergySystem.name.desc() if sort_dir == "desc" else UnionEnergySystem.name.asc()
        )
    else:
        query = query.order_by(RegionalEnergySystem.id.desc() if sort_dir == "desc" else RegionalEnergySystem.id.asc())

    # Выполнение запроса
    regional_energy_system_items = query.all()
    log_to_db(user, "Получение данных завершено", f"Найдено записей: {len(regional_energy_system_items)}")

    # Преобразование данных
    data = [{
        "Порядковый номер": idx + 1,
        "Региональная энергосистема": o.name,
        "Региональная энергосистема (полное название)": o.name_full,
        "ОЭС": o.union_energy_system.name if o.union_energy_system else "Не указан",
        "Субъекты РФ": ", ".join([district.name_full for district in o.regional_districts]) if o.regional_districts else "Не указан"
    } for idx, o in enumerate(regional_energy_system_items)]

    if not data:
        log_to_db(user, "Экспорт завершён", "Нет данных для экспорта.")
        return None

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)
    output = BytesIO()

    try:
        writer = pd.ExcelWriter(output, engine="xlsxwriter")
        df.to_excel(writer, index=False, sheet_name="Региональные энергосистемы")
        writer.close()  # Обязательно закрываем writer перед `seek(0)`
    except Exception as e:
        log_to_db(user, "Ошибка создания Excel-файла", str(e))
        raise ValueError("Ошибка при создании Excel-файла.")

    output.seek(0)
    log_to_db(user, "Экспорт таблицы субъектов РФ в Excel завершён", f"Экспортировано записей: {len(data)}")
    
    return output
