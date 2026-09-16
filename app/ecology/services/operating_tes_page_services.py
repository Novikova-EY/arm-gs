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
from app.ecology.models.operating_tes_coefficient_model import OperatingTesCoefficient
from app.ecology.models.operating_tes_fuel_characteristic_model import (
    OperatingTesFuelCharacteristic,
)
from app.ecology.models.operating_tes_input_model import OperatingTesInputValue
from app.ecology.services.operating_tes_calc_services import (
    apply_capture,
    ash_motkh,
    co_motkh,
    equivalent_energy_billion_kwh,
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
    CHAR_SOURCE_KEYS,
    CHAR_SOURCE_OPTIONS,
    COEFF_KINDS,
    DEFAULT_CHAR_NOTES,
    DEFAULT_CHAR_SOURCES,
    DEFAULT_CHARACTERISTICS,
    DEFAULT_SHEET_SLUG,
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
    FUEL_ADOPTED_KEYS,
    SPR_COLUMNS,
    SPR_HEADER_GROUPS,
    VOLUME_ROWS,
    default_coefficient,
    fuel_label_bg,
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
    load_operating_tes_fuel_inputs,
)
from app.ecology.services.formula_text.operating_tes_formula_text_services import (
    formula_text_for_sheet,
)
from app.extensions import db

CHAR_TEXT_FIELDS = frozenset({"note", "source_key"})
CHAR_EDIT_FIELDS = {key for key, _label in CHAR_COLUMNS} | CHAR_TEXT_FIELDS
_CHAR_ROWSPAN_KEYS = {
    key
    for group in CHAR_HEADER_GROUPS
    if int(group.get("rowspan") or 1) > 1
    for key in group["keys"]
}

_BUNDLE_METRICS = (
    "b",
    "bn",
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


def group_territories() -> list[dict[str, Any]]:
    """Одна строка вкладок в порядке столбцов макета Excel."""
    return [{"group": "territory", "sheets": list(TERRITORIES)}]


def _sum_present(values: list[Decimal | None]) -> Decimal | None:
    present = [item for item in values if item is not None]
    if not present:
        return None
    return sum(present, Decimal("0"))


_FUEL_BY_KEY = {spec["key"]: spec for spec in FUEL_ROWS}
_FUEL_ROOTS = [spec for spec in FUEL_ROWS if not spec.get("parent_key")]


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
    char_overrides: dict[tuple[str, int], dict[str, Any]],
) -> dict[str, Any]:
    chars = resolve_chars(fuel_key, year, char_overrides)
    if DEFAULT_CHARACTERISTICS.get(fuel_key):
        return chars
    for child in children:
        if DEFAULT_CHARACTERISTICS.get(child):
            return resolve_chars(child, year, char_overrides)
    return chars


def load_characteristic_overrides(years: list[int]) -> dict[tuple[str, int], dict[str, Any]]:
    version_id = get_current_db_version_id()
    query = OperatingTesFuelCharacteristic.query.filter(
        OperatingTesFuelCharacteristic.year_number.in_(years)
    )
    if version_id is not None:
        query = query.filter(OperatingTesFuelCharacteristic.database_version_id == version_id)
    out: dict[tuple[str, int], dict[str, Any]] = {}
    for row in query.all():
        payload = {
            key: getattr(row, key)
            for key, _label in CHAR_COLUMNS
        }
        payload["tj_per_kt"] = row.tj_per_kt
        payload["t_co2_per_tj"] = row.t_co2_per_tj
        payload["note"] = row.note
        payload["source_key"] = row.source_key
        out[(row.fuel_key, int(row.year_number))] = payload
    return out


