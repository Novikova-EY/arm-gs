#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Перенос параметров нагрузки между таблицами gs_pd (исправление путаницы ЕЭС / ЭЭС).

До исправления:
  - gs_pd_ees_russia_demand_params хранила «ЕЭС России» (должна — «ЭЭС России»);
  - gs_pd_ees_demand_params хранила «ЭЭС России»;
  - gs_pd_energy_system_type_demand_params для «ЕЭС России» пуста.

После скрипта:
  1) «ЕЭС России» (EnergySystemType) → gs_pd_energy_system_type_demand_params;
  2) «ЭЭС России» → gs_pd_ees_russia_demand_params.

Запуск из корня репозитория:

  python scripts/migrate_misplaced_ees_unified_pd_demand_params.py
  python scripts/migrate_misplaced_ees_unified_pd_demand_params.py --apply --yes

На сервере — то же в venv приложения, после `flask db upgrade` (колонка perimeter_variant_code
в gs_pd_energy_system_type_demand_params) и бэкапа БД.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from app import create_app
from app.common.perimeter_variant.constants import CODE_WITHOUT_NT, EES_UNIFIED_REF_NAME
from app.common.services.tranzaction_services import _commit_with_retry
from app.extensions import db
from app.power_demand.models.energy_systems.ees_demand_parameter_model import (
    EesDemandParameter,
)
from app.power_demand.models.energy_systems.ees_russia_demand_parameter_model import (
    EesRussiaDemandParameter,
)
from app.power_demand.models.energy_systems.energy_system_type_demand_parameter_model import (
    EnergySystemTypeDemandParameter,
)
from app.power_demand.services import demand_parameter_services as dps
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType

SCRIPT_USER = "script:migrate_misplaced_ees_unified_pd_demand_params"

_COPY_FIELDS = (
    "is_historical_maximum",
    "year_number",
    "max_power_consumption_mw",
    "peak_datetime_msk",
    "avg_daily_air_temp_c",
    "note",
    "database_version_id",
    "perimeter_variant_code",
    "created_by",
    "modified_by",
    "created_at",
    "updated_at",
)


def _normalize_pvc(raw: str | None) -> str | None:
    if raw in (None, ""):
        return CODE_WITHOUT_NT
    return str(raw).strip()


def _est_id_by_version(version_id: int | None) -> int | None:
    q = EnergySystemType.query.filter(EnergySystemType.name == EES_UNIFIED_REF_NAME)
    if version_id is not None:
        q = q.filter(EnergySystemType.database_version_id == version_id)
    else:
        q = dps.filter_parents_by_version(q, EnergySystemType)
    row = q.order_by(EnergySystemType.id.asc()).first()
    return int(row.id) if row is not None else None


def _row_dict(row: Any) -> dict[str, Any]:
    return {field: getattr(row, field) for field in _COPY_FIELDS}


def _slice_key(row: Any) -> tuple[bool, int | None, int | None, str]:
    return (
        bool(getattr(row, "is_historical_maximum", False)),
        getattr(row, "year_number", None),
        getattr(row, "database_version_id", None),
        _normalize_pvc(getattr(row, "perimeter_variant_code", None)) or "",
    )


def _target_est_exists(
    est_id: int,
    slice_key: tuple[bool, int | None, int | None, str],
) -> bool:
    is_hist, year_n, vid, pvc = slice_key
    q = EnergySystemTypeDemandParameter.query.filter(
        EnergySystemTypeDemandParameter.id_energy_system_type == est_id,
        EnergySystemTypeDemandParameter.database_version_id == vid,
        EnergySystemTypeDemandParameter.perimeter_variant_code == pvc,
    )
    if is_hist:
        q = q.filter(EnergySystemTypeDemandParameter.is_historical_maximum.is_(True))
    else:
        q = q.filter(
            EnergySystemTypeDemandParameter.is_historical_maximum.is_(False),
            EnergySystemTypeDemandParameter.year_number == year_n,
        )
    return q.first() is not None


def _target_ees_russia_exists(slice_key: tuple[bool, int | None, int | None, str]) -> bool:
    is_hist, year_n, vid, pvc = slice_key
    q = EesRussiaDemandParameter.query.filter(
        EesRussiaDemandParameter.database_version_id == vid,
        EesRussiaDemandParameter.perimeter_variant_code == pvc,
    )
    if is_hist:
        q = q.filter(EesRussiaDemandParameter.is_historical_maximum.is_(True))
    else:
        q = q.filter(
            EesRussiaDemandParameter.is_historical_maximum.is_(False),
            EesRussiaDemandParameter.year_number == year_n,
        )
    return q.first() is not None


def _plan_move_ees_unified_to_energy_system_type() -> tuple[list[dict[str, Any]], list[str]]:
    rows = EesRussiaDemandParameter.query.order_by(EesRussiaDemandParameter.id.asc()).all()
    to_insert: list[dict[str, Any]] = []
    warnings: list[str] = []
    for row in rows:
        vid = getattr(row, "database_version_id", None)
        est_id = _est_id_by_version(vid)
        if est_id is None:
            warnings.append(
                f"Пропуск id={row.id}: не найден EnergySystemType «{EES_UNIFIED_REF_NAME}» "
                f"для database_version_id={vid!r}"
            )
            continue
        data = _row_dict(row)
        data["perimeter_variant_code"] = _normalize_pvc(data.get("perimeter_variant_code"))
        sk = _slice_key(row)
        if _target_est_exists(est_id, sk):
            warnings.append(
                f"Пропуск id={row.id}: целевая строка уже есть в energy_system_type "
                f"(est_id={est_id}, slice={sk})"
            )
            continue
        to_insert.append(
            {
                "source_id": int(row.id),
                "est_id": est_id,
                "data": data,
            }
        )
    return to_insert, warnings


