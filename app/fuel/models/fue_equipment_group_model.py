# -*- coding: utf-8 -*-
"""
EquipmentGroup model (итоговая группа оборудования).
"""
import uuid
from sqlalchemy import String, cast
from sqlalchemy import event
from sqlalchemy.orm import reconstructor
from sqlalchemy.schema import Index
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_GENERATION, SCHEMA_REFDATA, SCHEMA_FUE_EM
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
from app.common.services.database_version_filter import filter_by_explicit_db_version
from app.common.services.refdata_fk_resolve import (
    coerce_regional_district_id_for_db_version,
    coerce_regional_energy_system_id_for_db_version,
)
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.territories.regional_district_model import RegionalDistrict


class EquipmentGroup(db.Model):
    __tablename__ = "gs_fue_equipment_groups"
    __table_args__ = (
        Index("ix_equipment_group_external_code", "external_code"),
        {"schema": SCHEMA_FUEL},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    external_code = db.Column(
        db.String(36),
        nullable=False,
    )

    # Пользовательский идентификатор/название группы
    name = db.Column(db.String(255), nullable=True)

    # Название (БД Топливо)
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
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_regional_districts.id", ondelete="SET NULL"),
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
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_regional_energy_systems.id", ondelete="SET NULL"),
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
        Заполняет regional_district_id и regional_energy_system_id:
        1) из Station через EquipmentGroupSet -> EquipmentGroupSetStation;
        2) для standalone-групп (котельные) — по obl через TerritoriesEnergyExternalMapping.
        """
        self.regional_district_id = None
        self.regional_energy_system_id = None
        if self.id is None:
            return
        # 1. EquipmentGroup -> EquipmentGroupSet (equipment_group_id)
        # -> EquipmentGroupSetStation (equipment_group_set_station_id) -> Station (station_id)
        for link in self.equipment_group_links_v2:
            eg_set_station = link.equipment_group_set_station
            if eg_set_station:
                station = eg_set_station.station
                if station:
                    version_id = self.database_version_id
                    self.regional_district_id = coerce_regional_district_id_for_db_version(
                        station.id_regional_district, version_id
                    )
                    self.regional_energy_system_id = coerce_regional_energy_system_id_for_db_version(
                        station.id_regional_energy_system, version_id
                    )
                    return

        # 2. Fallback для standalone-групп (котельные): по obl через TerritoriesEnergyExternalMapping.
        # RegionalDistrict и RegionalEnergySystem привязываются с учетом EquipmentGroup.database_version_id.
        if self.obl is not None:
            obl_val = int(self.obl) if not isinstance(self.obl, int) else self.obl
            mapping = db.session.query(TerritoriesEnergyExternalMapping).filter(
                (TerritoriesEnergyExternalMapping.obl == obl_val)
                | (TerritoriesEnergyExternalMapping.external_id == str(obl_val))
            ).first()
            if mapping:
                version_id = self.database_version_id
                if mapping.regional_district_ref_uuid:
                    rd_query = RegionalDistrict.query.filter(
                        RegionalDistrict.ref_uuid == mapping.regional_district_ref_uuid
                    )
                    rd_query = filter_by_explicit_db_version(rd_query, RegionalDistrict, version_id)
                    rd = rd_query.first()
                    if rd:
                        self.regional_district_id = rd.id
                if mapping.regional_energy_system_ref_uuid:
                    res_query = RegionalEnergySystem.query.filter(
                        RegionalEnergySystem.ref_uuid == mapping.regional_energy_system_ref_uuid
                    )
                    res_query = filter_by_explicit_db_version(res_query, RegionalEnergySystem, version_id)
                    res = res_query.first()
                    if res:
                        self.regional_energy_system_id = res.id

    def __repr__(self) -> str:
        return f"<EquipmentGroup id={self.id} name={self.name!r}>"


def _equipment_group_key(name, name_ext, numb, main) -> str:
    """
    Формирует стабильный ключ для генерации external_code.
    Используются только поля из исходных данных (numb, name, name_ext, main),
    без regional_district_id и regional_energy_system_id — они зависят от версии БД.
    Так группы с одинаковым numb для разных версий получают один external_code.
    """
    return (
        f"equipment_group|numb|{numb or ''}|name|{name or ''}"
        f"|name_ext|{name_ext or ''}|main|{main or ''}"
    )


@event.listens_for(EquipmentGroup, "before_insert")
def generate_external_code_before_insert(mapper, connection, target):
    """Генерирует стабильный external_code перед вставкой группы оборудования."""
    if target.external_code:
        return
    key = _equipment_group_key(
        target.name,
        target.name_ext,
        target.numb,
        target.main,
    )
    target.external_code = str(uuid.uuid5(uuid.NAMESPACE_URL, key))
