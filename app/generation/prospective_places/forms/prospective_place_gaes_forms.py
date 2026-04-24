# -*- coding: utf-8 -*-
"""Формы для перспективных площадок ГАЭС."""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, IntegerField
from wtforms.widgets import HiddenInput
from wtforms.validators import DataRequired, Length, Optional, NumberRange

from app.generation.prospective_places.forms.capital_cost_decimal_field import CapitalCostDecimalField
from app.generation.prospective_places.forms.construction_period_years_field import (
    ConstructionPeriodYearsField,
    validate_at_most_one_decimal_digit,
)


def _coerce_regional_district(value):
    """Преобразует значение SelectField в int или None."""
    if value is None or value == "" or value == "0":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class ProspectivePlaceGAESAddForm(FlaskForm):
    """Форма добавления перспективной площадки ГАЭС."""

    site_name = StringField(
        "Наименование площадки размещения ГАЭС",
        validators=[DataRequired(message="Укажите наименование площадки."), Length(max=255)],
    )

    id_regional_district = SelectField(
        "Субъект Российской Федерации",
        coerce=_coerce_regional_district,
        choices=[],
        validators=[DataRequired(message="Выберите субъект Российской Федерации.")],
    )


class ProspectivePlaceGAESEditForm(FlaskForm):
    """Форма редактирования перспективной площадки ГАЭС."""

    site_name = StringField(
        "Наименование площадки размещения ГАЭС",
        validators=[Optional(), Length(max=255)],
    )

    id_regional_district = SelectField(
        "Субъект Российской Федерации",
        coerce=_coerce_regional_district,
        choices=[],
        validators=[Optional()],
    )

    id_regional_energy_system = SelectField(
        "РЭС",
        coerce=_coerce_regional_district,
        choices=[],
        validators=[Optional()],
    )

    geo_location = TextAreaField(
        "Географическое расположение площадки",
        validators=[Optional(), Length(max=500)],
    )

    project_initiator = StringField(
        "Инициатор проекта",
        validators=[Optional(), Length(max=500)],
    )

    water_body = StringField(
        "Водный объект",
        validators=[Optional(), Length(max=500)],
    )

    planned_capacity_mw = IntegerField(
        "Планируемая установленная генерирующая мощность ГАЭС, МВт",
        validators=[Optional(), NumberRange(min=0)],
    )

    general_scheme_commissioning_period = StringField(
        "Генеральная схема до 2042 года (Период ввода в эксплуатацию). Распоряжение Правительства от 30.12.2024 №4153-р",
        validators=[Optional(), Length(max=255)],
    )

    construction_period_years = ConstructionPeriodYearsField(
        "Срок строительства по Протоколу Минэнерго от 25.05.2022 №РГ/07-0003пр (без учета срока выполнения ПИР- 2 года), лет",
        validators=[Optional(), NumberRange(min=0), validate_at_most_one_decimal_digit],
    )

    id_prospective_place_type_gaes = SelectField(
        "Тип площадки",
        coerce=_coerce_regional_district,
        choices=[],
        validators=[Optional()],
    )

    display_order = IntegerField(
        "Порядок отображения",
        validators=[Optional()],
    )


