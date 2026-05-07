# -*- coding: utf-8 -*-
"""
EquipmentGroupSetStation model (привязка типа группы оборудования к электростанции).
"""
from sqlalchemy import UniqueConstraint
from sqlalchemy.sql import func

from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_GENERATION, SCHEMA_REFDATA


class EquipmentGroupSetStation(db.Model):
    __tablename__ = "gs_fue_equipment_group_type_stations"
    __table_args__ = (
        UniqueConstraint(
            "station_id",
            "equipment_group_type_id",
            "database_version_id",
            name="uq_eq_group_type_station_version",
        ),
        {"schema": SCHEMA_FUEL},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK -> Station
    station_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.gs_gen_stations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    station = db.relationship("Station", back_populates="equipment_group_type_links_v2")

    # FK -> EquipmentGroupType
    equipment_group_type_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_equipment_groups.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    equipment_group_type = db.relationship(
        "EquipmentGroupType",
        backref="equipment_group_type_station_links_v2",
    )

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            "<EquipmentGroupSetStation "
            f"id={self.id} station_id={self.station_id} equipment_group_type_id={self.equipment_group_type_id}>"
        )
