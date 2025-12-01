# -*- coding: utf-8 -*-
"""
StationGroup model (Группа станций).
- Связь: StationGroup.stations (back_populates='group').
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA

class StationGroup(db.Model):
    __tablename__ = 'station_groups'
    __table_args__ = {"schema": SCHEMA_GENERATION}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    # Уникальность будет обеспечиваться через миграцию с database_version_id
    name = db.Column(db.String(80), nullable=False, index=True)

    stations = db.relationship(
        "Station",
        back_populates="group",
        foreign_keys="Station.id_station_group"
    )

    # timestamps (UTC, server-side)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    def __repr__(self) -> str:
        return f"<StationGroup id={self.id} name={self.name!r}>"
