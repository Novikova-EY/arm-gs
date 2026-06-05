"""Сервисный модуль: Виды экономической деятельности."""

from app.extensions import db
from sqlalchemy import func as sa_func, text
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO 
from config import SCHEMA_REFDATA
        
# Модели
from app.refdata.models.economic_activity.economic_activity_type_model import EconomicActivityType
from app.economics.models.federal_district_eat_consumption_parameter_model import (
    FederalDistrictEATConsumptionParameter,
)
from app.economics.models.russia_federation_consumption_parameter_model import (
    RussiaFederationConsumptionParameter,
)
from app.economics.models.federal_district_accum_fixed_capital_parameter_model import (
    FederalDistrictAccumFixedCapitalParameter,
)
from app.economics.models.russia_federation_accum_fixed_capital_parameter_model import (
    RussiaFederationAccumFixedCapitalParameter,
)
from app.economics.models.federal_district_product_output_parameter_model import (
    FederalDistrictProductOutputParameter,
)
from app.economics.models.russia_federation_product_output_parameter_model import (
    RussiaFederationProductOutputParameter,
)

_VED_DEPENDENT_PARAMETER_MODELS = (
    FederalDistrictEATConsumptionParameter,
    RussiaFederationConsumptionParameter,
    FederalDistrictAccumFixedCapitalParameter,
    RussiaFederationAccumFixedCapitalParameter,
    FederalDistrictProductOutputParameter,
    RussiaFederationProductOutputParameter,
)

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


def economic_activity_type_query(
        economic_activity_type_filter=None,
        sort_by="display_order",
        sort_dir="asc"):
    """ Базовый запрос для выборки видов экономической деятельности с фильтрацией и сортировкой. """

    # Валидация сортировки
    allowed_sort_by = {"id", "name", "name_2", "display_order", "number"}
    sort_by = sort_by if sort_by in allowed_sort_by else "display_order"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    # Базовый запрос
    query = EconomicActivityType.query.filter(EconomicActivityType.id.isnot(None), EconomicActivityType.id > 0)
    query = apply_version_filter(query, EconomicActivityType)

    # Фильтрация
    if economic_activity_type_filter:
        pattern = f"%{economic_activity_type_filter}%"
        query = query.filter(
            sa_func.coalesce(EconomicActivityType.name, "").ilike(pattern)
            | sa_func.coalesce(EconomicActivityType.name_2, "").ilike(pattern)
        )

    # Сортировка
    if sort_by == "display_order":
        if sort_dir == "desc":
            query = query.order_by(
                (EconomicActivityType.display_order.is_(None)),
                EconomicActivityType.display_order.desc()
            )
        else:
            query = query.order_by(
                (EconomicActivityType.display_order.is_(None)),
                EconomicActivityType.display_order.asc()
            )
    elif sort_by in ("name", "name_2"):
        sort_col = EconomicActivityType.name if sort_by == "name" else EconomicActivityType.name_2
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    else:
        sort_col = EconomicActivityType.id
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    return query


