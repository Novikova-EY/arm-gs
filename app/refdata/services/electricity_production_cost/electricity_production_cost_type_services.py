"""Сервисный модуль: затраты на производство и реализацию электрической энергии (мощности)."""

from app.extensions import db
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO
from config import SCHEMA_REFDATA

from app.refdata.models.electricity_production_cost.electricity_production_cost_type_model import (
    ElectricityProductionCostType,
)

from app.common.services.help_services import (
    _dash,
)
from app.common.services.tranzaction_services import (
    _commit_with_retry,
    _locked_get,
    no_autoflush,
    quick_fix_seq,
)

from app.common.services.database_version_filter import (
    apply_version_filter,
    set_db_version_on_create,
)

from app.logs.services.logging_service import log_to_db
from app.logs.services.field_names_ru import format_field_change


def electricity_production_cost_type_query(
        electricity_production_cost_type_filter=None,
        sort_by="cost_code",
        sort_dir="asc"):
    """Базовый запрос с фильтрацией и сортировкой."""

    allowed_sort_by = {"id", "name", "cost_code", "number"}
    sort_by = sort_by if sort_by in allowed_sort_by else "cost_code"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    query = ElectricityProductionCostType.query.filter(
        ElectricityProductionCostType.id.isnot(None),
        ElectricityProductionCostType.id > 0,
    )
    query = apply_version_filter(query, ElectricityProductionCostType)

    if electricity_production_cost_type_filter:
        query = query.filter(
            ElectricityProductionCostType.name.ilike(
                f"%{electricity_production_cost_type_filter}%"
            )
        )

    if sort_by == "cost_code":
        if sort_dir == "desc":
            query = query.order_by(
                (ElectricityProductionCostType.cost_code.is_(None)),
                ElectricityProductionCostType.cost_code.desc(),
            )
        else:
            query = query.order_by(
                (ElectricityProductionCostType.cost_code.is_(None)),
                ElectricityProductionCostType.cost_code.asc(),
            )
    elif sort_by == "name":
        sort_col = ElectricityProductionCostType.name
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    else:
        sort_col = ElectricityProductionCostType.id
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    return query


