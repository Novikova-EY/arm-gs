from app.extensions import db
from app.logs.models.logs_models import Log
from app.refdata.models.energy_systems_models import UnionEnergySystem, RegionalEnergySystem, EnergyArea
from app.refdata.models.territories_models import RegionalDistrict
from sqlalchemy.orm import joinedload
from app.logs.services.logging_service import log_to_db
from app.generation.services.station_services.help_services import get_energy_units

def get_energy_area_list(page, per_page, energy_area_filter=None, regional_district_filter=None, regional_energy_system_filter=None, union_energy_system_filter=None, sort_by="id", sort_dir="asc"):
    query = EnergyArea.query.options(
        joinedload(EnergyArea.regional_district)
            .joinedload(RegionalDistrict.regional_energy_systems)
    )

    # Фильтрация по названию энергорайона
    if energy_area_filter:
        query = query.filter(EnergyArea.name.ilike(f"%{energy_area_filter}%"))

    # Фильтрация по субъекту РФ
    if regional_district_filter:
        query = query.join(EnergyArea.regional_district).filter(
            RegionalDistrict.id == regional_district_filter
        )

    # Фильтрация по региональной энергосистеме
    if regional_energy_system_filter:
        query = query.join(EnergyArea.regional_district).join(RegionalDistrict.regional_energy_systems).filter(
            RegionalEnergySystem.id == regional_energy_system_filter
        )

    # Фильтрация по ОЭС
    if union_energy_system_filter:
        query = query.join(EnergyArea.regional_district)\
                    .join(RegionalDistrict.regional_energy_systems)\
                    .join(RegionalEnergySystem.union_energy_system)\
                    .filter(UnionEnergySystem.id == union_energy_system_filter)

    # Сортировка
    if sort_by == "name":
        query = query.order_by(EnergyArea.name.desc() if sort_dir == "desc" else EnergyArea.name.asc())
    elif sort_by == "regional_energy_system":
        query = query.join(EnergyArea.regional_district)\
                    .join(RegionalDistrict.regional_energy_systems)\
                    .order_by(RegionalEnergySystem.name.desc() if sort_dir == "desc" else RegionalEnergySystem.name.asc())

    elif sort_by == "union_energy_system":
        query = query.join(EnergyArea.regional_district)\
                    .join(RegionalDistrict.regional_energy_systems)\
                    .join(RegionalEnergySystem.union_energy_system)\
                    .order_by(UnionEnergySystem.name.desc() if sort_dir == "desc" else UnionEnergySystem.name.asc())
    else:
        query = query.order_by(EnergyArea.id.desc() if sort_dir == "desc" else EnergyArea.id.asc())

    # Пагинация
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return pagination


def get_total_with_filter(energy_area_filter, regional_district_filter, regional_energy_system_filter, union_energy_system_filter):
    query = EnergyArea.query.options(
        joinedload(EnergyArea.regional_district)
            .joinedload(RegionalDistrict.regional_energy_systems)
    )

    # Фильтрация по названию энергорайона
    if energy_area_filter:
        query = query.filter(EnergyArea.name.ilike(f"%{energy_area_filter}%"))

    # Фильтрация по субъекту РФ
    if regional_district_filter:
        query = query.join(EnergyArea.regional_district).filter(
            RegionalDistrict.id == regional_district_filter
        )

    # Фильтрация по региональной энергосистеме
    if regional_energy_system_filter:
        query = query.join(EnergyArea.regional_district).join(RegionalDistrict.regional_energy_systems).filter(
            RegionalEnergySystem.id == regional_energy_system_filter
        )

    # Фильтрация по ОЭС
    if union_energy_system_filter:
        query = query.join(EnergyArea.regional_district)\
                    .join(RegionalDistrict.regional_energy_systems)\
                    .join(RegionalEnergySystem.union_energy_system)\
                    .filter(UnionEnergySystem.id == union_energy_system_filter)

    return query.count()


def get_regional_districts():
    return RegionalDistrict.query.all()


def get_regional_energy_system():
    return RegionalEnergySystem.query.all()


def get_union_energy_system():
    return UnionEnergySystem.query.all()


