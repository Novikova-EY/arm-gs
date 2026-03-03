# -*- coding: utf-8 -*-
"""
EquipmentGroupExternalMapping model (связь типов групп оборудования с внешними идентификаторами из БД Топливо).
"""

from app.extensions import db
from config import SCHEMA_FUE_EM
from app.common.models.audit_mixin import AuditMixin


class EquipmentGroupExternalMapping(db.Model, AuditMixin):
    __tablename__ = "gs_fue_em_equipment_group"
    __table_args__ = ({"schema": SCHEMA_FUE_EM},)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Стабильный UUID типа группы оборудования для удобной связки
    equipment_group_ref_uuid = db.Column(
        db.String(36),
        nullable=True,
        index=True,
    )

    # Поля из БД Топливо (колонки с суффиксом _topl)
    name_topl = db.Column(db.String(255), nullable=True)
    code = db.Column(db.Integer, nullable=True, unique=True, index=True)
    type_ = db.Column("type", db.Integer, nullable=True)
    tm = db.Column(db.String(255), nullable=True)
    n1 = db.Column(db.Integer, nullable=True)
    n2 = db.Column(db.Integer, nullable=True)
    p1 = db.Column(db.Integer, nullable=True)
    p2 = db.Column(db.Integer, nullable=True)
    gruppa_oborud = db.Column(db.String(255), nullable=True)

    def __repr__(self) -> str:
        return (
            "<EquipmentGroupExternalMapping "
            f"id={self.id} equipment_group_ref_uuid={self.equipment_group_ref_uuid!r} "
            f"code={self.code!r}>"
        )

