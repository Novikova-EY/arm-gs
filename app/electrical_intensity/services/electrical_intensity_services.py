# -*- coding: utf-8 -*-
"""Сервисы страницы электроёмкости."""

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

from flask import session
from sqlalchemy import and_, func

from app.common.services.database_version_services import get_current_version
from app.common.services.help_services import (
    apply_thousand_grouping_to_display,
    format_decimal_trim_for_display,
)
from app.common.services.get_services.years.years_get_services import get_year_feature_dict
from app.common.services.get_services.territories.federal_district_get_services import (
    get_federal_district_list,
    get_federal_district_list_full,
)
from app.economics.models.federal_district_accum_fixed_capital_parameter_model import (
    FederalDistrictAccumFixedCapitalParameter,
)
from app.economics.models.russia_federation_accum_fixed_capital_parameter_model import (
    RussiaFederationAccumFixedCapitalParameter,
)
from app.economics.models.russia_federation_consumption_parameter_model import (
    RussiaFederationConsumptionParameter,
)
from app.economics.models.russia_federation_product_output_parameter_model import (
    RussiaFederationProductOutputParameter,
)
from app.economics.models.federal_district_eat_consumption_parameter_model import (
    FederalDistrictEATConsumptionParameter,
)
from app.economics.models.federal_district_product_output_parameter_model import (
    FederalDistrictProductOutputParameter,
)
from app.electrical_intensity.models.federal_district_electrical_intensity_coefficient_model import (
    FederalDistrictElectricalIntensityCoefficient,
)
from app.electrical_intensity.models.federal_district_electrical_intensity_year_parameter_model import (
    FederalDistrictElectricalIntensityYearParameter,
)
from app.electrical_intensity.models.federal_district_population_consumption_coefficient_model import (
    FederalDistrictPopulationConsumptionCoefficient,
)
from app.electrical_intensity.models.federal_district_population_consumption_year_parameter_model import (
    FederalDistrictPopulationConsumptionYearParameter,
)
from app.electrical_intensity.models.federal_district_fd_total_consumption_coefficient_model import (
    FederalDistrictFdTotalConsumptionCoefficient,
)
from app.electrical_intensity.models.russia_federation_electrical_intensity_coefficient_model import (
    RussiaFederationElectricalIntensityCoefficient,
)
from app.electrical_intensity.models.russia_federation_electrical_intensity_year_parameter_model import (
    RussiaFederationElectricalIntensityYearParameter,
)
from app.extensions import db
from app.generation.models.station.station_gaes_charge_consumption_model import (
    StationGaesChargeConsumption,
)
from app.generation.models.station.station_model import Station
from app.power_demand.services import demand_parameter_services as dps
from app.refdata.models.years.year_model import Year
from app.electrical_intensity.services.electrical_intensity_constants import (
    EI_BILLION_KWH_FACTOR,
    EI_INTENSITY_UNIT_FACTOR,
    EI_FD_EXCLUDED_NAME_KEYS,
    EI_FD_PLACEHOLDER_NAME_KEYS,
    INDUSTRIAL_GROUP_SECTION_LABEL,
    NETWORK_LOSSES_VED_TARGET,
    POWER_STATION_OWN_NEEDS_VED_TARGET,
    REF_ROW_ACCUM_FIXED_CAPITAL,
    REF_ROW_CONSUMPTION,
    REF_ROW_CSS_BY_KIND,
    REF_ROW_FD_ACCUM_FIXED_CAPITAL,
    REF_ROW_FD_NETWORK_LOSSES,
    REF_ROW_FD_POWER_STATION,
    REF_ROW_FD_TOTAL_CONSUMPTION,
    REF_ROW_FD_VED_CONSUMPTION,
    REF_ROW_FD_VRP,
    REF_ROW_FD_CSS_BY_KIND,
    REF_ROW_FD_FORMULA_KEY_BY_KIND,
    REF_ROW_FD_PLAN_FORMULA_KEY_BY_KIND,
    REF_ROW_FD_LABEL_BY_KIND,
    REF_ROW_FD_UNIT_BY_KIND,
    EI_FD_TOTAL_K_DISPLAY_ROUNDING_DIGITS,
    REF_ROW_INDUSTRIAL_FORMULA_KEY_BY_KIND,
    REF_ROW_KINDS,
    REF_ROW_PRODUCT_OUTPUT,
    REF_ROW_FORMULA_KEY_BY_KIND,
    REF_ROW_RF_CSS_BY_KIND,
    REF_ROW_RF_FORMULA_KEY_BY_KIND,
    REF_ROW_RF_GAES,
    REF_ROW_RF_CONSUMPTION_WITHOUT_GAES,
    REF_ROW_RF_GDP,
    REF_ROW_RF_GDP_INTENSITY,
    REF_ROW_RF_GROWTH_RATE,
    REF_ROW_RF_LABEL_BY_KIND,
    REF_ROW_RF_NETWORK_LOSSES,
    REF_ROW_RF_POWER_STATION,
    REF_ROW_RF_SOURCE_ENDPOINT,
    REF_ROW_RF_SOURCE_PAGE_TITLE,
    REF_ROW_RF_TOTAL_CONSUMPTION,
    REF_ROW_RF_UNIT_BY_KIND,
    REF_ROW_RF_VED_FORMULA_KEY_BY_KIND,
    REF_ROW_RF_VED_UNIT_BY_KIND,
    RF_VED_INTENSITY_ROW_LABEL,
    RF_VED_REF_ROW_KINDS,
    rf_ved_product_output_row_label,
    REF_ROW_RF_VED_CONSUMPTION,
    REF_ROW_SOURCE_ENDPOINT,
    REF_ROW_SOURCE_PAGE_TITLE,
    REF_ROW_UNIT_BY_KIND,
    ROW_FORMULA_KEY_BY_KIND,
    EI_COEFFICIENT_X_AVG_START_YEAR,
    EI_COEFFICIENT_A_COMPUTED_DISPLAY_ROUNDING_DIGITS,
    EI_COEFFICIENT_X_DISPLAY_ROUNDING_DIGITS,
    EI_FORMULA_EDITABLE_ROW_KINDS,
    EI_GRAPH_POINT_ROUNDING_DIGITS,
    EI_INTENSITY_MAX_FRACTION_DIGITS,
    EI_INTENSITY_TOOLTIP_ROUNDING_DIGITS,
    EI_INTENSITY_VALUE_ROW_KINDS,
    EI_MODEL_ROW_KINDS,
    ROW_KIND_CALCULATED,
    ROW_KIND_DELTA,
    ROW_KIND_GRAPH_POINT,
    ROW_KIND_INTENSITY,
    ROW_KINDS,
    ROW_LABEL_BY_KIND,
    ref_row_label,
    rf_gdp_row_label,
    HOUSEHOLD_VED_TARGET,
    POPULATION_SECTION_LABEL,
    POPULATION_SECTION_MARKER,
    POP_REF_ROW_CSS_BY_KIND,
    POP_REF_ROW_FORMULA_KEY_BY_KIND,
    POP_REF_ROW_PLAN_FORMULA_KEY_BY_KIND,
    POP_REF_ROW_LABEL_BY_KIND,
    POP_REF_ROW_SOURCE_ENDPOINT,
    POP_REF_ROW_SOURCE_PAGE_TITLE,
    POP_REF_ROW_UNIT_BY_KIND,
    POP_ROW_FORMULA_KEY_BY_KIND,
    POP_ROW_LABEL_BY_KIND,
    REF_ROW_ACCUM_MONETARY_INCOME,
    REF_ROW_HOUSEHOLD_CONSUMPTION,
    REF_ROW_POPULATION,
)
from app.economics.services.product_output_services import (
    _load_values_map as _load_product_output_values_map,
)
from app.economics.services.accum_fixed_capital_services import (
    _load_values_map as _load_accum_fixed_capital_values_map,
)
from app.economics.services.ved_consumption_services import (
    _load_values_map as _load_ved_consumption_values_map,
)
from app.electrical_intensity.services.formula_text.electrical_intensity_formula_text_services import (
    ei_formula_text,
)
from app.electrical_intensity.services.electrical_intensity_chart_services import (
    build_ei_section_scatter_chart,
    build_fd_summary_scatter_chart,
    build_rf_scatter_chart,
)
from app.electrical_intensity.services.electrical_intensity_logging import (
    _fmt_log_value,
    log_electrical_intensity_cell_change,
    queue_electrical_intensity_cell_change,
)
from app.common.services.get_services.years.years_get_services import (
    get_ges_tep_current_price_year_number,
    get_year_number_for_year_feature_name_current_version,
)
from app.economics.services.ved_consumption_constants import (
    INDUSTRIAL_COMPONENT_VED_TARGETS,
    TOTAL_VED_NAME,
)
from app.economics.services.ved_consumption_services import (
    _find_ved_by_target,
    _federal_district_name_key,
    _is_parent_industrial_ved_name,
    _normalize_label,
)
from app.economics.services.population_services import (
    _load_values_by_fd_year as _load_population_by_fd_year,
)
from app.economics.services.accum_monetary_income_services import (
    _load_values_by_fd_year as _load_accum_monetary_income_by_fd_year,
)
from app.refdata.models.years.year_model import Year
from app.refdata.models.economic_activity.economic_activity_type_model import EconomicActivityType
from app.generation.services.machine_services.machine_services import (
    is_same_decimal,
    to_decimal,
)
from app.refdata.models.territories.federal_district_model import FederalDistrict


def _username() -> str:
    return session.get("username", "Неизвестный пользователь")


def _is_federal_district_excluded(fd: FederalDistrict) -> bool:
    for attr in ("name", "name_abr", "name_full"):
        key = _federal_district_name_key(getattr(fd, attr, None))
        if not key:
            continue
        if key in EI_FD_EXCLUDED_NAME_KEYS or key in EI_FD_PLACEHOLDER_NAME_KEYS:
            return True
    return False


def _federal_districts_for_page() -> list[FederalDistrict]:
    return [fd for fd in get_federal_district_list() if not _is_federal_district_excluded(fd)]


def _format_full_numeric_tooltip(value: Any) -> str:
    if value in (None, ""):
        return ""
    s = format_decimal_trim_for_display(value, digits=0)
    return apply_thousand_grouping_to_display(s) if s else ""


def _ei_tooltip_digits_for_row_kind(row_kind: str | None) -> int | None:
    """None — полное значение без фиксированного округления."""
    if row_kind in EI_INTENSITY_VALUE_ROW_KINDS:
        return EI_INTENSITY_TOOLTIP_ROUNDING_DIGITS
    if row_kind == ROW_KIND_GRAPH_POINT:
        return EI_GRAPH_POINT_ROUNDING_DIGITS
    return None


def _format_cell_tooltip(value: Any, *, row_kind: str | None = None) -> str:
    if value in (None, ""):
        return ""
    digits = _ei_tooltip_digits_for_row_kind(row_kind)
    if digits is None:
        return _format_full_numeric_tooltip(value)
    s = format_decimal_trim_for_display(value, digits=digits)
    return apply_thousand_grouping_to_display(s) if s else ""


def _format_cell_display(value: Any, rounding_digits: int) -> str:
    if value is None:
        return "—"
    shown = format_decimal_trim_for_display(value, digits=rounding_digits)
    return apply_thousand_grouping_to_display(shown) if shown else "—"


def _ei_current_year_number() -> int | None:
    """Год с признаком «текущий» (с запасным «текущий (оценка)»)."""
    n = get_year_number_for_year_feature_name_current_version("текущий")
    if n is not None:
        return n
    return get_ges_tep_current_price_year_number()


def _ei_years_through_current(
    display_years: list[int], current_year: int | None
) -> frozenset[int]:
    """Годы, для которых электроёмкость и связанные строки считаются по формулам."""
    if current_year is None:
        return frozenset(display_years)
    return frozenset(y for y in display_years if y <= current_year)


def _ei_years_all_display(display_years: list[int]) -> frozenset[int]:
    """Все отображаемые годы (без ограничения текущим годом)."""
    return frozenset(display_years)


def _ei_plan_years(
    display_years: list[int],
    current_year: int | None,
    year_features: dict[int, str] | None = None,
) -> frozenset[int]:
    """Годы с признаком «план» (или после текущего года, если признак не задан)."""
    yf = year_features if year_features is not None else (get_year_feature_dict() or {})
    plan = frozenset(
        y
        for y in display_years
        if str(yf.get(y) or "").strip().lower().replace(" ", "") == "план"
    )
    if plan:
        return plan
    if current_year is None:
        return frozenset()
    return frozenset(y for y in display_years if y > current_year)


def _refresh_reference_row_displays(
    row: dict[str, Any],
    *,
    display_years: list[int],
    rounding_digits: int,
) -> None:
    cells = row.get("cells") or {}
    row["cell_tooltips"] = {
        year: _format_full_numeric_tooltip(cells.get(year)) for year in display_years
    }
    row["cells_display"] = {
        year: _format_cell_display(cells.get(year), rounding_digits)
        for year in display_years
    }


def _resolve_effective_coef_x_for_ved(
    *,
    ved_id: int,
    db_coef_x: Decimal | None,
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    ei_year_by_ved_kind_year: dict[tuple[int, str, int], Decimal | None],
    display_years: list[int],
    current_year: int | None,
) -> Decimal | None:
    """X из среднего graph_point (БД или формула) с запасным значением из коэффициентов."""
    gp_db_years = _graph_point_db_years_from_fd_ved_map(ved_id, ei_year_by_ved_kind_year)
    gp_cells: dict[int, Decimal | None] = {}
    for year in _ei_years_through_current(display_years, current_year):
        if year in gp_db_years:
            gp_cells[year] = ei_year_by_ved_kind_year.get(
                (ved_id, ROW_KIND_GRAPH_POINT, year)
            )
            continue
        intensity_curr = _compute_ei_intensity(
            consumption_by_ved_year.get((ved_id, year)),
            product_output_by_ved_year.get((ved_id, year)),
        )
        intensity_prev = _compute_ei_intensity(
            consumption_by_ved_year.get((ved_id, year - 1)),
            product_output_by_ved_year.get((ved_id, year - 1)),
        )
        gp_cells[year] = _compute_ei_graph_point(
            intensity_curr,
            intensity_prev,
            accum_by_ved_year.get((ved_id, year)),
            accum_by_ved_year.get((ved_id, year - 1)),
        )
    computed_x = _compute_coef_x_from_graph_points(
        {"cells": gp_cells}, current_year=current_year
    )
    return computed_x if computed_x is not None else db_coef_x


def _effective_coef_a(
    coef_a_manual: Decimal | None,
    coef_a_computed: Decimal | None,
) -> Decimal | None:
    """A для расчётов: вручную введённый, иначе «Арасч»."""
    return coef_a_manual if coef_a_manual is not None else coef_a_computed


def _resolve_effective_coef_a_for_ved(
    *,
    ved_id: int,
    db_coef_a: Decimal | None,
    db_coef_x: Decimal | None,
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    ei_year_by_ved_kind_year: dict[tuple[int, str, int], Decimal | None],
    display_years: list[int],
    current_year: int | None,
) -> Decimal | None:
    """A из БД или «Арасч» по фактической электроёмкости и накопленным инвестициям."""
    if db_coef_a is not None:
        return db_coef_a
    effective_x = _resolve_effective_coef_x_for_ved(
        ved_id=ved_id,
        db_coef_x=db_coef_x,
        consumption_by_ved_year=consumption_by_ved_year,
        product_output_by_ved_year=product_output_by_ved_year,
        accum_by_ved_year=accum_by_ved_year,
        ei_year_by_ved_kind_year=ei_year_by_ved_kind_year,
        display_years=display_years,
        current_year=current_year,
    )
    intensity_cells: dict[int, Decimal | None] = {}
    for year in _ei_years_through_current(display_years, current_year):
        intensity_cells[year] = _compute_ei_intensity(
            consumption_by_ved_year.get((ved_id, year)),
            product_output_by_ved_year.get((ved_id, year)),
        )
    return _compute_coef_a_from_intensity(
        {"cells": intensity_cells},
        accum_by_ved_year,
        ved_id=ved_id,
        coef_x=effective_x,
        current_year=current_year,
    )


def _compute_ved_plan_consumption_by_year(
    *,
    ved_id: int,
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    coef_a: Decimal | None,
    coef_x: Decimal | None,
    display_years: list[int],
    current_year: int | None,
) -> dict[int, Decimal]:
    """Потребление по одному ВЭД для годов «план» (без округления)."""
    if coef_a is None or coef_x is None:
        return {}
    plan_years = _ei_plan_years(display_years, current_year)
    cells: dict[int, Decimal] = {}
    for year in plan_years:
        product = product_output_by_ved_year.get((ved_id, year))
        intensity = _compute_ei_calculated(
            coef_a,
            coef_x,
            accum_by_ved_year.get((ved_id, year)),
        )
        val = _compute_consumption_from_intensity(intensity, product)
        if val is not None:
            cells[year] = val
    return cells


def _enrich_ved_consumption_plan_years(
    reference_rows: list[dict[str, Any]],
    *,
    ved_id: int,
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    coef_a: Decimal | None,
    coef_x: Decimal | None,
    display_years: list[int],
    rounding_digits: int,
    current_year: int | None,
) -> None:
    """Потребление по ВЭД для годов «план»: выпуск × электроёмкость (расчётная)."""
    consumption_row = next(
        (r for r in reference_rows if r.get("row_kind") == REF_ROW_CONSUMPTION),
        None,
    )
    if consumption_row is None:
        return

    plan_cells = _compute_ved_plan_consumption_by_year(
        ved_id=ved_id,
        product_output_by_ved_year=product_output_by_ved_year,
        accum_by_ved_year=accum_by_ved_year,
        coef_a=coef_a,
        coef_x=coef_x,
        display_years=display_years,
        current_year=current_year,
    )
    if not plan_cells:
        return

    formula_key = REF_ROW_FORMULA_KEY_BY_KIND.get(REF_ROW_CONSUMPTION, "")
    if formula_key:
        consumption_row["formula_hint"] = ei_formula_text(formula_key)

    cells = consumption_row.setdefault("cells", {})
    for year, val in plan_cells.items():
        cells[year] = val

    consumption_row["is_computed"] = True
    consumption_row["computed_years"] = frozenset(plan_cells.keys())
    _refresh_reference_row_displays(
        consumption_row,
        display_years=display_years,
        rounding_digits=rounding_digits,
    )


def _enrich_industrial_consumption_plan_years(
    reference_rows: list[dict[str, Any]],
    *,
    component_ved_ids: list[int],
    refdata_ved_ids: frozenset[int],
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    coef_by_ved: dict[int, tuple[Decimal | None, Decimal | None]],
    ei_year_by_ved_kind_year: dict[tuple[int, str, int], Decimal | None],
    display_years: list[int],
    rounding_digits: int,
    current_year: int | None,
) -> None:
    """Потребление «Промышленное производство» для годов «план»: сумма по компонентным ВЭД."""
    consumption_row = next(
        (r for r in reference_rows if r.get("row_kind") == REF_ROW_CONSUMPTION),
        None,
    )
    if consumption_row is None:
        return

    plan_years = _ei_plan_years(display_years, current_year)
    if not plan_years:
        return

    summed: dict[int, Decimal] = {}
    for ved_id in component_ved_ids:
        if ved_id not in refdata_ved_ids:
            continue
        coef_a, db_coef_x = coef_by_ved.get(ved_id, (None, None))
        coef_x = _resolve_effective_coef_x_for_ved(
            ved_id=ved_id,
            db_coef_x=db_coef_x,
            consumption_by_ved_year=consumption_by_ved_year,
            product_output_by_ved_year=product_output_by_ved_year,
            accum_by_ved_year=accum_by_ved_year,
            ei_year_by_ved_kind_year=ei_year_by_ved_kind_year,
            display_years=display_years,
            current_year=current_year,
        )
        effective_coef_a = _resolve_effective_coef_a_for_ved(
            ved_id=ved_id,
            db_coef_a=coef_a,
            db_coef_x=db_coef_x,
            consumption_by_ved_year=consumption_by_ved_year,
            product_output_by_ved_year=product_output_by_ved_year,
            accum_by_ved_year=accum_by_ved_year,
            ei_year_by_ved_kind_year=ei_year_by_ved_kind_year,
            display_years=display_years,
            current_year=current_year,
        )
        for year, val in _compute_ved_plan_consumption_by_year(
            ved_id=ved_id,
            product_output_by_ved_year=product_output_by_ved_year,
            accum_by_ved_year=accum_by_ved_year,
            coef_a=effective_coef_a,
            coef_x=coef_x,
            display_years=display_years,
            current_year=current_year,
        ).items():
            summed[year] = summed.get(year, Decimal(0)) + val

    if not summed:
        return

    formula_key = REF_ROW_INDUSTRIAL_FORMULA_KEY_BY_KIND.get(REF_ROW_CONSUMPTION, "")
    if formula_key:
        consumption_row["formula_hint"] = ei_formula_text(formula_key)

    cells = consumption_row.setdefault("cells", {})
    for year, val in summed.items():
        cells[year] = val

    consumption_row["is_computed"] = True
    consumption_row["computed_years"] = frozenset(summed.keys())
    _refresh_reference_row_displays(
        consumption_row,
        display_years=display_years,
        rounding_digits=rounding_digits,
    )


def _quantize_ei_value(
    value: Decimal, rounding_digits: int, *, row_kind: str | None = None
) -> Decimal:
    """Согласовано с format_decimal_for_display и Numeric(25, 10) в БД."""
    if rounding_digits == 0:
        if row_kind in EI_INTENSITY_VALUE_ROW_KINDS:
            q = Decimal(10) ** -EI_INTENSITY_MAX_FRACTION_DIGITS
            return value.quantize(q, rounding=ROUND_HALF_UP)
        return value
    if rounding_digits == -1:
        return value.to_integral_value(rounding=ROUND_HALF_UP)
    q = Decimal(10) ** -rounding_digits
    return value.quantize(q, rounding=ROUND_HALF_UP)


def _ei_display_digits_for_row(
    row_kind: str | None, default_rounding_digits: int
) -> int:
    if row_kind == ROW_KIND_GRAPH_POINT:
        return EI_GRAPH_POINT_ROUNDING_DIGITS
    if (
        default_rounding_digits == 0
        and row_kind in EI_INTENSITY_VALUE_ROW_KINDS
    ):
        return EI_INTENSITY_MAX_FRACTION_DIGITS
    return default_rounding_digits


def _ei_pow(base: Decimal, exponent: Decimal) -> Decimal | None:
    if base <= 0:
        return None
    try:
        return Decimal(str(float(base) ** float(exponent)))
    except (ValueError, OverflowError, InvalidOperation):
        return None


def _compute_ei_intensity(
    consumption: Decimal | None, product_output: Decimal | None
) -> Decimal | None:
    if consumption is None or product_output is None:
        return None
    if product_output == 0:
        return None
    return (consumption / product_output) * EI_INTENSITY_UNIT_FACTOR


def _compute_consumption_from_intensity(
    intensity: Decimal | None,
    product_output: Decimal | None,
) -> Decimal | None:
    if intensity is None or product_output is None:
        return None
    if product_output == 0:
        return None
    return (intensity * product_output) / EI_INTENSITY_UNIT_FACTOR


def _compute_ei_calculated(
    coef_a: Decimal | None,
    coef_x: Decimal | None,
    accum: Decimal | None,
) -> Decimal | None:
    if coef_a is None or coef_x is None or accum is None:
        return None
    powered = _ei_pow(accum, coef_x)
    if powered is None:
        return None
    return coef_a * powered


def _excel_log(number: Decimal, base: Decimal) -> Decimal | None:
    """LOG(number; base) как в русской Excel: логарифм number по основанию base."""
    if number <= 0 or base <= 0 or base == 1:
        return None
    try:
        return Decimal(str(math.log(float(number), float(base))))
    except (ValueError, OverflowError, ZeroDivisionError):
        return None


def _compute_ei_graph_point(
    intensity_curr: Decimal | None,
    intensity_prev: Decimal | None,
    accum_curr: Decimal | None,
    accum_prev: Decimal | None,
) -> Decimal | None:
    """LOG(Электроёмкость_Y/Электроёмкость_{Y-1}; Накопленные_Y/Накопленные_{Y-1})."""
    if (
        intensity_curr is None
        or intensity_prev is None
        or accum_curr is None
        or accum_prev is None
    ):
        return None
    if intensity_prev == 0 or accum_prev == 0:
        return None
    intensity_ratio = intensity_curr / intensity_prev
    accum_ratio = accum_curr / accum_prev
    return _excel_log(intensity_ratio, accum_ratio)


def _set_row_cell_value(
    row: dict[str, Any],
    year: int,
    value: Decimal | None,
    *,
    display_years: list[int],
    rounding_digits: int,
    tooltip_value: Decimal | None = None,
) -> None:
    row_kind = row.get("row_kind")
    display_rd = _ei_display_digits_for_row(row_kind, rounding_digits)
    tt_source = tooltip_value if tooltip_value is not None else value
    row["cells"][year] = value
    row["cell_tooltips"][year] = _format_cell_tooltip(tt_source, row_kind=row_kind)
    row["cells_display"][year] = _format_cell_display(value, display_rd)


