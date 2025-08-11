from app.extensions import db
from app.logs.models.logs_models import Log
from app.refdata.models.energy_systems_models import UnionEnergySystem, RegionalEnergySystem, EnergyUnit
from app.refdata.models.territories_models import RegionalDistrict
from sqlalchemy.orm import joinedload
from app.logs.services.logging_service import log_to_db


def get_energy_unit_list(page, per_page, energy_unit_filter=None, regional_district_filter=None, regional_energy_system_filter=None, union_energy_system_filter=None, sort_by="id", sort_dir="asc"):
    query = EnergyUnit.query.options(
        joinedload(EnergyUnit.regional_district)
            .joinedload(RegionalDistrict.regional_energy_systems)
    )

    # Фильтрация по названию энергоузла
    if energy_unit_filter:
        query = query.filter(EnergyUnit.name.ilike(f"%{energy_unit_filter}%"))

    # Фильтрация по субъекту РФ
    if regional_district_filter:
        query = query.join(EnergyUnit.regional_district).filter(
            RegionalDistrict.id == regional_district_filter
        )

    # Фильтрация по региональной энергосистеме
    if regional_energy_system_filter:
        query = query.join(EnergyUnit.regional_district).join(RegionalDistrict.regional_energy_systems).filter(
            RegionalEnergySystem.id == regional_energy_system_filter
        )

    # Фильтрация по ОЭС
    if union_energy_system_filter:
        query = query.join(EnergyUnit.regional_district)\
                    .join(RegionalDistrict.regional_energy_systems)\
                    .join(RegionalEnergySystem.union_energy_system)\
                    .filter(UnionEnergySystem.id == union_energy_system_filter)

    # Сортировка
    if sort_by == "name":
        query = query.order_by(EnergyUnit.name.desc() if sort_dir == "desc" else EnergyUnit.name.asc())
    elif sort_by == "regional_energy_system":
        query = query.join(EnergyUnit.regional_district)\
                    .join(RegionalDistrict.regional_energy_systems)\
                    .order_by(RegionalEnergySystem.name.desc() if sort_dir == "desc" else RegionalEnergySystem.name.asc())

    elif sort_by == "union_energy_system":
        query = query.join(EnergyUnit.regional_district)\
                    .join(RegionalDistrict.regional_energy_systems)\
                    .join(RegionalEnergySystem.union_energy_system)\
                    .order_by(UnionEnergySystem.name.desc() if sort_dir == "desc" else UnionEnergySystem.name.asc())
    else:
        query = query.order_by(EnergyUnit.id.desc() if sort_dir == "desc" else EnergyUnit.id.asc())

    # Пагинация
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    return pagination


def get_total_with_filter(energy_unit_filter, regional_district_filter, regional_energy_system_filter, union_energy_system_filter):
    query = EnergyUnit.query.options(
        joinedload(EnergyUnit.regional_district)
            .joinedload(RegionalDistrict.regional_energy_systems)
    )

    # Фильтрация по названию энергоузла
    if energy_unit_filter:
        query = query.filter(EnergyUnit.name.ilike(f"%{energy_unit_filter}%"))

    # Фильтрация по субъекту РФ
    if regional_district_filter:
        query = query.join(EnergyUnit.regional_district).filter(
            RegionalDistrict.id == regional_district_filter
        )

    # Фильтрация по региональной энергосистеме
    if regional_energy_system_filter:
        query = query.join(EnergyUnit.regional_district).join(RegionalDistrict.regional_energy_systems).filter(
            RegionalEnergySystem.id == regional_energy_system_filter
        )

    # Фильтрация по ОЭС
    if union_energy_system_filter:
        query = query.join(EnergyUnit.regional_district)\
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


