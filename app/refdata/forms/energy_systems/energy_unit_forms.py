"""Формы для «Энергоузлы»."""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from flask_wtf.file import FileField, FileAllowed, FileRequired


class EnergyUnitFilterForm(FlaskForm):
    csrf_token = HiddenField()

    energy_unit_ids = HiddenField("ID записей")

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
        validators=[DataRequired(message="Выберите субъект РФ.")],
    )
    regional_energy_system = SelectField(
        "Региональная энергосистема",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Выберите региональную энергосистему.")],
    )
    union_energy_system = SelectField(
        "ОЭС",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Выберите ОЭС.")],
    )

    energy_unit_delete = HiddenField("Удалить")

    # Фильтры
    energy_unit_filter = StringField(
        "Фильтр по энергоузлам",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по наименованию энергоузла"},
    )
    regional_district_filter = StringField(
        "Фильтр по субъекту РФ",
        validators=[Optional(), Length(max=100)],
    )
    regional_energy_system_filter = StringField(
        "Фильтр по региональной энергосистеме",
        validators=[Optional(), Length(max=100)],
    )
    union_energy_system_filter = StringField(
        "Фильтр по ОЭС",
        validators=[Optional(), Length(max=100)],
    )

    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddEnergyUnitForm(FlaskForm):
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