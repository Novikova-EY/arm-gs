# -*- coding: utf-8 -*-
"""
Boiler model (Котёл электростанции).
- Связь: Boiler.boiler_station -> Station.boilers (back_populates).
- Таймстемпы на стороне БД (UTC) через func.now().
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_GENERATION

class Boiler(db.Model):
    __tablename__ = 'boilers'
    __table_args__ = {"schema": SCHEMA_GENERATION}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)

    # FK -> Station
    id_station = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_GENERATION}.stations.id', ondelete='RESTRICT'),
        nullable=True,
        index=True
    )
    boiler_station = db.relationship('Station', back_populates='boilers')

    # timestamps (UTC, server-side)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<Boiler id={self.id} name={self.name!r} station_id={self.id_station}>"
