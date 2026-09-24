# -*- coding: utf-8 -*-
"""Контрольная выработка ЭЭ по Россия / типу ЭС / СЗ / ОЭС."""
from __future__ import annotations

from collections import defaultdict
from decimal import InvalidOperation
from typing import Any

from sqlalchemy.exc import OperationalError, ProgrammingError

from app.common.services.database_version_filter import (
    filter_by_db_version,
    set_db_version_on_create,
)
from app.common.services.help_services import parse_decimal_from_display
from app.common.services.tranzaction_services import _commit_with_retry
from app.energy_balance.models.energy_system_energy_generation_control_model import (
    HIERARCHY_CONTROL_LEVELS,
    HIERARCHY_CONTROL_PERIOD_YEAR,
    EnergySystemEnergyGenerationControl,
)
from app.energy_balance.services.energy_balance_cache import clear_energy_balance_cache
from app.energy_balance.services.station_ee_generation_page_services import (
    resolve_control_period,
)
from app.extensions import db

_tables_ready = False


def _ensure_tables() -> None:
    global _tables_ready
    if _tables_ready:
        return
    try:
        bind = db.session.get_bind()
        EnergySystemEnergyGenerationControl.__table__.create(bind, checkfirst=True)
        _tables_ready = True
    except Exception:
        pass


def _normalize_entity_id(level: str, entity_id) -> int | None:
    if level == "russia":
        return None
    try:
        value = int(entity_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("Неверный идентификатор строки") from exc
    if value in (0, -1):
        raise ValueError("Неверный идентификатор строки")
    return value


def load_hierarchy_control_generation(
    start_year: int,
    end_year: int,
) -> dict[str, Any]:
    """Значения параметра: russia / est / sa / ues."""
    result: dict[str, Any] = {
        "russia": {},
        "est": defaultdict(dict),
        "sa": defaultdict(dict),
        "ues": defaultdict(dict),
    }
    _ensure_tables()
    try:
        q = EnergySystemEnergyGenerationControl.query.filter(
            EnergySystemEnergyGenerationControl.year_number >= start_year,
            EnergySystemEnergyGenerationControl.year_number <= end_year,
            EnergySystemEnergyGenerationControl.month_number == HIERARCHY_CONTROL_PERIOD_YEAR,
        )
        q = filter_by_db_version(q, EnergySystemEnergyGenerationControl)
        rows = q.all()
    except (ProgrammingError, OperationalError):
        db.session.rollback()
        return {
            "russia": {},
            "est": {},
            "sa": {},
            "ues": {},
        }
    except Exception:
        return {
            "russia": {},
            "est": {},
            "sa": {},
            "ues": {},
        }

    for row in rows:
        level = (row.level or "").strip().lower()
        if level not in HIERARCHY_CONTROL_LEVELS or row.year_number is None:
            continue
        year = int(row.year_number)
        value = row.electricity_generation
        if level == "russia":
            result["russia"][year] = value
            continue
        if row.entity_id in (None, 0, -1):
            continue
        result[level][int(row.entity_id)][year] = value
    return {
        "russia": result["russia"],
        "est": dict(result["est"]),
        "sa": dict(result["sa"]),
        "ues": dict(result["ues"]),
    }


def overlay_hierarchy_control(
    aggregates: dict[str, Any],
    stored: dict[str, Any],
) -> dict[str, Any]:
    """Подставляет сохранённый параметр поверх сумм по РЭС."""
    if not stored:
        return aggregates
    russia = stored.get("russia") or {}
    if russia:
        merged = dict(aggregates.get("total") or {})
        merged.update(russia)
        aggregates["total"] = merged
    for bucket, key in (
        ("est", "energy_system_types"),
        ("sa", "synchronous_areas"),
        ("ues", "union_energy_systems"),
    ):
        overlay = stored.get(bucket) or {}
        if not overlay:
            continue
        current = dict(aggregates.get(key) or {})
        for entity_id, periods in overlay.items():
            merged = dict(current.get(entity_id) or {})
            merged.update(periods or {})
            current[entity_id] = merged
        aggregates[key] = current
    return aggregates


def update_hierarchy_control_generation_value(
    level: str,
    entity_id,
    period_key: int,
    raw_value,
    *,
    period_mode: str = "years",
    selected_year: int | None = None,
) -> dict[str, Any]:
    """Upsert контрольной выработки по уровню иерархии; пустое значение удаляет запись."""
    level_key = (level or "").strip().lower()
    if level_key not in HIERARCHY_CONTROL_LEVELS:
        raise ValueError("Неверный уровень агрегации")
    entity = _normalize_entity_id(level_key, entity_id)
    year_number, month_number = resolve_control_period(
        period_key,
        period_mode=period_mode,
        selected_year=selected_year,
    )
    try:
        parsed = parse_decimal_from_display(raw_value)
    except InvalidOperation as exc:
        raise ValueError("Неверное число") from exc

    _ensure_tables()
    q = EnergySystemEnergyGenerationControl.query.filter(
        EnergySystemEnergyGenerationControl.level == level_key,
        EnergySystemEnergyGenerationControl.year_number == year_number,
        EnergySystemEnergyGenerationControl.month_number == month_number,
    )
    if entity is None:
        q = q.filter(EnergySystemEnergyGenerationControl.entity_id.is_(None))
    else:
        q = q.filter(EnergySystemEnergyGenerationControl.entity_id == entity)
    q = filter_by_db_version(q, EnergySystemEnergyGenerationControl)
    existing = q.one_or_none()

    if parsed is None:
        if existing is not None:
            db.session.delete(existing)
            _commit_with_retry()
            clear_energy_balance_cache()
        return {
            "level": level_key,
            "entity_id": entity,
            "period_key": int(period_key),
            "value": None,
        }

    if existing is None:
        existing = EnergySystemEnergyGenerationControl(
            level=level_key,
            entity_id=entity,
            year_number=year_number,
            month_number=month_number,
            electricity_generation=parsed,
        )
        set_db_version_on_create(existing)
        db.session.add(existing)
    else:
        existing.electricity_generation = parsed
        db.session.add(existing)

    _commit_with_retry()
    clear_energy_balance_cache()
    return {
        "level": level_key,
        "entity_id": entity,
        "period_key": int(period_key),
        "value": parsed,
    }
