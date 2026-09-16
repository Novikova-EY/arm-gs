# -*- coding: utf-8 -*-
"""Страница расчёта по новым ТЭС: топливо d≠1, М = В × У, классы мощности."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.common.services.database_version_filter import get_current_db_version_id
from app.common.services.get_services.years.years_get_services import (
    get_year_feature_dict,
)
from app.ecology.models.new_tes_norm_model import NewTesNorm
from app.ecology.services.formula_text.operating_tes_formula_text_services import (
    ot_formula_text,
)
from app.ecology.services.new_tes_calc_services import (
    pg_mass_thousand_tonnes,
    zv_mass_thousand_tonnes,
    zv_mass_tonnes,
)
from app.ecology.services.new_tes_constants import (
    CAPACITY_CLASSES,
    CAPACITY_GT100_KEY,
    CAPACITY_LE100_KEY,
    DEFAULT_NORMS,
    DEFAULT_SHEET_SLUG,
    DEFAULT_TERRITORY_SLUG,
    NEW_TES_CALC_SHEETS,
    NEW_TES_EMISSION_VIEW,
    NORM_COLUMNS,
    NORM_FIELD_KEYS,
    NORM_HEADER_GROUPS,
    NORM_KINDS,
    VOLUME_ROW_FORMULA_KEYS,
    default_norm,
    get_calc_sheet,
    parse_norm_field,
)
from app.ecology.services.operating_tes_calc_services import (
    equivalent_energy_billion_kwh,
    specific_per_energy,
    specific_per_fuel,
)
from app.ecology.services.operating_tes_constants import (
    FUEL_ROWS,
    KIND_TOTAL,
    KIND_VALUE,
    PARENT_CHILDREN,
    TERRITORIES,
    TOP_INPUT_ROWS,
    VOLUME_ROWS,
    get_territory,
)
from app.ecology.services.operating_tes_fuel_input_services import (
    bucket_field_amount,
    bucket_top_input_amount,
    combine_capacity_buckets,
    empty_fuel_bucket,
    fuel_amount_for_key,
    get_fuel_module_consumption_row_specs,
    load_operating_tes_fuel_inputs,
)
from app.ecology.services.ecology_decimal_helpers import decimal_or_none as _d
from app.ecology.services.operating_tes_page_services import (
    _cells_for_territories,
    _metric_from_bundle,
    _nz,
    _pair_cells_for_territories,
    _row_dict,
    _sum_present,
    format_cell,
    get_filter_year_list,
    get_year_columns,
    group_territories,
    resolve_rounding_digits,
    resolve_selected_year,
    sum_metric_tree,
)
from app.ecology.services.operating_tes_formula_registry import NT_SHEET_FORMULA_KEYS
from app.extensions import db

_BUNDLE_METRICS = ("b", "ash", "so2", "nox", "co", "pg")

_SPECIFIC_SHEET_FORMULA = {
    "specific_e": "sheet_udel_e",
    "specific_fuel": "sheet_udel_fuel",
    "specific_ee": "sheet_udel_ee",
}


def _join_formulas(*keys: str) -> str:
    parts = []
    for key in keys:
        text = ot_formula_text(key)
        if text:
            parts.append(text)
    return "\n".join(parts)


def load_norm_overrides(years: list[int]) -> dict[tuple[str, str, int], dict[str, Any]]:
    version_id = get_current_db_version_id()
    query = NewTesNorm.query.filter(NewTesNorm.year_number.in_(years))
    if version_id is not None:
        query = query.filter(NewTesNorm.database_version_id == version_id)
    out: dict[tuple[str, str, int], dict[str, Any]] = {}
    for row in query.all():
        out[(row.fuel_key, row.capacity_class, int(row.year_number))] = {
            kind: getattr(row, kind) for kind in NORM_KINDS
        }
    return out


def ensure_default_norm_rows(years: list[int]) -> None:
    if not years:
        return
    version_id = get_current_db_version_id()
    query = NewTesNorm.query.filter(NewTesNorm.year_number.in_(years))
    if version_id is not None:
        query = query.filter(NewTesNorm.database_version_id == version_id)
    existing = {
        (row.fuel_key, row.capacity_class, int(row.year_number)) for row in query.all()
    }
    added = False
    for year in years:
        for fuel_key, by_class in DEFAULT_NORMS.items():
            for capacity_class, values in by_class.items():
                triple = (fuel_key, capacity_class, int(year))
                if triple in existing:
                    continue
                db.session.add(
                    NewTesNorm(
                        fuel_key=fuel_key,
                        capacity_class=capacity_class,
                        year_number=int(year),
                        database_version_id=version_id,
                        **{kind: values.get(kind) for kind in NORM_KINDS},
                    )
                )
                added = True
    if not added:
        return
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()


def resolve_norm(
    fuel_key: str,
    capacity_class: str,
    year: int,
    overrides: dict[tuple[str, str, int], dict[str, Any]],
) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    extra = overrides.get((fuel_key, capacity_class, year)) or {}
    for kind in NORM_KINDS:
        raw = extra.get(kind)
        if raw is None:
            raw = default_norm(fuel_key, capacity_class, kind)
        amount = _d(raw)
        out[kind] = amount if amount is not None else Decimal("0")
    return out


def _leaf_emissions(
    fuel_key: str,
    by_class: dict[str, dict[str, Decimal]] | None,
    year: int,
    overrides: dict[tuple[str, str, int], dict[str, Any]],
) -> dict[str, Decimal | None]:
    totals = {metric: None for metric in _BUNDLE_METRICS}
    b_sum = None
    for capacity_class in CAPACITY_CLASSES:
        bucket = (by_class or {}).get(capacity_class)
        b_tce = fuel_amount_for_key(bucket, fuel_key)
        if b_tce is None:
            continue
        b_sum = (b_sum or Decimal("0")) + b_tce
        norms = resolve_norm(fuel_key, capacity_class, year, overrides)
        ash = zv_mass_thousand_tonnes(b_tce, norms["ash"])
        so2 = zv_mass_thousand_tonnes(b_tce, norms["so2"])
        nox = zv_mass_thousand_tonnes(b_tce, norms["nox"])
        co = zv_mass_tonnes(b_tce, norms["co"])
        pg = pg_mass_thousand_tonnes(b_tce, norms["pg"])
        for metric, value in (
            ("ash", ash),
            ("so2", so2),
            ("nox", nox),
            ("co", co),
            ("pg", pg),
        ):
            if value is None:
                continue
            totals[metric] = (totals[metric] or Decimal("0")) + value
    totals["b"] = b_sum
    return totals


def compute_new_tes_year_bundle(
    territory_slug: str,
    year: int,
    by_class: dict[str, dict[str, Decimal]] | None,
    norm_overrides: dict[tuple[str, str, int], dict[str, Any]],
) -> dict[str, Any]:
    by_key: dict[str, dict[str, Decimal | None]] = {}
    for spec in FUEL_ROWS:
        if spec.get("is_header"):
            continue
        by_key[spec["key"]] = _leaf_emissions(
            spec["key"], by_class, year, norm_overrides
        )
    header_specs = sorted(
        [spec for spec in FUEL_ROWS if spec.get("is_header")],
        key=lambda item: int(item.get("indent") or 0),
        reverse=True,
    )
    for spec in header_specs:
        children = tuple(spec.get("children") or PARENT_CHILDREN.get(spec["key"]) or ())
        computed = {metric: None for metric in _BUNDLE_METRICS}
        for metric in _BUNDLE_METRICS:
            computed[metric] = _sum_present(
                [(by_key.get(child) or {}).get(metric) for child in children]
            )
        if computed["b"] is None:
            computed = _leaf_emissions(spec["key"], by_class, year, norm_overrides)
        by_key[spec["key"]] = computed
    volumes = {
        "ash": sum_metric_tree(by_key, "ash"),
        "so2": sum_metric_tree(by_key, "so2"),
        "nox": sum_metric_tree(by_key, "nox"),
        "co": sum_metric_tree(by_key, "co"),
        "co2": sum_metric_tree(by_key, "pg"),
    }
    volumes["pollutants_total"] = _sum_present(
        [volumes["ash"], volumes["so2"], volumes["nox"], volumes["co"]]
    )
    combined = combine_capacity_buckets(by_class)
    e_mln = _nz(combined.get("e"))
    q = _nz(combined.get("q"))
    b_total = _nz(combined.get("b"))
    e_bln = (e_mln / Decimal("1000")) if e_mln is not None else None
    e_eq = equivalent_energy_billion_kwh(e_mln, q)
    return {
        "by_key": by_key,
        "volumes": volumes,
        "e_bln": e_bln,
        "e_eq": e_eq,
        "q": q,
        "b": b_total,
        "combined": combined,
    }


def _volume_tooltip(spec_key: str, layout: str) -> str:
    keys = list(VOLUME_ROW_FORMULA_KEYS.get(spec_key) or ())
    extra = _SPECIFIC_SHEET_FORMULA.get(layout)
    if extra:
        keys.append(extra)
    return _join_formulas(*keys)


def build_new_tes_table_context(
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
    norm_overrides: dict[tuple[str, str, int], dict[str, Any]] = {}
    if layout == "fuel":
        raw = load_operating_tes_fuel_inputs(
            years, operating=False, by_capacity=True
        )
        inputs = {
            year: {
                slug: combine_capacity_buckets(by_class)
                for slug, by_class in (by_terr or {}).items()
            }
            for year, by_terr in raw.items()
        }
    elif layout == "chars":
        ensure_default_norm_rows(years)
        norm_overrides = load_norm_overrides(years)
    else:
        raw = load_operating_tes_fuel_inputs(
            years, operating=False, by_capacity=True
        )
        ensure_default_norm_rows(years)
        norm_overrides = load_norm_overrides(years)
        if selected_year_int is not None:
            by_terr = raw.get(selected_year_int) or {}
            for terr in territory_columns:
                slug = terr["slug"]
                bundles_by_terr[slug] = compute_new_tes_year_bundle(
                    slug,
                    selected_year_int,
                    by_terr.get(slug),
                    norm_overrides,
                )
            inputs = {
                selected_year_int: {
                    slug: (bundles_by_terr.get(slug) or {}).get("combined")
                    or empty_fuel_bucket()
                    for slug in (item["slug"] for item in territory_columns)
                }
            }
    rows: list[dict[str, Any]] = []
    if layout == "fuel":
        for spec in TOP_INPUT_ROWS:
            col_values, col_raw = _cells_for_territories(
                territory_columns,
                lambda slug, spec=spec: bucket_top_input_amount(
                    inputs.get(selected_year_int, {}).get(slug)
                    if selected_year_int
                    else None,
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
                    inputs.get(selected_year_int, {}).get(slug)
                    if selected_year_int
                    else None,
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
        for year in years:
            for spec in FUEL_ROWS:
                is_group = bool(spec.get("is_header")) and spec["key"] not in DEFAULT_NORMS
                le = resolve_norm(spec["key"], CAPACITY_LE100_KEY, year, norm_overrides)
                gt = resolve_norm(spec["key"], CAPACITY_GT100_KEY, year, norm_overrides)
                char_values: dict[str, str] = {}
                char_raw: dict[str, str] = {}
                packed = {CAPACITY_LE100_KEY: le, CAPACITY_GT100_KEY: gt}
                for field, _label in NORM_COLUMNS:
                    parsed = parse_norm_field(field)
                    raw = None
                    if parsed and not is_group:
                        kind, cls = parsed
                        raw = packed[cls].get(kind)
                    char_raw[field] = "" if raw is None else str(raw)
                    char_values[field] = "" if is_group else format_cell(raw, digits=digits)
                empty = not any(
                    char_raw.get(field) not in (None, "") for field, _label in NORM_COLUMNS
                )
                rows.append(
                    {
                        "key": spec["key"],
                        "label": spec["label"],
                        "kind": KIND_TOTAL if spec.get("is_header") else KIND_VALUE,
                        "indent": spec.get("indent") or 0,
                        "italic": bool(spec.get("indent")),
                        "css_class": "table-info" if spec.get("is_header") else "",
                        "editable_values": not is_group and spec["key"] in DEFAULT_NORMS,
                        "char_values": char_values,
                        "is_empty": False if spec.get("is_header") else empty,
                        "year": year,
                        "note": "",
                        "source_key": "",
                        "label_bg": None,
                        "label_fallback_bg": None,
                        "adopted": False,
                    }
                )
    elif layout == "emission":
        view = NEW_TES_EMISSION_VIEW[sheet["slug"]]
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
                    formula_tooltip=_volume_tooltip(spec["key"], layout),
                )
            )
    emission_view = NEW_TES_EMISSION_VIEW.get(sheet["slug"])
    if emission_view is not None:
        emission_view = dict(emission_view)
        emission_view["left_formula"] = ot_formula_text(
            emission_view.get("left_formula_key") or ""
        )
        emission_view["right_formula"] = ot_formula_text(
            emission_view.get("right_formula_key") or ""
        )
    sheet_formula_key = NT_SHEET_FORMULA_KEYS.get(sheet["slug"])
    formula_text = ot_formula_text(sheet_formula_key) if sheet_formula_key else ""
    return {
        "page_title": sheet.get("page_title") or sheet["sheet_name"],
        "territory": territory,
        "sheet": sheet,
        "territory_groups": group_territories(),
        "calc_sheets": list(NEW_TES_CALC_SHEETS),
        "years": years,
        "range_years": range_years,
        "territory_columns": territory_columns,
        "start_year": range_years[0] if range_years else None,
        "end_year": range_years[-1] if range_years else None,
        "view_year": selected_year,
        "chars_year": years[-1] if years else None,
        "char_columns": [
            {"key": key, "short": short, "hide_short": False}
            for key, short in NORM_COLUMNS
        ],
        "char_header_groups": [
            {
                "title": group["title"],
                "colspan": len(group["keys"]),
                "rowspan": int(group.get("rowspan") or 1),
            }
            for group in NORM_HEADER_GROUPS
        ],
        "source_options": [],
        "filter_year_list": get_filter_year_list(),
        "rounding_digits": digits,
        "year_features": get_year_feature_dict(),
        "rows": rows,
        "emission_view": emission_view,
        "formula_text": formula_text,
        "table_endpoint": "ecology_bp.new_tes_table",
        "value_endpoint": "ecology_bp.new_tes_update_value",
    }


def upsert_norm(fuel_key: str, year: int, field: str, value: Any) -> NewTesNorm:
    parsed = parse_norm_field(field)
    if parsed is None or field not in NORM_FIELD_KEYS:
        raise ValueError("Неизвестное поле норматива")
    kind, capacity_class = parsed
    if fuel_key not in DEFAULT_NORMS:
        raise ValueError("Неизвестный вид топлива")
    version_id = get_current_db_version_id()
    query = NewTesNorm.query.filter_by(
        fuel_key=fuel_key,
        capacity_class=capacity_class,
        year_number=int(year),
    )
    if version_id is not None:
        query = query.filter(NewTesNorm.database_version_id == version_id)
    row = query.first()
    if row is None:
        defaults = DEFAULT_NORMS.get(fuel_key, {}).get(capacity_class) or {}
        row = NewTesNorm(
            fuel_key=fuel_key,
            capacity_class=capacity_class,
            year_number=int(year),
            database_version_id=version_id,
            **{item: defaults.get(item) for item in NORM_KINDS},
        )
        db.session.add(row)
    setattr(row, kind, _d(value))
    db.session.commit()
    return row
