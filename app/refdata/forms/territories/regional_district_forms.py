"""Формы для справочника «Субъекты РФ»."""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from flask_wtf.file import FileField, FileAllowed, FileRequired


class RegionalDistrictFilterForm(FlaskForm):
    csrf_token = HiddenField()

    regional_district_ids = HiddenField("ID записей")

    name = StringField(
        "Наименование субъекта РФ",
        validators=[
            DataRequired(message="Поле «Наименование субъекта РФ» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    name_full = StringField(
        "Полное наименование субъекта РФ",
        validators=[
            DataRequired(message="Поле «Полное наименование субъекта РФ» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    name_rp = StringField(
        "Наименование (в родительном падеже)",
        validators=[
            DataRequired(message="Поле «Наименование (в родительном падеже)» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    federal_district = SelectField(
        "Федеральный округ",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Выберите федеральный округ.")],
    )
    energy_zone = SelectField(
        "Энергозона",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Выберите энергозону.")],
    )
    synchronous_area = SelectField(
        "Синхронная зона",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Выберите синхронную зону.")],
    )

    regional_district_delete = HiddenField("Удалить")

    # Фильтры
    regional_district_filter = StringField(
        "Фильтр по субъекту РФ",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по наименованию субъекта РФ"},
    )
    federal_district_filter = StringField(
        "Фильтр по федеральному округу",
        validators=[Optional(), Length(max=100)],
    )
    energy_zone_filter = SelectField(
        "Фильтр по энергозоне",
        choices=[],
        coerce=int,
        validators=[Optional()],
    )
    synchronous_area_filter = SelectField(
        "Фильтр по синхронной зоне",
        choices=[],
        coerce=int,
        validators=[Optional()],
    )

    page = HiddenField(default=1)

    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddRegionalDistrictForm(FlaskForm):
    csrf_token = HiddenField()

    name = StringField(
        "Наименование субъекта РФ",
        validators=[
            DataRequired(message="Поле «Наименование субъекта РФ» обязательно."),
            Length(min=3, max=255, message="Длина от 3 до 255 символов."),
        ],
    )
    name_full = StringField(
        "Полное наименование субъекта РФ",
        validators=[
            DataRequired(message="Поле «Полное наименование субъекта РФ» обязательно."),
            Length(min=3, max=255, message="Длина от 3 до 255 символов."),
        ],
    )
    name_rp = StringField(
        "Наименование (в родительном падеже)",
        validators=[
            DataRequired(message="Поле «Наименование (в родительном падеже)» обязательно."),
            Length(min=3, max=255, message="Длина от 3 до 255 символов."),
        ],
    )
    federal_district = SelectField(
        "Федеральный округ",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Выберите федеральный округ.")],
    )
    energy_zone = SelectField(
        "Энергозона",
        choices=[],
        coerce=int,
        validators=[Optional()],
    )
    synchronous_area = SelectField(
        "Синхронная зона",
        choices=[],
        coerce=int,
        validators=[Optional()],
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