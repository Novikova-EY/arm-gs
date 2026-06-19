# -*- coding: utf-8 -*-
"""Сопоставление наименований из сводов ОЭС со справочниками для перетоков ЭЭ."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.common.services.database_version_filter import filter_by_explicit_db_version
from app.energy_balance.services.ee_generation_import_services import _normalize_name
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.territories.foreign_border_country_model import ForeignBorderCountry
from app.refdata.models.territories.regional_district_model import RegionalDistrict

_MODEL_ANCHORS: dict[type, dict[str, Any]] = {}


def _name_matches(candidate: str | None, norm: str) -> bool:
    return bool(candidate) and _normalize_name(candidate) == norm


def _get_model_anchors(model_cls: type, name_fields: tuple[str, ...]) -> dict[str, Any]:
    cache_key = (model_cls, name_fields)
    if cache_key not in _MODEL_ANCHORS:
        anchors: dict[str, Any] = {}
        for item in model_cls.query.all():
            for field_name in name_fields:
                norm = _normalize_name(getattr(item, field_name, None))
                if norm and norm not in anchors:
                    anchors[norm] = item
        _MODEL_ANCHORS[cache_key] = anchors
    return _MODEL_ANCHORS[cache_key]


@dataclass
class _ModelNameResolver:
    version_id: int | None
    version_map: dict[str, int] = field(default_factory=dict)
    ref_uuid_map: dict[str, int] = field(default_factory=dict)
    anchors_by_norm: dict[str, Any] = field(default_factory=dict)

    def resolve(self, name: str) -> int | None:
        norm = _normalize_name(name)
        if not norm:
            return None
        direct_id = self.version_map.get(norm)
        if direct_id is not None:
            return direct_id
        anchor = self.anchors_by_norm.get(norm)
        if anchor is None:
            return None
        ref_uuid = (getattr(anchor, "ref_uuid", None) or "").strip()
        if ref_uuid:
            mapped_id = self.ref_uuid_map.get(ref_uuid)
            if mapped_id is not None:
                return mapped_id
        if getattr(anchor, "database_version_id", None) == self.version_id:
            return anchor.id
        return None


def _build_model_name_resolver(
    model_cls: type,
    version_id: int | None,
    name_fields: tuple[str, ...],
) -> _ModelNameResolver:
    version_map: dict[str, int] = {}
    ref_uuid_map: dict[str, int] = {}
    for item in filter_by_explicit_db_version(model_cls.query, model_cls, version_id).all():
        ref_uuid = (getattr(item, "ref_uuid", None) or "").strip()
        if ref_uuid:
            ref_uuid_map[ref_uuid] = item.id
        for field_name in name_fields:
            norm = _normalize_name(getattr(item, field_name, None))
            if norm and norm not in version_map:
                version_map[norm] = item.id
    return _ModelNameResolver(
        version_id=version_id,
        version_map=version_map,
        ref_uuid_map=ref_uuid_map,
        anchors_by_norm=_get_model_anchors(model_cls, name_fields),
    )


@dataclass
class TransferImportResolver:
    version_id: int | None
    res: _ModelNameResolver
    rd: _ModelNameResolver
    country: _ModelNameResolver
    energy_unit: _ModelNameResolver

    @classmethod
    def build(cls, version_id: int | None) -> TransferImportResolver:
        return cls(
            version_id=version_id,
            res=_build_model_name_resolver(
                RegionalEnergySystem,
                version_id,
                ("name", "name_full", "name_rp"),
            ),
            rd=_build_model_name_resolver(
                RegionalDistrict,
                version_id,
                ("name", "name_full", "name_rp", "name_dp"),
            ),
            country=_build_model_name_resolver(
                ForeignBorderCountry,
                version_id,
                ("name",),
            ),
            energy_unit=_build_model_name_resolver(
                EnergyUnit,
                version_id,
                ("name", "name_rp", "name_dp"),
            ),
        )

    def resolve_from_source(self, name: str) -> ResolvedFromSource:
        res_id = self.res.resolve(name)
        if res_id is not None:
            return ResolvedFromSource(res_id=res_id)
        rd_id = self.rd.resolve(name)
        return ResolvedFromSource(rd_id=rd_id)

    def resolve_to_target(self, name: str) -> ResolvedToTarget:
        res_id = self.res.resolve(name)
        if res_id is not None:
            return ResolvedToTarget(res_id=res_id)
        country_id = self.country.resolve(name)
        if country_id is not None:
            return ResolvedToTarget(country_id=country_id)
        rd_id = self.rd.resolve(name)
        if rd_id is not None:
            return ResolvedToTarget(rd_id=rd_id)
        eu_id = self.energy_unit.resolve(name)
        return ResolvedToTarget(energy_unit_id=eu_id)

    def has_country_anchor(self, name: str) -> bool:
        return _normalize_name(name) in self.country.anchors_by_norm

    def has_energy_unit_anchor(self, name: str) -> bool:
        return _normalize_name(name) in self.energy_unit.anchors_by_norm


def clear_transfer_import_resolver_cache() -> None:
    _MODEL_ANCHORS.clear()


def _resolve_refdata_id_by_name(
    *,
    model_cls,
    name: str,
    version_id: int | None,
    name_fields: tuple[str, ...],
) -> int | None:
    norm = _normalize_name(name)
    if not norm:
        return None

    q = filter_by_explicit_db_version(model_cls.query, model_cls, version_id)
    for item in q.all():
        for field in name_fields:
            if _name_matches(getattr(item, field, None), norm):
                return item.id

    anchor = None
    for item in model_cls.query.all():
        for field in name_fields:
            if _name_matches(getattr(item, field, None), norm):
                anchor = item
                break
        if anchor is not None:
            break
    if anchor is None:
        return None

    ref_uuid = (getattr(anchor, "ref_uuid", None) or "").strip()
    if ref_uuid:
        tgt = (
            filter_by_explicit_db_version(model_cls.query, model_cls, version_id)
            .filter(model_cls.ref_uuid == ref_uuid)
            .first()
        )
        if tgt:
            return tgt.id

    if getattr(anchor, "database_version_id", None) == version_id:
        return anchor.id
    return None


def _resolve_res_id_by_name(res_name: str, version_id: int | None) -> int | None:
    return _resolve_refdata_id_by_name(
        model_cls=RegionalEnergySystem,
        name=res_name,
        version_id=version_id,
        name_fields=("name", "name_full", "name_rp"),
    )


def _resolve_rd_id_by_name(rd_name: str, version_id: int | None) -> int | None:
    return _resolve_refdata_id_by_name(
        model_cls=RegionalDistrict,
        name=rd_name,
        version_id=version_id,
        name_fields=("name", "name_full", "name_rp", "name_dp"),
    )


def _resolve_energy_unit_id_by_name(eu_name: str, version_id: int | None) -> int | None:
    return _resolve_refdata_id_by_name(
        model_cls=EnergyUnit,
        name=eu_name,
        version_id=version_id,
        name_fields=("name", "name_rp", "name_dp"),
    )


def _find_energy_unit_anchor(eu_name: str) -> EnergyUnit | None:
    norm = _normalize_name(eu_name)
    if not norm:
        return None
    for eu in EnergyUnit.query.all():
        for field in ("name", "name_rp", "name_dp"):
            if _name_matches(getattr(eu, field, None), norm):
                return eu
    return None


def _find_foreign_border_country_anchor(country_name: str) -> ForeignBorderCountry | None:
    norm = _normalize_name(country_name)
    if not norm:
        return None
    for country in ForeignBorderCountry.query.all():
        if _name_matches(country.name, norm):
            return country
    return None


def _resolve_foreign_border_country_id_by_name(
    country_name: str,
    version_id: int | None,
) -> int | None:
    return _resolve_refdata_id_by_name(
        model_cls=ForeignBorderCountry,
        name=country_name,
        version_id=version_id,
        name_fields=("name",),
    )


@dataclass
class ResolvedFromSource:
    res_id: int | None = None
    rd_id: int | None = None


@dataclass
class ResolvedToTarget:
    res_id: int | None = None
    country_id: int | None = None
    rd_id: int | None = None
    energy_unit_id: int | None = None


def resolve_from_source(name: str, version_id: int | None) -> ResolvedFromSource:
    res_id = _resolve_res_id_by_name(name, version_id)
    if res_id is not None:
        return ResolvedFromSource(res_id=res_id)
    rd_id = _resolve_rd_id_by_name(name, version_id)
    return ResolvedFromSource(rd_id=rd_id)


def resolve_to_target(name: str, version_id: int | None) -> ResolvedToTarget:
    res_id = _resolve_res_id_by_name(name, version_id)
    if res_id is not None:
        return ResolvedToTarget(res_id=res_id)
    country_id = _resolve_foreign_border_country_id_by_name(name, version_id)
    if country_id is not None:
        return ResolvedToTarget(country_id=country_id)
    rd_id = _resolve_rd_id_by_name(name, version_id)
    if rd_id is not None:
        return ResolvedToTarget(rd_id=rd_id)
    eu_id = _resolve_energy_unit_id_by_name(name, version_id)
    return ResolvedToTarget(energy_unit_id=eu_id)
