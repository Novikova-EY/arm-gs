#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Удаление строк, ошибочно записанных в gs_ec_ees_russia_consumption_params при импорте
«ЕЭС России» (EnergySystemType). Агрегат «ЭЭС России» (EesRussia*) допускает только
with_nt / without_nt; варианты с ГАЭС относятся к типу энергосистемы «ЕЭС России».

Запуск из корня репозитория:

  python scripts/cleanup_misplaced_ees_unified_rows_in_ees_russia_ec.py
  python scripts/cleanup_misplaced_ees_unified_rows_in_ees_russia_ec.py --apply --yes

На сервере — то же, в venv приложения, с теми же флагами после бэкапа БД.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.common.perimeter_variant.constants import (
    CODE_WITHOUT_NT_WITH_GAES,
    CODE_WITHOUT_NT_WITHOUT_GAES,
    CODE_WITH_NT_WITH_GAES,
    CODE_WITH_NT_WITHOUT_GAES,
)
from app.common.services.tranzaction_services import _commit_with_retry
from app.extensions import db
from app.energy_consumption.models.energy_systems.ees_russia_energy_consumption_parameter_model import (
    EesRussiaEnergyConsumptionParameter,
)

SCRIPT_USER = "script:cleanup_misplaced_ees_unified_rows_in_ees_russia_ec"

# Явно: эти коды из шаблона «ЕЭС России» попадали в EesRussia до исправления импорта.
_MISPLACED_GAES_VARIANT_CODES: frozenset[str] = frozenset(
    {
        CODE_WITH_NT_WITH_GAES,
        CODE_WITH_NT_WITHOUT_GAES,
        CODE_WITHOUT_NT_WITH_GAES,
        CODE_WITHOUT_NT_WITHOUT_GAES,
    }
)


def _rows_to_delete() -> list[EesRussiaEnergyConsumptionParameter]:
    rows = (
        EesRussiaEnergyConsumptionParameter.query.filter(
            EesRussiaEnergyConsumptionParameter.perimeter_variant_code.in_(
                _MISPLACED_GAES_VARIANT_CODES
            )
        )
        .order_by(EesRussiaEnergyConsumptionParameter.id.asc())
        .all()
    )
    return rows


def _print_summary(rows: list[EesRussiaEnergyConsumptionParameter]) -> None:
    if not rows:
        print("Нет строк для удаления в gs_ec_ees_russia_consumption_params.")
        return
    by_code: Counter[str] = Counter()
    by_version: Counter[int | None] = Counter()
    for row in rows:
        by_code[str(row.perimeter_variant_code)] += 1
        by_version[row.database_version_id] += 1
    print(f"К удалению: {len(rows)} строк")
    print("  по perimeter_variant_code:")
    for code, cnt in sorted(by_code.items()):
        print(f"    {code}: {cnt}")
    print("  по database_version_id:")
    for vid, cnt in sorted(by_version.items(), key=lambda x: (x[0] is None, x[0] or 0)):
        print(f"    {vid}: {cnt}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Удалить из gs_ec_ees_russia_consumption_params строки с вариантами "
            "«ЕЭС России» (GAES), ошибочно импортированные до исправления маршрутизации."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Выполнить удаление (без флага — только отчёт).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Подтвердить удаление вместе с --apply.",
    )
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
        print(f"\nУдалено строк: {len(rows)} (modified_by не применяется при DELETE).")
        print("Повторите импорт Excel — «ЕЭС России» запишется в gs_ec_energy_system_type_consumption_params.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
