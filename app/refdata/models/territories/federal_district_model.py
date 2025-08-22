# -*- coding: utf-8 -*-
"""
FederalDistrict model (Федеральный округ).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA

class FederalDistrict(db.Model):
    __tablename__ = 'federal_districts'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name_full = db.Column(db.String(80), unique=True, nullable=True)
    name_abr = db.Column(db.String(80), unique=True, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    regional_districts = db.relationship('RegionalDistrict', back_populates='federal_district')

    def __repr__(self) -> str:
        return f"<FederalDistrict id={self.id} name={self.name!r}>"
