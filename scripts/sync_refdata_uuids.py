"""
Synchronize ref_uuid values across database versions for refdata tables.

Usage examples:
  python scripts/sync_refdata_uuids.py
  python scripts/sync_refdata_uuids.py --tables regional_districts,federal_districts
  python scripts/sync_refdata_uuids.py --base-version-id 3 --dry-run
  python scripts/sync_refdata_uuids.py --table regional_districts --key-fields region_id
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.extensions import db
from app.common.models.database_version_model import DatabaseVersion

from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.energy_area_model import EnergyArea
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit

from app.refdata.models.fuels.fuel_category_model import FuelCategory
from app.refdata.models.fuels.fuel_type_model import FuelType
from app.refdata.models.fuels.fuel_model import Fuel
from app.refdata.models.gen_companies.gen_company_model import GenCompany

from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.refdata_for_stations.condition_type_model import ConditionType
from app.refdata.models.refdata_for_stations.machine.machine_type_model import MachineType
from app.refdata.models.refdata_for_stations.machine.tes_type_model import TesType
from app.refdata.models.refdata_for_stations.machine.tes_machine_type_model import TesMachineType
from app.refdata.models.refdata_for_stations.machine.pgu_tes_machine_type_model import PGUTesMachineType
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroup
from app.refdata.models.refdata_for_stations.technologies.technology_type_model import TechnologyType
from app.refdata.models.refdata_for_stations.technologies.technology_availability_model import (
    TechnologyAvailability,
)


def _normalize_value(value):
    if isinstance(value, str):
        return value.strip()
    return value


def _key_by_fields(obj, fields: Iterable[str]):
    return tuple(_normalize_value(getattr(obj, field)) for field in fields)


def _regional_district_key(obj: RegionalDistrict):
    region_id = _normalize_value(obj.region_id)
    if region_id:
        return ("region_id", region_id)
    return ("name", _normalize_value(obj.name))


@dataclass(frozen=True)
class TableConfig:
    name: str
    model: type
    key_fields: tuple[str, ...] | None = None
    key_func: Callable | None = None


TABLES: dict[str, TableConfig] = {
    "federal_districts": TableConfig("federal_districts", FederalDistrict, ("name",)),
    "regional_districts": TableConfig(
        "regional_districts", RegionalDistrict, key_func=_regional_district_key
    ),
    "energy_zones": TableConfig("energy_zones", EnergyZone, ("number",)),
    "synchronous_areas": TableConfig("synchronous_areas", SynchronousArea, ("name",)),
    "energy_system_types": TableConfig("energy_system_types", EnergySystemType, ("name",)),
    "union_energy_systems": TableConfig("union_energy_systems", UnionEnergySystem, ("name",)),
    "regional_energy_systems": TableConfig("regional_energy_systems", RegionalEnergySystem, ("name",)),
    "energy_areas": TableConfig("energy_areas", EnergyArea, ("name",)),
    "energy_units": TableConfig("energy_units", EnergyUnit, ("name",)),
    "fuel_categories": TableConfig("fuel_categories", FuelCategory, ("name",)),
    "fuel_types": TableConfig("fuel_types", FuelType, ("name",)),
    "fuels": TableConfig("fuels", Fuel, ("name",)),
    "gen_companies": TableConfig("gen_companies", GenCompany, ("name",)),
    "station_types": TableConfig("station_types", StationType, ("name",)),
    "condition_types": TableConfig("condition_types", ConditionType, ("name",)),
    "machine_types": TableConfig("machine_types", MachineType, ("name",)),
    "tes_types": TableConfig("tes_types", TesType, ("name",)),
    "tes_machine_types": TableConfig("tes_machine_types", TesMachineType, ("name",)),
    "pgu_tes_machine_types": TableConfig("pgu_tes_machine_types", PGUTesMachineType, ("name",)),
    "equipment_groups": TableConfig("equipment_groups", EquipmentGroup, ("name",)),
    "technology_types": TableConfig("technology_types", TechnologyType, ("name",)),
    "technology_availabilities": TableConfig(
        "technology_availabilities", TechnologyAvailability, ("name",)
    ),
}


def _get_version_ids(model):
    rows = (
        db.session.query(model.database_version_id)
        .distinct()
        .order_by(model.database_version_id.asc())
        .all()
    )
    return [row[0] for row in rows]


def _resolve_base_version_id(explicit_id, model):
    if explicit_id is not None:
        return explicit_id
    active = DatabaseVersion.query.filter_by(is_active=True).first()
    if active and db.session.query(model).filter(model.database_version_id == active.id).first():
        return active.id
    version_ids = _get_version_ids(model)
    if not version_ids:
        return None
    return version_ids[0]


def _apply_version_filter(query, model, version_id):
    if version_id is None:
        return query.filter(model.database_version_id.is_(None))
    return query.filter(model.database_version_id == version_id)


def _build_key_map(config: TableConfig, base_version_id):
    query = _apply_version_filter(db.session.query(config.model), config.model, base_version_id)
    records = query.all()

    key_map = {}
    duplicates = []
    for obj in records:
        if config.key_func:
            key = config.key_func(obj)
        else:
            key = _key_by_fields(obj, config.key_fields or ())
        if key in key_map and key_map[key] != obj.ref_uuid:
            duplicates.append((key, key_map[key], obj.ref_uuid))
            continue
        key_map[key] = obj.ref_uuid
    return key_map, duplicates


def _sync_table(config: TableConfig, base_version_id, dry_run: bool):
    key_map, duplicates = _build_key_map(config, base_version_id)

    if duplicates:
        print(f"[{config.name}] WARNING: duplicate keys in base version:")
        for key, uuid_a, uuid_b in duplicates:
            print(f"  key={key} uuid_a={uuid_a} uuid_b={uuid_b}")

    if not key_map:
        print(f"[{config.name}] no base records to sync (base_version_id={base_version_id})")
        return 0

    version_ids = _get_version_ids(config.model)
    total_updated = 0

    for version_id in version_ids:
        if version_id == base_version_id:
            continue
        with db.session.no_autoflush:
            query = _apply_version_filter(
                db.session.query(config.model), config.model, version_id
            )
            updated = 0
            for obj in query.all():
                if config.key_func:
                    key = config.key_func(obj)
                else:
                    key = _key_by_fields(obj, config.key_fields or ())
                target_uuid = key_map.get(key)
                if target_uuid and obj.ref_uuid != target_uuid:
                    obj.ref_uuid = target_uuid
                    updated += 1
        if updated:
            print(f"[{config.name}] version_id={version_id} updated={updated}")
        total_updated += updated

    if total_updated and not dry_run:
        db.session.commit()
    elif dry_run:
        db.session.rollback()

    return total_updated


def _parse_args():
    parser = argparse.ArgumentParser(description="Sync ref_uuid across versions for refdata.")
    parser.add_argument(
        "--tables",
        help="Comma-separated list of tables to sync (default: all).",
        default="",
    )
    parser.add_argument(
        "--table",
        help="Alias for a single table (same as --tables with one value).",
        default="",
    )
    parser.add_argument(
        "--base-version-id",
        type=int,
        default=7,
        help="Base version id to take ref_uuid values from. Default: 7.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not commit changes; print what would be updated.",
    )
    parser.add_argument(
        "--key-fields",
        help="Override key fields for a single table, comma-separated.",
        default="",
    )
    return parser.parse_args()


def main():
    args = _parse_args()
    requested = args.tables or args.table
    if requested:
        table_names = [item.strip() for item in requested.split(",") if item.strip()]
    else:
        table_names = list(TABLES.keys())

    if args.key_fields and len(table_names) != 1:
        raise ValueError("--key-fields can be used only with a single --table/--tables entry.")

    app = create_app()
    with app.app_context():
        prev_history_flag = db.session.info.get("refdata_history_in_progress")
        db.session.info["refdata_history_in_progress"] = True
        try:
            for table_name in table_names:
                if table_name not in TABLES:
                    print(f"Unknown table: {table_name}")
                    continue
                config = TABLES[table_name]
                if args.key_fields:
                    fields = tuple(
                        item.strip() for item in args.key_fields.split(",") if item.strip()
                    )
                    if not fields:
                        raise ValueError("--key-fields must contain at least one field.")
                    config = TableConfig(config.name, config.model, key_fields=fields)

                base_version_id = _resolve_base_version_id(args.base_version_id, config.model)
                updated = _sync_table(config, base_version_id, args.dry_run)
                print(f"[{config.name}] total_updated={updated}")
        finally:
            if prev_history_flag is None:
                db.session.info.pop("refdata_history_in_progress", None)
            else:
                db.session.info["refdata_history_in_progress"] = prev_history_flag


if __name__ == "__main__":
    main()
