# -*- coding: utf-8 -*-
"""
PGUMachineName model (Название компонента ПГУ по годам).
- По аналогии с MachineName: year (Year), pgu_machine (PGUMachine).
- Текстовое поле name вместо ссылки на справочник.
"""
from sqlalchemy.sql import func
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin
from app.generation.models.common.version_year_unique_index import version_year_unique_index


class PGUMachineName(db.Model, AuditMixin):
    __tablename__ = 'gs_gen_pgu_machine_names'
    __table_args__ = (
        Index('ix_pgu_machine_name_id_pgu_machine', 'id_pgu_machine'),
        Index('ix_pgu_machine_name_year_number', 'year_number'),
        Index('ix_pgu_machine_names_pgu_machine_year', 'id_pgu_machine', 'year_number'),
        version_year_unique_index('uq_pgu_machine_names_machine_year_ver', 'id_pgu_machine'),
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
    year = db.relationship('Year', back_populates='pgu_machine_names', lazy='noload')

    # FK -> PGUMachine
    id_pgu_machine = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_GENERATION}.gs_gen_pgu_machines.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    pgu_machine_name_rel = db.relationship('PGUMachine', back_populates='pgu_machine_names')

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
        return f"<PGUMachineName id={self.id} pgu_machine_id={self.id_pgu_machine} year={self.year_number} name={self.name!r}>"
