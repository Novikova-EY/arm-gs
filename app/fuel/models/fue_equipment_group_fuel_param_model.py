# -*- coding: utf-8 -*-
"""
EquipmentGroupFuelParam model — топливные параметры для группы оборудования.
Схема gs_fue, одна группа может иметь несколько записей параметров по годам (по year_number).
"""
from sqlalchemy import UniqueConstraint, cast
from sqlalchemy.orm import foreign
from sqlalchemy.sql import func
from sqlalchemy.types import String
from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_REFDATA, SCHEMA_FUE_EM
from app.fuel.models.external_mapping.fue_em_territories_energy_model import (
    TerritoriesEnergyExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_union_energy_system_model import (
    UnionEnergySystemExternalMapping,
)
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.territories.regional_district_model import RegionalDistrict


class EquipmentGroupFuelParam(db.Model):
    """
    Топливные параметры группы оборудования.
    Одна запись на одну группу оборудования (EquipmentGroup) и один год (year_number).
    """
    __tablename__ = "gs_fue_equipment_group_fuel_param"
    __table_args__ = (
        UniqueConstraint(
            "equipment_group_id",
            "year_number",
            name="uq_equipment_group_fuel_param_group_year",
        ),
        {"schema": SCHEMA_FUEL},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK -> EquipmentGroup (итоговая группа оборудования)
    equipment_group_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_FUEL}.gs_fue_equipment_groups.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    equipment_group = db.relationship(
        "EquipmentGroup",
        backref="fuel_params",
        foreign_keys=[equipment_group_id],
        uselist=False,
        lazy="select",
    )

    # Наименование группы оборудования
    name = db.Column(db.String(512), nullable=True)

    # Ссылка на год (number из gs_years). Без FK: gs_years.number не уникален (дубли по версиям).
    year_number = db.Column(db.Integer, nullable=True, index=True)

    # Мощность:
    # Руст
    nust = db.Column(db.Numeric(20, 6), nullable=True)
    # Ррасп
    nr = db.Column(db.Numeric(20, 6), nullable=True)

    # Электроэнергия в тыс.кВтч:
    # Выр
    e = db.Column(db.Numeric(20, 6), nullable=True)
    # Этц
    ewtp = db.Column(db.Numeric(20, 6), nullable=True)
    # Отпуск
    eotp = db.Column(db.Numeric(20, 6), nullable=True)
    # Уд.расх
    eurt = db.Column(db.Numeric(20, 6), nullable=True)
    # Расх топ ээ
    eust = db.Column(db.Numeric(20, 6), nullable=True)
    # СН, %
    snk = db.Column(db.Numeric(20, 6), nullable=True)

    # Тепло в Гкал:
    # Отпуск, Гкал
    q = db.Column(db.Numeric(20, 6), nullable=True)
    # Отраб
    qotr = db.Column(db.Numeric(20, 6), nullable=True)
    # Уд.расх
    turt = db.Column(db.Numeric(20, 6), nullable=True)
    # Расх топ тэ
    tust = db.Column(db.Numeric(20, 6), nullable=True)
    # СН, кВтч/Гкал
    sn_t = db.Column(db.Numeric(20, 6), nullable=True)  # SNt
    
    # Расх топл. 
    b = db.Column(db.Numeric(20, 6), nullable=True)

    # Расх по типам топлива
    gaz = db.Column(db.Numeric(20, 6), nullable=True)
    isk_gaz = db.Column(db.Numeric(20, 6), nullable=True)
    mazut = db.Column(db.Numeric(20, 6), nullable=True)
    torf = db.Column(db.Numeric(20, 6), nullable=True)
    slan = db.Column(db.Numeric(20, 6), nullable=True)
    proch = db.Column(db.Numeric(20, 6), nullable=True)
    ugol = db.Column(db.Numeric(20, 6), nullable=True)
    don = db.Column(db.Numeric(20, 6), nullable=True)
    podm = db.Column(db.Numeric(20, 6), nullable=True)
    pech = db.Column(db.Numeric(20, 6), nullable=True)
    arkt = db.Column(db.Numeric(20, 6), nullable=True)
    kuzn = db.Column(db.Numeric(20, 6), nullable=True)
    ural = db.Column(db.Numeric(20, 6), nullable=True)
    bashk = db.Column(db.Numeric(20, 6), nullable=True)
    kazah = db.Column(db.Numeric(20, 6), nullable=True)
    kan = db.Column(db.Numeric(20, 6), nullable=True)
    tung = db.Column(db.Numeric(20, 6), nullable=True)
    irkut = db.Column(db.Numeric(20, 6), nullable=True)
    hak = db.Column(db.Numeric(20, 6), nullable=True)
    tuv = db.Column(db.Numeric(20, 6), nullable=True)
    bur = db.Column(db.Numeric(20, 6), nullable=True)
    chit = db.Column(db.Numeric(20, 6), nullable=True)
    yakut = db.Column(db.Numeric(20, 6), nullable=True)
    amur = db.Column(db.Numeric(20, 6), nullable=True)
    urg = db.Column(db.Numeric(20, 6), nullable=True)
    ushum = db.Column(db.Numeric(20, 6), nullable=True)
    prim = db.Column(db.Numeric(20, 6), nullable=True)
    mag = db.Column(db.Numeric(20, 6), nullable=True)
    chukot = db.Column(db.Numeric(20, 6), nullable=True)
    kamch = db.Column(db.Numeric(20, 6), nullable=True)
    sah = db.Column(db.Numeric(20, 6), nullable=True)

    
    # 
    nt = db.Column(db.Numeric(20, 6), nullable=True)
    # 
    nt_sum = db.Column(db.Numeric(20, 6), nullable=True)  # NTsum
    
    numb1120 = db.Column(db.Integer, nullable=True)
    numb1 = db.Column(db.Integer, nullable=True)

    # obor — FK -> EquipmentGroupExternalMapping.code
    obor = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_equipment_group.code", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    obor_equipment_group_mapping = db.relationship(
        "EquipmentGroupExternalMapping",
        foreign_keys=[obor],
        uselist=False,
        lazy="select",
    )
    ved = db.Column(db.Integer, nullable=True)
    ved_cyrillic = db.Column(db.Integer, nullable=True, name="вед")  # вед
    # obl — FK -> TerritoriesEnergyExternalMapping.external_id
    obl = db.Column(
        db.String(80),
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_territories_energy.external_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    obl_territories_energy = db.relationship(
        "TerritoriesEnergyExternalMapping",
        foreign_keys=[obl],
        primaryjoin=cast(obl, String(80)) == foreign(TerritoriesEnergyExternalMapping.external_id),
        uselist=False,
        lazy="select",
    )
    # dep — FK -> DepartmentExternalMapping.external_id
    dep = db.Column(
        db.String(80),
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_department.external_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    dep_department_mapping = db.relationship(
        "DepartmentExternalMapping",
        foreign_keys=[dep],
        uselist=False,
        lazy="select",
    )
    # oes — FK -> UnionEnergySystemExternalMapping.external_id
    oes = db.Column(
        db.String(80),
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_union_energy_system.external_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    oes_union_energy_system_mapping = db.relationship(
        "UnionEnergySystemExternalMapping",
        foreign_keys=[oes],
        primaryjoin=cast(oes, String(80)) == foreign(UnionEnergySystemExternalMapping.external_id),
        uselist=False,
        lazy="select",
    )

    @property
    def regional_district(self):
        """Субъект РФ через obl_territories_energy.regional_district_ref_uuid -> RegionalDistrict.ref_uuid."""
        tm = self.obl_territories_energy
        if tm is None or tm.regional_district_ref_uuid is None:
            return None
        q = RegionalDistrict.query.filter(
            RegionalDistrict.ref_uuid == tm.regional_district_ref_uuid
        )
        if self.database_version_id is not None:
            q = q.filter(RegionalDistrict.database_version_id == self.database_version_id)
        return q.first()

    @property
    def regional_energy_system(self):
        """РЭС через obl_territories_energy.regional_energy_system_ref_uuid -> RegionalEnergySystem.ref_uuid."""
        tm = self.obl_territories_energy
        if tm is None or tm.regional_energy_system_ref_uuid is None:
            return None
        q = RegionalEnergySystem.query.filter(
            RegionalEnergySystem.ref_uuid == tm.regional_energy_system_ref_uuid
        )
        if self.database_version_id is not None:
            q = q.filter(RegionalEnergySystem.database_version_id == self.database_version_id)
        return q.first()

    @property
    def union_energy_system(self):
        """ОЭС через oes_union_energy_system_mapping.union_energy_system_ref_uuid -> UnionEnergySystem.ref_uuid."""
        uem = self.oes_union_energy_system_mapping
        if uem is None or uem.union_energy_system_ref_uuid is None:
            return None
        q = UnionEnergySystem.query.filter(
            UnionEnergySystem.ref_uuid == uem.union_energy_system_ref_uuid
        )
        if self.database_version_id is not None:
            q = q.filter(UnionEnergySystem.database_version_id == self.database_version_id)
        return q.first()

    @property
    def energy_system_type_id(self):
        """ID типа энергосистемы (EST) через union_energy_system.id_energy_system_type."""
        ues = self.union_energy_system
        return ues.id_energy_system_type if ues else None

    ees = db.Column(db.Integer, nullable=True)
    # er — FK -> EconomicRegionExternalMapping.external_id
    er = db.Column(
        db.String(80),
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_economic_region.external_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    er_economic_region_mapping = db.relationship(
        "EconomicRegionExternalMapping",
        foreign_keys=[er],
        primaryjoin="EquipmentGroupFuelParam.er == foreign(EconomicRegionExternalMapping.external_id)",
        uselist=False,
        lazy="select",
    )
    # gk — FK -> GenCompanyExternalMapping.external_id
    gk = db.Column(
        db.String(80),
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_gen_company.external_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    gk_gen_company_mapping = db.relationship(
        "GenCompanyExternalMapping",
        foreign_keys=[gk],
        uselist=False,
        lazy="select",
    )
    # be — FK -> BusinessUnitExternalMapping.external_id
    be = db.Column(
        db.String(80),
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_business_unit.external_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    be_business_unit_mapping = db.relationship(
        "BusinessUnitExternalMapping",
        foreign_keys=[be],
        uselist=False,
        lazy="select",
    )

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # timestamps (UTC, server-side)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<EquipmentGroupFuelParam id={self.id} "
            f"equipment_group_id={self.equipment_group_id}>"
        )
