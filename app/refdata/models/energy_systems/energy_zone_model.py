# -*- coding: utf-8 -*-
"""
EnergyZone model (Справочник «Энергозоны»).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA

class EnergyZone(db.Model):
    __tablename__ = 'energy_zones'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    number = db.Column(db.String(256), unique=True, nullable=False, index=True)
    name = db.Column(db.String(256), unique=True, nullable=False, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # FK -> RegionalDistrict
    id_regional_district = db.Column(
        "id_regional_district",
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.regional_districts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    regional_district = db.relationship(
        "RegionalDistrict",
        back_populates="energy_zones",
        foreign_keys=[id_regional_district],
    )

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<EnergyZone id={self.id} number={self.number!r} name={self.name!r}>"