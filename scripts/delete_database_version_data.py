# -*- coding: utf-8 -*-
"""
Скрипт для удаления всех записей с указанным database_version_id.

Использование:
    python scripts/delete_database_version_data.py 19
    python scripts/delete_database_version_data.py 19 --dry-run
    python scripts/delete_database_version_data.py 19 --yes
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
from config import SCHEMA_REFDATA, SCHEMA_GENERATION, SCHEMA_FUEL, SCHEMA_LOGS  # noqa: E402


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


def _count_version_rows(schema, table, version_id):
    query = text(
        f"""
        SELECT COUNT(*) FROM {schema}.{table}
        WHERE database_version_id = :version_id
        """
    )
    return db.session.execute(query, {"version_id": version_id}).scalar()


def _delete_version_rows(schema, table, version_id):
    query = text(
        f"""
        DELETE FROM {schema}.{table}
        WHERE database_version_id = :version_id
        """
    )
    result = db.session.execute(query, {"version_id": version_id})
    return result.rowcount


def main():
    parser = argparse.ArgumentParser(
        description="Delete all rows with database_version_id = N across versioned tables."
    )
    parser.add_argument("version_id", type=int, help="database_version_id to delete (e.g. 19)")
    parser.add_argument("--dry-run", action="store_true", help="Only report counts, no deletes.")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    parser.add_argument("--delete-version-record", action="store_true",
                        help="Also delete the row from gs_database_versions.")
    args = parser.parse_args()

    version_id = args.version_id
    app = create_app()

    with app.app_context():
        print("=" * 80)
        print(f"УДАЛЕНИЕ ДАННЫХ: database_version_id = {version_id}")
        print("=" * 80)
        print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        # Проверяем существование версии
        version_exists = db.session.execute(
            text(f"SELECT 1 FROM {SCHEMA_REFDATA}.gs_database_versions WHERE id = :vid"),
            {"vid": version_id}
        ).scalar()
        if not version_exists:
            print(f"Внимание: версия {version_id} не найдена в gs_database_versions.")
            print("Будут удалены только данные из связанных таблиц (если такие есть).")
            print()

        # Порядок удаления (сначала зависимые таблицы, затем родительские)
        stage9_tables = [
            (SCHEMA_GENERATION, "pgu_machine_powers"),
            (SCHEMA_FUEL, "gs_fue_machine_fuel_param"),
        ]
        stage8_tables = [
            (SCHEMA_GENERATION, "machine_powers"),
            (SCHEMA_GENERATION, "machine_fuels"),
            (SCHEMA_GENERATION, "machine_tes_types"),
            (SCHEMA_GENERATION, "machine_names"),
            (SCHEMA_GENERATION, "pgu_machines"),
            (SCHEMA_FUEL, "gs_fue_equipment_group_extra_fuel_param"),
            (SCHEMA_FUEL, "gs_fue_equipment_group_fuel_param"),
            (SCHEMA_FUEL, "gs_fue_equipment_group_toplivo_param"),
        ]
        stage7_tables = [
            (SCHEMA_GENERATION, "machines"),
            (SCHEMA_FUEL, "gs_fue_equipment_group_set_stations"),
            (SCHEMA_FUEL, "gs_fue_equipment_group_sets"),
            (SCHEMA_GENERATION, "station_powers"),
            (SCHEMA_GENERATION, "boilers"),
        ]
        stage6_tables = [
            (SCHEMA_GENERATION, "stations"),
        ]
        stage5_tables = [
            (SCHEMA_REFDATA, "gs_regional_district_regional_energy_system"),
            (SCHEMA_REFDATA, "gs_energy_areas"),
            (SCHEMA_REFDATA, "gs_energy_units"),
        ]
        stage4_tables = [
            (SCHEMA_REFDATA, "gs_regional_districts"),
            (SCHEMA_REFDATA, "gs_regional_energy_systems"),
        ]
        stage3_tables = [
            (SCHEMA_REFDATA, "gs_union_energy_systems"),
            (SCHEMA_REFDATA, "gs_synchronous_areas"),
            (SCHEMA_REFDATA, "gs_energy_zones"),
            (SCHEMA_REFDATA, "gs_federal_districts"),
        ]
        stage2_tables = [
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
            (SCHEMA_REFDATA, "gs_year_service"),
            (SCHEMA_REFDATA, "gs_refdata_entity_years"),
            (SCHEMA_REFDATA, "gs_refdata_entities"),
            (SCHEMA_GENERATION, "station_groups"),
            (SCHEMA_GENERATION, "documents_kommod"),
            (SCHEMA_LOGS, "logs"),
        ]

        all_stages = [
            ("STAGE 9", stage9_tables),
            ("STAGE 8", stage8_tables),
            ("STAGE 7", stage7_tables),
            ("STAGE 6", stage6_tables),
            ("STAGE 5", stage5_tables),
            ("STAGE 4", stage4_tables),
            ("STAGE 3", stage3_tables),
            ("STAGE 2", stage2_tables),
        ]

        print(f"Поиск записей с database_version_id = {version_id}...")
        total_to_delete = 0
        table_counts = []
        for _, tables in all_stages:
            for schema, table in tables:
                if table == "gs_database_versions" and not args.delete_version_record:
                    continue
                try:
                    if not _table_has_version_column(schema, table):
                        continue
                except Exception:
                    continue
                try:
                    count = _count_version_rows(schema, table, version_id)
                except Exception:
                    count = 0
                if count > 0:
                    table_counts.append((schema, table, count))
                    total_to_delete += count

        if not table_counts:
            print(f"Записей с database_version_id = {version_id} не найдено.")
            return

        print("\nЗаписи для удаления:")
        for schema, table, count in table_counts:
            print(f"  - {schema}.{table}: {count}")
        print(f"\nВсего записей к удалению: {total_to_delete}")

        if args.dry_run:
            print("\nРежим dry-run. Изменения не применяются.")
            return

        if not args.yes:
            response = input("\nПродолжить удаление? (yes/no): ").strip().lower()
            if response != "yes":
                print("Отменено пользователем.")
                return

        print("\nУдаление записей...")
        deleted_total = 0
        try:
            for stage_name, tables in all_stages:
                print(f"{stage_name}:")
                for schema, table in tables:
                    if table == "gs_database_versions" and not args.delete_version_record:
                        continue
                    try:
                        if not _table_has_version_column(schema, table):
                            continue
                    except Exception:
                        continue
                    try:
                        count = _count_version_rows(schema, table, version_id)
                    except Exception:
                        count = 0
                    if count == 0:
                        continue
                    try:
                        deleted = _delete_version_rows(schema, table, version_id)
                        deleted_total += deleted
                        print(f"  - {schema}.{table}: удалено {deleted}")
                    except Exception as e:
                        print(f"  - {schema}.{table}: ОШИБКА {e}")
                        raise

            if args.delete_version_record and version_exists:
                result = db.session.execute(
                    text(f"DELETE FROM {SCHEMA_REFDATA}.gs_database_versions WHERE id = :vid"),
                    {"vid": version_id}
                )
                deleted_total += result.rowcount
                if result.rowcount > 0:
                    print(f"  - {SCHEMA_REFDATA}.gs_database_versions: удалена запись версии {version_id}")

            db.session.commit()
            print(f"\nГотово. Удалено записей: {deleted_total}")
        except Exception as exc:
            db.session.rollback()
            print(f"\nОШИБКА: {exc}")
            raise

        print(f"Время завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)


if __name__ == "__main__":
    main()
