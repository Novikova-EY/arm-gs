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
from app.fuel.models.external_mapping.fue_em_department_model import (
    DepartmentExternalMapping,
)
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

    # Ссылка на год (number из gs_sys_years). Без FK: gs_sys_years.number не уникален (дубли по версиям).
    year_number = db.Column(db.Integer, nullable=True, index=True)

    # Мощность:
    # Суммарная установленная мощность, МВт
    nust = db.Column(db.Numeric(36, 16), nullable=True)
    # Суммарная располагаемая мощность, МВт
    nr = db.Column(db.Numeric(36, 16), nullable=True)

    # ЧЧИУМ, ч (Access H)
    h = db.Column(db.Numeric(36, 16), nullable=True)
    # Признак фиксации ЧЧИУМ (Access HFIX): 1 — не пересчитывать H формулой распределения
    hfix = db.Column(db.Integer, nullable=True)

    # Электроэнергия в тыс.кВтч:
    # Выработка ЭЭ, тыс.кВтч
    e = db.Column(db.Numeric(36, 16), nullable=True)
    # Теплофикационная выработка ЭЭ, тыс.кВтч
    ewtp = db.Column(db.Numeric(36, 16), nullable=True)
    # Отпуск ЭЭ, тыс.кВтч
    eotp = db.Column(db.Numeric(36, 16), nullable=True)
    # УРУТ на отпуск ЭЭ, г у.т./кВтч
    eurt = db.Column(db.Numeric(36, 16), nullable=True)
    # Расх топ ээ
    eust = db.Column(db.Numeric(36, 16), nullable=True)
    # СН на выработку ЭЭ, %
    snk = db.Column(db.Numeric(36, 16), nullable=True)

    # Тепло в Гкал:
    # Отпуск ТЭ, тыс.Гкал
    q = db.Column(db.Numeric(36, 16), nullable=True)
    # Тепловое потребление (отборов турбин), тыс.Гкал
    qotr = db.Column(db.Numeric(36, 16), nullable=True)
    # УРУТ на отпуск ТЭ, кг у.т./⁠Гкал
    turt = db.Column(db.Numeric(36, 16), nullable=True)
    # Расход усл. топлива на ТЭ, тыс. т у.т.
    tust = db.Column(db.Numeric(36, 16), nullable=True)
    # СН, кВтч/⁠Гкал
    sn_t = db.Column(db.Numeric(36, 16), nullable=True)  # SNt
    
    # Расход топлива, всего
    b = db.Column(db.Numeric(36, 16), nullable=True)

    # Расх по типам топлива
    gaz = db.Column(db.Numeric(36, 16), nullable=True)
    isk_gaz = db.Column(db.Numeric(36, 16), nullable=True)
    mazut = db.Column(db.Numeric(36, 16), nullable=True)
    torf = db.Column(db.Numeric(36, 16), nullable=True)
    slan = db.Column(db.Numeric(36, 16), nullable=True)
    proch = db.Column(db.Numeric(36, 16), nullable=True)
    ugol = db.Column(db.Numeric(36, 16), nullable=True)
    don = db.Column(db.Numeric(36, 16), nullable=True)
    podm = db.Column(db.Numeric(36, 16), nullable=True)
    pech = db.Column(db.Numeric(36, 16), nullable=True)
    arkt = db.Column(db.Numeric(36, 16), nullable=True)
    kuzn = db.Column(db.Numeric(36, 16), nullable=True)
    ural = db.Column(db.Numeric(36, 16), nullable=True)
    bashk = db.Column(db.Numeric(36, 16), nullable=True)
    kazah = db.Column(db.Numeric(36, 16), nullable=True)
    kan = db.Column(db.Numeric(36, 16), nullable=True)
    tung = db.Column(db.Numeric(36, 16), nullable=True)
    irkut = db.Column(db.Numeric(36, 16), nullable=True)
    hak = db.Column(db.Numeric(36, 16), nullable=True)
    tuv = db.Column(db.Numeric(36, 16), nullable=True)
    bur = db.Column(db.Numeric(36, 16), nullable=True)
    chit = db.Column(db.Numeric(36, 16), nullable=True)
    yakut = db.Column(db.Numeric(36, 16), nullable=True)
    amur = db.Column(db.Numeric(36, 16), nullable=True)
    urg = db.Column(db.Numeric(36, 16), nullable=True)
    ushum = db.Column(db.Numeric(36, 16), nullable=True)
    prim = db.Column(db.Numeric(36, 16), nullable=True)
    mag = db.Column(db.Numeric(36, 16), nullable=True)
    chukot = db.Column(db.Numeric(36, 16), nullable=True)
    kamch = db.Column(db.Numeric(36, 16), nullable=True)
    sah = db.Column(db.Numeric(36, 16), nullable=True)

    
    # Тепловая мощность отборов, Гкал/ч
    nt = db.Column(db.Numeric(36, 16), nullable=True)
    
    # Сумма тепловых мощностей, Гкал/ч
    nt_sum = db.Column(db.Numeric(36, 16), nullable=True)  # NTsum
    
    # Код группы оборудования
    numb1120 = db.Column(db.Integer, nullable=True)
    numb1 = db.Column(db.Integer, nullable=True)

    # FK -> EquipmentGroupExternalMapping.code
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
    # FK -> TerritoriesEnergyExternalMapping.external_id
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
    # FK -> DepartmentExternalMapping.external_id
    dep = db.Column(
        db.String(80),
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_department.external_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    dep_department_mapping = db.relationship(
        "DepartmentExternalMapping",
        foreign_keys=[dep],
        primaryjoin=cast(dep, String(80)) == foreign(DepartmentExternalMapping.external_id),
        uselist=False,
        lazy="select",
    )
    # FK -> UnionEnergySystemExternalMapping.external_id
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
    # FK -> EconomicRegionExternalMapping.external_id
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
    # FK -> GenCompanyExternalMapping.external_id
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
    # FK -> BusinessUnitExternalMapping.external_id
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

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Подписи nust/nr/h для шапок (код поля — отдельно в скобках).
    NUST_COLUMN_LABEL = "Суммарная установленная мощность, МВт"
    NR_COLUMN_LABEL = "Суммарная располагаемая мощность, МВт"
    H_COLUMN_LABEL = "ЧЧИУМ, ч"
    # Подпись hfix для шапок (код Access HFIX — через fuel_header_access_codes).
    HFIX_COLUMN_LABEL = "Признак фиксации ЧЧИУМ"
    # Подпись eust для шапок («топлива на ЭЭ» непереносимо).
    EUST_COLUMN_LABEL = "Расход топлива на ЭЭ, тут/⁠тыс.кВтч"
    # Подпись eotp для шапок (неразрывный пробел между «Отпуск» и «ЭЭ»).
    EOTP_COLUMN_LABEL = "Отпуск ЭЭ, тыс.кВтч"
    # Подпись eurt для шапок (неразрывный пробел между «отпуск» и «ЭЭ»,
    # между «г» и «у.т.»).
    EURT_COLUMN_LABEL = "УРУТ на отпуск ЭЭ, г у.т./кВтч"
    # Подпись q для шапок (неразрывный пробел между «Отпуск» и «ТЭ»).
    Q_COLUMN_LABEL = "Отпуск ТЭ, тыс.Гкал"
    # Подпись turt для шапок (неразрывный пробел между «отпуск» и «ТЭ»;
    # «кг у.т./Гкал» целиком непереносимо).
    TURT_COLUMN_LABEL = "УРУТ на отпуск ТЭ, кг у.т./⁠Гкал"
    # Подпись tust для шапок («усл. топлива» и «на ТЭ» непереносимо;
    # «тыс. т у.т.» целиком непереносимо).
    TUST_COLUMN_LABEL = "Расход усл. топлива на ТЭ, тыс. т у.т."
    # Подпись nt для шапок (код поля — отдельно в скобках).
    NT_COLUMN_LABEL = "Тепловая мощность отборов, Гкал/ч"
    # Подпись nt_sum для шапок (код поля — отдельно в скобках).
    NT_SUM_COLUMN_LABEL = "Сумма тепловых мощностей, Гкал/ч"

    def __repr__(self) -> str:
        return (
            f"<EquipmentGroupFuelParam id={self.id} "
            f"equipment_group_id={self.equipment_group_id}>"
        )
