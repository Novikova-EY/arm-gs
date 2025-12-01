# -*- coding: utf-8 -*-
"""
TesType model (Тип ТЭС).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA, SCHEMA_GENERATION

class TesType(db.Model):
    __tablename__ = 'tes_types'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    machine_tes_types = db.relationship(
        'MachineTesType',
        back_populates='tes_type',
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TesType id={self.id} name={self.name!r}>"
