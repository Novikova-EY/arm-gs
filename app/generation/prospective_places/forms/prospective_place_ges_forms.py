# -*- coding: utf-8 -*-
"""Формы для перспективных площадок ГЭС."""
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


class ProspectivePlaceGESAddForm(FlaskForm):
    """Форма добавления перспективной площадки ГЭС."""

    site_name = StringField(
        "Наименование площадки размещения ГЭС",
        validators=[DataRequired(message="Укажите наименование площадки."), Length(max=255)],
    )

    id_regional_district = SelectField(
        "Субъект Российской Федерации",
        coerce=_coerce_regional_district,
        choices=[],
        validators=[DataRequired(message="Выберите субъект Российской Федерации.")],
    )


class ProspectivePlaceGESEditForm(FlaskForm):
    """Форма редактирования перспективной площадки ГЭС."""

    site_name = StringField(
        "Наименование площадки размещения ГЭС",
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

    regulation_type = StringField(
        "Вид регулирования",
        validators=[Optional(), Length(max=500)],
    )

    planned_capacity_mw = IntegerField(
        "Планируемая установленная генерирующая мощность ГЭС, МВт",
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

    id_prospective_place_type_ges = SelectField(
        "Тип площадки",
        coerce=_coerce_regional_district,
        choices=[],
        validators=[Optional()],
    )

    display_order = IntegerField(
        "Порядок отображения",
        validators=[Optional()],
    )


class ProspectivePlaceGesTepSourceEditForm(FlaskForm):
    """Перечень исходных технико-экономических показателей новых ГЭС по проектным (предпроектным) данным."""

    installed_capacity_mw = StringField(
        "Установленная генерирующая мощность, МВт",
        validators=[Optional(), Length(max=100)],
    )
    stage_1_capacity_mw = StringField(
        "1 очередь, МВт",
        validators=[Optional(), Length(max=100)],
    )
    stage_2_capacity_mw = StringField(
        "2 очередь, МВт",
        validators=[Optional(), Length(max=100)],
    )
    startup_complex_capacity_mw = StringField(
        "в т.ч. пусковой комплекс, МВт",
        validators=[Optional(), Length(max=100)],
    )
    units_count = IntegerField(
        "Количество агрегатов, шт.",
        validators=[Optional(), NumberRange(min=0)],
    )
    unit_capacity_mw = StringField(
        "Единичная мощность агрегата, МВт",
        validators=[Optional(), Length(max=100)],
    )
    hydro_turbine_type = StringField(
        "Тип гидротурбины",
        validators=[Optional(), Length(max=500)],
    )
    construction_period_years = ConstructionPeriodYearsField(
        "Срок строительства ГЭС, лет",
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
    generation_average_multiyear_million_kwh = StringField(
        "Среднемноголетняя выработка электроэнергии, млн кВтч",
        validators=[Optional(), Length(max=100)],
    )
    generation_medium_water_50pct_million_kwh = StringField(
        "Выработка электроэнергии при средневодных условиях (50% обеспеченности по каскаду), млн кВтч",
        validators=[Optional(), Length(max=100)],
    )
    generation_medium_water_management_year = StringField(
        "Водохозяйственный год для средневодных условий",
        validators=[Optional(), Length(max=255)],
    )
    generation_low_water_95pct_million_kwh = StringField(
        "Выработка электроэнергии при маловодных условиях (95% обеспеченности по каскаду), млн кВтч",
        validators=[Optional(), Length(max=100)],
    )
    generation_low_water_management_year = StringField(
        "Водохозяйственный год для маловодных условий",
        validators=[Optional(), Length(max=255)],
    )
    specific_capital_investment_thous_rub_per_kw = StringField(
        "Удельные капиталовложения в строительство (без НДС, за вычетом затрат на сооружение водохранилища для ГЭС), млн руб./МВт",
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
        "здания, сооружения, оборудование и водохранилище ГЭС",
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
