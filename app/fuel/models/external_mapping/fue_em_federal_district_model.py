# -*- coding: utf-8 -*-
"""
FederalDistrictExternalMapping model (связь ФО с внешними идентификаторами).
"""
from app.extensions import db
from config import SCHEMA_FUE_EM


class FederalDistrictExternalMapping(db.Model):
    __tablename__ = "gs_fue_em_federal_district"
    __table_args__ = ({"schema": SCHEMA_FUE_EM},)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Стабильный UUID ФО для удобной связки
    federal_district_ref_uuid = db.Column(
        db.String(36),
        nullable=True,
        index=True,
    )

    external_id = db.Column(db.String(80), nullable=True, index=True, unique=True)
    external_name = db.Column(db.String(255), nullable=True)

    def __repr__(self) -> str:
        return (
            "<FederalDistrictExternalMapping "
            f"id={self.id} fd_ref_uuid={self.federal_district_ref_uuid!r} "
            f"external_id={self.external_id!r}>"
        )
