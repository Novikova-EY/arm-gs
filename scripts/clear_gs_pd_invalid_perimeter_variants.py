#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Сброс недопустимых perimeter_variant_code в таблицах схемы gs_pd (модуль «Нагрузки»).

Строка попадает под очистку (perimeter_variant_code -> NULL), если выполняется хотя бы одно:
  1) код отсутствует в справочнике вариантов периметра (gs_sys);
  2) для сущности строки задана привязка вариантов, и код в неё не входит
     (например with_nt / without_nt у «ЭЭС России», где допустимы только GAES-варианты).

Дополнительно:
  --force-codes with_nt,without_nt  — сбросить эти коды во всех таблицах gs_pd,
                                      даже если они ещё допустимы для другой сущности
                                      (ОЭС Юга, Россия и т.д.). Используйте осознанно.

Запуск из корня репозитория:

  python scripts/clear_gs_pd_invalid_perimeter_variants.py
  python scripts/clear_gs_pd_invalid_perimeter_variants.py --apply --yes
  python scripts/clear_gs_pd_invalid_perimeter_variants.py --force-codes with_nt,without_nt --apply --yes
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Type

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.common.perimeter_variant.registry import (
    is_o1_perimeter_variant_code,
    perimeter_entity_context_for_model,
    perimeter_variant_codes_for_entity,
    perimeter_variant_definitions,
    resolve_catalog_o1_perimeter_variant_code,
)
from app.common.services.tranzaction_services import _commit_with_retry
from app.extensions import db
from app.power_demand.models.energy_systems.ees_demand_parameter_model import (
    EesDemandParameter,
)
from app.power_demand.models.energy_systems.ees_russia_demand_parameter_model import (
    EesRussiaDemandParameter,
)
from app.power_demand.models.energy_systems.synchronous_area_demand_parameter_model import (
    SynchronousAreaDemandParameter,
)
from app.power_demand.models.energy_systems.union_energy_system_demand_parameter_model import (
    UnionEnergySystemDemandParameter,
)
from app.power_demand.models.territories.regional_district_demand_parameter_model import (
    RegionalDistrictDemandParameter,
)
from app.power_demand.models.territories.russia_federation_demand_parameter_model import (
    RussiaFederationDemandParameter,
)

SCRIPT_USER = "script:clear_gs_pd_invalid_perimeter_variants"

PD_MODEL_PARENT_FK: dict[str, str] = {
    "UnionEnergySystemDemandParameter": "id_union_energy_system",
    "RegionalDistrictDemandParameter": "id_regional_district",
    "SynchronousAreaDemandParameter": "id_synchronous_area",
}

PD_MODELS_WITH_PERIMETER_VARIANT: tuple[Type[Any], ...] = (
    EesDemandParameter,
    EesRussiaDemandParameter,
    RussiaFederationDemandParameter,
    UnionEnergySystemDemandParameter,
    SynchronousAreaDemandParameter,
    RegionalDistrictDemandParameter,
)


@dataclass(frozen=True, slots=True)
class ClearReason:
    code: str
    reason: str
    entity_kind: str | None = None
    entity_name: str | None = None


def _known_catalog_codes() -> frozenset[str]:
    codes = set(perimeter_variant_definitions().keys())
    o1 = resolve_catalog_o1_perimeter_variant_code()
    if o1:
        codes.add(o1)
    return frozenset(codes)


def _code_known_in_catalog(code: str, catalog: frozenset[str]) -> bool:
    if code in catalog:
        return True
    if is_o1_perimeter_variant_code(code):
        return resolve_catalog_o1_perimeter_variant_code() in catalog
    return False


def _row_entity_context(model_name: str, row: Any) -> tuple[str, str] | None:
    fk_col = PD_MODEL_PARENT_FK.get(model_name)
    parent_id = int(getattr(row, fk_col)) if fk_col and getattr(row, fk_col) is not None else None
    return perimeter_entity_context_for_model(
        model_name,
        parent_fk_column=fk_col,
        parent_id=parent_id,
    )


def _should_clear_variant(
    code: str,
    *,
    catalog: frozenset[str],
    entity_ctx: tuple[str, str] | None,
    force_codes: frozenset[str],
) -> ClearReason | None:
    if code in force_codes:
        return ClearReason(code=code, reason="force-codes")

    if not _code_known_in_catalog(code, catalog):
        return ClearReason(code=code, reason="unknown-in-catalog")

    if entity_ctx is None:
        return None

    entity_kind, entity_name = entity_ctx
    allowed = perimeter_variant_codes_for_entity(entity_kind, entity_name)
    if allowed and code not in allowed:
        return ClearReason(
            code=code,
            reason="not-allowed-for-entity",
            entity_kind=entity_kind,
            entity_name=entity_name,
        )
    return None