def _find_ei_row(rows: list[dict[str, Any]], row_kind: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("row_kind") == row_kind:
            return row
    return None


def _find_ref_row_in_list(
    reference_rows: list[dict[str, Any]], ref_kind: str
) -> dict[str, Any] | None:
    for row in reference_rows:
        if row.get("row_kind") == ref_kind:
            return row
    return None


def _attach_rf_section_scatter_chart(
    section: dict[str, Any],
    *,
    display_years: list[int],
    current_year: int | None,
    calculated_cells: dict[int, Decimal | None] | None = None,
) -> None:
    """График секции РФ: факт ≤ текущего года, расчётная кривая — с текущего."""
    ref_rows = section.get("reference_rows") or []
    accum_row = _find_ref_row_in_list(ref_rows, REF_ROW_ACCUM_FIXED_CAPITAL)
    if accum_row is None:
        accum_row = _find_ref_row_in_list(ref_rows, REF_ROW_ACCUM_MONETARY_INCOME)
    intensity_row = _find_ei_row(section.get("rows") or [], ROW_KIND_INTENSITY)
    if accum_row is None or intensity_row is None:
        return
    if section.get("is_population_section"):
        x_axis_label = "Накопленные денежные доходы населения, млн руб."
        y_axis_label = "Потребление ЭЭ на душу населения, кВт·ч/тыс. руб."
    else:
        x_axis_label = "Накопленные инвестиции, млн руб."
        y_axis_label = "Электроемкость, кВт·ч/тыс. руб."
    scatter_chart = build_rf_scatter_chart(
        accum_cells=accum_row.get("cells") or {},
        intensity_cells=intensity_row.get("cells") or {},
        calculated_cells=calculated_cells,
        display_years=display_years,
        current_year=current_year,
        x_axis_label=x_axis_label,
        y_axis_label=y_axis_label,
    )
    if scatter_chart is not None:
        section["scatter_chart"] = scatter_chart


def _compute_ved_calculated_cells_for_fd(
    *,
    ved_id: int,
    fd_id: int,
    version_id: int | None,
    ved: EconomicActivityType,
    refdata_ved_ids: frozenset[int],
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    ei_year_by_ved_kind_year: dict[tuple[int, str, int], Decimal | None],
    display_years: list[int],
    rounding_digits: int,
    current_year: int | None,
) -> dict[int, Decimal | None] | None:
    """Расчётная электроёмкость по ВЭД на ФО (A×I^X), для суммирования на уровне РФ."""
    _, has_ei_model_block, ei_row_kinds = _ei_row_kinds_for_ved(
        ved, refdata_ids=refdata_ved_ids
    )
    if not has_ei_model_block or ROW_KIND_CALCULATED not in ei_row_kinds:
        return None
    coef_a, db_coef_x = _load_fd_ei_coef_map(version_id=version_id, fd_id=fd_id).get(
        ved_id, (None, None)
    )
    row_defs = _build_row_defs()
    active_row_defs = [
        rd
        for rd in row_defs
        if rd["row_kind"] in ei_row_kinds or rd["row_kind"] == ROW_KIND_INTENSITY
    ]
    values_by_kind_year = {
        (rk, year): ei_year_by_ved_kind_year.get((ved_id, rk, year))
        for rk in ei_row_kinds | {ROW_KIND_INTENSITY}
        for year in display_years
    }
    ved_graph_point_db_years = _graph_point_db_years_from_fd_ved_map(
        ved_id, ei_year_by_ved_kind_year
    )
    section_rows = [
        _attach_row_cells(
            rd,
            values_by_kind_year,
            display_years,
            rounding_digits,
            graph_point_db_years=(
                ved_graph_point_db_years
                if rd["row_kind"] == ROW_KIND_GRAPH_POINT
                else None
            ),
        )
        for rd in active_row_defs
    ]
    _enrich_ei_computed_rows(
        section_rows,
        ved_id=ved_id,
        consumption_by_ved_year=consumption_by_ved_year,
        product_output_by_ved_year=product_output_by_ved_year,
        accum_by_ved_year=accum_by_ved_year,
        coef_a=coef_a,
        coef_x=db_coef_x,
        display_years=display_years,
        rounding_digits=rounding_digits,
        current_year=current_year,
    )
    calculated_row = _find_ei_row(section_rows, ROW_KIND_CALCULATED)
    if calculated_row is None:
        return None
    return dict(calculated_row.get("cells") or {})


def _compute_industrial_calculated_cells_for_fd(
    *,
    component_ved_ids: list[int],
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    display_years: list[int],
    rounding_digits: int,
    current_year: int | None,
) -> dict[int, Decimal | None] | None:
    synthetic_ved_id = 0
    cons_cells = _sum_values_by_ved_year_for_veds(
        component_ved_ids, consumption_by_ved_year, display_years
    )
    prod_cells = _sum_values_by_ved_year_for_veds(
        component_ved_ids, product_output_by_ved_year, display_years
    )
    accum_cells = _sum_values_by_ved_year_for_veds(
        component_ved_ids, accum_by_ved_year, display_years
    )
    row_defs = _build_row_defs()
    active_row_defs = [
        rd
        for rd in row_defs
        if rd["row_kind"] in EI_MODEL_ROW_KINDS | {ROW_KIND_INTENSITY}
    ]
    section_rows = [
        _attach_row_cells(
            rd,
            {(rd["row_kind"], year): None for year in display_years},
            display_years,
            rounding_digits,
        )
        for rd in active_row_defs
    ]
    _enrich_ei_computed_rows(
        section_rows,
        ved_id=synthetic_ved_id,
        consumption_by_ved_year={
            (synthetic_ved_id, year): cons_cells.get(year) for year in display_years
        },
        product_output_by_ved_year={
            (synthetic_ved_id, year): prod_cells.get(year) for year in display_years
        },
        accum_by_ved_year={
            (synthetic_ved_id, year): accum_cells.get(year) for year in display_years
        },
        coef_a=None,
        coef_x=None,
        display_years=display_years,
        rounding_digits=rounding_digits,
        current_year=current_year,
    )
    calculated_row = _find_ei_row(section_rows, ROW_KIND_CALCULATED)
    if calculated_row is None:
        return None
    return dict(calculated_row.get("cells") or {})


def _compute_population_calculated_cells_for_fd(
    *,
    fd_id: int,
    version_id: int | None,
    ved_types: list[EconomicActivityType],
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    display_years: list[int],
    rounding_digits: int,
    current_year: int | None,
) -> dict[int, Decimal | None] | None:
    household_ved = _find_ved_by_target(ved_types, HOUSEHOLD_VED_TARGET)
    household_ved_id = int(household_ved.id) if household_ved is not None else None
    household_by_year = {
        year: (
            consumption_by_ved_year.get((household_ved_id, year))
            if household_ved_id is not None
            else None
        )
        for year in display_years
    }
    population_by_year = _load_population_by_fd_year(version_id=version_id, fd_id=fd_id)
    accum_income_by_year = _load_accum_monetary_income_by_fd_year(
        version_id=version_id, fd_id=fd_id
    )
    pop_year_values = _load_population_year_values_map(version_id=version_id, fd_id=fd_id)
    pop_graph_point_db_years = _graph_point_db_years_from_kind_year_map(pop_year_values)
    coef_a, coef_x = _load_population_coef(version_id=version_id, fd_id=fd_id)
    section_rows = [
        _attach_row_cells(
            rd,
            pop_year_values,
            display_years,
            rounding_digits,
            graph_point_db_years=(
                pop_graph_point_db_years
                if rd["row_kind"] == ROW_KIND_GRAPH_POINT
                else None
            ),
        )
        for rd in _build_population_row_defs()
    ]
    _enrich_population_computed_rows(
        section_rows,
        household_consumption_by_year=household_by_year,
        population_by_year=population_by_year,
        accum_income_by_year=accum_income_by_year,
        coef_a=coef_a,
        coef_x=coef_x,
        display_years=display_years,
        rounding_digits=rounding_digits,
        current_year=current_year,
    )
    calculated_row = _find_ei_row(section_rows, ROW_KIND_CALCULATED)
    if calculated_row is None:
        return None
    return dict(calculated_row.get("cells") or {})


def _compute_fd_territory_summary_intensity_cells(
    *,
    fd_id: int,
    version_id: int | None,
    ved_types: list[EconomicActivityType],
    display_years: list[int],
    rounding_digits: int,
    current_year: int | None,
    coeff_base_year: int,
    year_features: dict[int, str] | None = None,
) -> dict[int, Decimal | None]:
    """Электроёмкость сводного блока ФО (для суммирования на графике РФ)."""
    fd_filter = FederalDistrictProductOutputParameter.id_federal_district == fd_id
    product_by_ved = _load_product_output_values_map(
        version_id=version_id,
        model=FederalDistrictProductOutputParameter,
        territory_filter=fd_filter,
    )
    consumption_by_ved = _load_ved_consumption_values_map(
        version_id=version_id,
        model=FederalDistrictEATConsumptionParameter,
        territory_filter=FederalDistrictEATConsumptionParameter.id_federal_district
        == fd_id,
    )
    accum_by_ved = _load_accum_fixed_capital_values_map(
        version_id=version_id,
        model=FederalDistrictAccumFixedCapitalParameter,
        territory_filter=FederalDistrictAccumFixedCapitalParameter.id_federal_district
        == fd_id,
    )
    coef_by_ved = _load_fd_ei_coef_map(version_id=version_id, fd_id=fd_id)
    price_year = _resolve_price_year_for_ref_labels(
        version_id, fd_id, coeff_base_year
    )
    summary = _build_fd_territory_summary(
        fd_id=fd_id,
        version_id=version_id,
        ved_types=ved_types,
        product_output_by_ved_year=product_by_ved,
        consumption_by_ved_year=consumption_by_ved,
        accum_by_ved_year=accum_by_ved,
        coef_by_ved=coef_by_ved,
        display_years=display_years,
        rounding_digits=rounding_digits,
        price_year=price_year,
        current_year=current_year,
        year_features=year_features,
    )
    if summary is None:
        return {year: None for year in display_years}
    intensity_row = _find_ei_row(summary.get("rows") or [], ROW_KIND_INTENSITY)
    if intensity_row is None:
        return {year: None for year in display_years}
    return dict(intensity_row.get("cells") or {})


def _aggregate_rf_summary_chart_intensity_cells(
    *,
    version_id: int | None,
    ved_types: list[EconomicActivityType],
    display_years: list[int],
    rounding_digits: int,
    current_year: int | None,
    coeff_base_year: int,
    fd_filter_ids: frozenset[int],
    year_features: dict[int, str] | None = None,
) -> dict[int, Decimal | None]:
    """Сумма сводных электроёмкостей ФО для расчётной кривой графика РФ."""
    parts: list[dict[int, Decimal | None]] = []
    for fd in _federal_districts_for_page():
        if fd_filter_ids and fd.id not in fd_filter_ids:
            continue
        parts.append(
            _compute_fd_territory_summary_intensity_cells(
                fd_id=fd.id,
                version_id=version_id,
                ved_types=ved_types,
                display_years=display_years,
                rounding_digits=rounding_digits,
                current_year=current_year,
                coeff_base_year=coeff_base_year,
                year_features=year_features,
            )
        )
    if not parts:
        return {year: None for year in display_years}
    return _sum_cell_dicts(*parts, display_years=display_years)


def _natural_ln(value: Decimal) -> Decimal | None:
    if value <= 0:
        return None
    try:
        return Decimal(str(math.log(float(value))))
    except (ValueError, OverflowError):
        return None


def _natural_exp(value: Decimal) -> Decimal | None:
    try:
        return Decimal(str(math.exp(float(value))))
    except (ValueError, OverflowError):
        return None


def _compute_coef_x_from_graph_points(
    graph_point_row: dict[str, Any] | None,
    *,
    current_year: int | None,
) -> Decimal | None:
    """Среднее по «Характерные точки графика» за 2010…текущий год (пустые ячейки пропускаются)."""
    if graph_point_row is None or current_year is None:
        return None
    if current_year < EI_COEFFICIENT_X_AVG_START_YEAR:
        return None
    cells = graph_point_row.get("cells") or {}
    values: list[Decimal] = []
    for year in range(EI_COEFFICIENT_X_AVG_START_YEAR, current_year + 1):
        val = cells.get(year)
        if val is not None:
            values.append(val)
    if not values:
        return None
    return sum(values) / Decimal(len(values))


def _compute_coef_a_from_intensity(
    intensity_row: dict[str, Any] | None,
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    *,
    ved_id: int,
    coef_x: Decimal | None,
    current_year: int | None,
) -> Decimal | None:
    """A = exp( average( ln(Yi) - X * ln(Ii) ) ) за 2010…текущий год."""
    if intensity_row is None or coef_x is None or current_year is None:
        return None
    if current_year < EI_COEFFICIENT_X_AVG_START_YEAR:
        return None
    cells = intensity_row.get("cells") or {}
    terms: list[Decimal] = []
    for year in range(EI_COEFFICIENT_X_AVG_START_YEAR, current_year + 1):
        yi = cells.get(year)
        ii = accum_by_ved_year.get((ved_id, year))
        if yi is None or ii is None:
            continue
        ln_y = _natural_ln(yi)
        ln_i = _natural_ln(ii)
        if ln_y is None or ln_i is None:
            continue
        terms.append(ln_y - coef_x * ln_i)
    if not terms:
        return None
    return _natural_exp(sum(terms) / Decimal(len(terms)))


def _force_compute_graph_points_for_rows(
    rows: list[dict[str, Any]],
    *,
    ved_id: int,
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    display_years: list[int],
    rounding_digits: int,
    current_year: int | None,
) -> list[tuple[int, Decimal]]:
    """Рассчитать «Характерные точки графика» по формуле для всех лет ≤ текущего."""
    graph_point_row = _find_ei_row(rows, ROW_KIND_GRAPH_POINT)
    if graph_point_row is None:
        return []
    computed_years = _ei_years_through_current(display_years, current_year)
    written: list[tuple[int, Decimal]] = []
    for year in computed_years:
        consumption = consumption_by_ved_year.get((ved_id, year))
        product_output = product_output_by_ved_year.get((ved_id, year))
        accum = accum_by_ved_year.get((ved_id, year))
        intensity_curr = _compute_ei_intensity(consumption, product_output)
        intensity_prev = _compute_ei_intensity(
            consumption_by_ved_year.get((ved_id, year - 1)),
            product_output_by_ved_year.get((ved_id, year - 1)),
        )
        raw_gp = _compute_ei_graph_point(
            intensity_curr,
            intensity_prev,
            accum,
            accum_by_ved_year.get((ved_id, year - 1)),
        )
        if raw_gp is None:
            continue
        _set_row_cell_value(
            graph_point_row,
            year,
            raw_gp,
            display_years=display_years,
            rounding_digits=rounding_digits,
        )
        written.append((year, raw_gp))
    return written


def _enrich_ei_computed_rows(
    rows: list[dict[str, Any]],
    *,
    ved_id: int,
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    coef_a: Decimal | None,
    coef_x: Decimal | None,
    display_years: list[int],
    rounding_digits: int,
    current_year: int | None,
    auto_fill_graph_points: bool = True,
) -> tuple[Decimal | None, Decimal | None]:
    computed_years = _ei_years_through_current(display_years, current_year)
    intensity_row = _find_ei_row(rows, ROW_KIND_INTENSITY)
    graph_point_row = _find_ei_row(rows, ROW_KIND_GRAPH_POINT)
    calculated_row = _find_ei_row(rows, ROW_KIND_CALCULATED)
    delta_row = _find_ei_row(rows, ROW_KIND_DELTA)

    for year in computed_years:
        consumption = consumption_by_ved_year.get((ved_id, year))
        product_output = product_output_by_ved_year.get((ved_id, year))
        accum = accum_by_ved_year.get((ved_id, year))
        intensity_curr = _compute_ei_intensity(consumption, product_output)
        intensity_prev = _compute_ei_intensity(
            consumption_by_ved_year.get((ved_id, year - 1)),
            product_output_by_ved_year.get((ved_id, year - 1)),
        )

        if auto_fill_graph_points and _should_autofill_graph_point_cell(
            graph_point_row, year
        ):
            raw_gp = _compute_ei_graph_point(
                intensity_curr,
                intensity_prev,
                accum,
                accum_by_ved_year.get((ved_id, year - 1)),
            )
            if raw_gp is not None:
                _set_row_cell_value(
                    graph_point_row,
                    year,
                    raw_gp,
                    display_years=display_years,
                    rounding_digits=rounding_digits,
                )

        if intensity_row is not None:
            raw = _compute_ei_intensity(consumption, product_output)
            if raw is not None:
                _set_row_cell_value(
                    intensity_row,
                    year,
                    raw,
                    display_years=display_years,
                    rounding_digits=rounding_digits,
                )

    effective_coef_x = _compute_coef_x_from_graph_points(
        graph_point_row, current_year=current_year
    )
    if effective_coef_x is None:
        effective_coef_x = coef_x

    coef_a_computed = _compute_coef_a_from_intensity(
        intensity_row,
        accum_by_ved_year,
        ved_id=ved_id,
        coef_x=effective_coef_x,
        current_year=current_year,
    )
    effective_coef_a = _effective_coef_a(coef_a, coef_a_computed)

    calculated_years = _ei_years_all_display(display_years)
    for year in calculated_years:
        accum = accum_by_ved_year.get((ved_id, year))
        if calculated_row is not None:
            raw = _compute_ei_calculated(
                effective_coef_a, effective_coef_x, accum
            )
            if raw is not None:
                _set_row_cell_value(
                    calculated_row,
                    year,
                    raw,
                    display_years=display_years,
                    rounding_digits=rounding_digits,
                )

    if intensity_row is not None:
        intensity_row["computed_years"] = computed_years
    if calculated_row is not None:
        calculated_row["computed_years"] = calculated_years

    if delta_row is not None:
        delta_computed_years: set[int] = set()
        for year in computed_years:
            intensity_raw = _compute_ei_intensity(
                consumption_by_ved_year.get((ved_id, year)),
                product_output_by_ved_year.get((ved_id, year)),
            )
            calculated_raw = _compute_ei_calculated(
                effective_coef_a,
                effective_coef_x,
                accum_by_ved_year.get((ved_id, year)),
            )
            if intensity_raw is None or calculated_raw is None:
                continue
            delta_val = intensity_raw - calculated_raw
            _set_row_cell_value(
                delta_row,
                year,
                delta_val,
                display_years=display_years,
                rounding_digits=rounding_digits,
            )
            delta_computed_years.add(year)
        if delta_computed_years:
            delta_row["computed_years"] = frozenset(delta_computed_years)

    return effective_coef_x, coef_a_computed


def _compute_pop_per_capita_consumption(
    household_consumption: Decimal | None,
    population: Decimal | None,
) -> Decimal | None:
    if household_consumption is None or population is None:
        return None
    if population == 0:
        return None
    return household_consumption / population


def _compute_household_from_population_and_per_capita(
    population: Decimal | None,
    per_capita_calculated: Decimal | None,
) -> Decimal | None:
    if population is None or per_capita_calculated is None:
        return None
    return population * per_capita_calculated


def _enrich_population_household_plan_years(
    reference_rows: list[dict[str, Any]],
    *,
    section_rows: list[dict[str, Any]],
    population_by_year: dict[int, Decimal | None],
    display_years: list[int],
    rounding_digits: int,
    current_year: int | None,
) -> None:
    """Потребление в домашних хозяйствах для годов «план»: численность × расчёт на душу."""
    household_row = next(
        (r for r in reference_rows if r.get("row_kind") == REF_ROW_HOUSEHOLD_CONSUMPTION),
        None,
    )
    if household_row is None:
        return

    calculated_row = _find_ei_row(section_rows, ROW_KIND_CALCULATED)
    if calculated_row is None:
        return

    plan_years = _ei_plan_years(display_years, current_year)
    if not plan_years:
        return

    calculated_cells = calculated_row.get("cells") or {}
    plan_cells: dict[int, Decimal] = {}
    for year in plan_years:
        val = _compute_household_from_population_and_per_capita(
            population_by_year.get(year),
            calculated_cells.get(year),
        )
        if val is not None:
            plan_cells[year] = val

    if not plan_cells:
        return

    formula_key = POP_REF_ROW_PLAN_FORMULA_KEY_BY_KIND.get(
        REF_ROW_HOUSEHOLD_CONSUMPTION, ""
    )
    if formula_key:
        household_row["formula_hint"] = ei_formula_text(formula_key)

    cells = household_row.setdefault("cells", {})
    for year, val in plan_cells.items():
        cells[year] = val

    household_row["is_computed"] = True
    existing = household_row.get("computed_years")
    if existing:
        household_row["computed_years"] = frozenset(existing) | frozenset(plan_cells.keys())
    else:
        household_row["computed_years"] = frozenset(plan_cells.keys())
    _refresh_reference_row_displays(
        household_row,
        display_years=display_years,
        rounding_digits=rounding_digits,
    )


def _load_population_year_values_map(
    *,
    version_id: int | None,
    fd_id: int,
) -> dict[tuple[str, int], Decimal | None]:
    from app.common.services.economics_fd_data_cache import get_fd_pop_ei_year_values

    return get_fd_pop_ei_year_values(
        version_id=version_id,
        model=FederalDistrictPopulationConsumptionYearParameter,
        fd_id=fd_id,
    )


def _load_population_coef(
    *,
    version_id: int | None,
    fd_id: int,
) -> tuple[Decimal | None, Decimal | None]:
    from app.common.services.economics_fd_data_cache import get_fd_pop_ei_coef

    return get_fd_pop_ei_coef(
        version_id=version_id,
        model=FederalDistrictPopulationConsumptionCoefficient,
        fd_id=fd_id,
    )


def _build_population_row_defs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind in ROW_KINDS:
        formula_key = POP_ROW_FORMULA_KEY_BY_KIND.get(kind, "")
        row_css = ""
        if kind == ROW_KIND_INTENSITY:
            row_css = "lt-ei-row-intensity"
        elif kind == ROW_KIND_GRAPH_POINT:
            row_css = "lt-ei-row-graph-point"
        elif kind in (ROW_KIND_CALCULATED, ROW_KIND_DELTA):
            row_css = "table-warning"
        rows.append(
            {
                "row_kind": kind,
                "row_label": POP_ROW_LABEL_BY_KIND.get(kind, kind),
                "row_css": row_css,
                "formula_hint": ei_formula_text(formula_key) if formula_key else "",
                "is_computed": False,
                "is_formula_computed": kind in EI_FORMULA_EDITABLE_ROW_KINDS,
                "allows_manual_edit": kind in EI_FORMULA_EDITABLE_ROW_KINDS,
            }
        )
    return rows


def _build_population_reference_row(
    *,
    ref_kind: str,
    cells_by_year: dict[int, Decimal | None],
    display_years: list[int],
    rounding_digits: int,
    is_computed: bool = False,
) -> dict[str, Any]:
    cells = {year: cells_by_year.get(year) for year in display_years}
    formula_key = POP_REF_ROW_FORMULA_KEY_BY_KIND.get(ref_kind, "")
    return {
        "row_kind": ref_kind,
        "row_label": POP_REF_ROW_LABEL_BY_KIND.get(ref_kind, ref_kind),
        "unit_label": POP_REF_ROW_UNIT_BY_KIND.get(ref_kind, ""),
        "row_css": POP_REF_ROW_CSS_BY_KIND.get(ref_kind, ""),
        "is_readonly": True,
        "is_computed": is_computed,
        "source_endpoint": POP_REF_ROW_SOURCE_ENDPOINT.get(ref_kind, ""),
        "source_page_title": POP_REF_ROW_SOURCE_PAGE_TITLE.get(ref_kind, ""),
        "formula_hint": ei_formula_text(formula_key) if formula_key else "",
        "cells": cells,
        "cell_tooltips": {
            year: _format_full_numeric_tooltip(cells.get(year)) for year in display_years
        },
        "cells_display": {
            year: _format_cell_display(cells.get(year), rounding_digits)
            for year in display_years
        },
    }


def _enrich_population_computed_rows(
    rows: list[dict[str, Any]],
    *,
    household_consumption_by_year: dict[int, Decimal | None],
    population_by_year: dict[int, Decimal | None],
    accum_income_by_year: dict[int, Decimal | None],
    coef_a: Decimal | None,
    coef_x: Decimal | None,
    display_years: list[int],
    rounding_digits: int,
    current_year: int | None,
    auto_fill_graph_points: bool = True,
) -> tuple[Decimal | None, Decimal | None]:
    computed_years = _ei_years_through_current(display_years, current_year)
    intensity_row = _find_ei_row(rows, ROW_KIND_INTENSITY)
    graph_point_row = _find_ei_row(rows, ROW_KIND_GRAPH_POINT)
    calculated_row = _find_ei_row(rows, ROW_KIND_CALCULATED)
    delta_row = _find_ei_row(rows, ROW_KIND_DELTA)

    for year in computed_years:
        household = household_consumption_by_year.get(year)
        population = population_by_year.get(year)
        accum = accum_income_by_year.get(year)
        per_capita_curr = _compute_pop_per_capita_consumption(household, population)
        per_capita_prev = _compute_pop_per_capita_consumption(
            household_consumption_by_year.get(year - 1),
            population_by_year.get(year - 1),
        )

        if auto_fill_graph_points and _should_autofill_graph_point_cell(
            graph_point_row, year
        ):
            raw_gp = _compute_ei_graph_point(
                per_capita_curr,
                per_capita_prev,
                accum,
                accum_income_by_year.get(year - 1),
            )
            if raw_gp is not None:
                _set_row_cell_value(
                    graph_point_row,
                    year,
                    raw_gp,
                    display_years=display_years,
                    rounding_digits=rounding_digits,
                )

        if intensity_row is not None and per_capita_curr is not None:
            _set_row_cell_value(
                intensity_row,
                year,
                per_capita_curr,
                display_years=display_years,
                rounding_digits=rounding_digits,
            )

    effective_coef_x = _compute_coef_x_from_graph_points(
        graph_point_row, current_year=current_year
    )
    if effective_coef_x is None:
        effective_coef_x = coef_x

    accum_by_synthetic = {
        (0, year): accum_income_by_year.get(year) for year in display_years
    }
    coef_a_computed = _compute_coef_a_from_intensity(
        intensity_row,
        accum_by_synthetic,
        ved_id=0,
        coef_x=effective_coef_x,
        current_year=current_year,
    )
    effective_coef_a = _effective_coef_a(coef_a, coef_a_computed)

    calculated_years = _ei_years_all_display(display_years)
    for year in calculated_years:
        accum = accum_income_by_year.get(year)
        if calculated_row is not None:
            raw = _compute_ei_calculated(effective_coef_a, effective_coef_x, accum)
            if raw is not None:
                _set_row_cell_value(
                    calculated_row,
                    year,
                    raw,
                    display_years=display_years,
                    rounding_digits=rounding_digits,
                )

    if intensity_row is not None:
        intensity_row["computed_years"] = computed_years
    if calculated_row is not None:
        calculated_row["computed_years"] = calculated_years

    if delta_row is not None:
        delta_computed_years: set[int] = set()
        for year in computed_years:
            per_capita = _compute_pop_per_capita_consumption(
                household_consumption_by_year.get(year),
                population_by_year.get(year),
            )
            calculated_raw = _compute_ei_calculated(
                effective_coef_a,
                effective_coef_x,
                accum_income_by_year.get(year),
            )
            if per_capita is None or calculated_raw is None:
                continue
            delta_val = calculated_raw - per_capita
            _set_row_cell_value(
                delta_row,
                year,
                delta_val,
                display_years=display_years,
                rounding_digits=rounding_digits,
            )
            delta_computed_years.add(year)
        if delta_computed_years:
            delta_row["computed_years"] = frozenset(delta_computed_years)

    return effective_coef_x, coef_a_computed


def _force_compute_population_graph_points_for_rows(
    rows: list[dict[str, Any]],
    *,
    household_consumption_by_year: dict[int, Decimal | None],
    population_by_year: dict[int, Decimal | None],
    accum_income_by_year: dict[int, Decimal | None],
    display_years: list[int],
    rounding_digits: int,
    current_year: int | None,
) -> list[tuple[int, Decimal]]:
    graph_point_row = _find_ei_row(rows, ROW_KIND_GRAPH_POINT)
    if graph_point_row is None:
        return []
    computed_years = _ei_years_through_current(display_years, current_year)
    written: list[tuple[int, Decimal]] = []
    for year in computed_years:
        per_capita_curr = _compute_pop_per_capita_consumption(
            household_consumption_by_year.get(year),
            population_by_year.get(year),
        )
        per_capita_prev = _compute_pop_per_capita_consumption(
            household_consumption_by_year.get(year - 1),
            population_by_year.get(year - 1),
        )
        raw_gp = _compute_ei_graph_point(
            per_capita_curr,
            per_capita_prev,
            accum_income_by_year.get(year),
            accum_income_by_year.get(year - 1),
        )
        if raw_gp is None:
            continue
        _set_row_cell_value(
            graph_point_row,
            year,
            raw_gp,
            display_years=display_years,
            rounding_digits=rounding_digits,
        )
        written.append((year, raw_gp))
    return written


def _compute_household_consumption_by_year_for_fd(
    *,
    fd_id: int,
    version_id: int | None,
    ved_types: list[EconomicActivityType],
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    display_years: list[int],
    rounding_digits: int,
    current_year: int | None,
) -> dict[int, Decimal | None]:
    """Потребление в домашних хозяйствах по ФО (факт из БД + прогноз для годов «план»)."""
    household_ved = _find_ved_by_target(ved_types, HOUSEHOLD_VED_TARGET)
    household_ved_id = int(household_ved.id) if household_ved is not None else None
    household_by_year: dict[int, Decimal | None] = {
        year: (
            consumption_by_ved_year.get((household_ved_id, year))
            if household_ved_id is not None
            else None
        )
        for year in display_years
    }
    if household_ved_id is None:
        return household_by_year

    population_by_year = _load_population_by_fd_year(version_id=version_id, fd_id=fd_id)
    accum_income_by_year = _load_accum_monetary_income_by_fd_year(
        version_id=version_id, fd_id=fd_id
    )
    pop_year_values = _load_population_year_values_map(version_id=version_id, fd_id=fd_id)
    pop_graph_point_db_years = _graph_point_db_years_from_kind_year_map(pop_year_values)
    coef_a, coef_x = _load_population_coef(version_id=version_id, fd_id=fd_id)
    row_defs = _build_population_row_defs()
    section_rows = [
        _attach_row_cells(
            rd,
            pop_year_values,
            display_years,
            rounding_digits,
            graph_point_db_years=(
                pop_graph_point_db_years
                if rd["row_kind"] == ROW_KIND_GRAPH_POINT
                else None
            ),
        )
        for rd in row_defs
    ]
    _enrich_population_computed_rows(
        section_rows,
        household_consumption_by_year=household_by_year,
        population_by_year=population_by_year,
        accum_income_by_year=accum_income_by_year,
        coef_a=coef_a,
        coef_x=coef_x,
        display_years=display_years,
        rounding_digits=rounding_digits,
        current_year=current_year,
    )
    household_row = {
        "row_kind": REF_ROW_HOUSEHOLD_CONSUMPTION,
        "cells": dict(household_by_year),
    }
    _enrich_population_household_plan_years(
        [household_row],
        section_rows=section_rows,
        population_by_year=population_by_year,
        display_years=display_years,
        rounding_digits=rounding_digits,
        current_year=current_year,
    )
    return household_row["cells"]


def _build_population_section_for_fd(
    *,
    fd_id: int,
    version_id: int | None,
    ved_types: list[EconomicActivityType],
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    display_years: list[int],
    rounding_digits: int,
    current_year: int | None,
) -> dict[str, Any]:
    household_ved = _find_ved_by_target(ved_types, HOUSEHOLD_VED_TARGET)
    household_ved_id = int(household_ved.id) if household_ved is not None else None

    population_by_year = _load_population_by_fd_year(version_id=version_id, fd_id=fd_id)
    accum_income_by_year = _load_accum_monetary_income_by_fd_year(
        version_id=version_id, fd_id=fd_id
    )
    household_by_year = {
        year: (
            consumption_by_ved_year.get((household_ved_id, year))
            if household_ved_id is not None
            else None
        )
        for year in display_years
    }

    reference_rows = [
        _build_population_reference_row(
            ref_kind=REF_ROW_POPULATION,
            cells_by_year=population_by_year,
            display_years=display_years,
            rounding_digits=rounding_digits,
        ),
        _build_population_reference_row(
            ref_kind=REF_ROW_HOUSEHOLD_CONSUMPTION,
            cells_by_year=household_by_year,
            display_years=display_years,
            rounding_digits=rounding_digits,
            is_computed=True,
        ),
        _build_population_reference_row(
            ref_kind=REF_ROW_ACCUM_MONETARY_INCOME,
            cells_by_year=accum_income_by_year,
            display_years=display_years,
            rounding_digits=rounding_digits,
        ),
    ]

    pop_year_values = _load_population_year_values_map(version_id=version_id, fd_id=fd_id)
    pop_graph_point_db_years = _graph_point_db_years_from_kind_year_map(pop_year_values)
    coef_a, coef_x = _load_population_coef(version_id=version_id, fd_id=fd_id)
    row_defs = _build_population_row_defs()
    section_rows = [
        _attach_row_cells(
            rd,
            pop_year_values,
            display_years,
            rounding_digits,
            graph_point_db_years=(
                pop_graph_point_db_years
                if rd["row_kind"] == ROW_KIND_GRAPH_POINT
                else None
            ),
        )
        for rd in row_defs
    ]
    computed_x, computed_a = _enrich_population_computed_rows(
        section_rows,
        household_consumption_by_year=household_by_year,
        population_by_year=population_by_year,
        accum_income_by_year=accum_income_by_year,
        coef_a=coef_a,
        coef_x=coef_x,
        display_years=display_years,
        rounding_digits=rounding_digits,
        current_year=current_year,
    )
    _enrich_population_household_plan_years(
        reference_rows,
        section_rows=section_rows,
        population_by_year=population_by_year,
        display_years=display_years,
        rounding_digits=rounding_digits,
        current_year=current_year,
    )

    section: dict[str, Any] = {
        "ved_id": POPULATION_SECTION_MARKER,
        "ved_name": POPULATION_SECTION_LABEL,
        "is_population_section": True,
        "has_ei_block": True,
        "has_ei_intensity_block": True,
        "has_ei_model_block": True,
        "reference_rows": reference_rows,
        "rows": section_rows,
        "unit_label": "кВт.ч./тыс.руб.",
        "formula_hints": {
            "coefficient_a": ei_formula_text("ei_pop_coefficient_a"),
            "coefficient_a_computed": ei_formula_text("ei_pop_coefficient_a_computed"),
            "coefficient_x": ei_formula_text("ei_pop_coefficient_x"),
        },
    }
    section.update(
        _coef_display_fields(
            coef_a,
            computed_x,
            rounding_digits,
            coef_a_computed=computed_a,
        )
    )
    scatter_chart = build_ei_section_scatter_chart(
        section,
        display_years=display_years,
        current_year=current_year,
    )
    if scatter_chart is not None:
        section["scatter_chart"] = scatter_chart
    return section


def _ved_section_display_name(ved: EconomicActivityType) -> str | None:
    """Заголовок секции ВЭД на странице электроёмкости (поле name_2 справочника /refdata/ved)."""
    name_2 = (getattr(ved, "name_2", None) or "").strip()
    return name_2 or None


def _refdata_ved_types_for_version(version_id: int | None) -> list[EconomicActivityType]:
    """ВЭД из справочника /refdata/ved (id > 0, версия БД, display_order)."""
    from app.common.services.database_version_filter import (
        apply_version_filter,
        filter_by_explicit_db_version,
    )

    q = EconomicActivityType.query.filter(
        EconomicActivityType.id.isnot(None),
        EconomicActivityType.id > 0,
    )
    if version_id is not None:
        q = filter_by_explicit_db_version(q, EconomicActivityType, version_id)
    else:
        q = apply_version_filter(q, EconomicActivityType)
    q = q.order_by(
        (EconomicActivityType.display_order.is_(None)),
        EconomicActivityType.display_order.asc(),
    )
    return [v for v in q.all() if v.name]


def _refdata_ved_ids(version_id: int | None) -> frozenset[int]:
    return frozenset(int(v.id) for v in _refdata_ved_types_for_version(version_id))


def _ei_row_kinds_for_ved(
    ved: EconomicActivityType, *, refdata_ids: frozenset[int]
) -> tuple[bool, bool, frozenset[str]]:
    """(intensity_block, model_block, row_kinds) для секции ВЭД на странице электроёмкости."""
    if _is_total_consumption_ved(ved):
        return False, False, frozenset()
    intensity_block = True
    model_block = int(ved.id) in refdata_ids
    kinds: list[str] = []
    if intensity_block:
        kinds.append(ROW_KIND_INTENSITY)
    if model_block:
        kinds.extend(sorted(EI_MODEL_ROW_KINDS, key=ROW_KINDS.index))
    return intensity_block, model_block, frozenset(kinds)


def _find_total_ved_id(ved_types: list[EconomicActivityType]) -> int | None:
    target_n = _normalize_label(TOTAL_VED_NAME)
    for ved in ved_types:
        if ved.name and _normalize_label(ved.name) == target_n:
            return int(ved.id)
    return None


def _enrich_rf_ei_block(
    block: dict[str, Any],
    *,
    version_id: int | None,
    ved_types: list[EconomicActivityType],
    display_years: list[int],
    rounding_digits: int,
    current_year: int | None,
) -> None:
    total_ved_id = _find_total_ved_id(ved_types)
    if total_ved_id is None:
        return
    consumption_by_ved = _load_ved_consumption_values_map(
        version_id=version_id,
        model=RussiaFederationConsumptionParameter,
    )
    product_by_ved = _load_product_output_values_map(
        version_id=version_id,
        model=RussiaFederationProductOutputParameter,
    )
    accum_by_ved = _load_accum_fixed_capital_values_map(
        version_id=version_id,
        model=RussiaFederationAccumFixedCapitalParameter,
    )
    computed_x, computed_a = _enrich_ei_computed_rows(
        block.get("rows") or [],
        ved_id=total_ved_id,
        consumption_by_ved_year=consumption_by_ved,
        product_output_by_ved_year=product_by_ved,
        accum_by_ved_year=accum_by_ved,
        coef_a=block.get("coefficient_a"),
        coef_x=block.get("coefficient_x"),
        display_years=display_years,
        rounding_digits=rounding_digits,
        current_year=current_year,
    )
    block.update(
        _coef_display_fields(
            block.get("coefficient_a"),
            computed_x if computed_x is not None else block.get("coefficient_x"),
            rounding_digits,
            coef_a_computed=computed_a,
        )
    )


def _parse_decimal(raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    s = str(raw).strip().replace("\u00a0", "").replace(" ", "")
    if not s or s in ("—", "-", "–"):
        return None
    s = s.replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _is_total_consumption_ved(ved: EconomicActivityType) -> bool:
    return _normalize_label(ved.name) == _normalize_label(TOTAL_VED_NAME)


def _load_fd_ei_year_values_map(
    *,
    version_id: int | None,
    fd_id: int,
) -> dict[tuple[int, str, int], Decimal | None]:
    from app.common.services.economics_fd_data_cache import get_fd_ei_year_values

    return get_fd_ei_year_values(
        version_id=version_id,
        model=FederalDistrictElectricalIntensityYearParameter,
        fd_id=fd_id,
    )


def _load_fd_ei_coef_map(
    *,
    version_id: int | None,
    fd_id: int,
) -> dict[int, tuple[Decimal | None, Decimal | None]]:
    from app.common.services.economics_fd_data_cache import get_fd_ei_coef_values

    return get_fd_ei_coef_values(
        version_id=version_id,
        model=FederalDistrictElectricalIntensityCoefficient,
        fd_id=fd_id,
    )


def _coef_display_fields(
    coef_a_manual: Decimal | None,
    coef_x: Decimal | None,
    rounding_digits: int,
    *,
    coef_a_computed: Decimal | None = None,
) -> dict[str, Any]:
    return {
        "coefficient_a": coef_a_manual,
        "coefficient_a_manual": coef_a_manual,
        "coefficient_a_computed": coef_a_computed,
        "coefficient_x": coef_x,
        "coefficient_a_manual_display": _format_cell_display(
            coef_a_manual, rounding_digits
        ),
        "coefficient_a_computed_display": _format_cell_display(
            coef_a_computed, EI_COEFFICIENT_A_COMPUTED_DISPLAY_ROUNDING_DIGITS
        ),
        "coefficient_x_display": _format_cell_display(
            coef_x, EI_COEFFICIENT_X_DISPLAY_ROUNDING_DIGITS
        ),
        "coefficient_a_manual_tooltip": _format_full_numeric_tooltip(coef_a_manual),
        "coefficient_a_computed_tooltip": _format_full_numeric_tooltip(coef_a_computed),
        "coefficient_x_tooltip": _format_full_numeric_tooltip(coef_x),
        # Обратная совместимость (экспорт и пр.): A — значение из БД.
        "coefficient_a_display": _format_cell_display(coef_a_manual, rounding_digits),
        "coefficient_a_tooltip": _format_full_numeric_tooltip(coef_a_manual),
    }


def _load_year_values_map(
    *,
    version_id: int | None,
    model: type,
    territory_filter: Any | None = None,
) -> dict[tuple[str, int], Decimal | None]:
    q = model.query
    if version_id is not None:
        q = q.filter(model.database_version_id == version_id)
    if territory_filter is not None:
        q = q.filter(territory_filter)
    result: dict[tuple[str, int], Decimal | None] = {}
    for row in q.all():
        if row.year_number is None or not row.row_kind:
            continue
        result[(str(row.row_kind), int(row.year_number))] = row.parameter_value
    return result


def _load_coefficients(
    *,
    version_id: int | None,
    model: type,
    territory_filter: Any | None = None,
) -> tuple[Decimal | None, Decimal | None]:
    q = model.query
    if version_id is not None:
        q = q.filter(model.database_version_id == version_id)
    if territory_filter is not None:
        q = q.filter(territory_filter)
    row = q.first()
    if row is None:
        return None, None
    return row.coefficient_a, row.coefficient_x


def _build_row_defs() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for kind in ROW_KINDS:
        formula_key = ROW_FORMULA_KEY_BY_KIND.get(kind, "")
        row_css = ""
        if kind == "intensity":
            row_css = "lt-ei-row-intensity"
        elif kind == "graph_point":
            row_css = "lt-ei-row-graph-point"
        elif kind in ("calculated", "delta"):
            row_css = "table-warning"
        rows.append(
            {
                "row_kind": kind,
                "row_label": ROW_LABEL_BY_KIND.get(kind, kind),
                "row_css": row_css,
                "formula_hint": ei_formula_text(formula_key) if formula_key else "",
                "is_computed": False,
                "is_formula_computed": kind in EI_FORMULA_EDITABLE_ROW_KINDS,
                "allows_manual_edit": kind in EI_FORMULA_EDITABLE_ROW_KINDS,
            }
        )
    return rows


def _graph_point_db_years_from_fd_ved_map(
    ved_id: int,
    ei_year_by_ved: dict[tuple[int, str, int], Decimal | None],
) -> frozenset[int]:
    """Годы graph_point, для которых в БД есть запись (в т.ч. с NULL)."""
    return frozenset(
        year
        for (v_id, rk, year) in ei_year_by_ved.keys()
        if v_id == ved_id and rk == ROW_KIND_GRAPH_POINT
    )


def _graph_point_db_years_from_kind_year_map(
    values_by_kind_year: dict[tuple[str, int], Decimal | None],
) -> frozenset[int]:
    """Годы graph_point с записью в БД (карта (row_kind, year) → value)."""
    return frozenset(
        year
        for (rk, year) in values_by_kind_year.keys()
        if rk == ROW_KIND_GRAPH_POINT
    )


def _should_autofill_graph_point_cell(
    graph_point_row: dict[str, Any] | None, year: int
) -> bool:
    """Подставлять формулу только если в БД нет строки для этого года."""
    if graph_point_row is None:
        return False
    if year in graph_point_row.get("db_years", ()):
        return False
    return graph_point_row.get("cells", {}).get(year) is None


def _attach_row_cells(
    row_def: dict[str, Any],
    values_by_kind_year: dict[tuple[str, int], Decimal | None],
    display_years: list[int],
    rounding_digits: int,
    *,
    graph_point_db_years: frozenset[int] | None = None,
) -> dict[str, Any]:
    cells: dict[int, Any] = {}
    for year in display_years:
        cells[year] = values_by_kind_year.get((row_def["row_kind"], year))
    out = {**row_def, "cells": cells}
    row_kind = row_def.get("row_kind")
    if row_kind == ROW_KIND_GRAPH_POINT and graph_point_db_years is not None:
        out["db_years"] = graph_point_db_years
    out["cell_tooltips"] = {
        year: _format_cell_tooltip(cells.get(year), row_kind=row_kind)
        for year in display_years
    }
    display_rd = _ei_display_digits_for_row(row_kind, rounding_digits)
    out["cells_display"] = {
        year: _format_cell_display(cells.get(year), display_rd)
        for year in display_years
    }
    return out


def _resolve_price_year_for_ref_labels(
    version_id: int | None,
    fd_id: int,
    coeff_base_year: int,
) -> int:
    """Год цен для подписей выпуска/инвестиций (из product-output или базовый год периода)."""
    q = (
        FederalDistrictProductOutputParameter.query.join(
            Year,
            FederalDistrictProductOutputParameter.id_year_specific_product_output
            == Year.id,
        )
        .filter(
            FederalDistrictProductOutputParameter.id_federal_district == fd_id,
            FederalDistrictProductOutputParameter.id_year_specific_product_output.isnot(
                None
            ),
        )
    )
    if version_id is not None:
        q = q.filter(
            FederalDistrictProductOutputParameter.database_version_id
            == version_id
        )
    row = q.with_entities(Year.number).first()
    if row is not None and row[0] is not None:
        return int(row[0])
    ges_year = get_ges_tep_current_price_year_number()
    if ges_year is not None:
        return int(ges_year)
    return int(coeff_base_year)


def _find_industrial_component_veds(
    ved_types: list[EconomicActivityType],
) -> list[EconomicActivityType]:
    component_veds: list[EconomicActivityType] = []
    for target in INDUSTRIAL_COMPONENT_VED_TARGETS:
        ved = _find_ved_by_target(ved_types, target)
        if ved is None:
            return []
        component_veds.append(ved)
    return component_veds


def _sum_values_by_ved_year_for_veds(
    ved_ids: list[int],
    values_by_ved_year: dict[tuple[int, int], Decimal | None],
    display_years: list[int],
) -> dict[int, Decimal | None]:
    cells: dict[int, Decimal | None] = {}
    for year in display_years:
        total: Decimal | None = None
        has_any = False
        for ved_id in ved_ids:
            val = values_by_ved_year.get((ved_id, year))
            if val is not None:
                has_any = True
                total = (total or Decimal(0)) + val
        cells[year] = total if has_any else None
    return cells


def _scale_cells_by_factor(
    cells: dict[int, Decimal | None],
    *,
    factor: Decimal,
) -> dict[int, Decimal | None]:
    if factor == 0:
        return dict(cells)
    return {
        year: (val / factor if val is not None else None)
        for year, val in cells.items()
    }


def _sum_cell_maps(
    *cell_maps: dict[int, Decimal | None],
    display_years: list[int],
) -> dict[int, Decimal | None]:
    cells: dict[int, Decimal | None] = {}
    for year in display_years:
        total: Decimal | None = None
        has_any = False
        for cell_map in cell_maps:
            val = cell_map.get(year)
            if val is not None:
                has_any = True
                total = (total or Decimal(0)) + val
        cells[year] = total if has_any else None
    return cells


def _fd_total_excluded_ved_name_keys() -> frozenset[str]:
    return frozenset(
        {
            _normalize_label(TOTAL_VED_NAME),
            _normalize_label(NETWORK_LOSSES_VED_TARGET),
            _normalize_label(POWER_STATION_OWN_NEEDS_VED_TARGET),
        }
    )


def _ved_ids_for_fd_total_sums(ved_types: list[EconomicActivityType]) -> list[int]:
    excluded = _fd_total_excluded_ved_name_keys()
    ved_ids: list[int] = []
    for ved in ved_types:
        if not ved.name or not _ved_section_display_name(ved):
            continue
        if _is_parent_industrial_ved_name(ved.name):
            continue
        if _is_total_consumption_ved(ved):
            continue
        if _normalize_label(ved.name) in excluded:
            continue
        ved_ids.append(int(ved.id))
    return ved_ids


def _resolve_consumption_anchor_year(
    *,
    display_years: list[int],
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    ved_ids: list[int],
    current_year: int | None,
) -> int | None:
    """Последний год с фактическим потреблением (предпочтительно текущий)."""
    if current_year is not None:
        for ved_id in ved_ids:
            if consumption_by_ved_year.get((ved_id, current_year)) is not None:
                return current_year
    for year in reversed(display_years):
        for ved_id in ved_ids:
            if consumption_by_ved_year.get((ved_id, year)) is not None:
                return year
    return None


def _consumption_cells_for_ved_with_forecast(
    *,
    ved_id: int,
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    coef_a: Decimal | None,
    coef_x: Decimal | None,
    display_years: list[int],
    anchor_year: int | None,
) -> dict[int, Decimal | None]:
    """Потребление по ВЭД: факт из БД или прогноз (расчётная электроёмкость × выпуск)."""
    anchor_intensity: Decimal | None = None
    if anchor_year is not None:
        anchor_intensity = _compute_ei_intensity(
            consumption_by_ved_year.get((ved_id, anchor_year)),
            product_output_by_ved_year.get((ved_id, anchor_year)),
        )
    cells: dict[int, Decimal | None] = {}
    for year in display_years:
        direct = consumption_by_ved_year.get((ved_id, year))
        if direct is not None:
            cells[year] = direct
            continue
        product = product_output_by_ved_year.get((ved_id, year))
        intensity = _compute_ei_calculated(
            coef_a,
            coef_x,
            accum_by_ved_year.get((ved_id, year)),
        )
        if intensity is None:
            intensity = anchor_intensity
        cells[year] = _compute_consumption_from_intensity(intensity, product)
    return cells


def _scale_forecast_cells_from_anchor(
    cells: dict[int, Decimal | None],
    *,
    scale_cells: dict[int, Decimal | None],
    display_years: list[int],
    anchor_year: int | None,
) -> dict[int, Decimal | None]:
    """Прогноз строки без выпуска продукции — по темпу роста опорной суммы."""
    if anchor_year is None:
        return cells
    anchor_val = cells.get(anchor_year)
    anchor_scale = scale_cells.get(anchor_year)
    if anchor_val is None or anchor_scale is None or anchor_scale == 0:
        return cells
    out = dict(cells)
    for year in display_years:
        if out.get(year) is not None:
            continue
        scale_val = scale_cells.get(year)
        if scale_val is None:
            continue
        out[year] = anchor_val * (scale_val / anchor_scale)
    return out


def _load_fd_total_consumption_k_map(
    *,
    version_id: int | None,
    fd_id: int,
) -> dict[str, Decimal | None]:
    q = FederalDistrictFdTotalConsumptionCoefficient.query.filter(
        FederalDistrictFdTotalConsumptionCoefficient.id_federal_district == fd_id
    )
    if version_id is not None:
        q = q.filter(
            FederalDistrictFdTotalConsumptionCoefficient.database_version_id == version_id
        )
    result: dict[str, Decimal | None] = {}
    for row in q.all():
        if row.row_kind:
            result[str(row.row_kind)] = to_decimal(row.coefficient_k)
    return result


def _fd_total_k_display_fields(coefficient_k: Decimal | None) -> dict[str, Any]:
    return {
        "has_coefficient_k": True,
        "coefficient_k": coefficient_k,
        "coefficient_k_display": _format_cell_display(
            coefficient_k, EI_FD_TOTAL_K_DISPLAY_ROUNDING_DIGITS
        ),
        "coefficient_k_tooltip": _format_full_numeric_tooltip(coefficient_k),
    }


def _apply_fd_total_row_k_for_plan_years(
    cells: dict[int, Decimal | None],
    *,
    ved_consumption_cells: dict[int, Decimal | None],
    coefficient_k: Decimal | None,
    display_years: list[int],
    current_year: int | None,
    year_features: dict[int, str] | None = None,
) -> tuple[dict[int, Decimal | None], frozenset[int]]:
    """Плановые годы строки «Потери в сетях» / «С.н. электростанций»: потребление ВЭД × k."""
    if coefficient_k is None:
        return cells, frozenset()
    plan_years = _ei_plan_years(display_years, current_year, year_features)
    if not plan_years:
        return cells, frozenset()
    out = dict(cells)
    computed: set[int] = set()
    for year in plan_years:
        ved = ved_consumption_cells.get(year)
        if ved is None:
            continue
        out[year] = ved * coefficient_k
        computed.add(year)
    return out, frozenset(computed)


def _sum_displayed_ved_consumption_from_fd_sections(
    ved_sections: list[dict[str, Any]],
    *,
    display_years: list[int],
) -> dict[int, Decimal | None]:
    """Сумма строк «Потребление ЭЭ» по секциям ФО (как на странице), млн кВт·ч."""
    cells: dict[int, Decimal | None] = {year: None for year in display_years}
    for section in ved_sections:
        if section.get("is_industrial_group"):
            continue
        ref_kind = (
            REF_ROW_HOUSEHOLD_CONSUMPTION
            if section.get("is_population_section")
            else REF_ROW_CONSUMPTION
        )
        ref_row = next(
            (
                row
                for row in section.get("reference_rows") or []
                if row.get("row_kind") == ref_kind
            ),
            None,
        )
        if ref_row is None:
            continue
        row_cells = ref_row.get("cells") or {}
        for year in display_years:
            val = row_cells.get(year)
            if val is None:
                continue
            prev = cells.get(year)
            cells[year] = (prev or Decimal(0)) + val
    return cells


def _build_fd_network_and_power_station_cells(
    *,
    ved_types: list[EconomicActivityType],
    sum_ved_ids: list[int],
    ved_consumption_cells: dict[int, Decimal | None],
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    display_years: list[int],
    current_year: int | None,
    coefficient_k_by_row_kind: dict[str, Decimal | None] | None = None,
    year_features: dict[int, str] | None = None,
) -> tuple[
    dict[int, Decimal | None],
    dict[int, Decimal | None],
    dict[str, frozenset[int]],
]:
    network_losses_ved = _find_ved_by_target(ved_types, NETWORK_LOSSES_VED_TARGET)
    power_station_ved = _find_ved_by_target(ved_types, POWER_STATION_OWN_NEEDS_VED_TARGET)
    all_ved_ids = list(sum_ved_ids)
    if network_losses_ved is not None:
        all_ved_ids.append(int(network_losses_ved.id))
    if power_station_ved is not None:
        all_ved_ids.append(int(power_station_ved.id))
    anchor_year = _resolve_consumption_anchor_year(
        display_years=display_years,
        consumption_by_ved_year=consumption_by_ved_year,
        ved_ids=all_ved_ids,
        current_year=current_year,
    )

    k_by_kind = coefficient_k_by_row_kind or {}
    plan_computed_by_kind: dict[str, frozenset[int]] = {}

    network_losses_cells = {year: None for year in display_years}
    if network_losses_ved is not None:
        nl_id = int(network_losses_ved.id)
        for year in display_years:
            network_losses_cells[year] = consumption_by_ved_year.get((nl_id, year))
        nl_k = k_by_kind.get(REF_ROW_FD_NETWORK_LOSSES)
        if nl_k is not None:
            network_losses_cells, plan_computed_by_kind[REF_ROW_FD_NETWORK_LOSSES] = (
                _apply_fd_total_row_k_for_plan_years(
                    network_losses_cells,
                    ved_consumption_cells=ved_consumption_cells,
                    coefficient_k=nl_k,
                    display_years=display_years,
                    current_year=current_year,
                    year_features=year_features,
                )
            )
        else:
            network_losses_cells = _scale_forecast_cells_from_anchor(
                network_losses_cells,
                scale_cells=ved_consumption_cells,
                display_years=display_years,
                anchor_year=anchor_year,
            )

    power_station_cells = {year: None for year in display_years}
    if power_station_ved is not None:
        ps_id = int(power_station_ved.id)
        for year in display_years:
            power_station_cells[year] = consumption_by_ved_year.get((ps_id, year))
        ps_k = k_by_kind.get(REF_ROW_FD_POWER_STATION)
        if ps_k is not None:
            power_station_cells, plan_computed_by_kind[REF_ROW_FD_POWER_STATION] = (
                _apply_fd_total_row_k_for_plan_years(
                    power_station_cells,
                    ved_consumption_cells=ved_consumption_cells,
                    coefficient_k=ps_k,
                    display_years=display_years,
                    current_year=current_year,
                    year_features=year_features,
                )
            )
        else:
            power_station_cells = _scale_forecast_cells_from_anchor(
                power_station_cells,
                scale_cells=ved_consumption_cells,
                display_years=display_years,
                anchor_year=anchor_year,
            )

    return network_losses_cells, power_station_cells, plan_computed_by_kind


def _build_fd_summary_consumption_cells(
    *,
    ved_types: list[EconomicActivityType],
    sum_ved_ids: list[int],
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    coef_by_ved: dict[int, tuple[Decimal | None, Decimal | None]],
    display_years: list[int],
    current_year: int | None,
    coefficient_k_by_row_kind: dict[str, Decimal | None] | None = None,
    year_features: dict[int, str] | None = None,
) -> tuple[
    dict[int, Decimal | None],
    dict[int, Decimal | None],
    dict[int, Decimal | None],
    dict[str, frozenset[int]],
]:
    network_losses_ved = _find_ved_by_target(ved_types, NETWORK_LOSSES_VED_TARGET)
    power_station_ved = _find_ved_by_target(ved_types, POWER_STATION_OWN_NEEDS_VED_TARGET)
    all_ved_ids = list(sum_ved_ids)
    if network_losses_ved is not None:
        all_ved_ids.append(int(network_losses_ved.id))
    if power_station_ved is not None:
        all_ved_ids.append(int(power_station_ved.id))
    anchor_year = _resolve_consumption_anchor_year(
        display_years=display_years,
        consumption_by_ved_year=consumption_by_ved_year,
        ved_ids=all_ved_ids,
        current_year=current_year,
    )

    ved_consumption_cells: dict[int, Decimal | None] = {
        year: None for year in display_years
    }
    for ved_id in sum_ved_ids:
        coef_a, coef_x = coef_by_ved.get(ved_id, (None, None))
        ved_cells = _consumption_cells_for_ved_with_forecast(
            ved_id=ved_id,
            consumption_by_ved_year=consumption_by_ved_year,
            product_output_by_ved_year=product_output_by_ved_year,
            accum_by_ved_year=accum_by_ved_year,
            coef_a=coef_a,
            coef_x=coef_x,
            display_years=display_years,
            anchor_year=anchor_year,
        )
        for year in display_years:
            val = ved_cells.get(year)
            if val is not None:
                prev = ved_consumption_cells.get(year)
                ved_consumption_cells[year] = (prev or Decimal(0)) + val

    network_losses_cells, power_station_cells, plan_computed_by_kind = (
        _build_fd_network_and_power_station_cells(
            ved_types=ved_types,
            sum_ved_ids=sum_ved_ids,
            ved_consumption_cells=ved_consumption_cells,
            consumption_by_ved_year=consumption_by_ved_year,
            display_years=display_years,
            current_year=current_year,
            coefficient_k_by_row_kind=coefficient_k_by_row_kind,
            year_features=year_features,
        )
    )

    return (
        ved_consumption_cells,
        network_losses_cells,
        power_station_cells,
        plan_computed_by_kind,
    )


def _build_fd_total_reference_row(
    *,
    ref_kind: str,
    cells: dict[int, Decimal | None],
    display_years: list[int],
    rounding_digits: int,
    price_year: int | None = None,
    source_endpoint: str = "",
    source_page_title: str = "",
    coefficient_k: Decimal | None = None,
    plan_computed_years: frozenset[int] | None = None,
) -> dict[str, Any]:
    _ = price_year
    formula_key = REF_ROW_FD_FORMULA_KEY_BY_KIND.get(ref_kind, "")
    if plan_computed_years and REF_ROW_FD_PLAN_FORMULA_KEY_BY_KIND.get(ref_kind):
        formula_key = REF_ROW_FD_PLAN_FORMULA_KEY_BY_KIND[ref_kind]
    row: dict[str, Any] = {
        "row_kind": ref_kind,
        "row_label": REF_ROW_FD_LABEL_BY_KIND.get(ref_kind, ref_kind),
        "unit_label": REF_ROW_FD_UNIT_BY_KIND.get(ref_kind, ""),
        "row_css": REF_ROW_FD_CSS_BY_KIND.get(ref_kind, ""),
        "is_readonly": True,
        "is_computed": True,
        "source_endpoint": source_endpoint,
        "source_page_title": source_page_title,
        "formula_hint": ei_formula_text(formula_key) if formula_key else "",
        "cells": cells,
        "cell_tooltips": {
            year: _format_full_numeric_tooltip(cells.get(year)) for year in display_years
        },
        "cells_display": {
            year: _format_cell_display(cells.get(year), rounding_digits)
            for year in display_years
        },
    }
    if ref_kind in (REF_ROW_FD_NETWORK_LOSSES, REF_ROW_FD_POWER_STATION):
        row.update(_fd_total_k_display_fields(coefficient_k))
        if plan_computed_years:
            row["computed_years"] = plan_computed_years
    return row


def _build_fd_territory_summary(
    *,
    fd_id: int,
    version_id: int | None,
    ved_types: list[EconomicActivityType],
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    coef_by_ved: dict[int, tuple[Decimal | None, Decimal | None]],
    display_years: list[int],
    rounding_digits: int,
    price_year: int,
    current_year: int | None,
    year_features: dict[int, str] | None = None,
    coefficient_k_by_row_kind: dict[str, Decimal | None] | None = None,
    ved_sections: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    sum_ved_ids = _ved_ids_for_fd_total_sums(ved_types)
    if not sum_ved_ids:
        return None

    if coefficient_k_by_row_kind is None:
        coefficient_k_by_row_kind = _load_fd_total_consumption_k_map(
            version_id=version_id,
            fd_id=fd_id,
        )

    vrp_cells = _sum_values_by_ved_year_for_veds(
        sum_ved_ids, product_output_by_ved_year, display_years
    )
    accum_cells = _sum_values_by_ved_year_for_veds(
        sum_ved_ids, accum_by_ved_year, display_years
    )

    if ved_sections is not None:
        ved_consumption_cells = _sum_displayed_ved_consumption_from_fd_sections(
            ved_sections,
            display_years=display_years,
        )
        network_losses_cells, power_station_cells, plan_computed_by_kind = (
            _build_fd_network_and_power_station_cells(
                ved_types=ved_types,
                sum_ved_ids=sum_ved_ids,
                ved_consumption_cells=ved_consumption_cells,
                consumption_by_ved_year=consumption_by_ved_year,
                display_years=display_years,
                current_year=current_year,
                coefficient_k_by_row_kind=coefficient_k_by_row_kind,
                year_features=year_features,
            )
        )
    else:
        household_ved = _find_ved_by_target(ved_types, HOUSEHOLD_VED_TARGET)
        all_ved_types = ved_types
        if household_ved is None:
            all_ved_types = _refdata_ved_types_for_version(version_id)
            household_ved = _find_ved_by_target(all_ved_types, HOUSEHOLD_VED_TARGET)
        household_ved_id = int(household_ved.id) if household_ved is not None else None
        sum_ved_ids_for_consumption = [
            ved_id
            for ved_id in sum_ved_ids
            if household_ved_id is None or ved_id != household_ved_id
        ]
        (
            ved_consumption_cells,
            network_losses_cells,
            power_station_cells,
            plan_computed_by_kind,
        ) = _build_fd_summary_consumption_cells(
            ved_types=ved_types,
            sum_ved_ids=sum_ved_ids_for_consumption,
            consumption_by_ved_year=consumption_by_ved_year,
            product_output_by_ved_year=product_output_by_ved_year,
            accum_by_ved_year=accum_by_ved_year,
            coef_by_ved=coef_by_ved,
            display_years=display_years,
            current_year=current_year,
            coefficient_k_by_row_kind=coefficient_k_by_row_kind,
            year_features=year_features,
        )
        if household_ved_id is not None:
            household_by_year = _compute_household_consumption_by_year_for_fd(
                fd_id=fd_id,
                version_id=version_id,
                ved_types=all_ved_types,
                consumption_by_ved_year=consumption_by_ved_year,
                display_years=display_years,
                rounding_digits=rounding_digits,
                current_year=current_year,
            )
            ved_consumption_cells = _sum_cell_maps(
                ved_consumption_cells,
                household_by_year,
                display_years=display_years,
            )

    ved_consumption_bn_cells = _scale_cells_by_factor(
        ved_consumption_cells, factor=EI_BILLION_KWH_FACTOR
    )
    network_losses_bn_cells = _scale_cells_by_factor(
        network_losses_cells, factor=EI_BILLION_KWH_FACTOR
    )
    power_station_bn_cells = _scale_cells_by_factor(
        power_station_cells, factor=EI_BILLION_KWH_FACTOR
    )
    total_consumption_bn_cells = _sum_cell_maps(
        ved_consumption_bn_cells,
        network_losses_bn_cells,
        power_station_bn_cells,
        display_years=display_years,
    )

    consumption_raw_cells = _sum_cell_maps(
        ved_consumption_cells,
        network_losses_cells,
        power_station_cells,
        display_years=display_years,
    )

    reference_rows = [
        _build_fd_total_reference_row(
            ref_kind=REF_ROW_FD_VRP,
            cells=vrp_cells,
            display_years=display_years,
            rounding_digits=rounding_digits,
            price_year=price_year,
            source_endpoint=REF_ROW_SOURCE_ENDPOINT[REF_ROW_PRODUCT_OUTPUT],
            source_page_title=REF_ROW_SOURCE_PAGE_TITLE[REF_ROW_PRODUCT_OUTPUT],
        ),
        _build_fd_total_reference_row(
            ref_kind=REF_ROW_FD_TOTAL_CONSUMPTION,
            cells=total_consumption_bn_cells,
            display_years=display_years,
            rounding_digits=rounding_digits,
            price_year=price_year,
        ),
        _build_fd_total_reference_row(
            ref_kind=REF_ROW_FD_VED_CONSUMPTION,
            cells=ved_consumption_bn_cells,
            display_years=display_years,
            rounding_digits=rounding_digits,
            price_year=price_year,
            source_endpoint=REF_ROW_SOURCE_ENDPOINT[REF_ROW_CONSUMPTION],
            source_page_title=REF_ROW_SOURCE_PAGE_TITLE[REF_ROW_CONSUMPTION],
        ),
        _build_fd_total_reference_row(
            ref_kind=REF_ROW_FD_NETWORK_LOSSES,
            cells=network_losses_bn_cells,
            display_years=display_years,
            rounding_digits=rounding_digits,
            price_year=price_year,
            source_endpoint=REF_ROW_SOURCE_ENDPOINT[REF_ROW_CONSUMPTION],
            source_page_title=REF_ROW_SOURCE_PAGE_TITLE[REF_ROW_CONSUMPTION],
            coefficient_k=coefficient_k_by_row_kind.get(REF_ROW_FD_NETWORK_LOSSES),
            plan_computed_years=plan_computed_by_kind.get(REF_ROW_FD_NETWORK_LOSSES),
        ),
        _build_fd_total_reference_row(
            ref_kind=REF_ROW_FD_POWER_STATION,
            cells=power_station_bn_cells,
            display_years=display_years,
            rounding_digits=rounding_digits,
            price_year=price_year,
            source_endpoint=REF_ROW_SOURCE_ENDPOINT[REF_ROW_CONSUMPTION],
            source_page_title=REF_ROW_SOURCE_PAGE_TITLE[REF_ROW_CONSUMPTION],
            coefficient_k=coefficient_k_by_row_kind.get(REF_ROW_FD_POWER_STATION),
            plan_computed_years=plan_computed_by_kind.get(REF_ROW_FD_POWER_STATION),
        ),
        _build_fd_total_reference_row(
            ref_kind=REF_ROW_FD_ACCUM_FIXED_CAPITAL,
            cells=accum_cells,
            display_years=display_years,
            rounding_digits=rounding_digits,
            price_year=price_year,
            source_endpoint=REF_ROW_SOURCE_ENDPOINT[REF_ROW_ACCUM_FIXED_CAPITAL],
            source_page_title=REF_ROW_SOURCE_PAGE_TITLE[REF_ROW_ACCUM_FIXED_CAPITAL],
        ),
    ]

    intensity_row_def = next(
        rd for rd in _build_row_defs() if rd["row_kind"] == ROW_KIND_INTENSITY
    )
    intensity_by_year: dict[int, Decimal | None] = {
        year: _compute_ei_intensity(
            consumption_raw_cells.get(year),
            vrp_cells.get(year),
        )
        for year in display_years
    }
    section_rows = [
        _attach_row_cells(
            intensity_row_def,
            {
                (ROW_KIND_INTENSITY, year): intensity_by_year.get(year)
                for year in display_years
            },
            display_years,
            rounding_digits,
        )
    ]
    summary: dict[str, Any] = {
        "has_ei_intensity_block": True,
        "reference_rows": reference_rows,
        "rows": section_rows,
    }
    scatter_chart = build_fd_summary_scatter_chart(
        accum_cells=accum_cells,
        intensity_cells=intensity_by_year,
        display_years=display_years,
        current_year=current_year,
    )
    if scatter_chart is not None:
        summary["scatter_chart"] = scatter_chart
    return summary


def _resolve_price_year_for_rf_labels(
    version_id: int | None,
    coeff_base_year: int,
) -> int:
    """Год цен для подписи ВВП (из product-output РФ или базовый год периода)."""
    q = RussiaFederationProductOutputParameter.query.filter(
        RussiaFederationProductOutputParameter.id_year_specific_product_output.isnot(
            None
        )
    )
    if version_id is not None:
        q = q.filter(
            RussiaFederationProductOutputParameter.database_version_id == version_id
        )
    row = (
        q.join(
            Year,
            RussiaFederationProductOutputParameter.id_year_specific_product_output
            == Year.id,
        )
        .with_entities(Year.number)
        .first()
    )
    if row is not None and row[0] is not None:
        return int(row[0])
    ges_year = get_ges_tep_current_price_year_number()
    if ges_year is not None:
        return int(ges_year)
    return int(coeff_base_year)


def _load_rf_gaes_charge_cells(
    *,
    display_years: list[int],
) -> dict[int, Decimal | None]:
    """Суммарный заряд ГАЭС по РФ (млн кВт·ч), как строка «всего» на сводке ГАЭС."""
    if not display_years:
        return {}
    q = (
        db.session.query(
            StationGaesChargeConsumption.year_number,
            func.sum(StationGaesChargeConsumption.charge_consumption),
        )
        .select_from(StationGaesChargeConsumption)
        .join(Station, Station.id == StationGaesChargeConsumption.id_station)
    )
    q = dps.filter_parents_by_version(q, StationGaesChargeConsumption)
    q = dps.filter_parents_by_version(q, Station)
    q = q.filter(StationGaesChargeConsumption.year_number.in_(display_years))
    q = q.group_by(StationGaesChargeConsumption.year_number)
    cells: dict[int, Decimal | None] = {year: None for year in display_years}
    for year_n, total in q.all():
        if year_n is not None and total is not None:
            cells[int(year_n)] = total
    return cells


def _compute_yoy_growth_cells(
    base_cells: dict[int, Decimal | None],
    display_years: list[int],
) -> dict[int, Decimal | None]:
    cells: dict[int, Decimal | None] = {}
    for year in display_years:
        curr = base_cells.get(year)
        prev = base_cells.get(year - 1)
        if curr is not None and prev is not None and prev != 0:
            cells[year] = (curr / prev) * Decimal(100) - Decimal(100)
        else:
            cells[year] = None
    return cells


def _subtract_cell_maps(
    minuend: dict[int, Decimal | None],
    subtrahend: dict[int, Decimal | None],
    display_years: list[int],
) -> dict[int, Decimal | None]:
    cells: dict[int, Decimal | None] = {}
    for year in display_years:
        a = minuend.get(year)
        b = subtrahend.get(year)
        cells[year] = (a - b) if a is not None and b is not None else None
    return cells


def _compute_rf_gdp_intensity_cells(
    consumption_bn_cells: dict[int, Decimal | None],
    gdp_mln_cells: dict[int, Decimal | None],
    display_years: list[int],
    rounding_digits: int,
) -> dict[int, Decimal | None]:
    cells: dict[int, Decimal | None] = {}
    for year in display_years:
        cons_bn = consumption_bn_cells.get(year)
        gdp_mln = gdp_mln_cells.get(year)
        if cons_bn is not None and gdp_mln is not None and gdp_mln != 0:
            cons_mln = cons_bn * EI_BILLION_KWH_FACTOR
            cells[year] = cons_mln / gdp_mln * EI_INTENSITY_UNIT_FACTOR
        else:
            cells[year] = None
    return cells


def _build_rf_summary_reference_row(
    *,
    ref_kind: str,
    cells: dict[int, Decimal | None],
    display_years: list[int],
    rounding_digits: int,
    row_label: str | None = None,
    source_endpoint: str = "",
    source_page_title: str = "",
    param_inline_class: str = "",
    label_em: bool = False,
) -> dict[str, Any]:
    formula_key = REF_ROW_RF_FORMULA_KEY_BY_KIND.get(ref_kind, "")
    display_rd = (
        rounding_digits
        if ref_kind != REF_ROW_RF_GDP_INTENSITY
        else _ei_display_digits_for_row(ROW_KIND_INTENSITY, rounding_digits)
    )
    row: dict[str, Any] = {
        "row_kind": ref_kind,
        "row_label": row_label or REF_ROW_RF_LABEL_BY_KIND.get(ref_kind, ref_kind),
        "unit_label": REF_ROW_RF_UNIT_BY_KIND.get(ref_kind, ""),
        "row_css": REF_ROW_RF_CSS_BY_KIND.get(ref_kind, ""),
        "is_readonly": True,
        "is_computed": True,
        "source_endpoint": source_endpoint,
        "source_page_title": source_page_title,
        "formula_hint": ei_formula_text(formula_key) if formula_key else "",
        "cells": cells,
        "cell_tooltips": {
            year: _format_full_numeric_tooltip(cells.get(year))
            for year in display_years
        },
        "cells_display": {
            year: _format_cell_display(cells.get(year), display_rd)
            for year in display_years
        },
    }
    if param_inline_class:
        row["param_inline_class"] = param_inline_class
    if label_em:
        row["label_em"] = True
    return row


def _sum_fd_summary_reference_cells(
    fd_summaries: list[dict[str, Any]],
    row_kind: str,
    display_years: list[int],
) -> dict[int, Decimal | None]:
    """Сумма одноимённых строк сводки «всего» по ФО (с прогнозом на плановые годы)."""
    parts: list[dict[int, Decimal | None]] = []
    for summary in fd_summaries:
        ref_by_kind = {
            r["row_kind"]: r for r in summary.get("reference_rows") or []
        }
        row = ref_by_kind.get(row_kind)
        if row is not None:
            parts.append(row.get("cells") or {})
    if not parts:
        return {year: None for year in display_years}
    return _sum_cell_dicts(*parts, display_years=display_years)


def _build_rf_territory_summary(
    *,
    version_id: int | None,
    ved_types: list[EconomicActivityType],
    display_years: list[int],
    rounding_digits: int,
    coeff_base_year: int,
    fd_filter_ids: frozenset[int],
    current_year: int | None,
    fd_summaries: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    sum_ved_ids = _ved_ids_for_fd_total_sums(ved_types)
    if not sum_ved_ids:
        return None

    _, product_by_ved, _, _, accum_by_ved, _, _ = _aggregate_fd_maps_for_rf(
        version_id=version_id,
        ved_types=ved_types,
        display_years=display_years,
        rounding_digits=rounding_digits,
        fd_filter_ids=fd_filter_ids,
        current_year=current_year,
    )
    gdp_mln_cells = _sum_values_by_ved_year_for_veds(
        sum_ved_ids, product_by_ved, display_years
    )

    if fd_summaries:
        ved_consumption_bn_cells = _sum_fd_summary_reference_cells(
            fd_summaries, REF_ROW_FD_VED_CONSUMPTION, display_years
        )
        network_losses_bn_cells = _sum_fd_summary_reference_cells(
            fd_summaries, REF_ROW_FD_NETWORK_LOSSES, display_years
        )
        power_station_bn_cells = _sum_fd_summary_reference_cells(
            fd_summaries, REF_ROW_FD_POWER_STATION, display_years
        )
        total_consumption_bn_cells = _sum_fd_summary_reference_cells(
            fd_summaries, REF_ROW_FD_TOTAL_CONSUMPTION, display_years
        )
    else:
        consumption_by_ved = _load_ved_consumption_values_map(
            version_id=version_id,
            model=RussiaFederationConsumptionParameter,
        )
        household_ved = _find_ved_by_target(ved_types, HOUSEHOLD_VED_TARGET)
        household_ved_id = int(household_ved.id) if household_ved is not None else None
        sum_ved_ids_for_rf = [
            ved_id
            for ved_id in sum_ved_ids
            if household_ved_id is None or ved_id != household_ved_id
        ]
        ved_consumption_cells = _sum_values_by_ved_year_for_veds(
            sum_ved_ids_for_rf, consumption_by_ved, display_years
        )
        if household_ved_id is not None:
            household_by_year, _ = _aggregate_rf_household_and_population_by_year(
                version_id=version_id,
                ved_types=ved_types,
                display_years=display_years,
                fd_filter_ids=fd_filter_ids,
            )
            ved_consumption_cells = _sum_cell_maps(
                ved_consumption_cells,
                household_by_year,
                display_years=display_years,
            )

        network_losses_ved = _find_ved_by_target(ved_types, NETWORK_LOSSES_VED_TARGET)
        power_station_ved = _find_ved_by_target(
            ved_types, POWER_STATION_OWN_NEEDS_VED_TARGET
        )
        network_losses_cells = (
            {
                year: consumption_by_ved.get((int(network_losses_ved.id), year))
                for year in display_years
            }
            if network_losses_ved is not None
            else {year: None for year in display_years}
        )
        power_station_cells = (
            {
                year: consumption_by_ved.get((int(power_station_ved.id), year))
                for year in display_years
            }
            if power_station_ved is not None
            else {year: None for year in display_years}
        )
        ved_consumption_bn_cells = _scale_cells_by_factor(
            ved_consumption_cells, factor=EI_BILLION_KWH_FACTOR
        )
        network_losses_bn_cells = _scale_cells_by_factor(
            network_losses_cells, factor=EI_BILLION_KWH_FACTOR
        )
        power_station_bn_cells = _scale_cells_by_factor(
            power_station_cells, factor=EI_BILLION_KWH_FACTOR
        )
        total_consumption_bn_cells = _sum_cell_maps(
            ved_consumption_bn_cells,
            network_losses_bn_cells,
            power_station_bn_cells,
            display_years=display_years,
        )

    gaes_mln_cells = _load_rf_gaes_charge_cells(display_years=display_years)

    gaes_bn_cells = _scale_cells_by_factor(
        gaes_mln_cells, factor=EI_BILLION_KWH_FACTOR
    )
    gdp_bn_cells = _scale_cells_by_factor(
        gdp_mln_cells, factor=EI_BILLION_KWH_FACTOR
    )
    growth_rate_cells = _compute_yoy_growth_cells(
        total_consumption_bn_cells, display_years
    )
    consumption_without_gaes_bn_cells = _subtract_cell_maps(
        ved_consumption_bn_cells,
        gaes_bn_cells,
        display_years,
    )
    gdp_intensity_cells = _compute_rf_gdp_intensity_cells(
        total_consumption_bn_cells,
        gdp_mln_cells,
        display_years,
        rounding_digits,
    )
    accum_cells = _sum_values_by_ved_year_for_veds(
        sum_ved_ids, accum_by_ved, display_years
    )

    price_year = _resolve_price_year_for_rf_labels(version_id, coeff_base_year)

    reference_rows = [
        _build_rf_summary_reference_row(
            ref_kind=REF_ROW_RF_TOTAL_CONSUMPTION,
            cells=total_consumption_bn_cells,
            display_years=display_years,
            rounding_digits=rounding_digits,
        ),
        _build_rf_summary_reference_row(
            ref_kind=REF_ROW_RF_GROWTH_RATE,
            cells=growth_rate_cells,
            display_years=display_years,
            rounding_digits=rounding_digits,
            param_inline_class="lt-ei-param-inline--indented",
            label_em=True,
        ),
        _build_rf_summary_reference_row(
            ref_kind=REF_ROW_RF_VED_CONSUMPTION,
            cells=ved_consumption_bn_cells,
            display_years=display_years,
            rounding_digits=rounding_digits,
            source_endpoint=REF_ROW_RF_SOURCE_ENDPOINT[REF_ROW_RF_VED_CONSUMPTION],
            source_page_title=REF_ROW_RF_SOURCE_PAGE_TITLE[REF_ROW_RF_VED_CONSUMPTION],
        ),
        _build_rf_summary_reference_row(
            ref_kind=REF_ROW_RF_GAES,
            cells=gaes_bn_cells,
            display_years=display_years,
            rounding_digits=rounding_digits,
            source_endpoint=REF_ROW_RF_SOURCE_ENDPOINT[REF_ROW_RF_GAES],
            source_page_title=REF_ROW_RF_SOURCE_PAGE_TITLE[REF_ROW_RF_GAES],
        ),
        _build_rf_summary_reference_row(
            ref_kind=REF_ROW_RF_CONSUMPTION_WITHOUT_GAES,
            cells=consumption_without_gaes_bn_cells,
            display_years=display_years,
            rounding_digits=rounding_digits,
        ),
        _build_rf_summary_reference_row(
            ref_kind=REF_ROW_RF_NETWORK_LOSSES,
            cells=network_losses_bn_cells,
            display_years=display_years,
            rounding_digits=rounding_digits,
            source_endpoint=REF_ROW_RF_SOURCE_ENDPOINT[REF_ROW_RF_NETWORK_LOSSES],
            source_page_title=REF_ROW_RF_SOURCE_PAGE_TITLE[REF_ROW_RF_NETWORK_LOSSES],
        ),
        _build_rf_summary_reference_row(
            ref_kind=REF_ROW_RF_POWER_STATION,
            cells=power_station_bn_cells,
            display_years=display_years,
            rounding_digits=rounding_digits,
            source_endpoint=REF_ROW_RF_SOURCE_ENDPOINT[REF_ROW_RF_POWER_STATION],
            source_page_title=REF_ROW_RF_SOURCE_PAGE_TITLE[REF_ROW_RF_POWER_STATION],
        ),
        _build_rf_summary_reference_row(
            ref_kind=REF_ROW_RF_GDP,
            cells=gdp_bn_cells,
            display_years=display_years,
            rounding_digits=rounding_digits,
            row_label=rf_gdp_row_label(price_year),
            source_endpoint=REF_ROW_RF_SOURCE_ENDPOINT[REF_ROW_RF_GDP],
            source_page_title=REF_ROW_RF_SOURCE_PAGE_TITLE[REF_ROW_RF_GDP],
        ),
        _build_rf_summary_reference_row(
            ref_kind=REF_ROW_RF_GDP_INTENSITY,
            cells=gdp_intensity_cells,
            display_years=display_years,
            rounding_digits=rounding_digits,
        ),
    ]
    summary: dict[str, Any] = {"reference_rows": reference_rows}
    chart_calculated = _aggregate_rf_summary_chart_intensity_cells(
        version_id=version_id,
        ved_types=ved_types,
        display_years=display_years,
        rounding_digits=rounding_digits,
        current_year=current_year,
        coeff_base_year=coeff_base_year,
        fd_filter_ids=fd_filter_ids,
    )
    scatter_chart = build_rf_scatter_chart(
        accum_cells=accum_cells,
        intensity_cells=gdp_intensity_cells,
        calculated_cells=chart_calculated,
        display_years=display_years,
        current_year=current_year,
    )
    if scatter_chart is not None:
        summary["scatter_chart"] = scatter_chart
    return summary


def _build_industrial_sum_reference_row(
    *,
    ref_kind: str,
    component_ved_ids: list[int],
    values_by_ved_year: dict[tuple[int, int], Decimal | None],
    display_years: list[int],
    rounding_digits: int,
    price_year: int | None = None,
) -> dict[str, Any]:
    cells = _sum_values_by_ved_year_for_veds(
        component_ved_ids, values_by_ved_year, display_years
    )
    formula_key = REF_ROW_INDUSTRIAL_FORMULA_KEY_BY_KIND.get(ref_kind, "")
    source_endpoint = REF_ROW_SOURCE_ENDPOINT.get(ref_kind, "")
    return {
        "row_kind": ref_kind,
        "row_label": ref_row_label(ref_kind, price_year=price_year),
        "unit_label": REF_ROW_UNIT_BY_KIND.get(ref_kind, ""),
        "row_css": REF_ROW_CSS_BY_KIND.get(ref_kind, ""),
        "is_readonly": True,
        "is_computed": True,
        "source_endpoint": source_endpoint,
        "source_page_title": REF_ROW_SOURCE_PAGE_TITLE.get(ref_kind, ""),
        "formula_hint": ei_formula_text(formula_key) if formula_key else "",
        "cells": cells,
        "cell_tooltips": {
            year: _format_full_numeric_tooltip(cells.get(year)) for year in display_years
        },
        "cells_display": {
            year: _format_cell_display(cells.get(year), rounding_digits)
            for year in display_years
        },
    }


def _build_industrial_group_section_for_fd(
    *,
    component_veds: list[EconomicActivityType],
    refdata_ved_ids: frozenset[int],
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    ei_year_by_ved_kind_year: dict[tuple[int, str, int], Decimal | None],
    coef_by_ved: dict[int, tuple[Decimal | None, Decimal | None]],
    display_years: list[int],
    rounding_digits: int,
    price_year: int,
    current_year: int | None,
) -> dict[str, Any]:
    component_ved_ids = [int(v.id) for v in component_veds]
    synthetic_ved_id = 0
    value_maps = {
        "product_output": product_output_by_ved_year,
        "consumption": consumption_by_ved_year,
        "accum_fixed_capital": accum_by_ved_year,
    }
    reference_rows = [
        _build_industrial_sum_reference_row(
            ref_kind=ref_kind,
            component_ved_ids=component_ved_ids,
            values_by_ved_year=value_maps[ref_kind],
            display_years=display_years,
            rounding_digits=rounding_digits,
            price_year=price_year,
        )
        for ref_kind in REF_ROW_KINDS
    ]
    intensity_row_def = next(
        rd for rd in _build_row_defs() if rd["row_kind"] == ROW_KIND_INTENSITY
    )
    section_rows = [
        _attach_row_cells(intensity_row_def, {}, display_years, rounding_digits)
    ]
    synthetic_maps = {
        ref_kind: {
            (synthetic_ved_id, year): row["cells"].get(year)
            for year in display_years
        }
        for ref_kind, row in zip(REF_ROW_KINDS, reference_rows, strict=True)
    }
    _enrich_industrial_consumption_plan_years(
        reference_rows,
        component_ved_ids=component_ved_ids,
        refdata_ved_ids=refdata_ved_ids,
        product_output_by_ved_year=product_output_by_ved_year,
        consumption_by_ved_year=consumption_by_ved_year,
        accum_by_ved_year=accum_by_ved_year,
        coef_by_ved=coef_by_ved,
        ei_year_by_ved_kind_year=ei_year_by_ved_kind_year,
        display_years=display_years,
        rounding_digits=rounding_digits,
        current_year=current_year,
    )
    consumption_ref = next(
        (r for r in reference_rows if r.get("row_kind") == REF_ROW_CONSUMPTION),
        None,
    )
    if consumption_ref is not None:
        synthetic_maps["consumption"] = {
            (synthetic_ved_id, year): consumption_ref["cells"].get(year)
            for year in display_years
        }
    _enrich_ei_computed_rows(
        section_rows,
        ved_id=synthetic_ved_id,
        consumption_by_ved_year=synthetic_maps["consumption"],
        product_output_by_ved_year=synthetic_maps["product_output"],
        accum_by_ved_year=synthetic_maps["accum_fixed_capital"],
        coef_a=None,
        coef_x=None,
        display_years=display_years,
        rounding_digits=rounding_digits,
        current_year=current_year,
    )
    return {
        "ved_id": None,
        "ved_name": INDUSTRIAL_GROUP_SECTION_LABEL,
        "is_industrial_group": True,
        "has_ei_block": True,
        "has_ei_intensity_block": True,
        "has_ei_model_block": False,
        "reference_rows": reference_rows,
        "rows": section_rows,
    }


def _build_reference_row(
    *,
    ref_kind: str,
    ved_id: int,
    values_by_ved_year: dict[tuple[int, int], Decimal | None],
    display_years: list[int],
    rounding_digits: int,
    price_year: int | None = None,
) -> dict[str, Any]:
    cells: dict[int, Any] = {}
    for year in display_years:
        cells[year] = values_by_ved_year.get((ved_id, year))
    source_endpoint = REF_ROW_SOURCE_ENDPOINT.get(ref_kind, "")
    return {
        "row_kind": ref_kind,
        "row_label": ref_row_label(ref_kind, price_year=price_year),
        "unit_label": REF_ROW_UNIT_BY_KIND.get(ref_kind, ""),
        "row_css": REF_ROW_CSS_BY_KIND.get(ref_kind, ""),
        "is_readonly": True,
        "is_computed": False,
        "source_endpoint": source_endpoint,
        "source_page_title": REF_ROW_SOURCE_PAGE_TITLE.get(ref_kind, ""),
        "cells": cells,
        "cell_tooltips": {
            year: _format_full_numeric_tooltip(cells.get(year)) for year in display_years
        },
        "cells_display": {
            year: _format_cell_display(cells.get(year), rounding_digits)
            for year in display_years
        },
    }


def _build_ved_sections_for_fd(
    *,
    ved_types: list[EconomicActivityType],
    refdata_ved_ids: frozenset[int],
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    ei_year_by_ved_kind_year: dict[tuple[int, str, int], Decimal | None],
    coef_by_ved: dict[int, tuple[Decimal | None, Decimal | None]],
    display_years: list[int],
    rounding_digits: int,
    price_year: int,
    current_year: int | None,
) -> list[dict[str, Any]]:
    value_maps = {
        "product_output": product_output_by_ved_year,
        "consumption": consumption_by_ved_year,
        "accum_fixed_capital": accum_by_ved_year,
    }
    row_defs = _build_row_defs()
    component_veds = _find_industrial_component_veds(ved_types)
    component_ved_ids = frozenset(int(v.id) for v in component_veds)
    sections: list[dict[str, Any]] = []
    industrial_section: dict[str, Any] | None = None
    if component_veds:
        industrial_section = _build_industrial_group_section_for_fd(
            component_veds=component_veds,
            refdata_ved_ids=refdata_ved_ids,
            product_output_by_ved_year=product_output_by_ved_year,
            consumption_by_ved_year=consumption_by_ved_year,
            accum_by_ved_year=accum_by_ved_year,
            ei_year_by_ved_kind_year=ei_year_by_ved_kind_year,
            coef_by_ved=coef_by_ved,
            display_years=display_years,
            rounding_digits=rounding_digits,
            price_year=price_year,
            current_year=current_year,
        )
    for ved in ved_types:
        if _is_parent_industrial_ved_name(ved.name):
            continue
        if _is_total_consumption_ved(ved):
            continue
        ved_name = _ved_section_display_name(ved)
        if not ved_name:
            continue
        reference_rows = [
            _build_reference_row(
                ref_kind=ref_kind,
                ved_id=ved.id,
                values_by_ved_year=value_maps[ref_kind],
                display_years=display_years,
                rounding_digits=rounding_digits,
                price_year=price_year,
            )
            for ref_kind in REF_ROW_KINDS
        ]
        has_ei_intensity_block, has_ei_model_block, ei_row_kinds = _ei_row_kinds_for_ved(
            ved, refdata_ids=refdata_ved_ids
        )
        has_ei_block = has_ei_intensity_block or has_ei_model_block
        section: dict[str, Any] = {
            "ved_id": ved.id,
            "ved_name": ved_name,
            "has_ei_block": has_ei_block,
            "has_ei_intensity_block": has_ei_intensity_block,
            "has_ei_model_block": has_ei_model_block,
            "reference_rows": reference_rows,
            "rows": [],
        }
        if has_ei_block:
            coef_a, db_coef_x = (None, None)
            if has_ei_model_block:
                coef_a, db_coef_x = coef_by_ved.get(ved.id, (None, None))
            values_by_kind_year = {
                (rk, year): ei_year_by_ved_kind_year.get((ved.id, rk, year))
                for rk in ei_row_kinds
                for year in display_years
            }
            ved_graph_point_db_years = _graph_point_db_years_from_fd_ved_map(
                ved.id, ei_year_by_ved_kind_year
            )
            active_row_defs = [rd for rd in row_defs if rd["row_kind"] in ei_row_kinds]
            section["rows"] = [
                _attach_row_cells(
                    rd,
                    values_by_kind_year,
                    display_years,
                    rounding_digits,
                    graph_point_db_years=(
                        ved_graph_point_db_years
                        if rd["row_kind"] == ROW_KIND_GRAPH_POINT
                        else None
                    ),
                )
                for rd in active_row_defs
            ]
            computed_x: Decimal | None = None
            computed_a: Decimal | None = None
            if ei_row_kinds:
                computed_x, computed_a = _enrich_ei_computed_rows(
                    section["rows"],
                    ved_id=ved.id,
                    consumption_by_ved_year=consumption_by_ved_year,
                    product_output_by_ved_year=product_output_by_ved_year,
                    accum_by_ved_year=accum_by_ved_year,
                    coef_a=coef_a,
                    coef_x=db_coef_x,
                    display_years=display_years,
                    rounding_digits=rounding_digits,
                    current_year=current_year,
                )
            if has_ei_model_block:
                _enrich_ved_consumption_plan_years(
                    section["reference_rows"],
                    ved_id=int(ved.id),
                    product_output_by_ved_year=product_output_by_ved_year,
                    accum_by_ved_year=accum_by_ved_year,
                    coef_a=_effective_coef_a(coef_a, computed_a),
                    coef_x=computed_x if computed_x is not None else db_coef_x,
                    display_years=display_years,
                    rounding_digits=rounding_digits,
                    current_year=current_year,
                )
                section.update(
                    _coef_display_fields(
                        coef_a,
                        computed_x,
                        rounding_digits,
                        coef_a_computed=computed_a,
                    )
                )
            scatter_chart = build_ei_section_scatter_chart(
                section,
                display_years=display_years,
                current_year=current_year,
            )
            if scatter_chart is not None:
                section["scatter_chart"] = scatter_chart
        if industrial_section is not None and ved.id in component_ved_ids:
            sections.append(industrial_section)
            industrial_section = None
        sections.append(section)
    return sections


def _merge_ved_year_maps(
    target: dict[tuple[int, int], Decimal | None],
    source: dict[tuple[int, int], Decimal | None],
) -> None:
    for key, val in source.items():
        if val is None:
            continue
        prev = target.get(key)
        target[key] = (prev or Decimal(0)) + val


def _sum_cell_dicts(
    *cell_dicts: dict[int, Decimal | None],
    display_years: list[int],
) -> dict[int, Decimal | None]:
    cells: dict[int, Decimal | None] = {}
    for year in display_years:
        total: Decimal | None = None
        has_any = False
        for cell_dict in cell_dicts:
            val = cell_dict.get(year)
            if val is not None:
                has_any = True
                total = (total or Decimal(0)) + val
        cells[year] = total if has_any else None
    return cells


def _compute_ved_intensity_cells_for_fd(
    *,
    ved_id: int,
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    ei_year_by_ved_kind_year: dict[tuple[int, str, int], Decimal | None],
    display_years: list[int],
    rounding_digits: int,
    current_year: int | None,
) -> dict[int, Decimal | None]:
    intensity_row_def = next(
        rd for rd in _build_row_defs() if rd["row_kind"] == ROW_KIND_INTENSITY
    )
    values_by_kind_year = {
        (ROW_KIND_INTENSITY, year): ei_year_by_ved_kind_year.get(
            (ved_id, ROW_KIND_INTENSITY, year)
        )
        for year in display_years
    }
    rows = [
        _attach_row_cells(
            intensity_row_def, values_by_kind_year, display_years, rounding_digits
        )
    ]
    _enrich_ei_computed_rows(
        rows,
        ved_id=ved_id,
        consumption_by_ved_year=consumption_by_ved_year,
        product_output_by_ved_year=product_output_by_ved_year,
        accum_by_ved_year=accum_by_ved_year,
        coef_a=None,
        coef_x=None,
        display_years=display_years,
        rounding_digits=rounding_digits,
        current_year=current_year,
    )
    return rows[0]["cells"]


def _compute_industrial_intensity_cells_for_fd(
    *,
    component_ved_ids: list[int],
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    display_years: list[int],
    rounding_digits: int,
    current_year: int | None,
) -> dict[int, Decimal | None]:
    synthetic_ved_id = 0
    cons_cells = _sum_values_by_ved_year_for_veds(
        component_ved_ids, consumption_by_ved_year, display_years
    )
    prod_cells = _sum_values_by_ved_year_for_veds(
        component_ved_ids, product_output_by_ved_year, display_years
    )
    accum_cells = _sum_values_by_ved_year_for_veds(
        component_ved_ids, accum_by_ved_year, display_years
    )
    return _compute_ved_intensity_cells_for_fd(
        ved_id=synthetic_ved_id,
        consumption_by_ved_year={
            (synthetic_ved_id, year): cons_cells.get(year) for year in display_years
        },
        product_output_by_ved_year={
            (synthetic_ved_id, year): prod_cells.get(year) for year in display_years
        },
        accum_by_ved_year={
            (synthetic_ved_id, year): accum_cells.get(year) for year in display_years
        },
        ei_year_by_ved_kind_year={},
        display_years=display_years,
        rounding_digits=rounding_digits,
        current_year=current_year,
    )


def _compute_rf_ved_intensity_cells_for_fd(
    *,
    ved_id: int,
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    ei_year_by_ved_kind_year: dict[tuple[int, str, int], Decimal | None],
    display_years: list[int],
    rounding_digits: int,
) -> dict[int, Decimal | None]:
    """Электроёмкость по ВЭД для агрегата РФ: все отображаемые годы (сумма по ФО)."""
    return _compute_ved_intensity_cells_for_fd(
        ved_id=ved_id,
        consumption_by_ved_year=consumption_by_ved_year,
        product_output_by_ved_year=product_output_by_ved_year,
        accum_by_ved_year=accum_by_ved_year,
        ei_year_by_ved_kind_year=ei_year_by_ved_kind_year,
        display_years=display_years,
        rounding_digits=rounding_digits,
        current_year=None,
    )


def _compute_rf_industrial_intensity_cells_for_fd(
    *,
    component_ved_ids: list[int],
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    display_years: list[int],
    rounding_digits: int,
) -> dict[int, Decimal | None]:
    synthetic_ved_id = 0
    cons_cells = _sum_values_by_ved_year_for_veds(
        component_ved_ids, consumption_by_ved_year, display_years
    )
    prod_cells = _sum_values_by_ved_year_for_veds(
        component_ved_ids, product_output_by_ved_year, display_years
    )
    accum_cells = _sum_values_by_ved_year_for_veds(
        component_ved_ids, accum_by_ved_year, display_years
    )
    return _compute_rf_ved_intensity_cells_for_fd(
        ved_id=synthetic_ved_id,
        consumption_by_ved_year={
            (synthetic_ved_id, year): cons_cells.get(year) for year in display_years
        },
        product_output_by_ved_year={
            (synthetic_ved_id, year): prod_cells.get(year) for year in display_years
        },
        accum_by_ved_year={
            (synthetic_ved_id, year): accum_cells.get(year) for year in display_years
        },
        ei_year_by_ved_kind_year={},
        display_years=display_years,
        rounding_digits=rounding_digits,
    )


def _aggregate_fd_maps_for_rf(
    *,
    version_id: int | None,
    ved_types: list[EconomicActivityType],
    display_years: list[int],
    rounding_digits: int,
    fd_filter_ids: frozenset[int],
    current_year: int | None,
) -> tuple[
    dict[tuple[int, int], Decimal | None],
    dict[tuple[int, int], Decimal | None],
    dict[int, dict[int, Decimal | None]],
    dict[int, dict[int, Decimal | None]] | None,
    dict[tuple[int, int], Decimal | None],
    dict[int, dict[int, Decimal | None]],
    dict[int, Decimal | None] | None,
]:
    """Суммы потребления/выпуска/инвестиций и электроёмкости по ВЭД, агрегированные по ФО."""
    agg_consumption: dict[tuple[int, int], Decimal | None] = {}
    agg_product: dict[tuple[int, int], Decimal | None] = {}
    agg_accum: dict[tuple[int, int], Decimal | None] = {}
    intensity_by_ved: dict[int, list[dict[int, Decimal | None]]] = {}
    calculated_by_ved: dict[int, list[dict[int, Decimal | None]]] = {}
    industrial_intensity_parts: list[dict[int, Decimal | None]] = []
    industrial_calculated_parts: list[dict[int, Decimal | None]] = []
    component_veds = _find_industrial_component_veds(ved_types)
    component_ved_ids = [int(v.id) for v in component_veds]
    refdata_ved_ids = _refdata_ved_ids(version_id)
    ved_by_id = {int(v.id): v for v in ved_types}

    for fd in _federal_districts_for_page():
        if fd_filter_ids and fd.id not in fd_filter_ids:
            continue
        fd_filter = FederalDistrictProductOutputParameter.id_federal_district == fd.id
        product_by_ved = _load_product_output_values_map(
            version_id=version_id,
            model=FederalDistrictProductOutputParameter,
            territory_filter=fd_filter,
        )
        consumption_by_ved = _load_ved_consumption_values_map(
            version_id=version_id,
            model=FederalDistrictEATConsumptionParameter,
            territory_filter=FederalDistrictEATConsumptionParameter.id_federal_district
            == fd.id,
        )
        accum_by_ved = _load_accum_fixed_capital_values_map(
            version_id=version_id,
            model=FederalDistrictAccumFixedCapitalParameter,
            territory_filter=FederalDistrictAccumFixedCapitalParameter.id_federal_district
            == fd.id,
        )
        ei_year_by_ved = _load_fd_ei_year_values_map(version_id=version_id, fd_id=fd.id)

        _merge_ved_year_maps(agg_consumption, consumption_by_ved)
        _merge_ved_year_maps(agg_product, product_by_ved)
        _merge_ved_year_maps(agg_accum, accum_by_ved)

        for ved in ved_types:
            if _is_parent_industrial_ved_name(ved.name):
                continue
            if _is_total_consumption_ved(ved):
                continue
            if not _ved_section_display_name(ved):
                continue
            ved_id = int(ved.id)
            intensity_cells = _compute_rf_ved_intensity_cells_for_fd(
                ved_id=ved_id,
                consumption_by_ved_year=consumption_by_ved,
                product_output_by_ved_year=product_by_ved,
                accum_by_ved_year=accum_by_ved,
                ei_year_by_ved_kind_year=ei_year_by_ved,
                display_years=display_years,
                rounding_digits=rounding_digits,
            )
            intensity_by_ved.setdefault(ved_id, []).append(intensity_cells)
            ved = ved_by_id.get(ved_id)
            if ved is not None:
                calc_cells = _compute_ved_calculated_cells_for_fd(
                    ved_id=ved_id,
                    fd_id=fd.id,
                    version_id=version_id,
                    ved=ved,
                    refdata_ved_ids=refdata_ved_ids,
                    consumption_by_ved_year=consumption_by_ved,
                    product_output_by_ved_year=product_by_ved,
                    accum_by_ved_year=accum_by_ved,
                    ei_year_by_ved_kind_year=ei_year_by_ved,
                    display_years=display_years,
                    rounding_digits=rounding_digits,
                    current_year=current_year,
                )
                if calc_cells is not None:
                    calculated_by_ved.setdefault(ved_id, []).append(calc_cells)

        if component_ved_ids:
            industrial_intensity_parts.append(
                _compute_rf_industrial_intensity_cells_for_fd(
                    component_ved_ids=component_ved_ids,
                    consumption_by_ved_year=consumption_by_ved,
                    product_output_by_ved_year=product_by_ved,
                    accum_by_ved_year=accum_by_ved,
                    display_years=display_years,
                    rounding_digits=rounding_digits,
                )
            )
            industrial_calc = _compute_industrial_calculated_cells_for_fd(
                component_ved_ids=component_ved_ids,
                consumption_by_ved_year=consumption_by_ved,
                product_output_by_ved_year=product_by_ved,
                accum_by_ved_year=accum_by_ved,
                display_years=display_years,
                rounding_digits=rounding_digits,
                current_year=current_year,
            )
            if industrial_calc is not None:
                industrial_calculated_parts.append(industrial_calc)

    intensity_cells_by_ved: dict[int, dict[int, Decimal | None]] = {
        ved_id: _sum_cell_dicts(*parts, display_years=display_years)
        for ved_id, parts in intensity_by_ved.items()
    }
    industrial_intensity = (
        _sum_cell_dicts(*industrial_intensity_parts, display_years=display_years)
        if industrial_intensity_parts
        else None
    )
    calculated_cells_by_ved: dict[int, dict[int, Decimal | None]] = {
        ved_id: _sum_cell_dicts(*parts, display_years=display_years)
        for ved_id, parts in calculated_by_ved.items()
    }
    industrial_calculated = (
        _sum_cell_dicts(*industrial_calculated_parts, display_years=display_years)
        if industrial_calculated_parts
        else None
    )
    return (
        agg_consumption,
        agg_product,
        intensity_cells_by_ved,
        industrial_intensity,
        agg_accum,
        calculated_cells_by_ved,
        industrial_calculated,
    )


def _build_rf_ved_reference_row(
    *,
    ref_kind: str,
    ved_id: int,
    values_by_ved_year: dict[tuple[int, int], Decimal | None],
    display_years: list[int],
    rounding_digits: int,
    price_year: int,
) -> dict[str, Any]:
    cells = {
        year: values_by_ved_year.get((ved_id, year)) for year in display_years
    }
    if ref_kind == REF_ROW_PRODUCT_OUTPUT:
        cells = _scale_cells_by_factor(cells, factor=EI_BILLION_KWH_FACTOR)
        row_label = rf_ved_product_output_row_label(price_year)
        unit_label = REF_ROW_RF_VED_UNIT_BY_KIND[REF_ROW_PRODUCT_OUTPUT]
    else:
        row_label = ref_row_label(ref_kind)
        unit_label = REF_ROW_RF_VED_UNIT_BY_KIND.get(
            ref_kind, REF_ROW_UNIT_BY_KIND.get(ref_kind, "")
        )
    formula_key = REF_ROW_RF_VED_FORMULA_KEY_BY_KIND.get(ref_kind, "")
    return {
        "row_kind": ref_kind,
        "row_label": row_label,
        "unit_label": unit_label,
        "row_css": REF_ROW_CSS_BY_KIND.get(ref_kind, ""),
        "is_readonly": True,
        "is_computed": True,
        "source_endpoint": REF_ROW_SOURCE_ENDPOINT.get(ref_kind, ""),
        "source_page_title": REF_ROW_SOURCE_PAGE_TITLE.get(ref_kind, ""),
        "formula_hint": ei_formula_text(formula_key) if formula_key else "",
        "cells": cells,
        "cell_tooltips": {
            year: _format_full_numeric_tooltip(cells.get(year)) for year in display_years
        },
        "cells_display": {
            year: _format_cell_display(cells.get(year), rounding_digits)
            for year in display_years
        },
    }


def _build_rf_ved_intensity_row(
    *,
    cells: dict[int, Decimal | None],
    display_years: list[int],
    rounding_digits: int,
) -> dict[str, Any]:
    intensity_row_def = next(
        rd for rd in _build_row_defs() if rd["row_kind"] == ROW_KIND_INTENSITY
    )
    row_def = {
        **intensity_row_def,
        "row_label": RF_VED_INTENSITY_ROW_LABEL,
        "formula_hint": ei_formula_text("ei_rf_ved_intensity"),
        "is_computed": True,
    }
    out = {**row_def, "cells": cells}
    out["cell_tooltips"] = {
        year: _format_cell_tooltip(cells.get(year), row_kind=ROW_KIND_INTENSITY)
        for year in display_years
    }
    display_rd = _ei_display_digits_for_row(ROW_KIND_INTENSITY, rounding_digits)
    out["cells_display"] = {
        year: _format_cell_display(cells.get(year), display_rd)
        for year in display_years
    }
    return out


def _build_rf_industrial_group_section(
    *,
    component_ved_ids: list[int],
    consumption_by_ved_year: dict[tuple[int, int], Decimal | None],
    product_output_by_ved_year: dict[tuple[int, int], Decimal | None],
    accum_by_ved_year: dict[tuple[int, int], Decimal | None],
    intensity_cells: dict[int, Decimal | None],
    calculated_cells: dict[int, Decimal | None] | None,
    display_years: list[int],
    rounding_digits: int,
    price_year: int,
    current_year: int | None,
) -> dict[str, Any]:
    synthetic_ved_id = 0
    cons_cells = _sum_values_by_ved_year_for_veds(
        component_ved_ids, consumption_by_ved_year, display_years
    )
    prod_cells = _sum_values_by_ved_year_for_veds(
        component_ved_ids, product_output_by_ved_year, display_years
    )
    synthetic_consumption = {
        (synthetic_ved_id, year): cons_cells.get(year) for year in display_years
    }
    synthetic_product = {
        (synthetic_ved_id, year): prod_cells.get(year) for year in display_years
    }
    accum_cells = _sum_values_by_ved_year_for_veds(
        component_ved_ids, accum_by_ved_year, display_years
    )
    synthetic_accum = {
        (synthetic_ved_id, year): accum_cells.get(year) for year in display_years
    }
    reference_rows = [
        _build_rf_ved_reference_row(
            ref_kind=REF_ROW_CONSUMPTION,
            ved_id=synthetic_ved_id,
            values_by_ved_year=synthetic_consumption,
            display_years=display_years,
            rounding_digits=rounding_digits,
            price_year=price_year,
        ),
        _build_rf_ved_reference_row(
            ref_kind=REF_ROW_PRODUCT_OUTPUT,
            ved_id=synthetic_ved_id,
            values_by_ved_year=synthetic_product,
            display_years=display_years,
            rounding_digits=rounding_digits,
            price_year=price_year,
        ),
        _build_rf_ved_reference_row(
            ref_kind=REF_ROW_ACCUM_FIXED_CAPITAL,
            ved_id=synthetic_ved_id,
            values_by_ved_year=synthetic_accum,
            display_years=display_years,
            rounding_digits=rounding_digits,
            price_year=price_year,
        ),
    ]
    section: dict[str, Any] = {
        "ved_id": None,
        "ved_name": INDUSTRIAL_GROUP_SECTION_LABEL,
        "is_industrial_group": True,
        "has_ei_block": True,
        "has_ei_intensity_block": True,
        "has_ei_model_block": False,
        "reference_rows": reference_rows,
        "rows": [
            _build_rf_ved_intensity_row(
                cells=intensity_cells,
                display_years=display_years,
                rounding_digits=rounding_digits,
            )
        ],
        "unit_label": "кВт.ч./тыс.руб.",
    }
    _attach_rf_section_scatter_chart(
        section,
        display_years=display_years,
        current_year=current_year,
        calculated_cells=calculated_cells,
    )
    return section


def _build_ved_sections_for_rf(
    *,
    version_id: int | None,
    ved_types: list[EconomicActivityType],
    display_years: list[int],
    rounding_digits: int,
    coeff_base_year: int,
    current_year: int | None,
    fd_filter_ids: frozenset[int],
) -> list[dict[str, Any]]:
    price_year = _resolve_price_year_for_rf_labels(version_id, coeff_base_year)
    (
        consumption_by_ved_year,
        product_output_by_ved_year,
        intensity_cells_by_ved,
        industrial_intensity,
        accum_by_ved_year,
        calculated_cells_by_ved,
        industrial_calculated,
    ) = _aggregate_fd_maps_for_rf(
        version_id=version_id,
        ved_types=ved_types,
        display_years=display_years,
        rounding_digits=rounding_digits,
        fd_filter_ids=fd_filter_ids,
        current_year=current_year,
    )

    household_ved = _find_ved_by_target(ved_types, HOUSEHOLD_VED_TARGET)
    household_ved_id = int(household_ved.id) if household_ved is not None else None
    component_veds = _find_industrial_component_veds(ved_types)
    component_ved_ids = [int(v.id) for v in component_veds]
    sections: list[dict[str, Any]] = []
    industrial_section: dict[str, Any] | None = None
    if component_ved_ids and industrial_intensity is not None:
        industrial_section = _build_rf_industrial_group_section(
            component_ved_ids=component_ved_ids,
            consumption_by_ved_year=consumption_by_ved_year,
            product_output_by_ved_year=product_output_by_ved_year,
            accum_by_ved_year=accum_by_ved_year,
            intensity_cells=industrial_intensity,
            calculated_cells=industrial_calculated,
            display_years=display_years,
            rounding_digits=rounding_digits,
            price_year=price_year,
            current_year=current_year,
        )

    for ved in ved_types:
        if _is_parent_industrial_ved_name(ved.name):
            continue
        if _is_total_consumption_ved(ved):
            continue
        ved_id = int(ved.id)
        if household_ved_id is not None and ved_id == household_ved_id:
            continue
        ved_name = _ved_section_display_name(ved)
        if not ved_name:
            continue
        reference_rows = [
            _build_rf_ved_reference_row(
                ref_kind=ref_kind,
                ved_id=ved_id,
                values_by_ved_year=(
                    consumption_by_ved_year
                    if ref_kind == REF_ROW_CONSUMPTION
                    else product_output_by_ved_year
                    if ref_kind == REF_ROW_PRODUCT_OUTPUT
                    else accum_by_ved_year
                ),
                display_years=display_years,
                rounding_digits=rounding_digits,
                price_year=price_year,
            )
            for ref_kind in RF_VED_REF_ROW_KINDS
        ]
        section: dict[str, Any] = {
            "ved_id": ved_id,
            "ved_name": ved_name,
            "has_ei_block": True,
            "has_ei_intensity_block": True,
            "has_ei_model_block": False,
            "reference_rows": reference_rows,
            "rows": [
                _build_rf_ved_intensity_row(
                    cells=intensity_cells_by_ved.get(ved_id, {}),
                    display_years=display_years,
                    rounding_digits=rounding_digits,
                )
            ],
            "unit_label": "кВт.ч./тыс.руб.",
        }
        _attach_rf_section_scatter_chart(
            section,
            display_years=display_years,
            current_year=current_year,
            calculated_cells=calculated_cells_by_ved.get(ved_id),
        )
        if industrial_section is not None and ved_id in component_ved_ids:
            sections.append(industrial_section)
            industrial_section = None
        sections.append(section)
    return sections


def _aggregate_rf_household_and_population_by_year(
    *,
    version_id: int | None,
    ved_types: list[EconomicActivityType],
    display_years: list[int],
    fd_filter_ids: frozenset[int],
) -> tuple[dict[int, Decimal | None], dict[int, Decimal | None]]:
    """Суммы потребления в домашних хозяйствах и численности населения по ФО."""
    household_ved = _find_ved_by_target(ved_types, HOUSEHOLD_VED_TARGET)
    household_ved_id = int(household_ved.id) if household_ved is not None else None
    household_by_year: dict[int, Decimal | None] = {
        year: None for year in display_years
    }
    population_by_year: dict[int, Decimal | None] = {
        year: None for year in display_years
    }

    for fd in _federal_districts_for_page():
        if fd_filter_ids and fd.id not in fd_filter_ids:
            continue
        fd_population = _load_population_by_fd_year(version_id=version_id, fd_id=fd.id)
        for year in display_years:
            pop_val = fd_population.get(year)
            if pop_val is not None:
                prev = population_by_year.get(year)
                population_by_year[year] = (prev or Decimal(0)) + pop_val

        if household_ved_id is None:
            continue
        consumption_by_ved = _load_ved_consumption_values_map(
            version_id=version_id,
            model=FederalDistrictEATConsumptionParameter,
            territory_filter=FederalDistrictEATConsumptionParameter.id_federal_district
            == fd.id,
        )
        for year in display_years:
            hh_val = consumption_by_ved.get((household_ved_id, year))
            if hh_val is not None:
                prev = household_by_year.get(year)
                household_by_year[year] = (prev or Decimal(0)) + hh_val

    return household_by_year, population_by_year


def _build_rf_population_per_capita_row(
    *,
    household_by_year: dict[int, Decimal | None],
    population_by_year: dict[int, Decimal | None],
    display_years: list[int],
    rounding_digits: int,
) -> dict[str, Any]:
    cells: dict[int, Decimal | None] = {}
    for year in display_years:
        raw = _compute_pop_per_capita_consumption(
            household_by_year.get(year),
            population_by_year.get(year),
        )
        cells[year] = raw
    row_def = {
        "row_kind": ROW_KIND_INTENSITY,
        "row_label": POP_ROW_LABEL_BY_KIND[ROW_KIND_INTENSITY],
        "row_css": "lt-ei-row-intensity",
        "formula_hint": ei_formula_text("ei_rf_pop_per_capita"),
        "is_computed": True,
    }
    out = {**row_def, "cells": cells}
    out["cell_tooltips"] = {
        year: _format_cell_tooltip(cells.get(year), row_kind=ROW_KIND_INTENSITY)
        for year in display_years
    }
    display_rd = _ei_display_digits_for_row(ROW_KIND_INTENSITY, rounding_digits)
    out["cells_display"] = {
        year: _format_cell_display(cells.get(year), display_rd)
        for year in display_years
    }
    return out


def _build_population_section_for_rf(
    *,
    version_id: int | None,
    ved_types: list[EconomicActivityType],
    display_years: list[int],
    rounding_digits: int,
    fd_filter_ids: frozenset[int],
    current_year: int | None,
) -> dict[str, Any]:
    household_by_year, population_by_year = _aggregate_rf_household_and_population_by_year(
        version_id=version_id,
        ved_types=ved_types,
        display_years=display_years,
        fd_filter_ids=fd_filter_ids,
    )
    accum_income_by_year: dict[int, Decimal | None] = {
        year: None for year in display_years
    }
    for fd in _federal_districts_for_page():
        if fd_filter_ids and fd.id not in fd_filter_ids:
            continue
        fd_accum_income = _load_accum_monetary_income_by_fd_year(
            version_id=version_id, fd_id=fd.id
        )
        for year in display_years:
            val = fd_accum_income.get(year)
            if val is not None:
                prev = accum_income_by_year.get(year)
                accum_income_by_year[year] = (prev or Decimal(0)) + val
    household_row = _build_population_reference_row(
        ref_kind=REF_ROW_HOUSEHOLD_CONSUMPTION,
        cells_by_year=household_by_year,
        display_years=display_years,
        rounding_digits=rounding_digits,
        is_computed=True,
    )
    household_row["formula_hint"] = ei_formula_text("ei_rf_pop_household_consumption")
    population_row = _build_population_reference_row(
        ref_kind=REF_ROW_POPULATION,
        cells_by_year=population_by_year,
        display_years=display_years,
        rounding_digits=rounding_digits,
    )
    population_row["formula_hint"] = ei_formula_text("ei_rf_pop_population")
    section: dict[str, Any] = {
        "ved_id": POPULATION_SECTION_MARKER,
        "ved_name": POPULATION_SECTION_LABEL,
        "is_population_section": True,
        "has_ei_block": True,
        "has_ei_intensity_block": True,
        "has_ei_model_block": False,
        "reference_rows": [
            household_row,
            population_row,
            _build_population_reference_row(
                ref_kind=REF_ROW_ACCUM_MONETARY_INCOME,
                cells_by_year=accum_income_by_year,
                display_years=display_years,
                rounding_digits=rounding_digits,
            ),
        ],
        "rows": [
            _build_rf_population_per_capita_row(
                household_by_year=household_by_year,
                population_by_year=population_by_year,
                display_years=display_years,
                rounding_digits=rounding_digits,
            )
        ],
        "unit_label": "тыс. кВт.ч./чел.",
    }
    population_calculated_parts: list[dict[int, Decimal | None]] = []
    for fd in _federal_districts_for_page():
        if fd_filter_ids and fd.id not in fd_filter_ids:
            continue
        consumption_by_ved = _load_ved_consumption_values_map(
            version_id=version_id,
            model=FederalDistrictEATConsumptionParameter,
            territory_filter=FederalDistrictEATConsumptionParameter.id_federal_district
            == fd.id,
        )
        fd_calc = _compute_population_calculated_cells_for_fd(
            fd_id=fd.id,
            version_id=version_id,
            ved_types=ved_types,
            consumption_by_ved_year=consumption_by_ved,
            display_years=display_years,
            rounding_digits=rounding_digits,
            current_year=current_year,
        )
        if fd_calc is not None:
            population_calculated_parts.append(fd_calc)
    population_calculated = (
        _sum_cell_dicts(*population_calculated_parts, display_years=display_years)
        if population_calculated_parts
        else None
    )
    _attach_rf_section_scatter_chart(
        section,
        display_years=display_years,
        current_year=current_year,
        calculated_cells=population_calculated,
    )
    return section


def _territory_block(
    *,
    territory_kind: str,
    territory_id: int | None,
    label: str,
    abbr: str,
    values_by_kind_year: dict[tuple[str, int], Decimal | None],
    coef_a: Decimal | None,
    coef_x: Decimal | None,
    display_years: list[int],
    rounding_digits: int,
    ved_sections: list[dict[str, Any]] | None = None,
    fd_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row_defs = _build_row_defs()
    flat_graph_point_db_years = _graph_point_db_years_from_kind_year_map(
        values_by_kind_year
    )
    rows = [
        _attach_row_cells(
            rd,
            values_by_kind_year,
            display_years,
            rounding_digits,
            graph_point_db_years=(
                flat_graph_point_db_years
                if rd["row_kind"] == ROW_KIND_GRAPH_POINT
                else None
            ),
        )
        for rd in row_defs
    ]
    layout = "ved_sections" if ved_sections is not None else "flat"
    return {
        "territory_kind": territory_kind,
        "territory_id": territory_id,
        "label": label,
        "abbr": abbr,
        "layout": layout,
        **_coef_display_fields(coef_a, coef_x, rounding_digits),
        "fd_summary": fd_summary,
        "ved_sections": ved_sections or [],
        "rows": rows,
    }


def build_electrical_intensity_page_context(
    *,
    rounding_digits: int = 1,
    start_year: int,
    end_year: int,
    display_years: list[int],
    filter_year_list: list[int],
    coeff_base_year: int,
    summary_include_medium_years: bool,
    summary_include_long_years: bool = False,
    fd_filter_ids: frozenset[int],
    ved_filter_ids: frozenset[int],
    population_filter_selected: bool = False,
    has_active_filters: bool,
) -> dict[str, Any]:
    version_id = get_current_version()
    current_year = _ei_current_year_number()
    all_ved_types = _refdata_ved_types_for_version(version_id)
    refdata_ved_ids = frozenset(int(v.id) for v in all_ved_types)
    any_ved_filter = bool(ved_filter_ids) or population_filter_selected
    show_ved_sections = not any_ved_filter or bool(ved_filter_ids)
    show_population_section = not any_ved_filter or population_filter_selected
    if ved_filter_ids:
        ved_types = [v for v in all_ved_types if v.id in ved_filter_ids]
    elif population_filter_selected:
        ved_types = []
    else:
        ved_types = all_ved_types
    territory_blocks: list[dict[str, Any]] = []
    fd_territory_blocks: list[dict[str, Any]] = []
    fd_summaries_for_rf: list[dict[str, Any]] = []

    show_rf_block = show_ved_sections or show_population_section

    for fd in _federal_districts_for_page():
        if fd_filter_ids and fd.id not in fd_filter_ids:
            continue
        ei_year_by_ved = _load_fd_ei_year_values_map(version_id=version_id, fd_id=fd.id)
        coef_by_ved = _load_fd_ei_coef_map(version_id=version_id, fd_id=fd.id)
        fd_filter = (
            FederalDistrictProductOutputParameter.id_federal_district
            == fd.id
        )
        # Те же таблицы и поля, что на /economics/product_output/
        product_by_ved = _load_product_output_values_map(
            version_id=version_id,
            model=FederalDistrictProductOutputParameter,
            territory_filter=fd_filter,
        )
        # /economics/ved_consumption/
        consumption_by_ved = _load_ved_consumption_values_map(
            version_id=version_id,
            model=FederalDistrictEATConsumptionParameter,
            territory_filter=FederalDistrictEATConsumptionParameter.id_federal_district
            == fd.id,
        )
        # /economics/accum_fixed_capital/
        accum_by_ved = _load_accum_fixed_capital_values_map(
            version_id=version_id,
            model=FederalDistrictAccumFixedCapitalParameter,
            territory_filter=FederalDistrictAccumFixedCapitalParameter.id_federal_district
            == fd.id,
        )
        price_year = _resolve_price_year_for_ref_labels(
            version_id, fd.id, coeff_base_year
        )
        ved_sections: list[dict[str, Any]] = []
        if show_ved_sections:
            ved_sections = _build_ved_sections_for_fd(
                ved_types=ved_types,
                refdata_ved_ids=refdata_ved_ids,
                product_output_by_ved_year=product_by_ved,
                consumption_by_ved_year=consumption_by_ved,
                accum_by_ved_year=accum_by_ved,
                ei_year_by_ved_kind_year=ei_year_by_ved,
                coef_by_ved=coef_by_ved,
                display_years=display_years,
                rounding_digits=rounding_digits,
                price_year=price_year,
                current_year=current_year,
            )
        if show_population_section:
            ved_sections.append(
                _build_population_section_for_fd(
                    fd_id=fd.id,
                    version_id=version_id,
                    ved_types=all_ved_types,
                    consumption_by_ved_year=consumption_by_ved,
                    display_years=display_years,
                    rounding_digits=rounding_digits,
                    current_year=current_year,
                )
            )
        fd_summary = (
            _build_fd_territory_summary(
                fd_id=fd.id,
                version_id=version_id,
                ved_types=ved_types,
                product_output_by_ved_year=product_by_ved,
                consumption_by_ved_year=consumption_by_ved,
                accum_by_ved_year=accum_by_ved,
                coef_by_ved=coef_by_ved,
                display_years=display_years,
                rounding_digits=rounding_digits,
                price_year=price_year,
                current_year=current_year,
                year_features=get_year_feature_dict() or {},
                ved_sections=ved_sections,
            )
            if show_ved_sections
            else None
        )
        if fd_summary is not None:
            fd_summaries_for_rf.append(fd_summary)
        fd_territory_blocks.append(
            _territory_block(
                territory_kind="fd",
                territory_id=fd.id,
                label=fd.name_full or fd.name,
                abbr=fd.name_abr or fd.name,
                values_by_kind_year={},
                coef_a=None,
                coef_x=None,
                display_years=display_years,
                rounding_digits=rounding_digits,
                ved_sections=ved_sections,
                fd_summary=fd_summary,
            )
        )

    rf_summary = (
        _build_rf_territory_summary(
            version_id=version_id,
            ved_types=all_ved_types,
            display_years=display_years,
            rounding_digits=rounding_digits,
            coeff_base_year=coeff_base_year,
            fd_filter_ids=fd_filter_ids,
            current_year=current_year,
            fd_summaries=fd_summaries_for_rf if show_ved_sections else None,
        )
        if show_rf_block
        else None
    )
    rf_ved_sections: list[dict[str, Any]] = []
    if show_ved_sections:
        rf_ved_sections = _build_ved_sections_for_rf(
            version_id=version_id,
            ved_types=ved_types,
            display_years=display_years,
            rounding_digits=rounding_digits,
            coeff_base_year=coeff_base_year,
            current_year=current_year,
            fd_filter_ids=fd_filter_ids,
        )
    if show_rf_block:
        rf_ved_sections.append(
            _build_population_section_for_rf(
                version_id=version_id,
                ved_types=all_ved_types,
                display_years=display_years,
                rounding_digits=rounding_digits,
                fd_filter_ids=fd_filter_ids,
                current_year=current_year,
            )
        )
    rf_block = _territory_block(
        territory_kind="rf",
        territory_id=None,
        label="Российская Федерация",
        abbr="РФ",
        values_by_kind_year={},
        coef_a=None,
        coef_x=None,
        display_years=display_years,
        rounding_digits=rounding_digits,
        ved_sections=rf_ved_sections if show_rf_block else None,
    )
    rf_block["has_ei_model_block"] = False
    rf_block["rows"] = []
    if rf_summary is not None:
        rf_block["fd_summary"] = rf_summary
    if show_rf_block:
        territory_blocks.append(rf_block)
    territory_blocks.extend(fd_territory_blocks)

    federal_district_list = [
        {"id": x.id, "name": x.name}
        for x in get_federal_district_list_full()
        if not _is_federal_district_excluded(x)
    ]
    economic_activity_type_list = []
    for v in all_ved_types:
        display_name = _ved_section_display_name(v)
        if display_name:
            economic_activity_type_list.append({"id": v.id, "name": display_name})
    economic_activity_type_list.append(
        {"id": POPULATION_SECTION_MARKER, "name": POPULATION_SECTION_LABEL}
    )

    from app.electrical_intensity.services.electrical_intensity_diagnostic_services import (
        attach_electrical_intensity_diagnostics_to_blocks,
    )

    attach_electrical_intensity_diagnostics_to_blocks(
        territory_blocks,
        display_years=display_years,
        current_year=current_year,
    )

    return {
        "page_title": "Электроемкость по ФО",
        "years": display_years,
        "display_years": display_years,
        "year_features": get_year_feature_dict() or {},
        "filter_year_list": filter_year_list,
        "start_year": start_year,
        "end_year": end_year,
        "coeff_base_year": coeff_base_year,
        "summary_include_medium_years": summary_include_medium_years,
        "summary_include_long_years": summary_include_long_years,
        "lt_ei_year_segments": True,
        "territory_blocks": territory_blocks,
        "federal_district_list": federal_district_list,
        "economic_activity_type_list": economic_activity_type_list,
        "has_active_filters": has_active_filters,
        "rounding_digits": rounding_digits,
        "ei_current_year": current_year,
        "formula_hints": {
            "coefficient_a": ei_formula_text("ei_coefficient_a"),
            "coefficient_a_computed": ei_formula_text("ei_coefficient_a_computed"),
            "coefficient_x": ei_formula_text("ei_coefficient_x"),
        },
        "unit_label": "кВт.ч./тыс.руб.",
    }


def _save_population_graph_point_cell(
    *,
    version_id: int | None,
    user: str,
    fd_id: int,
    year_n: int,
    dec: Decimal,
    territory_cache: dict[tuple[str, int | None, int | None], str],
) -> bool:
    row = _get_or_create_population_year_row(
        version_id, fd_id, ROW_KIND_GRAPH_POINT, year_n, user
    )
    old_val = row.parameter_value
    if is_same_decimal(to_decimal(old_val), to_decimal(dec)):
        return False
    row.parameter_value = dec
    row.modified_by = user
    terr_key = ("fd", fd_id, None)
    if terr_key not in territory_cache:
        territory_cache[terr_key] = (
            f"{_territory_label_for_log('fd', fd_id)}, блок={POPULATION_SECTION_LABEL}"
        )
    log_electrical_intensity_cell_change(
        user,
        detail_chunks=[
            f"территория={territory_cache[terr_key]}",
            f"показатель={POP_ROW_LABEL_BY_KIND.get(ROW_KIND_GRAPH_POINT, ROW_KIND_GRAPH_POINT)}",
            f"год={year_n}",
            f"значение: {_fmt_log_value(old_val)} → {_fmt_log_value(dec)}",
        ],
        database_version_id=version_id,
    )
    return True


def _save_graph_point_cell(
    *,
    version_id: int | None,
    user: str,
    kind: str,
    fd_id: int | None,
    ved_id: int | None,
    year_n: int,
    dec: Decimal,
    territory_cache: dict[tuple[str, int | None, int | None], str],
) -> bool:
    """Записать одну ячейку graph_point в БД; True если значение изменилось."""
    if kind == "rf":
        row = _get_or_create_rf_year_row(version_id, ROW_KIND_GRAPH_POINT, year_n, user)
    elif kind == "fd" and fd_id is not None and ved_id is not None:
        row = _get_or_create_fd_year_row(
            version_id, fd_id, ved_id, ROW_KIND_GRAPH_POINT, year_n, user
        )
    else:
        return False

    old_val = row.parameter_value
    if is_same_decimal(to_decimal(old_val), to_decimal(dec)):
        return False

    row.parameter_value = dec
    row.modified_by = user
    terr_key = (kind, fd_id, ved_id)
    if terr_key not in territory_cache:
        parts = [_territory_label_for_log(kind, fd_id)]
        ved_part = _ved_label_for_log(ved_id)
        if ved_part:
            parts.append(f"ВЭД={ved_part}")
        territory_cache[terr_key] = ", ".join(parts)
    log_electrical_intensity_cell_change(
        user,
        detail_chunks=[
            f"территория={territory_cache[terr_key]}",
            f"показатель={ROW_LABEL_BY_KIND.get(ROW_KIND_GRAPH_POINT, ROW_KIND_GRAPH_POINT)}",
            f"год={year_n}",
            f"значение: {_fmt_log_value(old_val)} → {_fmt_log_value(dec)}",
        ],
        database_version_id=version_id,
    )
    return True


def calculate_and_save_all_graph_points(
    *,
    rounding_digits: int,
    display_years: list[int],
    fd_filter_ids: frozenset[int],
    ved_filter_ids: frozenset[int],
    population_filter_selected: bool = False,
) -> tuple[int, int]:
    """Рассчитать все «Характерные точки графика» (годы ≤ текущего) и сохранить в БД."""
    version_id = get_current_version()
    current_year = _ei_current_year_number()
    user = _username()
    all_ved_types = _refdata_ved_types_for_version(version_id)
    any_ved_filter = bool(ved_filter_ids) or population_filter_selected
    show_ved_sections = not any_ved_filter or bool(ved_filter_ids)
    show_population_section = not any_ved_filter or population_filter_selected
    if ved_filter_ids:
        ved_types = [v for v in all_ved_types if v.id in ved_filter_ids]
    elif population_filter_selected:
        ved_types = []
    else:
        ved_types = all_ved_types
    total_ved_id = _find_total_ved_id(ved_types)
    updated = 0
    skipped = 0
    territory_cache: dict[tuple[str, int | None, int | None], str] = {}

    if show_ved_sections and total_ved_id is not None:
        consumption_by_ved = _load_ved_consumption_values_map(
            version_id=version_id,
            model=RussiaFederationConsumptionParameter,
        )
        product_by_ved = _load_product_output_values_map(
            version_id=version_id,
            model=RussiaFederationProductOutputParameter,
        )
        accum_by_ved = _load_accum_fixed_capital_values_map(
            version_id=version_id,
            model=RussiaFederationAccumFixedCapitalParameter,
        )
        rf_values = _load_year_values_map(
            version_id=version_id,
            model=RussiaFederationElectricalIntensityYearParameter,
        )
        rf_row_defs = _build_row_defs()
        rf_rows = [
            _attach_row_cells(rd, rf_values, display_years, rounding_digits)
            for rd in rf_row_defs
        ]
        for year, dec in _force_compute_graph_points_for_rows(
            rf_rows,
            ved_id=total_ved_id,
            consumption_by_ved_year=consumption_by_ved,
            product_output_by_ved_year=product_by_ved,
            accum_by_ved_year=accum_by_ved,
            display_years=display_years,
            rounding_digits=rounding_digits,
            current_year=current_year,
        ):
            if _save_graph_point_cell(
                version_id=version_id,
                user=user,
                kind="rf",
                fd_id=None,
                ved_id=None,
                year_n=year,
                dec=dec,
                territory_cache=territory_cache,
            ):
                updated += 1
            else:
                skipped += 1

    refdata_ved_ids = _refdata_ved_ids(version_id)
    for fd in _federal_districts_for_page():
        if fd_filter_ids and fd.id not in fd_filter_ids:
            continue
        fd_filter = FederalDistrictProductOutputParameter.id_federal_district == fd.id
        product_by_ved = _load_product_output_values_map(
            version_id=version_id,
            model=FederalDistrictProductOutputParameter,
            territory_filter=fd_filter,
        )
        consumption_by_ved = _load_ved_consumption_values_map(
            version_id=version_id,
            model=FederalDistrictEATConsumptionParameter,
            territory_filter=FederalDistrictEATConsumptionParameter.id_federal_district
            == fd.id,
        )
        accum_by_ved = _load_accum_fixed_capital_values_map(
            version_id=version_id,
            model=FederalDistrictAccumFixedCapitalParameter,
            territory_filter=FederalDistrictAccumFixedCapitalParameter.id_federal_district
            == fd.id,
        )
        ei_year_by_ved = _load_fd_ei_year_values_map(version_id=version_id, fd_id=fd.id)
        coef_by_ved = _load_fd_ei_coef_map(version_id=version_id, fd_id=fd.id)
        if show_ved_sections:
            row_defs = _build_row_defs()
            for ved in ved_types:
                if not ved.name:
                    continue
                _, has_ei_model_block, ei_row_kinds = _ei_row_kinds_for_ved(
                    ved, refdata_ids=refdata_ved_ids
                )
                if not has_ei_model_block or ROW_KIND_GRAPH_POINT not in ei_row_kinds:
                    continue
                values_by_kind_year = {
                    (rk, year): ei_year_by_ved.get((ved.id, rk, year))
                    for rk in ei_row_kinds
                    for year in display_years
                }
                active_row_defs = [rd for rd in row_defs if rd["row_kind"] in ei_row_kinds]
                section_rows = [
                    _attach_row_cells(rd, values_by_kind_year, display_years, rounding_digits)
                    for rd in active_row_defs
                ]
                for year, dec in _force_compute_graph_points_for_rows(
                    section_rows,
                    ved_id=ved.id,
                    consumption_by_ved_year=consumption_by_ved,
                    product_output_by_ved_year=product_by_ved,
                    accum_by_ved_year=accum_by_ved,
                    display_years=display_years,
                    rounding_digits=rounding_digits,
                    current_year=current_year,
                ):
                    if _save_graph_point_cell(
                        version_id=version_id,
                        user=user,
                        kind="fd",
                        fd_id=fd.id,
                        ved_id=ved.id,
                        year_n=year,
                        dec=dec,
                        territory_cache=territory_cache,
                    ):
                        updated += 1
                    else:
                        skipped += 1

        if not show_population_section:
            continue

        household_ved = _find_ved_by_target(
            _refdata_ved_types_for_version(version_id), HOUSEHOLD_VED_TARGET
        )
        household_ved_id = int(household_ved.id) if household_ved is not None else None
        household_by_year = {
            year: (
                consumption_by_ved.get((household_ved_id, year))
                if household_ved_id is not None
                else None
            )
            for year in display_years
        }
        population_by_year = _load_population_by_fd_year(
            version_id=version_id, fd_id=fd.id
        )
        accum_income_by_year = _load_accum_monetary_income_by_fd_year(
            version_id=version_id, fd_id=fd.id
        )
        pop_year_values = _load_population_year_values_map(
            version_id=version_id, fd_id=fd.id
        )
        pop_row_defs = _build_population_row_defs()
        pop_rows = [
            _attach_row_cells(rd, pop_year_values, display_years, rounding_digits)
            for rd in pop_row_defs
        ]
        for year, dec in _force_compute_population_graph_points_for_rows(
            pop_rows,
            household_consumption_by_year=household_by_year,
            population_by_year=population_by_year,
            accum_income_by_year=accum_income_by_year,
            display_years=display_years,
            rounding_digits=rounding_digits,
            current_year=current_year,
        ):
            if _save_population_graph_point_cell(
                version_id=version_id,
                user=user,
                fd_id=fd.id,
                year_n=year,
                dec=dec,
                territory_cache=territory_cache,
            ):
                updated += 1
            else:
                skipped += 1

    if updated:
        from app.common.services.economics_fd_data_cache import (
            invalidate_economics_fd_data_cache,
        )

        invalidate_economics_fd_data_cache(
            version_id,
            "ei_year",
            "pop_ei_year",
        )

    return updated, skipped


def _ei_row_calc_json_payload(gp_row: dict[str, Any], *, display_years: list[int]) -> dict[str, Any]:
    """Сериализация строки graph_point для AJAX (ключи годов — строки)."""
    current_year = _ei_current_year_number()
    computed_years = _ei_years_through_current(display_years, current_year)
    cells: dict[str, str] = {}
    cells_display: dict[str, str] = {}
    cell_tooltips: dict[str, str] = {}
    for year in computed_years:
        if year not in (gp_row.get("cells") or {}):
            continue
        val = gp_row["cells"].get(year)
        if val is None:
            continue
        key = str(year)
        cells[key] = str(val)
        cells_display[key] = gp_row.get("cells_display", {}).get(year, "—")
        cell_tooltips[key] = gp_row.get("cell_tooltips", {}).get(year, "")
    diag_raw = gp_row.get("cell_diagnostic_notes") or {}
    cell_diagnostic_notes = {str(y): t for y, t in diag_raw.items() if t}
    return {
        "cells": cells,
        "cells_display": cells_display,
        "cell_tooltips": cell_tooltips,
        "cell_diagnostic_notes": cell_diagnostic_notes,
    }


def compute_graph_points_for_row(
    *,
    rounding_digits: int,
    display_years: list[int],
    territory_kind: str,
    territory_id: int | None,
    ved_id: int | str | None,
) -> dict[str, Any]:
    """Рассчитать graph_point для одной строки (без записи в БД)."""
    from app.electrical_intensity.services.electrical_intensity_diagnostic_services import (
        _attach_diagnostics_to_graph_point_row,
    )

    version_id = get_current_version()
    current_year = _ei_current_year_number()
    kind = str(territory_kind or "").strip()
    rows: list[dict[str, Any]] = []
    accum_by_ved: dict[tuple[int, int], Decimal | None] = {}
    diag_ved_id: int | None = None
    if kind == "rf":
        ved_types = _refdata_ved_types_for_version(version_id)
        total_ved_id = _find_total_ved_id(ved_types)
        if total_ved_id is None:
            return {
                "cells": {},
                "cells_display": {},
                "cell_tooltips": {},
                "cell_diagnostic_notes": {},
            }
        consumption_by_ved = _load_ved_consumption_values_map(
            version_id=version_id,
            model=RussiaFederationConsumptionParameter,
        )
        product_by_ved = _load_product_output_values_map(
            version_id=version_id,
            model=RussiaFederationProductOutputParameter,
        )
        accum_by_ved = _load_accum_fixed_capital_values_map(
            version_id=version_id,
            model=RussiaFederationAccumFixedCapitalParameter,
        )
        rf_values = _load_year_values_map(
            version_id=version_id,
            model=RussiaFederationElectricalIntensityYearParameter,
        )
        rf_row_defs = _build_row_defs()
        rows = [
            _attach_row_cells(rd, rf_values, display_years, rounding_digits)
            for rd in rf_row_defs
        ]
        _force_compute_graph_points_for_rows(
            rows,
            ved_id=total_ved_id,
            consumption_by_ved_year=consumption_by_ved,
            product_output_by_ved_year=product_by_ved,
            accum_by_ved_year=accum_by_ved,
            display_years=display_years,
            rounding_digits=rounding_digits,
            current_year=current_year,
        )
        gp_row = _find_ei_row(rows, ROW_KIND_GRAPH_POINT)
        diag_ved_id = total_ved_id
    elif kind == "fd" and territory_id is not None and str(ved_id) == POPULATION_SECTION_MARKER:
        fd_id = int(territory_id)
        consumption_by_ved = _load_ved_consumption_values_map(
            version_id=version_id,
            model=FederalDistrictEATConsumptionParameter,
            territory_filter=FederalDistrictEATConsumptionParameter.id_federal_district
            == fd_id,
        )
        household_ved = _find_ved_by_target(
            _refdata_ved_types_for_version(version_id), HOUSEHOLD_VED_TARGET
        )
        household_ved_id = int(household_ved.id) if household_ved is not None else None
        household_by_year = {
            year: (
                consumption_by_ved.get((household_ved_id, year))
                if household_ved_id is not None
                else None
            )
            for year in display_years
        }
        population_by_year = _load_population_by_fd_year(
            version_id=version_id, fd_id=fd_id
        )
        accum_income_by_year = _load_accum_monetary_income_by_fd_year(
            version_id=version_id, fd_id=fd_id
        )
        pop_year_values = _load_population_year_values_map(
            version_id=version_id, fd_id=fd_id
        )
        pop_row_defs = _build_population_row_defs()
        rows = [
            _attach_row_cells(rd, pop_year_values, display_years, rounding_digits)
            for rd in pop_row_defs
        ]
        _force_compute_population_graph_points_for_rows(
            rows,
            household_consumption_by_year=household_by_year,
            population_by_year=population_by_year,
            accum_income_by_year=accum_income_by_year,
            display_years=display_years,
            rounding_digits=rounding_digits,
            current_year=current_year,
        )
        gp_row = _find_ei_row(rows, ROW_KIND_GRAPH_POINT)
        accum_by_ved = {}
        diag_ved_id = None
        _attach_diagnostics_to_graph_point_row(
            rows,
            display_years=display_years,
            investment_cells=accum_income_by_year,
            current_year=current_year,
        )
        if gp_row is None:
            return {
                "cells": {},
                "cells_display": {},
                "cell_tooltips": {},
                "cell_diagnostic_notes": {},
            }
        return _ei_row_calc_json_payload(gp_row, display_years=display_years)
    elif kind == "fd" and territory_id is not None and ved_id is not None:
        fd_id = int(territory_id)
        try:
            ved_id_int = int(ved_id)
        except (TypeError, ValueError):
            return {
                "cells": {},
                "cells_display": {},
                "cell_tooltips": {},
                "cell_diagnostic_notes": {},
            }
        refdata_ved_ids = _refdata_ved_ids(version_id)
        ved = EconomicActivityType.query.get(ved_id_int)
        if ved is None:
            return {
                "cells": {},
                "cells_display": {},
                "cell_tooltips": {},
                "cell_diagnostic_notes": {},
            }
        _, has_ei_model_block, ei_row_kinds = _ei_row_kinds_for_ved(
            ved, refdata_ids=refdata_ved_ids
        )
        if not has_ei_model_block or ROW_KIND_GRAPH_POINT not in ei_row_kinds:
            return {
                "cells": {},
                "cells_display": {},
                "cell_tooltips": {},
                "cell_diagnostic_notes": {},
            }
        fd_filter = FederalDistrictProductOutputParameter.id_federal_district == fd_id
        product_by_ved = _load_product_output_values_map(
            version_id=version_id,
            model=FederalDistrictProductOutputParameter,
            territory_filter=fd_filter,
        )
        consumption_by_ved = _load_ved_consumption_values_map(
            version_id=version_id,
            model=FederalDistrictEATConsumptionParameter,
            territory_filter=FederalDistrictEATConsumptionParameter.id_federal_district
            == fd_id,
        )
        accum_by_ved = _load_accum_fixed_capital_values_map(
            version_id=version_id,
            model=FederalDistrictAccumFixedCapitalParameter,
            territory_filter=FederalDistrictAccumFixedCapitalParameter.id_federal_district
            == fd_id,
        )
        ei_year_by_ved = _load_fd_ei_year_values_map(version_id=version_id, fd_id=fd_id)
        values_by_kind_year = {
            (rk, year): ei_year_by_ved.get((ved_id_int, rk, year))
            for rk in ei_row_kinds
            for year in display_years
        }
        row_defs = _build_row_defs()
        active_row_defs = [rd for rd in row_defs if rd["row_kind"] in ei_row_kinds]
        rows = [
            _attach_row_cells(rd, values_by_kind_year, display_years, rounding_digits)
            for rd in active_row_defs
        ]
        _force_compute_graph_points_for_rows(
            rows,
            ved_id=ved_id_int,
            consumption_by_ved_year=consumption_by_ved,
            product_output_by_ved_year=product_by_ved,
            accum_by_ved_year=accum_by_ved,
            display_years=display_years,
            rounding_digits=rounding_digits,
            current_year=current_year,
        )
        gp_row = _find_ei_row(rows, ROW_KIND_GRAPH_POINT)
        diag_ved_id = ved_id_int
    else:
        return {
            "cells": {},
            "cells_display": {},
            "cell_tooltips": {},
            "cell_diagnostic_notes": {},
        }

    if gp_row is None:
        return {
            "cells": {},
            "cells_display": {},
            "cell_tooltips": {},
            "cell_diagnostic_notes": {},
        }
    if diag_ved_id is not None:
        _attach_diagnostics_to_graph_point_row(
            rows,
            display_years=display_years,
            investment_cells={
                year: accum_by_ved.get((diag_ved_id, year)) for year in display_years
            },
            current_year=current_year,
        )
    return _ei_row_calc_json_payload(gp_row, display_years=display_years)


def _territory_label_for_log(kind: str, fd_id: int | None) -> str:
    if kind == "rf":
        return "Российская Федерация"
    if fd_id is None:
        return "федеральный округ"
    fd = FederalDistrict.query.get(fd_id)
    if fd is None:
        return f"федеральный округ (id={fd_id})"
    return (fd.name_abr or fd.name or fd.name_full or f"id={fd_id}").strip()


def _ved_label_for_log(
    ved_id: int | None,
    *,
    ved_by_id: dict[int, EconomicActivityType] | None = None,
) -> str:
    if ved_id is None:
        return ""
    if ved_by_id is not None:
        ved = ved_by_id.get(ved_id)
        if ved is not None:
            return (_ved_section_display_name(ved) or ved.name or f"id={ved_id}").strip()
    ved = EconomicActivityType.query.get(ved_id)
    if ved is None:
        return f"ВЭД id={ved_id}"
    return (_ved_section_display_name(ved) or ved.name or f"id={ved_id}").strip()


def _preload_rf_year_row_cache(
    version_id: int | None,
) -> dict[tuple[str, int], RussiaFederationElectricalIntensityYearParameter]:
    q = RussiaFederationElectricalIntensityYearParameter.query
    if version_id is not None:
        q = q.filter(
            RussiaFederationElectricalIntensityYearParameter.database_version_id
            == version_id
        )
    cache: dict[tuple[str, int], RussiaFederationElectricalIntensityYearParameter] = {}
    for row in q.all():
        if row.year_number is None or not row.row_kind:
            continue
        cache[(str(row.row_kind), int(row.year_number))] = row
    return cache


def _preload_fd_year_row_cache(
    version_id: int | None,
) -> dict[
    tuple[int, int, str, int], FederalDistrictElectricalIntensityYearParameter
]:
    q = FederalDistrictElectricalIntensityYearParameter.query
    if version_id is not None:
        q = q.filter(
            FederalDistrictElectricalIntensityYearParameter.database_version_id
            == version_id
        )
    cache: dict[
        tuple[int, int, str, int], FederalDistrictElectricalIntensityYearParameter
    ] = {}
    for row in q.all():
        if row.year_number is None or not row.row_kind:
            continue
        cache[
            (
                int(row.id_federal_district),
                int(row.id_economic_activity_type),
                str(row.row_kind),
                int(row.year_number),
            )
        ] = row
    return cache


def _preload_rf_coef_row(
    version_id: int | None,
) -> RussiaFederationElectricalIntensityCoefficient | None:
    q = RussiaFederationElectricalIntensityCoefficient.query
    if version_id is not None:
        q = q.filter(
            RussiaFederationElectricalIntensityCoefficient.database_version_id
            == version_id
        )
    return q.first()


def _preload_fd_coef_cache(
    version_id: int | None,
) -> dict[tuple[int, int], FederalDistrictElectricalIntensityCoefficient]:
    q = FederalDistrictElectricalIntensityCoefficient.query
    if version_id is not None:
        q = q.filter(
            FederalDistrictElectricalIntensityCoefficient.database_version_id
            == version_id
        )
    cache: dict[tuple[int, int], FederalDistrictElectricalIntensityCoefficient] = {}
    for row in q.all():
        cache[(int(row.id_federal_district), int(row.id_economic_activity_type))] = row
    return cache


def _resolve_rf_year_row(
    cache: dict[tuple[str, int], RussiaFederationElectricalIntensityYearParameter],
    version_id: int | None,
    row_kind: str,
    year_n: int,
    user: str,
) -> RussiaFederationElectricalIntensityYearParameter:
    key = (row_kind, year_n)
    row = cache.get(key)
    if row is None:
        row = RussiaFederationElectricalIntensityYearParameter(
            row_kind=row_kind,
            year_number=year_n,
            database_version_id=version_id,
            created_by=user,
        )
        db.session.add(row)
        cache[key] = row
    return row


def _resolve_fd_year_row(
    cache: dict[
        tuple[int, int, str, int], FederalDistrictElectricalIntensityYearParameter
    ],
    version_id: int | None,
    fd_id: int,
    ved_id: int,
    row_kind: str,
    year_n: int,
    user: str,
) -> FederalDistrictElectricalIntensityYearParameter:
    key = (fd_id, ved_id, row_kind, year_n)
    row = cache.get(key)
    if row is None:
        row = FederalDistrictElectricalIntensityYearParameter(
            id_federal_district=fd_id,
            id_economic_activity_type=ved_id,
            row_kind=row_kind,
            year_number=year_n,
            database_version_id=version_id,
            created_by=user,
        )
        db.session.add(row)
        cache[key] = row
    return row


def _resolve_rf_coef_row(
    row: RussiaFederationElectricalIntensityCoefficient | None,
    version_id: int | None,
    user: str,
) -> RussiaFederationElectricalIntensityCoefficient:
    if row is None:
        row = RussiaFederationElectricalIntensityCoefficient(
            database_version_id=version_id,
            created_by=user,
        )
        db.session.add(row)
    return row


def _resolve_fd_coef_row(
    cache: dict[tuple[int, int], FederalDistrictElectricalIntensityCoefficient],
    version_id: int | None,
    fd_id: int,
    ved_id: int,
    user: str,
) -> FederalDistrictElectricalIntensityCoefficient:
    key = (fd_id, ved_id)
    row = cache.get(key)
    if row is None:
        row = FederalDistrictElectricalIntensityCoefficient(
            id_federal_district=fd_id,
            id_economic_activity_type=ved_id,
            database_version_id=version_id,
            created_by=user,
        )
        db.session.add(row)
        cache[key] = row
    return row


def save_electrical_intensity_from_post(form_data: Any) -> tuple[int, int]:
    version_id = get_current_version()
    current_year = _ei_current_year_number()
    user = _username()
    refdata_ids = _refdata_ved_ids(version_id)
    ved_by_id = {v.id: v for v in _refdata_ved_types_for_version(version_id)}
    updated = 0
    skipped = 0
    territory_cache: dict[tuple[str, int | None, int | None], str] = {}
    rf_year_cache = _preload_rf_year_row_cache(version_id)
    fd_year_cache = _preload_fd_year_row_cache(version_id)
    pop_year_cache = _preload_population_year_row_cache(version_id)
    rf_coef_row = _preload_rf_coef_row(version_id)
    fd_coef_cache = _preload_fd_coef_cache(version_id)
    pop_coef_cache = _preload_population_coef_cache(version_id)
    fd_total_k_cache = _preload_fd_total_k_cache(version_id)

    # Коэффициенты A, X
    coef_kinds = form_data.getlist("coef_territory_kind[]")
    coef_territory_ids = form_data.getlist("coef_territory_id[]")
    coef_ved_ids = form_data.getlist("coef_ved_id[]")
    coef_a_vals = form_data.getlist("coef_a[]")
    n_coef = min(
        len(coef_kinds),
        len(coef_territory_ids),
        len(coef_ved_ids),
        len(coef_a_vals),
    )
    for i in range(n_coef):
        kind = str(coef_kinds[i] or "").strip()
        terr_raw = str(coef_territory_ids[i] or "").strip()
        ved_raw = str(coef_ved_ids[i] or "").strip()
        dec_a = _parse_decimal(coef_a_vals[i])
        fd_id: int | None = None
        ved_id: int | None = None
        if kind == "rf":
            row = _resolve_rf_coef_row(rf_coef_row, version_id, user)
            rf_coef_row = row
        elif kind == "fd" and terr_raw and ved_raw == POPULATION_SECTION_MARKER:
            try:
                fd_id = int(terr_raw)
            except ValueError:
                skipped += 1
                continue
            row = _resolve_population_coef_row(
                pop_coef_cache, version_id, fd_id, user
            )
            ved_id = None
        elif kind == "fd" and terr_raw and ved_raw:
            try:
                fd_id = int(terr_raw)
                ved_id = int(ved_raw)
            except ValueError:
                skipped += 1
                continue
            if ved_id not in refdata_ids:
                skipped += 1
                continue
            row = _resolve_fd_coef_row(fd_coef_cache, version_id, fd_id, ved_id, user)
        else:
            skipped += 1
            continue

        terr_key = (kind, fd_id, ved_id)
        if terr_key not in territory_cache:
            parts = [_territory_label_for_log(kind, fd_id)]
            if ved_raw == POPULATION_SECTION_MARKER:
                parts.append(f"блок={POPULATION_SECTION_LABEL}")
            else:
                ved_part = _ved_label_for_log(ved_id, ved_by_id=ved_by_id)
                if ved_part:
                    parts.append(f"ВЭД={ved_part}")
            territory_cache[terr_key] = ", ".join(parts)

        for attr, dec, label in (("coefficient_a", dec_a, "A"),):
            old_val = getattr(row, attr)
            if is_same_decimal(to_decimal(old_val), to_decimal(dec)):
                continue
            setattr(row, attr, dec)
            row.modified_by = user
            queue_electrical_intensity_cell_change(
                user,
                detail_chunks=[
                    f"территория={territory_cache[terr_key]}",
                    f"{label}: {_fmt_log_value(old_val)} → {_fmt_log_value(dec)}",
                ],
                database_version_id=version_id,
            )
            updated += 1

    # Коэффициенты k блока «Всего» (Потери в сетях, С.н. электростанций)
    fd_total_k_kinds = form_data.getlist("fd_total_k_territory_kind[]")
    fd_total_k_territory_ids = form_data.getlist("fd_total_k_territory_id[]")
    fd_total_k_row_kinds = form_data.getlist("fd_total_k_row_kind[]")
    fd_total_k_values = form_data.getlist("fd_total_k_value[]")
    n_fd_total_k = min(
        len(fd_total_k_kinds),
        len(fd_total_k_territory_ids),
        len(fd_total_k_row_kinds),
        len(fd_total_k_values),
    )
    for i in range(n_fd_total_k):
        kind = str(fd_total_k_kinds[i] or "").strip()
        terr_raw = str(fd_total_k_territory_ids[i] or "").strip()
        row_kind = str(fd_total_k_row_kinds[i] or "").strip()
        if kind != "fd" or not terr_raw or row_kind not in (
            REF_ROW_FD_NETWORK_LOSSES,
            REF_ROW_FD_POWER_STATION,
        ):
            skipped += 1
            continue
        try:
            fd_id = int(terr_raw)
        except ValueError:
            skipped += 1
            continue
        dec_k = _parse_decimal(fd_total_k_values[i])
        row = _resolve_fd_total_k_row(
            fd_total_k_cache, version_id, fd_id, row_kind, user
        )
        terr_key = (kind, fd_id, row_kind)
        if terr_key not in territory_cache:
            row_label = REF_ROW_FD_LABEL_BY_KIND.get(row_kind, row_kind)
            territory_cache[terr_key] = (
                f"{_territory_label_for_log(kind, fd_id)}, строка={row_label}"
            )
        old_val = row.coefficient_k
        if is_same_decimal(to_decimal(old_val), to_decimal(dec_k)):
            continue
        row.coefficient_k = dec_k
        row.modified_by = user
        queue_electrical_intensity_cell_change(
            user,
            detail_chunks=[
                f"территория={territory_cache[terr_key]}",
                f"k: {_fmt_log_value(old_val)} → {_fmt_log_value(dec_k)}",
            ],
            database_version_id=version_id,
        )
        updated += 1

    # Ячейки по годам
    kinds = form_data.getlist("territory_kind[]")
    territory_ids = form_data.getlist("territory_id[]")
    cell_ved_ids = form_data.getlist("cell_ved_id[]")
    row_kinds = form_data.getlist("row_kind[]")
    years = form_data.getlist("cell_year[]")
    values = form_data.getlist("cell_value[]")
    orig_values = form_data.getlist("cell_orig_value[]")
    gp_had_display_flags = form_data.getlist("cell_gp_had_display[]")

    n = min(
        len(kinds),
        len(territory_ids),
        len(cell_ved_ids),
        len(row_kinds),
        len(years),
        len(values),
    )
    for i in range(n):
        kind = str(kinds[i] or "").strip()
        terr_raw = str(territory_ids[i] or "").strip()
        ved_raw = str(cell_ved_ids[i] or "").strip()
        rk = str(row_kinds[i] or "").strip()
        year_raw = str(years[i] or "").strip()
        val_raw = values[i]
        orig_raw = orig_values[i] if i < len(orig_values) else ""
        gp_had_display = (
            str(gp_had_display_flags[i] if i < len(gp_had_display_flags) else "")
            .strip()
            == "1"
        )

        if not rk or rk not in ROW_KINDS or not year_raw:
            skipped += 1
            continue
        try:
            year_n = int(year_raw)
        except ValueError:
            skipped += 1
            continue

        is_population_cell = kind == "fd" and terr_raw and ved_raw == POPULATION_SECTION_MARKER
        ved_id_check: int | None = None
        if kind == "fd" and terr_raw and ved_raw and not is_population_cell:
            try:
                ved_id_check = int(ved_raw)
            except ValueError:
                pass
        if is_population_cell:
            if rk not in ROW_KINDS or rk != ROW_KIND_GRAPH_POINT:
                skipped += 1
                continue
        elif ved_id_check is not None:
            if rk == ROW_KIND_GRAPH_POINT and ved_id_check in refdata_ids:
                pass
            else:
                ved_obj = ved_by_id.get(ved_id_check)
                if ved_obj is None and version_id is not None:
                    ved_obj = EconomicActivityType.query.filter(
                        EconomicActivityType.id == ved_id_check,
                        EconomicActivityType.database_version_id == version_id,
                    ).first()
                if ved_obj is not None:
                    _, _, allowed_kinds = _ei_row_kinds_for_ved(
                        ved_obj, refdata_ids=refdata_ids
                    )
                    if rk not in allowed_kinds:
                        skipped += 1
                        continue
                elif rk in EI_MODEL_ROW_KINDS:
                    skipped += 1
                    continue

        if rk == ROW_KIND_CALCULATED:
            skipped += 1
            continue
        if rk in (ROW_KIND_INTENSITY, ROW_KIND_DELTA):
            if current_year is None or year_n <= current_year:
                skipped += 1
                continue

        dec = _parse_decimal(val_raw)
        orig_dec = _parse_decimal(orig_raw)
        if dec is not None:
            if rk in EI_INTENSITY_VALUE_ROW_KINDS:
                dec = _quantize_ei_value(dec, 0, row_kind=rk)
            elif rk == ROW_KIND_GRAPH_POINT:
                dec = _quantize_ei_value(
                    dec, EI_GRAPH_POINT_ROUNDING_DIGITS
                )
        if orig_dec is not None and rk == ROW_KIND_GRAPH_POINT:
            orig_dec = _quantize_ei_value(
                orig_dec, EI_GRAPH_POINT_ROUNDING_DIGITS
            )
        fd_id = None
        ved_id = None
        existing_row: (
            RussiaFederationElectricalIntensityYearParameter
            | FederalDistrictElectricalIntensityYearParameter
            | None
        ) = None
        if kind == "rf":
            existing_row = rf_year_cache.get((rk, year_n))
        elif is_population_cell:
            try:
                fd_id = int(terr_raw)
            except ValueError:
                skipped += 1
                continue
            existing_row = pop_year_cache.get((fd_id, rk, year_n))
            ved_id = None
        elif kind == "fd" and terr_raw and ved_raw:
            try:
                fd_id = int(terr_raw)
                ved_id = int(ved_raw)
            except ValueError:
                skipped += 1
                continue
            existing_row = fd_year_cache.get((fd_id, ved_id, rk, year_n))
        else:
            skipped += 1
            continue

        old_val = existing_row.parameter_value if existing_row is not None else None
        graph_point_cleared = (
            rk == ROW_KIND_GRAPH_POINT
            and dec is None
            and (orig_dec is not None or gp_had_display)
        )
        if not graph_point_cleared and is_same_decimal(
            to_decimal(old_val), to_decimal(dec)
        ):
            skipped += 1
            continue

        if kind == "rf":
            row = _resolve_rf_year_row(
                rf_year_cache, version_id, rk, year_n, user
            )
        elif is_population_cell:
            row = _resolve_population_year_row(
                pop_year_cache, version_id, fd_id, rk, year_n, user
            )
        else:
            row = _resolve_fd_year_row(
                fd_year_cache, version_id, fd_id, ved_id, rk, year_n, user
            )

        row.parameter_value = dec
        row.modified_by = user
        terr_key = (kind, fd_id, ved_id)
        if terr_key not in territory_cache:
            parts = [_territory_label_for_log(kind, fd_id)]
            if is_population_cell:
                parts.append(f"блок={POPULATION_SECTION_LABEL}")
            else:
                ved_part = _ved_label_for_log(ved_id, ved_by_id=ved_by_id)
                if ved_part:
                    parts.append(f"ВЭД={ved_part}")
            territory_cache[terr_key] = ", ".join(parts)
        row_label = (
            POP_ROW_LABEL_BY_KIND.get(rk, rk)
            if is_population_cell
            else ROW_LABEL_BY_KIND.get(rk, rk)
        )
        queue_electrical_intensity_cell_change(
            user,
            detail_chunks=[
                f"территория={territory_cache[terr_key]}",
                f"показатель={row_label}",
                f"год={year_n}",
                f"значение: {_fmt_log_value(old_val)} → {_fmt_log_value(dec)}",
            ],
            database_version_id=version_id,
        )
        updated += 1

    if updated:
        from app.common.services.economics_fd_data_cache import (
            invalidate_economics_fd_data_cache,
        )

        invalidate_economics_fd_data_cache(
            version_id,
            "ei_year",
            "ei_coef",
            "pop_ei_year",
            "pop_ei_coef",
        )

    return updated, skipped


def _get_or_create_fd_year_row(
    version_id: int | None,
    fd_id: int,
    ved_id: int,
    row_kind: str,
    year_n: int,
    user: str,
) -> FederalDistrictElectricalIntensityYearParameter:
    filters = [
        FederalDistrictElectricalIntensityYearParameter.id_federal_district == fd_id,
        FederalDistrictElectricalIntensityYearParameter.id_economic_activity_type == ved_id,
        FederalDistrictElectricalIntensityYearParameter.row_kind == row_kind,
        FederalDistrictElectricalIntensityYearParameter.year_number == year_n,
    ]
    if version_id is not None:
        filters.append(
            FederalDistrictElectricalIntensityYearParameter.database_version_id == version_id
        )
    row = FederalDistrictElectricalIntensityYearParameter.query.filter(and_(*filters)).first()
    if row is None:
        row = FederalDistrictElectricalIntensityYearParameter(
            id_federal_district=fd_id,
            id_economic_activity_type=ved_id,
            row_kind=row_kind,
            year_number=year_n,
            database_version_id=version_id,
            created_by=user,
        )
        db.session.add(row)
    return row


def _get_or_create_rf_year_row(
    version_id: int | None,
    row_kind: str,
    year_n: int,
    user: str,
) -> RussiaFederationElectricalIntensityYearParameter:
    filters = [
        RussiaFederationElectricalIntensityYearParameter.row_kind == row_kind,
        RussiaFederationElectricalIntensityYearParameter.year_number == year_n,
    ]
    if version_id is not None:
        filters.append(
            RussiaFederationElectricalIntensityYearParameter.database_version_id == version_id
        )
    row = RussiaFederationElectricalIntensityYearParameter.query.filter(and_(*filters)).first()
    if row is None:
        row = RussiaFederationElectricalIntensityYearParameter(
            row_kind=row_kind,
            year_number=year_n,
            database_version_id=version_id,
            created_by=user,
        )
        db.session.add(row)
    return row


def _get_or_create_fd_coef(
    version_id: int | None,
    fd_id: int,
    ved_id: int,
    user: str,
) -> FederalDistrictElectricalIntensityCoefficient:
    filters = [
        FederalDistrictElectricalIntensityCoefficient.id_federal_district == fd_id,
        FederalDistrictElectricalIntensityCoefficient.id_economic_activity_type == ved_id,
    ]
    if version_id is not None:
        filters.append(
            FederalDistrictElectricalIntensityCoefficient.database_version_id == version_id
        )
    row = FederalDistrictElectricalIntensityCoefficient.query.filter(and_(*filters)).first()
    if row is None:
        row = FederalDistrictElectricalIntensityCoefficient(
            id_federal_district=fd_id,
            id_economic_activity_type=ved_id,
            database_version_id=version_id,
            created_by=user,
        )
        db.session.add(row)
    return row


def _preload_fd_total_k_cache(
    version_id: int | None,
) -> dict[tuple[int, str], FederalDistrictFdTotalConsumptionCoefficient]:
    q = FederalDistrictFdTotalConsumptionCoefficient.query
    if version_id is not None:
        q = q.filter(
            FederalDistrictFdTotalConsumptionCoefficient.database_version_id
            == version_id
        )
    return {
        (int(row.id_federal_district), str(row.row_kind)): row for row in q.all()
    }


def _resolve_fd_total_k_row(
    cache: dict[tuple[int, str], FederalDistrictFdTotalConsumptionCoefficient],
    version_id: int | None,
    fd_id: int,
    row_kind: str,
    user: str,
) -> FederalDistrictFdTotalConsumptionCoefficient:
    key = (fd_id, row_kind)
    row = cache.get(key)
    if row is None:
        row = FederalDistrictFdTotalConsumptionCoefficient(
            id_federal_district=fd_id,
            row_kind=row_kind,
            database_version_id=version_id,
            created_by=user,
        )
        db.session.add(row)
        cache[key] = row
    return row


def _preload_population_coef_cache(
    version_id: int | None,
) -> dict[int, FederalDistrictPopulationConsumptionCoefficient]:
    q = FederalDistrictPopulationConsumptionCoefficient.query
    if version_id is not None:
        q = q.filter(
            FederalDistrictPopulationConsumptionCoefficient.database_version_id
            == version_id
        )
    return {int(row.id_federal_district): row for row in q.all()}


def _resolve_population_coef_row(
    cache: dict[int, FederalDistrictPopulationConsumptionCoefficient],
    version_id: int | None,
    fd_id: int,
    user: str,
) -> FederalDistrictPopulationConsumptionCoefficient:
    row = cache.get(fd_id)
    if row is None:
        row = FederalDistrictPopulationConsumptionCoefficient(
            id_federal_district=fd_id,
            database_version_id=version_id,
            created_by=user,
        )
        db.session.add(row)
        cache[fd_id] = row
    return row


def _preload_population_year_row_cache(
    version_id: int | None,
) -> dict[tuple[int, str, int], FederalDistrictPopulationConsumptionYearParameter]:
    q = FederalDistrictPopulationConsumptionYearParameter.query
    if version_id is not None:
        q = q.filter(
            FederalDistrictPopulationConsumptionYearParameter.database_version_id
            == version_id
        )
    result: dict[tuple[int, str, int], FederalDistrictPopulationConsumptionYearParameter] = {}
    for row in q.all():
        if row.year_number is None or not row.row_kind:
            continue
        result[(int(row.id_federal_district), str(row.row_kind), int(row.year_number))] = row
    return result


def _resolve_population_year_row(
    cache: dict[tuple[int, str, int], FederalDistrictPopulationConsumptionYearParameter],
    version_id: int | None,
    fd_id: int,
    row_kind: str,
    year_n: int,
    user: str,
) -> FederalDistrictPopulationConsumptionYearParameter:
    key = (fd_id, row_kind, year_n)
    row = cache.get(key)
    if row is None:
        row = FederalDistrictPopulationConsumptionYearParameter(
            id_federal_district=fd_id,
            row_kind=row_kind,
            year_number=year_n,
            database_version_id=version_id,
            created_by=user,
        )
        db.session.add(row)
        cache[key] = row
    return row


def _get_or_create_population_year_row(
    version_id: int | None,
    fd_id: int,
    row_kind: str,
    year_n: int,
    user: str,
) -> FederalDistrictPopulationConsumptionYearParameter:
    filters = [
        FederalDistrictPopulationConsumptionYearParameter.id_federal_district == fd_id,
        FederalDistrictPopulationConsumptionYearParameter.row_kind == row_kind,
        FederalDistrictPopulationConsumptionYearParameter.year_number == year_n,
    ]
    if version_id is not None:
        filters.append(
            FederalDistrictPopulationConsumptionYearParameter.database_version_id
            == version_id
        )
    row = FederalDistrictPopulationConsumptionYearParameter.query.filter(
        and_(*filters)
    ).first()
    if row is None:
        row = FederalDistrictPopulationConsumptionYearParameter(
            id_federal_district=fd_id,
            row_kind=row_kind,
            year_number=year_n,
            database_version_id=version_id,
            created_by=user,
        )
        db.session.add(row)
    return row


def _get_or_create_rf_coef(
    version_id: int | None,
    user: str,
) -> RussiaFederationElectricalIntensityCoefficient:
    filters: list = []
    if version_id is not None:
        filters.append(
            RussiaFederationElectricalIntensityCoefficient.database_version_id == version_id
        )
    q = RussiaFederationElectricalIntensityCoefficient.query
    if filters:
        q = q.filter(and_(*filters))
    row = q.first()
    if row is None:
        row = RussiaFederationElectricalIntensityCoefficient(
            database_version_id=version_id,
            created_by=user,
        )
        db.session.add(row)
    return row
