"""Сервисный модуль: Типы технологий."""

from app.extensions import db
from sqlalchemy import func as sa_func, text
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 
from config import SCHEMA_REFDATA
        
# Модели
from app.refdata.models.refdata_for_stations.technologies.technology_type_model import TechnologyType

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

# Фильтрация по версиям
from app.common.services.database_version_filter import (
    apply_version_filter,
    set_db_version_on_create,
)

# Логирование
from app.logs.services.logging_service import log_to_db
from app.logs.services.field_names_ru import format_field_change, get_field_name_ru


def technology_type_query(
        technology_type_filter=None, 
        sort_by="id", 
        sort_dir="asc"):
    """ Базовый запрос для выборки типов технологий с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id","name"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Базовый запрос
    query = TechnologyType.query.filter(TechnologyType.id.isnot(None), TechnologyType.id > 0)
    query = apply_version_filter(query, TechnologyType)

    # Фильтрация
    if technology_type_filter:
        query = query.filter(TechnologyType.name.ilike(f"%{technology_type_filter}%"))

    # Сортировка
    if sort_by == "name":
        sort_col = TechnologyType.name
    else:
        sort_col = TechnologyType.id

    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    return query


@no_autoflush
def get_technology_type_list(
    page, 
    per_page, 
    technology_type_filter=None, 
    sort_by="id", 
    sort_dir="asc"):
    """ Получает список типов технологий с пагинацией, фильтрацией и сортировкой. """
    
    # Базовый запрос
    query = technology_type_query(
        technology_type_filter=technology_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_technology_type_service(data, user):
    """ Обновление данных по типам технологий """

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []
    
    log_to_db(
        user, 
        "Получены данные для обновления списка типов технологий", 
        f"{data}", 
        entity_type="technology_type")
    
    # Проверки на валидность данных
    with db.session.no_autoflush:
        for record in data:
            technology_type_id = record.get("technology_type_id")
            name = (record.get("name") or "").strip()

            if not name:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись: {record}", 
                    entity_type="technology_type",
                    entity_id=technology_type_id)
                raise ValueError(f"Поле 'name' обязательно для заполнения.")

            obj = db.session.get(TechnologyType, technology_type_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{technology_type_id}» не найдена.", 
                    entity_type="technology_type", 
                    entity_id=technology_type_id)
                raise ValueError(f"Запись с ID «{technology_type_id}» не найдена.")

            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (apply_version_filter(TechnologyType.query, TechnologyType)
                     .filter(TechnologyType.name == name,
                             TechnologyType.id != technology_type_id))
                if q.first():
                    raise ValueError(f"Запись с именем «{name}» уже существует.")

            changes = []

            if name != (obj.name or ""):
                changes.append(format_field_change("name", obj.name or "не указано", name, "technology_type"))
                obj.name = name

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    f"Обновлен тип технологии: {name}", 
                    f"Изменения: {'; '.join(changes)}", 
                    entity_type="technology_type", 
                    entity_id=technology_type_id)
                updated_ids.append(technology_type_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по типам технологий", 
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})", 
                entity_type="technology_type",
                entity_id=technology_type_id)
        else:
            log_to_db(user, "Изменений по типам технологий не обнаружено", "", entity_type="technology_type")
            
        return updated_ids
    
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения типов технологий (уникальность/целостность)", 
            str(e), 
            entity_type="technology_type",
            entity_id=technology_type_id)
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Неизвестная ошибка при сохранении типов технологий", 
            str(e), 
            entity_type="technology_type",
            entity_id=technology_type_id)
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_technology_type_service(data, user):
    """Создание новой записи: тип технологии"""
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
                        entity_type="technology_type")
                    raise ValueError("Каждая запись должна содержать 'name'.")

                dup = (apply_version_filter(TechnologyType.query, TechnologyType)
                        .filter(TechnologyType.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")

                obj = TechnologyType(name=name)
                set_db_version_on_create(obj)
                db.session.add(obj)
                db.session.flush()

                log_to_db(
                    user, 
                    "Создан тип технологии", 
                    f"Наименование: {name}",
                    entity_type="technology_type", 
                    entity_id=obj.id)

    try:
        _do_insert()
        _commit_with_retry()
        return None

    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "technology_types")
        _do_insert()
        _commit_with_retry()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения нового типа технологии", 
            str(e), 
            entity_type="technology_type")
        raise ValueError(f"Ошибка сохранения нового типа технологии: {e}") from e


@no_autoflush
def delete_technology_type_service(ids, user):
    """Удаляет записи типов технологий по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")

    log_to_db(
        user, 
        "Удаление типов технологий", 
        f"Переданы ID для удаления: {ids}", 
        entity_type="technology_type")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for ft_id in ids:
        try:
            technology_type_id = int(ft_id)
        except (TypeError, ValueError):
            invalid.append(ft_id)
            log_to_db(
                user, 
                "Ошибка удаления типов технологий", 
                f"Некорректный ID: {ft_id}", 
                entity_type="technology_type",
                entity_id=ft_id)
            continue

        obj = _locked_get(TechnologyType, technology_type_id)
        if obj:
            name = obj.name or f"ID={technology_type_id}"
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            log_to_db(
                user, 
                "Удален тип технологии", 
                f"{name}", 
                entity_type="technology_type", 
                entity_id=technology_type_id)
        else:
            not_found.append(technology_type_id)
            log_to_db(
                user, 
                "Ошибка удаления типов технологий", 
                f"Тип технологии с ID={technology_type_id} не найден.", 
                entity_type="technology_type", 
                entity_id=technology_type_id)

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
            "Ошибка удаления типов технологий", 
            str(e), 
            entity_type="technology_type",
            entity_id=technology_type_id)
        raise ValueError(f"Ошибка при удалении данных.")


def export_technology_type_service(
    user,
    technology_type_filter=None,
    sort_by="id",
    sort_dir="asc",):
    """ Экспортирует данные типов технологий в Excel. """

    log_to_db(
        user, "Начата выгрузка таблицы типов технологий. Параметры экспорта",
        (
            f"Фильтр по столбцу: Наименование типа технологии = {technology_type_filter},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        )
        , entity_type="technology_type"
    )

    # Базовый запрос
    query = technology_type_query(
        technology_type_filter=technology_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(
        user, 
        "Получение данных завершено", 
        f"Найдено записей: {len(items)}", 
        entity_type="technology_type")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Наименование": _dash(o.name),
        })

    log_to_db(
        user, 
        "Подготовка данных для экспорта таблицы типов технологий в Excel",
        f"Записей для экспорта: {len(data)}", 
        entity_type="technology_type")

    df = pd.DataFrame(data)

    # Создание Excel и авто-ширина столбцов
    output = BytesIO()
    sheet_name = "Типы технологий"
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
        "Экспорт таблицы типов технологий в Excel завершен", 
        f"Экспортировано записей: {len(data)}", 
        entity_type="technology_type")
    return output