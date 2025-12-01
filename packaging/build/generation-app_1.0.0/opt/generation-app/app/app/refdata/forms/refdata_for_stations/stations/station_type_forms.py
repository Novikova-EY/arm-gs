"""Формы для справочника «Типы электростанций (StationType)».
"""

from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, SelectField
from wtforms.validators import DataRequired, Optional, Length, NumberRange


class StationTypeFilterForm(FlaskForm):
    csrf_token = HiddenField()

    # Пакетное обновление
    ids = HiddenField("ID записей")
    name = StringField(
        "Тип электростанции",
        validators=[
            DataRequired(message="Поле «Тип электростанции» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    delete = HiddenField("Удалить")

    # Фильтр
    station_type_filter = StringField(
        "Фильтр по наименованию",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по типам электростанций"},
    )

    # Пагинация
    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddStationTypeForm(FlaskForm):
    csrf_token = HiddenField()

    name = StringField(
        "Тип электростанции",
        validators=[
            DataRequired(message="Поле «Тип электростанции» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )


