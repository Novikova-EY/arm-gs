from sqlalchemy import func

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_RATIONAL_STRUCTURE, SCHEMA_REFDATA


class TerritoryTechnology(db.Model, AuditMixin):
    __tablename__ = "gs_rs_territory_technologies"
    __table_args__ = (
        db.UniqueConstraint("database_version_id", "energy_zone_id", "name", name="uq_rs_territory_technology"),
        {"schema": SCHEMA_RATIONAL_STRUCTURE},
    )

    id = db.Column(db.Integer, primary_key=True)
    database_version_id = db.Column(db.Integer, db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    energy_zone_id = db.Column(db.Integer, db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_energy_zones.id", ondelete="CASCADE"), nullable=False, index=True)
    energy_zone = db.relationship("EnergyZone")
    name = db.Column(db.Text, nullable=False)
    technology_number = db.Column(db.Integer, nullable=False)
    technology_type_id = db.Column(db.Integer, db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_technology_types.id", ondelete="SET NULL"))
    equipment_group_type_id = db.Column(db.Integer, db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_equipment_groups.id", ondelete="SET NULL"))
    fuel_category = db.Column(db.String(10))
    references_manual = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    technology_type = db.relationship("TechnologyType")
    equipment_group_type = db.relationship("EquipmentGroupType")
    source_row = db.Column(db.Integer, nullable=False)
    unit_power = db.Column(db.Float)
    minimum_power = db.Column(db.Float)
    capacity_factor_1 = db.Column(db.Float)
    capacity_factor_2 = db.Column(db.Float)
    capacity_factor_3 = db.Column(db.Float)
    capacity_factor_4 = db.Column(db.Float)
    standard_deviation = db.Column(db.Float)
    capital_cost = db.Column(db.Float)
    modernization_cost = db.Column(db.Float)
    fuel_cost_winter = db.Column(db.Float)
    fuel_cost_summer = db.Column(db.Float)
    fixed_cost = db.Column(db.Float)
    transmission_cost = db.Column(db.Float)
    outage_probability_winter = db.Column(db.Float)
    outage_probability_summer = db.Column(db.Float)
    co2_per_fuel = db.Column(db.Float)
    co2_per_energy = db.Column(db.Float)
    quantity_min = db.Column(db.Float)
    quantity_mod = db.Column(db.Float)
    quantity_max = db.Column(db.Float)
    source_filename = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class TerritoryTransferSection(db.Model, AuditMixin):
    __tablename__ = "gs_rs_territory_transfer_sections"
    __table_args__ = (
        db.UniqueConstraint("database_version_id", "name", name="uq_rs_territory_transfer_section"),
        {"schema": SCHEMA_RATIONAL_STRUCTURE},
    )

    id = db.Column(db.Integer, primary_key=True)
    database_version_id = db.Column(db.Integer, db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    name = db.Column(db.Text, nullable=False)
    source_row = db.Column(db.Integer, nullable=False)
    # Ключи – номера энергозон из справочника выбранной версии.
    zone_membership = db.Column(db.JSON, nullable=False)
    zone_paths = db.Column(db.JSON, nullable=False)
    forward_limit = db.Column(db.Float, nullable=False)
    reverse_limit = db.Column(db.Float, nullable=False)
    source_filename = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
