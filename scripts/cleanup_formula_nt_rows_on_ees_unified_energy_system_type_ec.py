#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Удаление строк with_nt / without_nt для типа энергосистемы «ЕЭС России» в
gs_ec_energy_system_type_consumption_params — они появлялись после импорта Excel
из постобработки формул (ошибочная подстановка привязок агрегата «ЭЭС России»).

Запуск:
  python scripts/cleanup_formula_nt_rows_on_ees_unified_energy_system_type_ec.py
  python scripts/cleanup_formula_nt_rows_on_ees_unified_energy_system_type_ec.py --apply --yes
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.common.perimeter_variant.constants import (
    CODE_WITHOUT_NT,
    CODE_WITH_NT,
    EES_UNIFIED_REF_NAME,
)
from app.common.perimeter_variant.registry import perimeter_variant_codes_for_entity
from app.common.services.database_version_filter import filter_by_explicit_db_version
from app.common.services.tranzaction_services import _commit_with_retry
from app.common.perimeter_variant.constants import ENTITY_KIND_ENERGY_SYSTEM_TYPE
from app.extensions import db
from app.energy_consumption.models.energy_systems.energy_system_type_energy_consumption_parameter_model import (
    EnergySystemTypeEnergyConsumptionParameter,
)
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType

_MISPLACED_NT_CODES = frozenset({CODE_WITH_NT, CODE_WITHOUT_NT})


def _ees_unified_type_ids_by_version() -> dict[int | None, int]:
    out: dict[int | None, int] = {}
    for row in EnergySystemType.query.filter(EnergySystemType.name == EES_UNIFIED_REF_NAME).all():
        out[row.database_version_id] = int(row.id)
    return out


def _rows_to_delete() -> list[EnergySystemTypeEnergyConsumptionParameter]:
    allowed = frozenset(
        perimeter_variant_codes_for_entity(
            ENTITY_KIND_ENERGY_SYSTEM_TYPE,
            EES_UNIFIED_REF_NAME,
        )
    )
    if allowed & _MISPLACED_NT_CODES:
        print(
            "Предупреждение: в каталоге для «ЕЭС России» разрешены plain with_nt/without_nt; "
            "скрипт всё равно удалит только строки типа «ЕЭС России», не ТИТЭС."
        )
    type_ids = _ees_unified_type_ids_by_version()
    rows: list[EnergySystemTypeEnergyConsumptionParameter] = []
    for version_id, est_id in type_ids.items():
        q = EnergySystemTypeEnergyConsumptionParameter.query.filter(
            EnergySystemTypeEnergyConsumptionParameter.id_energy_system_type == est_id,
            EnergySystemTypeEnergyConsumptionParameter.perimeter_variant_code.in_(
                _MISPLACED_NT_CODES
            ),
        )
        q = filter_by_explicit_db_version(
            q, EnergySystemTypeEnergyConsumptionParameter, version_id
        )
        rows.extend(q.order_by(EnergySystemTypeEnergyConsumptionParameter.id.asc()).all())
    return rows


def _print_summary(rows: list[EnergySystemTypeEnergyConsumptionParameter]) -> None:
    if not rows:
        print("Нет строк для удаления в gs_ec_energy_system_type_consumption_params (ЕЭС России).")
        return
    by_code: Counter[str] = Counter()
    by_version: Counter[int | None] = Counter()
    for row in rows:
        by_code[str(row.perimeter_variant_code)] += 1
        by_version[row.database_version_id] += 1
    print(f"К удалению: {len(rows)} строк (тип «ЕЭС России»)")
    print("  по perimeter_variant_code:")
    for code, cnt in sorted(by_code.items()):
        print(f"    {code}: {cnt}")
    print("  по database_version_id:")
    for vid, cnt in sorted(by_version.items(), key=lambda x: (x[0] is None, x[0] or 0)):
        print(f"    {vid}: {cnt}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Удалить with_nt/without_nt у типа энергосистемы «ЕЭС России» "
            "(ошибочные строки после формул импорта)."
        )
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        rows = _rows_to_delete()
        _print_summary(rows)
        if not rows:
            return 0
        if not args.apply:
            print("\nDry-run. Для удаления: --apply --yes")
            return 0
        if not args.yes:
            print("\nУкажите --yes вместе с --apply для подтверждения.")
            return 1
        for row in rows:
            db.session.delete(row)
        _commit_with_retry()
        print(f"\nУдалено строк: {len(rows)}.")
        print("Повторите импорт Excel с вариантами with_nt_with_gaes / without_nt_with_gaes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
