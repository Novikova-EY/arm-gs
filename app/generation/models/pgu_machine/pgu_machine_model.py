# -*- coding: utf-8 -*-
"""
PGUMachine model (Компонент ПГУ).
- Сохранены все исходные связи и индексы, включая каскады к родительской Machine.
"""
from sqlalchemy.sql import func
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA

class PGUMachine(db.Model):
    __tablename__ = 'pgu_machines'
    __table_args__ = (
        Index('ix_pgu_machine_id_parent_machine', 'id_parent_machine'),
        Index('ix_pgu_machine_id_tes_machine_type', 'id_tes_machine_type'),
        Index('ix_pgu_machine_id_equipment_group_pgu', 'id_equipment_group_pgu'),
        Index('ix_pgu_machine_id_condition_type', 'id_condition_type'),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_ti = db.Column(db.Integer, nullable=True)

    # FK -> EquipmentGroup (ПГУ)
    id_equipment_group_pgu = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.equipment_groups.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    equipment_group_pgu = db.relationship('EquipmentGroup', back_populates='pgu_machines')

    # FK -> ConditionType
    id_condition_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.condition_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    condition_type = db.relationship('ConditionType', back_populates='pgu_machines')

    # FK -> Machine (родитель)
    id_parent_machine = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_GENERATION}.machines.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    parent_machine = db.relationship('Machine', backref=db.backref('pgu_submachines', cascade='all, delete-orphan'))

    machine_number = db.Column(db.String(80), nullable=True, index=True)
    machine_name = db.Column(db.String(255), nullable=False, index=True)

    # FK -> TesMachineType
    id_tes_machine_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.tes_machine_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    tes_machine_type = db.relationship('TesMachineType', backref='pgu_machines')

    # FK -> PGUTesMachineType (ГТ/ПТ)
    id_pgu_tes_machine_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.pgu_tes_machine_types.id'),
        nullable=True,
        index=True,
    )
    pgu_tes_machine_type = db.relationship('PGUTesMachineType', back_populates='pgu_machines')

    # Children: powers
    pgu_machine_powers = db.relationship(
        'PGUMachinePower',
        back_populates='pgu_machine',
        cascade="all, delete-orphan",
        foreign_keys='PGUMachinePower.id_pgu_machine',
    )

    # Даты/поля как в исходнике
    date_exploitation = db.Column(db.Integer, nullable=True)
    date_commission_fact = db.Column(db.String(10), nullable=True)
    date_joining_expected = db.Column(db.String(10), nullable=True)
    date_joining_fact = db.Column(db.String(10), nullable=True)
    date_detatchment_fact = db.Column(db.String(10), nullable=True)
    date_decompressing_expected = db.Column(db.Integer, nullable=True)
    date_decompressing_fact = db.Column(db.String(10), nullable=True)
    date_modernization_expected = db.Column(db.Integer, nullable=True)
    date_relabing_fact = db.Column(db.String(10), nullable=True)
    date_update_fact = db.Column(db.String(10), nullable=True)
    note = db.Column(db.String(512), nullable=True)
    year_modern = db.Column(db.String(10), nullable=True)
    year_demontaz = db.Column(db.String(10), nullable=True)
    resurs_gas = db.Column(db.String(10), nullable=True)

    # timestamps (UTC, server-side)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return f"<PGUMachine id={self.id} name={self.machine_name!r} parent_id={self.id_parent_machine}>"
