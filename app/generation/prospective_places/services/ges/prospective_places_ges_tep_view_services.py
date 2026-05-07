# -*- coding: utf-8 -*-
"""Данные для HTML-таблиц перечня ТЭП перспективных площадок ГЭС."""
from __future__ import annotations

from decimal import Decimal
from itertools import groupby
from typing import Any

from app.generation.prospective_places.models import ProspectivePlaceGesTepSource
from app.generation.prospective_places.forms.decimal_input_display import (
    format_construction_period_years_display,
    normalize_construction_period_years,
)
from app.generation.prospective_places.services.tep_capital_cost_current_year_services import (
    apply_derived_specific_capital_investment_to_tep_row_dict,
    fmt_numeric_million_rub as _fmt_numeric_million_rub,
    fmt_specific_capital_investment_thous_rub_per_kw_derived,
    fmt_thousand_rub_per_kw_scaled,
    merge_tep_row_full_with_capital_costs_current_year_prices,
    rows_match_for_derived_specific_capital_investment,
    rows_match_for_scaled_specific_semifixed_operating_costs,
)
TEP_MERGE_FIELDS = (
    "construction_period_years",
    "specific_semifixed_operating_costs_thous_rub_per_kw",
    "specific_capital_investment_thous_rub_per_kw",
    "id_year_specific_semifixed_operating_costs",
    "id_year_specific_capital_investment",
)


def _ges_tep_source_row_sort_key(m: ProspectivePlaceGesTepSource) -> tuple:
    """Порядок: ОЭС (UnionEnergySystem.display_order), площадка (display_order), id строк ТЭП."""
    st = m.station_prospective_place_ges
    ues_od = None
    st_od = None
    if st is not None:
        st_od = st.display_order
        res = st.regional_energy_system
        if res and res.union_energy_system:
            ues_od = res.union_energy_system.display_order
    return (
        ues_od is None,
        ues_od if ues_od is not None else 0,
        st_od is None,
        st_od if st_od is not None else 0,
        m.id_station_prospective_place_ges,
        m.id,
    )


def _norm_tep_val(row: ProspectivePlaceGesTepSource, field: str) -> str:
    v = getattr(row, field, None)
    if v is None:
        return "__none__"
    if field == "construction_period_years":
        n = normalize_construction_period_years(v)
        return "__none__" if n is None else format(n, "f")
    if isinstance(v, int):
        return str(v)
    s = (str(v) or "").strip()
    return s if s else "__empty__"


def _rows_same_for_field(group: list[ProspectivePlaceGesTepSource], field: str) -> bool:
    if len(group) <= 1:
        return True
    first = _norm_tep_val(group[0], field)
    return all(_norm_tep_val(r, field) == first for r in group[1:])


def _fmt_year_ref(year) -> str:
    if year is None:
        return "—"
    return str(year.number)


def build_tep_full_current_year_prices(
    r: ProspectivePlaceGesTepSource,
    target_year: int | None,
    coeff_by_year: dict[int, Decimal],
) -> dict[str, str]:
    """Те же поля, что fmt_tep_source_row_full, но три столбца капзатрат — пересчитаны в цены текущего года."""
    base = fmt_tep_source_row_full(r)
    return merge_tep_row_full_with_capital_costs_current_year_prices(
        base, r, target_year, coeff_by_year
    )


def _fmt_excel_like(val: Any) -> str:
    if val is None:
        return "—"
    s = str(val).strip() if val is not None else ""
    if not s:
        return "—"
    return s.replace(".", ",")


def _row_identity_cells(r: ProspectivePlaceGesTepSource) -> dict[str, str]:
    return {
        "ppt": _fmt_excel_like(
            (r.prospective_place_type_ges.name if r.prospective_place_type_ges else None) or "—"
        ),
        "installed_capacity_mw": _fmt_excel_like(r.installed_capacity_mw or "—"),
        "hydro_turbine_type": _fmt_excel_like(r.hydro_turbine_type or "—"),
    }


def _row_tep_cells(
    r: ProspectivePlaceGesTepSource,
    *,
    target_year: int | None = None,
    coeff_by_year: dict[int, Decimal] | None = None,
) -> dict[str, str]:
    coeff = coeff_by_year or {}
    if target_year:
        semifixed_display = fmt_thousand_rub_per_kw_scaled(
            r.specific_semifixed_operating_costs_thous_rub_per_kw,
            r.year_specific_semifixed_operating_costs,
            target_year,
            coeff,
        )
    else:
        semifixed_display = _fmt_excel_like(r.specific_semifixed_operating_costs_thous_rub_per_kw or "—")
    return {
        "construction_period_years": format_construction_period_years_display(
            r.construction_period_years
        )
        or "—",
        "specific_semifixed_operating_costs_thous_rub_per_kw": semifixed_display,
        "year_specific_semifixed_operating_costs": _fmt_year_ref(
            r.year_specific_semifixed_operating_costs
        ),
        "specific_capital_investment_thous_rub_per_kw": fmt_specific_capital_investment_thous_rub_per_kw_derived(
            r,
            installed_capacity_attr="installed_capacity_mw",
            target_year=target_year,
            coeff_by_year=coeff_by_year,
        ),
        "year_specific_capital_investment": _fmt_year_ref(
            r.year_capital_cost_wo_pir_ges_with_reservoir
        ),
    }


