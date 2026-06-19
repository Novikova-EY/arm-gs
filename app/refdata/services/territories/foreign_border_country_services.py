"""Сервисный модуль: зарубежные страны, имеющие общие границы с РФ."""

from app.extensions import db
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import pandas as pd
from io import BytesIO
from config import SCHEMA_REFDATA

from app.refdata.models.territories.foreign_border_country_model import ForeignBorderCountry

from app.common.services.help_services import _dash
from app.common.services.tranzaction_services import (
    _commit_with_retry,
    _locked_get,
    no_autoflush,
    quick_fix_seq,
)

from app.logs.services.logging_service import log_to_db
from app.logs.services.field_names_ru import format_field_change

from app.common.services.database_version_filter import apply_version_filter, set_db_version_on_create


def foreign_border_country_query(
    foreign_border_country_filter=None,
    sort_by="display_order",
    sort_dir="asc",
):
    """Базовый запрос для выборки стран с фильтрацией и сортировкой."""

    allowed_sort_by = {"id", "name", "display_order", "number"}
    sort_by = sort_by if sort_by in allowed_sort_by else "display_order"

    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    query = ForeignBorderCountry.query.filter(
        ForeignBorderCountry.id.isnot(None),
        ForeignBorderCountry.id > 0,
    )
    query = apply_version_filter(query, ForeignBorderCountry)

    if foreign_border_country_filter:
        query = query.filter(
            ForeignBorderCountry.name.ilike(f"%{foreign_border_country_filter}%")
        )

    if sort_by == "name":
        sort_col = ForeignBorderCountry.name
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    elif sort_by == "display_order":
        if sort_dir == "desc":
            query = query.order_by(
                (ForeignBorderCountry.display_order.is_(None)),
                ForeignBorderCountry.display_order.desc(),
            )
        else:
            query = query.order_by(
                (ForeignBorderCountry.display_order.is_(None)),
                ForeignBorderCountry.display_order.asc(),
            )
    else:
        sort_col = ForeignBorderCountry.id
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    return query


@no_autoflush
def get_foreign_border_country_list(
    page,
    per_page,
    foreign_border_country_filter=None,
    sort_by="display_order",
    sort_dir="asc",
):
    """Получает список стран с пагинацией, фильтрацией и сортировкой."""

    query = foreign_border_country_query(
        foreign_border_country_filter=foreign_border_country_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return query.paginate(page=page, per_page=per_page, error_out=False)


@no_autoflush
def update_foreign_border_country_service(data, user):
    """Обновление данных по зарубежным странам."""

    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    updated_ids = []
    foreign_border_country_id = None

    log_to_db(
        user,
        "Получены данные для обновления списка зарубежных стран",
        f"{data}",
        entity_type="foreign_border_country",
    )

    with db.session.no_autoflush:
        for record in data:
            foreign_border_country_id = record.get("foreign_border_country_id")
            name = (record.get("name") or "").strip()
            display_order = record.get("display_order")

            if not name:
                log_to_db(
                    user,
                    "Ошибка валидации",
                    f"Запись: {record}",
                    entity_type="foreign_border_country",
                    entity_id=foreign_border_country_id,
                )
                raise ValueError("Поле 'name' обязательно для заполнения.")

            obj = db.session.get(ForeignBorderCountry, foreign_border_country_id)
            if not obj:
                log_to_db(
                    user,
                    "Ошибка валидации",
                    f"Запись с ID «{foreign_border_country_id}» не найдена.",
                    entity_type="foreign_border_country",
                    entity_id=foreign_border_country_id,
                )
                raise ValueError(f"Запись с ID «{foreign_border_country_id}» не найдена.")

            if name != (obj.name or ""):
                q = (
                    apply_version_filter(ForeignBorderCountry.query, ForeignBorderCountry)
                    .filter(
                        ForeignBorderCountry.name == name,
                        ForeignBorderCountry.id != foreign_border_country_id,
                    )
                )
                if q.first():
                    raise ValueError(f"Запись с именем «{name}» уже существует.")

            if display_order is not None and display_order != obj.display_order:
                q_display = (
                    apply_version_filter(ForeignBorderCountry.query, ForeignBorderCountry)
                    .filter(
                        ForeignBorderCountry.display_order == display_order,
                        ForeignBorderCountry.id != foreign_border_country_id,
                    )
                )
                if q_display.first():
                    raise ValueError(
                        f"Запись с порядком отображения «{display_order}» уже существует."
                    )

            changes = []

            if name != (obj.name or ""):
                changes.append(
                    format_field_change(
                        "name",
                        obj.name or "не указано",
                        name,
                        "foreign_border_country",
                    )
                )
                obj.name = name

            if display_order != obj.display_order:
                old_val = obj.display_order if obj.display_order is not None else "не указано"
                new_val = display_order if display_order is not None else "не указано"
                changes.append(f"Порядок отображения: {old_val} → {new_val}")
                obj.display_order = display_order

            if changes:
                log_to_db(
                    user,
                    f"Обновлена зарубежная страна: {name}",
                    f"Изменения: {'; '.join(changes)}",
                    entity_type="foreign_border_country",
                    entity_id=foreign_border_country_id,
                )
                updated_ids.append(foreign_border_country_id)

        db.session.flush()

    try:
        _commit_with_retry()

        if updated_ids:
            log_to_db(
                user,
                "Сохранены изменения по зарубежным странам",
                f"Измененных записей: {len(updated_ids)} (id: {updated_ids})",
                entity_type="foreign_border_country",
                entity_id=foreign_border_country_id,
            )
        else:
            log_to_db(
                user,
                "Изменений по зарубежным странам не обнаружено",
                "",
                entity_type="foreign_border_country",
            )

        return updated_ids

    except IntegrityError as e:
        db.session.rollback()
        log_to_db(
            user,
            "Ошибка сохранения зарубежных стран (уникальность/целостность)",
            str(e),
            entity_type="foreign_border_country",
            entity_id=foreign_border_country_id,
        )
        raise ValueError(
            "Ошибка сохранения данных. Возможно, нарушены уникальные ограничения или внешние ключи."
        )
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user,
            "Неизвестная ошибка при сохранении зарубежных стран",
            str(e),
            entity_type="foreign_border_country",
            entity_id=foreign_border_country_id,
        )
        raise ValueError(f"Произошла ошибка при обновлении данных: {e}")