class ProspectivePlaceGaesTepSourceEditForm(FlaskForm):
    """Перечень исходных технико-экономических показателей новых ГАЭС по проектным (предпроектным) данным."""

    installed_capacity_mw_generator_mode = StringField(
        "Установленная мощность в генераторном режиме, МВт",
        validators=[Optional(), Length(max=100)],
    )
    startup_complex_capacity_mw_generator_mode = StringField(
        "в т.ч. пусковой комплекс, МВт",
        validators=[Optional(), Length(max=100)],
    )
    stage_1_capacity_mw_generator_mode = StringField(
        "1 очередь в генераторном режиме, МВт",
        validators=[Optional(), Length(max=100)],
    )
    stage_2_capacity_mw_generator_mode = StringField(
        "2 очередь в генераторном режиме, МВт",
        validators=[Optional(), Length(max=100)],
    )
    unit_capacity_mw_generator_mode = StringField(
        "Единичная мощность агрегата, МВт",
        validators=[Optional(), Length(max=100)],
    )
    installed_capacity_mw_pump_mode = StringField(
        "Установленная мощность в насосном режиме, МВт",
        validators=[Optional(), Length(max=100)],
    )
    startup_complex_capacity_mw_pump_mode = StringField(
        "в т.ч. пусковой комплекс, МВт",
        validators=[Optional(), Length(max=100)],
    )
    stage_1_capacity_mw_pump_mode = StringField(
        "1 очередь в насосном режиме, МВт",
        validators=[Optional(), Length(max=100)],
    )
    stage_2_capacity_mw_pump_mode = StringField(
        "2 очередь в насосном режиме, МВт",
        validators=[Optional(), Length(max=100)],
    )
    unit_capacity_mw_pump_mode = StringField(
        "Единичная мощность агрегата, МВт",
        validators=[Optional(), Length(max=100)],
    )
    units_count = IntegerField(
        "Количество агрегатов, шт.",
        validators=[Optional(), NumberRange(min=0)],
    )
    hydro_turbine_type = StringField(
        "Тип гидротурбины",
        validators=[Optional(), Length(max=500)],
    )
    ccium_turbine_mode = StringField(
        "генераторный режим",
        validators=[Optional(), Length(max=100)],
    )
    ccium_pump_mode = StringField(
        "насосный режим",
        validators=[Optional(), Length(max=100)],
    )
    construction_period_years = ConstructionPeriodYearsField(
        "Срок строительства ГАЭС, лет",
        validators=[Optional(), NumberRange(min=0), validate_at_most_one_decimal_digit],
    )
    construction_increment_year_01_mw = StringField("Прирост мощности, 1 год", validators=[Optional(), Length(max=100)])
    construction_increment_year_02_mw = StringField("Прирост мощности, 2 год", validators=[Optional(), Length(max=100)])
    construction_increment_year_03_mw = StringField("Прирост мощности, 3 год", validators=[Optional(), Length(max=100)])
    construction_increment_year_04_mw = StringField("Прирост мощности, 4 год", validators=[Optional(), Length(max=100)])
    construction_increment_year_05_mw = StringField("Прирост мощности, 5 год", validators=[Optional(), Length(max=100)])
    construction_increment_year_06_mw = StringField("Прирост мощности, 6 год", validators=[Optional(), Length(max=100)])
    construction_increment_year_07_mw = StringField("Прирост мощности, 7 год", validators=[Optional(), Length(max=100)])
    construction_increment_year_08_mw = StringField("Прирост мощности, 8 год", validators=[Optional(), Length(max=100)])
    construction_increment_year_09_mw = StringField("Прирост мощности, 9 год", validators=[Optional(), Length(max=100)])
    construction_increment_year_10_mw = StringField("Прирост мощности, 10 год", validators=[Optional(), Length(max=100)])
    construction_increment_year_11_mw = StringField("Прирост мощности, 11 год", validators=[Optional(), Length(max=100)])
    construction_increment_year_12_mw = StringField("Прирост мощности, 12 год", validators=[Optional(), Length(max=100)])
    specific_semifixed_operating_costs_thous_rub_per_kw = StringField(
        "Удельные условно-постоянные эксплуатационные затраты (без амортизационных отчислений), млн руб./МВт",
        validators=[Optional(), Length(max=100)],
    )
    id_year_specific_semifixed_operating_costs = SelectField(
        "год предоставления информации",
        coerce=_coerce_regional_district,
        choices=[],
        validators=[Optional()],
    )
    generation_average_multiyear_billion_kwh = StringField(
        "Годовая выработка электроэнергии, млрд кВт·ч",
        validators=[Optional(), Length(max=100)],
    )
    generation_average_multiyear_million_kwh_stage_1 = StringField(
        "Годовая выработка электроэнергии, 1 очередь, млн кВт·ч",
        validators=[Optional(), Length(max=100)],
    )
    generation_average_multiyear_million_kwh_stage_2 = StringField(
        "Годовая выработка электроэнергии, 2 очередь, млн кВт·ч",
        validators=[Optional(), Length(max=100)],
    )
    generation_medium_water_50pct_billion_kwh = StringField(
        "Выработка электроэнергии при средневодных условиях (50% обеспеченности по каскаду), млн кВт·ч",
        validators=[Optional(), Length(max=100)],
    )
    generation_low_water_95pct_billion_kwh = StringField(
        "Выработка электроэнергии при маловодных условиях (95% обеспеченности по каскаду), млн кВт·ч",
        validators=[Optional(), Length(max=100)],
    )
    annual_charging_electricity_consumption_million_kwh = StringField(
        "Годовое потребление электрической энергии ГАЭС на заряд, млн кВт·ч",
        validators=[Optional(), Length(max=100)],
    )
    annual_charging_electricity_consumption_million_kwh_stage_1 = StringField(
        "Годовое потребление электрической энергии ГАЭС на заряд, 1 очередь, млн кВт·ч",
        validators=[Optional(), Length(max=100)],
    )
    annual_charging_electricity_consumption_million_kwh_stage_2 = StringField(
        "Годовое потребление электрической энергии ГАЭС на заряд, 2 очередь, млн кВт·ч",
        validators=[Optional(), Length(max=100)],
    )
    specific_capital_investment_thous_rub_per_kw = StringField(
        "Удельные капиталовложения в строительство (с бассейнами), млн руб./МВт",
        validators=[Optional(), Length(max=100)],
    )
    id_year_specific_capital_investment = IntegerField(
        "год предоставления информации",
        widget=HiddenInput(),
        validators=[Optional()],
    )
    capital_cost_wo_pir_total_million_rub = CapitalCostDecimalField(
        "Капитальные затраты (без ПИР)",
        validators=[Optional()],
    )
    id_year_capital_cost_wo_pir_total = SelectField(
        "год предоставления информации",
        coerce=_coerce_regional_district,
        choices=[],
        validators=[Optional()],
    )
    capital_cost_wo_pir_ges_with_reservoir_million_rub = CapitalCostDecimalField(
        "здания, сооружения, оборудование и бассейнами ГАЭС",
        validators=[Optional()],
    )
    id_year_capital_cost_wo_pir_ges_with_reservoir = SelectField(
        "год предоставления информации",
        coerce=_coerce_regional_district,
        choices=[],
        validators=[Optional()],
    )
    capital_cost_wo_pir_svm_million_rub = CapitalCostDecimalField(
        "СВМ",
        validators=[Optional()],
    )
    id_year_capital_cost_wo_pir_svm = SelectField(
        "год предоставления информации",
        coerce=_coerce_regional_district,
        choices=[],
        validators=[Optional()],
    )
    note = TextAreaField("Примечание", validators=[Optional()])
