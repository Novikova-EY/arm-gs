# -*- coding: utf-8 -*-
"""
CitiesExternalMapping model (справочник "Города" из БД Топливо).
"""

from app.extensions import db
from config import SCHEMA_FUE_EM


class CitiesExternalMapping(db.Model):
    __tablename__ = "gs_fue_em_cities"
    __table_args__ = ({"schema": SCHEMA_FUE_EM},)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Поля из БД Топливо
    code_topl = db.Column(db.Integer, nullable=False, index=True, unique=True)
    name_topl = db.Column(db.String(255), nullable=True)
    naselenie = db.Column(db.Numeric(18, 2), nullable=True)
    gilfond = db.Column(db.Numeric(18, 2), nullable=True)
    obesp_cts = db.Column(db.String(255), nullable=True)
    dprom_ao = db.Column(db.String(255), nullable=True)
    dgkh_ao = db.Column(db.String(255), nullable=True)
    obl = db.Column(db.Integer, nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<CitiesExternalMapping id={self.id} code_topl={self.code_topl!r}>"

