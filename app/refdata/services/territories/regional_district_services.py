"""Сервисный модуль: Субъекты РФ."""

from app.extensions import db
from sqlalchemy import or_, func, nullslast, cast, Integer, case
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

# Фильтрация по версиям
from app.common.services.database_version_filter import (
    apply_version_filter,
    set_db_version_on_create,
)

# Логирование
from app.logs.services.logging_service import log_to_db
from app.logs.services.field_names_ru import format_field_change, get_field_name_ru


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
    allowed_sort_by = {
        "id",
        "name",
        "name_full",
        "name_rp",
        "name_dp",
        "federal_district",
        "energy_zone",
        "synchronous_area",
        "region_id",
        "ref_uuid",
    }
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Безопасная конвертация ID-фильтров
    federal_district_id = _to_int_or_none(federal_district_filter)
    energy_zone_id = _to_int_or_none(energy_zone_filter)
    synchronous_area_id = _to_int_or_none(synchronous_area_filter)

    # Базовый запрос
    q = db.session.query(RegionalDistrict)
    q = q.outerjoin(EnergyZone, EnergyZone.id == RegionalDistrict.id_energy_zone)
    q = q.outerjoin(FederalDistrict, FederalDistrict.id == RegionalDistrict.id_federal_district)
    q = q.outerjoin(SynchronousArea, SynchronousArea.id == RegionalDistrict.id_synchronous_area)
    q = apply_version_filter(q, RegionalDistrict)

    # Фильтрация
    rd = (regional_district_filter or "").strip()
    if rd:
        q = q.filter(
            or_(
                RegionalDistrict.name.ilike(f"%{rd}%"),
                RegionalDistrict.name_full.ilike(f"%{rd}%"),
                RegionalDistrict.name_dp.ilike(f"%{rd}%"),
            )
        )

    # ID-фильтры
    if federal_district_id is not None:
        q = q.filter(FederalDistrict.id == federal_district_id)

    if synchronous_area_id is not None:
        q = q.filter(SynchronousArea.id == synchronous_area_id)

    if energy_zone_id is not None:
        q = q.filter(RegionalDistrict.id_energy_zone == energy_zone_id)

    # Сортировка
    if sort_by == "energy_zone":
        primary = EnergyZone.number
        order = primary.asc() if sort_dir == "asc" else primary.desc()
        try:
            q = q.order_by(order.nullslast(), RegionalDistrict.id.asc())
        except AttributeError:
            q = q.order_by(nullslast(order), RegionalDistrict.id.asc())

    elif sort_by == "federal_district":
        col = FederalDistrict.name
        order = col.asc() if sort_dir == "asc" else col.desc()
        try:
            q = q.order_by(order.nullslast(), RegionalDistrict.id.asc())
        except AttributeError:
            q = q.order_by(nullslast(order), RegionalDistrict.id.asc())    
    
    elif sort_by == "name_full":
        col = RegionalDistrict.name_full
        order = col.asc() if sort_dir == "asc" else col.desc()
        q = q.order_by(order, RegionalDistrict.id.asc())

    elif sort_by == "name_rp":
        col = RegionalDistrict.name_rp
        order = col.asc() if sort_dir == "asc" else col.desc()
        q = q.order_by(order, RegionalDistrict.id.asc())

    elif sort_by == "name_dp":
        col = RegionalDistrict.name_dp
        order = col.asc() if sort_dir == "asc" else col.desc()
        q = q.order_by(order, RegionalDistrict.id.asc())

    elif sort_by == "region_id":
        col = cast(RegionalDistrict.region_id, Integer)
        if sort_dir == "asc":
            q = q.order_by(nullslast(col.asc()), RegionalDistrict.id.asc())
        else:
            q = q.order_by(nullslast(col.desc()), RegionalDistrict.id.asc())

    elif sort_by == "ref_uuid":
        order = RegionalDistrict.ref_uuid.asc() if sort_dir == "asc" else RegionalDistrict.ref_uuid.desc()
        q = q.order_by(order, RegionalDistrict.id.asc())

    elif sort_by == "synchronous_area":
        col = SynchronousArea.name
        order = col.asc() if sort_dir == "asc" else col.desc()
        try:
            q = q.order_by(order.nullslast(), RegionalDistrict.id.asc())
        except AttributeError:
            q = q.order_by(nullslast(order), RegionalDistrict.id.asc())

    else:
        order = RegionalDistrict.id.asc() if sort_dir == "asc" else RegionalDistrict.id.desc()
        q = q.order_by(order)

    q = q.filter(RegionalDistrict.id.isnot(None), RegionalDistrict.id > 0)
    
    return q


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
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []
    
    log_to_db(
        user, 
        "Получены данные для обновления списка субъектов РФ", 
        f"{data}", 
        entity_type="regional_district")
    
    with db.session.no_autoflush:
        for record in data:
            regional_district_id = _to_int_or_none(record.get("regional_district_id"), keep_zero=False)
            region_id = _to_int_or_none(record.get("region_id"), keep_zero=False)
            name = (record.get("name") or "").strip()
            name_full = (record.get("name_full") or "").strip() or None
            name_rp = (record.get("name_rp") or "").strip() or None
            name_dp = (record.get("name_dp") or "").strip() or None

            # Проверки на валидность данных
            if not name:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись: {record}", 
                    entity_type="regional_district",
                    entity_id=regional_district_id)
                raise ValueError(f"Поле 'name' обязательно для заполнения. Данные: {record}")

            obj = db.session.get(RegionalDistrict, regional_district_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{regional_district_id}» не найдена.", 
                    entity_type="regional_district", 
                    entity_id=regional_district_id)
                raise ValueError(f"Запись с ID «{regional_district_id}» не найдена.")

            # name_dp NOT NULL: если не передали/пусто — используем fallback
            if not name_dp:
                name_dp = name_full or name

            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (apply_version_filter(RegionalDistrict.query, RegionalDistrict)
                     .filter(RegionalDistrict.name == name,
                             RegionalDistrict.id != regional_district_id))
                if q.first():
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись с наименованием «{name}» уже существует.", 
                        entity_type="regional_district",
                        entity_id=regional_district_id)
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
            # Проверка уникальности name_full
            if name_full != (obj.name_full or ""):
                q_full = (apply_version_filter(RegionalDistrict.query, RegionalDistrict)
                     .filter(RegionalDistrict.name_full == name_full,
                             RegionalDistrict.id != regional_district_id))
                if q_full.first():
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись с полным наименованием «{name_full}» уже существует.", 
                        entity_type="regional_district",
                        entity_id=regional_district_id)
                    raise ValueError(f"Запись с полным наименованием «{name_full}» уже существует.")

            changes = []

            if name != (obj.name or ""):
                changes.append(format_field_change("name", obj.name or "не указано", name, "regional_district"))
                obj.name = name

            if name_full != (obj.name_full or None):
                old_val = obj.name_full or "не указано"
                new_val = name_full or "не указано"
                changes.append(f"Полное наименование: {old_val} → {new_val}")
                obj.name_full = name_full

            if name_rp != (obj.name_rp or None):
                old_val = obj.name_rp or "не указано"
                new_val = name_rp or "не указано"
                changes.append(f"Наименование (в родительном падеже): {old_val} → {new_val}")
                obj.name_rp = name_rp

            if name_dp != (obj.name_dp or None):
                old_val = obj.name_dp or "не указано"
                new_val = name_dp or "не указано"
                changes.append(f"Наименование (в дательном падеже): {old_val} → {new_val}")
                obj.name_dp = name_dp

            if region_id != obj.region_id:
                old_val = obj.region_id if obj.region_id is not None else "не указано"
                new_val = region_id if region_id is not None else "не указано"
                changes.append(f"Порядковый номер субъекта РФ: {old_val} → {new_val}")
                obj.region_id = region_id

            # Проверка наличия ФО
            if "federal_district_id" in record:
                new_val = _to_int_or_none(record.get("federal_district_id"), keep_zero=False)
                if new_val != obj.id_federal_district:
                    new_obj = db.session.get(FederalDistrict, new_val) if new_val is not None else None
                    if new_val is not None and not new_obj:
                        raise ValueError(f"Федеральный округ с id={new_val} не найден.")
                    
                    prev_obj = db.session.get(FederalDistrict, obj.id_federal_district) if obj.id_federal_district else None
                    old_name = prev_obj.name if prev_obj else "не указано"
                    new_name = new_obj.name if new_obj else "не указано"
                    changes.append(format_field_change("id_federal_district", old_name, new_name, "regional_district"))
                    obj.id_federal_district = new_val

            # Проверка наличия энергозоны
            if "energy_zone_id" in record:
                new_val = _to_int_or_none(record.get("energy_zone_id"), keep_zero=True)
                if new_val != obj.id_energy_zone:
                    new_obj = db.session.get(EnergyZone, new_val) if new_val is not None else None
                    if new_val is not None and not new_obj:
                        raise ValueError(f"Энергозона с id={new_val} не найден.")

                    prev_obj = db.session.get(EnergyZone, obj.id_energy_zone) if obj.id_energy_zone else None
                    old_name = prev_obj.name if prev_obj else "не указано"
                    new_name = new_obj.name if new_obj else "не указано"
                    changes.append(f"Энергозона: {old_name} → {new_name}")
                    obj.id_energy_zone = new_val

            # Проверка наличия синхронной зоны
            if "synchronous_area_id" in record:
                new_val = _to_int_or_none(record.get("synchronous_area_id"), keep_zero=True)
                if new_val != obj.id_synchronous_area:
                    new_obj = db.session.get(SynchronousArea, new_val) if new_val is not None else None
                    if new_val is not None and not new_obj:
                        raise ValueError(f"Синхронная зона с id={new_val} не найден.")

                    prev_obj = db.session.get(SynchronousArea, obj.id_synchronous_area) if obj.id_synchronous_area else None
                    old_name = prev_obj.name if prev_obj else "не указано"
                    new_name = new_obj.name if new_obj else "не указано"
                    changes.append(f"Синхронная зона: {old_name} → {new_name}")
                    obj.id_synchronous_area = new_val

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    f"Обновлен субъект РФ: {name}", 
                    f"Изменения: {'; '.join(changes)}", 
                    entity_type="regional_district", 
                    entity_id=regional_district_id)
                updated_ids.append(regional_district_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(user, "Сохранены изменения по субъектам РФ", 
                      f"Измененных записей: {len(updated_ids)} (id: {updated_ids})", entity_type="regional_district")
        else:
            log_to_db(user, "Изменений по субъектам РФ не обнаружено", "", entity_type="regional_district")
            
        return updated_ids

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения субъектов РФ (уникальность/целостность)", str(e), entity_type="regional_district")
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Неизвестная ошибка при сохранении субъектов РФ", str(e), entity_type="regional_district")
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_regional_district_service(data, user):
    """Создание новой записи: субъект РФ"""

    if not isinstance(data, list) or not data:
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    try:
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                name = (record.get("name") or "").strip()
                name_full = (record.get("name_full") or "").strip()
                name_rp = (record.get("name_rp") or "").strip()
                name_dp = (record.get("name_dp") or "").strip()
                federal_district_id = _to_int_or_none(record.get("federal_district_id"), keep_zero=False)

                # Проверка на наличие необходимых данных
                if not name or not name_full or not name_rp or federal_district_id is None:
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись: {record}", 
                        entity_type="regional_district")
                    raise ValueError(f"Каждая запись должна содержать 'name', 'name_full', 'name_rp' и 'federal_district_id'. Данные: {record}")

                # name_dp NOT NULL: если не передали/пусто — используем fallback
                if not name_dp:
                    name_dp = name_full or name

                # Проверяем существование федерального округа
                obj = db.session.get(FederalDistrict, federal_district_id)
                if not obj:
                    raise ValueError(f"Федеральный округ с id={federal_district_id} не найден.")

                # Проверяем уникальность name
                dup = (apply_version_filter(RegionalDistrict.query, RegionalDistrict)
                        .filter(RegionalDistrict.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
                # Проверяем уникальность name_full
                dup_full = (apply_version_filter(RegionalDistrict.query, RegionalDistrict)
                        .filter(RegionalDistrict.name_full == name_full)
                        .with_for_update().first())
                if dup_full:
                    raise ValueError(f"Запись с полным наименованием «{name_full}» уже существует.")

                # Создаем новую запись
                obj = RegionalDistrict(
                    name=name,
                    name_full=name_full or None,
                    name_rp=name_rp or None,
                    name_dp=name_dp or None,
                    id_federal_district=federal_district_id,
                )
                set_db_version_on_create(obj)
                db.session.add(obj)
                db.session.flush()  # получить id без полного коммита

                log_to_db(
                    user,
                    "Создан субъект РФ",
                    (
                        f"Наименование: {name};"
                        f"Полное наименование: {_dash(name_full)};"
                        f"Наименование (в родительном падеже): {_dash(name_rp)};"
                        f"Наименование (в дательном падеже): {_dash(name_dp)};"
                        f"Федеральный округ: {get_federal_district_name(federal_district_id)}",
                    ),
                    entity_type="regional_district", 
                    entity_id=obj.id)

        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        return None

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения нового субъекта РФ. Возможно, нарушены уникальные ограничения или внешние ключи.", str(e), entity_type="regional_district")
        raise ValueError(f"Ошибка сохранения нового субъекта РФ. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка сохранения нового субъекта РФ", str(e), entity_type="regional_district")
        raise ValueError(f"Ошибка при сохранения нового субъекта РФ: {e}")


@no_autoflush
def delete_regional_district_service(ids, user):
    """Удаляет записи субъектов РФ по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")

    log_to_db(
        user, 
        "Удаление субъектов РФ", 
        f"Переданы ID для удаления: {ids}", 
        entity_type="regional_district")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for rd_id in ids:
        try:
            regional_district_id = int(rd_id)
        except (TypeError, ValueError):
            invalid.append(rd_id)
            log_to_db(
                user, 
                "Ошибка удаления субъекта РФ", 
                f"Некорректный ID: {rd_id}",
                entity_type="regional_district",
                entity_id=regional_district_id)
            continue

        obj = _locked_get(RegionalDistrict, regional_district_id)
        if obj:
            name = obj.name or f"ID={regional_district_id}"
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            log_to_db(
                user, 
                "Удален субъект РФ", 
                f"{name}", 
                entity_type="regional_district", 
                entity_id=regional_district_id)
        else:
            not_found.append(regional_district_id)
            log_to_db(
                user, 
                "Ошибка удаления субъекта РФ", 
                f"Субъект РФ с ID={regional_district_id} не найден.", 
                entity_type="regional_district", 
                entity_id=regional_district_id)

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

        return {
            "deleted": successful_deletes,
            "deleted_names": deleted_names,
            "not_found": not_found,
            "invalid": invalid,
        }
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка удаления субъектов РФ", 
            str(e), 
            entity_type="regional_district",
            entity_id=regional_district_id)
        raise ValueError(f"Ошибка при удалении данных.")


@no_autoflush
def import_regional_district_service(file, user):
    """Импортирует данные субъектов РФ из Excel-файла в базу данных с проверкой уникальности."""

    try:
        # Чтение данных из файла Excel
        data = pd.read_excel(file)

        # Проверка наличия обязательных столбцов
        required_columns = {'name', 'name_full', 'federal_district_name'}
        if not required_columns.issubset(data.columns):
            raise ValueError(f"Неверный формат файла. Отсутствуют обязательные столбцы: 'name', 'name_full', 'federal_district_name'.")

        # Очистка данных (удаление пустых строк)
        data = data.dropna(subset=['name', 'name_full', 'federal_district_name'])

        if data.empty:
            raise ValueError(f"Файл не содержит данных для обновления.")

        # Удаление лишних пробелов
        data['name'] = data['name'].str.strip()
        data['name_full'] = data['name_full'].str.strip()
        data['federal_district_name'] = data['federal_district_name'].str.strip()
        if 'name_rp' in data.columns:
            data['name_rp'] = data['name_rp'].astype(str).str.strip()
        if 'name_dp' in data.columns:
            data['name_dp'] = data['name_dp'].astype(str).str.strip()

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
            name_rp = (row.get('name_rp') if 'name_rp' in data.columns else None)
            name_dp = (row.get('name_dp') if 'name_dp' in data.columns else None)

            # fallback для NOT NULL полей
            name_rp = (str(name_rp).strip() if name_rp is not None and str(name_rp).strip().lower() != 'nan' else "") or name_full
            name_dp = (str(name_dp).strip() if name_dp is not None and str(name_dp).strip().lower() != 'nan' else "") or name_full

            # Проверка существования федерального округа
            if federal_district_name not in federal_districts:
                raise ValueError(f"Федеральный округ '{federal_district_name}' не найден в базе данных.")

            id_federal_district = federal_districts[federal_district_name]

            # Проверка существования записи
            existing_record = db.session.query(RegionalDistrict).filter_by(name=name).first()

            if existing_record:
                # Проверяем, есть ли изменения в записи
                if (
                    existing_record.name_full != name_full
                    or existing_record.id_federal_district != id_federal_district
                    or (existing_record.name_rp or "") != (name_rp or "")
                    or (existing_record.name_dp or "") != (name_dp or "")
                ):
                    existing_record.name_full = name_full
                    existing_record.id_federal_district = id_federal_district
                    existing_record.name_rp = name_rp
                    existing_record.name_dp = name_dp
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
                    name_rp=name_rp,
                    name_dp=name_dp,
                    id_federal_district=id_federal_district
                )
                set_db_version_on_create(new_record)
                db.session.add(new_record)
                added_count += 1

        # Если нет изменений, данных для обновления нет
        if updated_count == 0 and added_count == 0 and deleted_count == 0:
            raise ValueError(f"Данные для обновления отсутствуют.")

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
        log_to_db(user, "Ошибка импорта данных (IntegrityError)", str(e), entity_type="regional_district")
        raise ValueError(f"Ошибка целостности данных при импорте. Проверьте уникальность записей.")
    except ValueError as e:
        db.session.rollback()
        log_to_db(user, "Ошибка импорта данных (ValueError)", str(e), entity_type="regional_district")
        raise
    except Exception as e:
        db.session.rollback()
        log_to_db(user, "Ошибка импорта данных", str(e), entity_type="regional_district")
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

    log_to_db(user, "Начата выгрузка таблицы субъектов РФ из базы данных", entity_type="regional_district")
    log_to_db(user, "Параметры экспорта",
            (
                f"Фильтр по столбцу: Наименование субъекта РФ = {regional_district_filter},"
                f"Фильтр по столбцу: ФО = {get_federal_district_name(federal_district_filter)},"
                f"Фильтр по столбцу: Энергозона = {get_energy_zone_name(energy_zone_filter)},"
                f"Фильтр по столбцу: Синхронная зона = {get_synchronous_area_name(synchronous_area_filter)},"
                f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
            ), entity_type="regional_district"
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
    log_to_db(user, "Получение данных завершено", f"Найдено записей: {len(items)}", entity_type="regional_district")

    # Подготовка данных для Excel
    data = []
    
    for idx, o in enumerate(items, start=1):
        ez_num = getattr(o.energy_zone, "number", None)
        ez_name = getattr(o.energy_zone, "name", None)
    
        data.append({
            "№": idx,
            "Порядковый номер субъекта РФ": _dash(o.region_id),
            "Наименование субъекта РФ": _dash(o.name),
            "Полное наименование субъекта РФ": _dash(o.name_full),
            "Наименование (в родительном падеже)": _dash(o.name_rp),
            "Наименование (в дательном падеже)": _dash(o.name_dp),
            "Федеральный округ": getattr(o.federal_district, "name", "Не указан") or "Не указан",
            "Энергозона номер": _dash(ez_num),
            "Энергозона наименование": _dash(ez_name) or "Не указана",
            "Синхронная зона": getattr(o.synchronous_area, "name", "Не указана") or "Не указана",
        })

    log_to_db(user, "Подготовка данных для экспорта таблицы субъектов РФ в Excel",
              f"Записей для экспорта: {len(data)}", entity_type="regional_district")

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
    log_to_db(user, "Экспорт таблицы субъектов РФ в Excel завершен", f"Экспортировано записей: {len(data)}", entity_type="regional_district")
    return output