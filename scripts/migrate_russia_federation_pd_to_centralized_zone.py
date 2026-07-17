#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Перенос параметров нагрузки из RussiaFederationDemandParameter
в CentralizedZoneDemandParameter.

Источник: gs_pd.gs_pd_russia_federation_demand_params
Цель:     gs_pd.gs_pd_centralized_zone_demand_params

Перед записью таблица CentralizedZoneDemandParameter полностью очищается,
затем в неё копируются срезы из RussiaFederationDemandParameter
(год / исторический максимум, database_version_id, perimeter_variant_code).
Дубликаты по уникальному ключу цели схлопываются (оставляется более
заполненная / свежая строка). После записи RussiaFederationDemandParameter
очищается.

Запуск из корня репозитория:

  python scripts/migrate_russia_federation_pd_to_centralized_zone.py
  python scripts/migrate_russia_federation_pd_to_centralized_zone.py --apply --yes
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.common.perimeter_variant.constants import CODE_WITHOUT_NT
from app.common.services.tranzaction_services import _commit_with_retry
from app.extensions import db
from app.power_demand.models.energy_systems.centralized_zone_demand_parameter_model import (
    CentralizedZoneDemandParameter,
)
from app.power_demand.models.territories.russia_federation_demand_parameter_model import (
    RussiaFederationDemandParameter,
)

SCRIPT_USER = "script:migrate_russia_federation_pd_to_centralized_zone"

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


def _row_dict(row: Any) -> dict[str, Any]:
    return {field: getattr(row, field) for field in _COPY_FIELDS}


def _slice_key(data: dict[str, Any]) -> tuple[bool, int | None, int | None, str]:
    return (
        bool(data.get("is_historical_maximum")),
        data.get("year_number"),
        data.get("database_version_id"),
        _normalize_pvc(data.get("perimeter_variant_code")) or "",
    )


def _row_richness(data: dict[str, Any]) -> tuple[int, datetime]:
    filled = sum(
        1
        for key in (
            "max_power_consumption_mw",
            "peak_datetime_msk",
            "avg_daily_air_temp_c",
            "note",
        )
        if data.get(key) is not None
    )
    updated = data.get("updated_at") or data.get("created_at") or datetime.min
    if getattr(updated, "tzinfo", None) is not None:
        updated = updated.replace(tzinfo=None)
    return filled, updated


def _plan_copy() -> tuple[list[dict[str, Any]], int, int, list[str]]:
    target_count = CentralizedZoneDemandParameter.query.count()
    rows = RussiaFederationDemandParameter.query.order_by(
        RussiaFederationDemandParameter.id.asc()
    ).all()
    by_slice: dict[tuple[bool, int | None, int | None, str], dict[str, Any]] = {}
    warnings: list[str] = []
    for row in rows:
        data = _row_dict(row)
        data["perimeter_variant_code"] = _normalize_pvc(data.get("perimeter_variant_code"))
        sk = _slice_key(data)
        existing = by_slice.get(sk)
        if existing is None:
            by_slice[sk] = {"source_id": int(row.id), "data": data}
            continue
        if _row_richness(data) >= _row_richness(existing["data"]):
            warnings.append(
                f"Дубликат slice={sk}: оставляем id={row.id}, "
                f"отбрасываем id={existing['source_id']}"
            )
            by_slice[sk] = {"source_id": int(row.id), "data": data}
        else:
            warnings.append(
                f"Дубликат slice={sk}: оставляем id={existing['source_id']}, "
                f"отбрасываем id={row.id}"
            )
    return list(by_slice.values()), int(target_count), len(rows), warnings


def _print_plan(
    moves: list[dict[str, Any]],
    target_count: int,
    source_count: int,
    warnings: list[str],
) -> None:
    print(
        f"Очистка CentralizedZoneDemandParameter: {target_count} строк будет удалено"
    )
    print(
        f"RussiaFederationDemandParameter -> CentralizedZoneDemandParameter: "
        f"{len(moves)} уникальных срезов из {source_count} исходных строк"
    )
    print(
        f"Очистка RussiaFederationDemandParameter: {source_count} строк будет удалено"
    )
    by_pvc: Counter[str] = Counter()
    by_vid: Counter[str] = Counter()
    for item in moves:
        data = item["data"]
        by_pvc[str(data.get("perimeter_variant_code") or "")] += 1
        by_vid[str(data.get("database_version_id"))] += 1
    for code, cnt in sorted(by_pvc.items()):
        print(f"  perimeter_variant_code={code!r}: {cnt}")
    for vid, cnt in sorted(by_vid.items()):
        print(f"  database_version_id={vid}: {cnt}")
    if warnings:
        print(f"\nПредупреждения ({len(warnings)}):")
        for w in warnings[:40]:
            print(f"  - {w}")
        if len(warnings) > 40:
            print(f"  ... и ещё {len(warnings) - 40}")


def _apply(moves: list[dict[str, Any]]) -> None:
    deleted_target = CentralizedZoneDemandParameter.query.delete(synchronize_session=False)
    db.session.flush()

    for item in moves:
        target = CentralizedZoneDemandParameter(**item["data"])
        target.modified_by = SCRIPT_USER
        if not target.created_by:
            target.created_by = SCRIPT_USER
        db.session.add(target)

    db.session.flush()
    deleted_source = RussiaFederationDemandParameter.query.delete(synchronize_session=False)

    _commit_with_retry()
    print(
        f"\nГотово: очищено CentralizedZoneDemandParameter={deleted_target}; "
        f"записано={len(moves)}; "
        f"очищено RussiaFederationDemandParameter={deleted_source}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Очистка CentralizedZoneDemandParameter, перезапись данными из "
            "RussiaFederationDemandParameter и очистка исходной таблицы."
        )
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
        moves, target_count, source_count, warnings = _plan_copy()
        _print_plan(moves, target_count, source_count, warnings)

        if not moves and target_count == 0 and source_count == 0:
            print("\nНечего переносить: обе таблицы уже пусты.")
            return 0
        if not args.apply:
            print("\nDry-run. Для переноса: --apply --yes")
            return 0
        if not args.yes:
            print("\nУкажите --yes вместе с --apply для подтверждения.")
            return 1
        _apply(moves)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
