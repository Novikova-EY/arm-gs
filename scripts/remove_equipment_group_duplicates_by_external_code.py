#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Удаление дублей EquipmentGroup по (external_code, database_version_id).

Оставляет наиболее заполненную запись, сливает в нее пустые поля из дублей,
переназначает связанные записи и удаляет осиротевшие дубликаты.

Запуск:
    python scripts/remove_equipment_group_duplicates_by_external_code.py --dry-run
    python scripts/remove_equipment_group_duplicates_by_external_code.py --yes
"""

import argparse
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import delete, func, inspect, select, update

from app import create_app
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_fuel_formula_model import EquipmentGroupFuelFormula
from app.fuel.models.fue_equipment_group_coefficient_result_model import (
    EquipmentGroupCoefficientResult,
)
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import EquipmentGroupExtraFuelParam
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.fuel.models.fue_equipment_group_specific_fuel_cost_model import (
    EquipmentGroupSpecificFuelCost,
)
from app.fuel.models.fue_equipment_group_specific_fuel_price_model import (
    EquipmentGroupSpecificFuelPrice,
)
from app.fuel.services.equipment_groups.equipment_group_merge_services import (
    _choose_primary_group,
    _merge_group_fields_return_list,
    _reassign_sets_to_primary,
)


def _reassign_table_rows_to_primary(table, group_ids: list[int], primary_id: int, key_fields: tuple[str, ...]) -> tuple[int, int]:
    """
    Переназначает строки detail-таблицы на primary_id через SQL Core.
    Это избегает ORM autoflush и побочных изменений связанных mapping-таблиц.
    """
    reassigned = 0
    deleted = 0
    rows = db.session.execute(
        select(table).where(table.c.equipment_group_id.in_(group_ids))
    ).all()
    for row in rows:
        data = row._mapping
        if data["equipment_group_id"] == primary_id:
            continue

        filters = [table.c.equipment_group_id == primary_id]
        for field in key_fields:
            filters.append(table.c[field] == data[field])

        duplicate = db.session.execute(
            select(table).where(*filters).limit(1)
        ).first()
        if duplicate:
            duplicate_data = duplicate._mapping
            values_to_fill = {}
            for column in table.columns:
                field = column.name
                if field in {"id", "equipment_group_id", "created_at", "updated_at"}:
                    continue
                if duplicate_data[field] is None and data[field] is not None:
                    values_to_fill[field] = data[field]
            if values_to_fill:
                db.session.execute(
                    update(table)
                    .where(table.c.id == duplicate_data["id"])
                    .values(**values_to_fill)
                )
            db.session.execute(
                delete(table).where(table.c.id == data["id"])
            )
            deleted += 1
        else:
            db.session.execute(
                update(table)
                .where(table.c.id == data["id"])
                .values(equipment_group_id=primary_id)
            )
            reassigned += 1
    return reassigned, deleted


def _table_exists(model) -> bool:
    inspector = inspect(db.engine)
    table = model.__table__
    return inspector.has_table(table.name, schema=table.schema)


def _remove_orphan_groups_sql(groups: list[EquipmentGroup], primary_id: int) -> int:
    """
    Удаляет группы прямым SQL DELETE, чтобы SQLAlchemy не пытался лениво грузить
    связанные коллекции через ORM (в т.ч. optional-таблицы, которых может не быть).
    """
    removed = 0
    for group in groups:
        if not group or group.id == primary_id:
            continue
        still_used = EquipmentGroupSet.query.filter_by(
            equipment_group_id=group.id
        ).first()
        if still_used:
            continue
        db.session.execute(
            delete(EquipmentGroup.__table__).where(EquipmentGroup.__table__.c.id == group.id)
        )
        removed += 1
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Удаление дублей EquipmentGroup по (external_code, database_version_id)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать, что будет сделано, без изменений",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Без подтверждения",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        has_formula_table = _table_exists(EquipmentGroupFuelFormula)
        has_coeff_table = _table_exists(EquipmentGroupCoefficientResult)

        dup_stmt = (
            select(
                EquipmentGroup.external_code,
                EquipmentGroup.database_version_id,
                func.array_agg(EquipmentGroup.id).label("ids"),
            )
            .where(EquipmentGroup.external_code.isnot(None))
            .group_by(EquipmentGroup.external_code, EquipmentGroup.database_version_id)
            .having(func.count() > 1)
        )
        duplicates = db.session.execute(dup_stmt).all()

        if not duplicates:
            print("Дублей EquipmentGroup по (external_code, database_version_id) не найдено.")
            return

        print("=" * 80)
        print("Удаление дублей EquipmentGroup по (external_code, database_version_id)")
        print("=" * 80)
        print(f"Старт: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Найдено групп дублей: {len(duplicates)}")
        if args.dry_run:
            print("[DRY-RUN] Изменения не применяются")
        print()

        if not args.dry_run and not args.yes:
            confirm = input("Продолжить объединение дублей? [y/N]: ").strip().lower()
            if confirm not in ("y", "yes"):
                print("Отменено.")
                return

        total_removed_groups = 0
        total_reassigned_sets = 0
        total_formula_reassigned = 0
        total_formula_deleted = 0
        total_coeff_reassigned = 0
        total_coeff_deleted = 0
        total_detail_reassigned = 0
        total_detail_deleted = 0
        total_groups_merged = 0

        for external_code, db_version_id, ids in duplicates:
            group_ids = sorted(set(ids))
            groups = EquipmentGroup.query.filter(EquipmentGroup.id.in_(group_ids)).order_by(EquipmentGroup.id.asc()).all()
            primary = _choose_primary_group(groups) or (groups[0] if groups else None)
            if not primary:
                continue

            drop_ids = [group.id for group in groups if group.id != primary.id]
            print(
                f"external_code={external_code} db_version={db_version_id}: "
                f"оставляем id={primary.id}, удаляем {drop_ids}"
            )
            total_groups_merged += len(drop_ids)

            if args.dry_run:
                continue

            for group in groups:
                if group.id == primary.id:
                    continue
                _merge_group_fields_return_list(primary, group)

            total_reassigned_sets += EquipmentGroupSet.query.filter(
                EquipmentGroupSet.equipment_group_id.in_(drop_ids)
            ).count()
            _reassign_sets_to_primary(drop_ids, primary.id)

            detail_tables = [
                (EquipmentGroupFuelParam.__table__, ("year_number",)),
                (EquipmentGroupExtraFuelParam.__table__, ("year_number",)),
                (EquipmentGroupSpecificFuelConsumption.__table__, ("year_number",)),
                (EquipmentGroupSpecificFuelCost.__table__, ("year_number",)),
                (EquipmentGroupSpecificFuelPrice.__table__, ("year_number",)),
            ]
            for table, key_fields in detail_tables:
                reassigned, deleted_count = _reassign_table_rows_to_primary(
                    table,
                    group_ids,
                    primary.id,
                    key_fields,
                )
                total_detail_reassigned += reassigned
                total_detail_deleted += deleted_count

            if has_formula_table:
                formula_reassigned, formula_deleted = _reassign_table_rows_to_primary(
                    EquipmentGroupFuelFormula.__table__,
                    group_ids,
                    primary.id,
                    ("year_number", "variant_number", "database_version_id"),
                )
                total_formula_reassigned += formula_reassigned
                total_formula_deleted += formula_deleted

            if has_coeff_table:
                coeff_reassigned, coeff_deleted = _reassign_table_rows_to_primary(
                    EquipmentGroupCoefficientResult.__table__,
                    group_ids,
                    primary.id,
                    ("distribution_parameter_id", "year_number", "database_version_id"),
                )
                total_coeff_reassigned += coeff_reassigned
                total_coeff_deleted += coeff_deleted

            removed = _remove_orphan_groups_sql(groups, primary.id)
            total_removed_groups += removed

        if args.dry_run:
            print()
            print(f"[DRY-RUN] Будет объединено групп: {total_groups_merged}")
            return

        db.session.commit()
        print()
        print(f"Объединено дублирующих групп: {total_groups_merged}")
        print(f"Удалено осиротевших групп: {total_removed_groups}")
        print(f"Переназначено EquipmentGroupSet: {total_reassigned_sets}")
        print(f"Detail rows: переназначено {total_detail_reassigned}, удалено конфликтов {total_detail_deleted}")
        if has_formula_table:
            print(f"FuelFormula: переназначено {total_formula_reassigned}, удалено конфликтов {total_formula_deleted}")
        else:
            print("FuelFormula: таблица отсутствует, шаг пропущен")
        if has_coeff_table:
            print(f"CoefficientResult: переназначено {total_coeff_reassigned}, удалено конфликтов {total_coeff_deleted}")
        else:
            print("CoefficientResult: таблица отсутствует, шаг пропущен")
        print(f"Готово: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == "__main__":
    main()
