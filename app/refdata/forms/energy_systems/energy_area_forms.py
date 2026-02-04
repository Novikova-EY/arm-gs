"""Формы для «Энергоузлы»."""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from flask_wtf.file import FileField, FileAllowed, FileRequired


class EnergyAreaFilterForm(FlaskForm):
    csrf_token = HiddenField()

    energy_area_ids = HiddenField("ID записей")

    name = StringField(
        "Энергоузел",
        validators=[
            DataRequired(message="Поле «Энергоузел» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    regional_district = SelectField(
        "Субъект РФ",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Поиск по наименованию энергоузла.")],
    )
    regional_energy_system = SelectField(
        "Региональная энергосистема",
        choices=[],
        coerce=int,
    )
    union_energy_system = SelectField(
        "ОЭС",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Выберите ОЭС.")],
    )

    energy_area_delete = HiddenField("Удалить")

    # Фильтры
    energy_area_filter = StringField(
        "Фильтр по энергоузлам",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Введите энергоузел"},
    )
    regional_district_filter = StringField(
        "Фильтр по субъекту РФ",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Введите субъект РФ"},
    )
    regional_energy_system_filter = StringField(
        "Фильтр по региональной энергосистеме",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Введите региональную энергосистему"},
    )
    union_energy_system_filter = StringField(
        "Фильтр по ОЭС",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Введите ОЭС"},
    )

    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddEnergyAreaForm(FlaskForm):
    csrf_token = HiddenField()

    name = StringField(
        "Энергоузел",
        validators=[
            DataRequired(message="Поле «Энергоузел» обязательно."),
            Length(min=3, max=255, message="Длина от 3 до 255 символов."),
        ],
    )
    regional_district = SelectField(
        "Субъект РФ",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Выберите субъект РФ.")],
    )
    regional_energy_system = SelectField(
        "Региональная энергосистема",
        choices=[],
        coerce=int,
        validators=[Optional()],
    )
    union_energy_system = SelectField(
        "ОЭС",
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