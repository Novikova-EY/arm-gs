# -*- coding: utf-8 -*-
"""
TerritoriesEnergyExternalMapping model (единая таблица для субъектов РФ/РЭС/энергорайонов).
"""
from app.extensions import db
from config import SCHEMA_FUE_EM


class TerritoriesEnergyExternalMapping(db.Model):
    __tablename__ = "gs_fue_em_territories_energy"
    __table_args__ = ({"schema": SCHEMA_FUE_EM},)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # UUID для связей (могут отсутствовать)
    regional_district_ref_uuid = db.Column(db.String(36), nullable=True, index=True)
    regional_energy_system_ref_uuid = db.Column(db.String(36), nullable=True, index=True)
    energy_zone_ref_uuid = db.Column(db.String(36), nullable=True, index=True)

    # Поля из БД Топливо
    name_topl = db.Column(db.String(255), nullable=True)
    ao_topl = db.Column(db.String(255), nullable=True)
    obl_topl = db.Column(db.String(255), nullable=True)
    alph_topl = db.Column(db.String(255), nullable=True)
    dep_topl = db.Column(
        db.String(80),
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_department.external_id"),
        nullable=True,
    )
    oes_topl = db.Column(
        db.String(80),
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_union_energy_system.external_id"),
        nullable=True,
    )
    er_topl = db.Column(
        db.String(80),
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_economic_region.external_id"),
        nullable=True,
    )
    terr_belyaev_topl = db.Column(db.String(255), nullable=True)
    teo90_topl = db.Column(db.String(255), nullable=True)
    fo_topl = db.Column(
        db.String(80),
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_federal_district.external_id"),
        nullable=True,
    )
    abbr_topl = db.Column(db.String(255), nullable=True)
    reu_topl = db.Column(db.String(255), nullable=True)
    pter_topl = db.Column(db.String(255), nullable=True)
    keyword_topl = db.Column(db.String(255), nullable=True)

    def __repr__(self) -> str:
        return (
            "<TerritoriesEnergyExternalMapping "
            f"id={self.id} rd_uuid={self.regional_district_ref_uuid!r} "
            f"res_uuid={self.regional_energy_system_ref_uuid!r} "
            f"ez_uuid={self.energy_zone_ref_uuid!r}>"
        )
