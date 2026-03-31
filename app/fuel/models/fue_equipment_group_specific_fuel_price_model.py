# -*- coding: utf-8 -*-
"""
EquipmentGroupSpecificFuelPrice model — цена для групп оборудования.
Поля из Excel: NAME, Year, OBL, GAZ_c, gazpp_c, gaz_prir_c, MAZUT_c и т.д.
"""
from sqlalchemy import UniqueConstraint
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_REFDATA


class EquipmentGroupSpecificFuelPrice(db.Model):
    """
    Цена для группы оборудования.
    Связь с EquipmentGroup через equipment_group_id.
    Поля из Excel: NAME, Year, OBL, GAZ_c, gazpp_c, gaz_prir_c, MAZUT_c и др.
    """
    __tablename__ = "gs_fue_equipment_group_specific_fuel_price"
    __table_args__ = (
        UniqueConstraint(
            "equipment_group_id",
            "year_number",
            name="uq_equipment_group_specific_fuel_price_group_year",
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
        backref="specific_fuel_prices",
        foreign_keys=[equipment_group_id],
        uselist=False,
        lazy="select",
    )

    name = db.Column(db.String(512), nullable=True)  # NAME
    year_number = db.Column(db.Integer, nullable=True, index=True)  # Year
    obl = db.Column(db.String(80), nullable=True)  # OBL

    # Ценовые поля (Numeric) — рассчитываются по формулам xxx_c = cost.xxx / quantity.
    # quantity из EquipmentGroupFuelParam (FROM_EQUIPMENT_GROUP) или EquipmentGroupExtraFuelParam (FROM_EXTRA_FUEL).
    gaz_c = db.Column(db.Numeric(36, 16), nullable=True)
    gazpp_c = db.Column(db.Numeric(36, 16), nullable=True)
    gaz_prir_c = db.Column(db.Numeric(36, 16), nullable=True)
    mazut_c = db.Column(db.Numeric(36, 16), nullable=True)
    disel_c = db.Column(db.Numeric(36, 16), nullable=True)
    maztop_c = db.Column(db.Numeric(36, 16), nullable=True)
    gtt_c = db.Column(db.Numeric(36, 16), nullable=True)
    nft_proch_c = db.Column(db.Numeric(36, 16), nullable=True)
    torf_c = db.Column(db.Numeric(36, 16), nullable=True)
    isk_gaz_c = db.Column(db.Numeric(36, 16), nullable=True)
    domen_g_c = db.Column(db.Numeric(36, 16), nullable=True)
    koks_g_c = db.Column(db.Numeric(36, 16), nullable=True)
    prochgaz_c = db.Column(db.Numeric(36, 16), nullable=True)
    proch_c = db.Column(db.Numeric(36, 16), nullable=True)
    tvproch_c = db.Column(db.Numeric(36, 16), nullable=True)
    szh_gaz_c = db.Column(db.Numeric(36, 16), nullable=True)
    inoe_c = db.Column(db.Numeric(36, 16), nullable=True)
    don_c = db.Column(db.Numeric(36, 16), nullable=True)
    podm_c = db.Column(db.Numeric(36, 16), nullable=True)
    pech_c = db.Column(db.Numeric(36, 16), nullable=True)
    vork_c = db.Column(db.Numeric(36, 16), nullable=True)
    intin_c = db.Column(db.Numeric(36, 16), nullable=True)
    kuzn_c = db.Column(db.Numeric(36, 16), nullable=True)
    kuzngd_c = db.Column(db.Numeric(36, 16), nullable=True)
    kuznt_c = db.Column(db.Numeric(36, 16), nullable=True)
    kuznss_c = db.Column(db.Numeric(36, 16), nullable=True)
    kuznun_c = db.Column(db.Numeric(36, 16), nullable=True)
    ural_c = db.Column(db.Numeric(36, 16), nullable=True)
    sver_c = db.Column(db.Numeric(36, 16), nullable=True)
    chel_c = db.Column(db.Numeric(36, 16), nullable=True)
    kizel_c = db.Column(db.Numeric(36, 16), nullable=True)
    bashk_c = db.Column(db.Numeric(36, 16), nullable=True)
    kazah_c = db.Column(db.Numeric(36, 16), nullable=True)
    ekib_c = db.Column(db.Numeric(36, 16), nullable=True)
    maikub_c = db.Column(db.Numeric(36, 16), nullable=True)
    karag_c = db.Column(db.Numeric(36, 16), nullable=True)
    karajyra_c = db.Column(db.Numeric(36, 16), nullable=True)
    teniz_c = db.Column(db.Numeric(36, 16), nullable=True)
    kan_c = db.Column(db.Numeric(36, 16), nullable=True)
    nazar_c = db.Column(db.Numeric(36, 16), nullable=True)
    ibor_c = db.Column(db.Numeric(36, 16), nullable=True)
    berez_c = db.Column(db.Numeric(36, 16), nullable=True)
    per_c = db.Column(db.Numeric(36, 16), nullable=True)
    irbei_c = db.Column(db.Numeric(36, 16), nullable=True)
    kansk_c = db.Column(db.Numeric(36, 16), nullable=True)
    irkut_c = db.Column(db.Numeric(36, 16), nullable=True)
    azey_c = db.Column(db.Numeric(36, 16), nullable=True)
    mug_c = db.Column(db.Numeric(36, 16), nullable=True)
    cher_c = db.Column(db.Numeric(36, 16), nullable=True)
    tung_c = db.Column(db.Numeric(36, 16), nullable=True)
    jer_c = db.Column(db.Numeric(36, 16), nullable=True)
    karab_c = db.Column(db.Numeric(36, 16), nullable=True)
    hak_c = db.Column(db.Numeric(36, 16), nullable=True)
    tuv_c = db.Column(db.Numeric(36, 16), nullable=True)
    bur_c = db.Column(db.Numeric(36, 16), nullable=True)
    gusin_c = db.Column(db.Numeric(36, 16), nullable=True)
    tugn_c = db.Column(db.Numeric(36, 16), nullable=True)
    okino_c = db.Column(db.Numeric(36, 16), nullable=True)
    chit_c = db.Column(db.Numeric(36, 16), nullable=True)
    har_c = db.Column(db.Numeric(36, 16), nullable=True)
    urt_c = db.Column(db.Numeric(36, 16), nullable=True)
    tataur_c = db.Column(db.Numeric(36, 16), nullable=True)
    tarbag_c = db.Column(db.Numeric(36, 16), nullable=True)
    zab_kam_c = db.Column(db.Numeric(36, 16), nullable=True)
    amur_c = db.Column(db.Numeric(36, 16), nullable=True)
    rai_c = db.Column(db.Numeric(36, 16), nullable=True)
    erk_c = db.Column(db.Numeric(36, 16), nullable=True)
    ogodj_c = db.Column(db.Numeric(36, 16), nullable=True)
    svo_c = db.Column(db.Numeric(36, 16), nullable=True)
    urg_c = db.Column(db.Numeric(36, 16), nullable=True)
    ushum_c = db.Column(db.Numeric(36, 16), nullable=True)
    prim_c = db.Column(db.Numeric(36, 16), nullable=True)
    bikin_c = db.Column(db.Numeric(36, 16), nullable=True)
    razdol_c = db.Column(db.Numeric(36, 16), nullable=True)
    hankai_c = db.Column(db.Numeric(36, 16), nullable=True)
    yakut_c = db.Column(db.Numeric(36, 16), nullable=True)
    neru_c = db.Column(db.Numeric(36, 16), nullable=True)
    zyryan_c = db.Column(db.Numeric(36, 16), nullable=True)
    pyak_c = db.Column(db.Numeric(36, 16), nullable=True)
    mag_c = db.Column(db.Numeric(36, 16), nullable=True)
    chukot_c = db.Column(db.Numeric(36, 16), nullable=True)
    anad_c = db.Column(db.Numeric(36, 16), nullable=True)
    bering_c = db.Column(db.Numeric(36, 16), nullable=True)
    kamch_c = db.Column(db.Numeric(36, 16), nullable=True)
    sah_c = db.Column(db.Numeric(36, 16), nullable=True)

    # Служебные поля
    numb1120 = db.Column(db.Integer, nullable=True, index=True)
    sost = db.Column(db.String(80), nullable=True)
    group = db.Column(db.String(80), nullable=True)

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
            f"<EquipmentGroupSpecificFuelPrice id={self.id} "
            f"equipment_group_id={self.equipment_group_id} year={self.year_number}>"
        )