@no_autoflush
def get_electricity_production_cost_type_list(
    page,
    per_page,
    electricity_production_cost_type_filter=None,
    sort_by="cost_code",
    sort_dir="asc",
):
    query = electricity_production_cost_type_query(
        electricity_production_cost_type_filter=electricity_production_cost_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_electricity_production_cost_type_service(data, user, _retried=False):
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []

    log_to_db(
        user,
        "Получены данные для обновления списка затрат на производство ЭЭ (мощности)",
        f"{data}",
        entity_type="electricity_production_cost_type",
    )

    with db.session.no_autoflush:
        batch = []
        for record in data:
            record_id = record.get("electricity_production_cost_type_id")
            name = (record.get("name") or "").strip()
            cost_code = record.get("cost_code")

            if not name:
                log_to_db(
                    user,
                    "Ошибка валидации",
                    f"Запись: {record}",
                    entity_type="electricity_production_cost_type",
                    entity_id=record_id,
                )
                raise ValueError("Поле 'name' обязательно для заполнения.")

            obj = db.session.get(ElectricityProductionCostType, record_id)
            if not obj:
                log_to_db(
                    user,
                    "Ошибка валидации",
                    f"Запись с ID «{record_id}» не найдена.",
                    entity_type="electricity_production_cost_type",
                    entity_id=record_id,
                )
                raise ValueError(f"Запись с ID «{record_id}» не найдена.")

            if name != (obj.name or ""):
                q = apply_version_filter(
                    ElectricityProductionCostType.query.filter(
                        ElectricityProductionCostType.name == name,
                        ElectricityProductionCostType.id != record_id,
                    ),
                    ElectricityProductionCostType,
                )
                if q.first():
                    raise ValueError(f"Запись с именем «{name}» уже существует в текущей версии БД.")

            if cost_code is not None and str(cost_code).strip() != "":
                try:
                    cost_code = int(cost_code)
                except (TypeError, ValueError):
                    cost_code = None
            else:
                cost_code = None

            batch.append({
                "electricity_production_cost_type_id": record_id,
                "name": name,
                "cost_code": cost_code,
                "obj": obj,
                "prev_cost_code": obj.cost_code,
            })

        for item in batch:
            obj = item["obj"]
            if item["cost_code"] != obj.cost_code:
                obj.cost_code = None

        db.session.flush()

        for item in batch:
            record_id = item["electricity_production_cost_type_id"]
            name = item["name"]
            cost_code = item["cost_code"]
            obj = item["obj"]
            prev_code = item["prev_cost_code"]

            if cost_code is not None:
                dup = apply_version_filter(
                    ElectricityProductionCostType.query.filter(
                        ElectricityProductionCostType.cost_code == cost_code,
                        ElectricityProductionCostType.id != record_id,
                    ),
                    ElectricityProductionCostType,
                ).first()
                if dup:
                    other = dup.name or "—"
                    raise ValueError(
                        f"Код затрат «{cost_code}» уже задан у записи «{other}» (id={dup.id}). "
                        f"Укажите другой код или измените код у той строки. "
                        f"Колонка «№» — это не код затрат."
                    )

            changes = []

            if name != (obj.name or ""):
                changes.append(
                    format_field_change(
                        "name",
                        obj.name or "не указано",
                        name,
                        "electricity_production_cost_type",
                    )
                )
                obj.name = name

            if cost_code != prev_code:
                old_val = prev_code if prev_code is not None else "не указано"
                new_val = cost_code if cost_code is not None else "не указано"
                changes.append(f"Код затрат: {old_val} → {new_val}")
                obj.cost_code = cost_code

            if changes:
                log_to_db(
                    user,
                    f"Обновлена запись затрат на производство ЭЭ (мощности): {name}",
                    f"Изменения: {'; '.join(changes)}",
                    entity_type="electricity_production_cost_type",
                    entity_id=record_id,
                )
                updated_ids.append(record_id)

        db.session.flush()

    try:
        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user,
                "Сохранены изменения по затратам на производство ЭЭ (мощности)",
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})",
                entity_type="electricity_production_cost_type",
                entity_id=record_id,
            )
        else:
            log_to_db(
                user,
                "Изменений по затратам на производство ЭЭ (мощности) не обнаружено",
                "",
                entity_type="electricity_production_cost_type",
            )

        return updated_ids

    except IntegrityError as e:
        db.session.rollback()
        err_str = str(e).lower()
        if not _retried and (
            "gs_sys_refdata_entity_years" in err_str
            or "refdata_entity_years_pkey" in err_str
        ):
            try:
                quick_fix_seq(SCHEMA_REFDATA, "gs_sys_refdata_entity_years")
                quick_fix_seq(SCHEMA_REFDATA, "gs_sys_refdata_entities")
                return update_electricity_production_cost_type_service(data, user, _retried=True)
            except ValueError:
                raise
            except Exception:
                pass
        log_to_db(
            user,
            "Ошибка сохранения затрат на производство ЭЭ (мощности) (уникальность/целостность)",
            str(e),
            entity_type="electricity_production_cost_type",
            entity_id=record_id,
        )
        raise ValueError(
            "Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи."
        )
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user,
            "Неизвестная ошибка при сохранении затрат на производство ЭЭ (мощности)",
            str(e),
            entity_type="electricity_production_cost_type",
            entity_id=record_id,
        )
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_electricity_production_cost_type_service(data, user):
    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    def _do_insert():
        with db.session.no_autoflush:
            for record in data:
                name = (record.get("name") or "").strip()
                cost_code = record.get("cost_code")
                if not name:
                    log_to_db(
                        user,
                        "Ошибка валидации",
                        f"Запись: {record}",
                        entity_type="electricity_production_cost_type",
                    )
                    raise ValueError("Каждая запись должна содержать 'name'.")

                dup = (
                    apply_version_filter(
                        ElectricityProductionCostType.query.filter(
                            ElectricityProductionCostType.name == name,
                        ),
                        ElectricityProductionCostType,
                    )
                    .with_for_update()
                    .first()
                )
                if dup:
                    raise ValueError(
                        f"Запись с наименованием «{name}» уже существует в текущей версии БД."
                    )

                if cost_code is not None:
                    try:
                        cost_code = int(cost_code)
                    except (TypeError, ValueError):
                        cost_code = None
                if cost_code is not None:
                    dup_code = apply_version_filter(
                        ElectricityProductionCostType.query.filter(
                            ElectricityProductionCostType.cost_code == cost_code,
                        ),
                        ElectricityProductionCostType,
                    ).first()
                    if dup_code:
                        other = dup_code.name or "—"
                        raise ValueError(
                            f"Код затрат «{cost_code}» уже задан у записи «{other}» (id={dup_code.id})."
                        )

                obj = ElectricityProductionCostType(name=name, cost_code=cost_code)
                set_db_version_on_create(obj)
                db.session.add(obj)
                db.session.flush()

                log_to_db(
                    user,
                    "Создана запись затрат на производство ЭЭ (мощности)",
                    f"Наименование: {name}",
                    entity_type="electricity_production_cost_type",
                    entity_id=obj.id,
                )

    try:
        _do_insert()
        _commit_with_retry()
        return None

    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "gs_sys_electricity_production_cost_types")
        _do_insert()
        _commit_with_retry()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user,
            "Ошибка сохранения новой записи затрат на производство ЭЭ (мощности)",
            str(e),
            entity_type="electricity_production_cost_type",
        )
        raise ValueError(
            f"Ошибка сохранения новой записи затрат на производство ЭЭ (мощности): {e}"
        ) from e


