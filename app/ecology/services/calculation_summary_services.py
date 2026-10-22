"""Сводные расчеты на основе принятых топливных данных трех категорий ТЭС."""
from decimal import Decimal

from app.ecology.services.ecology_decimal_helpers import decimal_or_none
from app.ecology.services.new_tes_page_services import build_new_tes_table_context
from app.ecology.services.operating_tes_constants import TOP_INPUT_FIELD, VOLUME_ROWS
from app.ecology.services.operating_tes_fuel_input_services import apply_input_override_to_bucket
from app.ecology.services.operating_tes_page_services import (
    _build_specific_emission_tables,
    _cells_for_territories,
    _row_dict,
    _sum_present,
    build_operating_tes_table_context,
)

CALCULATION_SUMMARY_TABS = (
    {"slug": "toplivo", "sheet_name": "Данные по модулю Топливо"},
    {"slug": "operating", "sheet_name": "Объемы выбросов для действующих ТЭС"},
    {"slug": "new", "sheet_name": "Объемы выбросов для новых ТЭС", "parent_slug": "new", "subtab_name": "Всего"},
    {"slug": "new-le100", "sheet_name": "Объемы выбросов для новых ТЭС до 100 МВт", "parent_slug": "new", "subtab_name": "до 100 МВт"},
    {"slug": "new-gt100", "sheet_name": "Объемы выбросов для новых ТЭС 100 МВт и более", "parent_slug": "new", "subtab_name": "100 МВт и более"},
    {"slug": "russia", "sheet_name": "Объемы выбросов по России"},
)


def _sum_rows(context, sources):
    source_rows = [
        {row["key"]: row for row in source["rows"]} for source in sources
    ]
    source_columns = [
        {col.get("territory_slug", col["slug"]): col["slug"] for col in source["value_columns"]}
        for source in sources
    ]
    territories = {col["slug"]: col.get("territory_slug", col["slug"]) for col in context["value_columns"]}
    rows = []
    for row in context["rows"]:
        def amount(slug):
            territory = territories[slug]
            return _sum_present([
                decimal_or_none(by_key[row["key"]]["col_values_raw"][columns[territory]])
                for by_key, columns in zip(source_rows, source_columns)
            ])

        values, raw = _cells_for_territories(context["value_columns"], amount, context["rounding_digits"])
        rows.append(_row_dict(
            key=row["key"], label=row["label"], unit=row["unit"],
            kind=row["kind"], indent=row["indent"], italic=row["italic"],
            col_values=values, col_values_raw=raw,
        ))
    return rows


def _transpose_new_volumes(context):
    total = context["rows"][0]
    columns = context["territory_columns"]
    rows = []
    for spec in VOLUME_ROWS:
        metric = spec["key"]

        def amount(slug):
            value = decimal_or_none(total["col_values_raw"][f"{slug}:{metric}"])
            # В исходной таблице новых ТЭС ЗВ — в тоннах. Форма действующих
            # ТЭС использует тыс. т, кроме отдельной строки CO (тонны).
            if value is not None and metric not in {"co", "co2"}:
                value /= Decimal("1000")
            return value

        values, raw = _cells_for_territories(columns, amount, context["rounding_digits"])
        rows.append(_row_dict(
            key=metric, label=spec["label"], unit="т" if metric == "co" else "тыс. т",
            kind=spec["kind"], indent=spec["indent"],
            col_values=values, col_values_raw=raw,
        ))
    return {
        **context, "rows": rows, "value_columns": columns,
        "new_tes_volume_columns": (),
    }


def _build_russia_specific_emission_tables(context, fuel_context):
    inputs = {}
    bundles = {}
    for column in context["value_columns"]:
        slug = column["slug"]
        bucket = {}
        for row in fuel_context["rows"]:
            amount = decimal_or_none(row["col_values_raw"][slug])
            if row["key"] in TOP_INPUT_FIELD:
                apply_input_override_to_bucket(bucket, row["key"], amount)
            elif amount is not None:
                bucket[row["key"]] = amount
        inputs.setdefault(column["year"], {})[column["territory_slug"]] = bucket
        bundles[slug] = {"volumes": {
            row["key"]: decimal_or_none(row["col_values_raw"][slug])
            for row in context["rows"]
        }}
    return _build_specific_emission_tables(
        context["value_columns"], bundles, inputs, context["rounding_digits"],
    )


def build_calculation_summary_context(territory_slug, sheet_slug, **filters):
    tab = next((tab for tab in CALCULATION_SUMMARY_TABS if tab["slug"] == sheet_slug), None)
    if tab is None:
        return None
    source_sheet = "toplivo" if sheet_slug == "toplivo" else "obemy"
    new_filters = {key: value for key, value in filters.items() if key != "coefficient_rounding_digits"}

    def new_context(capacity):
        return build_new_tes_table_context(
            territory_slug, source_sheet, capacity_class=capacity, **new_filters,
        )

    if sheet_slug in {"new-le100", "new-gt100"}:
        context = new_context(sheet_slug.removeprefix("new-"))
        if context is None:
            return None
    elif sheet_slug == "operating":
        context = build_operating_tes_table_context(territory_slug, source_sheet, **filters)
    else:
        le100, gt100 = new_context("le100"), new_context("gt100")
        if le100 is None or gt100 is None:
            return None
        if sheet_slug == "toplivo":
            context = build_operating_tes_table_context(territory_slug, source_sheet, **filters)
            context["rows"] = _sum_rows(context, [context, le100, gt100])
            context["page_title"] = "Топливные показатели действующих и новых ТЭС (модуль Топливо)"
            context["page_title_html"] = context["page_title"]
        else:
            new_sources = [_transpose_new_volumes(source) for source in (le100, gt100)]
            context = new_sources[0]
            context["rows"] = _sum_rows(context, new_sources)
            if sheet_slug == "russia":
                operating = build_operating_tes_table_context(territory_slug, source_sheet, **filters)
                operating["rows"] = _sum_rows(operating, [operating, context])
                context = operating
                fuel_context = build_calculation_summary_context(territory_slug, "toplivo", **filters)
                context["specific_emission_tables"] = _build_russia_specific_emission_tables(context, fuel_context)
            else:
                context["page_title"] = "Ожидаемые объемы выбросов вредных веществ и парниковых газов в атмосферу, тыс. т"
                context["page_title_html"] = context["page_title"]
                context["specific_emission_tables"] = []
    return {
        **context,
        "sheet": {**context["sheet"], **tab},
        "calc_sheets": CALCULATION_SUMMARY_TABS,
        "new_tes_capacity_tabs": (),
        "capacity_class": None,
        "table_endpoint": "ecology_bp.calculation_summary",
        "can_edit": False,
        "document_title": "Сводные данные расчетов",
        "territory_filter_storage_key": "ecology.calculation_summary.territories",
    }
