# -*- coding: utf-8 -*-
"""
Cleanup script: remove rows where database_version_id IS NULL.

Notes:
- Uses staged deletion order to avoid FK violations.
- Skips tables without a database_version_id column.
- Supports --dry-run and --yes flags.
"""

import argparse
import os
import sys
from datetime import datetime

from sqlalchemy import text

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from config import SCHEMA_REFDATA, SCHEMA_GENERATION, SCHEMA_FUEL  # noqa: E402


def _table_has_version_column(schema, table):
    query = text(
        """
        SELECT COUNT(*)
        FROM information_schema.columns
        WHERE table_schema = :schema_name
          AND table_name = :table_name
          AND column_name = 'database_version_id'
        """
    )
    return db.session.execute(query, {"schema_name": schema, "table_name": table}).scalar() > 0


def _count_null_rows(schema, table):
    query = text(
        f"""
        SELECT COUNT(*) FROM {schema}.{table}
        WHERE database_version_id IS NULL
        """
    )
    return db.session.execute(query).scalar()


def _delete_null_rows(schema, table):
    query = text(
        f"""
        DELETE FROM {schema}.{table}
        WHERE database_version_id IS NULL
        """
    )
    result = db.session.execute(query)
    return result.rowcount


def main():
    parser = argparse.ArgumentParser(
        description="Delete rows with database_version_id IS NULL across versioned tables."
    )
    parser.add_argument("--dry-run", action="store_true", help="Only report counts, no deletes.")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    args = parser.parse_args()

    app = create_app()

    with app.app_context():
        print("=" * 80)
        print("CLEANUP: database_version_id IS NULL")
        print("=" * 80)
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Staged deletion order (children -> parents)
        stage8_tables = [
            (SCHEMA_GENERATION, "pgu_machine_powers"),
        ]
        stage7_tables = [
            (SCHEMA_GENERATION, "machine_powers"),
            (SCHEMA_GENERATION, "machine_fuels"),
            (SCHEMA_GENERATION, "machine_tes_types"),
            (SCHEMA_GENERATION, "pgu_machines"),
        ]
        stage6_tables = [
            (SCHEMA_GENERATION, "machines"),
            (SCHEMA_FUEL, "gs_fue_equipment_group_set_stations"),
            (SCHEMA_FUEL, "gs_fue_equipment_group_sets"),
            (SCHEMA_GENERATION, "station_powers"),
            (SCHEMA_GENERATION, "boilers"),
        ]
        stage5_tables = [
            (SCHEMA_GENERATION, "stations"),
        ]
        stage4_tables = [
            (SCHEMA_REFDATA, "gs_regional_district_regional_energy_system"),
            (SCHEMA_REFDATA, "gs_energy_areas"),
            (SCHEMA_REFDATA, "gs_energy_units"),
        ]
        stage3_tables = [
            (SCHEMA_REFDATA, "gs_regional_districts"),
            (SCHEMA_REFDATA, "gs_regional_energy_systems"),
        ]
        stage2_tables = [
            (SCHEMA_REFDATA, "gs_union_energy_systems"),
            (SCHEMA_REFDATA, "gs_synchronous_areas"),
            (SCHEMA_REFDATA, "gs_energy_zones"),
            (SCHEMA_REFDATA, "gs_federal_districts"),
        ]
        stage1_tables = [
            (SCHEMA_REFDATA, "gs_station_types"),
            (SCHEMA_REFDATA, "gs_machine_types"),
            (SCHEMA_REFDATA, "gs_tes_types"),
            (SCHEMA_REFDATA, "gs_tes_machine_types"),
            (SCHEMA_REFDATA, "gs_pgu_tes_machine_types"),
            (SCHEMA_REFDATA, "gs_condition_types"),
            (SCHEMA_REFDATA, "gs_technology_types"),
            (SCHEMA_REFDATA, "gs_technology_availabilities"),
            (SCHEMA_REFDATA, "gs_equipment_groups"),
            (SCHEMA_REFDATA, "gs_energy_system_types"),
            (SCHEMA_REFDATA, "gs_fuel_categories"),
            (SCHEMA_REFDATA, "gs_fuel_types"),
            (SCHEMA_REFDATA, "gs_fuels"),
            (SCHEMA_REFDATA, "gs_companies"),
            (SCHEMA_REFDATA, "gs_year_features"),
            (SCHEMA_REFDATA, "gs_years"),
            (SCHEMA_GENERATION, "station_groups"),
            (SCHEMA_GENERATION, "documents_kommod"),
        ]

        all_stages = [
            ("STAGE 8", stage8_tables),
            ("STAGE 7", stage7_tables),
            ("STAGE 6", stage6_tables),
            ("STAGE 5", stage5_tables),
            ("STAGE 4", stage4_tables),
            ("STAGE 3", stage3_tables),
            ("STAGE 2", stage2_tables),
            ("STAGE 1", stage1_tables),
        ]

        print("Scanning tables for NULL database_version_id...")
        total_to_delete = 0
        table_counts = []
        for _, tables in all_stages:
            for schema, table in tables:
                if not _table_has_version_column(schema, table):
                    continue
                count = _count_null_rows(schema, table)
                if count > 0:
                    table_counts.append((schema, table, count))
                    total_to_delete += count

        if not table_counts:
            print("No rows found with database_version_id IS NULL.")
            return

        print("\nRows to delete:")
        for schema, table, count in table_counts:
            print(f"  - {schema}.{table}: {count}")
        print(f"\nTotal rows to delete: {total_to_delete}")

        if args.dry_run:
            print("\nDry run requested. No changes applied.")
            return

        if not args.yes:
            response = input("\nProceed with deletion? (yes/no): ").strip().lower()
            if response != "yes":
                print("Canceled by user.")
                return

        print("\nDeleting rows...")
        deleted_total = 0
        try:
            for stage_name, tables in all_stages:
                print(f"{stage_name}:")
                for schema, table in tables:
                    if not _table_has_version_column(schema, table):
                        continue
                    count = _count_null_rows(schema, table)
                    if count == 0:
                        continue
                    deleted = _delete_null_rows(schema, table)
                    deleted_total += deleted
                    print(f"  - {schema}.{table}: deleted {deleted}")

            db.session.commit()
            print(f"\nDone. Deleted rows: {deleted_total}")
        except Exception as exc:
            db.session.rollback()
            print(f"\nERROR: {exc}")
            raise

        print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)


if __name__ == "__main__":
    main()
