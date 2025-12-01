# -*- coding: utf-8 -*-
"""
MachineTesType model (Тип ТЭС агрегата).
- Связи сохранены: year (Year.machine_tes_types), machine_tes_type (Machine.machine_tes_types), tes_type (TesType.machine_tes_types).
"""
from sqlalchemy.sql import func
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA

class MachineTesType(db.Model):
    __tablename__ = 'machine_tes_types'
    __table_args__ = (
        Index('ix_machine_tes_type_id_machine', 'id_machine'),
        Index('ix_machine_tes_type_id_tes_type', 'id_tes_type'),
        Index('ix_machine_tes_type_year_number', 'year_number'),
        {"schema": SCHEMA_GENERATION},
    )
    __mapper_args__ = {"confirm_deleted_rows": False}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK -> Year (по полю years.number)
    year_number = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.years.number', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    year = db.relationship('Year', back_populates='machine_tes_types', lazy='noload')

    # FK -> Machine
    id_machine = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_GENERATION}.machines.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    machine_tes_type = db.relationship('Machine', back_populates='machine_tes_types')

    # FK -> TesType
    id_tes_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.tes_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    tes_type = db.relationship('TesType', back_populates='machine_tes_types')

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
        return f"<MachineTesType id={self.id} machine_id={self.id_machine} year={self.year_number} tes_type_id={self.id_tes_type}>"
