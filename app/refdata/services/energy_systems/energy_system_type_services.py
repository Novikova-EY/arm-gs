"""Сервисный модуль: Части энергосистемы России."""

from app.extensions import db
from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 
from config import SCHEMA_REFDATA

# Модели
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType

# Сервисы
from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
    get_energy_system_type_name,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_name,
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
from app.common.services.database_version_filter import set_db_version_on_create

# Логирование
from app.logs.services.logging_service import log_to_db
from app.logs.services.field_names_ru import format_field_change, get_field_name_ru


def energy_system_type_query(
    energy_system_type_filter=None,
    sort_by="id",
    sort_dir="asc"):
    """ Базовый запрос для выборки частей энергосистемы России с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id","name"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Базовый запрос
    query = EnergySystemType.query

    # Фильтрация
    if energy_system_type_filter:
        query = query.filter(
            or_(
                EnergySystemType.name.ilike(f"%{energy_system_type_filter}%"),
            )
        )

    # Сортировка
    if sort_by in ["name"]:
        sort_field = getattr(EnergySystemType, sort_by)
        query = query.order_by(sort_field.desc() if sort_dir == "desc" else sort_field.asc())

    else:
        query = query.order_by(EnergySystemType.id.desc() if sort_dir == "desc" else EnergySystemType.id.asc())

    # Исключаем запись "Не указано" (id=0)
    query = query.filter(EnergySystemType.id.isnot(None), EnergySystemType.id > 0)

    return query


@no_autoflush
def get_energy_system_type_list(
    page, 
    per_page, 
    energy_system_type_filter=None, 
    sort_by="id", 
    sort_dir="asc"):
    """ Получает список частей энергосистемы России с пагинацией, фильтрацией и сортировкой. """
    
    # Базовый запрос
    query = energy_system_type_query(
        energy_system_type_filter=energy_system_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_energy_system_type_service(data, user):
    """ Обновление данных по частям энергосистемы России. """
        
    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []

    log_to_db(
        user, 
        "Получены данные для обновления списка энергоузлов", 
        f"{data}",
        entity_type="energy_system_type")

    with db.session.no_autoflush:
        for record in data:
            energy_system_type_id = record.get("energy_system_type_id")
            name = record.get("name")

           # Проверки на валидность данных
            if not name:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись: {record}",
                    entity_type="energy_system_type",
                    entity_id=energy_system_type_id)
                raise ValueError(f"Каждая запись должна содержать 'name'. Данные: {record}")
            
            obj = db.session.get(EnergySystemType, energy_system_type_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{energy_system_type_id}» не найдена.",
                    entity_type="energy_system_type", 
                    entity_id=energy_system_type_id)
                raise ValueError(f"Запись с ID «{energy_system_type_id}» не найдена.")

            # Проверка уникальности name только если меняется
            if name != (obj.name or ""):
                q = (EnergySystemType.query
                     .filter(EnergySystemType.name == name,
                             EnergySystemType.id != energy_system_type_id))
                if q.first():
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись с наименованием «{name}» уже существует.",
                        entity_type="energy_system_type",
                        entity_id=energy_system_type_id)
                    raise ValueError(f"Запись с именем «{name}» уже существует.")
            
            changes = []

            if name != (obj.name or ""):
                changes.append(format_field_change("name", obj.name or "не указано", name, "energy_system_type"))
                obj.name = name
            
            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    f"Обновлена запись части энергосистемы России: {name}", 
                    f"Изменения: {'; '.join(changes)}",
                    entity_type="energy_system_type", 
                    entity_id=energy_system_type_id)
                updated_ids.append(energy_system_type_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по частям энергосистемы России", 
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})",
                entity_type="energy_system_type")
        else:
            log_to_db(
                user, 
                "Изменений по частям энергосистемы России не обнаружено", 
                "", 
                entity_type="energy_system_type")
            
        return updated_ids

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения части энергосистемы России (уникальность/целостность)", 
            str(e), 
            entity_type="energy_system_type")
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Неизвестная ошибка при сохранении части энергосистемы России", 
            str(e), 
            entity_type="energy_system_type")
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")
    

@no_autoflush
def add_energy_system_type_service(data, user):
    """ Создание новой записи: часть энергосистемы России """
        
    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    def _do_insert():
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                name = record.get("name")

                if not name:
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись: {record}", 
                        entity_type="energy_system_type")
                    raise ValueError(f"Каждая запись должна содержать 'name'. Данные: {record}")

                # Проверяем уникальность name
                dup = (EnergySystemType.query
                        .filter(EnergySystemType.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с именем «{name}» уже существует.")

                # Создаем новую запись
                obj = EnergySystemType(
                    name=name,
                )
                set_db_version_on_create(obj)
                db.session.add(obj)
                db.session.flush()  # получить id без полного коммита

                log_to_db(
                    user, 
                    "Создана часть энергосистемы России",
                    (f"Наименование: {name};"),
                    entity_type="energy_system_type", 
                    entity_id=obj.id)

    try:
        _do_insert()
        _commit_with_retry()
        return None

    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "energy_system_types")
        _do_insert()
        _commit_with_retry()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения части энергосистемы России", 
            str(e), 
            entity_type="energy_system_type")
        raise ValueError(f"Ошибка при добавлении/обновлении записей: {e}")
    

@no_autoflush
def delete_energy_system_type_service(ids, user):
    """Удаляет записи частей энергосистемы России по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")
    
    log_to_db(
        user, 
        "Удаление записей", 
        f"Переданы ID для удаления: {ids}",
        entity_type="energy_system_type")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for est_id in ids:
        try:
            energy_system_type_id = _to_int_or_none(est_id, keep_zero=False)
        except (TypeError, ValueError):
            invalid.append(est_id)
            log_to_db(
                user, 
                "Ошибка удаления части энергосистемы России", 
                f"Некорректный ID: {est_id}",
                entity_type="energy_system_type",
                entity_id=est_id)
            continue

        obj = _locked_get(EnergySystemType, energy_system_type_id)
        if obj:
            db.session.delete(obj)
            deleted_names.append(get_energy_system_type_name(energy_system_type_id))
            successful_deletes += 1
            log_to_db(
                user, 
                "Удалена часть энергосистемы России", 
                f"{get_energy_system_type_name(energy_system_type_id)}",
                entity_type="energy_system_type",
                entity_id=energy_system_type_id)
        else:
            not_found.append(energy_system_type_id)
            log_to_db(
                user, 
                "Ошибка удаления части энергосистемы России", 
                f"Часть энергосистемы России с ID={energy_system_type_id} не найдена.",
                entity_type="energy_system_type",
                entity_id=energy_system_type_id)

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
            "Ошибка удаления частей энергосистемы России", 
            str(e), 
            entity_type="energy_system_type",
            entity_id=energy_system_type_id)
        raise ValueError(f"Ошибка при удалении данных.")
    