def update_energy_unit(data, user):
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    for record in data:
        energy_unit_id = record.get("id")
        name = record.get("name")
        regional_district_id = record.get("regional_district_id")
        regional_energy_system_id = record.get("regional_energy_system_id")

        # Проверка на наличие необходимых данных
        if not name or not regional_district_id:
            log_to_db(user, "Ошибка валидации", f"Запись: {record}")
            raise ValueError("Каждая запись должна содержать 'name' и 'regional_district'.")

        if energy_unit_id:
            # Обновление существующей записи
            energy_unit = EnergyUnit.query.get(energy_unit_id)
            if energy_unit:
                # Проверка на дублирование имени
                duplicate = EnergyUnit.query.filter(EnergyUnit.name == name, EnergyUnit.id != energy_unit_id).first()
                if duplicate:
                    log_to_db(user, "Ошибка дублирования", f"Имя: {name}, ID: {energy_unit_id}")
                    raise ValueError(f"Запись с именем '{name}' уже существует.")
                
                # Обновление полей записи
                energy_unit.name = name
                energy_unit.id_regional_district = regional_district_id
                energy_unit.id_regional_energy_system = regional_energy_system_id
                
                try:
                    db.session.commit()
                    log_to_db(user, "Успешное обновление", f"Обновлена энергоузел ID: {energy_unit_id}")
                except Exception as e:
                    db.session.rollback()
                    log_to_db(user, "Ошибка сохранения", f"Ошибка при обновлении энергоузла с ID: {energy_unit_id}, ошибка: {str(e)}")
                    raise ValueError(f"Ошибка при обновлении записи с ID {energy_unit_id}: {str(e)}")
            else:
                log_to_db(user, "Ошибка обновления", f"энергоузел с ID {energy_unit_id} не существует.")
                raise ValueError(f"Запись энергоузла с ID {energy_unit_id} не найдена.")
        else:
            new_energy_unit = EnergyUnit(name=name, id_regional_district=regional_district_id, id_regional_energy_system = regional_energy_system_id)
                       
            db.session.add(new_energy_unit)

            try:
                db.session.commit()
                

                log_to_db(user, "Успешное добавление", f"Добавлен новый энергоузел: {name}")
            except Exception as e:
                db.session.rollback()
                log_to_db(user, "Ошибка сохранения", f"Ошибка при добавлении энергоузла: {name}, ошибка: {str(e)}")
                raise ValueError(f"Ошибка при добавлении новой записи: {str(e)}")


def add_energy_unit(data, user):
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    for record in data:
        energy_unit_id = record.get("id")
        name = record.get("name")
        regional_district_id = record.get("regional_district")
        regional_energy_system_id = record.get("regional_energy_system")

        # Проверка на наличие необходимых данных
        if not name or not regional_district_id or not regional_energy_system_id:
            log_to_db(user, "Ошибка валидации", f"Запись: {record}")
            raise ValueError("Каждая запись должна содержать 'name', 'regional_district' и 'regional_energy_system'.")

        if energy_unit_id:
            # Обновление существующей записи
            energy_unit = EnergyUnit.query.get(energy_unit_id)
            if energy_unit:
                # Проверка на дублирование имени
                duplicate = EnergyUnit.query.filter(EnergyUnit.name == name, EnergyUnit.id != energy_unit_id).first()
                if duplicate:
                    log_to_db(user, "Ошибка дублирования", f"Имя: {name}, ID: {energy_unit_id}")
                    raise ValueError(f"Запись с именем '{name}' уже существует.")
                
                # Обновление полей записи
                energy_unit.name = name
                energy_unit.id_regional_district = regional_district_id
                energy_unit.id_regional_energy_system = regional_energy_system_id
                
                try:
                    db.session.commit()
                    log_to_db(user, "Успешное обновление", f"Обновлена энергоузел ID: {energy_unit_id}")
                except Exception as e:
                    db.session.rollback()
                    log_to_db(user, "Ошибка сохранения", f"Ошибка при обновлении энергоузла с ID: {energy_unit_id}, ошибка: {str(e)}")
                    raise ValueError(f"Ошибка при обновлении записи с ID {energy_unit_id}: {str(e)}")
            else:
                log_to_db(user, "Ошибка обновления", f"энергоузел с ID {energy_unit_id} не существует.")
                raise ValueError(f"Запись энергоузла с ID {energy_unit_id} не найдена.")
        else:
            new_energy_unit = EnergyUnit(name=name, id_regional_district=regional_district_id, id_regional_energy_system=regional_energy_system_id)
                       
            db.session.add(new_energy_unit)

            try:
                db.session.commit()
                

                log_to_db(user, "Успешное добавление", f"Добавлен новый энергоузел: {name}")
            except Exception as e:
                db.session.rollback()
                log_to_db(user, "Ошибка сохранения", f"Ошибка при добавлении энергоузла: {name}, ошибка: {str(e)}")
                raise ValueError(f"Ошибка при добавлении новой записи: {str(e)}")


