# -*- coding: utf-8 -*-
"""
EquipmentGroupExtraFuelParam model — дополнительные топливные параметры групп оборудования.
"""
from sqlalchemy import UniqueConstraint
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_REFDATA


class EquipmentGroupExtraFuelParam(db.Model):
    """
    Дополнительные топливные параметры группы оборудования.
    Связь с EquipmentGroup через equipment_group_id.
    """
    __tablename__ = "gs_fue_equipment_group_extra_fuel_param"
    __table_args__ = (
        UniqueConstraint(
            "equipment_group_id",
            "year_number",
            name="uq_equipment_group_extra_fuel_param_group_year",
        ),
        {"schema": SCHEMA_FUEL},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK -> EquipmentGroup (итоговая группа оборудования)
    equipment_group_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_FUEL}.gs_fue_equipment_groups.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    equipment_group = db.relationship(
        "EquipmentGroup",
        backref="extra_fuel_params",
        foreign_keys=[equipment_group_id],
        uselist=False,
        lazy="select",
    )

    name = db.Column(db.String(512), nullable=True)
    year_number = db.Column(db.Integer, nullable=True, index=True)

    # Топливные поля (Numeric по аналогии с EquipmentGroupFuelParam)
    gaz_prir = db.Column(db.Numeric(20, 6), nullable=True)
    gazpp = db.Column(db.Numeric(20, 6), nullable=True)
    disel = db.Column(db.Numeric(20, 6), nullable=True)
    maztop = db.Column(db.Numeric(20, 6), nullable=True)
    gtt = db.Column(db.Numeric(20, 6), nullable=True)
    nft_proch = db.Column(db.Numeric(20, 6), nullable=True)
    domen_g = db.Column(db.Numeric(20, 6), nullable=True)
    koks_g = db.Column(db.Numeric(20, 6), nullable=True)
    prochgaz = db.Column(db.Numeric(20, 6), nullable=True)
    tvproch = db.Column(db.Numeric(20, 6), nullable=True)
    szh_gaz = db.Column(db.Numeric(20, 6), nullable=True)
    inoe = db.Column(db.Numeric(20, 6), nullable=True)

    nazar = db.Column(db.Numeric(20, 6), nullable=True)
    ibor = db.Column(db.Numeric(20, 6), nullable=True)
    berez = db.Column(db.Numeric(20, 6), nullable=True)
    per = db.Column(db.Numeric(20, 6), nullable=True)
    irbei = db.Column(db.Numeric(20, 6), nullable=True)
    kansk = db.Column(db.Numeric(20, 6), nullable=True)
    gusin = db.Column(db.Numeric(20, 6), nullable=True)
    tugn = db.Column(db.Numeric(20, 6), nullable=True)
    okino = db.Column(db.Numeric(20, 6), nullable=True)
    azey = db.Column(db.Numeric(20, 6), nullable=True)
    mug = db.Column(db.Numeric(20, 6), nullable=True)
    cher = db.Column(db.Numeric(20, 6), nullable=True)
    jer = db.Column(db.Numeric(20, 6), nullable=True)
    karab = db.Column(db.Numeric(20, 6), nullable=True)
    vork = db.Column(db.Numeric(20, 6), nullable=True)
    intin = db.Column(db.Numeric(20, 6), nullable=True)
    sver = db.Column(db.Numeric(20, 6), nullable=True)
    chel = db.Column(db.Numeric(20, 6), nullable=True)
    kizel = db.Column(db.Numeric(20, 6), nullable=True)
    har = db.Column(db.Numeric(20, 6), nullable=True)
    urt = db.Column(db.Numeric(20, 6), nullable=True)
    tataur = db.Column(db.Numeric(20, 6), nullable=True)
    tarbag = db.Column(db.Numeric(20, 6), nullable=True)
    zab_kam = db.Column(db.Numeric(20, 6), nullable=True)
    rai = db.Column(db.Numeric(20, 6), nullable=True)
    erk = db.Column(db.Numeric(20, 6), nullable=True)
    ogodj = db.Column(db.Numeric(20, 6), nullable=True)
    svo = db.Column(db.Numeric(20, 6), nullable=True)
    bikin = db.Column(db.Numeric(20, 6), nullable=True)
    razdol = db.Column(db.Numeric(20, 6), nullable=True)
    hankai = db.Column(db.Numeric(20, 6), nullable=True)
    neru = db.Column(db.Numeric(20, 6), nullable=True)
    zyryan = db.Column(db.Numeric(20, 6), nullable=True)
    pyak = db.Column(db.Numeric(20, 6), nullable=True)
    kuzngd = db.Column(db.Numeric(20, 6), nullable=True)
    kuznt = db.Column(db.Numeric(20, 6), nullable=True)
    kuznss = db.Column(db.Numeric(20, 6), nullable=True)
    kuznun = db.Column(db.Numeric(20, 6), nullable=True)
    bering = db.Column(db.Numeric(20, 6), nullable=True)
    anad = db.Column(db.Numeric(20, 6), nullable=True)
    ekib = db.Column(db.Numeric(20, 6), nullable=True)
    maikub = db.Column(db.Numeric(20, 6), nullable=True)
    karag = db.Column(db.Numeric(20, 6), nullable=True)
    karajyra = db.Column(db.Numeric(20, 6), nullable=True)
    teniz = db.Column(db.Numeric(20, 6), nullable=True)

    numb1120 = db.Column(db.Integer, nullable=True, index=True)  # связь по NUMB1120
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
            f"<EquipmentGroupExtraFuelParam id={self.id} "
            f"equipment_group_id={self.equipment_group_id} year={self.year_number}>"
        )
