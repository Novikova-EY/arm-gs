# -*- coding: utf-8 -*-
"""Характеристики топлива для расчёта выбросов действующих ТЭС (лист «Хар.топл.»)."""
from sqlalchemy import ForeignKeyConstraint, Numeric, UniqueConstraint
from sqlalchemy.sql import func

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ECOLOGY, SCHEMA_REFDATA


class OperatingTesFuelCharacteristic(db.Model, AuditMixin):
    """Общие для всех уровней характеристики топлива по году и версии БД."""

    __tablename__ = "gs_eco_operating_tes_fuel_chars"
    __table_args__ = (
        UniqueConstraint(
            "territory_slug",
            "fuel_key",
            "year_number",
            "database_version_id",
            name="uq_eco_ot_fuel_char_slice_key_year_ver",
        ),
        ForeignKeyConstraint(
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_eco_ot_fuel_char_year_ver",
        ),
        {"schema": SCHEMA_ECOLOGY},
    )

    # Уникальный идентификатор записи
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Общий набор хранится под vsego; поле сохранено для совместимости со старыми срезами.
    territory_slug = db.Column(
        db.String(40), nullable=False, default="vsego", server_default="vsego", index=True
    )

    # Ключ вида топлива (gas_natural, mazut, donetsk, …)
    fuel_key = db.Column(db.String(80), nullable=False, index=True)

    # Год: Year.number + database_version_id (composite FK)
    year_number = db.Column(db.Integer, nullable=False, index=True)
    year = db.relationship(
        "Year",
        lazy="noload",
        primaryjoin=(
            "and_(Year.number==OperatingTesFuelCharacteristic.year_number, "
            "Year.database_version_id==OperatingTesFuelCharacteristic.database_version_id)"
        ),
        foreign_keys="[OperatingTesFuelCharacteristic.year_number, OperatingTesFuelCharacteristic.database_version_id]",
        viewonly=True,
    )

    # Зольность Ар, %
    ash = db.Column(Numeric(36, 16), nullable=True)

    # Доля золы аун, д.ед.
    ash_share = db.Column(Numeric(36, 16), nullable=True)

    # Потери тепла от механической неполноты сгорания qч, %
    q_mech = db.Column(Numeric(36, 16), nullable=True)

    # Сернистость Sp, %
    sulfur = db.Column(Numeric(36, 16), nullable=True)

    # Доля оксидов серы x, д.ед.
    sulfur_share = db.Column(Numeric(36, 16), nullable=True)

    # Низшая теплота сгорания QH, кДж/кг
    qh_kj = db.Column(Numeric(36, 16), nullable=True)

    # Низшая теплота сгорания QH, ккал/кг
    qh_kcal = db.Column(Numeric(36, 16), nullable=True)

    # Удельный выброс оксидов азота bj, кг/т у.т.
    bj = db.Column(Numeric(36, 16), nullable=True)

    # Национальный коэффициент эмиссии CO2 (KCO2), т/т у.т.
    k_co2 = db.Column(Numeric(36, 16), nullable=True)

    # Коэффициент доли потери тепла от химической неполноты сгорания R, %
    r_chem = db.Column(Numeric(36, 16), nullable=True)

    # Потери тепла от химической неполноты сгорания q3, %
    q_chem = db.Column(Numeric(36, 16), nullable=True)

    # Коэффициент перевода в условное топливо, т у.т./т
    tut_per_t = db.Column(Numeric(36, 16), nullable=True)

    # Энергосодержание, ТДж/тыс. т натур. топлива
    tj_per_kt = db.Column(Numeric(36, 16), nullable=True)

    # Коэффициент эмиссии CO2, т СО2/ТДж
    t_co2_per_tj = db.Column(Numeric(36, 16), nullable=True)

    # Примечание
    note = db.Column(db.Text, nullable=True)

    # Источник характеристик (выпадающий список листа «Справочник»)
    source_key = db.Column(db.String(40), nullable=True)

    # Дата и время создания записи
    created_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Дата и время последнего изменения записи
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # Версия базы данных, FK -> gs_sys.gs_database_versions
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<OperatingTesFuelCharacteristic id={self.id} "
            f"fuel={self.fuel_key} year={self.year_number}>"
        )