def fmt_tep_source_row_full(r: ProspectivePlaceGesTepSource) -> dict[str, str]:
    """Все поля перечня ТЭП для таблицы (как на карточке площадки)."""
    ppt = (r.prospective_place_type_ges.name if r.prospective_place_type_ges else None) or "—"
    note_raw = (r.note or "").strip()
    note_display = note_raw if note_raw else "—"
    inc = {}
    for i in range(1, 13):
        attr = f"construction_increment_year_{i:02d}_mw"
        inc[attr] = _fmt_excel_like(getattr(r, attr, None) or "—")
    result = {
        "ppt": _fmt_excel_like(ppt),
        "installed_capacity_mw": _fmt_excel_like(r.installed_capacity_mw or "—"),
        "stage_1_capacity_mw": _fmt_excel_like(r.stage_1_capacity_mw or "—"),
        "stage_2_capacity_mw": _fmt_excel_like(r.stage_2_capacity_mw or "—"),
        "startup_complex_capacity_mw": _fmt_excel_like(r.startup_complex_capacity_mw or "—"),
        "units_count": str(r.units_count) if r.units_count is not None else "—",
        "unit_capacity_mw": _fmt_excel_like(r.unit_capacity_mw or "—"),
        "hydro_turbine_type": _fmt_excel_like(r.hydro_turbine_type or "—"),
        "construction_period_years": format_construction_period_years_display(
            r.construction_period_years
        )
        or "—",
        **inc,
        "specific_semifixed_operating_costs_thous_rub_per_kw": _fmt_excel_like(
            r.specific_semifixed_operating_costs_thous_rub_per_kw or "—"
        ),
        "generation_average_multiyear_billion_kwh": _fmt_excel_like(
            r.generation_average_multiyear_billion_kwh or "—"
        ),
        "generation_medium_water_management_year": _fmt_excel_like(
            r.generation_medium_water_management_year or "—"
        ),
        "generation_medium_water_50pct_billion_kwh": _fmt_excel_like(
            r.generation_medium_water_50pct_billion_kwh or "—"
        ),
        "generation_low_water_management_year": _fmt_excel_like(
            r.generation_low_water_management_year or "—"
        ),
        "generation_low_water_95pct_billion_kwh": _fmt_excel_like(
            r.generation_low_water_95pct_billion_kwh or "—"
        ),
        "capital_cost_wo_pir_total_million_rub": _fmt_numeric_million_rub(
            r.capital_cost_wo_pir_total_million_rub
        ),
        "year_capital_cost_wo_pir_total": _fmt_year_ref(r.year_capital_cost_wo_pir_total),
        "capital_cost_wo_pir_ges_with_reservoir_million_rub": _fmt_numeric_million_rub(
            r.capital_cost_wo_pir_ges_with_reservoir_million_rub
        ),
        "year_capital_cost_wo_pir_ges_with_reservoir": _fmt_year_ref(
            r.year_capital_cost_wo_pir_ges_with_reservoir
        ),
        "capital_cost_wo_pir_svm_million_rub": _fmt_numeric_million_rub(
            r.capital_cost_wo_pir_svm_million_rub
        ),
        "year_capital_cost_wo_pir_svm": _fmt_year_ref(r.year_capital_cost_wo_pir_svm),
        "note": note_display,
    }
    apply_derived_specific_capital_investment_to_tep_row_dict(
        result, r, target_year=None, coeff_by_year=None
    )
    result["year_specific_semifixed_operating_costs"] = _fmt_year_ref(
        r.year_specific_semifixed_operating_costs
    )
    # Год у удельных капвложений — как у капзатрат «ГЭС (с водохранилищем)» (база расчёта).
    result["year_specific_capital_investment"] = result["year_capital_cost_wo_pir_ges_with_reservoir"]
    return result


def total_capacity_mw_sum(rows: list[ProspectivePlaceGesTepSource]) -> float:
    total = 0.0
    for r in rows:
        try:
            val = (r.installed_capacity_mw or "").strip()
            if val:
                total += float(val.replace(",", "."))
        except (ValueError, TypeError):
            pass
    return total


def collect_all_ges_tep_rows(stations: list) -> list[ProspectivePlaceGesTepSource]:
    """Все строки ТЭП по списку площадок (без отбора по типу площадки из справочника)."""
    rows: list[ProspectivePlaceGesTepSource] = []
    for s in stations:
        rows.extend(s.ges_tep_source_indicators or [])
    return rows


