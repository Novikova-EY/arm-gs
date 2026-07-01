"""Формы для справочника «Типы затрат на производство ЭЭ и ТЭ»."""

from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, SelectField, IntegerField
from wtforms.validators import DataRequired, Optional, Length, NumberRange


class ElectricityProductionCostTypeFilterForm(FlaskForm):
    csrf_token = HiddenField()

    ids = HiddenField("ID записей")
    name = StringField(
        "Наименование",
        validators=[
            DataRequired(message="Поле «Наименование» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    delete = HiddenField("Удалить")

    electricity_production_cost_type_filter = StringField(
        "Фильтр по наименованию",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по наименованию"},
    )

    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddElectricityProductionCostTypeForm(FlaskForm):
    csrf_token = HiddenField()

    name = StringField(
        "Наименование",
        validators=[
            DataRequired(message="Поле «Наименование» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )

    cost_code = IntegerField(
        "Код затрат",
        validators=[Optional(), NumberRange(min=0)],
    )
