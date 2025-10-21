"""Сервисный модуль: Доступность технологий."""

from app.extensions import db
from sqlalchemy import func as sa_func, text
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 
from config import SCHEMA_REFDATA
        
# Модели
from app.refdata.models.refdata_for_stations.technologies.technology_availability_model import TechnologyAvailability

# Сервисы
from app.common.services.help_services import (
    _dash,
    _clean_name,
)
from app.common.services.tranzaction_services import (
    _commit_with_retry,
    _locked_get,
    no_autoflush,
    quick_fix_seq,
)

# Логирование
from app.logs.services.logging_service import log_to_db
from app.logs.services.field_names_ru import format_field_change, get_field_name_ru


def technology_availability_query(
        technology_availability_filter=None, 
        sort_by="id", 
        sort_dir="asc"):
    """ Базовый запрос для выборки доступности технологий с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id","name"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Базовый запрос
    query = TechnologyAvailability.query.filter(TechnologyAvailability.id.isnot(None), TechnologyAvailability.id > 0)

    # Фильтрация
    if technology_availability_filter:
        query = query.filter(TechnologyAvailability.name.ilike(f"%{technology_availability_filter}%"))

    # Сортировка
    if sort_by == "name":
        sort_col = TechnologyAvailability.name
    else:
        sort_col = TechnologyAvailability.id

    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    return query


@no_autoflush
def get_technology_availability_list(
    page, 
    per_page, 
    technology_availability_filter=None, 
    sort_by="id", 
    sort_dir="asc"):
    """ Получает список доступности технологий с пагинацией, фильтрацией и сортировкой. """
    
    # Базовый запрос
    query = technology_availability_query(
        technology_availability_filter=technology_availability_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_technology_availability_service(data, user):
    """ Обновление данных по доступности технологий """

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []
    
    log_to_db(
        user, 
        "Получены данные для обновления списка доступности технологий", 
        f"{data}", 
        entity_type="technology_availability")
    
    # Проверки на валидность данных
    with db.session.no_autoflush:
        for record in data:
            technology_availability_id = record.get("technology_availability_id")
            name = (record.get("name") or "").strip()

            if not name:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись: {record}", 
                    entity_type="technology_availability",
                    entity_id=technology_availability_id)
                raise ValueError(f"Поле 'name' обязательно для заполнения.")

            obj = db.session.get(TechnologyAvailability, technology_availability_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{technology_availability_id}» не найдена.", 
                    entity_type="technology_availability", 
                    entity_id=technology_availability_id)
                raise ValueError(f"Запись с ID «{technology_availability_id}» не найдена.")

            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (TechnologyAvailability.query
                     .filter(TechnologyAvailability.name == name,
                             TechnologyAvailability.id != technology_availability_id))
                if q.first():
                    raise ValueError(f"Запись с именем «{name}» уже существует.")

            changes = []

            if name != (obj.name or ""):
                changes.append(format_field_change("name", obj.name or "не указано", name, "technology_availability"))
                obj.name = name

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    f"Обновлен тип технологии: {name}", 
                    f"Изменения: {'; '.join(changes)}", 
                    entity_type="technology_availability", 
                    entity_id=technology_availability_id)
                updated_ids.append(technology_availability_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по доступности технологий", 
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})", 
                entity_type="technology_availability",
                entity_id=technology_availability_id)
        else:
            log_to_db(user, "Изменений по доступности технологий не обнаружено", "", entity_type="technology_availability")
            
        return updated_ids
    
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения доступности технологий (уникальность/целостность)", 
            str(e), 
            entity_type="technology_availability",
            entity_id=technology_availability_id)
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Неизвестная ошибка при сохранении доступности технологий", 
            str(e), 
            entity_type="technology_availability",
            entity_id=technology_availability_id)
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_technology_availability_service(data, user):
    """Создание новой записи: доступность технологии"""
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    def _do_insert():
        with db.session.no_autoflush:
            for record in data:
                name = (record.get("name") or "").strip()
                if not name:
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись: {record}", 
                        entity_type="technology_availability")
                    raise ValueError("Каждая запись должна содержать 'name'.")

                dup = (TechnologyAvailability.query
                       .filter(TechnologyAvailability.name == name)
                       .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")

                obj = TechnologyAvailability(name=name)
                db.session.add(obj)
                db.session.flush()

                log_to_db(
                    user, 
                    "Создана доступность технологии", 
                    f"Наименование: {name}",
                    entity_type="technology_availability", 
                    entity_id=obj.id)

    try:
        _do_insert()
        _commit_with_retry()
        return None

    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "technology_availabilitys")
        _do_insert()
        _commit_with_retry()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения новой доступности технологии", 
            str(e), 
            entity_type="technology_availability")
        raise ValueError(f"Ошибка сохранения новой доступности технологии: {e}") from e


@no_autoflush
def delete_technology_availability_service(ids, user):
    """Удаляет записи доступности технологий по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")

    log_to_db(
        user, 
        "Удаление доступности технологий", 
        f"Переданы ID для удаления: {ids}", 
        entity_type="technology_availability")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for ft_id in ids:
        try:
            technology_availability_id = int(ft_id)
        except (TypeError, ValueError):
            invalid.append(ft_id)
            log_to_db(
                user, 
                "Ошибка удаления доступности технологий", 
                f"Некорректный ID: {ft_id}", 
                entity_type="technology_availability",
                entity_id=ft_id)
            continue

        obj = _locked_get(TechnologyAvailability, technology_availability_id)
        if obj:
            name = obj.name or f"ID={technology_availability_id}"
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            log_to_db(
                user, 
                "Удалена доступность технологии", 
                f"{name}", 
                entity_type="technology_availability", 
                entity_id=technology_availability_id)
        else:
            not_found.append(technology_availability_id)
            log_to_db(
                user, 
                "Ошибка удаления доступности технологий", 
                f"Тип агрегата с ID={technology_availability_id} не найден.", 
                entity_type="technology_availability", 
                entity_id=technology_availability_id)

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
            "Ошибка удаления доступности технологий", 
            str(e), 
            entity_type="technology_availability",
            entity_id=technology_availability_id)
        raise ValueError(f"Ошибка при удалении данных.")


