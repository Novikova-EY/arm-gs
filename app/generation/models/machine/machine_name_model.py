# -*- coding: utf-8 -*-
"""
MachineName model (Название агрегата по годам).
- Связи сохранены: year (Year.machine_names), machine_name (Machine.machine_names).
- Текстовое поле name вместо ссылки на справочник (аналог MachineFuel с id_fuel).
"""
from sqlalchemy.sql import func
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin
from app.generation.models.common.version_year_unique_index import version_year_unique_index


class MachineName(db.Model, AuditMixin):
    __tablename__ = 'gs_gen_machine_names'
    __table_args__ = (
        Index('ix_machine_name_id_machine', 'id_machine'),
        Index('ix_machine_name_year_number', 'year_number'),
        Index('ix_machine_names_machine_year', 'id_machine', 'year_number'),
        version_year_unique_index('uq_machine_names_machine_year_ver', 'id_machine'),
        {"schema": SCHEMA_GENERATION},
    )
    __mapper_args__ = {"confirm_deleted_rows": False}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK -> Year (по полю years.number)
    year_number = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_years.number', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    year = db.relationship('Year', back_populates='machine_names', lazy='noload')

    # FK -> Machine
    id_machine = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_GENERATION}.gs_gen_machines.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    machine_name_rel = db.relationship('Machine', back_populates='machine_names')

    # Текстовое поле названия
    name = db.Column(db.String(1024), nullable=True)

    # timestamps (UTC, server-side)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    def __repr__(self) -> str:
        return f"<MachineName id={self.id} machine_id={self.id_machine} year={self.year_number} name={self.name!r}>"
