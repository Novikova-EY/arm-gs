# -*- coding: utf-8 -*-
"""
CitiesExternalMapping model (справочник "Города" из БД Топливо).
"""

from app.extensions import db
from config import SCHEMA_FUE_EM
from app.common.models.audit_mixin import AuditMixin


class CitiesExternalMapping(db.Model, AuditMixin):
    __tablename__ = "gs_fue_em_cities"
    __table_args__ = ({"schema": SCHEMA_FUE_EM},)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Поля из БД Топливо
    code = db.Column(db.Integer, nullable=False, index=True, unique=True)
    name = db.Column(db.String(255), nullable=True)
    naselenie = db.Column(db.Numeric(18, 2), nullable=True)
    gilfond = db.Column(db.Numeric(18, 2), nullable=True)
    obesp_cts = db.Column(db.String(255), nullable=True)
    dprom_ao = db.Column(db.Integer, nullable=True)
    dgkh_ao = db.Column(db.Integer, nullable=True)
    obl = db.Column(db.Integer, nullable=True, index=True)

    # Связь obl -> TerritoriesEnergyExternalMapping.obl (оба Integer)
    territories_energy = db.relationship(
        "TerritoriesEnergyExternalMapping",
        primaryjoin="CitiesExternalMapping.obl == TerritoriesEnergyExternalMapping.obl",
        foreign_keys="[TerritoriesEnergyExternalMapping.obl]",
        lazy="joined",
        viewonly=True,
        uselist=False,
    )

    def __repr__(self) -> str:
        return f"<CitiesExternalMapping id={self.id} code={self.code!r}>"

