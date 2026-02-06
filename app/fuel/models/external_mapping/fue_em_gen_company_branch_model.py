# -*- coding: utf-8 -*-
"""
GenCompanyBranchExternalMapping model (связь филиалов генерирующих компаний с внешними идентификаторами).

Ожидаемые поля загрузки: code_topl, name_topl, name.
Поле `name` используется для поиска и сопоставления с GenCompany.name.
"""

from app.extensions import db
from config import SCHEMA_FUE_EM


class GenCompanyBranchExternalMapping(db.Model):
    __tablename__ = "gs_fue_em_gen_company_branch"
    __table_args__ = ({"schema": SCHEMA_FUE_EM},)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # UUID генерирующей компании (поиск/сопоставление по полю name из Excel)
    gen_company_ref_uuid = db.Column(db.String(36), nullable=True, index=True)

    # Данные из БД Топливо (филиалы)
    external_id = db.Column(db.String(80), nullable=True, index=True)
    external_name = db.Column(db.String(255), nullable=True)

    # Наименование из Excel, по которому ищем GenCompany.name
    local_name = db.Column(db.String(255), nullable=True)

    def __repr__(self) -> str:
        return (
            "<GenCompanyBranchExternalMapping "
            f"id={self.id} gen_company_ref_uuid={self.gen_company_ref_uuid!r} "
            f"external_id={self.external_id!r}>"
        )