def _scan_and_maybe_clear(
    *,
    apply_changes: bool,
    force_codes: frozenset[str],
) -> tuple[dict[str, Counter[str]], list[tuple[str, int, str, ClearReason]]]:
    catalog = _known_catalog_codes()
    by_table: dict[str, Counter[str]] = defaultdict(Counter)
    samples: list[tuple[str, int, str, ClearReason]] = []
    cleared_total = 0

    for model in PD_MODELS_WITH_PERIMETER_VARIANT:
        if not hasattr(model, "perimeter_variant_code"):
            continue
        table = model.__tablename__
        model_name = model.__name__
        rows = (
            model.query.filter(model.perimeter_variant_code.isnot(None))
            .order_by(model.id.asc())
            .all()
        )
        for row in rows:
            code = str(getattr(row, "perimeter_variant_code", "") or "").strip()
            if not code:
                continue
            entity_ctx = _row_entity_context(model_name, row)
            reason = _should_clear_variant(
                code,
                catalog=catalog,
                entity_ctx=entity_ctx,
                force_codes=force_codes,
            )
            if reason is None:
                continue
            by_table[table][code] += 1
            if len(samples) < 40:
                samples.append((table, int(row.id), code, reason))
            if apply_changes:
                row.perimeter_variant_code = None
                row.modified_by = SCRIPT_USER
                cleared_total += 1

    if apply_changes and cleared_total:
        _commit_with_retry()

    return dict(by_table), samples


def _print_inventory() -> None:
    print("Текущее распределение perimeter_variant_code (все непустые значения):")
    for model in PD_MODELS_WITH_PERIMETER_VARIANT:
        if not hasattr(model, "perimeter_variant_code"):
            continue
        rows = (
            db.session.query(model.perimeter_variant_code, db.func.count())
            .filter(model.perimeter_variant_code.isnot(None))
            .group_by(model.perimeter_variant_code)
            .order_by(model.perimeter_variant_code.asc())
            .all()
        )
        if not rows:
            continue
        print(f"  {model.__tablename__}:")
        for code, cnt in rows:
            print(f"    {code!r}: {cnt}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Сброс недопустимых perimeter_variant_code в gs_pd (нагрузки)."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Записать изменения (по умолчанию только отчёт).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Не спрашивать подтверждение при --apply.",
    )
    parser.add_argument(
        "--force-codes",
        default="",
        help="Дополнительно сбросить эти коды везде (через запятую), "
        "например: with_nt,without_nt",
    )
    parser.add_argument(
        "--show-inventory",
        action="store_true",
        help="Показать все непустые коды по таблицам перед отчётом об очистке.",
    )
    args = parser.parse_args()

    apply_changes = bool(args.apply)
    force_codes = frozenset(
        c.strip()
        for c in str(args.force_codes or "").split(",")
        if c.strip()
    )

    app = create_app()
    with app.app_context():
        catalog = _known_catalog_codes()
        print("=" * 72)
        print("Очистка perimeter_variant_code в gs_pd")
        print("=" * 72)
        print(f"Старт:     {datetime.now().isoformat(timespec='seconds')}")
        print(f"Режим:     {'APPLY' if apply_changes else 'DRY-RUN'}")
        print(f"Справочник: {len(catalog)} код(ов) вариантов периметра")
        if force_codes:
            print(f"Force:     {', '.join(sorted(force_codes))}")
        print()

        if args.show_inventory:
            _print_inventory()
            print()

        if apply_changes and not args.yes:
            q = input(
                "Сбросить недопустимые perimeter_variant_code в NULL во всех "
                "таблицах gs_pd? [y/N]: "
            )
            if str(q).strip().lower() not in ("y", "yes", "д", "да"):
                print("Отмена.")
                return

        by_table, samples = _scan_and_maybe_clear(
            apply_changes=apply_changes,
            force_codes=force_codes,
        )

        total = sum(sum(counter.values()) for counter in by_table.values())
        if not total:
            print("Нет строк для очистки.")
            return

        print(f"Будет очищено строк: {total}" if not apply_changes else f"Очищено строк: {total}")
        print()
        for table in sorted(by_table):
            print(f"  {table}:")
            for code, cnt in sorted(by_table[table].items()):
                print(f"    {code!r}: {cnt}")
        print()

        if samples:
            print("Примеры (таблица, id, код, причина):")
            for table, row_id, code, reason in samples:
                extra = ""
                if reason.entity_kind and reason.entity_name:
                    extra = f" [{reason.entity_kind}: {reason.entity_name}]"
                print(f"  {table} id={row_id} {code!r} — {reason.reason}{extra}")
            if total > len(samples):
                print(f"  ... и ещё {total - len(samples)} строк(и)")

        if not apply_changes:
            print()
            print("DRY-RUN: для записи добавьте --apply --yes")


if __name__ == "__main__":
    main()
