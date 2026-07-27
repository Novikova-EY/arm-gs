# -*- coding: utf-8 -*-
"""
Fuel model (Вид топлива).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin
from app.refdata.models.refdata_uuid_mixin import RefdataUuidMixin


class Fuel(db.Model, AuditMixin, VersionedModelMixin, RefdataUuidMixin):
    __tablename__ = 'gs_sys_fuels'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)

    # Код вида топлива из Excel «Состав видов топлива» (столбец Kod)
    kod = db.Column(db.Integer, nullable=True, index=True)

    # Название вида топлива из базы Топливо
    nazvl = db.Column(db.String(80), nullable=True)

    # Название типа угольного топлива из базы Топливо (каменный/бурый)
    kmbur = db.Column(db.String(80), nullable=True)

    # FK -> Fuel (родительский вид в иерархии состава)
    parent_id = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_fuels.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    parent = db.relationship(
        'Fuel',
        remote_side=[id],
        backref=db.backref('children', lazy='dynamic'),
        foreign_keys=[parent_id],
    )

    # FK -> FuelType
    id_fuel_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_fuel_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True
    )
    fuel_type = db.relationship('FuelType', back_populates='fuels')

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # связь с таблицей топлив агрегатов  электростанции
    machine_fuels = db.relationship('MachineFuel', back_populates='fuel')

    def __repr__(self) -> str:
        return (
            f"<Fuel id={self.id} name={self.name!r} kod={self.kod} "
            f"type_id={self.id_fuel_type} parent_id={self.parent_id}>"
        )
