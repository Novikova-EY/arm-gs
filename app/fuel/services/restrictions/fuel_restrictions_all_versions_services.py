# -*- coding: utf-8 -*-
"""Синхронизация «Ограничения» во всех версиях БД (ключ year + oes + obl)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.extensions import db
from app.fuel.models.fue_restriction_model import FuelRestriction
from app.refdata.services.refdata_all_versions_common import (
    all_database_version_ids_for_refdata,
)

# Поля данных (кроме ключа и database_version_id) — копируются во все версии.
FR_SYNC_DATA_ATTRS: tuple[str, ...] = (
    "restriction_name",
    "emin",
    "emax",
    "ecur",
    "h",
    "ecurdis",
    "hdis",
    "etp",
    "kobl",
    "kcur",
)


def _as_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _row_key(
    year: Decimal | None, oes: Decimal | None, obl: Decimal | None
) -> tuple[Decimal, Decimal, Decimal] | None:
    if year is None or oes is None or obl is None:
        return None
    return (Decimal(year), Decimal(oes), Decimal(obl))


def find_restriction_by_key_in_version(
    *,
    version_id: int,
    year: Decimal,
    oes: Decimal,
    obl: Decimal,
) -> FuelRestriction | None:
    return (
        FuelRestriction.query.filter(
            FuelRestriction.database_version_id == version_id,
            FuelRestriction.year == year,
            FuelRestriction.oes == oes,
            FuelRestriction.obl == obl,
        )
        .order_by(FuelRestriction.id.asc())
        .first()
    )


def apply_fr_data_fields(row: FuelRestriction, data: dict[str, Any]) -> None:
    for attr in FR_SYNC_DATA_ATTRS:
        if attr in data:
            setattr(row, attr, data[attr])


def data_dict_from_restriction(row: FuelRestriction) -> dict[str, Any]:
    return {attr: getattr(row, attr, None) for attr in FR_SYNC_DATA_ATTRS}


def upsert_fuel_restriction_in_all_versions(
    *,
    year: Decimal | int | None,
    oes: Decimal | int | None,
    obl: Decimal | int | None,
    data: dict[str, Any],
    match_year: Decimal | int | None = None,
    match_oes: Decimal | int | None = None,
    match_obl: Decimal | int | None = None,
) -> tuple[int, int, list[str]]:
    """
    Создаёт/обновляет копию ограничения во всех версиях БД.

    Поиск: (match_year, match_oes, match_obl) если заданы (старый ключ при
    смене year/oes/obl), иначе (year, oes, obl).

    Returns:
        (added, updated, warnings)
    """
    year_v = _as_decimal(year)
    oes_v = _as_decimal(oes)
    obl_v = _as_decimal(obl)
    if year_v is None or oes_v is None or obl_v is None:
        raise ValueError("Для синхронизации ограничений нужны year, oes и obl.")

    match_y = _as_decimal(match_year) if match_year is not None else year_v
    match_o = _as_decimal(match_oes) if match_oes is not None else oes_v
    match_b = _as_decimal(match_obl) if match_obl is not None else obl_v
    if match_y is None or match_o is None or match_b is None:
        match_y, match_o, match_b = year_v, oes_v, obl_v

    version_ids = all_database_version_ids_for_refdata()
    if not version_ids:
        raise ValueError(
            "В системе нет зарегистрированных версий БД — "
            "нельзя сохранить ограничения во всех версиях."
        )

    added = 0
    updated = 0
    warnings: list[str] = []

    for vid in version_ids:
        row = find_restriction_by_key_in_version(
            version_id=vid, year=match_y, oes=match_o, obl=match_b
        )
        # Если ключ сменился — ищем ещё и по новому ключу (на случай коллизии).
        if row is None and (match_y, match_o, match_b) != (year_v, oes_v, obl_v):
            row = find_restriction_by_key_in_version(
                version_id=vid, year=year_v, oes=oes_v, obl=obl_v
            )

        if row is None:
            row = FuelRestriction(
                database_version_id=vid,
                year=year_v,
                oes=oes_v,
                obl=obl_v,
            )
            apply_fr_data_fields(row, data)
            db.session.add(row)
            added += 1
        else:
            row.year = year_v
            row.oes = oes_v
            row.obl = obl_v
            row.database_version_id = vid
            apply_fr_data_fields(row, data)
            updated += 1

    return added, updated, warnings


def delete_fuel_restriction_in_all_versions(row_id: int) -> list[int]:
    """
    Удаляет ограничение и все его копии с тем же (year, oes, obl) во всех версиях.

    Returns:
        список удалённых id
    """
    anchor = db.session.get(FuelRestriction, row_id)
    if anchor is None:
        return []

    key = _row_key(anchor.year, anchor.oes, anchor.obl)
    deleted_ids: list[int] = []

    if key is None:
        did = int(anchor.id)
        db.session.delete(anchor)
        return [did]

    year_v, oes_v, obl_v = key
    targets = (
        FuelRestriction.query.filter(
            FuelRestriction.year == year_v,
            FuelRestriction.oes == oes_v,
            FuelRestriction.obl == obl_v,
        )
        .order_by(FuelRestriction.id.asc())
        .all()
    )
    if not targets:
        targets = [anchor]

    for row in targets:
        deleted_ids.append(int(row.id))
        db.session.delete(row)
    return deleted_ids
