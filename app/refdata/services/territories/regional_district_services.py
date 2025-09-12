"""Сервисный модуль: Субъекты РФ."""

from app.extensions import db
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 

# Модели
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea

from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.territories.federal_district_model import FederalDistrict

# Сервисы
from app.common.services.get_services.energy_systems.energy_zone_get_services import (
    get_energy_zone_name,
)
from app.common.services.get_services.energy_systems.synchronous_area_get_services import (
    get_synchronous_area_name,
)
from app.common.services.get_services.territories.federal_district_get_services import (
    get_federal_district_name,
)
from app.common.services.help_services import (
    _dash,
    _to_int_or_none,
)
from app.common.services.tranzaction_services import (
    _commit_with_retry,
    _locked_get,
    no_autoflush,
)

# Логирование
from app.logs.services.logging_service import log_to_db


def regional_district_query(
    regional_district_filter=None,
    federal_district_filter=None,
    energy_zone_filter=None,
    synchronous_area_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """ Базовый запрос для выборки субъектов РФ с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id","name","federal_district","energy_zone","synchronous_area","region_id"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Безопасная конвертация ID-фильтров
    federal_district_id = _to_int_or_none(federal_district_filter)
    energy_zone_id = _to_int_or_none(energy_zone_filter)
    synchronous_area_id = _to_int_or_none(synchronous_area_filter)

    # Базовый запрос
    query = (
        RegionalDistrict.query
        .options(
            joinedload(RegionalDistrict.federal_district),
            joinedload(RegionalDistrict.energy_zone),
            joinedload(RegionalDistrict.synchronous_area),
        )
        .join(FederalDistrict)
        .outerjoin(EnergyZone, RegionalDistrict.energy_zone)
        .outerjoin(SynchronousArea, RegionalDistrict.synchronous_area)
        .filter(RegionalDistrict.id.isnot(None), RegionalDistrict.id > 0)
    )
        
    # Фильтрация
    if regional_district_filter:
        rd = regional_district_filter.strip()
        if rd:
            query = query.filter(
                or_(
                    RegionalDistrict.name.ilike(f"%{rd}%"),
                    RegionalDistrict.name_full.ilike(f"%{rd}%"),
                )
            )

    if energy_zone_id is not None:
        query = query.filter(RegionalDistrict.id_energy_zone == energy_zone_id)

    if synchronous_area_id is not None:
        query = query.filter(RegionalDistrict.id_synchronous_area == synchronous_area_id)

    if federal_district_id is not None:
        query = query.filter(FederalDistrict.id == federal_district_id)

    # Сортировка
    if sort_by == "name":
        sort_col = RegionalDistrict.name
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    elif sort_by == "region_id":
        sort_col = RegionalDistrict.region_id
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    elif sort_by == "federal_district":
        sort_col = FederalDistrict.name
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    elif sort_by == "energy_zone":
        query = query.join(EnergyZone, isouter=True)
        sort_col = EnergyZone.name
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    elif sort_by == "synchronous_area":
        query = query.join(SynchronousArea, isouter=True)
        sort_col = SynchronousArea.name
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    else:  # "id" (по умолчанию)
        sort_col = RegionalDistrict.id
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    # Исключаем запись "Не указано" (id=0)
    query = query.filter(RegionalDistrict.id.isnot(None), RegionalDistrict.id > 0)

    return query


@no_autoflush
def get_regional_district_list(
    page,
    per_page,
    regional_district_filter=None,
    federal_district_filter=None,
    energy_zone_filter=None,
    synchronous_area_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """ Получает список субъектов РФ с пагинацией, фильтрацией и сортировкой. """

    # Базовый запрос
    query = regional_district_query(
        regional_district_filter=regional_district_filter,
        federal_district_filter=federal_district_filter,
        energy_zone_filter=energy_zone_filter,
        synchronous_area_filter=synchronous_area_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_regional_district_service(data, user):
    """ Обновление данных по субъектам РФ. """

    if not isinstance(data, list) or not data:
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []
    
    log_to_db(user, "Получены данные для обновления списка субъектов РФ", 
              f"{data}")
    
    with db.session.no_autoflush:
        for record in data:
            regional_district_id = _to_int_or_none(record.get("id"), keep_zero=False)
            region_id = _to_int_or_none(record.get("region_id"), keep_zero=False)
            name = (record.get("name") or "").strip()
            name_full = (record.get("name_full") or "").strip() or None

            # Проверки на валидность данных
            if not name:
                log_to_db(user, "Ошибка валидации", 
                          f"Запись: {record}")
                raise ValueError("Поле 'name' обязательно для заполнения. Данные: {record}")

            obj = db.session.get(RegionalDistrict, regional_district_id)
            if not obj:
                log_to_db(user, "Ошибка валидации", 
                          f"Запись с ID «{regional_district_id}» не найдена.")
                raise ValueError(f"Запись с ID «{regional_district_id}» не найдена.")

            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (RegionalDistrict.query
                     .filter(RegionalDistrict.name == name,
                             RegionalDistrict.id != regional_district_id))
                if q.first():
                    log_to_db(user, "Ошибка валидации", 
                              f"Запись с наименованием «{name}» уже существует.")
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
            # Проверка уникальности name_full
            if name_full != (obj.name_full or ""):
                q_full = (RegionalDistrict.query
                     .filter(RegionalDistrict.name_full == name_full,
                             RegionalDistrict.id != regional_district_id))
                if q_full.first():
                    log_to_db(user, "Ошибка валидации", 
                              f"Запись с полным наименованием «{name_full}» уже существует.")
                    raise ValueError(f"Запись с полным наименованием «{name_full}» уже существует.")

            changes = {}

            if name != (obj.name or ""):
                changes["Наименование"] = f"{_dash(obj.name)} → {name}"
                obj.name = name

            if name_full != (obj.name_full or None):
                changes["Полное наименование"] = f"{_dash(obj.name_full)} → {_dash(name_full)}"
                obj.name_full = name_full

            if region_id != obj.region_id:
                changes["Порядковый номер субъекта РФ"] = f"{_dash(obj.region_id)} → {_dash(region_id)}"
                obj.region_id = region_id

            # Проверка наличия ФО
            if "federal_district_id" in record:
                new_val = _to_int_or_none(record.get("federal_district_id"), keep_zero=False)
                if new_val != obj.id_federal_district:
                    new_obj = db.session.get(FederalDistrict, new_val) if new_val is not None else None
                    if new_val is not None and not new_obj:
                        raise ValueError(f"Федеральный округ с id={new_val} не найден.")
                    
                    prev_obj = db.session.get(FederalDistrict, obj.id_federal_district) if obj.id_federal_district else None
                    changes["Федеральный округ"] = f"{_dash(prev_obj.name if prev_obj else None)} → {_dash(new_obj.name if new_obj else None)}"
                    obj.id_federal_district = new_val

            # Проверка наличия энергозоны
            if "energy_zone_id" in record:
                new_val = _to_int_or_none(record.get("energy_zone_id"), keep_zero=True)
                if new_val != obj.id_energy_zone:
                    new_obj = db.session.get(EnergyZone, new_val) if new_val is not None else None
                    if new_val is not None and not new_obj:
                        raise ValueError(f"Энергозона с id={new_val} не найден.")

                    prev_obj = db.session.get(EnergyZone, obj.id_energy_zone) if obj.id_energy_zone else None
                    changes["Энергозона"] = f"{_dash(prev_obj.name if prev_obj else None)} → {_dash(new_obj.name if new_obj else None)}"
                    obj.id_energy_zone = new_val

            # Проверка наличия синхронной зоны
            if "synchronous_area_id" in record:
                new_val = _to_int_or_none(record.get("synchronous_area_id"), keep_zero=True)
                if new_val != obj.id_synchronous_area:
                    new_obj = db.session.get(SynchronousArea, new_val) if new_val is not None else None
                    if new_val is not None and not new_obj:
                        raise ValueError(f"Синхронная зона с id={new_val} не найден.")

                    prev_obj = db.session.get(SynchronousArea, obj.id_synchronous_area) if obj.id_synchronous_area else None
                    changes["Синхронная зона"] = f"{_dash(prev_obj.name if prev_obj else None)} → {_dash(new_obj.name if new_obj else None)}"
                    obj.id_synchronous_area = new_val

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(user, f"Обновлен субъект РФ: {name}", 
                          f"Изменения = {changes}")
                updated_ids.append(regional_district_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(user, "Сохранены изменения по субъектам РФ", 
                      f"Измененных записей: {len(updated_ids)} (id: {updated_ids})")
        else:
            log_to_db(user, "Изменений по субъектам РФ не обнаружено", "")
            
        return updated_ids

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения субъектов РФ (уникальность/целостность)", str(e))
        raise ValueError("Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка при сохранении субъектов РФ", str(e))
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_regional_district_service(data, user):
    """Создание новой записи: субъект РФ"""

    if not isinstance(data, list) or not data:
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    try:
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                name = (record.get("name") or "").strip()
                name_full = (record.get("name_full") or "").strip()
                federal_district_id = _to_int_or_none(record.get("federal_district_id"), keep_zero=False)

                # Проверка на наличие необходимых данных
                if not name or not name_full or federal_district_id is None:
                    log_to_db(user, "Ошибка валидации", f"Запись: {record}")
                    raise ValueError("Каждая запись должна содержать 'name', 'name_full' и 'federal_district_id'. Данные: {record}")

                # Проверяем существование федерального округа
                obj = db.session.get(FederalDistrict, federal_district_id)
                if not obj:
                    raise ValueError(f"Федеральный округ с id={federal_district_id} не найден.")

                # Проверяем уникальность name
                dup = (FederalDistrict.query
                        .filter(FederalDistrict.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
                # Проверяем уникальность name_full
                dup_full = (FederalDistrict.query
                        .filter(FederalDistrict.name_full == name_full)
                        .with_for_update().first())
                if dup_full:
                    raise ValueError(f"Запись с полным наименованием «{name_full}» уже существует.")

                # Создаем новую запись
                obj = FederalDistrict(
                    name=name,
                    name_full=name_full or None,
                    id_federal_district=federal_district_id,
                )
                db.session.add(obj)
                db.session.flush()  # получить id без полного коммита

                log_to_db(
                    user,
                    "Создан субъект РФ",
                    f"Наименование: {name};"
                    f"Полное наименование: {_dash(name_full)};"
                    f"Федеральный округ: {get_federal_district_name(federal_district_id)}"
                )

        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        return None

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения нового субъекта РФ. Возможно, нарушены уникальные ограничения или внешние ключи.", str(e))
        raise ValueError("Ошибка сохранения нового субъекта РФ. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения нового субъекта РФ", str(e))
        raise ValueError(f"Ошибка при сохранения нового субъекта РФ: {e}")


@no_autoflush
def delete_regional_district_service(ids, user):
    """Удаляет записи субъектов РФ по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError("Не переданы ID для удаления.")

    log_to_db(user, "Удаление субъектов РФ", f"Переданы ID для удаления: {ids}")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for rd_id in ids:
        try:
            regional_district_id = int(rd_id)
        except (TypeError, ValueError):
            invalid.append(rd_id)
            log_to_db(user, "Ошибка удаления субъекта РФ", 
                      f"Некорректный ID: {rd_id}")
            continue

        obj = _locked_get(RegionalDistrict, regional_district_id)
        if obj:
            name = obj.name or f"ID={regional_district_id}"
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            log_to_db(user, "Удален субъект РФ", f"{name}")
        else:
            not_found.append(regional_district_id)
            log_to_db(user, "Ошибка удаления субъекта РФ", 
                      f"Субъект РФ с ID={regional_district_id} не найден.")

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        parts = [f"Удалено: {successful_deletes}"]
        if deleted_names:
            parts.append(f"Наименование: {deleted_names}")
        if not_found:
            parts.append(f"Не найдены ID: {not_found}")
        if invalid:
            parts.append(f"Некорректные ID: {invalid}")

        log_to_db(user, "Результат удаления субъектов РФ", "; ".join(parts))

        return {
            "deleted": successful_deletes,
            "deleted_names": deleted_names,
            "not_found": not_found,
            "invalid": invalid,
        }
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка удаления субъектов РФ", str(e))
        raise ValueError("Ошибка при удалении данных.")


@no_autoflush
def import_regional_district_service(file, user):
    """Импортирует данные субъектов РФ из Excel-файла в базу данных с проверкой уникальности."""

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
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        # Логирование результата
        log_to_db(
            user,
            "Импорт завершен",
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


def export_regional_district_service(
    user,
    regional_district_filter=None,
    federal_district_filter=None,
    energy_zone_filter=None,
    synchronous_area_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """ Экспортирует данные субъектов РФ в Excel. """

    log_to_db(user, "Начата выгрузка таблицы субъектов РФ из базы данных")
    log_to_db(user, "Параметры экспорта",
            (
                f"Фильтр по столбцу: Наименование субъекта РФ = {regional_district_filter},"
                f"Фильтр по столбцу: ФО = {get_federal_district_name(federal_district_filter)},"
                f"Фильтр по столбцу: Энергозона = {get_energy_zone_name(energy_zone_filter)},"
                f"Фильтр по столбцу: Синхронная зона = {get_synchronous_area_name(synchronous_area_filter)},"
                f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
            ),
    )

    # Базовый запрос
    query = regional_district_query(
        regional_district_filter=regional_district_filter,
        federal_district_filter=federal_district_filter,
        energy_zone_filter=energy_zone_filter,
        synchronous_area_filter=synchronous_area_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(user, "Получение данных завершено", f"Найдено записей: {len(items)}")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Порядковый номер субъекта РФ": _dash(o.region_id),
            "Наименование субъекта РФ": _dash(o.name),
            "Полное наименование субъекта РФ": _dash(o.name_full),
            "Федеральный округ": getattr(o.federal_district, "name", "Не указан") or "Не указан",
            "Энергозона номер": (
                getattr(getattr(o, "energy_zone", None), "number", None)
                if getattr(o, "energy_zone", None) is not None else None
            ),
            "Энергозона наименование": getattr(o.energy_zone, "name", "Не указана") or "Не указана",
            "Синхронная зона": getattr(o.synchronous_area, "name", "Не указана") or "Не указана",
        })

    log_to_db(user, "Подготовка данных для экспорта таблицы субъектов РФ в Excel",
              f"Записей для экспорта: {len(data)}")

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)

    # Создание Excel и авто-ширина столбцов
    output = BytesIO()
    sheet_name = "Субъекты РФ"
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]

        # Автоподбор ширины с аккуратным лимитом
        for i, col in enumerate(df.columns):
            max_len = max(len(str(col)), *(len(str(v)) for v in df[col].values)) if not df.empty else len(str(col))
            ws.set_column(i, i, min(max_len + 2, 60))

    # Возврат файла в ответе
    output.seek(0)
    log_to_db(user, "Экспорт таблицы субъектов РФ в Excel завершен", f"Экспортировано записей: {len(data)}")
    return output