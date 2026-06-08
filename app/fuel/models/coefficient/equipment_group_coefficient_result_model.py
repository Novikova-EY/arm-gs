# -*- coding: utf-8 -*-
"""
Снимок результатов этапа «Коэфф» для группы оборудования и параметра распределения.
"""

from sqlalchemy import Index, UniqueConstraint

from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_REFDATA


class EquipmentGroupCoefficientResult(db.Model):
    __tablename__ = "gs_fue_equipment_group_coefficient_results"
    __table_args__ = (
        UniqueConstraint(
            "equipment_group_id",
            "distribution_parameter_id",
            "year_number",
            "database_version_id",
            name="uq_eq_group_coeff_result_group_dist_year_version",
        ),
        Index("ix_fue_eg_coeff_res_eg_id", "equipment_group_id"),
        Index("ix_fue_eg_coeff_res_dist_id", "distribution_parameter_id"),
        Index("ix_fue_eg_coeff_res_year", "year_number"),
        Index("ix_fue_eg_coeff_res_db_ver", "database_version_id"),
        {"schema": SCHEMA_FUEL},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    equipment_group_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_FUEL}.gs_fue_equipment_groups.id", ondelete="RESTRICT"),
        nullable=False,
    )
    equipment_group = db.relationship(
        "EquipmentGroup",
        backref="coefficient_results",
        foreign_keys=[equipment_group_id],
        uselist=False,
        lazy="select",
    )

    distribution_parameter_id = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_FUEL}.gs_fue_distribution_parameters.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )
    distribution_parameter = db.relationship(
        "DistributionParameter",
        backref="equipment_group_coefficient_results",
        foreign_keys=[distribution_parameter_id],
        uselist=False,
        lazy="select",
    )

    year_number = db.Column(db.Integer, nullable=False)
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Входные коэффициенты параметра распределения (копия/снимок)
    k = db.Column(db.Numeric(20, 6), nullable=True)
    kplus = db.Column(db.Numeric(20, 6), nullable=True)
    kmin = db.Column(db.Numeric(20, 6), nullable=True)

    kn = db.Column(db.Numeric(20, 6), nullable=True)
    knps = db.Column(db.Numeric(20, 6), nullable=True)
    kngt = db.Column(db.Numeric(20, 6), nullable=True)
    knpg = db.Column(db.Numeric(20, 6), nullable=True)

    hnps = db.Column(db.Numeric(20, 6), nullable=True)
    hngt = db.Column(db.Numeric(20, 6), nullable=True)
    hnpg = db.Column(db.Numeric(20, 6), nullable=True)

    doptim = db.Column(db.Numeric(20, 6), nullable=True)
    lim = db.Column(db.Numeric(20, 6), nullable=True)

    coeff_base = db.Column(db.Numeric(20, 6), nullable=True)
    coeff_min = db.Column(db.Numeric(20, 6), nullable=True)
    coeff_max = db.Column(db.Numeric(20, 6), nullable=True)
    coeff_effective = db.Column(db.Numeric(20, 6), nullable=True)

    note = db.Column(db.Text, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<EquipmentGroupCoefficientResult id={self.id} "
            f"equipment_group_id={self.equipment_group_id} "
            f"distribution_parameter_id={self.distribution_parameter_id} "
            f"year_number={self.year_number}>"
        )
