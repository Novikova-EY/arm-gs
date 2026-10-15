# -*- coding: utf-8 -*-
"""Сохранение значений перетоков электрической энергии."""

from __future__ import annotations

from decimal import InvalidOperation
from typing import Any

from app.common.services.database_version_filter import (
    filter_by_db_version,
    filter_by_explicit_db_version,
    get_current_db_version_id,
)
from app.common.services.help_services import parse_decimal_from_display
from app.common.services.tranzaction_services import _commit_with_retry
from app.extensions import db
from app.energy_balance.models.regional_energy_system_transfer_model import (
    EE_TRANSFER_PERIOD_YEAR,
    RegionalEnergySystemTransfer,
)
from app.energy_balance.services.energy_balance_cache import clear_energy_balance_cache
from app.energy_balance.services.ee_import_export_oes_value_services import (
    recalculate_ee_import_export_oes_values,
)
from app.energy_balance.services.ee_receive_transfer_oes_value_services import (
    recalculate_ee_receive_transfer_oes_values,
)
from app.energy_balance.services.ee_transfers_page_services import (
    _get_res_territory_maps,
    _infer_transfer_ues_id,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_display_order_map,
    get_union_energy_systems_map,
)
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem


_SOURCE_FIELDS = (
    "id_from_regional_energy_system",
    "id_from_regional_district",
)
_TARGET_FIELDS = (
    "id_to_regional_energy_system",
    "id_to_foreign_border_country",
    "id_to_regional_district",
    "id_to_energy_unit",
)


def _parse_optional_id(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _validate_transfer_identity(identity: dict[str, int | None]) -> None:
    if sum(identity[field] is not None for field in _SOURCE_FIELDS) != 1:
        raise ValueError("Не удалось определить источник перетока")
    if sum(identity[field] is not None for field in _TARGET_FIELDS) != 1:
        raise ValueError("Не удалось определить получателя перетока")


def _validate_transfer_period(year_number: int, month_number: int) -> None:
    if year_number < 1:
        raise ValueError("Неверный период перетока")
    if month_number == EE_TRANSFER_PERIOD_YEAR:
        return
    if not 1 <= month_number <= 12:
        raise ValueError("Неверный месяц периода перетока")


def update_ee_transfer_value(
    *,
    ues_id: Any,
    source_res_id: Any,
    source_rd_id: Any,
    target_res_id: Any,
    target_country_id: Any,
    target_rd_id: Any,
    target_energy_unit_id: Any,
    year: Any,
    month: Any,
    raw_value: Any,
) -> dict[str, Any]:
    try:
        year_number = int(year)
        month_number = int(month)
        union_energy_system_id = int(ues_id)
        identity = {
            "id_from_regional_energy_system": _parse_optional_id(source_res_id),
            "id_from_regional_district": _parse_optional_id(source_rd_id),
            "id_to_regional_energy_system": _parse_optional_id(target_res_id),
            "id_to_foreign_border_country": _parse_optional_id(target_country_id),
            "id_to_regional_district": _parse_optional_id(target_rd_id),
            "id_to_energy_unit": _parse_optional_id(target_energy_unit_id),
        }
    except (TypeError, ValueError) as exc:
        raise ValueError("Неверные данные ячейки") from exc

    _validate_transfer_period(year_number, month_number)
    _validate_transfer_identity(identity)

    try:
        value = parse_decimal_from_display(raw_value)
    except InvalidOperation as exc:
        raise ValueError("Введите корректное число") from exc
    if value is not None and not value.is_finite():
        raise ValueError("Введите конечное числовое значение")

    ues = filter_by_db_version(UnionEnergySystem.query, UnionEnergySystem).filter_by(
        id=union_energy_system_id
    ).first()
    if ues is None:
        raise ValueError("ОЭС не найдена в текущей версии БД")

    version_id = get_current_db_version_id()
    query = filter_by_explicit_db_version(
        RegionalEnergySystemTransfer.query,
        RegionalEnergySystemTransfer,
        version_id,
    ).filter_by(**identity)
    # Пары, в которых ОЭС выводится по источнику, могут храниться с NULL в поле ОЭС.
    territory_maps = _get_res_territory_maps()
    ues_names = dict(get_union_energy_systems_map())
    display_orders = get_union_energy_system_display_order_map()
    pair_records = query.all()
    matching_pair = next(
        (
            candidate
            for candidate in pair_records
            if candidate.id_union_energy_system == union_energy_system_id
            or (
                candidate.id_union_energy_system is None
                and _infer_transfer_ues_id(
                    candidate,
                    res_ues_map=territory_maps["res_ues_map"],
                    rd_res_map=territory_maps["rd_res_map"],
                    ues_names=ues_names,
                    display_orders=display_orders,
                )
                == union_energy_system_id
            )
        ),
        None,
    )
    if matching_pair is None:
        raise ValueError("Переток не найден в текущей версии БД")

    candidates = query.filter_by(year_number=year_number, month_number=month_number).all()
    record = next(
        (
            candidate
            for candidate in candidates
            if candidate.id_union_energy_system == union_energy_system_id
        ),
        None,
    )
    if record is None:
        record = next(
            (
                candidate
                for candidate in candidates
                if candidate.id_union_energy_system is None
                and _infer_transfer_ues_id(
                    candidate,
                    res_ues_map=territory_maps["res_ues_map"],
                    rd_res_map=territory_maps["rd_res_map"],
                    ues_names=ues_names,
                    display_orders=display_orders,
                )
                == union_energy_system_id
            ),
            None,
        )

    if record is None:
        record = RegionalEnergySystemTransfer(
            **identity,
            id_union_energy_system=union_energy_system_id,
            year_number=year_number,
            month_number=month_number,
            database_version_id=version_id,
            source_oes_name=matching_pair.source_oes_name,
            transfer_value=value,
        )
        db.session.add(record)

    if not record.source_oes_name:
        # Перетоки без ОЭС в файле выводятся на странице по ОЭС источника.
        record.source_oes_name = matching_pair.source_oes_name

    if month_number == EE_TRANSFER_PERIOD_YEAR:
        # Свод перетоков между ОЭС пересчитывается из завершённого годового периода.
        record.transfer_value = value
        db.session.flush()
        recalculate_ee_import_export_oes_values(year_number=year_number, version_id=version_id)
        recalculate_ee_receive_transfer_oes_values(year_number=year_number, version_id=version_id)
    else:
        record.transfer_value = value

    _commit_with_retry()
    clear_energy_balance_cache()
    return {"year": year_number, "month": month_number, "value": value}
