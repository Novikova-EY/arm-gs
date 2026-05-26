# -*- coding: utf-8 -*-
"""
Перечень исходных технико-экономических показателей новых ГЭС
по проектным (предпроектным) данным.

Одна запись привязана к площадке StationProspectivePlaceGES.
"""
from sqlalchemy.sql import func
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin


class ProspectivePlaceGesTepSource(db.Model, AuditMixin):
    __tablename__ = "gs_gen_ges_tep_source_project_indicators"
    __table_args__ = (
        Index(
            "ix_ges_tep_source_id_station",
            "id_station_prospective_place_ges",
        ),
        Index(
            "ix_ges_tep_source_id_prospective_place_type_ges",
            "id_prospective_place_type_ges",
        ),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    id_station_prospective_place_ges = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.gs_gen_station_prospective_place_ges.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    station_prospective_place_ges = db.relationship(
        "StationProspectivePlaceGES",
        back_populates="ges_tep_source_indicators",
        foreign_keys=[id_station_prospective_place_ges],
    )

    id_prospective_place_type_ges = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.gs_gen_prospective_place_types_ges.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    prospective_place_type_ges = db.relationship(
        "ProspectivePlaceTypeGES",
        back_populates="ges_tep_source_indicators",
        foreign_keys=[id_prospective_place_type_ges],
    )

    # Установленная генерирующая мощность, МВт
    installed_capacity_mw = db.Column(db.String(100), nullable=True)
    # 1 очередь, МВт
    stage_1_capacity_mw = db.Column(db.String(100), nullable=True)
    # 2 очередь, МВт
    stage_2_capacity_mw = db.Column(db.String(100), nullable=True)
    # Пусковой комплекс, МВт
    startup_complex_capacity_mw = db.Column(db.String(100), nullable=True)

    # Количество агрегатов
    units_count = db.Column(db.Integer, nullable=True)

    # Мощность одного агрегата, МВт
    unit_capacity_mw = db.Column(db.String(100), nullable=True)

    # Тип гидротурбины
    hydro_turbine_type = db.Column(db.String(500), nullable=True)

    # Срок строительства, лет (до одного знака после запятой)
    construction_period_years = db.Column(db.Numeric(12, 1), nullable=True)

    # Очередность строительства (прирост вводимой мощности), МВт по годам 1–12
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

    # Удельные условно-постоянные эксплуатационные затраты (без амортизации), млн руб./МВт
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

    # Среднемноголетняя выработка электроэнергии, млн кВт·ч
    generation_average_multiyear_million_kwh = db.Column(db.String(100), nullable=True)

    # Выработка электроэнергии при среднем уровне воды, млн кВт·ч
    generation_medium_water_50pct_million_kwh = db.Column(db.String(100), nullable=True)
    # Год управления уровнем воды при среднем уровне воды
    generation_medium_water_management_year = db.Column(db.String(255), nullable=True)

    # Выработка электроэнергии при низком уровне воды, млн кВт·ч
    generation_low_water_95pct_million_kwh = db.Column(db.String(100), nullable=True)
    # Год управления уровнем воды при низком уровне воды
    generation_low_water_management_year = db.Column(db.String(255), nullable=True)

    # Удельные капиталовложения (без НДС), за вычетом затрат на водохранилище, млн руб./МВт
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

    # Стоимость (капзатраты без ПИР), млн руб
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
        return f"<ProspectivePlaceGesTepSource id={self.id} station_id={self.id_station_prospective_place_ges!r}>"
