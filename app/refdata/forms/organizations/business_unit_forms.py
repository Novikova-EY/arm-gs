# -*- coding: utf-8 -*-
"""Формы для «Бизнес единицы»."""
from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, SelectField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from flask_wtf.file import FileField, FileAllowed, FileRequired


class BusinessUnitFilterForm(FlaskForm):
    csrf_token = HiddenField()

    business_unit_ids = HiddenField("ID записей")

    name = StringField(
        "Короткое наименование бизнес единицы",
        validators=[
            DataRequired(message="Поле «Короткое наименование бизнес единицы» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    name_full = StringField(
        "Полное наименование бизнес единицы",
        validators=[
            DataRequired(message="Поле «Полное наименование бизнес единицы» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    name_abr = StringField(
        "Сокращенное наименование бизнес единицы",
        validators=[
            DataRequired(message="Поле «Сокращенное наименование бизнес единицы» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )

    business_unit_filter = StringField(
        "Фильтр по бизнес единицам",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по наименованию бизнес единицы"},
    )

    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, "5 строк"), (10, "10 строк"), (25, "25 строк"), (50, "50 строк")],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddBusinessUnitForm(FlaskForm):
    csrf_token = HiddenField()

    name = StringField(
        "Короткое наименование бизнес единицы",
        validators=[
            DataRequired(message="Поле «Короткое наименование бизнес единицы» обязательно."),
            Length(min=3, max=255, message="Длина от 3 до 255 символов."),
        ],
    )
    name_full = StringField(
        "Полное наименование бизнес единицы",
        validators=[
            DataRequired(message="Поле «Полное наименование бизнес единицы» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    name_abr = StringField(
        "Сокращенное наименование бизнес единицы",
        validators=[
            DataRequired(message="Поле «Сокращенное наименование бизнес единицы» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )


class FileUploadBusinessUnitForm(FlaskForm):
    csrf_token = HiddenField()

    file = FileField(
        "Файл",
        validators=[
            FileRequired(message="Выберите файл для загрузки."),
            FileAllowed(["csv", "xls", "xlsx"], message="Допустимые форматы: csv, xls, xlsx."),
        ],
    )
