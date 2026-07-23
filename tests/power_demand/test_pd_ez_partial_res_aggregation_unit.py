# -*- coding: utf-8 -*-
"""Агрегаты энергозон: не брать полный показатель РЭС при частичном пересечении с зоной."""

from __future__ import annotations

from app.power_demand.services import demand_summary_services as dss


def _res_row(
    *,
    ez_id: int,
    res_id: int,
    parameter_key: str,
    year_values: list[str],
    fully_in_zone: bool | None = True,
) -> dict:
    row = {
        "parameter_key": parameter_key,
        "demand_model_name": "RegionalEnergySystemDemandParameter",
        "id_energy_zone": ez_id,
        "id_regional_energy_system": res_id,
        "parent_fk_column": "id_regional_energy_system",
        "parent_id": res_id,
        "year_values": year_values,
    }
    if fully_in_zone is not None:
        row["pd_pd_ez_res_fully_in_zone"] = fully_in_zone
    return row


def test_ez_combined_on_ees_aggregate_skips_partial_res() -> None:
    years = [2017, 2025]
    rows = [
        _res_row(
            ez_id=8,
            res_id=1,
            parameter_key="combined_on_ees",
            year_values=["100", "110"],
            fully_in_zone=True,
        ),
        _res_row(
            ez_id=8,
            res_id=640,
            parameter_key="combined_on_ees",
            year_values=["12 399", "11 886,2"],
            fully_in_zone=False,
        ),
        _res_row(
            ez_id=9,
            res_id=640,
            parameter_key="combined_on_ees",
            year_values=["12 399", "11 886,2"],
            fully_in_zone=True,
        ),
    ]
    sums = dss._aggregate_res_combined_on_ees_mw_sum_by_energy_zone(rows, years)
    assert sums[8] == [100.0, 110.0]
    assert sums[9] == [12399.0, 11886.2]


def test_ez_res_fully_in_zone_ignores_placeholder_outside_district() -> None:
    """Субъект в «не указано» не делает РЭС частичной для реальной зоны (НАО / Архангельск)."""
    from types import SimpleNamespace

    placeholder_ez = SimpleNamespace(name="не указано", number="не указано")
    zone2_ez = SimpleNamespace(name="Коми-Архангельская", number="2")
    arkhangelsk = SimpleNamespace(id=638, name="Архангельская область", energy_zone=zone2_ez)
    nenets = SimpleNamespace(id=670, name="Ненецкий АО", energy_zone=placeholder_ez)
    res = SimpleNamespace(
        id=572,
        name="ЭС Архангельской области и Ненецкого АО",
        regional_districts=[arkhangelsk, nenets],
        energy_units=[],
    )
    # Минимально мокаем builder-зависимости через прямой расчёт флага как в коде.
    in_zone_ids = {638}
    placeholder_names = dss.PLACEHOLDER_NAMES

    def _rd_outside_blocks_full_res(rd) -> bool:
        if rd.id in in_zone_ids:
            return False
        ez = getattr(rd, "energy_zone", None)
        if ez is None:
            return False
        ez_name = (getattr(ez, "name", None) or "").strip().casefold()
        ez_number = str(getattr(ez, "number", None) or "").strip().casefold()
        return ez_name not in placeholder_names and ez_number not in placeholder_names

    fully = bool(in_zone_ids) and not any(
        _rd_outside_blocks_full_res(rd) for rd in res.regional_districts
    )
    assert fully is True

    # Тюмень: субъект в другой реальной зоне — частичная.
    zone8 = SimpleNamespace(name="Урал без Тюмени", number="8")
    zone9 = SimpleNamespace(name="Тюменская ЭС", number="9")
    khmao = SimpleNamespace(id=716, energy_zone=zone8)
    tyumen = SimpleNamespace(id=712, energy_zone=zone9)
    in_zone_ids_u = {716}
    fully_u = bool(in_zone_ids_u) and not any(
        (
            False
            if rd.id in in_zone_ids_u
            else (
                (getattr(rd.energy_zone, "name", "") or "").strip().casefold()
                not in placeholder_names
                and str(getattr(rd.energy_zone, "number", "") or "").strip().casefold()
                not in placeholder_names
            )
        )
        for rd in (khmao, tyumen)
    )
    assert fully_u is False


def test_ez_combined_on_ez_aggregate_skips_partial_res() -> None:
    years = [2017]
    rows = [
        _res_row(
            ez_id=7,
            res_id=1,
            parameter_key="combined_on_ez",
            year_values=["50"],
            fully_in_zone=True,
        ),
        _res_row(
            ez_id=7,
            res_id=2,
            parameter_key="combined_on_ez",
            year_values=["999"],
            fully_in_zone=False,
        ),
    ]
    sums = dss._aggregate_res_combined_on_ez_mw_sum_by_energy_zone(rows, years)
    assert sums[7] == [50.0]
