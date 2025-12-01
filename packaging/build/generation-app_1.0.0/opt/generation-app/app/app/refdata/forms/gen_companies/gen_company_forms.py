"""Формы для справочника «Генерирующие компании»."""
from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, SelectField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from flask_wtf.file import FileField, FileAllowed, FileRequired


class GenCompanyFilterForm(FlaskForm):
    csrf_token = HiddenField()

    gen_company_ids = HiddenField("ID записей")

    name = StringField(
        "Наименование генерирующей компании",
        validators=[
            DataRequired(message="Поле «Наименование генерирующей компании» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )

    gen_company_filter = StringField(
        "Фильтр по наименованию",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по названию генерирующей компании"},
    )

    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddGenCompanyForm(FlaskForm):
    csrf_token = HiddenField()

    name = StringField(
        "Наименование генерирующей компании",
        validators=[
            DataRequired(message="Поле «Наименование генерирующей компании» обязательно."),
            Length(min=3, max=255, message="Длина от 3 до 255 символов."),
        ],
    )


class FileUploadForm(FlaskForm):
    csrf_token = HiddenField()

    file = FileField(
        "Файл",
        validators=[
            FileRequired(message="Выберите файл для загрузки."),
            FileAllowed(["csv", "xls", "xlsx"], message="Допустимые форматы: csv, xls, xlsx."),
        ],
    )