def build_tep_view_rows(
    tep_rows: list[ProspectivePlaceGesTepSource],
    *,
    start_idx: int = 1,
    tep_main_current_year_prices: bool = False,
    tep_main_scaling_target_year: int | None = None,
) -> list[dict[str, Any]]:
    """Строки для шаблона: группировка по электростанции, merged TEP при совпадении значений.

    ``tep_main_scaling_target_year`` — год конца цепочки пересчёта капзатрат (как в подписи
    «в ценах N года»). Если не передан, используется год «текущий» из справочника годов; при
    расхождении с подписью цепочка коэффициентов могла не совпадать с таблицей коэффициентов.
    """
    if not tep_rows:
        return []

    tep_rows = sorted(tep_rows, key=_ges_tep_source_row_sort_key)

    target_year: int | None = None
    coeff_by_year: dict[int, Decimal] = {}
    if tep_main_current_year_prices:
        from app.common.services.get_services.years.years_get_services import (
            get_ges_tep_current_price_year_number,
        )
        from app.generation.prospective_places.services.tep_capital_cost_current_year_services import (
            get_tep_price_coefficient_by_year_map,
        )

        coeff_by_year = get_tep_price_coefficient_by_year_map()
        if tep_main_scaling_target_year is not None:
            target_year = tep_main_scaling_target_year
        else:
            target_year = get_ges_tep_current_price_year_number()

    rows_out: list[dict[str, Any]] = []
    idx = start_idx
    for _sid, group_iter in groupby(tep_rows, key=lambda m: m.id_station_prospective_place_ges):
        group = list(group_iter)
        n = len(group)
        merged_flags = {
            f: _rows_same_for_field(group, f)
            for f in TEP_MERGE_FIELDS
            if f
            not in (
                "specific_capital_investment_thous_rub_per_kw",
                "specific_semifixed_operating_costs_thous_rub_per_kw",
            )
        }
        merged_flags["specific_semifixed_operating_costs_thous_rub_per_kw"] = (
            rows_match_for_scaled_specific_semifixed_operating_costs(
                group,
                target_year=target_year if tep_main_current_year_prices else None,
                coeff_by_year=coeff_by_year if tep_main_current_year_prices else None,
            )
            if tep_main_current_year_prices
            else _rows_same_for_field(group, "specific_semifixed_operating_costs_thous_rub_per_kw")
        )
        merged_flags["specific_capital_investment_thous_rub_per_kw"] = (
            rows_match_for_derived_specific_capital_investment(
                group,
                target_year=target_year if tep_main_current_year_prices else None,
                coeff_by_year=coeff_by_year if tep_main_current_year_prices else None,
            )
        )

        for i, r in enumerate(group):
            site = (
                r.station_prospective_place_ges.site_name
                if r.station_prospective_place_ges
                else None
            ) or "—"
            tep_full = fmt_tep_source_row_full(r)
            if tep_main_current_year_prices:
                tep_full_current_year = build_tep_full_current_year_prices(
                    r, target_year, coeff_by_year
                )
            else:
                tep_full_current_year = tep_full
            rows_out.append(
                {
                    "idx": idx,
                    "show_station_cell": i == 0,
                    "station_rowspan": n,
                    "site_name": site,
                    "station_id": r.id_station_prospective_place_ges,
                    "merged_tep": merged_flags,
                    "is_first_in_station": i == 0,
                    "machine": _row_identity_cells(r),
                    "tep": _row_tep_cells(
                        r,
                        target_year=target_year if tep_main_current_year_prices else None,
                        coeff_by_year=coeff_by_year if tep_main_current_year_prices else None,
                    ),
                    "tep_full": tep_full,
                    "tep_full_current_year": tep_full_current_year,
                }
            )
            idx += 1

    return rows_out


def build_tep_groups_by_station_place_type(
    ges_place_type_groups: list[dict[str, Any]],
    *,
    tep_main_current_year_prices: bool = False,
    tep_main_scaling_target_year: int | None = None,
) -> tuple[list[dict[str, Any]], float]:
    """Те же группы, что build_ges_stations_grouped_by_place_type: подписи + все строки ТЭП в группе."""
    tep_groups: list[dict[str, Any]] = []
    next_idx = 1
    total_mw = 0.0
    apply_current = bool(tep_main_current_year_prices)
    for group in ges_place_type_groups:
        machines = collect_all_ges_tep_rows(group["stations"])
        rows = build_tep_view_rows(
            machines,
            start_idx=next_idx,
            tep_main_current_year_prices=apply_current,
            tep_main_scaling_target_year=tep_main_scaling_target_year if apply_current else None,
        )
        next_idx += len(rows)
        total_mw += total_capacity_mw_sum(machines)
        tep_groups.append({"type_label": group["type_label"], "tep_rows": rows})
    return tep_groups, total_mw
