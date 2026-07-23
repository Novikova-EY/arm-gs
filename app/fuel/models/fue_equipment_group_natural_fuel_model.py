# -*- coding: utf-8 -*-
"""
EquipmentGroupNaturalFuel — калорийные эквиваленты / натуральный расход (Натура99).
"""
from sqlalchemy import String, UniqueConstraint, cast, ForeignKeyConstraint
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_REFDATA
from app.fuel.models.external_mapping.fue_em_department_model import (
    DepartmentExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_economic_region_model import (
    EconomicRegionExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_territories_energy_model import (
    TerritoriesEnergyExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_union_energy_system_model import (
    UnionEnergySystemExternalMapping,
)

class EquipmentGroupNaturalFuel(db.Model):
    """
    Натуральный расход / калорийные эквиваленты топлива по группе оборудования.
    Связь с EquipmentGroup через equipment_group_id и numb1120 = EquipmentGroup.numb.
    year_number + database_version_id → Year.number + Year.database_version_id.
    """
    __tablename__ = "gs_fue_equipment_group_natural_fuel"
    __table_args__ = (
        UniqueConstraint(
            "equipment_group_id",
            "year_number",
            name="uq_equipment_group_natural_fuel_group_year",
        ),
        ForeignKeyConstraint(
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_equipment_group_natural_fuel_year_ver",
        ),
        {"schema": SCHEMA_FUEL},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    equipment_group_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_FUEL}.gs_fue_equipment_groups.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    equipment_group = db.relationship(
        "EquipmentGroup",
        backref="natural_fuels",
        foreign_keys=[equipment_group_id],
        uselist=False,
        lazy="select",
    )

    name = db.Column(db.String(512), nullable=True)

    # Ссылка на год: Year.number + database_version_id (composite FK).
    # Односторонняя связь без back_populates — иначе configure_mappers падает
    # из‑за порядка импорта fuel.models / Year.
    year_number = db.Column(db.Integer, nullable=True, index=True)
    year = db.relationship(
        "Year",
        lazy="noload",
        primaryjoin=(
            "and_(Year.number==EquipmentGroupNaturalFuel.year_number, "
            "Year.database_version_id==EquipmentGroupNaturalFuel.database_version_id)"
        ),
        foreign_keys="[EquipmentGroupNaturalFuel.year_number, EquipmentGroupNaturalFuel.database_version_id]",
        viewonly=True,
    )

    gaz = db.Column(db.Numeric(36, 16), nullable=True)
    gazpp = db.Column(db.Numeric(36, 16), nullable=True)
    gaz_prir = db.Column(db.Numeric(36, 16), nullable=True)
    isk_gaz = db.Column(db.Numeric(36, 16), nullable=True)
    domen_g = db.Column(db.Numeric(36, 16), nullable=True)
    koks_g = db.Column(db.Numeric(36, 16), nullable=True)
    prochgaz = db.Column(db.Numeric(36, 16), nullable=True)
    mazut = db.Column(db.Numeric(36, 16), nullable=True)
    disel = db.Column(db.Numeric(36, 16), nullable=True)
    maztop = db.Column(db.Numeric(36, 16), nullable=True)
    gtt = db.Column(db.Numeric(36, 16), nullable=True)
    nft_proch = db.Column(db.Numeric(36, 16), nullable=True)
    torf = db.Column(db.Numeric(36, 16), nullable=True)
    gtd = db.Column(db.Numeric(36, 16), nullable=True)
    slan = db.Column(db.Numeric(36, 16), nullable=True)
    proch = db.Column(db.Numeric(36, 16), nullable=True)
    tvproch = db.Column(db.Numeric(36, 16), nullable=True)
    szh_gaz = db.Column(db.Numeric(36, 16), nullable=True)
    inoe = db.Column(db.Numeric(36, 16), nullable=True)
    ugol = db.Column(db.Numeric(36, 16), nullable=True)
    don = db.Column(db.Numeric(36, 16), nullable=True)
    podm = db.Column(db.Numeric(36, 16), nullable=True)
    vork = db.Column(db.Numeric(36, 16), nullable=True)
    intin = db.Column(db.Numeric(36, 16), nullable=True)
    pech = db.Column(db.Numeric(36, 16), nullable=True)
    arkt = db.Column(db.Numeric(36, 16), nullable=True)
    kuzn = db.Column(db.Numeric(36, 16), nullable=True)
    kuzngd = db.Column(db.Numeric(36, 16), nullable=True)
    kuznt = db.Column(db.Numeric(36, 16), nullable=True)
    kuznss = db.Column(db.Numeric(36, 16), nullable=True)
    kuznun = db.Column(db.Numeric(36, 16), nullable=True)
    ural = db.Column(db.Numeric(36, 16), nullable=True)
    sver = db.Column(db.Numeric(36, 16), nullable=True)
    chel = db.Column(db.Numeric(36, 16), nullable=True)
    kizel = db.Column(db.Numeric(36, 16), nullable=True)
    bashk = db.Column(db.Numeric(36, 16), nullable=True)
    kazah = db.Column(db.Numeric(36, 16), nullable=True)
    ekib = db.Column(db.Numeric(36, 16), nullable=True)
    maikub = db.Column(db.Numeric(36, 16), nullable=True)
    karag = db.Column(db.Numeric(36, 16), nullable=True)
    karajyra = db.Column(db.Numeric(36, 16), nullable=True)
    teniz = db.Column(db.Numeric(36, 16), nullable=True)
    kan = db.Column(db.Numeric(36, 16), nullable=True)
    nazar = db.Column(db.Numeric(36, 16), nullable=True)
    ibor = db.Column(db.Numeric(36, 16), nullable=True)
    berez = db.Column(db.Numeric(36, 16), nullable=True)
    per = db.Column(db.Numeric(36, 16), nullable=True)
    irbei = db.Column(db.Numeric(36, 16), nullable=True)
    kansk = db.Column(db.Numeric(36, 16), nullable=True)
    irkut = db.Column(db.Numeric(36, 16), nullable=True)
    azey = db.Column(db.Numeric(36, 16), nullable=True)
    mug = db.Column(db.Numeric(36, 16), nullable=True)
    cher = db.Column(db.Numeric(36, 16), nullable=True)
    tung = db.Column(db.Numeric(36, 16), nullable=True)
    jer = db.Column(db.Numeric(36, 16), nullable=True)
    karab = db.Column(db.Numeric(36, 16), nullable=True)
    hak = db.Column(db.Numeric(36, 16), nullable=True)
    tuv = db.Column(db.Numeric(36, 16), nullable=True)
    bur = db.Column(db.Numeric(36, 16), nullable=True)
    gusin = db.Column(db.Numeric(36, 16), nullable=True)
    tugn = db.Column(db.Numeric(36, 16), nullable=True)
    okino = db.Column(db.Numeric(36, 16), nullable=True)
    chit = db.Column(db.Numeric(36, 16), nullable=True)
    har = db.Column(db.Numeric(36, 16), nullable=True)
    urt = db.Column(db.Numeric(36, 16), nullable=True)
    tataur = db.Column(db.Numeric(36, 16), nullable=True)
    tarbag = db.Column(db.Numeric(36, 16), nullable=True)
    zab_kam = db.Column(db.Numeric(36, 16), nullable=True)
    yakut = db.Column(db.Numeric(36, 16), nullable=True)
    neru = db.Column(db.Numeric(36, 16), nullable=True)
    zyryan = db.Column(db.Numeric(36, 16), nullable=True)
    pyak = db.Column(db.Numeric(36, 16), nullable=True)
    amur = db.Column(db.Numeric(36, 16), nullable=True)
    rai = db.Column(db.Numeric(36, 16), nullable=True)
    erk = db.Column(db.Numeric(36, 16), nullable=True)
    ogodj = db.Column(db.Numeric(36, 16), nullable=True)
    svo = db.Column(db.Numeric(36, 16), nullable=True)
    urg = db.Column(db.Numeric(36, 16), nullable=True)
    ushum = db.Column(db.Numeric(36, 16), nullable=True)
    prim = db.Column(db.Numeric(36, 16), nullable=True)
    bikin = db.Column(db.Numeric(36, 16), nullable=True)
    razdol = db.Column(db.Numeric(36, 16), nullable=True)
    hankai = db.Column(db.Numeric(36, 16), nullable=True)
    mag = db.Column(db.Numeric(36, 16), nullable=True)
    chukot = db.Column(db.Numeric(36, 16), nullable=True)
    bering = db.Column(db.Numeric(36, 16), nullable=True)
    anad = db.Column(db.Numeric(36, 16), nullable=True)
    kamch = db.Column(db.Numeric(36, 16), nullable=True)
    sah = db.Column(db.Numeric(36, 16), nullable=True)

    # Код субъекта РФ (как у EquipmentGroup.obl)
    obl = db.Column(db.Integer, nullable=True, index=True)
    territories_energy_external_mapping = db.relationship(
        "TerritoriesEnergyExternalMapping",
        foreign_keys=[obl],
        primaryjoin=cast(obl, String) == TerritoriesEnergyExternalMapping.external_id,
        viewonly=True,
        uselist=False,
    )

    # Код департамента (как у EquipmentGroup.dep)
    dep = db.Column(db.Integer, nullable=True, index=True)
    department_external_mapping = db.relationship(
        "DepartmentExternalMapping",
        foreign_keys=[dep],
        primaryjoin=cast(dep, String) == DepartmentExternalMapping.external_id,
        viewonly=True,
        uselist=False,
    )

    # Код ОЭС (как у EquipmentGroup.oes)
    oes = db.Column(db.Integer, nullable=True, index=True)
    union_energy_system_external_mapping = db.relationship(
        "UnionEnergySystemExternalMapping",
        foreign_keys=[oes],
        primaryjoin=cast(oes, String) == UnionEnergySystemExternalMapping.external_id,
        viewonly=True,
        uselist=False,
    )

    # Код экономического района (как у EquipmentGroup.er)
    er = db.Column(db.Integer, nullable=True, index=True)
    economic_region_external_mapping = db.relationship(
        "EconomicRegionExternalMapping",
        foreign_keys=[er],
        primaryjoin=cast(er, String) == EconomicRegionExternalMapping.external_id,
        viewonly=True,
        uselist=False,
    )

    # Код электростанции: numb1120 = EquipmentGroup.numb (без FK — numb не уникален)
    numb1120 = db.Column(db.Integer, nullable=True, index=True)
    equipment_group_by_numb = db.relationship(
        "EquipmentGroup",
        primaryjoin=(
            "and_("
            "EquipmentGroupNaturalFuel.numb1120==foreign(EquipmentGroup.numb), "
            "EquipmentGroupNaturalFuel.database_version_id==EquipmentGroup.database_version_id"
            ")"
        ),
        viewonly=True,
        uselist=False,
        lazy="select",
    )

    numb1 = db.Column(db.Integer, nullable=True)

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
            f"<EquipmentGroupNaturalFuel id={self.id} "
            f"equipment_group_id={self.equipment_group_id} year={self.year_number}>"
        )
