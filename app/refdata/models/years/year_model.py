# -*- coding: utf-8 -*-
"""
Year model (Год).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA, SCHEMA_GENERATION
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin


class Year(db.Model, AuditMixin, VersionedModelMixin):
    __tablename__ = 'gs_sys_years'
    __table_args__ = (
        db.UniqueConstraint(
            "number",
            "database_version_id",
            name="uq_gs_years_number_version",
        ),
        {
            "schema": SCHEMA_REFDATA,
            "extend_existing": True,
        },
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    number = db.Column(db.Integer, nullable=False, index=True)

    # FK -> YearFeature
    id_year_feature = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_year_features.id', ondelete='RESTRICT'),
        nullable=True,
        index=True
    )
    year_feature = db.relationship('YearFeature', back_populates='years')

    # FK -> DatabaseVersion
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Годы теперь версионируются через database_version_id

    # Relations retained as-is
    station_powers = db.relationship('StationPower', back_populates='year')
    machine_powers = db.relationship('MachinePower', back_populates='year')
    machine_fuels = db.relationship('MachineFuel', back_populates='year')
    machine_tes_types = db.relationship('MachineTesType', back_populates='year')
    machine_names = db.relationship('MachineName', back_populates='year')
    pgu_machine_names = db.relationship('PGUMachineName', back_populates='year')
    fd_economic_activity_consumption_parameters = db.relationship(
        'FederalDistrictEATConsumptionParameter', back_populates='year'
    )
    rf_economic_activity_consumption_parameters = db.relationship(
        'RussiaFederationConsumptionParameter', back_populates='year'
    )
    fd_economic_activity_accum_fixed_capital_parameters = db.relationship(
        'FederalDistrictAccumFixedCapitalParameter', back_populates='year'
    )
    rf_economic_activity_accum_fixed_capital_parameters = db.relationship(
        'RussiaFederationAccumFixedCapitalParameter', back_populates='year'
    )
    fd_economic_activity_product_output_parameters = db.relationship(
        'FederalDistrictProductOutputParameter',
        back_populates='year',
        primaryjoin=(
            "and_(Year.number==FederalDistrictProductOutputParameter.year_number, "
            "Year.database_version_id==FederalDistrictProductOutputParameter.database_version_id)"
        ),
    )
    rf_economic_activity_product_output_parameters = db.relationship(
        'RussiaFederationProductOutputParameter',
        back_populates='year',
        primaryjoin=(
            "and_(Year.number==RussiaFederationProductOutputParameter.year_number, "
            "Year.database_version_id==RussiaFederationProductOutputParameter.database_version_id)"
        ),
    )
    fd_electrical_intensity_year_parameters = db.relationship(
        'FederalDistrictElectricalIntensityYearParameter', back_populates='year'
    )
    rf_electrical_intensity_year_parameters = db.relationship(
        'RussiaFederationElectricalIntensityYearParameter', back_populates='year'
    )
    fd_population_parameters = db.relationship(
        'FederalDistrictPopulationParameter', back_populates='year'
    )
    fd_accum_monetary_income_parameters = db.relationship(
        'FederalDistrictAccumMonetaryIncomeParameter', back_populates='year'
    )
    fd_population_consumption_year_parameters = db.relationship(
        'FederalDistrictPopulationConsumptionYearParameter', back_populates='year'
    )

    def __repr__(self) -> str:
        return f"<Year id={self.id} number={self.number}>"
