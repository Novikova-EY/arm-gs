from sqlalchemy import CheckConstraint, Index, UniqueConstraint, func
from sqlalchemy.orm import synonym

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from app.rational_structure.equipment_types import EQUIPMENT_TYPES
from config import SCHEMA_GENERATION, SCHEMA_RATIONAL_STRUCTURE, SCHEMA_REFDATA


class EquipmentTechnicalCharacteristic(db.Model, AuditMixin):
    """Технические характеристики оборудования по данным Техинспекции."""

    __tablename__ = "gs_rs_equipment_technical_characteristics"
    __table_args__ = (
        UniqueConstraint("database_version_id", "equipment_type", "equipment_code", "report_year", name="uq_rs_equipment_code_year_version"),
        CheckConstraint(
            "equipment_type IN ('steam', 'gas', 'hydro', 'boiler_energy', 'boiler_water')",
            name="ck_rs_equipment_type",
        ),
        Index("ix_rs_equipment_version_year_type", "database_version_id", "report_year", "equipment_type"),
        Index("ix_rs_equipment_version_machine", "database_version_id", "machine_id"),
        Index("ix_rs_equipment_version_pgu_machine", "database_version_id", "pgu_machine_id"),
        {"schema": SCHEMA_RATIONAL_STRUCTURE},
    )

    id = db.Column(db.Integer, primary_key=True)
    database_version_id = db.Column(db.Integer, db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="CASCADE"), nullable=False)
    equipment_type = db.Column(db.String(20), nullable=False)
    # Совместимость с сервисами турбин после обобщения модели оборудования.
    turbine_type = synonym("equipment_type")
    equipment_code = db.Column(db.String(100), nullable=False)
    report_year = db.Column(db.Integer, nullable=False)
    equipment_kind = db.Column(db.Text)
    subject_name = db.Column(db.Text)
    station_name = db.Column(db.Text)
    station_number = db.Column(db.Text)
    equipment_subclass = db.Column(db.Text)
    equipment_brand = db.Column(db.Text)
    commissioning_year = db.Column(db.Integer)
    installed_electric_power = db.Column(db.Numeric(24, 8))
    nominal_active_power = db.Column(db.Numeric(24, 8))
    technical_min_power = db.Column(db.Numeric(24, 8))
    technical_max_power = db.Column(db.Numeric(24, 8))
    total_heat_power = db.Column(db.Numeric(24, 8))
    district_heat_power = db.Column(db.Numeric(24, 8))
    electricity_generation = db.Column(db.Numeric(24, 8))
    heat_output = db.Column(db.Numeric(24, 8))
    standard_service_life = db.Column(db.Text)
    operating_hours_total = db.Column(db.Numeric(24, 8))
    operating_hours_year = db.Column(db.Numeric(24, 8))
    expected_service_life_year = db.Column(db.Integer)
    standard_start_count = db.Column(db.Numeric(24, 8))
    start_count_total = db.Column(db.Numeric(24, 8))
    start_count_year = db.Column(db.Numeric(24, 8))
    standard_overhaul_hours = db.Column(db.Numeric(24, 8))
    last_overhaul_year = db.Column(db.Integer)
    hours_since_overhaul = db.Column(db.Numeric(24, 8))
    extension_count = db.Column(db.Numeric(24, 8))
    extension_decision = db.Column(db.Text)
    assigned_service_life = db.Column(db.Text)
    element_replacement_year = db.Column(db.Integer)
    replaced_element = db.Column(db.Text)
    remarking_year = db.Column(db.Integer)
    remarking_reason = db.Column(db.Text)
    decommissioning_year = db.Column(db.Integer)
    decommissioning_reason = db.Column(db.Text)
    recommissioning = db.Column(db.Text)
    # Поля гидротурбин и котлов, которых нет в общем наборе турбин.
    design_head = db.Column(db.Numeric(24, 8))
    steam_capacity = db.Column(db.Numeric(24, 8))
    heat_power = db.Column(db.Numeric(24, 8))
    fuel_project = db.Column(db.Text)
    fuel_main = db.Column(db.Text)
    fuel_reserve = db.Column(db.Text)
    efficiency_gross = db.Column(db.Numeric(24, 8))
    water_consumption = db.Column(db.Numeric(24, 8))
    operation_mode = db.Column(db.Text)
    # Состав специфичных полей может отличаться у разных видов оборудования.
    extra_values = db.Column(db.JSON, nullable=False, default=dict)
    # Сопоставление с агрегатом генерации
    machine_id = db.Column(db.Integer, db.ForeignKey(f"{SCHEMA_GENERATION}.gs_gen_machines.id", ondelete="SET NULL"), nullable=True, index=True)
    pgu_machine_id = db.Column(db.Integer, db.ForeignKey(f"{SCHEMA_GENERATION}.gs_gen_pgu_machines.id", ondelete="SET NULL"), nullable=True, index=True)
    match_status = db.Column(db.String(20), nullable=False, default="not_checked")
    match_details = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    @property
    def equipment_type_label(self) -> str:
        return EQUIPMENT_TYPES.get(self.equipment_type, self.equipment_type)
