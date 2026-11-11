from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import joinedload
from werkzeug.exceptions import BadRequest

from app.common.models.database_version_model import DatabaseVersion
from app.extensions import db
from app.rational_structure.models.territory_technology_model import TerritoryTechnology, TerritoryTransferSection
from app.rational_structure.services.territory_technology_columns import TECHNOLOGY_COLUMNS, TECHNOLOGY_HEADER_GROUPS
from app.rational_structure.services.territory_input_page_services import territory_reference_years
from app.rational_structure.services.territory_technology_excel_services import read_territory_inputs
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.rational_structure.services.territory_technology_matching import match_technology_name, technology_references


def import_territory_inputs(raw, version_id, username, source_filename):
    if version_id is None or db.session.get(DatabaseVersion, version_id) is None:
        raise ValueError("Выберите версию базы данных перед загрузкой.")
    technologies, sections = read_territory_inputs(raw)
    zones = {zone.number: zone for zone in db.session.scalars(select(EnergyZone).where(EnergyZone.database_version_id == version_id))}
    used_zones = {row["zone_number"] for row in technologies}
    used_zones.update(zone for row in sections for zone in row["zone_membership"])
    missing = used_zones - zones.keys()
    if missing:
        raise ValueError("В справочнике выбранной версии отсутствуют энергозоны: " + ", ".join(sorted(missing)))
    references = technology_references(version_id)
    counts = {"created": 0, "updated": 0, "technologies": len(technologies), "sections": len(sections)}
    try:
        for model, records in ((TerritoryTechnology, technologies), (TerritoryTransferSection, sections)):
            existing = list(db.session.scalars(select(model).where(model.database_version_id == version_id)))
            by_key = {(row.energy_zone_id, row.name) if model is TerritoryTechnology else row.name: row for row in existing}
            for record in records:
                if model is TerritoryTechnology:
                    record["energy_zone_id"] = zones[record.pop("zone_number")].id
                    key = (record["energy_zone_id"], record["name"])
                else:
                    key = record["name"]
                record["source_filename"] = source_filename
                row = by_key.get(key)
                if row is None:
                    if model is TerritoryTechnology:
                        record.update(match_technology_name(record["name"], references))
                    db.session.add(model(database_version_id=version_id, created_by=username, **record))
                    counts["created"] += 1
                else:
                    if model is TerritoryTechnology and not row.references_manual:
                        record.update(match_technology_name(record["name"], references))
                    for field, value in record.items():
                        setattr(row, field, value)
                    row.modified_by = username
                    counts["updated"] += 1
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return counts


def build_territory_technology_context(args, version_id):
    zones = sorted(db.session.scalars(select(EnergyZone).where(EnergyZone.database_version_id == version_id)),
                   key=lambda zone: (not zone.number.isdigit(), int(zone.number) if zone.number.isdigit() else zone.number))
    selected_zone = args.get("energy_zone", "").strip()
    zone = next((zone for zone in zones if str(zone.id) == selected_zone), None)
    if selected_zone and zone is None:
        raise BadRequest("Энергозона не найдена в выбранной версии БД.")
    rounding = args.get("rounding_digits", 1, type=int)
    if rounding not in (-1, 0, 1, 2, 3, 6):
        rounding = 1
    sheet = args.get("sheet", "technologies")
    if sheet not in ("technologies", "transfers"):
        raise BadRequest("Неизвестный лист.")
    statement = select(TerritoryTechnology).options(
        joinedload(TerritoryTechnology.energy_zone), joinedload(TerritoryTechnology.technology_type),
        joinedload(TerritoryTechnology.equipment_group_type),
    ).where(TerritoryTechnology.database_version_id == version_id)
    if zone is not None:
        statement = statement.where(TerritoryTechnology.energy_zone_id == zone.id)
    rows = list(db.session.scalars(statement.order_by(TerritoryTechnology.source_row)))
    sections = list(db.session.scalars(select(TerritoryTransferSection).where(
        TerritoryTransferSection.database_version_id == version_id).order_by(TerritoryTransferSection.source_row)))
    matrix_zones = [item for item in zones if any(item.number in row.zone_membership for row in sections)]
    if zone is not None:
        matrix_zones = [zone] if zone in matrix_zones else []
    version = db.session.get(DatabaseVersion, version_id) if version_id is not None else None
    _, year_features = territory_reference_years(version_id)
    return dict(rows=rows, sections=sections, zones=zones, matrix_zones=matrix_zones, year_features=year_features,
                selected_zone=selected_zone, selected_energy_zone=zone, sheet=sheet, rounding_digits=rounding,
                columns=TECHNOLOGY_COLUMNS, technology_header_groups=TECHNOLOGY_HEADER_GROUPS,
                version_id=version_id, version=version,
                **technology_references(version_id))
