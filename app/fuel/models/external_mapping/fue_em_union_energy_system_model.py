# -*- coding: utf-8 -*-
"""
UnionEnergySystemExternalMapping model (связь ОЭС с внешними идентификаторами).
"""
from app.extensions import db
from config import SCHEMA_FUE_EM
from app.common.models.audit_mixin import AuditMixin


class UnionEnergySystemExternalMapping(db.Model, AuditMixin):
    __tablename__ = "gs_fue_em_union_energy_system"
    __table_args__ = ({"schema": SCHEMA_FUE_EM},)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Стабильный UUID ОЭС для удобной связки
    union_energy_system_ref_uuid = db.Column(
        db.String(36),
        nullable=True,
        index=True,
    )

    external_id = db.Column(db.String(80), nullable=True, index=True, unique=True)
    external_name = db.Column(db.String(255), nullable=True)
    external_nameoes = db.Column(db.String(255), nullable=True)
    external_abbr = db.Column(db.String(255), nullable=True)

    def __repr__(self) -> str:
        return (
            "<UnionEnergySystemExternalMapping "
            f"id={self.id} ues_ref_uuid={self.union_energy_system_ref_uuid!r} "
            f"external_id={self.external_id!r}>"
        )
