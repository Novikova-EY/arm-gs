# -*- coding: utf-8 -*-
"""
EquipmentGroup model (итоговая группа оборудования).
"""
from sqlalchemy import String, cast
from sqlalchemy.orm import reconstructor
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_REFDATA, SCHEMA_FUE_EM
from app.fuel.models.external_mapping.fue_em_business_unit_model import (
    BusinessUnitExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_cities_model import CitiesExternalMapping
from app.fuel.models.external_mapping.fue_em_department_model import (
    DepartmentExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_economic_region_model import (
    EconomicRegionExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_federal_district_model import (
    FederalDistrictExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_gen_company_branch_model import (
    GenCompanyBranchExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_gen_company_model import (
    GenCompanyExternalMapping,
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


class EquipmentGroup(db.Model):
    __tablename__ = "gs_fue_equipment_groups"
    __table_args__ = ({"schema": SCHEMA_FUEL},)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Пользовательский идентификатор/название группы
    name = db.Column(db.String(255), nullable=True)

    # Название (Топливо)
    name_ext = db.Column(db.String(255), nullable=True)

    # Признак группы оборудования
    niv = db.Column(db.Integer, nullable=True)

    # Признак станции, разбитой на группы оборудования
    comp = db.Column(db.Integer, nullable=True)

    # Код станции, в которую входит группа оборудования
    main = db.Column(db.Integer, nullable=True)

    # Признак действующей станции
    d = db.Column(db.Integer, nullable=True)

    # Признак расширяемой станции
    r = db.Column(db.Integer, nullable=True)

    # Признак ФОРЭМ
    forem = db.Column(db.Integer, nullable=True)

    # Ведомство
    vedomstvo = db.Column(db.Integer, nullable=True)

    # Код субъекта РФ (FK -> TerritoriesEnergyExternalMapping.external_id)
    obl = db.Column(db.Integer, nullable=True, index=True)
    territories_energy_external_mapping = db.relationship(
        "TerritoriesEnergyExternalMapping",
        foreign_keys=[obl],
        primaryjoin=cast(obl, String) == TerritoriesEnergyExternalMapping.external_id,
        viewonly=True,
        uselist=False,
    )

    # FK -> RegionalDistrict (заполняется при загрузке по obl и database_version_id)
    regional_district_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_regional_districts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    regional_district = db.relationship(
        "RegionalDistrict",
        foreign_keys=[regional_district_id],
        uselist=False,
        lazy="select",
    )

    # FK -> RegionalEnergySystem (заполняется при загрузке по obl и database_version_id)
    regional_energy_system_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_regional_energy_systems.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    regional_energy_system = db.relationship(
        "RegionalEnergySystem",
        foreign_keys=[regional_energy_system_id],
        uselist=False,
        lazy="select",
    )

    # Код департамента (FK -> DepartmentExternalMapping)
    dep = db.Column(db.Integer, nullable=True, index=True)
    department_external_mapping = db.relationship(
        "DepartmentExternalMapping",
        foreign_keys=[dep],
        primaryjoin=cast(dep, String) == DepartmentExternalMapping.external_id,
        viewonly=True,
        uselist=False,
    )

    # FK -> Department
    id_department = db.Column(db.Integer, nullable=True, index=True)

    # Код ОЭС (FK -> UnionEnergySystemExternalMapping.external_id)
    oes = db.Column(db.Integer, nullable=True, index=True)
    union_energy_system_external_mapping = db.relationship(
        "UnionEnergySystemExternalMapping",
        foreign_keys=[oes],
        primaryjoin=cast(oes, String) == UnionEnergySystemExternalMapping.external_id,
        viewonly=True,
        uselist=False,
    )

    # Код экономического района (FK -> EconomicRegionExternalMapping.external_id)
    er = db.Column(db.Integer, nullable=True, index=True)
    economic_region_external_mapping = db.relationship(
        "EconomicRegionExternalMapping",
        foreign_keys=[er],
        primaryjoin=cast(er, String) == EconomicRegionExternalMapping.external_id,
        viewonly=True,
        uselist=False,
    )

    # Код федерального округа (FK -> FederalDistrictExternalMapping.external_id)
    fo = db.Column(db.Integer, nullable=True, index=True)
    federal_district_external_mapping = db.relationship(
        "FederalDistrictExternalMapping",
        foreign_keys=[fo],
        primaryjoin=cast(fo, String) == FederalDistrictExternalMapping.external_id,
        viewonly=True,
        uselist=False,
    )

    # Код станции
    numb = db.Column(db.Integer, nullable=True)

    # Название типов турбин, которое соответствует коду (необязательное)
    tm = db.Column(db.String(255), nullable=True)

    # Мощность блока в группе оборудования_вариант 1
    n1 = db.Column(db.String(255), nullable=True)

    # Мощность блока в группе оборудования_вариант 2
    n2 = db.Column(db.String(255), nullable=True)

    # Давление пара перед турбиной_вариант 1
    p1 = db.Column(db.String(255), nullable=True)

    # Давление пара перед турбиной_вариант 2
    p2 = db.Column(db.String(255), nullable=True)

    # Порядковый номер станции
    ordnumb = db.Column(db.String(255), nullable=True)

    # Адрес
    addr = db.Column(db.String(255), nullable=True)

    # Примечание
    note = db.Column(db.String(1000), nullable=True)

    # Код города (связь по code -> CitiesExternalMapping.code, viewonly)
    # cast для совместимости, если в БД один из столбцов VARCHAR
    codegor = db.Column(db.Integer, nullable=True)
    cities_external_mapping = db.relationship(
        "CitiesExternalMapping",
        primaryjoin=cast(codegor, String) == cast(CitiesExternalMapping.code, String),
        foreign_keys=[codegor],
        viewonly=True,
        uselist=False,
        lazy="select",
    )

    # Тип генерирующей компании (FK -> BusinessUnitExternalMapping.external_id)
    be = db.Column(db.Integer, nullable=True, index=True)
    business_unit_external_mapping = db.relationship(
        "BusinessUnitExternalMapping",
        foreign_keys=[be],
        primaryjoin=cast(be, String) == BusinessUnitExternalMapping.external_id,
        viewonly=True,
        uselist=False,
    )

    # Код генерирующей компании (FK -> GenCompanyExternalMapping.external_id)
    gk = db.Column(db.Integer, nullable=True, index=True)
    gen_company_external_mapping = db.relationship(
        "GenCompanyExternalMapping",
        foreign_keys=[gk],
        primaryjoin=cast(gk, String) == GenCompanyExternalMapping.external_id,
        viewonly=True,
        uselist=False,
    )

    # Код филиала генерирующей компании (связь по external_id -> GenCompanyBranchExternalMapping, без FK в БД)
    gkf = db.Column(db.Integer, nullable=True, index=True)
    gen_company_branch_external_mapping = db.relationship(
        "GenCompanyBranchExternalMapping",
        foreign_keys=[gkf],
        primaryjoin=cast(gkf, String) == GenCompanyBranchExternalMapping.external_id,
        viewonly=True,
        uselist=False,
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

    def _populate_regional_ids(self) -> None:
        """
        Заполняет regional_district_id и regional_energy_system_id из Station
        через EquipmentGroupSet -> EquipmentGroupSetStation.
        """
        self.regional_district_id = None
        self.regional_energy_system_id = None
        if self.id is None:
            return
        # EquipmentGroup -> EquipmentGroupSet (equipment_group_id)
        # -> EquipmentGroupSetStation (equipment_group_set_station_id) -> Station (station_id)
        for link in self.equipment_group_links_v2:
            eg_set_station = link.equipment_group_set_station
            if eg_set_station:
                station = eg_set_station.station
                if station:
                    self.regional_district_id = station.id_regional_district
                    self.regional_energy_system_id = station.id_regional_energy_system
                    return

    def __repr__(self) -> str:
        return f"<EquipmentGroup id={self.id} name={self.name!r}>"
