"""Сервисный модуль: Типы состояния (ConditionType)."""

from app.extensions import db
from sqlalchemy import or_, text
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO
from config import SCHEMA_REFDATA

# Модель
from app.refdata.models.refdata_for_stations.condition_type_model import ConditionType

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


def condition_type_query(
    condition_type_filter: str | None = None, 
    sort_by: str = "id", 
    sort_dir: str = "asc"):
    """Базовый запрос выборки типов состояния с фильтрацией и сортировкой."""

    # Валидация сортировки
    allowed_sort_by = {"id", "name"}
    sort_by = sort_by if sort_by in allowed_sort_by else "id"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Базовый запрос
    query = ConditionType.query.filter(ConditionType.id > 0)
    query = apply_version_filter(query, ConditionType)

    # Фильтрация
    if condition_type_filter:
        query = query.filter(or_(ConditionType.name.ilike(f"%{condition_type_filter}%")))

    # Сортировка
    sort_col = ConditionType.name if sort_by == "name" else ConditionType.id

    query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    
    return query


@no_autoflush
def get_condition_type_list(
    page: int, 
    per_page: int, 
    condition_type_filter: str | None = None, 
    sort_by: str = "id", 
    sort_dir: str = "asc"):
    """ Получает список типов состояния с пагинацией."""

    # Базовый запрос
    query = condition_type_query(
        condition_type_filter=condition_type_filter, 
        sort_by=sort_by, 
        sort_dir=sort_dir)

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_condition_type_service(data: list[dict], user: str):
    """Обновление данных по типам состояния."""

    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    updated_ids: list[int] = []

    log_to_db(
        user,
        "Получены данные для обновления списка типов состояния",
        f"{data}",
        entity_type="condition_type")

    # Проверки на валидность данных
    with db.session.no_autoflush:
        for record in data:
            condition_type_id = record.get("condition_type_id")
            name = (record.get("name") or "").strip()

            if not name:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись: {record}", 
                    entity_type="condition_type",
                    entity_id=condition_type_id)
                raise ValueError("Поле 'name' обязательно для заполнения.")

            obj = db.session.get(ConditionType, condition_type_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{condition_type_id}» не найдена.", 
                    entity_type="condition_type", 
                    entity_id=condition_type_id)
                raise ValueError(f"Запись с ID «{condition_type_id}» не найдена.")

            # Проверка уникальности name
            if name != (obj.name or ""):
                q = (apply_version_filter(ConditionType.query, ConditionType)
                        .filter(ConditionType.name == name, 
                                ConditionType.id != condition_type_id))
                if q.first():
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")

            changes = []

            if name != (obj.name or ""):
                changes.append(format_field_change("name", obj.name or "не указано", name, "condition_type"))
                obj.name = name

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    "Обновлен тип состояния", 
                    f"Изменения: {'; '.join(changes)}", 
                    entity_type="condition_type", 
                    entity_id=condition_type_id)
                updated_ids.append(condition_type_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по типам состояния", 
                f"Изменено записей: {len(updated_ids)}", 
                entity_type="condition_type"
                )
        else:
            log_to_db(
                user, 
                "Изменений по типам состояния не обнаружено", 
                "", 
                entity_type="condition_type")

        return updated_ids

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user,
            "Ошибка сохранения типов состояния (уникальность/целостность)",
            str(e),
            entity_type="condition_type"
            )
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Неизвестная ошибка при сохранении типов состояния", 
            str(e), 
            entity_type="condition_type"
            )
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_condition_type_service(data: list[dict], user: str):
    """Создание новой записи: тип состояния."""
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    def _do_insert():
        with db.session.no_autoflush:
            # Итерация по входным данным (валидация/применение)
            for record in data:
                name = (record.get("name") or "").strip()

                if not name:
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись: {record}", 
                        entity_type="condition_type")
                    raise ValueError(f"Каждая запись должна содержать 'name'. Данные: {record}")

                dup = (apply_version_filter(ConditionType.query, ConditionType)
                        .filter(ConditionType.name == name)
                        .with_for_update().first())
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")

                # Создаем новую запись
                obj = ConditionType(
                    name=name
                    )
                set_db_version_on_create(obj)
                db.session.add(obj)
                db.session.flush()  # получить id без полного коммита

                log_to_db(
                    user, 
                    "Создан тип состояния", 
                    f"Наименование: {name}", 
                    entity_type="condition_type",
                    entity_id=obj.id)

    try:
        _do_insert()
        _commit_with_retry()
        return None

    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "condition_types")
        _do_insert()
        _commit_with_retry()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения нового типа состояния", 
            str(e), 
            entity_type="condition_type"
            )
        raise ValueError(f"Ошибка сохранения нового типа состояния: {e}")


