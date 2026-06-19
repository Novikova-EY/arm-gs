"""Формы для справочника «Виды экономической деятельности (EconomicActivityType)».
"""

from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, SelectField, IntegerField
from wtforms.validators import DataRequired, Optional, Length, NumberRange


class EconomicActivityTypeFilterForm(FlaskForm):
    csrf_token = HiddenField()

    # Пакетное обновление
    ids = HiddenField("ID записей")
    name = StringField(
        "Полное наименование",
        validators=[
            DataRequired(message="Поле «Полное наименование» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    delete = HiddenField("Удалить")

    # Фильтр
    economic_activity_type_filter = StringField(
        "Фильтр по наименованию",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по видам экономической деятельности"},
    )

    # Пагинация
    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddEconomicActivityTypeForm(FlaskForm):
    csrf_token = HiddenField()

    name = StringField(
        "Полное наименование",
        validators=[
            DataRequired(message="Поле «Полное наименование» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )

    name_2 = StringField(
        "Краткое наименование",
        validators=[Optional(), Length(max=255, message="Длина не более 255 символов.")],
    )

    display_order = IntegerField(
        "Порядок отображения",
        validators=[Optional(), NumberRange(min=0)],
    )


