# -*- coding: utf-8 -*-
"""
EquipmentGroupSet model (link между итоговой группой и связкой станция+тип).
"""
from sqlalchemy import UniqueConstraint
from sqlalchemy.sql import func

from app.extensions import db
from config import SCHEMA_FUEL


class EquipmentGroupSet(db.Model):
    __tablename__ = "gs_fue_equipment_group_sets"
    __table_args__ = (
        UniqueConstraint(
            "equipment_group_id",
            "equipment_group_set_station_id",
            name="uq_equipment_group_set_link",
        ),
        {"schema": SCHEMA_FUEL},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK -> EquipmentGroup (итоговая группа)
    equipment_group_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_FUEL}.gs_fue_equipment_groups.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    equipment_group = db.relationship(
        "EquipmentGroup",
        backref="equipment_group_links_v2",
    )

    # FK -> EquipmentGroupSetStation (тип группы оборудования на станции)
    equipment_group_set_station_id = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_FUEL}.gs_fue_equipment_group_type_stations.id", ondelete="RESTRICT"
        ),
        nullable=False,
        index=True,
    )
    equipment_group_set_station = db.relationship(
        "EquipmentGroupSetStation",
        backref="equipment_group_links_v2",
    )

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            "<EquipmentGroupSet "
            f"id={self.id} equipment_group_id={self.equipment_group_id} "
            f"equipment_group_set_station_id={self.equipment_group_set_station_id}>"
        )
