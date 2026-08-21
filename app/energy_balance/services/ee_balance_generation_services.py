# -*- coding: utf-8 -*-
"""Выработка ЭЭ по типам станций для листов баланса электрической энергии."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.common.services.database_version_filter import filter_by_db_version
from app.energy_balance.services.power_balance_installed_capacity_services import (
    get_power_balance_station_type_groups,
    resolve_sheet_territory,
    resolve_station_balance_territory,
)
from app.energy_balance.services.station_ee_generation_page_services import (
    load_annual_generation_by_station,
)
from app.generation.models.station.station_model import Station


def generation_type_groups() -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for group in get_power_balance_station_type_groups():
        key = str(group.get("key") or "")
        if key.startswith("installed_"):
            key = "generation_" + key[len("installed_") :]
        groups.append({**group, "key": key})
    return groups


def generation_type_keys(groups: list[dict[str, Any]] | None = None) -> tuple[str, ...]:
    items = groups if groups is not None else generation_type_groups()
    return tuple(group["key"] for group in items)


def _decimal_or_zero(raw: Any) -> Decimal:
    if raw is None:
        return Decimal("0")
    return Decimal(str(raw))


def _territory_lookups(
    res_ids: set[int],
    district_ids: set[int],
) -> tuple[dict[int, int], dict[int, int], dict[int, int]]:
    from app.refdata.models.energy_systems.regional_energy_system_model import (
        RegionalEnergySystem,
    )
    from app.refdata.models.territories.regional_district_model import RegionalDistrict

    res_to_ues: dict[int, int] = {}
    if res_ids:
        for res in RegionalEnergySystem.query.filter(RegionalEnergySystem.id.in_(res_ids)):
            ues_id = getattr(res, "id_union_energy_system", None)
            if ues_id:
                res_to_ues[int(res.id)] = int(ues_id)
    district_to_ues: dict[int, int] = {}
    district_to_sa: dict[int, int] = {}
    if district_ids:
        for district in RegionalDistrict.query.filter(RegionalDistrict.id.in_(district_ids)):
            sa_id = getattr(district, "id_synchronous_area", None)
            if sa_id:
                district_to_sa[int(district.id)] = int(sa_id)
            for res in district.regional_energy_systems or []:
                ues_id = getattr(res, "id_union_energy_system", None)
                if ues_id:
                    district_to_ues[int(district.id)] = int(ues_id)
                    break
    return res_to_ues, district_to_ues, district_to_sa


def _type_id_to_group_key(groups: list[dict[str, Any]]) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for group in groups:
        for type_id in group.get("type_ids") or ():
            try:
                mapping[int(type_id)] = str(group["key"])
            except (TypeError, ValueError, KeyError):
                continue
    return mapping


def load_ee_balance_generation_inputs(
    years: list[int],
    sheets: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, dict[int, Decimal]]]:
    """Выработка ЭЭ по типам станций для листов с прямой территорией (не ЕЭС / 1-я СЗ)."""
    if not years:
        return {}
    groups = generation_type_groups()
    type_to_key = _type_id_to_group_key(groups)
    if not type_to_key:
        return {}

    from app.generation.services.station_services.station_services import get_filtered_station_ids

    try:
        station_ids = get_filtered_station_ids({})
    except Exception:
        station_ids = []
    if not station_ids:
        return {}

    try:
        query = Station.query.filter(Station.id.in_(station_ids))
        query = filter_by_db_version(query, Station)
        stations = list(
            query.with_entities(
                Station.id,
                Station.id_station_type,
                Station.id_regional_energy_system,
                Station.id_regional_district,
            ).all()
        )
    except Exception:
        return {}
    if not stations:
        return {}

    res_ids: set[int] = set()
    district_ids: set[int] = set()
    for station in stations:
        res_id = getattr(station, "id_regional_energy_system", None)
        district_id = getattr(station, "id_regional_district", None)
        if res_id:
            res_ids.add(int(res_id))
        if district_id:
            district_ids.add(int(district_id))
    try:
        res_to_ues, district_to_ues, district_to_sa = _territory_lookups(res_ids, district_ids)
    except Exception:
        return {}

    try:
        generation_by_station = load_annual_generation_by_station(
            [int(station.id) for station in stations if getattr(station, "id", None)],
            min(years),
            max(years),
        )
    except Exception:
        generation_by_station = {}

    ues_by_key: dict[int, dict[str, dict[int, Decimal]]] = {}
    sa_by_key: dict[int, dict[str, dict[int, Decimal]]] = {}
    wanted_years = [int(year) for year in years]
    for station in stations:
        type_id = getattr(station, "id_station_type", None)
        group_key = type_to_key.get(int(type_id)) if type_id is not None else None
        if not group_key:
            continue
        station_id = int(station.id)
        year_map = generation_by_station.get(station_id) or {}
        res_id = getattr(station, "id_regional_energy_system", None)
        district_id = getattr(station, "id_regional_district", None)
        ues_id, sa_id = resolve_station_balance_territory(
            id_regional_energy_system=int(res_id) if res_id else None,
            id_regional_district=int(district_id) if district_id else None,
            res_to_ues=res_to_ues,
            district_to_ues=district_to_ues,
            district_to_sa=district_to_sa,
        )
        for year in wanted_years:
            value = year_map.get(year)
            if value is None:
                continue
            amount = _decimal_or_zero(value)
            if ues_id is not None:
                ues_by_key.setdefault(ues_id, {}).setdefault(group_key, {})
                bucket = ues_by_key[ues_id][group_key]
                bucket[year] = bucket.get(year, Decimal("0")) + amount
            if sa_id is not None:
                sa_by_key.setdefault(sa_id, {}).setdefault(group_key, {})
                bucket = sa_by_key[sa_id][group_key]
                bucket[year] = bucket.get(year, Decimal("0")) + amount

    if sheets:
        sheet_specs: list[tuple[str, dict[str, Any] | None]] = []
        for sheet in sheets:
            if sheet.get("skip_direct_capacity") or sheet.get("layout") in {"ees_rossii", "sz1"}:
                continue
            sheet_specs.append((sheet["slug"], sheet.get("territory")))
    else:
        sheet_specs = []

    inputs: dict[str, dict[str, dict[int, Decimal]]] = {}
    for slug, territory in sheet_specs:
        resolved = (
            territory if territory and territory.get("id") is not None else resolve_sheet_territory(slug)
        )
        if resolved is None:
            continue
        try:
            entity_id = int(resolved["id"])
        except (TypeError, ValueError, KeyError):
            continue
        kind = str(resolved.get("kind") or "")
        by_key = ues_by_key.get(entity_id) if kind == "ues" else sa_by_key.get(entity_id) if kind == "sa" else None
        if kind not in {"ues", "sa"}:
            continue
        sheet_inputs: dict[str, dict[int, Decimal]] = {}
        for group in groups:
            year_map = (by_key or {}).get(group["key"]) or {}
            sheet_inputs[group["key"]] = {
                year: _decimal_or_zero(year_map.get(year)) for year in wanted_years
            }
        inputs[slug] = sheet_inputs
    return inputs
