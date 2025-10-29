# -*- coding: utf-8 -*-
"""
SynchronousArea model (Синхронная зона).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA, SCHEMA_GENERATION

class SynchronousArea(db.Model):
    __tablename__ = 'synchronous_areas'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    number = db.Column(db.String(256), unique=True, nullable=True, index=True)
    name = db.Column(db.String(256), unique=True, nullable=False, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # связь с моделью RegionalDistrict
    regional_districts = db.relationship(
        'RegionalDistrict',
        back_populates='synchronous_area',
        foreign_keys='RegionalDistrict.id_synchronous_area',
    )

    def __repr__(self) -> str:
        return f"<SynchronousArea id={self.id} number={self.number!r} name={self.name!r}>"
