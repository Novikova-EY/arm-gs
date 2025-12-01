"""Формы для справочника «Типы агрегатов (PGUTesMachineType)».
"""

from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, SelectField
from wtforms.validators import DataRequired, Optional, Length, NumberRange


class PGUTesMachineTypeFilterForm(FlaskForm):
    csrf_token = HiddenField()

    # Пакетное обновление
    ids = HiddenField("ID записей")
    name = StringField(
        "Тип агрегата",
        validators=[
            DataRequired(message="Поле «Тип агрегата» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    delete = HiddenField("Удалить")

    # Фильтр
    pgu_tes_machine_type_filter = StringField(
        "Фильтр по наименованию",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по типам агрегатов"},
    )

    # Пагинация
    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddPGUTesMachineTypeForm(FlaskForm):
    csrf_token = HiddenField()

    name = StringField(
        "Тип агрегата",
        validators=[
            DataRequired(message="Поле «Тип агрегата» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )


