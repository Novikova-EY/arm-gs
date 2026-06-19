"""Формы для справочника «Зарубежные страны, имеющие общие границы с РФ»."""

from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, SelectField, IntegerField
from wtforms.validators import DataRequired, Optional, Length, NumberRange


class ForeignBorderCountryFilterForm(FlaskForm):
    csrf_token = HiddenField()

    ids = HiddenField("ID записей")
    name = StringField(
        "Наименование страны",
        validators=[
            DataRequired(message="Поле «Наименование страны» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    delete = HiddenField("Удалить")

    display_order = IntegerField(
        "Порядок отображения",
        validators=[Optional()],
    )

    foreign_border_country_filter = StringField(
        "Фильтр по наименованию",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по странам"},
    )

    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddForeignBorderCountryForm(FlaskForm):
    csrf_token = HiddenField()

    name = StringField(
        "Наименование страны",
        validators=[
            DataRequired(message="Поле «Наименование страны» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
