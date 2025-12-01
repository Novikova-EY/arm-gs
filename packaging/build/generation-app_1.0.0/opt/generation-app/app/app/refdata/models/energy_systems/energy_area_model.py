# -*- coding: utf-8 -*-
"""
EnergyArea model (Энергорайон).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA, SCHEMA_GENERATION


class EnergyArea(db.Model):
    __tablename__ = 'energy_areas'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(256), nullable=False, index=True)

    # FK -> RegionalDistrict (обязательный)
    id_regional_district = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.regional_districts.id', ondelete='RESTRICT'),
        index=True,
        nullable=False
    )
    regional_district = db.relationship('RegionalDistrict', back_populates='energy_areas')

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    __table_args__ = (
        db.UniqueConstraint('database_version_id', 'name', name='uq_refdata_energy_areas_ver_name'),
        {"schema": SCHEMA_REFDATA},
    )

    # связь с агрегатами (Machine)
    machines = db.relationship('Machine', back_populates='energy_area')

    # --- ВЫЧИСЛЯЕМЫЕ СВОЙСТВА ---

    @property
    def regional_energy_systems(self):
        """
        Список РЭС, связанных с субъектом РФ этого энергорайона.
        Может быть пустым или содержать несколько элементов.
        """
        rd = self.regional_district
        return rd.regional_energy_systems if rd else []

    @property
    def regional_energy_system(self):
        """
        Удобное «одиночное» представление РЭС:
        - Если ровно одна РЭС у субъекта — вернем ее.
        - Иначе None (чтобы не навязывать произвольный выбор).
        """
        ress = self.regional_energy_systems
        return ress[0] if len(ress) == 1 else None

    @property
    def union_energy_systems(self):
        """
        Множество ОЭС, соответствующих всем РЭС субъекта (set).
        """
        return {res.union_energy_system for res in self.regional_energy_systems if res.union_energy_system}

    @property
    def union_energy_system(self):
        """
        Удобное «одиночное» представление ОЭС:
        - Если все РЭС субъекта относятся к одной и той же ОЭС — вернем ее.
        - Иначе None.
        """
        ues = {res.union_energy_system for res in self.regional_energy_systems if res.union_energy_system}
        return next(iter(ues)) if len(ues) == 1 else None

    def __repr__(self) -> str:
        return f"<EnergyArea id={self.id} name={self.name!r}>"
