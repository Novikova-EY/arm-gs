# -*- coding: utf-8 -*-
"""
Year model (Год).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA

class Year(db.Model):
    __tablename__ = 'years'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    number = db.Column(db.Integer, unique=True, nullable=False, index=True)

    # FK -> YearFeature
    id_year_feature = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.year_features.id', ondelete='RESTRICT'),
        nullable=True,
        index=True
    )
    year_feature = db.relationship('YearFeature', back_populates='years')

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relations retained as-is
    station_powers = db.relationship('StationPower', back_populates='year')
    machine_powers = db.relationship('MachinePower', back_populates='year')
    machine_fuels = db.relationship('MachineFuel', back_populates='year')
    machine_tes_types = db.relationship('MachineTesType', back_populates='year', lazy='subquery')

    def __repr__(self) -> str:
        return f"<Year id={self.id} number={self.number}>"