def load_coefficient_overrides(years: list[int]) -> dict[tuple[str, int, str], Decimal]:
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
        out[(row.territory_slug, int(row.year_number), row.kind)] = amount
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
        OperatingTesFuelCharacteristic.year_number.in_(years)
    )
    coeff_q = OperatingTesCoefficient.query.filter(
        OperatingTesCoefficient.year_number.in_(years)
    )
    if version_id is not None:
        char_q = char_q.filter(OperatingTesFuelCharacteristic.database_version_id == version_id)
        coeff_q = coeff_q.filter(OperatingTesCoefficient.database_version_id == version_id)
    existing_chars = {(row.fuel_key, int(row.year_number)) for row in char_q.all()}
    existing_coeffs = {
        (row.territory_slug, int(row.year_number), row.kind) for row in coeff_q.all()
    }
    added = False
    for year in years:
        for fuel_key, defaults in DEFAULT_CHARACTERISTICS.items():
            if (fuel_key, year) in existing_chars:
                continue
            db.session.add(
                OperatingTesFuelCharacteristic(
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
    overrides: dict[tuple[str, int], dict[str, Any]],
) -> dict[str, Any]:
    base = dict(DEFAULT_CHARACTERISTICS.get(fuel_key) or {})
    if fuel_key in DEFAULT_CHAR_NOTES:
        base["note"] = DEFAULT_CHAR_NOTES[fuel_key]
    if fuel_key in DEFAULT_CHAR_SOURCES:
        base["source_key"] = DEFAULT_CHAR_SOURCES[fuel_key]
    extra = overrides.get((fuel_key, year)) or {}
    for key, value in extra.items():
        if value is not None:
            base[key] = value
    return base


def resolve_coeff(
    territory_slug: str,
    year: int,
    kind: str,
    overrides: dict[tuple[str, int, str], Decimal],
) -> Decimal:
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
    ash_m = ash_motkh(bn, chars)
    so2_m = so2_motkh(bn, chars)
    nox_raw = nox_motkh(b_tce, chars)
    co_m = co_motkh(bn, chars)
    pg_m = pg_motkh(b_tce, chars)
    energy, pg_tj_m = pg_tj_energy_and_mass(bn, chars)
    return {
        "b": b_tce,
        "bn": bn,
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
    for parent, children in PARENT_CHILDREN.items():
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
    char_overrides: dict[tuple[str, int], dict[str, Any]],
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
        chars = resolve_chars(key, year, char_overrides)
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
            chars = _fallback_header_chars(key, year, children, char_overrides)
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
    e_mln = _nz((bucket or {}).get("e"))
    q = _nz((bucket or {}).get("q"))
    b_total = _nz((bucket or {}).get("b"))
    e_bln = (e_mln / Decimal("1000")) if e_mln is not None else None
    e_eq = equivalent_energy_billion_kwh(e_mln, q)
    return {
        "by_key": by_key,
        "volumes": volumes,
        "coeffs": coeffs,
        "e_bln": e_bln,
        "e_eq": e_eq,
        "q": q,
        "b": b_total,
        "chars": {
            spec["key"]: resolve_chars(spec["key"], year, char_overrides) for spec in FUEL_ROWS
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


def build_operating_tes_table_context(
    territory_slug: str,
    sheet_slug: str,
    start_year: Any = None,
    end_year: Any = None,
    rounding_digits: Any = None,
    view_year: Any = None,
) -> dict[str, Any] | None:
    territory = get_territory(territory_slug) or get_territory(DEFAULT_TERRITORY_SLUG)
    sheet = get_calc_sheet(sheet_slug) or get_calc_sheet(DEFAULT_SHEET_SLUG)
    if territory is None or sheet is None:
        return None
    range_years = get_year_columns(start_year, end_year)
    selected_year = resolve_selected_year(view_year, range_years)
    years = [selected_year] if selected_year is not None else []
    digits = resolve_rounding_digits(rounding_digits)
    layout = sheet["layout"]
    territory_columns = list(TERRITORIES)
    selected_year_int = selected_year
    inputs: dict[int, Any] = {}
    bundles_by_terr: dict[str, Any] = {}
    char_overrides: dict[tuple[str, int], dict[str, Any]] = {}
    if layout == "fuel":
        inputs = load_operating_tes_fuel_inputs(years)
    elif layout in {"chars", "spravochnik"}:
        ensure_default_persisted_rows(years)
        char_overrides = load_characteristic_overrides(years)
    else:
        inputs = load_operating_tes_fuel_inputs(years)
        ensure_default_persisted_rows(years)
        input_overrides = load_input_overrides(years)
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
        if selected_year_int is not None:
            for terr in territory_columns:
                slug = terr["slug"]
                bundles_by_terr[slug] = compute_year_bundle(
                    slug,
                    selected_year_int,
                    inputs.get(selected_year_int, {}).get(slug),
                    char_overrides,
                    coeff_overrides,
                )
    rows: list[dict[str, Any]] = []
    if layout == "fuel":
        for spec in TOP_INPUT_ROWS:
            col_values, col_raw = _cells_for_territories(
                territory_columns,
                lambda slug, spec=spec: bucket_top_input_amount(
                    inputs.get(selected_year_int, {}).get(slug) if selected_year_int else None,
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
                territory_columns,
                lambda slug, spec=spec: bucket_field_amount(
                    inputs.get(selected_year_int, {}).get(slug) if selected_year_int else None,
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
    elif layout in {"chars", "spravochnik"}:
        display_columns = SPR_COLUMNS if layout == "spravochnik" else CHAR_COLUMNS
        for year in years:
            for spec in FUEL_ROWS:
                is_group = bool(spec.get("is_header")) and not DEFAULT_CHARACTERISTICS.get(
                    spec["key"]
                )
                chars = resolve_chars(spec["key"], year, char_overrides)
                char_values: dict[str, str] = {}
                char_raw: dict[str, str] = {}
                for field, _label in display_columns:
                    raw = None if is_group else chars.get(field)
                    char_raw[field] = "" if raw is None else str(raw)
                    char_values[field] = (
                        "" if is_group else format_cell(raw, digits=digits)
                    )
                empty = not any(
                    char_raw.get(field) not in (None, "") for field, _label in display_columns
                )
                source_key = "" if is_group else str(chars.get("source_key") or "")
                note = "" if is_group else str(chars.get("note") or "")
                rows.append(
                    {
                        "key": spec["key"],
                        "label": spec["label"],
                        "kind": KIND_TOTAL if spec.get("is_header") else KIND_VALUE,
                        "indent": spec.get("indent") or 0,
                        "italic": bool(spec.get("indent")),
                        "css_class": "table-info" if spec.get("is_header") else "",
                        "editable_values": not is_group,
                        "char_values": char_values,
                        "is_empty": False if spec.get("is_header") else empty,
                        "year": year,
                        "note": note,
                        "source_key": source_key,
                        "label_bg": None if is_group else fuel_label_bg(spec["key"], source_key),
                        "label_fallback_bg": None if is_group else fuel_label_bg(spec["key"], None),
                        "adopted": (not is_group) and spec["key"] in FUEL_ADOPTED_KEYS,
                    }
                )
    elif layout == "coeff":
        for spec in COEFF_KINDS:
            col_values, col_raw = _cells_for_territories(
                territory_columns,
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
        if view["kind"] == "pair":
            left_metric = view["left_metric"]
            right_metric = view["right_metric"]
            for spec in FUEL_ROWS:
                pair_values, col_raw = _pair_cells_for_territories(
                    territory_columns,
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
                    territory_columns,
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
            mass = (bundle.get("volumes") or {}).get(spec_key)
            if layout == "volumes":
                return mass
            if layout == "specific_e":
                return specific_per_energy(mass, bundle.get("e_eq"))
            if layout == "specific_ee":
                return specific_per_energy(mass, bundle.get("e_bln"))
            return specific_per_fuel(mass, bundle.get("b"))

        for spec in VOLUME_ROWS:
            col_values, col_raw = _cells_for_territories(
                territory_columns,
                lambda slug, spec=spec: _volume_raw(slug, spec["key"]),
                digits,
            )
            unit = sheet["unit"]
            if layout == "volumes":
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
    display_char_columns = SPR_COLUMNS if layout == "spravochnik" else CHAR_COLUMNS
    display_char_groups = SPR_HEADER_GROUPS if layout == "spravochnik" else CHAR_HEADER_GROUPS
    return {
        "page_title": page_title,
        "territory": territory,
        "sheet": sheet,
        "territory_groups": group_territories(),
        "calc_sheets": list(CALC_SHEETS),
        "years": years,
        "range_years": range_years,
        "territory_columns": territory_columns,
        "start_year": range_years[0] if range_years else None,
        "end_year": range_years[-1] if range_years else None,
        "view_year": selected_year,
        "chars_year": chars_year,
        "char_columns": [
            {
                "key": key,
                "short": short,
                "hide_short": key in _CHAR_ROWSPAN_KEYS,
            }
            for key, short in display_char_columns
        ],
        "char_header_groups": [
            {
                "title": group["title"],
                "colspan": len(group["keys"]),
                "rowspan": int(group.get("rowspan") or 1),
            }
            for group in display_char_groups
        ],
        "source_options": list(CHAR_SOURCE_OPTIONS) if layout == "spravochnik" else [],
        "filter_year_list": get_filter_year_list(),
        "rounding_digits": digits,
        "year_features": get_year_feature_dict(),
        "rows": rows,
        "emission_view": emission_view,
        "formula_text": formula_text,
    }


def upsert_coefficient(territory_slug: str, year: int, kind: str, value: Any) -> OperatingTesCoefficient:
    version_id = get_current_db_version_id()
    query = OperatingTesCoefficient.query.filter_by(
        territory_slug=territory_slug,
        year_number=int(year),
        kind=kind,
    )
    if version_id is not None:
        query = query.filter(OperatingTesCoefficient.database_version_id == version_id)
    row = query.first()
    if row is None:
        row = OperatingTesCoefficient(
            territory_slug=territory_slug,
            year_number=int(year),
            kind=kind,
            database_version_id=version_id,
        )
        db.session.add(row)
    row.value = _d(value)
    db.session.commit()
    return row


def upsert_characteristic(fuel_key: str, year: int, field: str, value: Any) -> OperatingTesFuelCharacteristic:
    if field not in CHAR_EDIT_FIELDS:
        raise ValueError("Неизвестное поле характеристики")
    if field == "source_key" and value not in (None, "") and str(value) not in CHAR_SOURCE_KEYS:
        raise ValueError("Неизвестный источник характеристик")
    version_id = get_current_db_version_id()
    query = OperatingTesFuelCharacteristic.query.filter_by(
        fuel_key=fuel_key,
        year_number=int(year),
    )
    if version_id is not None:
        query = query.filter(OperatingTesFuelCharacteristic.database_version_id == version_id)
    row = query.first()
    if row is None:
        defaults = DEFAULT_CHARACTERISTICS.get(fuel_key) or {}
        row = OperatingTesFuelCharacteristic(
            fuel_key=fuel_key,
            year_number=int(year),
            database_version_id=version_id,
            note=DEFAULT_CHAR_NOTES.get(fuel_key),
            source_key=DEFAULT_CHAR_SOURCES.get(fuel_key),
            **{key: defaults.get(key) for key, _label in CHAR_COLUMNS},
        )
        db.session.add(row)
    if field in CHAR_TEXT_FIELDS:
        setattr(row, field, "" if value in (None, "") else str(value).strip())
    else:
        setattr(row, field, _d(value))
    db.session.commit()
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
