# -*- coding: utf-8 -*-
"""Данные для страницы «Ограничения» (/fuel/restrictions)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable

from sqlalchemy import nullslast

from app.common.services.database_version_filter import (
    filter_by_db_version,
    get_current_db_version_id,
)
from app.fuel.models.external_mapping.fue_em_territories_energy_model import (
    TerritoriesEnergyExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_union_energy_system_model import (
    UnionEnergySystemExternalMapping,
)
from app.fuel.models.fue_restriction_model import FuelRestriction
from app.refdata.models.energy_systems.regional_energy_system_model import (
    RegionalEnergySystem,
)
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem


def _code_key(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return str(int(value))
    except (TypeError, ValueError):
        text = str(value).strip()
        return text or None


def _codes_from_values(values: Iterable[Any]) -> list[Decimal]:
    result: list[Decimal] = []
    for x in values:
        key = _code_key(x)
        if key is None:
            continue
        try:
            result.append(Decimal(int(key)))
        except (TypeError, ValueError):
            continue
    return result


def resolve_oes_codes_from_union_energy_system_ids(
    ues_ids: list[int] | None,
) -> list[Decimal]:
    """UnionEnergySystem.id → Access-коды oes (external_id маппинга)."""
    if not ues_ids:
        return []
    ids = [int(x) for x in ues_ids if x is not None]
    if not ids:
        return []
    version_id = get_current_db_version_id()
    ues_q = UnionEnergySystem.query.filter(UnionEnergySystem.id.in_(ids))
    if version_id is not None:
        ues_q = ues_q.filter(UnionEnergySystem.database_version_id == version_id)
    uuids = [u.ref_uuid for u in ues_q.all() if u.ref_uuid]
    if not uuids:
        return []
    mappings = UnionEnergySystemExternalMapping.query.filter(
        UnionEnergySystemExternalMapping.union_energy_system_ref_uuid.in_(uuids),
        UnionEnergySystemExternalMapping.external_id.isnot(None),
    ).all()
    return _codes_from_values(m.external_id for m in mappings)


def resolve_obl_codes_from_regional_energy_system_ids(
    res_ids: list[int] | None,
) -> list[Decimal]:
    """RegionalEnergySystem.id → Access-коды obl (external_id territories_energy)."""
    if not res_ids:
        return []
    ids = [int(x) for x in res_ids if x is not None]
    if not ids:
        return []
    version_id = get_current_db_version_id()
    res_q = RegionalEnergySystem.query.filter(RegionalEnergySystem.id.in_(ids))
    if version_id is not None:
        res_q = res_q.filter(RegionalEnergySystem.database_version_id == version_id)
    uuids = [r.ref_uuid for r in res_q.all() if r.ref_uuid]
    if not uuids:
        return []
    mappings = TerritoriesEnergyExternalMapping.query.filter(
        TerritoriesEnergyExternalMapping.regional_energy_system_ref_uuid.in_(uuids),
        TerritoriesEnergyExternalMapping.external_id.isnot(None),
    ).all()
    return _codes_from_values(m.external_id for m in mappings)


def get_fuel_restrictions_list(
    *,
    year_number: int | None = None,
    year_numbers: list[int] | None = None,
    oes_codes: list[int | str | Decimal] | None = None,
    obl_codes: list[int | str | Decimal] | None = None,
    union_energy_system_ids: list[int] | None = None,
    regional_energy_system_ids: list[int] | None = None,
) -> list[FuelRestriction]:
    """
    Список ограничений. Сортировка как в Access Form_Open: OrderBy = \"obl\".

    - year_number / year_numbers: фильтр по полю year (год расчёта); None — все.
    - oes_codes / union_energy_system_ids: фильтр по ОЭС (код Access или id справочника).
    - obl_codes / regional_energy_system_ids: фильтр по РЭС (код Access или id справочника).
    """
    q = filter_by_db_version(FuelRestriction.query, FuelRestriction)

    years: list[int] = []
    if year_numbers:
        years.extend(int(y) for y in year_numbers if y is not None)
    if year_number is not None:
        years.append(int(year_number))
    years = list(dict.fromkeys(years))
    if len(years) == 1:
        q = q.filter(FuelRestriction.year == Decimal(years[0]))
    elif years:
        q = q.filter(FuelRestriction.year.in_([Decimal(y) for y in years]))

    resolved_oes = list(oes_codes or [])
    if union_energy_system_ids:
        resolved_oes.extend(
            resolve_oes_codes_from_union_energy_system_ids(union_energy_system_ids)
        )
    oes_vals = _codes_from_values(resolved_oes)
    if union_energy_system_ids and not oes_vals:
        # Выбраны ОЭС без маппинга — пустая выборка, а не «все».
        q = q.filter(FuelRestriction.id == -1)
    elif oes_vals:
        q = q.filter(FuelRestriction.oes.in_(oes_vals))

    resolved_obl = list(obl_codes or [])
    if regional_energy_system_ids:
        resolved_obl.extend(
            resolve_obl_codes_from_regional_energy_system_ids(regional_energy_system_ids)
        )
    obl_vals = _codes_from_values(resolved_obl)
    if regional_energy_system_ids and not obl_vals:
        q = q.filter(FuelRestriction.id == -1)
    elif obl_vals:
        q = q.filter(FuelRestriction.obl.in_(obl_vals))

    return (
        q.order_by(
            nullslast(FuelRestriction.obl.asc()),
            FuelRestriction.id.asc(),
        )
        .all()
    )


def build_restriction_oes_name_map(
    rows: Iterable[FuelRestriction],
) -> dict[str, str]:
    """oes (external_id) → название ОЭС."""
    keys = {_code_key(r.oes) for r in rows if r.oes is not None}
    keys.discard(None)
    if not keys:
        return {}
    mappings = UnionEnergySystemExternalMapping.query.filter(
        UnionEnergySystemExternalMapping.external_id.in_(list(keys))
    ).all()
    uuid_to_name: dict[str, str] = {}
    uuids = [
        m.union_energy_system_ref_uuid
        for m in mappings
        if m.union_energy_system_ref_uuid
    ]
    if uuids:
        version_id = get_current_db_version_id()
        ues_q = UnionEnergySystem.query.filter(UnionEnergySystem.ref_uuid.in_(uuids))
        if version_id is not None:
            ues_q = ues_q.filter(UnionEnergySystem.database_version_id == version_id)
        for ues in ues_q.all():
            if ues.ref_uuid:
                uuid_to_name[ues.ref_uuid] = ues.name
    result: dict[str, str] = {}
    for m in mappings:
        if not m.external_id:
            continue
        name = (
            uuid_to_name.get(m.union_energy_system_ref_uuid or "")
            or m.external_nameoes
            or m.external_name
            or m.external_id
        )
        result[m.external_id] = name
    return result


def build_restriction_obl_name_map(
    rows: Iterable[FuelRestriction],
) -> dict[str, str]:
    """obl (external_id) → название РЭС (RegionalEnergySystem / mapping)."""
    keys = {_code_key(r.obl) for r in rows if r.obl is not None}
    keys.discard(None)
    if not keys:
        return {}
    mappings = TerritoriesEnergyExternalMapping.query.filter(
        TerritoriesEnergyExternalMapping.external_id.in_(list(keys))
    ).all()
    uuid_to_name: dict[str, str] = {}
    uuids = [
        m.regional_energy_system_ref_uuid
        for m in mappings
        if m.regional_energy_system_ref_uuid
    ]
    if uuids:
        version_id = get_current_db_version_id()
        res_q = RegionalEnergySystem.query.filter(
            RegionalEnergySystem.ref_uuid.in_(uuids)
        )
        if version_id is not None:
            res_q = res_q.filter(
                RegionalEnergySystem.database_version_id == version_id
            )
        for res in res_q.all():
            if res.ref_uuid:
                uuid_to_name[res.ref_uuid] = res.name
    result: dict[str, str] = {}
    for m in mappings:
        if not m.external_id:
            continue
        name = (
            uuid_to_name.get(m.regional_energy_system_ref_uuid or "")
            or m.external_name
            or m.name_ext
            or m.external_id
        )
        result[m.external_id] = name
    return result


def get_restriction_oes_choices() -> list[dict[str, Any]]:
    """Варианты ОЭС для фильтра и редактирования: value = external_id (oes)."""
    mappings = (
        UnionEnergySystemExternalMapping.query.filter(
            UnionEnergySystemExternalMapping.external_id.isnot(None)
        )
        .order_by(UnionEnergySystemExternalMapping.external_id.asc())
        .all()
    )
    if not mappings:
        return []
    uuids = [
        m.union_energy_system_ref_uuid
        for m in mappings
        if m.union_energy_system_ref_uuid
    ]
    uuid_to_name: dict[str, str] = {}
    if uuids:
        version_id = get_current_db_version_id()
        ues_q = UnionEnergySystem.query.filter(UnionEnergySystem.ref_uuid.in_(uuids))
        if version_id is not None:
            ues_q = ues_q.filter(UnionEnergySystem.database_version_id == version_id)
        for ues in ues_q.all():
            if ues.ref_uuid:
                uuid_to_name[ues.ref_uuid] = ues.name

    choices: list[dict[str, Any]] = []
    for m in mappings:
        if not m.external_id:
            continue
        name = (
            uuid_to_name.get(m.union_energy_system_ref_uuid or "")
            or m.external_nameoes
            or m.external_name
            or m.external_id
        )
        choices.append({"oes": m.external_id, "name": name})
    choices.sort(key=lambda c: (c["name"].lower() == "не указано", c["name"].lower()))
    return choices


def get_restriction_obl_choices() -> list[dict[str, Any]]:
    """Варианты РЭС для редактирования: value = external_id (obl)."""
    mappings = (
        TerritoriesEnergyExternalMapping.query.filter(
            TerritoriesEnergyExternalMapping.external_id.isnot(None)
        )
        .order_by(TerritoriesEnergyExternalMapping.external_id.asc())
        .all()
    )
    if not mappings:
        return []
    uuids = [
        m.regional_energy_system_ref_uuid
        for m in mappings
        if m.regional_energy_system_ref_uuid
    ]
    uuid_to_name: dict[str, str] = {}
    if uuids:
        version_id = get_current_db_version_id()
        res_q = RegionalEnergySystem.query.filter(
            RegionalEnergySystem.ref_uuid.in_(uuids)
        )
        if version_id is not None:
            res_q = res_q.filter(
                RegionalEnergySystem.database_version_id == version_id
            )
        for res in res_q.all():
            if res.ref_uuid:
                uuid_to_name[res.ref_uuid] = res.name

    choices: list[dict[str, Any]] = []
    for m in mappings:
        if not m.external_id:
            continue
        name = (
            uuid_to_name.get(m.regional_energy_system_ref_uuid or "")
            or m.external_name
            or m.name_ext
            or m.external_id
        )
        choices.append({"obl": m.external_id, "name": name})
    choices.sort(key=lambda c: (c["name"].lower() == "не указано", c["name"].lower()))
    return choices