def delete_energy_unit_list(ids, user):
    log_to_db(user, "Удаление записей из списка энергоузлов", f"Переданы ID для удаления: {ids}")

    successful_deletes = 0

    try:
        for energy_unit_id in ids:
            energy_unit_id = int(energy_unit_id)
            energy_unit = EnergyUnit.query.get(energy_unit_id)
            if energy_unit:
                db.session.delete(energy_unit)
                log_to_db(user, "Удаление записи", f"Удален энергоузел с ID: {energy_unit_id}")

        db.session.commit()
        log_to_db(user, "Удаление энергоузла(ов) завершено", f"Успешно удалено записей: {successful_deletes}")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления энергоузла(ов)", str(e))
        raise ValueError("Ошибка при удалении данных энергоузла(ов).")


import pandas as pd
from sqlalchemy.exc import IntegrityError
from io import BytesIO

def export_energy_unit_to_excel(user, energy_unit_filter=None, regional_district_filter=None, regional_energy_system_filter=None, union_energy_system_filter=None, sort_by="id", sort_dir="asc"):
    log_to_db(user, "Начата выгрузка таблицы энергоузлов из базы данных")
    log_to_db(user, "Параметры экспорта", f"energy_unit_filter={energy_unit_filter}, regional_district_filter={regional_district_filter}, energy_unit_filter={energy_unit_filter}, union_energy_system_filter={union_energy_system_filter}, sort_by={sort_by}, sort_dir={sort_dir}")

    query = EnergyUnit.query.options(
        joinedload(EnergyUnit.regional_district)
            .joinedload(RegionalDistrict.regional_energy_systems)
    )

    # Фильтрация по названию энергоузла
    if energy_unit_filter:
        query = query.filter(EnergyUnit.name.ilike(f"%{energy_unit_filter}%"))

    # Фильтрация по субъекту РФ
    if regional_district_filter:
        query = query.join(EnergyUnit.regional_district).filter(
            RegionalDistrict.id == regional_district_filter
        )

    # Фильтрация по региональной энергосистеме
    if regional_energy_system_filter:
        query = query.join(EnergyUnit.regional_district).join(RegionalDistrict.regional_energy_systems).filter(
            RegionalEnergySystem.id == regional_energy_system_filter
        )

    # Фильтрация по ОЭС
    if union_energy_system_filter:
        query = query.join(EnergyUnit.regional_district)\
                    .join(RegionalDistrict.regional_energy_systems)\
                    .join(RegionalEnergySystem.union_energy_system)\
                    .filter(UnionEnergySystem.id == union_energy_system_filter)

    # Сортировка
    if sort_by == "name":
        query = query.order_by(EnergyUnit.name.desc() if sort_dir == "desc" else EnergyUnit.name.asc())
    elif sort_by == "regional_energy_system":
        query = query.join(EnergyUnit.regional_district)\
                    .join(RegionalDistrict.regional_energy_systems)\
                    .order_by(RegionalEnergySystem.name.desc() if sort_dir == "desc" else RegionalEnergySystem.name.asc())

    elif sort_by == "union_energy_system":
        query = query.join(EnergyUnit.regional_district)\
                    .join(RegionalDistrict.regional_energy_systems)\
                    .join(RegionalEnergySystem.union_energy_system)\
                    .order_by(UnionEnergySystem.name.desc() if sort_dir == "desc" else UnionEnergySystem.name.asc())
    else:
        query = query.order_by(EnergyUnit.id.desc() if sort_dir == "desc" else EnergyUnit.id.asc())

    # Выполнение запроса
    energy_unit_items = query.all()
    log_to_db(user, "Получение данных завершено", f"Найдено записей: {len(energy_unit_items)}")

    # Преобразование данных
    data = [{
        "№": idx + 1,
        "Энергоузел": o.name,
        "Субъект РФ": o.regional_district.name if o.regional_district else "Не указан",
        "Региональная энергосистема": o.regional_energy_system.name if o.regional_energy_system.name else "Не указана",
        "ОЭС": o.union_energy_system.name if o.union_energy_system else "Не указана",
    } for idx, o in enumerate(energy_unit_items)]

    if not data:
        log_to_db(user, "Экспорт таблицы энергоузлов завершён", "Нет данных для экспорта.")
        return None

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)
    output = BytesIO()

    try:
        writer = pd.ExcelWriter(output, engine="xlsxwriter")
        df.to_excel(writer, index=False, sheet_name="Энергоузлы")
        writer.close()  # Закрываем writer перед `seek(0)`
    except Exception as e:
        log_to_db(user, "Ошибка создания Excel-файла", str(e))
        raise ValueError("Ошибка при создании Excel-файла.")

    output.seek(0)
    log_to_db(user, "Экспорт таблицы энергоузлов в Excel завершён", f"Экспортировано записей: {len(data)}")
    
    return output