def _plan_move_ees_to_ees_russia() -> tuple[list[dict[str, Any]], list[str]]:
    rows = EesDemandParameter.query.order_by(EesDemandParameter.id.asc()).all()
    to_insert: list[dict[str, Any]] = []
    warnings: list[str] = []
    for row in rows:
        data = _row_dict(row)
        data["perimeter_variant_code"] = _normalize_pvc(data.get("perimeter_variant_code"))
        sk = _slice_key(row)
        if _target_ees_russia_exists(sk):
            warnings.append(
                f"Пропуск id={row.id}: целевая строка уже есть в ees_russia (slice={sk})"
            )
            continue
        to_insert.append({"source_id": int(row.id), "data": data})
    return to_insert, warnings


def _print_plan(
    est_moves: list[dict[str, Any]],
    ees_moves: list[dict[str, Any]],
    warnings: list[str],
) -> None:
    print(f"Шаг 1. ЕЭС России: ees_russia -> energy_system_type: {len(est_moves)} строк")
    by_pvc: Counter[str] = Counter()
    for item in est_moves:
        by_pvc[str(item["data"].get("perimeter_variant_code") or "")] += 1
    for code, cnt in sorted(by_pvc.items()):
        print(f"  perimeter_variant_code={code!r}: {cnt}")

    print(f"Шаг 2. ЭЭС России: ees -> ees_russia: {len(ees_moves)} строк")
    by_pvc_ees: Counter[str] = Counter()
    for item in ees_moves:
        by_pvc_ees[str(item["data"].get("perimeter_variant_code") or "")] += 1
    for code, cnt in sorted(by_pvc_ees.items()):
        print(f"  perimeter_variant_code={code!r}: {cnt}")

    if warnings:
        print(f"\nПредупреждения ({len(warnings)}):")
        for w in warnings[:30]:
            print(f"  - {w}")
        if len(warnings) > 30:
            print(f"  ... и ещё {len(warnings) - 30}")


def _drop_legacy_ees_russia_unique_indexes() -> None:
    """Старые uq_ees_russia_dp_* без perimeter_variant_code блокируют несколько hist-строк на версию."""
    for ix in ("uq_ees_russia_dp_hist", "uq_ees_russia_dp_year"):
        db.session.execute(text(f'DROP INDEX IF EXISTS "gs_pd"."{ix}"'))


def _apply(est_moves: list[dict[str, Any]], ees_moves: list[dict[str, Any]]) -> None:
    _drop_legacy_ees_russia_unique_indexes()
    deleted_ees_russia_ids: list[int] = []
    for item in est_moves:
        target = EnergySystemTypeDemandParameter(
            id_energy_system_type=int(item["est_id"]),
            **item["data"],
        )
        target.modified_by = SCRIPT_USER
        if not target.created_by:
            target.created_by = SCRIPT_USER
        db.session.add(target)
        deleted_ees_russia_ids.append(int(item["source_id"]))

    for sid in deleted_ees_russia_ids:
        row = EesRussiaDemandParameter.query.get(sid)
        if row is not None:
            db.session.delete(row)

    deleted_ees_ids: list[int] = []
    for item in ees_moves:
        target = EesRussiaDemandParameter(**item["data"])
        target.modified_by = SCRIPT_USER
        if not target.created_by:
            target.created_by = SCRIPT_USER
        db.session.add(target)
        deleted_ees_ids.append(int(item["source_id"]))

    for sid in deleted_ees_ids:
        row = EesDemandParameter.query.get(sid)
        if row is not None:
            db.session.delete(row)

    _commit_with_retry()
    print(
        f"\nГотово: перенесено в energy_system_type={len(est_moves)}, "
        f"в ees_russia={len(ees_moves)}; удалено из ees_russia={len(deleted_ees_russia_ids)}, "
        f"из ees={len(deleted_ees_ids)}."
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Перенос параметров нагрузки ЕЭС/ЭЭС между таблицами gs_pd."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Выполнить перенос (без флага — только план).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Подтвердить перенос вместе с --apply.",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        col_exists = db.session.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_schema = 'gs_pd' "
                "AND table_name = 'gs_pd_energy_system_type_demand_params' "
                "AND column_name = 'perimeter_variant_code'"
            )
        ).fetchone()
        if not col_exists:
            print(
                "Ошибка: нет колонки perimeter_variant_code в "
                "gs_pd_energy_system_type_demand_params. Сначала выполните: flask db upgrade"
            )
            return 1

        est_moves, w1 = _plan_move_ees_unified_to_energy_system_type()
        ees_moves, w2 = _plan_move_ees_to_ees_russia()
        _print_plan(est_moves, ees_moves, w1 + w2)

        if not est_moves and not ees_moves:
            print("\nНечего переносить.")
            return 0
        if not args.apply:
            print("\nDry-run. Для переноса: --apply --yes")
            return 0
        if not args.yes:
            print("\nУкажите --yes вместе с --apply для подтверждения.")
            return 1
        _apply(est_moves, ees_moves)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
