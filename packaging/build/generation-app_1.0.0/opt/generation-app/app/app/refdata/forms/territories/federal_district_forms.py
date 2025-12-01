"""Формы для «Федеральные округа (ФО)»."""
from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, SelectField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from flask_wtf.file import FileField, FileAllowed, FileRequired


class FederalDistrictFilterForm(FlaskForm):
    csrf_token = HiddenField()

    federal_district_ids = HiddenField("ID записей")

    name = StringField(
        "Короткое наименование ФО",
        validators=[
            DataRequired(message="Поле «Короткое наименование ФО» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    name_full = StringField(
        "Полное наименование ФО",
        validators=[
            DataRequired(message="Поле «Полное наименование ФО» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    name_abr = StringField(
        "Сокращенное наименование ФО",
        validators=[
            DataRequired(message="Поле «Сокращенное наименование ФО» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )

    federal_district_filter = StringField(
        "Фильтр по ФО",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по наименованию федерального округа"},
    )

    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddFederalDistrictForm(FlaskForm):
    csrf_token = HiddenField()

    name = StringField(
        "Короткое наименование ФО",
        validators=[
            DataRequired(message="Поле «Короткое наименование ФО» обязательно."),
            Length(min=3, max=255, message="Длина от 3 до 255 символов."),
        ],
    )
    name_full = StringField(
        "Полное наименование ФО",
        validators=[
            DataRequired(message="Поле «Полное наименование ФО» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    name_abr = StringField(
        "Сокращенное наименование ФО",
        validators=[
            DataRequired(message="Поле «Сокращенное наименование ФО» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )


class FileUploadFederalDistrictForm(FlaskForm):
    csrf_token = HiddenField()

    file = FileField(
        "Файл",
        validators=[
            FileRequired(message="Выберите файл для загрузки."),
            FileAllowed(["csv", "xls", "xlsx"], message="Допустимые форматы: csv, xls, xlsx."),
        ],
    )