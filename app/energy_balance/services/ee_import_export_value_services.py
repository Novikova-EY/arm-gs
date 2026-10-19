# -*- coding: utf-8 -*-
"""Сохранение годовых значений импорта/экспорта ЭЭ по ОЭС и стране."""

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
from app.energy_balance.models.ee_import_export_oes_value_model import EeImportExportOesValue
from app.energy_balance.services.energy_balance_cache import clear_energy_balance_cache
from app.energy_balance.services.change_log_services import log_cell_change
from app.extensions import db
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.territories.foreign_border_country_model import ForeignBorderCountry


def load_ee_import_export_oes_values(
    *,
    version_id: int | None = None,
    years: list[int] | None = None,
) -> dict[tuple[int, int, int], Decimal | None]:
    """Сохранённые значения по ключу (ОЭС, страна, год) для текущей версии БД."""
    query = filter_by_explicit_db_version(
        EeImportExportOesValue.query,
        EeImportExportOesValue,
        get_current_db_version_id() if version_id is None else version_id,
    )
    if years:
        query = query.filter(EeImportExportOesValue.year_number.in_([int(year) for year in years]))
    return {
        (
            record.id_union_energy_system,
            record.id_foreign_border_country,
            int(record.year_number),
        ): Decimal(str(record.transfer_value)) if record.transfer_value is not None else None
        for record in query.all()
    }


def update_ee_import_export_value(
    *,
    ues_id: int,
    country_id: int,
    year: int,
    direction: str = "import",
    raw_value: Any,
    user: Any = None,
) -> dict[str, Any]:
    try:
        year_number = int(year)
        ues_id = int(ues_id)
        country_id = int(country_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Неверные данные ячейки") from exc

    if year_number < 1:
        raise ValueError("Неверный год")

    try:
        value = parse_decimal_from_display(raw_value)
    except InvalidOperation as exc:
        raise ValueError("Введите корректное число") from exc
    if value is not None and not value.is_finite():
        raise ValueError("Введите конечное числовое значение")
    if direction not in {"import", "export"}:
        raise ValueError("Неверное направление потока")
    if value is not None:
        value = abs(value) if direction == "import" else -abs(value)

    oes = (
        filter_by_db_version(UnionEnergySystem.query, UnionEnergySystem)
        .filter_by(id=ues_id)
        .first()
    )
    if oes is None:
        raise ValueError("ОЭС не найдена в текущей версии БД")
    country = (
        filter_by_db_version(ForeignBorderCountry.query, ForeignBorderCountry)
        .filter_by(id=country_id)
        .first()
    )
    if country is None:
        raise ValueError("Страна не найдена в текущей версии БД")

    version_id = get_current_db_version_id()
    existing = (
        filter_by_explicit_db_version(
            EeImportExportOesValue.query, EeImportExportOesValue, version_id
        )
        .filter_by(
            id_union_energy_system=ues_id,
            id_foreign_border_country=country_id,
            year_number=year_number,
        )
        .first()
    )
    previous_value = None if existing is None else existing.transfer_value

    if value is None:
        if existing is None:
            db.session.add(
                EeImportExportOesValue(
                    id_union_energy_system=ues_id,
                    id_foreign_border_country=country_id,
                    year_number=year_number,
                    transfer_value=None,
                    database_version_id=version_id,
                )
            )
        else:
            existing.transfer_value = None
    elif existing is None:
        db.session.add(
            EeImportExportOesValue(
                id_union_energy_system=ues_id,
                id_foreign_border_country=country_id,
                year_number=year_number,
                transfer_value=value,
                database_version_id=version_id,
            )
        )
    else:
        existing.transfer_value = value

    _commit_with_retry()
    clear_energy_balance_cache()
    log_cell_change(
        user,
        "Изменения в балансе ЭЭ, импорт/экспорт электроэнергии по ОЭС",
        f"{year_number} г., {'импорт' if direction == 'import' else 'экспорт'}",
        previous_value,
        value,
        context=f"Лист: импорт/экспорт ЭЭ по ОЭС; ОЭС: {oes.name}; страна: {country.name}",
    )
    return {"year": year_number, "value": value}