@no_autoflush
def delete_condition_type_service(ids: list[int], user: str):
    """Удаление записей типов состояния по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError("Не переданы ID для удаления.")

    log_to_db(
        user, 
        "Удаление типов состояния", 
        f"Переданы ID для удаления: {ids}", 
        entity_type="condition_type")

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for any_id in ids:
        try:
            condition_type_id = int(any_id)
        except (TypeError, ValueError):
            invalid.append(any_id)
            log_to_db(
                user,
                "Ошибка удаления типов состояния",
                f"Некорректный ID: {any_id}",
                entity_type="condition_type",
                entity_id=any_id)
            continue

        obj = _locked_get(ConditionType, condition_type_id)
        if obj:
            name = _dash(obj.name)
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            log_to_db(
                user, 
                "Удален тип состояния", 
                f"Наименование: {name}", 
                entity_type="condition_type",
                entity_id=condition_type_id)
        else:
            not_found.append(condition_type_id)
            log_to_db(
                user,
                "Ошибка удаления типов состояния",
                f"Тип состояния с ID={condition_type_id} не найден.",
                entity_type="condition_type",
                entity_id=condition_type_id)
    
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
            "Ошибка удаления типов состояния", 
            str(e), 
            entity_type="condition_type",
            entity_id=condition_type_id)
        raise ValueError(f"Ошибка при удалении данных.")


def export_condition_type_service(
    user: str, 
    condition_type_filter: str | None = None, 
    sort_by: str = "id", 
    sort_dir: str = "asc"
):
    """Экспортирует данные типов состояния в Excel."""

    log_to_db(
        user, 
        "Начата выгрузка типов состояния в Excel", 
        "",
        entity_type="condition_type"
        )
    log_to_db(
        user,
        "Параметры экспорта",
        (
            f"Фильтр по столбцу: Наименование типа состояния = {condition_type_filter},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        ),
        entity_type="condition_type"
    )

    query = condition_type_query(
        condition_type_filter=condition_type_filter, 
        sort_by=sort_by, 
        sort_dir=sort_dir)
    
    # Получение данных
    items = query.all()
    log_to_db(
        user, 
        "Получение данных завершено", 
        f"Найдено записей: {len(items)}", 
        entity_type="condition_type")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Наименование": _dash(o.name),
        })

    log_to_db(
        user,
        "Подготовка данных для экспорта таблицы типов состояния в Excel",
        f"Записей для экспорта: {len(data)}",
        entity_type="condition_type")

    df = pd.DataFrame(data)

    # Создание Excel и авто-ширина столбцов
    output = BytesIO()
    sheet_name = "Типы состояния"
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
        "Экспорт типов состояния завершен", 
        f"Экспортировано записей: {len(data)}", 
        entity_type="condition_type"
        )
    return output

# === all_versions_condition_type start ===
@no_autoflush
def add_condition_type_all_versions_service(data, user):
    from app.refdata.services.refdata_all_versions_common import add_all_versions_records, update_all_versions_records, fk_id_for_version

    def normalize_record(record):
        name = (record.get("name") or "").strip()
        if not name:
            raise ValueError("Каждая запись должна содержать 'name'.")
        return {
            "name": name,
        }

    def resolve_for_version(clean, version_id):
        return {
            "name": clean["name"],
        }

    return add_all_versions_records(
        data=data,
        user=user,
        model_cls=ConditionType,
        entity_type="condition_type",
        normalize_record=normalize_record,
        resolve_for_version=resolve_for_version,
        unique_fields=['name']
    )


@no_autoflush
def update_condition_type_all_versions_service(data, user):
    from app.refdata.services.refdata_all_versions_common import add_all_versions_records, update_all_versions_records, fk_id_for_version

    def normalize_record(record):
        condition_type_id = record.get("condition_type_id")
        name = (record.get("name") or "").strip()
        if not name:
            raise ValueError("Поле 'name' обязательно для заполнения.")
        return {
            "condition_type_id": condition_type_id,
            "name": name,
        }

    def resolve_for_version(clean, version_id):
        return {
            "name": clean["name"],
        }

    return update_all_versions_records(
        data=data,
        user=user,
        model_cls=ConditionType,
        entity_type="condition_type",
        pk_field="condition_type_id",
        normalize_record=normalize_record,
        resolve_for_version=resolve_for_version,
        tracked_fields=['name'],
        unique_fields=['name'],
        temp_fields=['name'],
        clear_fields=[]
    )
# === all_versions_condition_type end ===
