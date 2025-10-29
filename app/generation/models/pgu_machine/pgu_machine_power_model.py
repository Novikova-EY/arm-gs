# -*- coding: utf-8 -*-
"""
PGUMachinePower model (Мощности ПГУ-компонентов).
- Связи сохранены: year (Year.pgu_machine_powers via backref), pgu_machine (PGUMachine.pgu_machine_powers).
"""
from sqlalchemy.sql import func
from sqlalchemy import Numeric
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA

class PGUMachinePower(db.Model):
    __tablename__ = 'pgu_machine_powers'
    __table_args__ = (
        Index('ix_pgu_machine_power_id_pgu_machine', 'id_pgu_machine'),
        Index('ix_pgu_machine_power_year_number', 'year_number'),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK -> Year (по полю years.number)
    year_number = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.years.number', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    year = db.relationship('Year', backref='pgu_machine_powers')

    # FK -> PGUMachine
    id_pgu_machine = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_GENERATION}.pgu_machines.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
    )
    pgu_machine = db.relationship('PGUMachine', back_populates='pgu_machine_powers')

    # Установленная мощность (по году)
    p_ust = db.Column(Numeric(25, 15), nullable=True)

    # timestamps (UTC, server-side)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    def __repr__(self) -> str:
        return f"<PGUMachinePower id={self.id} pgu_machine_id={self.id_pgu_machine} year={self.year_number} p_ust={self.p_ust}>"