def export_technology_availability_service(
    user,
    technology_availability_filter=None,
    sort_by="id",
    sort_dir="asc",):
    """ Экспортирует данные доступности технологий в Excel. """

    log_to_db(
        user, "Начата выгрузка таблицы доступности технологий. Параметры экспорта",
        (
            f"Фильтр по столбцу: Наименование типа технологии = {technology_availability_filter},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        )
        , entity_type="technology_availability"
    )

    # Базовый запрос
    query = technology_availability_query(
        technology_availability_filter=technology_availability_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(
        user, 
        "Получение данных завершено", 
        f"Найдено записей: {len(items)}", 
        entity_type="technology_availability")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Наименование": _dash(o.name),
        })

    log_to_db(
        user, 
        "Подготовка данных для экспорта таблицы доступности технологий в Excel",
        f"Записей для экспорта: {len(data)}", 
        entity_type="technology_availability")

    df = pd.DataFrame(data)

    # Создание Excel и авто-ширина столбцов
    output = BytesIO()
    sheet_name = "Доступность технологий"
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]

        # Автоподбор ширины с аккуратным лимитом
        for i, col in enumerate(df.columns):
            max_len = max(len(str(col)), *(len(str(v)) for v in df[col].values)) if not df.empty else len(str(col))
            ws.set_column(i, i, min(max_len + 2, 60))

    output.seek(0)
    log_to_db(
        user, 
        "Экспорт таблицы доступности технологий в Excel завершен", 
        f"Экспортировано записей: {len(data)}", 
        entity_type="technology_availability")
    return output