@no_autoflush
def get_economic_activity_type_list(
    page,
    per_page,
    economic_activity_type_filter=None,
    sort_by="display_order",
    sort_dir="asc"):
    """ Получает список видов экономической деятельности с пагинацией, фильтрацией и сортировкой. """
    
    # Базовый запрос
    query = economic_activity_type_query(
        economic_activity_type_filter=economic_activity_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Пагинация
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_economic_activity_type_service(data, user, _retried=False):
    """ Обновление данных по видам экономической деятельности """

    if not isinstance(data, list):
        raise ValueError(f"Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []
    
    log_to_db(
        user, 
        "Получены данные для обновления списка видов экономической деятельности", 
        f"{data}", 
        entity_type="economic_activity_type")
    
    # Проверки на валидность данных
    with db.session.no_autoflush:
        batch = []
        for record in data:
            economic_activity_type_id = record.get("economic_activity_type_id")
            name = (record.get("name") or "").strip()
            name_2 = (record.get("name_2") or "").strip() or None
            display_order = record.get("display_order")

            if not name:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись: {record}", 
                    entity_type="economic_activity_type",
                    entity_id=economic_activity_type_id)
                raise ValueError(f"Поле 'name' обязательно для заполнения.")

            obj = db.session.get(EconomicActivityType, economic_activity_type_id)
            if not obj:
                log_to_db(
                    user, 
                    "Ошибка валидации", 
                    f"Запись с ID «{economic_activity_type_id}» не найдена.", 
                    entity_type="economic_activity_type", 
                    entity_id=economic_activity_type_id)
                raise ValueError(f"Запись с ID «{economic_activity_type_id}» не найдена.")

            # Проверка уникальности name в рамках текущей версии БД
            if name != (obj.name or ""):
                q = apply_version_filter(
                    EconomicActivityType.query.filter(
                        EconomicActivityType.name == name,
                        EconomicActivityType.id != economic_activity_type_id,
                    ),
                    EconomicActivityType,
                )
                if q.first():
                    raise ValueError(f"Запись с именем «{name}» уже существует в текущей версии БД.")

            # Нормализация display_order (из формы может прийти строка или пустое значение)
            if display_order is not None and str(display_order).strip() != "":
                try:
                    display_order = int(display_order)
                except (TypeError, ValueError):
                    display_order = None
            else:
                display_order = None

            batch.append({
                "economic_activity_type_id": economic_activity_type_id,
                "name": name,
                "name_2": name_2,
                "display_order": display_order,
                "obj": obj,
                "prev_display_order": obj.display_order,
            })

        # Сначала сбрасываем порядок у строк, для которых он меняется, чтобы не ловить
        # ложный дубликат при обмене номерами между строками одной формы.
        for item in batch:
            obj = item["obj"]
            if item["display_order"] != obj.display_order:
                obj.display_order = None

        db.session.flush()

        for item in batch:
            economic_activity_type_id = item["economic_activity_type_id"]
            name = item["name"]
            name_2 = item["name_2"]
            display_order = item["display_order"]
            obj = item["obj"]
            prev_do = item["prev_display_order"]

            # Проверка уникальности display_order в рамках текущей версии БД (как в списке на экране)
            if display_order is not None:
                dup = apply_version_filter(
                    EconomicActivityType.query.filter(
                        EconomicActivityType.display_order == display_order,
                        EconomicActivityType.id != economic_activity_type_id,
                    ),
                    EconomicActivityType,
                ).first()
                if dup:
                    other = dup.name or "—"
                    raise ValueError(
                        f"Порядок «{display_order}» уже задан у записи «{other}» (id={dup.id}). "
                        f"Укажите другой номер или измените порядок у той строки. "
                        f"Колонка «№» — это не порядок отображения."
                    )

            changes = []

            if name != (obj.name or ""):
                changes.append(format_field_change("name", obj.name or "не указано", name, "economic_activity_type"))
                obj.name = name

            prev_name_2 = (obj.name_2 or "").strip() or None
            if name_2 != prev_name_2:
                changes.append(
                    format_field_change(
                        "name_2",
                        obj.name_2 or "не указано",
                        name_2 or "не указано",
                        "economic_activity_type",
                    )
                )
                obj.name_2 = name_2

            if display_order != prev_do:
                old_val = prev_do if prev_do is not None else "не указано"
                new_val = display_order if display_order is not None else "не указано"
                changes.append(f"Порядок отображения: {old_val} → {new_val}")
                obj.display_order = display_order

            # Если есть реальные изменения — лог и добавление в список
            if changes:
                log_to_db(
                    user, 
                    f"Обновлен вид экономической деятельности: {name}", 
                    f"Изменения: {'; '.join(changes)}", 
                    entity_type="economic_activity_type", 
                    entity_id=economic_activity_type_id)
                updated_ids.append(economic_activity_type_id)

        db.session.flush()

    try:
        # Сохранение изменений в базе данных
        # Фиксация транзакции (устойчивый коммит)
        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user, 
                "Сохранены изменения по видам экономической деятельности", 
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})", 
                entity_type="economic_activity_type",
                entity_id=economic_activity_type_id)
        else:
            log_to_db(user, "Изменений по видам экономической деятельности не обнаружено", "", entity_type="economic_activity_type")
            
        return updated_ids
    
    except IntegrityError as e:
        db.session.rollback()
        err_str = str(e).lower()
        # При UniqueViolation на gs_sys_refdata_entity_years (рассинхронизация sequence) — выравниваем и повторяем 1 раз
        if not _retried and ("gs_sys_refdata_entity_years" in err_str or "refdata_entity_years_pkey" in err_str):
            try:
                quick_fix_seq(SCHEMA_REFDATA, "gs_sys_refdata_entity_years")
                quick_fix_seq(SCHEMA_REFDATA, "gs_sys_refdata_entities")
                return update_economic_activity_type_service(data, user, _retried=True)
            except ValueError:
                raise
            except Exception:
                pass
        log_to_db(
            user, 
            "Ошибка сохранения видов экономической деятельности (уникальность/целостность)", 
            str(e), 
            entity_type="economic_activity_type",
            entity_id=economic_activity_type_id)
        raise ValueError(f"Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи.")
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Неизвестная ошибка при сохранении видов экономической деятельности", 
            str(e), 
            entity_type="economic_activity_type",
            entity_id=economic_activity_type_id)
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_economic_activity_type_service(data, user):
    """Создание новой записи: вид экономической деятельности"""
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    def _do_insert():
        with db.session.no_autoflush:
            for record in data:
                name = (record.get("name") or "").strip()
                name_2 = (record.get("name_2") or "").strip() or None
                display_order = record.get("display_order")
                if not name:
                    log_to_db(
                        user, 
                        "Ошибка валидации", 
                        f"Запись: {record}", 
                        entity_type="economic_activity_type")
                    raise ValueError("Каждая запись должна содержать 'name'.")

                dup = (
                    apply_version_filter(
                        EconomicActivityType.query.filter(EconomicActivityType.name == name),
                        EconomicActivityType,
                    )
                    .with_for_update()
                    .first()
                )
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует в текущей версии БД.")

                if display_order is not None:
                    try:
                        display_order = int(display_order)
                    except (TypeError, ValueError):
                        display_order = None
                if display_order is not None:
                    dup_order = apply_version_filter(
                        EconomicActivityType.query.filter(
                            EconomicActivityType.display_order == display_order,
                        ),
                        EconomicActivityType,
                    ).first()
                    if dup_order:
                        other = dup_order.name or "—"
                        raise ValueError(
                            f"Порядок «{display_order}» уже задан у записи «{other}» (id={dup_order.id})."
                        )

                obj = EconomicActivityType(name=name, name_2=name_2, display_order=display_order)
                set_db_version_on_create(obj)
                db.session.add(obj)
                db.session.flush()

                log_to_db(
                    user, 
                    "Создан вид экономической деятельности", 
                    f"Наименование: {name}",
                    entity_type="economic_activity_type", 
                    entity_id=obj.id)

    try:
        _do_insert()
        _commit_with_retry()
        return None

    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "economic_activity_types")
        _do_insert()
        _commit_with_retry()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка сохранения нового вида экономической деятельности", 
            str(e), 
            entity_type="economic_activity_type")
        raise ValueError(f"Ошибка сохранения нового вида экономической деятельности: {e}") from e


