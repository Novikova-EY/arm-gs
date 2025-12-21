"""Сервисный модуль: Объединенные энергосистемы."""

from app.extensions import db
from sqlalchemy import or_, desc
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 
from config import SCHEMA_REFDATA

# Модели
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.territories.regional_district_model import RegionalDistrict

# Сервисы
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_name,
)
from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
    get_regional_energy_system_name,
)
from app.common.services.help_services import (
    _dash,
    _to_int_or_none,
)
from app.common.services.tranzaction_services import (
    _commit_with_retry,
    _locked_get,
    no_autoflush,
    quick_fix_seq,
)

# Фильтрация по версиям
from app.common.services.database_version_filter import (
    apply_version_filter,
    set_db_version_on_create,
)

# Логирование
from app.logs.services.logging_service import log_to_db
from app.logs.services.field_names_ru import format_field_change, get_field_name_ru


def regional_energy_system_query(
    regional_energy_system_filter=None,
    union_energy_system_filter=None,
    sort_by="id",
    sort_dir="asc"):
    """ Базовый запрос для выборки региональных энергосистем с фильтрацией и сортировкой. """

    # Нормализация входов
    sort_dir = "desc" if (sort_dir or "").lower() == "desc" else "asc"
    desc = (sort_dir == "desc")
    sort_by = (sort_by or "id").lower()
    allowed_sort = {"id", "name", "name_full", "name_rp", "union_energy_system"}
    if sort_by not in allowed_sort:
        sort_by = "id"

    # Безопасная конвертация ID-фильтров
    union_energy_system_id = _to_int_or_none(union_energy_system_filter)

    # Базовый запрос
    query = (
        RegionalEnergySystem.query
        .options(
            joinedload(RegionalEnergySystem.regional_districts),
            joinedload(RegionalEnergySystem.union_energy_system)
        )
    )
    query = apply_version_filter(query, RegionalEnergySystem)

    # Фильтрация по названию региональной энергосистемы
    if regional_energy_system_filter:
        query = query.filter(RegionalEnergySystem.name.ilike(f"%{regional_energy_system_filter}%"))

    # Фильтрация по ОЭС (строго по ID)
    if union_energy_system_filter:
        query = query.filter(RegionalEnergySystem.id_union_energy_system == union_energy_system_id)

    # Сортировка
    if sort_by == "name":
        query = query.order_by(RegionalEnergySystem.name.desc() if sort_dir == "desc" else RegionalEnergySystem.name.asc())
    
    elif sort_by == "name_full":
        query = query.order_by(RegionalEnergySystem.name_full.desc() if sort_dir == "desc" else RegionalEnergySystem.name_full.asc())
    
    elif sort_by == "name_rp":
        query = query.order_by(RegionalEnergySystem.name_rp.desc() if sort_dir == "desc" else RegionalEnergySystem.name_rp.asc())
    
    elif sort_by == "union_energy_system":
        query = (query
            .outerjoin(RegionalEnergySystem.union_energy_system)
            .order_by(
                UnionEnergySystem.name.desc().nulls_last() if desc
                else UnionEnergySystem.name.asc().nulls_first(),
                RegionalEnergySystem.id.desc() if desc else RegionalEnergySystem.id.asc(),
            )
        )
    
    else:
        query = query.order_by(RegionalEnergySystem.id.desc() if sort_dir == "desc" else RegionalEnergySystem.id.asc())


    # Исключаем запись "Не указано" (id=0)
    query = query.filter(RegionalEnergySystem.id.isnot(None), RegionalEnergySystem.id > 0)

    return query


