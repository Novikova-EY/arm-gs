# -*- coding: utf-8 -*-
"""Страница расчёта по действующим ТЭС: вкладки территорий и листов макета."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.common.services.database_version_filter import get_current_db_version_id
from app.common.services.get_services.years.years_get_services import (
    get_filter_end_year,
    get_filter_start_year,
    get_sipr_end_year,
    get_sipr_start_year,
    get_year_feature_dict,
    get_year_numbers_sorted_for_current_db_version,
)
from app.common.services.help_services import format_decimal_trim_for_display
from app.ecology.services.ecology_decimal_helpers import decimal_or_none as _d
from app.ecology.services.ecology_logging_services import (
    affiliation_label,
    characteristic_label,
    coefficient_label,
    context_lines,
    fuel_label,
    log_cell_change,
    territory_label,
)
from app.ecology.models.operating_tes_coefficient_model import OperatingTesCoefficient
from app.ecology.models.operating_tes_fuel_characteristic_model import (
    OperatingTesFuelCharacteristic,
)
from app.ecology.models.operating_tes_input_model import OperatingTesInputValue
from app.ecology.services.operating_tes_calc_services import (
    apply_capture,
    ash_motkh,
    to_natural_by_heat,
    co_motkh,
    nox_motkh,
    pg_motkh,
    pg_tj_energy_and_mass,
    so2_motkh,
    specific_per_energy,
    specific_per_fuel,
    to_natural,
)
from app.ecology.services.operating_tes_constants import (
    CALC_SHEETS,
    CHAR_COLUMNS,
    CHAR_HEADER_GROUPS,
    COEFF_KINDS,
    COEFFICIENT_TERRITORIES,
    COEFFICIENT_AFFILIATIONS,
    get_coefficient_territory,
    DEFAULT_CHAR_NOTES,
    DEFAULT_CHAR_SOURCES,
    DEFAULT_CHARACTERISTICS,
    DEFAULT_TERRITORY_SLUG,
    EMISSION_FORMULAS,
    EMISSION_SHEET_VIEW,
    FUEL_PARAM_FIELDS,
    FUEL_ROWS,
    KIND_TOTAL,
    KIND_VALUE,
    PARENT_CHILDREN,
    ROUNDING_CHOICES,
    ROUNDING_DIGITS,
    TERRITORIES,
    TOP_INPUT_FIELD,
    TOP_INPUT_ROWS,
    VOLUME_ROWS,
    default_coefficient,
    get_calc_sheet,
    get_territory,
)
from app.ecology.services.operating_tes_fuel_input_services import (
    apply_input_override_to_bucket,
    bucket_field_amount,
    bucket_top_input_amount,
    empty_fuel_bucket,
    fuel_amount_for_key,
    get_fuel_module_consumption_row_specs,
)
from app.ecology.services.formula_text.operating_tes_formula_text_services import (
    format_emission_formula,
    format_natural_fuel_formula,
    formula_text_for_sheet,
    ot_formula_text,
)
from app.ecology.services.operating_tes_territory_services import get_territory_columns
from app.extensions import db

CHAR_EDIT_FIELDS = {key for key, _label in CHAR_COLUMNS}
_CHAR_HEADER_TITLES = {
    key: group["title"] for group in CHAR_HEADER_GROUPS for key in group["keys"]
}

_BUNDLE_METRICS = (
    "b",
    "bn",
    "heat_bn",
    "ash_motkh",
    "ash",
    "so2_motkh",
    "so2",
    "nox_raw",
    "co_motkh",
    "co",
    "pg_motkh",
    "pg",
    "energy_tj",
    "pg_tj_motkh",
    "pg_tj",
)


def _parse_optional_year(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def resolve_view_year(value: Any, years: list[int]) -> int | None:
    """Год из кнопок периода: только если он входит в выбранный диапазон."""
    if value in (None, ""):
        return None
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    return year if year in years else None


def resolve_selected_year(value: Any, years: list[int]) -> int | None:
    """Год для таблицы: выбранный, иначе первый год периода."""
    selected = resolve_view_year(value, years)
    if selected is not None:
        return selected
    return years[0] if years else None


def resolve_rounding_digits(value: Any = None) -> int:
    if value in (None, ""):
        return ROUNDING_DIGITS
    try:
        digits = int(value)
    except (TypeError, ValueError):
        return ROUNDING_DIGITS
    if digits in ROUNDING_CHOICES:
        return digits
    return ROUNDING_DIGITS


def get_filter_year_list() -> list[int]:
    years = get_year_numbers_sorted_for_current_db_version()
    if years:
        return years
    start = int(get_filter_start_year() or get_sipr_start_year())
    end = int(get_filter_end_year() or get_sipr_end_year())
    if start > end:
        start, end = end, start
    return list(range(start, end + 1))


def get_year_columns(start_year: Any = None, end_year: Any = None) -> list[int]:
    default_start = int(get_sipr_start_year())
    default_end = int(get_sipr_end_year())
    if default_start > default_end:
        default_start, default_end = default_end, default_start
    start = _parse_optional_year(start_year, default_start)
    end = _parse_optional_year(end_year, default_end)
    if start > end:
        start, end = end, start
    bounds = get_filter_year_list()
    if bounds:
        lo, hi = bounds[0], bounds[-1]
        start = max(lo, min(start, hi))
        end = max(lo, min(end, hi))
        if start > end:
            start, end = end, start
    return list(range(start, end + 1))


def format_cell(value: Any, digits: int | None = None) -> str:
    return format_decimal_trim_for_display(value, digits=digits)


def group_territories(territories=None) -> list[dict[str, Any]]:
    """Одна строка вкладок в порядке территорий расчёта."""
    return [{"group": "territory", "sheets": get_territory_columns() if territories is None else territories}]


def _sum_present(values: list[Decimal | None]) -> Decimal | None:
    present = [item for item in values if item is not None]
    if not present:
        return None
    return sum(present, Decimal("0"))


_FUEL_BY_KEY = {spec["key"]: spec for spec in FUEL_ROWS}
_FUEL_ROOTS = [spec for spec in FUEL_ROWS if not spec.get("parent_key")]


def _characteristic_row_specs() -> list[dict[str, Any]]:
    """Иерархия модуля топлива с прежними ключами сохранённых характеристик."""
    keys_by_field = {field: key for key, field in FUEL_PARAM_FIELDS.items()}
    return [
        {**spec, "key": keys_by_field.get(spec["key"], spec["key"])}
        for spec in get_fuel_module_consumption_row_specs()
        if spec["key"] != "b"
    ]


def _nz(value: Any) -> Decimal | None:
    amount = _d(value)
    if amount is None or amount == 0:
        return None
    return amount


def sum_metric_tree(by_key: dict[str, dict[str, Decimal | None]], metric: str) -> Decimal | None:
    """Сумма по дереву: дети, если есть данные, иначе значение узла (без двойного счёта)."""

    def node_value(spec: dict[str, Any]) -> Decimal | None:
        children = tuple(spec.get("children") or ())
        if children:
            child_sum = _sum_present(
                [
                    node_value(_FUEL_BY_KEY[child])
                    for child in children
                    if child in _FUEL_BY_KEY
                ]
            )
            if child_sum is not None:
                return child_sum
        return (by_key.get(spec["key"]) or {}).get(metric)

    return _sum_present([node_value(spec) for spec in _FUEL_ROOTS])


def _fallback_header_chars(
    fuel_key: str,
    year: int,
    children: tuple[str, ...],
    char_overrides: dict[tuple[str, str, int], dict[str, Any]],
    territory_slug: str,
) -> dict[str, Any]:
    chars = resolve_chars(fuel_key, year, char_overrides, territory_slug)
    if DEFAULT_CHARACTERISTICS.get(fuel_key):
        return chars
    for child in children:
        if DEFAULT_CHARACTERISTICS.get(child):
            return resolve_chars(child, year, char_overrides, territory_slug)
    return chars


def load_characteristic_overrides(years: list[int]) -> dict[tuple[str, str, int], dict[str, Any]]:
    version_id = get_current_db_version_id()
    query = OperatingTesFuelCharacteristic.query.filter(
        OperatingTesFuelCharacteristic.year_number.in_(years),
        OperatingTesFuelCharacteristic.territory_slug == DEFAULT_TERRITORY_SLUG,
    )
    if version_id is not None:
        query = query.filter(OperatingTesFuelCharacteristic.database_version_id == version_id)
    out: dict[tuple[str, str, int], dict[str, Any]] = {}
    for row in query.all():
        payload = {
            key: getattr(row, key)
            for key, _label in CHAR_COLUMNS
        }
        payload["tj_per_kt"] = row.tj_per_kt
        payload["t_co2_per_tj"] = row.t_co2_per_tj
        payload["note"] = row.note
        payload["source_key"] = row.source_key
        out[(row.territory_slug, row.fuel_key, int(row.year_number))] = payload
    return out


def load_coefficient_overrides(
    years: list[int], affiliation: str = "all"
) -> dict[tuple[str, int, str], Decimal]:
    version_id = get_current_db_version_id()
    query = OperatingTesCoefficient.query.filter(
        OperatingTesCoefficient.year_number.in_(years)
    )
    if version_id is not None:
        query = query.filter(OperatingTesCoefficient.database_version_id == version_id)
    out: dict[tuple[str, int, str], Decimal] = {}
    for row in query.all():
        amount = _d(row.value)
        if amount is None:
            continue
        slug = row.territory_slug
        if affiliation != "all" and slug == affiliation and row.affiliation == "all":
            slug = "vsego"
        elif row.affiliation != affiliation:
            continue
        out[(slug, int(row.year_number), row.kind)] = amount
    return out


def load_input_overrides(years: list[int]) -> dict[tuple[str, int, str], Decimal]:
    version_id = get_current_db_version_id()
    query = OperatingTesInputValue.query.filter(
        OperatingTesInputValue.year_number.in_(years)
    )
    if version_id is not None:
        query = query.filter(OperatingTesInputValue.database_version_id == version_id)
    out: dict[tuple[str, int, str], Decimal] = {}
    for row in query.all():
        amount = _d(row.value)
        if amount is None:
            continue
        out[(row.territory_slug, int(row.year_number), row.row_key)] = amount
    return out


def ensure_default_persisted_rows(years: list[int]) -> None:
    """Записывает в БД справочные Хар.топл. и Коэфф., чтобы значения сохранялись."""
    if not years:
        return
    version_id = get_current_db_version_id()
    from sqlalchemy.exc import IntegrityError

    char_q = OperatingTesFuelCharacteristic.query.filter(
        OperatingTesFuelCharacteristic.year_number.in_(years),
        OperatingTesFuelCharacteristic.territory_slug == DEFAULT_TERRITORY_SLUG,
    )
    coeff_q = OperatingTesCoefficient.query.filter(
        OperatingTesCoefficient.year_number.in_(years)
    )
    if version_id is not None:
        char_q = char_q.filter(OperatingTesFuelCharacteristic.database_version_id == version_id)
        coeff_q = coeff_q.filter(OperatingTesCoefficient.database_version_id == version_id)
    existing_chars = {
        (row.territory_slug, row.fuel_key, int(row.year_number)) for row in char_q.all()
    }
    existing_coeffs = {
        (row.territory_slug, int(row.year_number), row.kind)
        for row in coeff_q.all() if row.affiliation == "all"
    }
    added = False
    for year in years:
        for fuel_key, defaults in DEFAULT_CHARACTERISTICS.items():
            if (DEFAULT_TERRITORY_SLUG, fuel_key, year) in existing_chars:
                continue
            db.session.add(
                OperatingTesFuelCharacteristic(
                    territory_slug=DEFAULT_TERRITORY_SLUG,
                    fuel_key=fuel_key,
                    year_number=int(year),
                    database_version_id=version_id,
                    note=DEFAULT_CHAR_NOTES.get(fuel_key),
                    source_key=DEFAULT_CHAR_SOURCES.get(fuel_key),
                    **{key: defaults.get(key) for key, _label in CHAR_COLUMNS},
                )
            )
            added = True
        for territory in TERRITORIES:
            for kind in COEFF_KINDS:
                triple = (territory["slug"], int(year), kind["key"])
                if triple in existing_coeffs:
                    continue
                db.session.add(
                    OperatingTesCoefficient(
                        territory_slug=territory["slug"],
                        year_number=int(year),
                        kind=kind["key"],
                        value=default_coefficient(year, territory["slug"], kind["key"]),
                        database_version_id=version_id,
                    )
                )
                added = True
    if not added:
        return
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()


def resolve_chars(
    fuel_key: str,
    year: int,
    overrides: dict[tuple[str, str, int], dict[str, Any]],
    territory_slug: str = DEFAULT_TERRITORY_SLUG,
) -> dict[str, Any]:
    base = dict(DEFAULT_CHARACTERISTICS.get(fuel_key) or {})
    if fuel_key in DEFAULT_CHAR_NOTES:
        base["note"] = DEFAULT_CHAR_NOTES[fuel_key]
    if fuel_key in DEFAULT_CHAR_SOURCES:
        base["source_key"] = DEFAULT_CHAR_SOURCES[fuel_key]
    # Характеристики общие для всех территорий и принадлежностей.
    extra = overrides.get((DEFAULT_TERRITORY_SLUG, fuel_key, year)) or {}
    for key, value in extra.items():
        if value is not None:
            base[key] = value
    return base


def coefficient_territory_slug(territory_slug: str) -> str:
    return {
        "norilsk": "tites-sibir",
        "isolated-dv": "tites-vostok",
        "nikolaevsky": "decentralized-zone",
    }.get(territory_slug, territory_slug)


def resolve_coeff(
    territory_slug: str,
    year: int,
    kind: str,
    overrides: dict[tuple[str, int, str], Decimal],
) -> Decimal:
    if kind in {"ash_eta", "sulfur_eta", "co_k", "nox_n", "pg_k"}:
        # У специальных территорий на вкладке коэффициентов другие ключи.
        territory_slug = coefficient_territory_slug(territory_slug)
    if (territory_slug, year, kind) in overrides:
        return overrides[(territory_slug, year, kind)]
    return Decimal(str(default_coefficient(year, territory_slug, kind)))


def _fuel_b_for_row(
    fuel_key: str,
    is_header: bool,
    children: tuple[str, ...],
    bucket: dict[str, Decimal] | None,
    leaf_b: dict[str, Decimal | None],
) -> Decimal | None:
    if is_header and children:
        child_vals = [leaf_b.get(child) for child in children]
        child_sum = _sum_present(child_vals)
        if child_sum is not None:
            return child_sum
    field_val = fuel_amount_for_key(bucket, fuel_key)
    if field_val is not None:
        return field_val
    if is_header and children:
        return _sum_present([leaf_b.get(child) for child in children])
    return None


def _compute_leaf_emissions(
    fuel_key: str,
    b_tce: Decimal | None,
    chars: dict[str, Any],
    coeffs: dict[str, Decimal],
) -> dict[str, Decimal | None]:
    bn = to_natural(b_tce, chars)
    heat_bn = to_natural_by_heat(b_tce, chars)
    ash_m = ash_motkh(heat_bn, chars)
    so2_m = so2_motkh(heat_bn, chars)
    nox_raw = nox_motkh(b_tce, chars)
    co_m = co_motkh(heat_bn, chars)
    pg_m = pg_motkh(b_tce, chars)
    energy, pg_tj_m = pg_tj_energy_and_mass(b_tce, chars)
    return {
        "b": b_tce,
        "bn": bn,
        "heat_bn": heat_bn,
        "ash_motkh": ash_m,
        "ash": apply_capture(ash_m, coeffs.get("ash_eta")),
        "so2_motkh": so2_m,
        "so2": apply_capture(so2_m, coeffs.get("sulfur_eta")),
        "nox_raw": nox_raw,
        "co_motkh": co_m,
        "co": apply_capture(co_m, coeffs.get("co_k")),
        "pg_motkh": pg_m,
        "pg": apply_capture(pg_m, coeffs.get("pg_k")),
        "energy_tj": energy,
        "pg_tj_motkh": pg_tj_m,
        "pg_tj": apply_capture(pg_tj_m, coeffs.get("pg_k")),
    }


def _fill_headers(by_key: dict[str, dict[str, Decimal | None]]) -> None:
    for parent in sorted(
        PARENT_CHILDREN, key=lambda key: int(_FUEL_BY_KEY[key].get("indent") or 0), reverse=True,
    ):
        children = PARENT_CHILDREN[parent]
        parent_row = by_key.get(parent)
        if not parent_row:
            continue
        for metric in _BUNDLE_METRICS:
            if parent_row.get(metric) is not None:
                continue
            parent_row[metric] = _sum_present(
                [(by_key.get(child) or {}).get(metric) for child in children]
            )


def compute_year_bundle(
    territory_slug: str,
    year: int,
    bucket: dict[str, Decimal] | None,
    char_overrides: dict[tuple[str, str, int], dict[str, Any]],
    coeff_overrides: dict[tuple[str, int, str], Decimal],
) -> dict[str, Any]:
    coeffs = {
        kind["key"]: resolve_coeff(territory_slug, year, kind["key"], coeff_overrides)
        for kind in COEFF_KINDS
    }
    leaf_b: dict[str, Decimal | None] = {}
    by_key: dict[str, dict[str, Decimal | None]] = {}
    # leaves first
    for spec in FUEL_ROWS:
        if spec.get("is_header"):
            continue
        key = spec["key"]
        b_tce = fuel_amount_for_key(bucket, key)
        leaf_b[key] = b_tce
        chars = resolve_chars(key, year, char_overrides, territory_slug)
        by_key[key] = _compute_leaf_emissions(key, b_tce, chars, coeffs)
    header_specs = sorted(
        [spec for spec in FUEL_ROWS if spec.get("is_header")],
        key=lambda item: int(item.get("indent") or 0),
        reverse=True,
    )
    for spec in header_specs:
        key = spec["key"]
        children = tuple(spec.get("children") or PARENT_CHILDREN.get(key) or ())
        b_tce = _fuel_b_for_row(key, True, children, bucket, leaf_b)
        leaf_b[key] = b_tce
        child_sum = _sum_present([leaf_b.get(child) for child in children])
        if child_sum is not None:
            computed = {metric: None for metric in _BUNDLE_METRICS}
            computed["b"] = b_tce
        else:
            chars = _fallback_header_chars(key, year, children, char_overrides, territory_slug)
            computed = _compute_leaf_emissions(key, b_tce, chars, coeffs)
        by_key[key] = computed
    _fill_headers(by_key)
    nox_n = coeffs["nox_n"]
    nox_total_raw = sum_metric_tree(by_key, "nox_raw")
    nox_total = apply_capture(nox_total_raw, nox_n)
    for spec in FUEL_ROWS:
        row = by_key.setdefault(spec["key"], {})
        raw = row.get("nox_raw")
        row["nox"] = apply_capture(raw, nox_n) if raw is not None else None
    volumes = {
        "ash": sum_metric_tree(by_key, "ash"),
        "so2": sum_metric_tree(by_key, "so2"),
        "nox": nox_total,
        "co": sum_metric_tree(by_key, "co"),
        "co2": sum_metric_tree(by_key, "co2") or sum_metric_tree(by_key, "pg"),
    }
    volumes["pollutants_total"] = _sum_present(
        [volumes["ash"], volumes["so2"], volumes["nox"], volumes["co"]]
    )
    return {
        "by_key": by_key,
        "ash_motkh_total": sum_metric_tree(by_key, "ash_motkh"),
        "so2_motkh_total": sum_metric_tree(by_key, "so2_motkh"),
        "co_motkh_total": sum_metric_tree(by_key, "co_motkh"),
        "nox_motkh_total": nox_total_raw,
        "pg_motkh_total": sum_metric_tree(by_key, "pg_motkh"),
        "pg_tj_motkh_total": sum_metric_tree(by_key, "pg_tj_motkh"),
        "volumes": volumes,
        "coeffs": coeffs,
        "chars": {
            spec["key"]: resolve_chars(spec["key"], year, char_overrides, territory_slug) for spec in FUEL_ROWS
        },
    }


def _row_dict(
    *,
    key: str,
    label: str,
    unit: str,
    kind: str,
    indent: int,
    col_values: dict[str, str],
    col_values_raw: dict[str, str],
    formula_tooltip: str = "",
    italic: bool = False,
    editable_values: bool = False,
    editable_field: str | None = None,
    pair_values: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    empty = not any(col_values_raw.get(col) not in (None, "", "0") for col in col_values_raw)
    return {
        "key": key,
        "label": label,
        "unit": unit,
        "kind": kind,
        "indent": indent,
        "css_class": "table-info" if kind == KIND_TOTAL else "",
        "col_values": col_values,
        "col_values_raw": col_values_raw,
        "pair_values": pair_values or {},
        "formula_tooltip": formula_tooltip,
        "formula_tooltip_html": format_natural_fuel_formula(formula_tooltip) if formula_tooltip else None,
        "italic": italic,
        "editable_values": editable_values,
        "editable_field": editable_field,
        "hide_when_empty": True,
        "is_empty": empty,
    }


def _cells_for_territories(
    territory_columns: list[dict[str, Any]],
    getter,
    digits: int,
) -> tuple[dict[str, str], dict[str, str]]:
    col_values: dict[str, str] = {}
    col_raw: dict[str, str] = {}
    for terr in territory_columns:
        slug = terr["slug"]
        raw = getter(slug)
        col_raw[slug] = "" if raw is None else str(raw)
        col_values[slug] = format_cell(raw, digits=digits)
    return col_values, col_raw


def _pair_cells_for_territories(
    territory_columns: list[dict[str, Any]],
    getter_left,
    getter_right,
    digits: int,
) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    pair_values: dict[str, dict[str, str]] = {}
    col_raw: dict[str, str] = {}
    for terr in territory_columns:
        slug = terr["slug"]
        left = getter_left(slug)
        right = getter_right(slug)
        pair_values[slug] = {
            "left": format_cell(left, digits=digits),
            "right": format_cell(right, digits=digits),
        }
        col_raw[f"{slug}:l"] = "" if left is None else str(left)
        col_raw[f"{slug}:r"] = "" if right is None else str(right)
    return pair_values, col_raw


def _metric_from_bundle(bundles_by_terr: dict[str, Any], slug: str, row_key: str, metric: str):
    return (
        ((bundles_by_terr.get(slug) or {}).get("by_key") or {}).get(row_key) or {}
    ).get(metric)


def _build_specific_emission_tables(
    value_columns: list[dict[str, Any]],
    bundles: dict[str, Any],
    inputs: dict[int, Any],
    digits: int,
) -> list[dict[str, Any]]:
    energy_title = "Удельные выбросы ЗВ и ПГ на единицу приведенной энергии, г/кВт.ч"
    electricity_title = "Удельные выбросы ЗВ и ПГ на единицу электрической энергии, г/кВт.ч"
    fuel_formula = "М × 1000 / В"
    solid_formula = "М × 100 / (Нефтетопливо + Торф + тв.топливо + Уголь всего)"
    brought_energy_formula = "М / (Выработка электроэнергии + Отпуск тепла / 859,8)"
    electricity_formula = "М / Выработка электроэнергии"
    tables = [
        {"key": "energy", "title": energy_title, "formula": brought_energy_formula},
        {"key": "energy_fuel", "title": electricity_title, "formula": electricity_formula},
        {"key": "fuel", "title": "Удельные выбросы ЗВ и ПГ на единицу топлива, кг/т у.т.",
         "formula": f"{fuel_formula}; для золы и SO2: {solid_formula}"},
    ]
    values = {table["key"]: {} for table in tables}
    for column in value_columns:
        slug = column["slug"]
        bucket = inputs.get(column["year"], {}).get(column["territory_slug"])
        fuel = bucket_field_amount(bucket, "b")
        electricity = bucket_top_input_amount(bucket, "ee_generation")
        heat = bucket_top_input_amount(bucket, "heat_output")
        brought_energy = _sum_present([
            electricity,
            heat / Decimal("859.8") if heat is not None else None,
        ])
        solid_fuel = _sum_present([
            fuel_amount_for_key(bucket, key)
            for key in ("oil_fuel", "peat", "other_solid", "coal")
        ])
        volumes = bundles[slug]["volumes"]
        for table in tables:
            values[table["key"]][slug] = {}
        for spec in VOLUME_ROWS:
            key = spec["key"]
            mass = volumes[key]
            if key == "pollutants_total":
                # CO is reported in tonnes while the other pollutants use thousand tonnes.
                mass_for_energy = _sum_present([
                    volumes.get("ash"),
                    volumes.get("so2"),
                    volumes.get("nox"),
                    volumes.get("co") / Decimal("1000")
                    if volumes.get("co") is not None else None,
                ])
            elif key == "co":
                mass_for_energy = mass / Decimal("1000") if mass is not None else None
            else:
                mass_for_energy = mass
            values["energy"][slug][key] = specific_per_energy(mass_for_energy, brought_energy)
            values["energy_fuel"][slug][key] = specific_per_energy(mass_for_energy, electricity)
            if key in {"ash", "so2"}:
                per_fuel = (
                    mass * Decimal("100") / solid_fuel
                    if mass is not None and solid_fuel not in (None, 0) else None
                )
            else:
                per_fuel = specific_per_fuel(mass, fuel)
            values["fuel"][slug][key] = per_fuel
    for table in tables:
        table["rows"] = []
        for spec in VOLUME_ROWS:
            key = spec["key"]
            col_values, col_raw = _cells_for_territories(
                value_columns,
                lambda slug, key=key: values[table["key"]][slug][key],
                digits,
            )
            formula = table["formula"]
            if key == "co" and table["key"] in {"energy", "energy_fuel"}:
                formula = formula.replace("М /", "М / 1000 /", 1)
            elif key == "pollutants_total" and table["key"] in {"energy", "energy_fuel"}:
                formula = f"Σ удельных выбросов ЗВ ({formula})"
            elif table["key"] == "fuel":
                formula = solid_formula if key in {"ash", "so2"} else fuel_formula
            table["rows"].append(_row_dict(
                key=key, label=spec["label"], unit="", kind=spec["kind"],
                indent=spec["indent"], col_values=col_values, col_values_raw=col_raw,
                formula_tooltip=(
                    f"{formula}. М – выбросы из таблицы объемов, тыс. т (CO – т); "
                    "выработка электроэнергии, млрд.кВт.ч, и отпуск тепла, тыс.Гкал, – данные модуля Топливо."
                    if table["key"] in {"energy", "energy_fuel"}
                    else f"{formula}. М – значение из таблицы объемов; В – расход топлива, всего, тыс.т у.т."
                ),
            ))
    return tables


def build_operating_tes_table_context(
    territory_slug: str,
    sheet_slug: str,
    start_year: Any = None,
    end_year: Any = None,
    rounding_digits: Any = None,
    view_year: Any = None,
    fuel_source: bool = False,
    affiliation: str = "all",
    coefficient_rounding_digits: Any = 0,
    fuel_scope: str = "operating",
) -> dict[str, Any] | None:
    sheet = get_calc_sheet(sheet_slug)
    is_coefficient = sheet is not None and sheet["layout"] == "coeff"
    if is_coefficient:
        if territory_slug in {"minen", "prompred"}:
            affiliation, territory_slug = territory_slug, "vsego"
        territory = get_coefficient_territory(territory_slug)
        if affiliation not in {"all", "minen", "prompred"}:
            return None
    else:
        territory = get_territory(territory_slug) or get_territory(DEFAULT_TERRITORY_SLUG)
    if territory is None or sheet is None:
        return None
    range_years = get_year_columns(start_year, end_year)
    selected_year = resolve_selected_year(view_year, range_years)
    year_columns_mode = sheet["layout"] not in {"chars", "emission", "emission_tj", "volumes", "fuel"}
    years = [selected_year] if not year_columns_mode and selected_year is not None else range_years
    digits = resolve_rounding_digits(rounding_digits)
    coefficient_digits = resolve_rounding_digits(coefficient_rounding_digits or 0)
    from app.ecology.services.fuel_exchange_services import load_accepted_fuel_inputs

    layout = sheet["layout"]
    territories = get_territory_columns()
    coefficient_territories = get_territory_columns(COEFFICIENT_TERRITORIES) if is_coefficient else []
    catalog = coefficient_territories if is_coefficient else territories
    territory = next(item for item in catalog if item["slug"] == territory["slug"])
    territory_columns = [territory] if is_coefficient else territories
    value_columns = [
        {**terr, "slug": f'{terr["slug"]}:{year}', "territory_slug": terr["slug"], "year": year,
         "coefficient_territory_slug": coefficient_territory_slug(terr["slug"])}
        for terr in territory_columns for year in years
    ]
    columns_by_key = {column["slug"]: column for column in value_columns}
    inputs: dict[int, Any] = {}
    bundles_by_terr: dict[str, Any] = {}
    char_overrides: dict[tuple[str, str, int], dict[str, Any]] = {}
    fuel_summary_errors = []
    if layout == "fuel":
        if fuel_source:
            from app.ecology.services.fuel_summary_services import build_fuel_summary

            summary, errors = build_fuel_summary(years)
            inputs = summary[fuel_scope]
            fuel_summary_errors = errors[fuel_scope]
        else:
            inputs = load_accepted_fuel_inputs(years)
    elif layout == "coeff":
        coeff_overrides = load_coefficient_overrides(years, affiliation)
        default_slug = (
            affiliation if territory_slug == "vsego" and affiliation != "all" else territory_slug
        )
        for column in value_columns:
            year = column["year"]
            bundles_by_terr[column["slug"]] = {"coeffs": {
                kind["key"]: coeff_overrides.get(
                    (territory_slug, year, kind["key"]),
                    Decimal(str(default_coefficient(year, default_slug, kind["key"]))),
                )
                for kind in COEFF_KINDS
            }}
    elif layout == "chars":
        ensure_default_persisted_rows(years)
        char_overrides = load_characteristic_overrides(years)
    else:
        inputs = load_accepted_fuel_inputs(years)
        ensure_default_persisted_rows(years)
        input_overrides = {} if sheet["slug"] in {"zola", "sera", "co", "azot", "pg", "pg-tj"} else load_input_overrides(years)
        for year in years:
            by_terr = inputs.setdefault(year, {})
            for terr in territory_columns:
                slug = terr["slug"]
                bucket = by_terr.get(slug)
                if bucket is None:
                    bucket = empty_fuel_bucket()
                    by_terr[slug] = bucket
                for (ov_terr, y, row_key), amount in input_overrides.items():
                    if ov_terr == slug and y == year:
                        apply_input_override_to_bucket(bucket, row_key, amount)
        char_overrides = load_characteristic_overrides(years)
        coeff_overrides = load_coefficient_overrides(years)
        for column in value_columns:
            slug, year = column["territory_slug"], column["year"]
            bundles_by_terr[column["slug"]] = compute_year_bundle(
                slug, year, inputs.get(year, {}).get(slug), char_overrides, coeff_overrides,
            )
    rows: list[dict[str, Any]] = []
    if layout == "fuel":
        for spec in TOP_INPUT_ROWS:
            col_values, col_raw = _cells_for_territories(
                value_columns,
                lambda slug, spec=spec: bucket_top_input_amount(
                    inputs.get(columns_by_key[slug]["year"], {}).get(columns_by_key[slug]["territory_slug"]),
                    spec["key"],
                ),
                digits,
            )
            rows.append(
                _row_dict(
                    key=spec["key"],
                    label=spec["label"],
                    unit=spec["unit"],
                    kind=spec["kind"],
                    indent=0,
                    col_values=col_values,
                    col_values_raw=col_raw,
                )
            )
        for spec in get_fuel_module_consumption_row_specs():
            col_values, col_raw = _cells_for_territories(
                value_columns,
                lambda slug, spec=spec: bucket_field_amount(
                    inputs.get(columns_by_key[slug]["year"], {}).get(columns_by_key[slug]["territory_slug"]),
                    spec["key"],
                ),
                digits,
            )
            rows.append(
                _row_dict(
                    key=spec["key"],
                    label=spec["label"],
                    unit=spec.get("unit") or sheet["unit"],
                    kind=spec["kind"],
                    indent=spec.get("indent") or 0,
                    col_values=col_values,
                    col_values_raw=col_raw,
                    italic=bool(spec.get("indent")),
                )
            )
    elif layout == "chars":
        for spec in _characteristic_row_specs():
            is_header = spec["kind"] == KIND_TOTAL
            is_group = is_header and not DEFAULT_CHARACTERISTICS.get(spec["key"])
            values_by_year = {}
            raw_values = []
            for year in years:
                chars = resolve_chars(spec["key"], year, char_overrides, territory_slug)
                values_by_year[year] = {
                    field: "" if is_group else format_cell(chars.get(field), digits=digits)
                    for field, _label in CHAR_COLUMNS
                }
                raw_values.extend(None if is_group else chars.get(field) for field, _label in CHAR_COLUMNS)
            rows.append({
                "key": spec["key"],
                "label": spec["label"],
                "kind": spec["kind"],
                "indent": spec.get("indent") or 0,
                "italic": bool(spec.get("indent")),
                "css_class": "table-info" if is_header else "",
                "editable_values": not is_group,
                "char_values": values_by_year,
                "is_empty": False if is_header else not any(value is not None for value in raw_values),
            })
    elif layout == "coeff":
        for spec in COEFF_KINDS:
            col_values, col_raw = _cells_for_territories(
                value_columns,
                lambda slug, spec=spec: (bundles_by_terr.get(slug) or {}).get("coeffs", {}).get(
                    spec["key"]
                ),
                digits,
            )
            rows.append(
                _row_dict(
                    key=spec["key"],
                    label=spec["label"],
                    unit="",
                    kind=KIND_VALUE,
                    indent=0,
                    col_values=col_values,
                    col_values_raw=col_raw,
                    editable_values=True,
                    editable_field=spec["key"],
                )
            )
    elif layout in {"emission", "emission_tj"}:
        view = EMISSION_SHEET_VIEW[sheet["slug"]]
        if sheet["slug"] in {"zola", "sera", "co", "azot", "pg", "pg-tj"}:
            prefix, eta_key, eta_label = {
                "zola": ("ash", "ash_eta", "КПД золоулавливания"),
                "sera": ("so2", "sulfur_eta", "КПД сероочистки"),
                "co": ("co", "co_k", "Коэффициент подавления CO"),
                "azot": ("nox", "nox_n", "Коэффициент подавления оксидов азота в топке n"),
                "pg": ("pg", "pg_k", "Коэффициент подавления ПГ (оксидов углерода)"),
                "pg-tj": ("pg_tj", "pg_k", "Коэффициент подавления ПГ (оксидов углерода)"),
            }[sheet["slug"]]
            total_key = f"{prefix}_motkh_total"
            emitted_key = f"{prefix}_emitted"
            summary_values = {}
            for column in value_columns:
                slug = column["slug"]
                bundle = bundles_by_terr[slug]
                motkh = bundle[total_key]
                eta = bundle["coeffs"][eta_key]
                summary_values[slug] = {
                    total_key: motkh,
                    eta_key: eta,
                    emitted_key: apply_capture(motkh, eta),
                }
            for key, label in (
                (total_key, "ΣМотх."),
                (eta_key, eta_label),
                (emitted_key, "Мвыб."),
            ):
                col_values, col_raw = _cells_for_territories(
                    value_columns, lambda slug, key=key: summary_values[slug][key],
                    coefficient_digits if key == eta_key else digits,
                )
                row = _row_dict(
                    key=key, label=label, unit="", kind=KIND_TOTAL, indent=0,
                    col_values=col_values, col_values_raw=col_raw,
                )
                row.update(
                    span_pair=view["kind"] == "pair", is_empty=False,
                    css_class="table-warning" if key == eta_key else "table-primary",
                    label_html=format_emission_formula(label),
                    formula_tooltip_html=format_emission_formula(ot_formula_text(key)),
                )
                if key == eta_key:
                    row.update(
                        editable_values=True, editable_field=eta_key,
                        emitted_key=emitted_key,
                        capture_totals={col: str(values[total_key]) if values[total_key] is not None else ""
                                        for col, values in summary_values.items()},
                        default_coefficients={
                            col["slug"]: str(resolve_coeff(col["territory_slug"], col["year"], eta_key, {}))
                            for col in value_columns
                        },
                    )
                rows.append(row)
        if view["kind"] == "pair":
            left_metric = view["left_metric"]
            right_metric = view["right_metric"]
            for spec in FUEL_ROWS:
                pair_values, col_raw = _pair_cells_for_territories(
                    value_columns,
                    lambda slug, spec=spec: _metric_from_bundle(
                        bundles_by_terr, slug, spec["key"], left_metric
                    ),
                    lambda slug, spec=spec: _metric_from_bundle(
                        bundles_by_terr, slug, spec["key"], right_metric
                    ),
                    digits,
                )
                rows.append(
                    _row_dict(
                        key=spec["key"],
                        label=spec["label"],
                        unit="",
                        kind=spec["kind"],
                        indent=spec.get("indent") or 0,
                        col_values={},
                        col_values_raw=col_raw,
                        pair_values=pair_values,
                        italic=bool(spec.get("indent")),
                    )
                )
        else:
            metric = view["metric"]
            for spec in FUEL_ROWS:
                col_values, col_raw = _cells_for_territories(
                    value_columns,
                    lambda slug, spec=spec: _metric_from_bundle(
                        bundles_by_terr, slug, spec["key"], metric
                    ),
                    digits,
                )
                rows.append(
                    _row_dict(
                        key=spec["key"],
                        label=spec["label"],
                        unit="",
                        kind=spec["kind"],
                        indent=spec.get("indent") or 0,
                        col_values=col_values,
                        col_values_raw=col_raw,
                        italic=bool(spec.get("indent")),
                    )
                )
    else:
        formula = EMISSION_FORMULAS.get("zola", "")

        def _volume_raw(slug: str, spec_key: str) -> Any:
            bundle = bundles_by_terr.get(slug) or {}
            return (bundle.get("volumes") or {}).get(spec_key)

        for spec in VOLUME_ROWS:
            col_values, col_raw = _cells_for_territories(
                value_columns,
                lambda slug, spec=spec: _volume_raw(slug, spec["key"]),
                digits,
            )
            unit = "т" if spec["key"] == "co" else "тыс. т"
            rows.append(
                _row_dict(
                    key=spec["key"],
                    label=spec["label"],
                    unit=unit,
                    kind=KIND_TOTAL if spec["kind"] == KIND_TOTAL else KIND_VALUE,
                    indent=spec.get("indent") or 0,
                    col_values=col_values,
                    col_values_raw=col_raw,
                    formula_tooltip=formula if spec["key"] == "ash" else "",
                )
            )
    chars_year = years[-1] if years else None
    page_title = sheet.get("page_title") or sheet["sheet_name"]
    emission_view = EMISSION_SHEET_VIEW.get(sheet["slug"])
    formula_text = formula_text_for_sheet(sheet["slug"])
    formula_html = None
    if sheet["slug"] in {"zola", "sera", "co", "azot", "pg", "pg-tj"}:
        formula_html = format_emission_formula(formula_text)
        emission_view = dict(emission_view)
        if emission_view["kind"] == "pair":
            left_formula_key = "pg_tj_energy" if sheet["slug"] == "pg-tj" else "ash_to_natural"
            right_formula_key = "pg_tj_mass" if sheet["slug"] == "pg-tj" else emission_view["right_metric"]
            emission_view["left_formula"] = ot_formula_text(left_formula_key)
            emission_view["left_formula_html"] = format_emission_formula(emission_view["left_formula"])
            emission_view["right_formula"] = ot_formula_text(right_formula_key)
            emission_view["right_formula_html"] = format_emission_formula(emission_view["right_formula"])
        else:
            formula_key = "nox_motkh" if sheet["slug"] == "azot" else emission_view["metric"]
            emission_view["metric_formula_html"] = format_emission_formula(ot_formula_text(formula_key))
    return {
        "page_title": page_title,
        "page_title_html": format_emission_formula(page_title),
        "fuel_summary_errors": fuel_summary_errors,
        "territory": territory,
        "sheet": sheet,
        "territory_groups": group_territories(territories),
        "calc_sheets": list(CALC_SHEETS),
        "years": years,
        "range_years": range_years,
        "territory_columns": territory_columns,
        "value_columns": value_columns,
        "year_columns_mode": year_columns_mode,
        "coefficient_territories": coefficient_territories,
        "coefficient_affiliations": COEFFICIENT_AFFILIATIONS,
        "affiliation": affiliation,
        "start_year": range_years[0] if range_years else None,
        "end_year": range_years[-1] if range_years else None,
        "view_year": selected_year,
        "chars_year": chars_year,
        "char_columns": [
            {"key": key, "short": short} for key, short in CHAR_COLUMNS
        ],
        "char_header_groups": CHAR_HEADER_GROUPS,
        "char_header_cells": [
            {"key": key, "title": f"{_CHAR_HEADER_TITLES[key]} ({short})"}
            for key, short in CHAR_COLUMNS
        ],
        "filter_year_list": get_filter_year_list(),
        "rounding_digits": digits,
        "coefficient_rounding_digits": coefficient_digits,
        "year_features": get_year_feature_dict(),
        "rows": rows,
        "specific_emission_tables": (
            _build_specific_emission_tables(value_columns, bundles_by_terr, inputs, digits)
            if layout == "volumes" else []
        ),
        "emission_view": emission_view,
        "formula_text": formula_text,
        "formula_tooltip_html": format_natural_fuel_formula(formula_text),
        "formula_html": formula_html,
    }


def upsert_coefficient(
    territory_slug: str, year: int, kind: str, value: Any, affiliation: str = "all"
) -> OperatingTesCoefficient:
    if get_territory(territory_slug) is None and get_coefficient_territory(territory_slug) is None:
        raise ValueError("Неизвестная территория")
    if affiliation not in {"all", "minen", "prompred"}:
        raise ValueError("Неизвестная принадлежность")
    if kind not in {item["key"] for item in COEFF_KINDS}:
        raise ValueError("Неизвестный коэффициент")
    # Подписи для журнала – до нормализации срезов принадлежности.
    log_context = context_lines(
        ("лист", "Коэффициенты"),
        ("территория", territory_label(territory_slug)),
        ("принадлежность", affiliation_label(affiliation)),
        ("год", int(year)),
    )
    log_action = f"Коэффициенты – {territory_label(territory_slug)}"
    # Сохраняем прежние общие срезы принадлежности, используемые на «Объемах».
    if territory_slug == "vsego" and affiliation != "all":
        territory_slug, affiliation = affiliation, "all"
    elif territory_slug in {"minen", "prompred"} and affiliation != "all":
        raise ValueError("Для принадлежности необходимо выбрать территорию")
    version_id = get_current_db_version_id()
    query = OperatingTesCoefficient.query.filter_by(
        territory_slug=territory_slug,
        affiliation=affiliation,
        year_number=int(year),
        kind=kind,
    )
    if version_id is not None:
        query = query.filter(OperatingTesCoefficient.database_version_id == version_id)
    row = query.first()
    if row is None:
        row = OperatingTesCoefficient(
            territory_slug=territory_slug,
            affiliation=affiliation,
            year_number=int(year),
            kind=kind,
            database_version_id=version_id,
        )
        db.session.add(row)
        previous_value = default_coefficient(int(year), territory_slug, kind)
    else:
        # Пустое значение на странице показывается справочным – журнал должен
        # фиксировать то, что видел пользователь.
        previous_value = (
            row.value
            if row.value is not None
            else default_coefficient(int(year), territory_slug, kind)
        )
    row.value = _d(value)
    db.session.commit()
    log_cell_change(
        log_action,
        coefficient_label(kind),
        previous_value,
        row.value,
        context=log_context,
    )
    return row


def upsert_characteristic(
    territory_slug: str, fuel_key: str, year: int, field: str, value: Any
) -> OperatingTesFuelCharacteristic:
    if get_territory(territory_slug) is None:
        raise ValueError("Неизвестный срез характеристик")
    if fuel_key not in _FUEL_BY_KEY and not any(
        spec["key"] == fuel_key for spec in _characteristic_row_specs()
    ):
        raise ValueError("Неизвестный вид топлива")
    if field not in CHAR_EDIT_FIELDS:
        raise ValueError("Неизвестное поле характеристики")
    version_id = get_current_db_version_id()
    territory_slug = DEFAULT_TERRITORY_SLUG
    log_context = context_lines(
        ("лист", "Характеристики"),
        ("территория", territory_label(territory_slug)),
        ("топливо", fuel_label(fuel_key)),
        ("год", int(year)),
    )
    query = OperatingTesFuelCharacteristic.query.filter_by(
        territory_slug=territory_slug,
        fuel_key=fuel_key,
        year_number=int(year),
    )
    if version_id is not None:
        query = query.filter(OperatingTesFuelCharacteristic.database_version_id == version_id)
    defaults = DEFAULT_CHARACTERISTICS.get(fuel_key) or {}
    row = query.first()
    if row is None:
        row = OperatingTesFuelCharacteristic(
            territory_slug=territory_slug,
            fuel_key=fuel_key,
            year_number=int(year),
            database_version_id=version_id,
            note=DEFAULT_CHAR_NOTES.get(fuel_key),
            source_key=DEFAULT_CHAR_SOURCES.get(fuel_key),
            **{key: defaults.get(key) for key, _label in CHAR_COLUMNS},
        )
        db.session.add(row)
        previous_value = defaults.get(field)
    else:
        stored_value = getattr(row, field, None)
        previous_value = stored_value if stored_value is not None else defaults.get(field)
    setattr(row, field, _d(value))
    db.session.commit()
    log_cell_change(
        f"Характеристики – {territory_label(territory_slug)}",
        characteristic_label(field),
        previous_value,
        getattr(row, field),
        context=log_context,
    )
    return row


def upsert_input(territory_slug: str, year: int, row_key: str, value: Any) -> OperatingTesInputValue:
    if row_key not in TOP_INPUT_FIELD and row_key not in FUEL_PARAM_FIELDS:
        raise ValueError("Неизвестная строка ввода")
    version_id = get_current_db_version_id()
    query = OperatingTesInputValue.query.filter_by(
        territory_slug=territory_slug,
        year_number=int(year),
        row_key=row_key,
    )
    if version_id is not None:
        query = query.filter(OperatingTesInputValue.database_version_id == version_id)
    row = query.first()
    if row is None:
        row = OperatingTesInputValue(
            territory_slug=territory_slug,
            year_number=int(year),
            row_key=row_key,
            database_version_id=version_id,
        )
        db.session.add(row)
    row.value = _d(value)
    db.session.commit()
    return row
