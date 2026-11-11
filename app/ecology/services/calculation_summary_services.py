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
    {"slug": "russia", "sheet_name": "Объемы выбросов по России"},
    {"slug": "specific", "sheet_name": "Удельные выбросы по России"},
    {"slug": "dynamics", "sheet_name": "Динамика изменения выбросов"},
    {"slug": "dynamics-specific", "sheet_name": "Динамика изменения удельных выбросов",
     "excel_sheet_name": "Динамика удельных выбросов"},
)

# Скрытые вкладки остаются доступны по ранее сохраненным ссылкам.
_LEGACY_TABS = (
    {"slug": "operating", "sheet_name": "Объемы выбросов для действующих ТЭС"},
    {"slug": "new", "sheet_name": "Объемы выбросов для новых ТЭС"},
    {"slug": "new-le100", "sheet_name": "Объемы выбросов для новых ТЭС до 100 МВт"},
    {"slug": "new-gt100", "sheet_name": "Объемы выбросов для новых ТЭС 100 МВт и более"},
)


def _sum_rows(context, sources):
    source_rows = [
        {row["key"]: row for row in source["rows"]} for source in sources
    ]
    source_columns = [
        {
            (col.get("territory_slug", col["slug"]), col.get("affiliation", "all")): col["slug"]
            for col in source["value_columns"]
        }
        for source in sources
    ]
    output_columns = {col["slug"]: col for col in context["value_columns"]}
    rows = []
    for row in context["rows"]:
        def amount(slug):
            output_column = output_columns[slug]
            key = (
                output_column.get("territory_slug", output_column["slug"]),
                output_column.get("affiliation", "all"),
            )
            amounts = []
            for by_key, columns in zip(source_rows, source_columns):
                source_slug = columns.get(key)
                if source_slug is None:
                    continue
                amounts.append(decimal_or_none(by_key[row["key"]]["col_values_raw"][source_slug]))
            return _sum_present(amounts)

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
            # В исходной таблице новых ТЭС ЗВ – в тоннах. Форма действующих
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
        context["value_columns"], bundles, inputs, context["specific_rounding_digits"],
    )


def _build_emission_dynamics(territory_slug, filters, specific=False):
    source_sheet = "specific" if specific else "russia"
    context = build_calculation_summary_context(
        territory_slug, source_sheet, include_affiliation_columns=False, **filters,
    )
    annual = {
        year: context if year == context["view_year"] else build_calculation_summary_context(
            territory_slug, source_sheet, include_affiliation_columns=False,
            **{**filters, "view_year": year},
        )
        for year in context["range_years"]
    }
    columns = [
        {"slug": f"{territory_slug}:{year}", "territory_slug": territory_slug,
         "year": year, "sheet_name": str(year)}
        for year in annual
    ]

    def range_rows(template_rows, tables, digits):
        rows_by_year = {
            year: {row["key"]: row for row in table["rows"]}
            for year, table in tables.items()
        }
        rows = []
        for row in template_rows:
            amounts = {
                column["slug"]: decimal_or_none(
                    rows_by_year[column["year"]][row["key"]]["col_values_raw"][column["slug"]]
                )
                for column in columns
            }
            values, raw = _cells_for_territories(columns, amounts.get, digits)
            rows.append(_row_dict(
                key=row["key"], label=row["label"], unit=row["unit"],
                kind=row["kind"], indent=row["indent"], italic=row["italic"],
                col_values=values, col_values_raw=raw, formula_tooltip=row["formula_tooltip"],
            ))
        return rows

    if specific:
        tables_by_year = {
            year: {table["key"]: table for table in source["specific_emission_tables"]}
            for year, source in annual.items()
        }
        title = "Динамика изменения удельных выбросов"
        content = {
            "rows": [],
            "specific_emission_tables": [
                {**table, "rows": range_rows(
                    table["rows"], {year: tables[table["key"]] for year, tables in tables_by_year.items()},
                    context["specific_rounding_digits"],
                )}
                for table in context["specific_emission_tables"]
            ],
        }
    else:
        breakdowns = {
            year: {table["key"]: table for table in source["summary_volume_tables"]}
            for year, source in annual.items()
        }
        title = "Динамика ожидаемых объемов выбросов вредных веществ и парниковых газов в атмосферу, тыс. т"
        content = {
            "rows": range_rows(context["rows"], annual, context["rounding_digits"]),
            "summary_volume_tables": [
                {**table, "rows": range_rows(
                    table["rows"], {year: tables[table["key"]] for year, tables in breakdowns.items()},
                    context["rounding_digits"],
                )}
                for table in context["summary_volume_tables"]
            ],
        }
    return {
        **context,
        "page_title": title, "page_title_html": title,
        "dynamics_territories": context["territory_columns"],
        "territory_columns": columns, "value_columns": columns,
        "year_columns_mode": True, "years": list(annual),
        "main_table_title": None,
        **content,
    }