def update_energy_area(data, user):
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    for record in data:
        energy_area_id = record.get("id")
        name = record.get("name")
        regional_district_id = record.get("regional_district_id")

        # Проверка на наличие необходимых данных
        if not name or not regional_district_id:
            log_to_db(user, "Ошибка валидации", f"Запись: {record}")
            raise ValueError("Каждая запись должна содержать 'name' и 'regional_district'.")

        if energy_area_id:
            # Обновление существующей записи
            energy_area = EnergyArea.query.get(energy_area_id)
            if energy_area:
                # Проверка на дублирование имени
                duplicate = EnergyArea.query.filter(EnergyArea.name == name, EnergyArea.id != energy_area_id).first()
                if duplicate:
                    log_to_db(user, "Ошибка дублирования", f"Имя: {name}, ID: {energy_area_id}")
                    raise ValueError(f"Запись с именем '{name}' уже существует.")
                
                # Обновление полей записи
                energy_area.name = name
                energy_area.id_regional_district = regional_district_id
                
                try:
                    db.session.commit()
                    get_energy_units.cache_clear()
                    log_to_db(user, "Успешное обновление", f"Обновлен энергорайон ID: {energy_area_id}")
                except Exception as e:
                    db.session.rollback()
                    log_to_db(user, "Ошибка сохранения", f"Ошибка при обновлении энергорайона с ID: {energy_area_id}, ошибка: {str(e)}")
                    raise ValueError(f"Ошибка при обновлении записи с ID {energy_area_id}: {str(e)}")
            else:
                log_to_db(user, "Ошибка обновления", f"энергорайона с ID {energy_area_id} не существует.")
                raise ValueError(f"Запись энергорайона с ID {energy_area_id} не найдена.")
        else:
            new_energy_area = EnergyArea(name=name, id_regional_district=regional_district_id)
                       
            db.session.add(new_energy_area)

            try:
                db.session.commit()
                get_energy_units.cache_clear()
                log_to_db(user, "Успешное добавление", f"Добавлен новый энергорайон: {name}")
            except Exception as e:
                db.session.rollback()
                log_to_db(user, "Ошибка сохранения", f"Ошибка при добавлении энергорайона: {name}, ошибка: {str(e)}")
                raise ValueError(f"Ошибка при добавлении новой записи: {str(e)}")


def add_energy_area(data, user):
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    for record in data:
        energy_area_id = record.get("id")
        name = record.get("name")
        regional_district_id = record.get("regional_district")

        # Проверка на наличие необходимых данных
        if not name or not regional_district_id:
            log_to_db(user, "Ошибка валидации", f"Запись: {record}")
            raise ValueError("Каждая запись должна содержать 'name' и 'regional_district'.")

        if energy_area_id:
            # Обновление существующей записи
            energy_area = EnergyArea.query.get(energy_area_id)
            if energy_area:
                # Проверка на дублирование имени
                duplicate = EnergyArea.query.filter(EnergyArea.name == name, EnergyArea.id != energy_area_id).first()
                if duplicate:
                    log_to_db(user, "Ошибка дублирования", f"Имя: {name}, ID: {energy_area_id}")
                    raise ValueError(f"Запись с именем '{name}' уже существует.")
                
                # Обновление полей записи
                energy_area.name = name
                energy_area.id_regional_district = regional_district_id
                
                try:
                    db.session.commit()
                    get_energy_units.cache_clear()
                    log_to_db(user, "Успешное обновление", f"Обновлен энергорайон ID: {energy_area_id}")
                except Exception as e:
                    db.session.rollback()
                    log_to_db(user, "Ошибка сохранения", f"Ошибка при обновлении энергорайона с ID: {energy_area_id}, ошибка: {str(e)}")
                    raise ValueError(f"Ошибка при обновлении записи с ID {energy_area_id}: {str(e)}")
            else:
                log_to_db(user, "Ошибка обновления", f"энергорайона с ID {energy_area_id} не существует.")
                raise ValueError(f"Запись энергорайона с ID {energy_area_id} не найдена.")
        else:
            new_energy_area = EnergyArea(name=name, id_regional_district=regional_district_id)
            db.session.add(new_energy_area)

            try:
                db.session.commit()
                get_energy_units.cache_clear()
                log_to_db(user, "Успешное добавление", f"Добавлен новый энергорайон: {name}")
            except Exception as e:
                db.session.rollback()
                log_to_db(user, "Ошибка сохранения", f"Ошибка при добавлении энергорайона: {name}, ошибка: {str(e)}")
                raise ValueError(f"Ошибка при добавлении новой записи: {str(e)}")


