# -*- coding: utf-8 -*-
"""Сохранение годовых значений приема/передачи ЭЭ между ОЭС."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.common.services.database_version_filter import (
    filter_by_db_version,
    filter_by_explicit_db_version,
    get_current_db_version_id,
)
from app.common.services.help_services import parse_decimal_from_display
from app.common.services.tranzaction_services import _commit_with_retry
from app.energy_balance.models.ee_receive_transfer_oes_value_model import (
    EeReceiveTransferOesValue,
)
from app.energy_balance.models.regional_energy_system_transfer_model import (
    EE_TRANSFER_PERIOD_YEAR,
    RegionalEnergySystemTransfer,
)
from app.energy_balance.services.energy_balance_cache import clear_energy_balance_cache
from app.energy_balance.services.ee_transfers_page_services import (
    _get_res_territory_maps,
    _infer_transfer_target_res_id,
    _infer_transfer_ues_id,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_display_order_map,
    get_union_energy_systems_map,
)
from app.extensions import db
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem


def load_ee_receive_transfer_oes_values(
    *,
    version_id: int | None = None,
    years: list[int] | None = None,
) -> dict[tuple[int, int, int], Decimal | None]:
    """Сохранённые значения по ключу (источник ОЭС, принимающая ОЭС, год)."""
    query = filter_by_explicit_db_version(
        EeReceiveTransferOesValue.query,
        EeReceiveTransferOesValue,
        get_current_db_version_id() if version_id is None else version_id,
    )
    if years:
        query = query.filter(
            EeReceiveTransferOesValue.year_number.in_([int(year) for year in years])
        )
    return {
        (
            record.id_source_union_energy_system,
            record.id_target_union_energy_system,
            int(record.year_number),
        ): Decimal(str(record.transfer_value))
        if record.transfer_value is not None
        else None
        for record in query.all()
    }


def recalculate_ee_receive_transfer_oes_values(
    *, year_number: int, version_id: int | None
) -> None:
    territory_maps = _get_res_territory_maps()
    ues_names = dict(get_union_energy_systems_map())
    display_orders = get_union_energy_system_display_order_map()
    transfers = filter_by_explicit_db_version(
        RegionalEnergySystemTransfer.query, RegionalEnergySystemTransfer, version_id
    ).filter(
        RegionalEnergySystemTransfer.year_number == year_number,
        RegionalEnergySystemTransfer.month_number == EE_TRANSFER_PERIOD_YEAR,
    ).all()

    totals: dict[tuple[int, int], Decimal] = {}
    for transfer in transfers:
        source_ues_id = _infer_transfer_ues_id(
            transfer,
            res_ues_map=territory_maps["res_ues_map"],
            rd_res_map=territory_maps["rd_res_map"],
            tites_ues_ids=territory_maps.get("tites_ues_ids", set()),
            ues_names=ues_names,
            display_orders=display_orders,
        )
        target_res_id = _infer_transfer_target_res_id(
            {
                "to_res_id": getattr(transfer, "id_to_regional_energy_system", None),
                "to_rd_id": getattr(transfer, "id_to_regional_district", None),
                "to_eu_id": getattr(transfer, "id_to_energy_unit", None),
            },
            territory_maps=territory_maps,
            ues_names=ues_names,
            display_orders=display_orders,
        )
        target_ues_id = territory_maps["res_ues_map"].get(target_res_id)
        if (
            source_ues_id is None
            or target_ues_id is None
            or source_ues_id == target_ues_id
            or transfer.transfer_value is None
        ):
            continue

        key = (source_ues_id, target_ues_id)
        totals[key] = totals.get(key, Decimal(0)) + Decimal(str(transfer.transfer_value))

    existing = filter_by_explicit_db_version(
        EeReceiveTransferOesValue.query, EeReceiveTransferOesValue, version_id
    ).filter_by(year_number=year_number).all()
    existing_by_key = {
        (record.id_source_union_energy_system, record.id_target_union_energy_system): record
        for record in existing
    }

    for key, value in totals.items():
        record = existing_by_key.pop(key, None)
        if record is None:
            db.session.add(
                EeReceiveTransferOesValue(
                    id_source_union_energy_system=key[0],
                    id_target_union_energy_system=key[1],
                    year_number=year_number,
                    transfer_value=value,
                    database_version_id=version_id,
                )
            )
        else:
            record.transfer_value = value

    for obsolete in existing_by_key.values():
        db.session.delete(obsolete)


def update_ee_receive_transfer_value(
    *,
    source_ues_id: int,
    target_ues_id: int,
    year: int,
    raw_value: Any,
) -> dict[str, Any]:
    try:
        year_number = int(year)
        source_ues_id = int(source_ues_id)
        target_ues_id = int(target_ues_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Неверные данные ячейки") from exc

    if year_number < 1:
        raise ValueError("Неверный год")
    if source_ues_id == target_ues_id:
        raise ValueError("Нельзя сохранить переток внутри одной ОЭС")

    try:
        value = parse_decimal_from_display(raw_value)
    except InvalidOperation as exc:
        raise ValueError("Введите корректное число") from exc
    if value is not None and not value.is_finite():
        raise ValueError("Введите конечное числовое значение")

    source = (
        filter_by_db_version(UnionEnergySystem.query, UnionEnergySystem)
        .filter_by(id=source_ues_id)
        .first()
    )
    if source is None:
        raise ValueError("Источник не найден в текущей версии БД")
    target = (
        filter_by_db_version(UnionEnergySystem.query, UnionEnergySystem)
        .filter_by(id=target_ues_id)
        .first()
    )
    if target is None:
        raise ValueError("Приёмщик не найден в текущей версии БД")

    version_id = get_current_db_version_id()
    existing = (
        filter_by_explicit_db_version(
            EeReceiveTransferOesValue.query,
            EeReceiveTransferOesValue,
            version_id,
        )
        .filter_by(
            id_source_union_energy_system=source_ues_id,
            id_target_union_energy_system=target_ues_id,
            year_number=year_number,
        )
        .first()
    )

    if value is None:
        if existing is None:
            db.session.add(
                EeReceiveTransferOesValue(
                    id_source_union_energy_system=source_ues_id,
                    id_target_union_energy_system=target_ues_id,
                    year_number=year_number,
                    transfer_value=None,
                    database_version_id=version_id,
                )
            )
        else:
            existing.transfer_value = None
    elif existing is None:
        db.session.add(
            EeReceiveTransferOesValue(
                id_source_union_energy_system=source_ues_id,
                id_target_union_energy_system=target_ues_id,
                year_number=year_number,
                transfer_value=value,
                database_version_id=version_id,
            )
        )
    else:
        existing.transfer_value = value

    _commit_with_retry()
    clear_energy_balance_cache()
    return {"year": year_number, "value": value}


update_ee_receive_transfer_oes_value = update_ee_receive_transfer_value
