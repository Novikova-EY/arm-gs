# -*- coding: utf-8 -*-
"""Данные для HTML-таблиц ТЭП (основные / резервные площадки) на списке АЭС."""
from __future__ import annotations

from decimal import Decimal
from itertools import groupby
from typing import Any

from app.generation.prospective_places.models import MachineProspectivePlaceAES
from app.generation.prospective_places.models.aes.prospective_place_type_aes_model import ProspectivePlaceTypeAES
from app.generation.prospective_places.services.tep_capital_cost_current_year_services import (
    rows_match_for_scaled_thousand_rub_pair,
)

# Поля ТЭП, которые при одинаковых значениях по всем блокам станции объединяются (как merged_values на карточке)
TEP_MERGE_FIELDS = (
    "service_life_years",
    "construction_period_years",
    "max_annual_operating_hours",
    "specific_fuel_cost_rub_per_kwh",
    "id_year_specific_fuel_cost",
    "specific_fixed_operating_costs_thous_rub_per_kw",
    "id_year_specific_fixed_operating_costs",
    "relative_auxiliary_power_consumption_pct",
    "specific_capital_investment_thous_rub_per_kw",
    "id_year_specific_capital_investment",
    "specific_decommissioning_cost_thous_rub_per_kw",
    "id_year_specific_decommissioning",
    "emergency_state_probability",
    "ozp",
    "vlp",
)

_SCALED_VALUE_FIELDS = (
    "specific_fuel_cost_rub_per_kwh",
    "specific_fixed_operating_costs_thous_rub_per_kw",
    "specific_capital_investment_thous_rub_per_kw",
    "specific_decommissioning_cost_thous_rub_per_kw",
)


def _norm_tep_val(mp: MachineProspectivePlaceAES, field: str) -> str:
    v = getattr(mp, field, None)
    if v is None:
        return "__none__"
    if isinstance(v, int):
        return str(v)
    s = (str(v) or "").strip()
    return s if s else "__empty__"


def _machines_same_for_field(group: list[MachineProspectivePlaceAES], field: str) -> bool:
    if len(group) <= 1:
        return True
    first = _norm_tep_val(group[0], field)
    return all(_norm_tep_val(mp, field) == first for mp in group[1:])


def _fmt_excel_like(val: Any) -> str:
    if val is None:
        return "—"
    s = str(val).strip() if val is not None else ""
    if not s:
        return "—"
    return s.replace(".", ",")


def _fmt_year_ref(year) -> str:
    if year is None:
        return "—"
    return str(year.number)


def _scaled_thousand_display(
    mp: MachineProspectivePlaceAES,
    raw_attr: str,
    year_rel_attr: str,
    *,
    apply_current_year: bool,
    target_year: int | None,
    coeff_by_year: dict[int, Decimal],
) -> str:
    from app.generation.prospective_places.services.tep_capital_cost_current_year_services import (
        fmt_thousand_rub_per_kw_scaled,
    )

    raw = getattr(mp, raw_attr, None)
    yrel = getattr(mp, year_rel_attr, None)
    if apply_current_year and target_year is not None:
        return fmt_thousand_rub_per_kw_scaled(raw, yrel, target_year, coeff_by_year)
    return _fmt_excel_like(raw or "—")


def _row_machine_cells(mp: MachineProspectivePlaceAES) -> dict[str, str]:
    return {
        "ppt": _fmt_excel_like(
            (mp.prospective_place_type.name if mp.prospective_place_type else None) or "—"
        ),
        "station_block_number": _fmt_excel_like(mp.station_block_number or "—"),
        "unit_type": _fmt_excel_like(mp.unit_type or "—"),
        "unit_capacity_mw": _fmt_excel_like(mp.unit_capacity_mw or "—"),
        "possible_implementation_period": _fmt_excel_like(mp.possible_implementation_period or "—"),
    }