@no_autoflush
def get_regional_energy_system_list(
    page, 
    per_page, 
    sort_by="id", 
    sort_dir="asc",
    regional_energy_system_filter=None, 
    union_energy_system_filter=None, 
    ):
    """ Получает список региональных энергосистем с пагинацией, фильтрацией и сортировкой, загружая связи с субъектами РФ. """

    # Базовый запрос
    query = regional_energy_system_query(
        sort_by=sort_by,
        sort_dir=sort_dir,
        regional_energy_system_filter=regional_energy_system_filter,
        union_energy_system_filter=union_energy_system_filter,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_regional_energy_system_service(data, user):
    """Обновление данных по региональным энергосистемам."""

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []

    log_to_db(
        user, 
        "Получены данные для обновления списка региональных энергосистем", 
        f"{data}", 
        entity_type="regional_energy_system")

    with db.session.no_autoflush:
        for record in data:
            regional_energy_system_id = record.get("regional_energy_system_id")
            name = record.get("name")
            name_full = record.get("name_full")
            name_rp = record.get("name_rp")
            union_energy_system_id = record.get("union_energy_system_id")
            regional_district_ids = record.get("regional_district_ids", None)

            # Проверки на валидность данных
            if not name or union_energy_system_id is None:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись: {record}",
                    entity_type="regional_energy_system",
                    entity_id=regional_energy_system_id)
                raise ValueError(f"Каждая запись должна содержать 'name' и 'union_energy_system_id'. Данные: {record}")

            obj = db.session.get(RegionalEnergySystem, regional_energy_system_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{regional_energy_system_id}» не найдена.",
                    entity_type="regional_energy_system", 
                    entity_id=regional_energy_system_id)
                raise ValueError(f"Запись с ID «{regional_energy_system_id}» не найдена.")

            # Если у записи по каким-то причинам не проставлена версия БД,
            # аккуратно проставляем текущую, иначе она не будет отображаться
            # при активной версии (apply_version_filter скрывает NULL).
            set_db_version_on_create(obj)
            
            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (apply_version_filter(RegionalEnergySystem.query, RegionalEnergySystem)
                     .filter(RegionalEnergySystem.name == name,
                             RegionalEnergySystem.id != regional_energy_system_id))
                if q.first():
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")

            # Проверка уникальности name_full
            if name_full != (obj.name_full or ""):
                q_full = (apply_version_filter(RegionalEnergySystem.query, RegionalEnergySystem)
                     .filter(RegionalEnergySystem.name_full == name_full,
                             RegionalEnergySystem.id != regional_energy_system_id))
                if q_full.first():
                    raise ValueError(f"Запись с полным наименованием «{name_full}» уже существует.")
                
            changes = []

            if name != (obj.name or ""):
                changes.append(format_field_change("name", obj.name or "не указано", name, "regional_energy_system"))
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

            # Опциональные FK (если ключ присутствует в record)
            if "union_energy_system_id" in record:
                ues = _to_int_or_none(record.get("union_energy_system_id"), keep_zero=False)
                if ues != obj.id_union_energy_system:
                    new_ues = db.session.get(UnionEnergySystem, ues) if ues is not None else None
                    if ues is not None and not new_ues:
                        raise ValueError(f"ОЭС с id={ues} не найдена.")
                    
                    prev_fd = db.session.get(UnionEnergySystem, obj.id_union_energy_system) if obj.id_union_energy_system else None
                    old_name = prev_fd.name if prev_fd else "не указано"
                    new_name = new_ues.name if new_ues else "не указано"
                    changes.append(format_field_change("id_union_energy_system", old_name, new_name, "regional_energy_system"))
                    obj.id_union_energy_system = ues

            # Обновление связей «многие ко многим»
            if regional_district_ids is not None:
                # Обновление связей «многие ко многим»
                existing_districts = {district.id for district in obj.regional_districts}
                new_districts = set(regional_district_ids) if regional_district_ids else set()

                # Добавить новые связи
                for district_id in new_districts - existing_districts:
                    district = RegionalDistrict.query.get(district_id)
                    if district:
                        obj.regional_districts.append(district)

                # Удалить устаревшие связи
                for district_id in existing_districts - new_districts:
                    district = RegionalDistrict.query.get(district_id)
                    if district:
                        obj.regional_districts.remove(district)

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    f"Обновлена региональная энергосистема: {name}", 
                    f"Изменения: {'; '.join(changes)}",
                    entity_type="regional_energy_system", 
                    entity_id=regional_energy_system_id)
                updated_ids.append(regional_energy_system_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по региональной энергосистеме", 
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})",
                entity_type="regional_energy_system")
        else:
            log_to_db(
                user, 
                "Изменений по региональным энергосистемам не обнаружено", 
                "", 
                entity_type="regional_energy_system")
            
        return updated_ids

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения региональной энергосистемы (уникальность/целостность)", 
            str(e), 
            entity_type="regional_energy_system")
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Неизвестная ошибка при сохранении региональной энергосистемы", 
            str(e), 
            entity_type="regional_energy_system")
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_regional_energy_system_service(data, user):
    """Создание новой записи: региональная энергосистема"""

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    def _do_insert():
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                name = (record.get("name") or "").strip()
                name_full = (record.get("name_full") or "").strip()
                name_rp = (record.get("name_rp") or "").strip()
                union_energy_system_id = _to_int_or_none(record.get("union_energy_system_id"), keep_zero=False)
                regional_district_ids = record.get("regional_districts", [])

                # Проверка на наличие необходимых данных
                if not name or not name_full or not name_rp or not union_energy_system_id:
                    log_to_db(
                        user, 
                        "Ошибка валидации",
                        f"Запись: {record}", 
                        entity_type="regional_energy_system")
                    raise ValueError(f"Каждая запись должна содержать 'name', 'name_full', 'name_rp' и 'union_energy_system_id'. Данные: {record}")

                # Проверяем существование ОЭС
                obj = db.session.get(UnionEnergySystem, union_energy_system_id)
                if not obj:
                    raise ValueError(f"ОЭС с id={union_energy_system_id} не найдена.")

                # Проверяем уникальность name
                dup = (apply_version_filter(RegionalEnergySystem.query, RegionalEnergySystem)
                        .filter(RegionalEnergySystem.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")
                
                # Проверяем уникальность name_full
                dup_full = (apply_version_filter(RegionalEnergySystem.query, RegionalEnergySystem)
                        .filter(RegionalEnergySystem.name_full == name_full)
                        .with_for_update().first())
                if dup_full:
                    raise ValueError(f"Запись с полным наименованием «{name_full}» уже существует.")

                # Создаем новую запись
                obj = RegionalEnergySystem(
                    name=name,
                    name_full=name_full or None,
                    name_rp=name_rp or None,
                    id_union_energy_system=union_energy_system_id,
                )
                # Обязательно проставляем database_version_id,
                # иначе запись не будет видна при активной версии БД.
                set_db_version_on_create(obj)

                # Обновление связей «многие ко многим»
                existing_districts = {district.id for district in obj.regional_districts}
                new_districts = set(regional_district_ids)

                # Добавить новые связи
                for district_id in new_districts - existing_districts:
                    district = RegionalDistrict.query.get(district_id)
                    if district:
                        obj.regional_districts.append(district)

                # Удалить устаревшие связи
                for district_id in existing_districts - new_districts:
                    district = RegionalDistrict.query.get(district_id)
                    if district:
                        obj.regional_districts.remove(district)

                db.session.add(obj)
                db.session.flush()  # получить id без полного коммита

                log_to_db(
                    user, 
                    "Создана региональная энергосистема",
                    (
                        f"Наименование: {name}; "
                        f"Полное наименование: {_dash(name_full)}; "
                        f"Наименование (в родительном падеже): {_dash(name_rp)}; "
                        f"Часть энергосистемы России: {get_union_energy_system_name(union_energy_system_id)} "
                    ),
                    entity_type="regional_energy_system", 
                    entity_id=obj.id)

    try:
        _do_insert()
        _commit_with_retry()
        return None

    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "regional_energy_systems")
        _do_insert()
        _commit_with_retry()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения новой региональной энергосистемы", 
            str(e), 
            entity_type="regional_energy_system")
        raise ValueError(f"Ошибка сохранения новой региональной энергосистемы: {e}")


