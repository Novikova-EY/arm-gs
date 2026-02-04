# -*- coding: utf-8 -*-
"""
EquipmentGroupSetStation model (связь many-to-many между группой и станциями).
"""
from sqlalchemy import UniqueConstraint
from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.versioned_model import VersionedModelMixin


class EquipmentGroupSetStation(db.Model, VersionedModelMixin):
    __tablename__ = "gs_fue_equipment_group_set_stations"
    __table_args__ = (
        UniqueConstraint(
            "equipment_group_set_id",
            "station_id",
            name="uq_equipment_group_set_stations_set_station",
        ),
        {"schema": SCHEMA_FUEL},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK -> EquipmentGroupSet
    equipment_group_set_id = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_FUEL}.gs_fue_equipment_group_sets.id", ondelete="RESTRICT"
        ),
        nullable=False,
        index=True,
    )
    equipment_group_set = db.relationship("EquipmentGroupSet", back_populates="station_links")

    # FK -> Station
    station_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.stations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    station = db.relationship("Station", back_populates="equipment_group_set_links")

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<EquipmentGroupSetStation id={self.id} set_id={self.equipment_group_set_id} station_id={self.station_id}>"
