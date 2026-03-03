# -*- coding: utf-8 -*-
"""
GenCompanyExternalMapping model (связь генерирующих компаний с внешними идентификаторами).
"""
from app.extensions import db
from config import SCHEMA_FUE_EM
from app.common.models.audit_mixin import AuditMixin


class GenCompanyExternalMapping(db.Model, AuditMixin):
    __tablename__ = "gs_fue_em_gen_company"
    __table_args__ = ({"schema": SCHEMA_FUE_EM},)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Стабильный UUID генерирующей компании для удобной связки
    gen_company_ref_uuid = db.Column(
        db.String(36),
        nullable=True,
        index=True,
    )

    external_id = db.Column(db.String(80), nullable=True, index=True, unique=True)
    external_name = db.Column(db.String(255), nullable=True)
    external_name1 = db.Column(db.String(255), nullable=True)

    def __repr__(self) -> str:
        return (
            "<GenCompanyExternalMapping "
            f"id={self.id} gen_company_ref_uuid={self.gen_company_ref_uuid!r} "
            f"external_id={self.external_id!r}>"
        )