def _purge_economic_activity_type_dependent_parameters(ved_id: int) -> int:
    """Удаляет строки долгосрочного прогноза, ссылающиеся на вид экономической деятельности."""
    removed = 0
    for model in _VED_DEPENDENT_PARAMETER_MODELS:
        removed += (
            model.query.filter_by(id_economic_activity_type=ved_id)
            .delete(synchronize_session=False)
        )
    return removed


@no_autoflush
def delete_economic_activity_type_service(ids, user):
    """Удаляет записи видов экономической деятельности по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError(f"Не переданы ID для удаления.")

    log_to_db(
        user, 
        "Удаление видов экономической деятельности", 
        f"Переданы ID для удаления: {ids}", 
        entity_type="economic_activity_type")

    successful_deletes = 0
    deleted_record_ids = []
    deleted_names = []
    not_found = []
    invalid = []

    for ft_id in ids:
        try:
            economic_activity_type_id = int(ft_id)
        except (TypeError, ValueError):
            invalid.append(ft_id)
            log_to_db(
                user, 
                "Ошибка удаления видов экономической деятельности", 
                f"Некорректный ID: {ft_id}", 
                entity_type="economic_activity_type",
                entity_id=ft_id)
            continue

        obj = _locked_get(EconomicActivityType, economic_activity_type_id)
        if obj:
            name = obj.name or f"ID={economic_activity_type_id}"
            removed_params = _purge_economic_activity_type_dependent_parameters(
                economic_activity_type_id
            )
            if removed_params:
                log_to_db(
                    user,
                    "Удалены связанные данные долгосрочного прогноза по ВЭД",
                    f"ВЭД id={economic_activity_type_id}, удалено строк: {removed_params}",
                    entity_type="economic_activity_type",
                    entity_id=economic_activity_type_id,
                )
            db.session.delete(obj)
            successful_deletes += 1
            deleted_record_ids.append(economic_activity_type_id)
            deleted_names.append(name)
            log_to_db(
                user, 
                "Удален вид экономической деятельности", 
                f"{name}", 
                entity_type="economic_activity_type", 
                entity_id=economic_activity_type_id)
        else:
            not_found.append(economic_activity_type_id)
            log_to_db(
                user, 
                "Ошибка удаления видов экономической деятельности", 
                f"Вид экономической деятельности с ID={economic_activity_type_id} не найден.", 
                entity_type="economic_activity_type", 
                entity_id=economic_activity_type_id)

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
            "deleted_ids": deleted_record_ids,
            "deleted_names": deleted_names,
            "not_found": not_found,
            "invalid": invalid,
        }
    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user,
            "Ошибка удаления видов экономической деятельности (целостность)",
            str(e),
            entity_type="economic_activity_type",
            entity_id=economic_activity_type_id,
        )
        raise ValueError(
            "Невозможно удалить вид экономической деятельности: на него ссылаются "
            "другие данные в системе. Сначала удалите связанные записи или обратитесь к администратору."
        ) from e
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user, 
            "Ошибка удаления видов экономической деятельности", 
            str(e), 
            entity_type="economic_activity_type",
            entity_id=economic_activity_type_id)
        raise ValueError(f"Ошибка при удалении данных.") from e


def export_economic_activity_type_service(
    user,
    economic_activity_type_filter=None,
    sort_by="display_order",
    sort_dir="asc",):
    """ Экспортирует данные видов экономической деятельности в Excel. """

    log_to_db(
        user, "Начата выгрузка таблицы видов экономической деятельности. Параметры экспорта",
        (
            f"Фильтр по столбцу: Наименование вида экономической деятельности = {economic_activity_type_filter},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        )
        , entity_type="economic_activity_type"
    )

    # Базовый запрос
    query = economic_activity_type_query(
        economic_activity_type_filter=economic_activity_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    # Получение данных
    items = query.all()
    log_to_db(
        user, 
        "Получение данных завершено", 
        f"Найдено записей: {len(items)}", 
        entity_type="economic_activity_type")

    # Подготовка данных для Excel
    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Порядок отображения": o.display_order if o.display_order is not None else "",
            "Наименование": _dash(o.name),
            "Вид экономической деятельности_2": _dash(o.name_2),
        })

    log_to_db(
        user, 
        "Подготовка данных для экспорта таблицы видов экономической деятельности в Excel",
        f"Записей для экспорта: {len(data)}", 
        entity_type="economic_activity_type")

    df = pd.DataFrame(data)

    # Создание Excel и авто-ширина столбцов
    output = BytesIO()
    sheet_name = "Виды экономической деятельности"
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
        "Экспорт таблицы видов экономической деятельности в Excel завершен", 
        f"Экспортировано записей: {len(data)}", 
        entity_type="economic_activity_type")
    return output

# === all_versions_economic_activity_type start ===
@no_autoflush
def add_economic_activity_type_all_versions_service(data, user):
    from app.refdata.services.refdata_all_versions_common import add_all_versions_records, update_all_versions_records, fk_id_for_version

    def normalize_record(record):
        display_order = record.get("display_order")
        name = (record.get("name") or "").strip()
        name_2 = (record.get("name_2") or "").strip() or None
        if not name:
            raise ValueError("Каждая запись должна содержать 'name'.")
        return {
            "name": name,
            "name_2": name_2,
            "display_order": display_order,
        }

    def resolve_for_version(clean, version_id):
        return {
            "name": clean["name"],
            "name_2": clean["name_2"],
            "display_order": clean["display_order"],
        }

    return add_all_versions_records(
        data=data,
        user=user,
        model_cls=EconomicActivityType,
        entity_type="economic_activity_type",
        normalize_record=normalize_record,
        resolve_for_version=resolve_for_version,
        unique_fields=['name', 'display_order']
    )


@no_autoflush
def update_economic_activity_type_all_versions_service(data, user):
    from app.refdata.services.refdata_all_versions_common import add_all_versions_records, update_all_versions_records, fk_id_for_version

    def normalize_record(record):
        economic_activity_type_id = record.get("economic_activity_type_id")
        display_order = record.get("display_order")
        name = (record.get("name") or "").strip()
        name_2 = (record.get("name_2") or "").strip() or None
        if not name:
            raise ValueError("Поле 'name' обязательно для заполнения.")
        return {
            "economic_activity_type_id": economic_activity_type_id,
            "name": name,
            "name_2": name_2,
            "display_order": display_order,
        }

    def resolve_for_version(clean, version_id):
        return {
            "name": clean["name"],
            "name_2": clean["name_2"],
            "display_order": clean["display_order"],
        }

    return update_all_versions_records(
        data=data,
        user=user,
        model_cls=EconomicActivityType,
        entity_type="economic_activity_type",
        pk_field="economic_activity_type_id",
        normalize_record=normalize_record,
        resolve_for_version=resolve_for_version,
        tracked_fields=['name', 'name_2', 'display_order'],
        unique_fields=['name', 'display_order'],
        temp_fields=['name'],
        clear_fields=['display_order']
    )
# === all_versions_economic_activity_type end ===
