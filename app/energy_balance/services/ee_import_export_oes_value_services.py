# -*- coding: utf-8 -*-
"""Пересчёт сохраняемых годовых агрегатов импорта/экспорта ЭЭ по ОЭС."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from app.common.services.database_version_filter import filter_by_explicit_db_version
from app.energy_balance.models.ee_import_export_oes_value_model import EeImportExportOesValue
from app.energy_balance.models.regional_energy_system_transfer_model import (
    EE_TRANSFER_PERIOD_YEAR,
    RegionalEnergySystemTransfer,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_display_order_map,
    get_union_energy_systems_map,
)
from app.energy_balance.services.ee_transfers_page_services import (
    _get_res_territory_maps,
    _infer_transfer_ues_id,
)
from app.extensions import db


def recalculate_ee_import_export_oes_values(*, year_number: int, version_id: int | None) -> None:
    """Синхронизировать агрегаты ОЭС со всеми годовыми строками-перетоками за год."""
    transfers = filter_by_explicit_db_version(
        RegionalEnergySystemTransfer.query, RegionalEnergySystemTransfer, version_id
    ).filter(
        RegionalEnergySystemTransfer.year_number == year_number,
        RegionalEnergySystemTransfer.month_number == EE_TRANSFER_PERIOD_YEAR,
        RegionalEnergySystemTransfer.id_to_foreign_border_country.isnot(None),
    ).all()

    territory_maps = _get_res_territory_maps()
    rd_res_map = territory_maps["rd_res_map"]
    needs_res_ranking = any(
        transfer.id_from_regional_district is not None
        and len(rd_res_map.get(transfer.id_from_regional_district, set())) > 1
        for transfer in transfers
    )
    ues_names = dict(get_union_energy_systems_map()) if needs_res_ranking else {}
    display_orders = get_union_energy_system_display_order_map() if needs_res_ranking else {}
    totals: dict[tuple[int, int], Decimal] = defaultdict(Decimal)
    for transfer in transfers:
        ues_id = _infer_transfer_ues_id(
            transfer,
            res_ues_map=territory_maps["res_ues_map"],
            rd_res_map=rd_res_map,
            tites_ues_ids=territory_maps.get("tites_ues_ids", set()),
            ues_names=ues_names,
            display_orders=display_orders,
        )
        if ues_id is None or transfer.transfer_value is None:
            continue
        key = (ues_id, transfer.id_to_foreign_border_country)
        totals[key] += Decimal(str(transfer.transfer_value))

    existing = filter_by_explicit_db_version(
        EeImportExportOesValue.query, EeImportExportOesValue, version_id
    ).filter_by(year_number=year_number).all()
    existing_by_key = {
        (record.id_union_energy_system, record.id_foreign_border_country): record
        for record in existing
    }

    for key, value in totals.items():
        record = existing_by_key.pop(key, None)
        if record is None:
            record = EeImportExportOesValue(
                id_union_energy_system=key[0],
                id_foreign_border_country=key[1],
                year_number=year_number,
                database_version_id=version_id,
                transfer_value=value,
            )
            db.session.add(record)
        else:
            record.transfer_value = value

    for obsolete in existing_by_key.values():
        db.session.delete(obsolete)