def delete_energy_area_list(ids, user):
    log_to_db(user, "Удаление записей из списка энергорайонов", f"Переданы ID для удаления: {ids}")

    successful_deletes = 0

    try:
        for energy_area_id in ids:
            try:
                energy_area_id = int(energy_area_id)
                energy_area = EnergyArea.query.get(energy_area_id)
                if energy_area:
                    db.session.delete(energy_area)
                    log_to_db(user, "Удаление записи", f"Удалён энергорайон с ID: {energy_area_id}")
            except ValueError:
                log_to_db(user, "Ошибка удаления энергорайона", f"Некорректный ID: {energy_area_id}")
                continue

        db.session.commit()
        get_energy_units.cache_clear()
        log_to_db(user, "Удаление энергорайона(ов) завершено", f"Успешно удалено записей: {successful_deletes}")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления энергорайона(ов)", str(e))
        raise ValueError("Ошибка при удалении данных энергорайона(ов).")


import pandas as pd
from sqlalchemy.exc import IntegrityError
from io import BytesIO

def export_energy_area_to_excel(user, energy_area_filter=None, regional_district_filter=None, regional_energy_system_filter=None, union_energy_system_filter=None, sort_by="id", sort_dir="asc"):
    log_to_db(user, "Начата выгрузка таблицы субъектов РФ из базы данных")
    log_to_db(user, "Параметры экспорта", f"energy_area_filter={energy_area_filter}, union_energy_system_filter={union_energy_system_filter}, sort_by={sort_by}, sort_dir={sort_dir}")

    query = EnergyArea.query.options(
        joinedload(EnergyArea.regional_district)
            .joinedload(RegionalDistrict.regional_energy_systems)
    )

    # Фильтрация по названию энергорайона
    if energy_area_filter:
        query = query.filter(EnergyArea.name.ilike(f"%{energy_area_filter}%"))

    # Фильтрация по субъекту РФ
    if regional_district_filter:
        query = query.join(EnergyArea.regional_district).filter(
            RegionalDistrict.id == regional_district_filter
        )

    # Фильтрация по региональной энергосистеме
    if regional_energy_system_filter:
        query = query.join(EnergyArea.regional_district).join(RegionalDistrict.regional_energy_systems).filter(
            RegionalEnergySystem.id == regional_energy_system_filter
        )

    # Фильтрация по ОЭС
    if union_energy_system_filter:
        query = query.join(EnergyArea.regional_district)\
                    .join(RegionalDistrict.regional_energy_systems)\
                    .join(RegionalEnergySystem.union_energy_system)\
                    .filter(UnionEnergySystem.id == union_energy_system_filter)

    # Сортировка
    if sort_by == "name":
        query = query.order_by(EnergyArea.name.desc() if sort_dir == "desc" else EnergyArea.name.asc())
    elif sort_by == "regional_energy_system":
        query = query.join(EnergyArea.regional_district)\
                    .join(RegionalDistrict.regional_energy_systems)\
                    .order_by(RegionalEnergySystem.name.desc() if sort_dir == "desc" else RegionalEnergySystem.name.asc())

    elif sort_by == "union_energy_system":
        query = query.join(EnergyArea.regional_district)\
                    .join(RegionalDistrict.regional_energy_systems)\
                    .join(RegionalEnergySystem.union_energy_system)\
                    .order_by(UnionEnergySystem.name.desc() if sort_dir == "desc" else UnionEnergySystem.name.asc())
    else:
        query = query.order_by(EnergyArea.id.desc() if sort_dir == "desc" else EnergyArea.id.asc())

    # Выполнение запроса
    energy_area_items = query.all()
    log_to_db(user, "Получение данных завершено", f"Найдено записей: {len(energy_area_items)}")

    # Преобразование данных
    data = [{
        "№": idx + 1,
        "Энергорайон": o.name,
        "Субъект РФ": o.regional_district.name if o.regional_district else "Не указан",
        "Региональная энергосистема": o.regional_energy_system.name if o.regional_energy_system.name else "Не указана",
        "ОЭС": o.union_energy_system.name if o.union_energy_system else "Не указана",
    } for idx, o in enumerate(energy_area_items)]

    if not data:
        log_to_db(user, "Экспорт таблицы энергорайонов завершён", "Нет данных для экспорта.")
        return None

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)
    output = BytesIO()

    try:
        writer = pd.ExcelWriter(output, engine="xlsxwriter")
        df.to_excel(writer, index=False, sheet_name="Энергорайоны")
        writer.close()  # Закрываем writer перед `seek(0)`
    except Exception as e:
        log_to_db(user, "Ошибка создания Excel-файла", str(e))
        raise ValueError("Ошибка при создании Excel-файла.")

    output.seek(0)
    log_to_db(user, "Экспорт таблицы энергорайонов в Excel завершён", f"Экспортировано записей: {len(data)}")
    
    return output