@no_autoflush
def delete_electricity_production_cost_type_service(ids, user):
    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError("Не переданы ID для удаления.")

    log_to_db(
        user,
        "Удаление записей затрат на производство ЭЭ (мощности)",
        f"Переданы ID для удаления: {ids}",
        entity_type="electricity_production_cost_type",
    )

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []

    for item_id in ids:
        try:
            record_id = int(item_id)
        except (TypeError, ValueError):
            invalid.append(item_id)
            log_to_db(
                user,
                "Ошибка удаления затрат на производство ЭЭ (мощности)",
                f"Некорректный ID: {item_id}",
                entity_type="electricity_production_cost_type",
                entity_id=item_id,
            )
            continue

        obj = _locked_get(ElectricityProductionCostType, record_id)
        if obj:
            name = obj.name or f"ID={record_id}"
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            log_to_db(
                user,
                "Удалена запись затрат на производство ЭЭ (мощности)",
                f"{name}",
                entity_type="electricity_production_cost_type",
                entity_id=record_id,
            )
        else:
            not_found.append(record_id)
            log_to_db(
                user,
                "Ошибка удаления затрат на производство ЭЭ (мощности)",
                f"Запись с ID={record_id} не найдена.",
                entity_type="electricity_production_cost_type",
                entity_id=record_id,
            )

    try:
        _commit_with_retry()

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
            "Ошибка удаления затрат на производство ЭЭ (мощности)",
            str(e),
            entity_type="electricity_production_cost_type",
            entity_id=record_id,
        )
        raise ValueError("Ошибка при удалении данных.")


def export_electricity_production_cost_type_service(
    user,
    electricity_production_cost_type_filter=None,
    sort_by="cost_code",
    sort_dir="asc",
):
    log_to_db(
        user,
        "Начата выгрузка таблицы затрат на производство ЭЭ (мощности). Параметры экспорта",
        (
            f"Фильтр по столбцу: Наименование = {electricity_production_cost_type_filter},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        ),
        entity_type="electricity_production_cost_type",
    )

    query = electricity_production_cost_type_query(
        electricity_production_cost_type_filter=electricity_production_cost_type_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    items = query.all()
    log_to_db(
        user,
        "Получение данных завершено",
        f"Найдено записей: {len(items)}",
        entity_type="electricity_production_cost_type",
    )

    data = []
    for idx, o in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Код затрат": o.cost_code if o.cost_code is not None else "",
            "Наименование": _dash(o.name),
        })

    df = pd.DataFrame(data)

    output = BytesIO()
    sheet_name = "Затраты на производство ЭЭ"
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]

        for i, col in enumerate(df.columns):
            max_len = max(len(str(col)), *(len(str(v)) for v in df[col].values)) if not df.empty else len(str(col))
            ws.set_column(i, i, min(max_len + 2, 60))

    output.seek(0)
    log_to_db(
        user,
        "Экспорт таблицы затрат на производство ЭЭ (мощности) в Excel завершен",
        f"Экспортировано записей: {len(data)}",
        entity_type="electricity_production_cost_type",
    )
    return output


@no_autoflush
def add_electricity_production_cost_type_all_versions_service(data, user):
    from app.refdata.services.refdata_all_versions_common import add_all_versions_records

    def normalize_record(record):
        cost_code = record.get("cost_code")
        name = (record.get("name") or "").strip()
        if not name:
            raise ValueError("Каждая запись должна содержать 'name'.")
        return {
            "name": name,
            "cost_code": cost_code,
        }

    def resolve_for_version(clean, version_id):
        return {
            "name": clean["name"],
            "cost_code": clean["cost_code"],
        }

    return add_all_versions_records(
        data=data,
        user=user,
        model_cls=ElectricityProductionCostType,
        entity_type="electricity_production_cost_type",
        normalize_record=normalize_record,
        resolve_for_version=resolve_for_version,
        unique_fields=['name', 'cost_code'],
    )


@no_autoflush
def update_electricity_production_cost_type_all_versions_service(data, user):
    from app.refdata.services.refdata_all_versions_common import update_all_versions_records

    def normalize_record(record):
        record_id = record.get("electricity_production_cost_type_id")
        cost_code = record.get("cost_code")
        name = (record.get("name") or "").strip()
        if not name:
            raise ValueError("Поле 'name' обязательно для заполнения.")
        return {
            "electricity_production_cost_type_id": record_id,
            "name": name,
            "cost_code": cost_code,
        }

    def resolve_for_version(clean, version_id):
        return {
            "name": clean["name"],
            "cost_code": clean["cost_code"],
        }

    return update_all_versions_records(
        data=data,
        user=user,
        model_cls=ElectricityProductionCostType,
        entity_type="electricity_production_cost_type",
        pk_field="electricity_production_cost_type_id",
        normalize_record=normalize_record,
        resolve_for_version=resolve_for_version,
        tracked_fields=['name', 'cost_code'],
        unique_fields=['name', 'cost_code'],
        temp_fields=['name'],
        clear_fields=['cost_code'],
    )
