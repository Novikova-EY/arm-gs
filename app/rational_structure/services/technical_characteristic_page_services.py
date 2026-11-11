import json
from decimal import Decimal

from sqlalchemy import false, func, or_, select
from werkzeug.datastructures import MultiDict

from app.common.services.help_services import format_decimal_for_display
from app.extensions import db
from app.rational_structure.models import TurbineTechnicalCharacteristic
from app.rational_structure.equipment_types import DEFAULT_PAGE, EQUIPMENT_TYPES, MATCHABLE_TYPES, PAGES
from app.rational_structure.services.technical_characteristic_columns import TURBINE_TYPES, columns_for_equipment
from app.rational_structure.services.technical_characteristic_group_links import station_head_group_ids
from app.refdata.models.years.year_model import Year
from config import END_YEAR, START_YEAR


def _filter_token(value):
    if isinstance(value, Decimal):
        value = format(value.normalize(), "f")
    return json.dumps(None if value in (None, "") else str(value), ensure_ascii=False)


def build_technical_characteristic_context(args: MultiDict, version_id: int | None, *, page_key: str = DEFAULT_PAGE) -> dict:
    model = TurbineTechnicalCharacteristic
    page_config = PAGES[page_key]
    equipment_types = page_config["equipment_types"]
    matchable = bool(MATCHABLE_TYPES.intersection(equipment_types))
    base = select(model).where(model.database_version_id == version_id, model.equipment_type.in_(equipment_types))
    data_years = list(db.session.scalars(base.with_only_columns(model.report_year).distinct().order_by(model.report_year.desc())))
    reference_years = list(db.session.scalars(select(Year.number).where(Year.database_version_id == version_id)))
    selected_year = args.get("year", type=int)
    if selected_year is None or not 1900 <= selected_year <= 2200:
        selected_year = data_years[0] if data_years else START_YEAR
    years = sorted(set(reference_years or range(START_YEAR, END_YEAR + 1)) | set(data_years) | {selected_year})
    filters = {key: args.get(key, "").strip() for key in ("turbine_type", "subject", "station", "aggregate", "search", "match_status")}
    filters["year"] = str(selected_year)
    filters["equipment_type"] = args.get("equipment_type", filters["turbine_type"]).strip()
    rounding_digits = args.get("rounding_digits", 1, type=int)
    if rounding_digits not in (-1, 0, 1, 2, 3):
        rounding_digits = 1
    base = base.where(model.report_year == selected_year)
    statement = base
    if filters["equipment_type"]:
        statement = statement.where(model.equipment_type == filters["equipment_type"])
    for key, field in (("subject", model.subject_name), ("station", model.station_name)):
        if filters[key]:
            statement = statement.where(field.contains(filters[key], autoescape=True))
    for key, fields in (
        ("aggregate", (model.equipment_brand, model.station_number)),
        ("search", (model.equipment_code, model.equipment_brand, model.station_number)),
    ):
        if filters[key]:
            statement = statement.where(or_(*(field.contains(filters[key], autoescape=True) for field in fields)))
    if matchable and filters["match_status"]:
        statement = statement.where(model.match_status == filters["match_status"])

    extra_labels = set()
    for values in db.session.scalars(base.with_only_columns(model.extra_values)):
        extra_labels.update(values)
    extra_labels = sorted(extra_labels)
    columns = tuple(column for column in columns_for_equipment(equipment_types[0])
                    if column[0] not in ("report_year", "equipment_kind"))
    # equipment_code is first in COLUMNS, then match columns, then rest of COLUMNS
    equipment_code_col = next((c for c in columns if c[0] == "equipment_code"), None)
    rest_columns = tuple(c for c in columns if c[0] != "equipment_code")
    header_columns = []
    if equipment_code_col:
        attr, label, kind = equipment_code_col
        header_columns.append({"key": attr, "label": label, "kind": kind, "field": getattr(model, attr), "extra": False})
    match_status_labels = {
        "matched": "Совпало",
        "partial": "Частично",
        "ambiguous": "Неоднозначно",
        "unmatched": "Не найдено",
        "not_checked": "Не проверялось",
    }
    if matchable:
        header_columns += [
            {"key": "match_status", "label": "Статус сопоставления", "kind": "text", "field": model.match_status, "extra": False, "filter_labels": match_status_labels},
            {"key": "machine_id", "label": "ID агрегата", "kind": "number", "field": model.machine_id, "extra": False},
        ]
    header_columns += [
        {"key": attr, "label": label, "kind": kind, "field": getattr(model, attr), "extra": False}
        for attr, label, kind in rest_columns
    ] + [
        {"key": label, "label": label, "kind": "text", "field": model.extra_values[label].as_string(), "extra": True}
        for label in extra_labels
    ]
    # Списки значений охватывают всю выборку поиска, а не одну страницу таблицы.
    choices = [{} for column in header_columns]
    for values in db.session.execute(statement.with_only_columns(*(column["field"] for column in header_columns))):
        for column, options, value in zip(header_columns, choices, values):
            token = _filter_token(value)
            if value in (None, ""):
                label = "(Пустые)"
            elif column["key"] == "turbine_type":
                label = TURBINE_TYPES[value]
            elif column["key"] == "match_status":
                label = match_status_labels.get(value, str(value))
            elif column["kind"] == "number":
                label = format_decimal_for_display(value, 0)
            else:
                label = str(value)
            options[token] = (label, value)

    header_filter_args = {}
    for column, options in zip(header_columns, choices):
        param = ("extra_" if column["extra"] else "column_") + column["key"]
        selected = list(dict.fromkeys(args.getlist(param)))
        sorted_options = sorted(options.items(), key=lambda item: (
            item[1][1] is not None,
            item[1][0] if column["kind"] == "text" else item[1][1],
        ))
        column.update(param=param, selected=selected, options=[
            (token, label) for token, (label, value) in sorted_options
        ])
        if selected:
            header_filter_args[param] = selected
            values = [options[token][1] for token in selected if token in options]
            present = [value for value in values if value not in (None, "")]
            conditions = [column["field"].in_(present)] if present else []
            if any(value in (None, "") for value in values):
                conditions.append(column["field"].is_(None))
                if column["kind"] == "text":
                    conditions.append(column["field"] == "")
            statement = statement.where(or_(*conditions) if conditions else false())

    per_page_param = args.get("per_page", "25")
    if per_page_param not in ("10", "25", "50", "100", "all"):
        per_page_param = "25"
    per_page = None if per_page_param == "all" else int(per_page_param)
    page = max(args.get("page", 1, type=int), 1)
    page_size = per_page
    if per_page is None:
        page = 1
        page_size = max(db.session.scalar(statement.with_only_columns(func.count(model.id))), 1)
    statement = statement.order_by(model.station_name, model.station_number, model.turbine_type, model.equipment_code)
    pagination = db.paginate(statement, page=page, per_page=page_size, max_per_page=None, error_out=False)
    return {
        "page_key": page_key,
        "page_config": page_config,
        "pages": PAGES,
        "matchable": matchable,
        "equipment_type_choices": {key: EQUIPMENT_TYPES[key] for key in equipment_types},
        "pagination": pagination,
        "station_head_group_ids": station_head_group_ids(pagination.items, version_id),
        "current_page": pagination.page,
        "total_pages": max(pagination.pages, 1),
        "statement": statement,
        "columns": columns,
        "header_columns": header_columns,
        "header_filter_args": header_filter_args,
        "extra_labels": extra_labels,
        "years": years,
        "selected_year": selected_year,
        "rounding_digits": rounding_digits,
        "filters": filters,
        "has_active_filters": any(value for key, value in filters.items() if key != "year") or bool(header_filter_args),
        "turbine_types": TURBINE_TYPES,
        "per_page": per_page,
        "per_page_param": per_page_param,
        "version_id": version_id,
    }
