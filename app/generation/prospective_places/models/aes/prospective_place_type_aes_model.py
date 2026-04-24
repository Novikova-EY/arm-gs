# -*- coding: utf-8 -*-
"""
ProspectivePlaceTypeAES — тип перспективной площадки АЭС (справочник refdata).

Таблица gs_gen_gs_prospective_place_types. Только для MachineProspectivePlaceAES.
Для ГЭС см. ProspectivePlaceTypeGES.
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin


class ProspectivePlaceTypeAES(db.Model, AuditMixin):
    """Справочник типов перспективной площадки АЭС."""

    __tablename__ = "gs_gen_gs_prospective_place_types"
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, unique=True, nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    machine_prospective_places = db.relationship(
        "MachineProspectivePlaceAES",
        back_populates="prospective_place_type",
        primaryjoin="ProspectivePlaceTypeAES.id == MachineProspectivePlaceAES.id_prospective_place_type",
    )

    def __repr__(self) -> str:
        return f"<ProspectivePlaceTypeAES id={self.id} name={self.name!r}>"
