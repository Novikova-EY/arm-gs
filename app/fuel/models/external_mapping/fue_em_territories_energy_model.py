# -*- coding: utf-8 -*-
"""
TerritoriesEnergyExternalMapping model (единая таблица для субъектов РФ/РЭС/энергорайонов).
"""
from app.extensions import db
from config import SCHEMA_FUE_EM
from app.common.models.audit_mixin import AuditMixin


class TerritoriesEnergyExternalMapping(db.Model, AuditMixin):
    __tablename__ = "gs_fue_em_territories_energy"
    __table_args__ = ({"schema": SCHEMA_FUE_EM},)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Внешний код для связей (аналог obl_topl, уникальный ключ для FK)
    external_id = db.Column(db.String(80), nullable=True, index=True, unique=True)
    # Название для отображения (из name_topl)
    external_name = db.Column(db.String(255), nullable=True)

    # UUID для связей (могут отсутствовать)
    regional_district_ref_uuid = db.Column(db.String(36), nullable=True, index=True)
    regional_energy_system_ref_uuid = db.Column(db.String(36), nullable=True, index=True)
    energy_zone_ref_uuid = db.Column(db.String(36), nullable=True, index=True)

    # Поля из БД Топливо
    name_ext = db.Column(db.String(255), nullable=True)
    ao = db.Column(db.String(255), nullable=True)
    obl = db.Column(db.Integer, nullable=True, index=True)
    alph = db.Column(db.Integer, nullable=True)
    dep = db.Column(db.Integer, nullable=True, index=True)
    oes = db.Column(db.Integer, nullable=True, index=True)
    er = db.Column(db.Integer, nullable=True, index=True)
    terr_belyaev = db.Column(db.Integer, nullable=True)
    teo90 = db.Column(db.Integer, nullable=True)
    fo = db.Column(db.Integer, nullable=True, index=True)
    abbr = db.Column(db.String(255), nullable=True)
    reu = db.Column(db.String(255), nullable=True)
    pter = db.Column(db.String(255), nullable=True)
    keyword = db.Column(db.String(255), nullable=True)

    def __repr__(self) -> str:
        return (
            "<TerritoriesEnergyExternalMapping "
            f"id={self.id} rd_uuid={self.regional_district_ref_uuid!r} "
            f"res_uuid={self.regional_energy_system_ref_uuid!r} "
            f"ez_uuid={self.energy_zone_ref_uuid!r}>"
        )