def build_calculation_summary_context(territory_slug, sheet_slug, include_affiliation_columns=False, **filters):
    tab = next((tab for tab in (*CALCULATION_SUMMARY_TABS, *_LEGACY_TABS) if tab["slug"] == sheet_slug), None)
    if tab is None:
        return None
    source_sheet = "toplivo" if sheet_slug == "toplivo" else "obemy"
    new_filters = {
        key: value for key, value in filters.items()
        if key not in {"coefficient_rounding_digits", "specific_rounding_digits"}
    }

    def new_context(capacity):
        return build_new_tes_table_context(
            territory_slug, source_sheet, capacity_class=capacity, **new_filters,
        )

    if sheet_slug in {"dynamics", "dynamics-specific"}:
        context = _build_emission_dynamics(territory_slug, filters, specific=sheet_slug == "dynamics-specific")
    elif sheet_slug in {"new-le100", "new-gt100"}:
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
            context = {**new_sources[0], "rows": _sum_rows(new_sources[0], new_sources)}
            if sheet_slug in {"russia", "specific"}:
                operating = build_operating_tes_table_context(
                    territory_slug, source_sheet,
                    show_affiliation_columns=include_affiliation_columns,
                    **filters,
                )
                context = {**operating, "rows": _sum_rows(operating, [operating, context])}
                context["specific_emission_tables"] = []
                if sheet_slug == "russia":
                    context["main_table_title"] = "Всего"
                    context["summary_volume_tables"] = [
                        {"key": "operating", "title": "Действующие ТЭС", "rows": operating["rows"]},
                        {"key": "new-gt100", "title": "Новые ТЭС – 100 МВт и более",
                         "rows": _sum_rows(operating, [new_sources[1]])},
                        {"key": "new-le100", "title": "Новые ТЭС – менее 100 МВт",
                         "rows": _sum_rows(operating, [new_sources[0]])},
                    ]
                else:
                    fuel_context = build_calculation_summary_context(territory_slug, "toplivo", **filters)
                    context["specific_emission_tables"] = _build_russia_specific_emission_tables(context, fuel_context)
                    context["specific_emissions_only"] = True
                    context["page_title"] = "Удельные выбросы ЗВ и ПГ"
                    context["page_title_html"] = context["page_title"]
            else:
                context["page_title"] = "Ожидаемые объемы выбросов вредных веществ и парниковых газов в атмосферу, тыс. т"
                context["page_title_html"] = context["page_title"]
                context["specific_emission_tables"] = []
    if sheet_slug == "russia":
        context["show_affiliation_columns"] = include_affiliation_columns
        context["affiliation_columns"] = (
            context.get("affiliation_columns", []) if include_affiliation_columns else []
        )
    return {
        **context,
        "sheet": {**context["sheet"], **tab},
        "calc_sheets": CALCULATION_SUMMARY_TABS,
        "new_tes_capacity_tabs": (),
        "capacity_class": None,
        "table_endpoint": "ecology_bp.calculation_summary",
        "can_edit": False,
        "document_title": "Сводные данные расчетов",
        "territory_filter_storage_key": None if context.get("dynamics_territories") else "ecology.calculation_summary.territories",
    }
