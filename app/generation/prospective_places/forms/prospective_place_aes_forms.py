# -*- coding: utf-8 -*-
"""Формы для перспективных площадок АЭС."""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, IntegerField
from wtforms.validators import DataRequired, Length, Optional, NumberRange


def _coerce_regional_district(value):
    """Преобразует значение SelectField в int или None."""
    if value is None or value == "" or value == "0":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_int_optional(value):
    """Преобразует значение в int или None."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class ProspectivePlaceAESAddForm(FlaskForm):
    """Форма добавления перспективной площадки АЭС."""

    site_name = StringField(
        "Наименование площадки размещения АЭС",
        validators=[DataRequired(message="Укажите наименование площадки."), Length(max=255)],
    )

    id_regional_district = SelectField(
        "Субъект Российской Федерации",
        coerce=_coerce_regional_district,
        choices=[],
        validators=[DataRequired(message="Выберите субъект Российской Федерации.")],
    )


class ProspectivePlaceAESEditForm(FlaskForm):
    """Форма редактирования перспективной площадки АЭС."""

    site_name = StringField(
        "Наименование площадки размещения АЭС",
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

    planned_capacity_mw = IntegerField(
        "Планируемая установленная генерирующая мощность АЭС, МВт",
        validators=[Optional(), NumberRange(min=0)],
    )

    planned_unit_capacity_mw = IntegerField(
        "Планируемая единичная мощность энергоблока, МВт",
        validators=[Optional(), NumberRange(min=0)],
    )

    selection_factor = TextAreaField(
        "Фактор отбора",
        validators=[Optional(), Length(max=255)],
    )


class MachineProspectivePlaceAESEditForm(FlaskForm):
    """Форма добавления/редактирования энергоблока перспективной площадки АЭС."""

    id_prospective_place_type = SelectField(
        "Тип площадки",
        coerce=_coerce_regional_district,
        choices=[],
        validators=[Optional()],
    )
    station_block_number = StringField(
        "Станционный номер блока",
        validators=[Optional(), Length(max=100)],
    )
    unit_type = StringField(
        "Тип энергоблока",
        validators=[Optional(), Length(max=255)],
    )
    unit_capacity_mw = StringField(
        "Установленная генерирующая мощность АЭС, МВт",
        validators=[Optional(), Length(max=100)],
    )
    possible_implementation_period = StringField(
        "Возможный срок реализации",
        validators=[Optional(), Length(max=50)],
    )
    service_life_years = IntegerField(
        "Срок эксплуатации АЭС, лет",
        validators=[Optional(), NumberRange(min=0)],
    )
    construction_period_years = IntegerField(
        "Срок строительства АЭС, лет",
        validators=[Optional(), NumberRange(min=0)],
    )
    max_annual_operating_hours = StringField(
        "Предельное годовое число часов использования мощности энергоблока, час",
        validators=[Optional(), Length(max=100)],
    )
    specific_fuel_cost_rub_per_kwh = StringField(
        "Удельная топливная составляющая эксплуатационных затрат в ценах текущего года, тыс. руб./кВт",
        validators=[Optional(), Length(max=100)],
    )
    id_year_specific_fuel_cost = SelectField(
        "Год данных (топливная составляющая)",
        coerce=_coerce_int_optional,
        choices=[],
        validators=[Optional()],
    )
    specific_fixed_operating_costs_thous_rub_per_kw = StringField(
        "Удельные условно постоянные эксплуатационные затраты (без амортизационных отчислений), тыс. руб. в ценах текущего года г./кВт",
        validators=[Optional(), Length(max=100)],
    )
    id_year_specific_fixed_operating_costs = SelectField(
        "Год данных (условно постоянные затраты)",
        coerce=_coerce_int_optional,
        choices=[],
        validators=[Optional()],
    )
    relative_auxiliary_power_consumption_pct = StringField(
        "Относительная величина расхода электрической энергии на собственные нужды АЭС, %",
        validators=[Optional(), Length(max=100)],
    )
    specific_capital_investment_thous_rub_per_kw = StringField(
        "Удельные капиталовложения в строительство АЭС в ценах текущего года (без НДС), тыс. руб./кВт",
        validators=[Optional(), Length(max=100)],
    )
    id_year_specific_capital_investment = SelectField(
        "Год данных (удельные капиталовложения)",
        coerce=_coerce_int_optional,
        choices=[],
        validators=[Optional()],
    )
    specific_decommissioning_cost_thous_rub_per_kw = StringField(
        "Удельные затраты на вывод из эксплуатации, тыс. руб./кВт",
        validators=[Optional(), Length(max=100)],
    )
    id_year_specific_decommissioning = SelectField(
        "Год данных (вывод из эксплуатации)",
        coerce=_coerce_int_optional,
        choices=[],
        validators=[Optional()],
    )
    emergency_state_probability = StringField(
        "Вероятность аварийного состояния",
        validators=[Optional(), Length(max=100)],
    )
    ozp = StringField("ОЗП", validators=[Optional(), Length(max=100)])
    vlp = StringField("ВЛП", validators=[Optional(), Length(max=100)])
    note = TextAreaField("Примечание", validators=[Optional()])
