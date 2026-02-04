# -*- coding: utf-8 -*-
"""
DepartmentExternalMapping model (связь департаментов с внешними идентификаторами).
"""
from app.extensions import db
from config import SCHEMA_FUE_EM


class DepartmentExternalMapping(db.Model):
    __tablename__ = "gs_fue_em_department"
    __table_args__ = ({"schema": SCHEMA_FUE_EM},)

    external_id = db.Column(db.String(80), primary_key=True, nullable=False)
    external_name = db.Column(db.String(255), nullable=True)

    def __repr__(self) -> str:
        return (
            "<DepartmentExternalMapping "
            f"external_id={self.external_id!r} external_name={self.external_name!r}>"
        )
