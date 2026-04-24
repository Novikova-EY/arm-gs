# -*- coding: utf-8 -*-
"""
Агрегированный результат этапа «Коэфф» по параметру распределения.
"""
from sqlalchemy import Index, UniqueConstraint

from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_REFDATA


class DistributionCoefficientSummary(db.Model):
    __tablename__ = "gs_fue_distribution_coefficient_summaries"
    __table_args__ = (
        UniqueConstraint(
            "distribution_parameter_id",
            "year_number",
            "database_version_id",
            name="uq_fue_dist_coeff_summary_param_year_version",
        ),
        Index("ix_fue_dist_coeff_sum_param", "distribution_parameter_id"),
        Index("ix_fue_dist_coeff_sum_year", "year_number"),
        Index("ix_fue_dist_coeff_sum_db_ver", "database_version_id"),
        {"schema": SCHEMA_FUEL},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    distribution_parameter_id = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_FUEL}.gs_fue_distribution_parameters.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    year_number = db.Column(db.Integer, nullable=False)
    base_year = db.Column(db.Integer, nullable=True)
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
    )

    bnust = db.Column(db.Numeric(20, 6), nullable=True)
    be = db.Column(db.Numeric(20, 6), nullable=True)
    betp = db.Column(db.Numeric(20, 6), nullable=True)
    bq = db.Column(db.Numeric(20, 6), nullable=True)
    bqotr = db.Column(db.Numeric(20, 6), nullable=True)

    cnust = db.Column(db.Numeric(20, 6), nullable=True)
    cnustn = db.Column(db.Numeric(20, 6), nullable=True)
    cnustngt = db.Column(db.Numeric(20, 6), nullable=True)
    cnustnpg = db.Column(db.Numeric(20, 6), nullable=True)
    cnustnps = db.Column(db.Numeric(20, 6), nullable=True)
    cetp = db.Column(db.Numeric(20, 6), nullable=True)
    cq = db.Column(db.Numeric(20, 6), nullable=True)
    cqotr = db.Column(db.Numeric(20, 6), nullable=True)

    bptp = db.Column(db.Numeric(20, 6), nullable=True)
    cptp = db.Column(db.Numeric(20, 6), nullable=True)
    bh = db.Column(db.Numeric(20, 6), nullable=True)
    ch = db.Column(db.Numeric(20, 6), nullable=True)
    ph1 = db.Column(db.Numeric(20, 6), nullable=True)
    pe = db.Column(db.Numeric(20, 6), nullable=True)
    hd = db.Column(db.Numeric(20, 6), nullable=True)
    kn = db.Column(db.Numeric(20, 6), nullable=True)
    ph = db.Column(db.Numeric(20, 6), nullable=True)
    pq = db.Column(db.Numeric(20, 6), nullable=True)
    potr = db.Column(db.Numeric(20, 6), nullable=True)

    e_target = db.Column(db.Numeric(20, 6), nullable=True)
    k = db.Column(db.Numeric(20, 6), nullable=True)
    kplus = db.Column(db.Numeric(20, 6), nullable=True)
    kmin = db.Column(db.Numeric(20, 6), nullable=True)
    knps = db.Column(db.Numeric(20, 6), nullable=True)
    kngt = db.Column(db.Numeric(20, 6), nullable=True)
    knpg = db.Column(db.Numeric(20, 6), nullable=True)
    hnps = db.Column(db.Numeric(20, 6), nullable=True)
    hngt = db.Column(db.Numeric(20, 6), nullable=True)
    hnpg = db.Column(db.Numeric(20, 6), nullable=True)
    doptim = db.Column(db.Numeric(20, 6), nullable=True)
    lim = db.Column(db.Numeric(20, 6), nullable=True)

    note = db.Column(db.Text, nullable=True)

    distribution_parameter = db.relationship(
        "DistributionParameter",
        backref=db.backref("coefficient_summaries", lazy="dynamic"),
    )

    def __repr__(self) -> str:
        return (
            f"<DistributionCoefficientSummary id={self.id} "
            f"distribution_parameter_id={self.distribution_parameter_id} "
            f"year_number={self.year_number}>"
        )
