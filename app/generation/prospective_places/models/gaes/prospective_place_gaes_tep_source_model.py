# -*- coding: utf-8 -*-
"""
Перечень исходных технико-экономических показателей новых ГАЭС
по проектным (предпроектным) данным.

Одна запись привязана к площадке StationProspectivePlaceGAES.
"""
from sqlalchemy.sql import func
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin


class ProspectivePlaceGaesTepSource(db.Model, AuditMixin):
    __tablename__ = "gs_gen_gaes_tep_source_project_indicators"
    __table_args__ = (
        Index(
            "ix_gaes_tep_source_id_station",
            "id_station_prospective_place_gaes",
        ),
        Index(
            "ix_gaes_tep_source_id_prospective_place_type_gaes",
            "id_prospective_place_type_gaes",
        ),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    id_station_prospective_place_gaes = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.gs_gen_station_prospective_place_gaes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    station_prospective_place_gaes = db.relationship(
        "StationProspectivePlaceGAES",
        back_populates="gaes_tep_source_indicators",
        foreign_keys=[id_station_prospective_place_gaes],
    )

    id_prospective_place_type_gaes = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.gs_gen_prospective_place_types_gaes.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    prospective_place_type_gaes = db.relationship(
        "ProspectivePlaceTypeGAES",
        back_populates="gaes_tep_source_indicators",
        foreign_keys=[id_prospective_place_type_gaes],
    )

    # Установленная мощность в генераторном режиме (всего → в т.ч. ПК → 1–2 очередь)
    installed_capacity_mw_generator_mode = db.Column(db.String(100), nullable=True)
    startup_complex_capacity_mw_generator_mode = db.Column(db.String(100), nullable=True)
    stage_1_capacity_mw_generator_mode = db.Column(db.String(100), nullable=True)
    stage_2_capacity_mw_generator_mode = db.Column(db.String(100), nullable=True)

    # Установленная мощность в насосном режиме (всего → в т.ч. ПК → 1–2 очередь)
    installed_capacity_mw_pump_mode = db.Column(db.String(100), nullable=True)
    startup_complex_capacity_mw_pump_mode = db.Column(db.String(100), nullable=True)
    stage_1_capacity_mw_pump_mode = db.Column(db.String(100), nullable=True)
    stage_2_capacity_mw_pump_mode = db.Column(db.String(100), nullable=True)

    # Количество агрегатов
    units_count = db.Column(db.Integer, nullable=True)

    # Единичная мощность агрегата (генераторный / насосный режим)
    unit_capacity_mw_generator_mode = db.Column(db.String(100), nullable=True)
    unit_capacity_mw_pump_mode = db.Column(db.String(100), nullable=True)

    # Тип гидротурбины
    hydro_turbine_type = db.Column(db.String(500), nullable=True)

    # Число часов использования установленной мощности в сутки, час/сутки
    ccium_turbine_mode = db.Column(db.String(100), nullable=True)
    ccium_pump_mode = db.Column(db.String(100), nullable=True)

    # Срок строительства ГАЭС (до одного знака после запятой)
    construction_period_years = db.Column(db.Numeric(12, 1), nullable=True)

    # Очередность строительства (прирост вводимой мощности)
    construction_increment_year_01_mw = db.Column(db.String(100), nullable=True)
    construction_increment_year_02_mw = db.Column(db.String(100), nullable=True)
    construction_increment_year_03_mw = db.Column(db.String(100), nullable=True)
    construction_increment_year_04_mw = db.Column(db.String(100), nullable=True)
    construction_increment_year_05_mw = db.Column(db.String(100), nullable=True)
    construction_increment_year_06_mw = db.Column(db.String(100), nullable=True)
    construction_increment_year_07_mw = db.Column(db.String(100), nullable=True)
    construction_increment_year_08_mw = db.Column(db.String(100), nullable=True)
    construction_increment_year_09_mw = db.Column(db.String(100), nullable=True)
    construction_increment_year_10_mw = db.Column(db.String(100), nullable=True)
    construction_increment_year_11_mw = db.Column(db.String(100), nullable=True)
    construction_increment_year_12_mw = db.Column(db.String(100), nullable=True)

    # Удельные условно-постоянные эксплуатационные затраты (без амортизационных отчислений), млн руб./МВт
    specific_semifixed_operating_costs_thous_rub_per_kw = db.Column(db.String(100), nullable=True)
    id_year_specific_semifixed_operating_costs = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_years.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    year_specific_semifixed_operating_costs = db.relationship(
        "Year",
        foreign_keys=[id_year_specific_semifixed_operating_costs],
    )

    # Годовая выработка электроэнергии, млн кВтч
    generation_average_multiyear_million_kwh = db.Column(db.String(100), nullable=True)
    # Годовая выработка электроэнергии — 1 очередь, млн кВтч
    generation_average_multiyear_million_kwh_stage_1 = db.Column(db.String(100), nullable=True)
    # Годовая выработка электроэнергии — 2 очередь, млн кВтч
    generation_average_multiyear_million_kwh_stage_2 = db.Column(db.String(100), nullable=True)

    # Выработка электроэнергии при средневодных условиях (50% обеспеченности по каскаду), млн кВтч
    generation_medium_water_50pct_million_kwh = db.Column(db.String(100), nullable=True)

    # Выработка электроэнергии при маловодных условиях (95% обеспеченности по каскаду), млн кВтч
    generation_low_water_95pct_million_kwh = db.Column(db.String(100), nullable=True)

    # Годовое потребление электрической энергии ГАЭС на заряд, млн кВтч
    annual_charging_electricity_consumption_million_kwh = db.Column(db.String(100), nullable=True)
    # Годовое потребление электрической энергии ГАЭС на заряд, млн кВтч — по очередям
    annual_charging_electricity_consumption_million_kwh_stage_1 = db.Column(db.String(100), nullable=True)
    annual_charging_electricity_consumption_million_kwh_stage_2 = db.Column(db.String(100), nullable=True)

    # Удельные капиталовложения в строительство (с бассейнами), млн руб./МВт
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

    # Стоимость (капзатраты без ПИР), млн руб; год — справочник Year
    capital_cost_wo_pir_total_million_rub = db.Column(db.Numeric(24, 4), nullable=True)
    id_year_capital_cost_wo_pir_total = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_years.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    year_capital_cost_wo_pir_total = db.relationship(
        "Year",
        foreign_keys=[id_year_capital_cost_wo_pir_total],
    )

    # Стоимость (капзатраты без ПИР), в том числе ГЭС (с водохранилищем), млн руб
    capital_cost_wo_pir_ges_with_reservoir_million_rub = db.Column(db.Numeric(24, 4), nullable=True)
    id_year_capital_cost_wo_pir_ges_with_reservoir = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_years.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    year_capital_cost_wo_pir_ges_with_reservoir = db.relationship(
        "Year",
        foreign_keys=[id_year_capital_cost_wo_pir_ges_with_reservoir],
    )

    # Стоимость (капзатраты без ПИР), в том числе СВМ, млн руб
    capital_cost_wo_pir_svm_million_rub = db.Column(db.Numeric(24, 4), nullable=True)
    id_year_capital_cost_wo_pir_svm = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_years.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    year_capital_cost_wo_pir_svm = db.relationship(
        "Year",
        foreign_keys=[id_year_capital_cost_wo_pir_svm],
    )

    # Капиталовложения в строительство ГАЭС с приведением к ценам текущего года (без НДС), млрд. руб.
    capital_investment_gaes_construction_current_prices_billion_rub = db.Column(db.String(100), nullable=True)

    # Примечание
    note = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<ProspectivePlaceGaesTepSource id={self.id} station_id={self.id_station_prospective_place_gaes!r}>"