@no_autoflush
def add_foreign_border_country_service(data, user):
    """Создание новой записи: зарубежная страна."""

    if not isinstance(data, list):
        raise ValueError("Данные должны быть предоставлены в виде списка словарей.")

    def _do_insert():
        with db.session.no_autoflush:
            for record in data:
                name = (record.get("name") or "").strip()
                display_order = record.get("display_order")
                if not name:
                    log_to_db(
                        user,
                        "Ошибка валидации",
                        f"Запись: {record}",
                        entity_type="foreign_border_country",
                    )
                    raise ValueError("Каждая запись должна содержать 'name'.")

                dup = (
                    apply_version_filter(ForeignBorderCountry.query, ForeignBorderCountry)
                    .filter(ForeignBorderCountry.name == name)
                    .with_for_update()
                    .first()
                )
                if dup:
                    raise ValueError(f"Запись с наименованием «{name}» уже существует.")

                if display_order is not None:
                    dup_display = (
                        apply_version_filter(ForeignBorderCountry.query, ForeignBorderCountry)
                        .filter(ForeignBorderCountry.display_order == display_order)
                        .with_for_update()
                        .first()
                    )
                    if dup_display:
                        raise ValueError(
                            f"Запись с порядком отображения «{display_order}» уже существует."
                        )

                obj = ForeignBorderCountry(name=name, display_order=display_order)
                set_db_version_on_create(obj)
                db.session.add(obj)
                db.session.flush()

                log_to_db(
                    user,
                    "Создана запись зарубежной страны",
                    f"Наименование: {name}",
                    entity_type="foreign_border_country",
                    entity_id=obj.id,
                )

    try:
        _do_insert()
        _commit_with_retry()
        return None

    except IntegrityError:
        db.session.rollback()
        quick_fix_seq(SCHEMA_REFDATA, "gs_sys_foreign_border_countries")
        _do_insert()
        _commit_with_retry()
        return None
    except Exception as e:
        db.session.rollback()
        log_to_db(
            user,
            "Ошибка сохранения новой зарубежной страны",
            str(e),
            entity_type="foreign_border_country",
        )
        raise ValueError(f"Ошибка сохранения новой зарубежной страны: {e}") from e


