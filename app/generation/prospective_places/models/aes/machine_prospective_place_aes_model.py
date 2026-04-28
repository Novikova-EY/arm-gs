# -*- coding: utf-8 -*-
"""
MachineProspectivePlaceAES model (Энергоблок перспективной площадки размещения АЭС).

Поля:
- FK: id_prospective_place_type -> ProspectivePlaceTypeAES / gs_gen.gs_gen_prospective_place_types (типы площадок АЭС)
- Текстовые: станционный номер блока, тип энергоблока, мощность энергоблока, предельное годовое число часов,
  удельная топливная составляющая, удельные условно постоянные затраты, относительная величина расхода,
  удельные капиталовложения, удельные затраты на вывод, вероятность аварийного состояния,
  ОЗП, ВЛП, примечание
- Возможный срок реализации (год или дата, напр. 2042 или 31.12.2042)
"""
from sqlalchemy.sql import func
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin


class MachineProspectivePlaceAES(db.Model, AuditMixin):
    __tablename__ = 'gs_gen_machine_prospective_place_aes'
    __table_args__ = (
        Index('ix_machine_prospective_place_aes_id_station_prospective_place', 'id_station_prospective_place_aes'),
        Index('ix_machine_prospective_place_aes_id_prospective_place_type', 'id_prospective_place_type'),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK -> StationProspectivePlaceAES
    id_station_prospective_place_aes = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.gs_gen_station_prospective_place_aes.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    station_prospective_place_aes = db.relationship(
        'StationProspectivePlaceAES',
        back_populates='machine_prospective_places',
        foreign_keys=[id_station_prospective_place_aes],
    )

    # FK -> ProspectivePlaceTypeAES (справочник типов площадки АЭС)
    id_prospective_place_type = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.gs_gen_prospective_place_types.id", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )
    prospective_place_type = db.relationship(
        "ProspectivePlaceTypeAES",
        back_populates='machine_prospective_places',
        foreign_keys=[id_prospective_place_type],
    )

    # Станционный номер блока (текст)
    station_block_number = db.Column(db.String(100), nullable=True)

    # Текстовые поля
    # Тип энергоблока
    unit_type = db.Column(db.String(255), nullable=True)
    # Мощность энергоблока, МВт
    unit_capacity_mw = db.Column(db.String(100), nullable=True)
    # Предельное годовое число часов использования мощности энергоблока, час
    max_annual_operating_hours = db.Column(db.String(100), nullable=True)
    # Удельная топливная составляющая эксплуатационных затрат в ценах текущего года, тыс. руб./кВт
    specific_fuel_cost_rub_per_kwh = db.Column(db.String(100), nullable=True)
    id_year_specific_fuel_cost = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_years.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    year_specific_fuel_cost = db.relationship(
        "Year",
        foreign_keys=[id_year_specific_fuel_cost],
    )

    # Удельные условно постоянные эксплуатационные затраты (без амортизационных отчислений), тыс. руб. в ценах текущего года г./кВт
    specific_fixed_operating_costs_thous_rub_per_kw = db.Column(db.String(100), nullable=True)
    id_year_specific_fixed_operating_costs = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_years.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    year_specific_fixed_operating_costs = db.relationship(
        "Year",
        foreign_keys=[id_year_specific_fixed_operating_costs],
    )
    # Относительная величина расхода электрической энергии на собственные нужды АЭС, %
    relative_auxiliary_power_consumption_pct = db.Column(db.String(100), nullable=True)
    # Удельные капиталовложения в строительство АЭС в ценах текущего года (без НДС), тыс. руб./кВт
    specific_capital_investment_thous_rub_per_kw = db.Column(db.String(100), nullable=True)
    id_year_specific_capital_investment = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_years.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    year_specific_capital_investment = db.relationship(
        "Year",
        foreign_keys=[id_year_specific_capital_investment],
    )

    # Удельные затраты на вывод из эксплуатации, тыс. руб./кВт
    specific_decommissioning_cost_thous_rub_per_kw = db.Column(db.String(100), nullable=True)
    id_year_specific_decommissioning = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_years.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    year_specific_decommissioning = db.relationship(
        "Year",
        foreign_keys=[id_year_specific_decommissioning],
    )
    # Вероятность аварийного состояния, о.е
    emergency_state_probability = db.Column(db.String(100), nullable=True)
    # ОЗП, о.е
    ozp = db.Column(db.String(100), nullable=True)
    # ВЛП, о.е
    vlp = db.Column(db.String(100), nullable=True)
    # Примечание
    note = db.Column(db.Text, nullable=True)

    # Возможный срок реализации (год: 2042 или дата: 31.12.2042)
    possible_implementation_period = db.Column(db.String(50), nullable=True)

    # Срок эксплуатации АЭС, лет
    service_life_years = db.Column(db.Integer, nullable=True)
    # Срок строительства АЭС, лет
    construction_period_years = db.Column(db.Integer, nullable=True)

    # timestamps (UTC, server-side)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    def __repr__(self) -> str:
        return f"<MachineProspectivePlaceAES id={self.id} unit_type={self.unit_type!r}>"
