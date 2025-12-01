"""Формы для «Энергозоны»."""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from flask_wtf.file import FileField, FileAllowed, FileRequired


class EnergyZoneFilterForm(FlaskForm):
    csrf_token = HiddenField()

    energy_zone_ids = HiddenField("ID записей")

    number = StringField(
        "Номер энергозоны",
        validators=[
            DataRequired(message="Поле «Номер энергозоны» обязательно."),
            Length(min=1, max=255, message="Длина от 1 до 255 символов."),
        ],
    )
    name = StringField(
        "Наименование энергозоны",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Введите наименование энергозоны"},
    )
    regional_district = SelectField(
        "Субъект РФ",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Выберите субъект РФ.")],
    )

    energy_zone_delete = HiddenField("Удалить")

    # Фильтр
    energy_zone_filter = StringField(
        "Фильтр по энергозонам",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по наименованию энергозоны"},
    )

    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddEnergyZoneForm(FlaskForm):
    csrf_token = HiddenField()

    number = StringField(
        "Номер энергозоны",
        validators=[
            DataRequired(message="Поле «Номер энергозоны» обязательно."),
            Length(min=1, max=255, message="Длина от 1 до 255 символов."),
        ],
    )
    name = StringField(
        "Наименование энергозоны",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Введите наименование энергозоны"},
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