def _row_tep_cells(
    mp: MachineProspectivePlaceAES,
    *,
    apply_current_year_prices: bool,
    target_year: int | None,
    coeff_by_year: dict[int, Decimal],
) -> dict[str, str]:
    coeff = coeff_by_year
    use_scale = bool(apply_current_year_prices and target_year is not None)
    return {
        "service_life_years": (
            str(mp.service_life_years) if mp.service_life_years is not None else "—"
        ),
        "construction_period_years": (
            str(mp.construction_period_years) if mp.construction_period_years is not None else "—"
        ),
        "max_annual_operating_hours": _fmt_excel_like(mp.max_annual_operating_hours or "—"),
        "specific_fuel_cost_rub_per_kwh": _scaled_thousand_display(
            mp,
            "specific_fuel_cost_rub_per_kwh",
            "year_specific_fuel_cost",
            apply_current_year=use_scale,
            target_year=target_year,
            coeff_by_year=coeff,
        ),
        "year_specific_fuel_cost": _fmt_year_ref(mp.year_specific_fuel_cost),
        "specific_fixed_operating_costs_thous_rub_per_kw": _scaled_thousand_display(
            mp,
            "specific_fixed_operating_costs_thous_rub_per_kw",
            "year_specific_fixed_operating_costs",
            apply_current_year=use_scale,
            target_year=target_year,
            coeff_by_year=coeff,
        ),
        "year_specific_fixed_operating_costs": _fmt_year_ref(mp.year_specific_fixed_operating_costs),
        "relative_auxiliary_power_consumption_pct": _fmt_excel_like(
            mp.relative_auxiliary_power_consumption_pct or "—"
        ),
        "specific_capital_investment_thous_rub_per_kw": _scaled_thousand_display(
            mp,
            "specific_capital_investment_thous_rub_per_kw",
            "year_specific_capital_investment",
            apply_current_year=use_scale,
            target_year=target_year,
            coeff_by_year=coeff,
        ),
        "year_specific_capital_investment": _fmt_year_ref(mp.year_specific_capital_investment),
        "specific_decommissioning_cost_thous_rub_per_kw": _scaled_thousand_display(
            mp,
            "specific_decommissioning_cost_thous_rub_per_kw",
            "year_specific_decommissioning",
            apply_current_year=use_scale,
            target_year=target_year,
            coeff_by_year=coeff,
        ),
        "year_specific_decommissioning": _fmt_year_ref(mp.year_specific_decommissioning),
        "emergency_state_probability": _fmt_excel_like(mp.emergency_state_probability or "—"),
        "ozp": _fmt_excel_like(mp.ozp or "—"),
        "vlp": _fmt_excel_like(mp.vlp or "—"),
    }


def total_capacity_mw_sum(machines: list[MachineProspectivePlaceAES]) -> float:
    total = 0.0
    for mp in machines:
        try:
            val = (mp.unit_capacity_mw or "").strip()
            if val:
                total += float(val.replace(",", "."))
        except (ValueError, TypeError):
            pass
    return total


def collect_main_and_reserve_machines(stations: list) -> tuple[list[MachineProspectivePlaceAES], list[MachineProspectivePlaceAES]]:
    main_types = ProspectivePlaceTypeAES.query.filter(ProspectivePlaceTypeAES.name.ilike("%основн%")).all()
    reserve_types = ProspectivePlaceTypeAES.query.filter(ProspectivePlaceTypeAES.name.ilike("%резерв%")).all()
    main_type_ids = {t.id for t in main_types}
    reserve_type_ids = {t.id for t in reserve_types}

    machines_main: list[MachineProspectivePlaceAES] = []
    machines_reserve: list[MachineProspectivePlaceAES] = []
    for s in stations:
        for mp in s.machine_prospective_places:
            ppt_id = mp.id_prospective_place_type
            if ppt_id in main_type_ids:
                machines_main.append(mp)
            elif ppt_id in reserve_type_ids:
                machines_reserve.append(mp)
    return machines_main, machines_reserve