def export_energy_system_type_service(
        user, 
        energy_system_type_filter=None, 
        sort_by="id", 
        sort_dir="asc"):
    """ Экспортирует данные списка частей энергосистемы России в Excel. """

    log_to_db(
        user, "Начата выгрузка таблицы частей энергосистемы России. Параметры экспорта", 
            f"Фильтр по столбцу: Наименование части энергосистемы России = {energy_system_type_filter},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}.",
            entity_type="energy_system_type")
    
    # Базовый запрос
    query = energy_system_type_query(
        energy_system_type_filter=energy_system_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(
        user, 
        "Получение данных завершено", 
        f"Найдено записей: {len(items)}",
        entity_type="energy_system_type")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Наименование части энергосистемы России": _dash(o.name),
        })

    log_to_db(
        user, 
        "Подготовка данных для экспорта таблицы частей энергосистемы России в Excel", 
        f"Записей для экспорта: {len(data)}",
        entity_type="energy_system_type")

    # Подготовка данных к записи в Excel
    df = pd.DataFrame(data)
    
    # Создание Excel-файла
    output = BytesIO()
    sheet_name = "Часть энергосистемы России"
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
        "Экспорт таблицы частей энергосистемы России в Excel завершен", 
        f"Экспортировано записей: {len(data)}",
        entity_type="energy_system_type")

    return output