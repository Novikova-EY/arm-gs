# -*- coding: utf-8 -*-
"""
BusinessUnitExternalMapping model (связь бизнес единиц с внешними идентификаторами).
"""
from app.extensions import db
from config import SCHEMA_FUE_EM


class BusinessUnitExternalMapping(db.Model):
    __tablename__ = "gs_fue_em_business_unit"
    __table_args__ = ({"schema": SCHEMA_FUE_EM},)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    external_id = db.Column(db.String(80), nullable=False, index=True)
    external_name = db.Column(db.String(255), nullable=True)

    def __repr__(self) -> str:
        return (
            "<BusinessUnitExternalMapping "
            f"id={self.id} external_id={self.external_id!r}>"
        )