@no_autoflush
def delete_regional_energy_system_service(ids, user):
    """Удаляет записи региональных энергосистем по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")
    
    log_to_db(
        user, 
        "Удаление записей", 
        f"Переданы ID для удаления: {ids}",
        entity_type="regional_energy_system")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for res_id in ids:
        try:
            regional_energy_system_id = int(res_id)
        except (TypeError, ValueError):
            invalid.append(res_id)
            log_to_db(
                user, 
                "Ошибка удаления региональной энергосистемы", 
                f"Некорректный ID: {res_id}",
                entity_type="regional_energy_system",
                entity_id=res_id)
            continue

        obj = _locked_get(RegionalEnergySystem, regional_energy_system_id)
        if obj:
            db.session.delete(obj)
            deleted_names.append(get_regional_energy_system_name(regional_energy_system_id))
            successful_deletes += 1
            log_to_db(
                user, 
                "Удалена региональная энергосистема" 
                f"{get_regional_energy_system_name(regional_energy_system_id)}",
                entity_type="regional_energy_system", 
                entity_id=regional_energy_system_id)
        else:
            not_found.append(regional_energy_system_id)
            log_to_db(
                user, 
                "Ошибка удаления региональной энергосистемы", 
                f"Региональная энергосистема с ID={regional_energy_system_id} не найдена.",
                entity_type="regional_energy_system", 
                entity_id=regional_energy_system_id)

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
            "Ошибка удаления региональных энергосистем", 
            str(e), 
            entity_type="regional_energy_system",
            entity_id=regional_energy_system_id)
        raise ValueError(f"Ошибка при удалении данных.")


@no_autoflush
def import_regional_energy_system_service(file, user):
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
                log_to_db(
                    user, 
                    "Предупреждение", 
                    f"ОЭС '{oes_name}' не найден в базе. Запись '{row['name']}' пропущена.", 
                    entity_type="regional_energy_system")
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

                log_to_db(
                    user, 
                    "Обновление записи", 
                    f"Обновлена энергосистема ID {row['id']}. {old_data} → {new_data}", 
                    entity_type="regional_energy_system")
                updated_count += 1
            else:
                # Создаем новую запись
                new_record = RegionalEnergySystem(
                    id=row['id'],
                    name=row['name'],
                    id_union_energy_system=oes_id
                )
                set_db_version_on_create(new_record)
                db.session.add(new_record)
                log_to_db(
                    user, 
                    "Добавление новой записи", 
                    f"Добавлена новая энергосистема: {row['name']} (ОЭС: {oes_name})", 
                    entity_type="regional_energy_system")
                imported_count += 1  # Увеличиваем счетчик новых записей

        # Сохраняем изменения
        db.session.commit()
        log_to_db(
            user, 
            "Импорт завершен", 
            f"Добавлено записей: {imported_count}, Обновлено: {updated_count}", 
            entity_type="regional_energy_system")

        return {"imported": imported_count, "updated": updated_count}

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user, "Ошибка импорта (IntegrityError)", 
            str(e), 
            entity_type="regional_energy_system")
        raise ValueError(f"Ошибка целостности данных. Возможно, дублируются ID или имена.")

    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, "Ошибка импорта", 
            str(e), 
            entity_type="regional_energy_system")
        raise ValueError(f"Ошибка при импорте данных: {e}")


def export_regional_energy_system_service(
        user, 
        regional_energy_system_filter=None, 
        union_energy_system_filter=None, 
        sort_by="id", 
        sort_dir="asc"):
    """ Экспортирует данные списка региональных энергосистем в Excel. """
        
    log_to_db(
        user, 
        "Начата выгрузка таблицы региональных энергосистем. Параметры экспорта", 
        (
            f"Фильтр по столбцу: Наименование региональной энергосистемы = {regional_energy_system_filter}," 
            f"Фильтр по столбцу: ОЭС = {get_union_energy_system_name(union_energy_system_filter)},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        ),
        entity_type="regional_energy_system")

    # Базовый запрос
    query = regional_energy_system_query(
        regional_energy_system_filter=regional_energy_system_filter,
        union_energy_system_filter=union_energy_system_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(
        user, 
        "Получение данных завершено", 
        f"Найдено записей: {len(items)}", 
        entity_type="regional_energy_system")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
        "№": idx,
        "Региональная энергосистема": _dash(o.name),
        "Региональная энергосистема (полное название)": _dash(o.name_full),
        "Наименование (в родительном падеже)": _dash(o.name_rp),
        "ОЭС": o.union_energy_system.name if o.union_energy_system else "Не указана",
        "Субъекты РФ": ", ".join([district.name_full for district in o.regional_districts]) if o.regional_districts else "Не указаны"
        })

    if not data:
        log_to_db(
            user, 
            "Экспорт завершен", 
            "Нет данных для экспорта.", 
            entity_type="regional_energy_system")
        return None

    log_to_db(
        user, 
        "Подготовка данных для экспорта таблицы региональных энергосистем в Excel", 
        f"Записей для экспорта: {len(data)}",
        entity_type="regional_energy_system")
    
    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)

    # Создание Excel-файла
    output = BytesIO()
    sheet_name = "Региональные энергосистемы"
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]

        # Автоподбор ширины с аккуратным лимитом
        for i, col in enumerate(df.columns):
            max_len = max(len(str(col)), *(len(str(v)) for v in df[col].values)) if not df.empty else len(str(col))
            ws.set_column(i, i, min(max_len + 2, 60))

    # Возврат файла в ответе
    output.seek(0)
    log_to_db(
        user, 
        "Экспорт таблицы региональных энергосистем в Excel завершен", 
        f"Экспортировано записей: {len(data)}",
        entity_type="regional_energy_system")
    
    return output