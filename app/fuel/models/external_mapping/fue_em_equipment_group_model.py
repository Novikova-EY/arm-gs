# -*- coding: utf-8 -*-
"""
EquipmentGroupExternalMapping model (связь типов групп оборудования с внешними идентификаторами из БД Топливо).
"""

from app.extensions import db
from config import SCHEMA_FUE_EM


class EquipmentGroupExternalMapping(db.Model):
    __tablename__ = "gs_fue_em_equipment_group"
    __table_args__ = ({"schema": SCHEMA_FUE_EM},)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Стабильный UUID типа группы оборудования для удобной связки
    equipment_group_ref_uuid = db.Column(
        db.String(36),
        nullable=True,
        index=True,
    )

    # Поля из БД Топливо
    name_topl = db.Column(db.String(255), nullable=True)
    code_topl = db.Column(db.Integer, nullable=True, index=True)
    type_topl = db.Column(db.Integer, nullable=True)
    tm_topl = db.Column(db.String(255), nullable=True)
    n1_topl = db.Column(db.Integer, nullable=True)
    n2_topl = db.Column(db.Integer, nullable=True)
    p1_topl = db.Column(db.Integer, nullable=True)
    p2_topl = db.Column(db.Integer, nullable=True)
    gruppa_oborud_topl = db.Column(db.String(255), nullable=True)

    def __repr__(self) -> str:
        return (
            "<EquipmentGroupExternalMapping "
            f"id={self.id} equipment_group_ref_uuid={self.equipment_group_ref_uuid!r} "
            f"code_topl={self.code_topl!r}>"
        )

