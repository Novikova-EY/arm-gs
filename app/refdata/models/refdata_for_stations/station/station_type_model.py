# -*- coding: utf-8 -*-
"""
StationType model (Тип электростанции).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA

class StationType(db.Model):
    __tablename__ = 'station_types'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), unique=True, nullable=False, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    stations = db.relationship('Station', back_populates='station_type')

    def __repr__(self) -> str:
        return f"<StationType id={self.id} name={self.name!r}>"