def build_tep_view_rows(
    machines: list[MachineProspectivePlaceAES],
    *,
    tep_main_current_year_prices: bool = False,
    tep_main_scaling_target_year: int | None = None,
) -> list[dict[str, Any]]:
    """Строки для шаблона: группировка по станции, merged TEP при совпадении значений."""
    if not machines:
        return []

    target_year: int | None = None
    coeff_by_year: dict[int, Decimal] = {}
    apply_current = bool(tep_main_current_year_prices)
    if apply_current:
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
    idx = 1
    for _sid, group_iter in groupby(machines, key=lambda m: m.id_station_prospective_place_aes):
        group = list(group_iter)
        n = len(group)
        merged_flags: dict[str, bool] = {}
        for f in TEP_MERGE_FIELDS:
            if f in _SCALED_VALUE_FIELDS and apply_current:
                continue
            if f in (
                "id_year_specific_fuel_cost",
                "id_year_specific_fixed_operating_costs",
                "id_year_specific_capital_investment",
                "id_year_specific_decommissioning",
            ) and apply_current:
                continue
            merged_flags[f] = _machines_same_for_field(group, f)

        if apply_current:
            merged_flags["specific_fuel_cost_rub_per_kwh"] = rows_match_for_scaled_thousand_rub_pair(
                group,
                "specific_fuel_cost_rub_per_kwh",
                "year_specific_fuel_cost",
                target_year=target_year,
                coeff_by_year=coeff_by_year,
            )
            merged_flags["specific_fixed_operating_costs_thous_rub_per_kw"] = (
                rows_match_for_scaled_thousand_rub_pair(
                    group,
                    "specific_fixed_operating_costs_thous_rub_per_kw",
                    "year_specific_fixed_operating_costs",
                    target_year=target_year,
                    coeff_by_year=coeff_by_year,
                )
            )
            merged_flags["specific_capital_investment_thous_rub_per_kw"] = (
                rows_match_for_scaled_thousand_rub_pair(
                    group,
                    "specific_capital_investment_thous_rub_per_kw",
                    "year_specific_capital_investment",
                    target_year=target_year,
                    coeff_by_year=coeff_by_year,
                )
            )
            merged_flags["specific_decommissioning_cost_thous_rub_per_kw"] = (
                rows_match_for_scaled_thousand_rub_pair(
                    group,
                    "specific_decommissioning_cost_thous_rub_per_kw",
                    "year_specific_decommissioning",
                    target_year=target_year,
                    coeff_by_year=coeff_by_year,
                )
            )
            merged_flags["id_year_specific_fuel_cost"] = _machines_same_for_field(
                group, "id_year_specific_fuel_cost"
            )
            merged_flags["id_year_specific_fixed_operating_costs"] = _machines_same_for_field(
                group, "id_year_specific_fixed_operating_costs"
            )
            merged_flags["id_year_specific_capital_investment"] = _machines_same_for_field(
                group, "id_year_specific_capital_investment"
            )
            merged_flags["id_year_specific_decommissioning"] = _machines_same_for_field(
                group, "id_year_specific_decommissioning"
            )

        for i, mp in enumerate(group):
            site = (
                mp.station_prospective_place_aes.site_name
                if mp.station_prospective_place_aes
                else None
            ) or "—"
            rows_out.append(
                {
                    "idx": idx,
                    "show_station_cell": i == 0,
                    "station_rowspan": n,
                    "site_name": site,
                    "place_id": mp.id_station_prospective_place_aes,
                    "machine_id": mp.id,
                    "merged_tep": merged_flags,
                    "is_first_in_station": i == 0,
                    "machine": _row_machine_cells(mp),
                    "tep": _row_tep_cells(
                        mp,
                        apply_current_year_prices=apply_current,
                        target_year=target_year,
                        coeff_by_year=coeff_by_year,
                    ),
                }
            )
            idx += 1

    return rows_out
