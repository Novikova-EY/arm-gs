"""Сервисный модуль: Субъекты РФ."""

from app.extensions import db
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 

# Модели
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea

# Сервисы
from app.logs.services.logging_service import log_to_db
from app.refdata.services.common_services.help_services import (
    _dash,
    _to_int_or_none,
)
from app.refdata.services.common_services.tranzaction_services import (
    _commit_with_retry,
    _locked_get,
    no_autoflush,
)


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
    """Получает список субъектов РФ с пагинацией, фильтрацией и сортировкой."""

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

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_regional_district_service(data, user):
    """Обновление данных по субъектам РФ."""

    if not isinstance(data, list) or not data:
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []
    
    # Итерация по входным данным (валидация/применение)
    with db.session.no_autoflush:
        for record in data:
            regional_district_id = record.get("id")
            region_id = _to_int_or_none(record.get("region_id"), keep_zero=False)
            name = (record.get("name") or "").strip()
            name_full = (record.get("name_full") or "").strip() or None

            if not name:
                raise ValueError("Поле 'name' обязательно для заполнения.")

            obj = db.session.get(RegionalDistrict, regional_district_id)
            if not obj:
                raise ValueError(f"Запись с ID «{regional_district_id}» не найдена.")

            # Проверка уникальности name только если меняется
            if name != (obj.name or ""):
                q = (RegionalDistrict.query
                     .filter(RegionalDistrict.name == name,
                             RegionalDistrict.id != regional_district_id))
                if q.first():
                    raise ValueError(f"Запись с именем «{name}» уже существует.")

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

            # Опциональные FK (если ключ присутствует в record)
            if "id_federal_district" in record:
                new_fd_id = _to_int_or_none(record.get("id_federal_district"), keep_zero=False)
                if new_fd_id != obj.id_federal_district:
                    new_fd = db.session.get(FederalDistrict, new_fd_id) if new_fd_id is not None else None
                    if new_fd_id is not None and not new_fd:
                        raise ValueError(f"Федеральный округ с id={new_fd_id} не найден.")
                    prev_fd = db.session.get(FederalDistrict, obj.id_federal_district) if obj.id_federal_district else None
                    changes["Федеральный округ"] = f"{_dash(prev_fd.name if prev_fd else None)} → {_dash(new_fd.name if new_fd else None)}"
                    obj.id_federal_district = new_fd_id

            # Энергозона (если ключ присутствует во входе)
            if "id_energy_zone" in record:
                new_val = _to_int_or_none(record.get("id_energy_zone"), keep_zero=True)
                if new_val != obj.id_energy_zone:
                    new_obj = None
                    if new_val is not None:
                        new_obj = db.session.get(EnergyZone, new_val)
                        if not new_obj:
                            raise ValueError(f"Энергозона с id={new_val} не найдена.")

                    prev_obj = db.session.get(EnergyZone, obj.id_energy_zone) if obj.id_energy_zone else None
                    changes["Энергозона"] = f"{_dash(prev_obj.name if prev_obj else None)} → {_dash(new_obj.name if new_obj else None)}"
                    obj.id_energy_zone = new_val

            # Синхронная зона (если ключ присутствует во входе)
            if "id_synchronous_area" in record:
                new_val = _to_int_or_none(record.get("id_synchronous_area"), keep_zero=True)
                if new_val != obj.id_synchronous_area:
                    new_obj = None
                    if new_val is not None:
                        new_obj = db.session.get(SynchronousArea, new_val)
                        if not new_obj:
                            raise ValueError(f"Синхронная зона с id={new_val} не найдена.")

                    prev_obj = db.session.get(SynchronousArea, obj.id_synchronous_area) if obj.id_synchronous_area else None
                    changes["Синхронная зона"] = f"{_dash(prev_obj.name if prev_obj else None)} → {_dash(new_obj.name if new_obj else None)}"
                    obj.id_synchronous_area = new_val

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(user, f"Обновлен субъект РФ: {name}", f"Изменения = {changes}")
                updated_ids.append(regional_district_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(user, "Сохранены изменения по субъектам РФ", f"Измененных записей: {len(updated_ids)} (id: {updated_ids})")
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
    """Создание/обновление субъектов РФ"""

    if not isinstance(data, list) or not data:
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    log_to_db(user, "Получены данные для добавления/обновления субъектов РФ", f"Кол-во записей: {len(data)}")

    created_ids = []
    updated_count = 0

    try:
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                regional_district_id = record.get("id")
                name = (record.get("name") or "").strip()
                name_full = (record.get("name_full") or "").strip()
                id_federal_district = _to_int_or_none(record.get("id_federal_district"), keep_zero=False)

                if not name or not name_full or id_federal_district is None:
                    log_to_db(user, "Ошибка валидации", f"Запись: {record}")
                    raise ValueError("Каждая запись должна содержать 'name', 'name_full' и 'id_federal_district'.")

                # Проверяем существование ФО
                fd_obj = db.session.get(FederalDistrict, id_federal_district)
                if not fd_obj:
                    raise ValueError(f"Федеральный округ с id={id_federal_district} не найден.")
                fd_name = fd_obj.name

                #----- ОБНОВЛЕНИЕ-----
                if regional_district_id:
                    obj = _locked_get(RegionalDistrict, regional_district_id)
                    if not obj:
                        log_to_db(user, "Ошибка обновления субъекта РФ", f"Запись с ID={regional_district_id} не найдена")
                        raise ValueError(f"Запись с ID {regional_district_id} не найдена.")

                    # Уникальность name — только если меняется
                    if (obj.name or "") != name:
                        dup = (RegionalDistrict.query
                               .filter(RegionalDistrict.name == name,
                                       RegionalDistrict.id != regional_district_id)
                               .with_for_update().first())
                        if dup:
                            raise ValueError(f"Запись с именем «{name}» уже существует.")

                    изменения = {}

                    if (obj.name or "") != name:
                        изменения["Наименование"] = f"{_dash(obj.name)} → {name}"
                        obj.name = name

                    if (obj.name_full or "") != name_full:
                        изменения["Полное наименование"] = f"{_dash(obj.name_full)} → {_dash(name_full)}"
                        obj.name_full = name_full or None

                    if obj.id_federal_district != id_federal_district:
                        prev_fd = db.session.get(FederalDistrict, obj.id_federal_district) if obj.id_federal_district else None
                        prev_fd_name = prev_fd.name if prev_fd else "—"
                        изменения["Федеральный округ"] = f"{prev_fd_name} → {fd_name}"
                        obj.id_federal_district = id_federal_district

                    if изменения:
                        updated_count += 1
                        log_to_db(user, "Обновлен субъект РФ", f"Наименование = {name}. Изменения = {изменения}")

                #----- СОЗДАНИЕ-----
                else:
                    # Уникальность name при создании
                    dup = (RegionalDistrict.query
                           .filter(RegionalDistrict.name == name)
                           .with_for_update().first())
                    if dup:
                        raise ValueError(f"Запись с именем «{name}» уже существует.")

                    obj = RegionalDistrict(
                        name=name,
                        name_full=name_full or None,
                        id_federal_district=id_federal_district,
                    )
                    db.session.add(obj)
                    db.session.flush()  # получить id без полного коммита
                    created_ids.append(obj.id)

                    log_to_db(
                        user,
                        "Создан субъект РФ",
                        f"Наименование: {name}; Полное наименование: {_dash(name_full)}; Федеральный округ: {fd_name}"
                    )

        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        # Итоговый лог
        tail = []
        if created_ids:
            tail.append(f"создано: {len(created_ids)} (id: {created_ids})")
        if updated_count:
            tail.append(f"обновлено: {updated_count}")
        log_to_db(user, "Сохранение субъектов РФ завершено", "; ".join(tail) or "Изменений нет")

        if len(created_ids) == 1:
            return created_ids[0]
        if created_ids:
            return created_ids
        return None

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения субъектов РФ (уникальность/целостность)", str(e))
        raise ValueError("Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения субъектов РФ", str(e))
        raise ValueError(f"Ошибка при добавлении/обновлении записей: {e}")


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
            log_to_db(user, "Ошибка удаления субъекта РФ", f"Некорректный ID: {rd_id}")
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
            log_to_db(user, "Ошибка удаления субъекта РФ", f"Субъект РФ с ID={regional_district_id} не найден.")

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
    """ Экспортирует данные субъектов РФ в Excel и возвращает BytesIO. """

    # Нормализация входов
    sort_dir = "desc" if (sort_dir or "").lower() == "desc" else "asc"
    sort_by = (sort_by or "id").lower()
    allowed_sort = {"id", "name", "name_full", "federal_district", "energy_zone", "synchronous_area"}
    if sort_by not in allowed_sort:
        sort_by = "id"

    federal_district_id = _to_int_or_none(federal_district_filter)
    energy_zone_id = _to_int_or_none(energy_zone_filter)
    synchronous_area_id = _to_int_or_none(synchronous_area_filter)
    rd = (regional_district_filter or "").strip()

    log_to_db(user, "Начата выгрузка таблицы субъектов РФ из базы данных")
    log_to_db(
        user,
        "Параметры экспорта",
        (
            f"regional_district_filter={rd!r}, "
            f"federal_district_id={federal_district_id}, "
            f"energy_zone_id={energy_zone_id}, "
            f"synchronous_area_id={synchronous_area_id}, "
            f"sort_by={sort_by}, sort_dir={sort_dir}"
        ),
    )

    # Базовый запрос
    q = (
        RegionalDistrict.query
        .options(
            selectinload(RegionalDistrict.federal_district),
            selectinload(RegionalDistrict.energy_zone),
            selectinload(RegionalDistrict.synchronous_area),
        )
        .filter(RegionalDistrict.id > 0)
    )

    # Фильтрация
    if rd:
        like = f"%{rd}%"
        query = query.filter(or_(RegionalDistrict.name.ilike(like),
                         RegionalDistrict.name_full.ilike(like)))

    if federal_district_id is not None:
        query = query.join(FederalDistrict).filter(FederalDistrict.id == federal_district_id)

    if energy_zone_id is not None:
        query = query.join(EnergyZone, isouter=True).filter(RegionalDistrict.id_energy_zone == energy_zone_id)

    if synchronous_area_id is not None:
        query = query.join(SynchronousArea, isouter=True).filter(RegionalDistrict.id_synchronous_area == synchronous_area_id)

    # Сортировка
    if sort_by == "name":
        order_col = RegionalDistrict.name
        query = query.order_by(order_col.desc() if sort_dir == "desc" else order_col.asc())

    elif sort_by == "name_full":
        order_col = RegionalDistrict.name_full
        query = query.order_by(order_col.desc() if sort_dir == "desc" else order_col.asc())

    elif sort_by == "region_id":
        order_col = RegionalDistrict.region_id
        query = query.order_by(order_col.desc() if sort_dir == "desc" else order_col.asc())

    elif sort_by == "federal_district":
        query = query.join(FederalDistrict) if "federal_districts" not in str(q.statement) else q
        order_cols = [FederalDistrict.name.desc() if sort_dir == "desc" else FederalDistrict.name.asc(),
                      RegionalDistrict.name.asc()]
        query = query.order_by(*order_cols)

    elif sort_by == "energy_zone":
        query = query.join(EnergyZone, isouter=True)
        order_cols = [EnergyZone.name.desc() if sort_dir == "desc" else EnergyZone.name.asc(),
                      RegionalDistrict.name.asc()]
        query = query.order_by(*order_cols)

    elif sort_by == "synchronous_area":
        query = query.join(SynchronousArea, isouter=True)
        order_cols = [SynchronousArea.name.desc() if sort_dir == "desc" else SynchronousArea.name.asc(),
                      RegionalDistrict.name.asc()]
        query = query.order_by(*order_cols)

    else:
        order_col = RegionalDistrict.id
        query = query.order_by(order_col.desc() if sort_dir == "desc" else order_col.asc())

    items = query.all()

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Порядковый номер субъекта РФ": f"{o.name}: {o.region_id or ''}",
            "Наименование субъекта РФ": o.name or "",
            "Полное наименование субъекта РФ": o.name_full or "",
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

    output.seek(0)
    log_to_db(user, "Экспорт таблицы субъектов РФ в Excel завершен", f"Экспортировано записей: {len(data)}")
    return output