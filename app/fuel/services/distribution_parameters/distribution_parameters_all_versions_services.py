# -*- coding: utf-8 -*-
"""Синхронизация параметров распределения во всех версиях БД (по ref_uuid)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import joinedload

from app.extensions import db
from app.fuel.models.fue_distribution_parameter_model import DistributionParameter
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.years.year_model import Year
from app.refdata.services.refdata_all_versions_common import (
    all_database_version_ids_for_refdata,
    new_shared_ref_uuid,
)

# Поля данных (не FK версии) — копируются во все версии.
DP_SYNC_DATA_ATTRS: tuple[str, ...] = (
    "filter_text",
    "e",
    "kplus",
    "kmin",
    "k",
    "bkl",
    "wname",
    "uname",
    "toplname",
    "dopname",
    "kn",
    "knps",
    "kngt",
    "knpg",
    "hnps",
    "hngt",
    "hnpg",
    "numb",
    "doptim",
    "lim",
)


def year_id_for_version(year_number: int | None, version_id: int) -> int | None:
    if year_number is None:
        return None
    row = (
        Year.query.filter(
            Year.number == int(year_number),
            Year.database_version_id == version_id,
        ).first()
    )
    return int(row.id) if row else None


def year_number_by_id(year_id: int | None) -> int | None:
    if year_id is None:
        return None
    row = db.session.get(Year, int(year_id))
    return int(row.number) if row and row.number is not None else None


def ues_ref_uuid_by_id(ues_id: int | None) -> str | None:
    if ues_id is None:
        return None
    row = db.session.get(UnionEnergySystem, int(ues_id))
    return row.ref_uuid if row and row.ref_uuid else None


def ues_id_for_version(ues_ref_uuid: str | None, version_id: int) -> int | None:
    if not ues_ref_uuid:
        return None
    row = (
        UnionEnergySystem.query.filter(
            UnionEnergySystem.ref_uuid == ues_ref_uuid,
            UnionEnergySystem.database_version_id == version_id,
        ).first()
    )
    return int(row.id) if row else None


def ensure_dp_ref_uuid(dp: DistributionParameter) -> str:
    if dp.ref_uuid and str(dp.ref_uuid).strip():
        return str(dp.ref_uuid).strip()
    dp.ref_uuid = new_shared_ref_uuid()
    return dp.ref_uuid


def find_dp_by_ref_uuid_in_version(
    ref_uuid: str, version_id: int
) -> DistributionParameter | None:
    return (
        DistributionParameter.query.filter(
            DistributionParameter.ref_uuid == ref_uuid,
            DistributionParameter.database_version_id == version_id,
        )
        .order_by(DistributionParameter.id.asc())
        .first()
    )


def find_dp_by_logical_key_in_version(
    *,
    version_id: int,
    ues_ref_uuid: str | None,
    year_number: int | None,
    base_year_number: int | None,
) -> DistributionParameter | None:
    """Поиск без ref_uuid: ОЭС (ref_uuid) + номера годов в конкретной версии."""
    id_year = year_id_for_version(year_number, version_id)
    if id_year is None:
        return None
    id_ues = ues_id_for_version(ues_ref_uuid, version_id)
    id_base = year_id_for_version(base_year_number, version_id)

    q = DistributionParameter.query.filter(
        DistributionParameter.database_version_id == version_id,
        DistributionParameter.id_year == id_year,
    )
    if id_ues is None:
        q = q.filter(DistributionParameter.id_union_energy_system.is_(None))
    else:
        q = q.filter(DistributionParameter.id_union_energy_system == id_ues)
    if id_base is None:
        q = q.filter(DistributionParameter.id_base_year.is_(None))
    else:
        q = q.filter(DistributionParameter.id_base_year == id_base)
    return q.order_by(DistributionParameter.id.asc()).first()


def apply_dp_data_fields(dp: DistributionParameter, data: dict[str, Any]) -> None:
    for attr in DP_SYNC_DATA_ATTRS:
        if attr in data:
            setattr(dp, attr, data[attr])


def upsert_distribution_parameter_in_all_versions(
    *,
    ref_uuid: str | None,
    ues_ref_uuid: str | None,
    year_number: int,
    base_year_number: int | None,
    data: dict[str, Any],
) -> tuple[str, int, int, list[str]]:
    """
    Создаёт/обновляет копию параметра во всех версиях БД.

    Returns:
        (ref_uuid, added, updated, warnings)
    """
    version_ids = all_database_version_ids_for_refdata()
    if not version_ids:
        raise ValueError(
            "В системе нет зарегистрированных версий БД — "
            "нельзя сохранить параметры распределения во всех версиях."
        )

    shared_ref = (ref_uuid or "").strip() or None
    if not shared_ref:
        # Ищем уже существующую логическую строку в любой версии
        for vid in version_ids:
            found = find_dp_by_logical_key_in_version(
                version_id=vid,
                ues_ref_uuid=ues_ref_uuid,
                year_number=year_number,
                base_year_number=base_year_number,
            )
            if found is not None:
                shared_ref = ensure_dp_ref_uuid(found)
                break
    if not shared_ref:
        shared_ref = new_shared_ref_uuid()

    added = 0
    updated = 0
    warnings: list[str] = []

    for vid in version_ids:
        id_year = year_id_for_version(year_number, vid)
        if id_year is None:
            warnings.append(
                f"Версия БД id={vid}: нет года {year_number} в справочнике — пропуск."
            )
            continue
        id_base = year_id_for_version(base_year_number, vid) if base_year_number is not None else None
        if base_year_number is not None and id_base is None:
            warnings.append(
                f"Версия БД id={vid}: нет базового года {base_year_number} — пропуск."
            )
            continue
        id_ues = ues_id_for_version(ues_ref_uuid, vid) if ues_ref_uuid else None
        if ues_ref_uuid and id_ues is None:
            warnings.append(
                f"Версия БД id={vid}: нет ОЭС с ref_uuid={ues_ref_uuid} — пропуск."
            )
            continue

        dp = find_dp_by_ref_uuid_in_version(shared_ref, vid)
        if dp is None:
            dp = find_dp_by_logical_key_in_version(
                version_id=vid,
                ues_ref_uuid=ues_ref_uuid,
                year_number=year_number,
                base_year_number=base_year_number,
            )
            if dp is not None:
                dp.ref_uuid = shared_ref

        if dp is None:
            dp = DistributionParameter(
                ref_uuid=shared_ref,
                database_version_id=vid,
                id_union_energy_system=id_ues,
                id_year=id_year,
                id_base_year=id_base,
            )
            apply_dp_data_fields(dp, data)
            db.session.add(dp)
            added += 1
        else:
            dp.ref_uuid = shared_ref
            dp.database_version_id = vid
            dp.id_union_energy_system = id_ues
            dp.id_year = id_year
            dp.id_base_year = id_base
            apply_dp_data_fields(dp, data)
            updated += 1

    return shared_ref, added, updated, warnings


def delete_distribution_parameter_in_all_versions(row_id: int) -> list[int]:
    """
    Удаляет параметр и все его копии по ref_uuid во всех версиях.
    Зависимые сводки/результаты «Коэфф» удаляются явно (ORM иначе обнуляет FK).

    Returns:
        список удалённых id
    """
    from app.fuel.models.coefficient.distribution_coefficient_summary_model import (
        DistributionCoefficientSummary,
    )
    from app.fuel.models.coefficient.equipment_group_coefficient_result_model import (
        EquipmentGroupCoefficientResult,
    )

    anchor = db.session.get(DistributionParameter, row_id)
    if anchor is None:
        return []

    ref = ensure_dp_ref_uuid(anchor)
    targets = (
        DistributionParameter.query.filter(DistributionParameter.ref_uuid == ref)
        .order_by(DistributionParameter.id.asc())
        .all()
    )
    if not targets:
        targets = [anchor]

    deleted_ids: list[int] = []
    for dp in targets:
        did = int(dp.id)
        DistributionCoefficientSummary.query.filter_by(
            distribution_parameter_id=did
        ).delete(synchronize_session=False)
        EquipmentGroupCoefficientResult.query.filter_by(
            distribution_parameter_id=did
        ).delete(synchronize_session=False)
        db.session.delete(dp)
        deleted_ids.append(did)
    return deleted_ids


def logical_identity_from_dp(dp: DistributionParameter) -> tuple[str | None, int | None, int | None]:
    """(ues_ref_uuid, year_number, base_year_number) для якоря."""
    dp = (
        DistributionParameter.query.options(
            joinedload(DistributionParameter.union_energy_system),
            joinedload(DistributionParameter.year),
            joinedload(DistributionParameter.base_year),
        )
        .filter(DistributionParameter.id == dp.id)
        .first()
    ) or dp
    ues_uuid = None
    if dp.union_energy_system and dp.union_energy_system.ref_uuid:
        ues_uuid = dp.union_energy_system.ref_uuid
    elif dp.id_union_energy_system:
        ues_uuid = ues_ref_uuid_by_id(dp.id_union_energy_system)
    yn = dp.year.number if dp.year else year_number_by_id(dp.id_year)
    byn = (
        dp.base_year.number
        if dp.base_year
        else year_number_by_id(dp.id_base_year)
    )
    return ues_uuid, yn, byn
