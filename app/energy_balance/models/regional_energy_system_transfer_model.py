# -*- coding: utf-8 -*-
"""
RegionalEnergySystemTransfer — перетоки электроэнергии между энергосистемами (млн кВт·ч).

Источник перетока — RegionalEnergySystem или RegionalDistrict (субъект РФ), ровно одна связь.
Получатель — RegionalEnergySystem, ForeignBorderCountry, RegionalDistrict или EnergyUnit
(энергорайон), ровно одна связь.

- year_number — календарный год;
- month_number = 0 — годовое значение («год»);
- month_number = 1..12 — значение за соответствующий месяц года.
"""
from sqlalchemy.sql import func
from sqlalchemy import Numeric, Index, text, CheckConstraint
from app.extensions import db
from config import SCHEMA_ENERGY_BALANCE, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin

EE_TRANSFER_PERIOD_YEAR = 0


class RegionalEnergySystemTransfer(db.Model, AuditMixin):
    __tablename__ = "gs_bem_regional_energy_system_transfers"
    __table_args__ = (
        CheckConstraint(
            "(id_from_regional_energy_system IS NOT NULL AND id_from_regional_district IS NULL) OR "
            "(id_from_regional_energy_system IS NULL AND id_from_regional_district IS NOT NULL)",
            name="ck_ee_transfer_from_source",
        ),
        CheckConstraint(
            "(id_to_regional_energy_system IS NOT NULL AND id_to_foreign_border_country IS NULL "
            "AND id_to_regional_district IS NULL AND id_to_energy_unit IS NULL) OR "
            "(id_to_regional_energy_system IS NULL AND id_to_foreign_border_country IS NOT NULL "
            "AND id_to_regional_district IS NULL AND id_to_energy_unit IS NULL) OR "
            "(id_to_regional_energy_system IS NULL AND id_to_foreign_border_country IS NULL "
            "AND id_to_regional_district IS NOT NULL AND id_to_energy_unit IS NULL) OR "
            "(id_to_regional_energy_system IS NULL AND id_to_foreign_border_country IS NULL "
            "AND id_to_regional_district IS NULL AND id_to_energy_unit IS NOT NULL)",
            name="ck_ee_transfer_to_target",
        ),
        Index("ix_ee_transfer_from_res", "id_from_regional_energy_system"),
        Index("ix_ee_transfer_from_rd", "id_from_regional_district"),
        Index("ix_ee_transfer_to_res", "id_to_regional_energy_system"),
        Index("ix_ee_transfer_to_country", "id_to_foreign_border_country"),
        Index("ix_ee_transfer_to_rd", "id_to_regional_district"),
        Index("ix_ee_transfer_to_eu", "id_to_energy_unit"),
        Index("ix_ee_transfer_ues", "id_union_energy_system"),
        Index("ix_ee_transfer_year_number", "year_number"),
        Index("ix_ee_transfer_month_number", "month_number"),
        Index(
            "ix_ee_transfer_from_to_year_month",
            "id_from_regional_energy_system",
            "id_from_regional_district",
            "id_to_regional_energy_system",
            "id_to_foreign_border_country",
            "id_to_regional_district",
            "id_to_energy_unit",
            "year_number",
            "month_number",
        ),
        Index(
            "uq_ee_transfer_from_to_ues_year_month_ver",
            text("COALESCE(id_from_regional_energy_system, -1)"),
            text("COALESCE(id_from_regional_district, -1)"),
            text("COALESCE(id_to_regional_energy_system, -1)"),
            text("COALESCE(id_to_foreign_border_country, -1)"),
            text("COALESCE(id_to_regional_district, -1)"),
            text("COALESCE(id_to_energy_unit, -1)"),
            "id_union_energy_system",
            "year_number",
            "month_number",
            text("COALESCE(database_version_id, -1)"),
            unique=True,
        ),
        db.ForeignKeyConstraint(
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_ee_transfer_year_ver",
        ),
        {"schema": SCHEMA_ENERGY_BALANCE},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    year_number = db.Column(db.Integer, nullable=True, index=True)
    month_number = db.Column(
        db.Integer,
        nullable=False,
        default=EE_TRANSFER_PERIOD_YEAR,
        server_default="0",
        index=True,
    )

    id_from_regional_energy_system = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_REFDATA}.gs_sys_regional_energy_systems.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )
    from_regional_energy_system = db.relationship(
        "RegionalEnergySystem",
        foreign_keys=[id_from_regional_energy_system],
    )

    id_from_regional_district = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_REFDATA}.gs_sys_regional_districts.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )
    from_regional_district = db.relationship(
        "RegionalDistrict",
        foreign_keys=[id_from_regional_district],
    )

    id_to_regional_energy_system = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_REFDATA}.gs_sys_regional_energy_systems.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )
    to_regional_energy_system = db.relationship(
        "RegionalEnergySystem",
        foreign_keys=[id_to_regional_energy_system],
    )

    id_to_foreign_border_country = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_REFDATA}.gs_sys_foreign_border_countries.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )
    to_foreign_border_country = db.relationship(
        "ForeignBorderCountry",
        foreign_keys=[id_to_foreign_border_country],
    )

    id_to_regional_district = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_REFDATA}.gs_sys_regional_districts.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )
    to_regional_district = db.relationship(
        "RegionalDistrict",
        foreign_keys=[id_to_regional_district],
    )

    id_to_energy_unit = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_REFDATA}.gs_sys_energy_units.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )
    to_energy_unit = db.relationship(
        "EnergyUnit",
        foreign_keys=[id_to_energy_unit],
    )

    id_union_energy_system = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_REFDATA}.gs_sys_union_energy_systems.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )
    union_energy_system = db.relationship(
        "UnionEnergySystem",
        foreign_keys=[id_union_energy_system],
    )

    source_oes_name = db.Column(db.String(500), nullable=True)

    transfer_value = db.Column(Numeric(25, 16))

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    @property
    def is_annual(self) -> bool:
        return self.month_number == EE_TRANSFER_PERIOD_YEAR

    @property
    def from_display_name(self) -> str:
        res = self.from_regional_energy_system
        if res is not None:
            return res.name or "—"
        rd = self.from_regional_district
        if rd is not None:
            return rd.name or rd.name_full or "—"
        return "—"

    @property
    def to_display_name(self) -> str:
        if self.to_regional_energy_system is not None:
            return self.to_regional_energy_system.name or "—"
        if self.to_foreign_border_country is not None:
            return self.to_foreign_border_country.name or "—"
        if self.to_regional_district is not None:
            return self.to_regional_district.name or self.to_regional_district.name_full or "—"
        if self.to_energy_unit is not None:
            return self.to_energy_unit.name or "—"
        return "—"

    def __repr__(self) -> str:
        period = "год" if self.is_annual else f"мес.{self.month_number}"
        return (
            f"<RegionalEnergySystemTransfer id={self.id} "
            f"from_res={self.id_from_regional_energy_system} "
            f"from_rd={self.id_from_regional_district} "
            f"to_res={self.id_to_regional_energy_system} "
            f"to_country={self.id_to_foreign_border_country} "
            f"to_rd={self.id_to_regional_district} "
            f"to_eu={self.id_to_energy_unit} "
            f"year={self.year_number} period={period} value={self.transfer_value}>"
        )