@no_autoflush
def delete_foreign_border_country_service(ids, user):
    """Удаляет записи зарубежных стран по переданным ID."""

    if not isinstance(ids, (list, tuple)) or not ids:
        raise ValueError("Не переданы ID для удаления.")

    log_to_db(
        user,
        "Удаление зарубежных стран",
        f"Переданы ID для удаления: {ids}",
        entity_type="foreign_border_country",
    )

    successful_deletes = 0
    deleted_names = []
    not_found = []
    invalid = []
    foreign_border_country_id = None

    for item_id in ids:
        try:
            foreign_border_country_id = int(item_id)
        except (TypeError, ValueError):
            invalid.append(item_id)
            log_to_db(
                user,
                "Ошибка удаления зарубежных стран",
                f"Некорректный ID: {item_id}",
                entity_type="foreign_border_country",
                entity_id=item_id,
            )
            continue

        obj = _locked_get(ForeignBorderCountry, foreign_border_country_id)
        if obj:
            name = obj.name or f"ID={foreign_border_country_id}"
            db.session.delete(obj)
            successful_deletes += 1
            deleted_names.append(name)
            log_to_db(
                user,
                "Удалена зарубежная страна",
                f"{name}",
                entity_type="foreign_border_country",
                entity_id=foreign_border_country_id,
            )
        else:
            not_found.append(foreign_border_country_id)
            log_to_db(
                user,
                "Ошибка удаления зарубежных стран",
                f"Запись с ID={foreign_border_country_id} не найдена.",
                entity_type="foreign_border_country",
                entity_id=foreign_border_country_id,
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
            "Ошибка удаления зарубежных стран",
            str(e),
            entity_type="foreign_border_country",
            entity_id=foreign_border_country_id,
        )
        raise ValueError("Ошибка при удалении данных.")


def export_foreign_border_country_service(
    user,
    foreign_border_country_filter=None,
    sort_by="display_order",
    sort_dir="asc",
):
    """Экспортирует данные зарубежных стран в Excel."""

    log_to_db(
        user,
        "Начата выгрузка таблицы зарубежных стран. Параметры экспорта",
        (
            f"Фильтр по столбцу: Наименование страны = {foreign_border_country_filter},"
            f"Сортировка по = {sort_by}, направление сортировки = {sort_dir}."
        ),
        entity_type="foreign_border_country",
    )

    query = foreign_border_country_query(
        foreign_border_country_filter=foreign_border_country_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )

    items = query.all()
    log_to_db(
        user,
        "Получение данных завершено",
        f"Найдено записей: {len(items)}",
        entity_type="foreign_border_country",
    )

    data = []
    for idx, item in enumerate(items, start=1):
        data.append({
            "№": idx,
            "Наименование": _dash(item.name),
        })

    df = pd.DataFrame(data)

    output = BytesIO()
    sheet_name = "Зарубежные страны"
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]
        for i, col in enumerate(df.columns):
            max_len = max(len(str(col)), *(len(str(v)) for v in df[col].values)) if not df.empty else len(str(col))
            ws.set_column(i, i, min(max_len + 2, 60))

    output.seek(0)
    log_to_db(
        user,
        "Экспорт таблицы зарубежных стран в Excel завершен",
        f"Экспортировано записей: {len(data)}",
        entity_type="foreign_border_country",
    )
    return output


@no_autoflush
def add_foreign_border_country_all_versions_service(data, user):
    from app.refdata.services.refdata_all_versions_common import add_all_versions_records

    def normalize_record(record):
        display_order = record.get("display_order")
        name = (record.get("name") or "").strip()
        if not name:
            raise ValueError("Каждая запись должна содержать 'name'.")
        return {
            "name": name,
            "display_order": display_order,
        }

    def resolve_for_version(clean, version_id):
        return {
            "name": clean["name"],
            "display_order": clean["display_order"],
        }

    return add_all_versions_records(
        data=data,
        user=user,
        model_cls=ForeignBorderCountry,
        entity_type="foreign_border_country",
        normalize_record=normalize_record,
        resolve_for_version=resolve_for_version,
        unique_fields=["name", "display_order"],
    )


@no_autoflush
def update_foreign_border_country_all_versions_service(data, user):
    from app.refdata.services.refdata_all_versions_common import update_all_versions_records

    def normalize_record(record):
        foreign_border_country_id = record.get("foreign_border_country_id")
        display_order = record.get("display_order")
        name = (record.get("name") or "").strip()
        if not name:
            raise ValueError("Поле 'name' обязательно для заполнения.")
        return {
            "foreign_border_country_id": foreign_border_country_id,
            "name": name,
            "display_order": display_order,
        }

    def resolve_for_version(clean, version_id):
        return {
            "name": clean["name"],
            "display_order": clean["display_order"],
        }

    return update_all_versions_records(
        data=data,
        user=user,
        model_cls=ForeignBorderCountry,
        entity_type="foreign_border_country",
        pk_field="foreign_border_country_id",
        normalize_record=normalize_record,
        resolve_for_version=resolve_for_version,
        tracked_fields=["name", "display_order"],
        unique_fields=["name", "display_order"],
        temp_fields=["name"],
        clear_fields=["display_order"],
    )
