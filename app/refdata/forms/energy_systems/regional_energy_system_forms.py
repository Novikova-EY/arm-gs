"""Формы для «Региональные энергосистемы»."""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SelectMultipleField, HiddenField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from flask_wtf.file import FileField, FileAllowed, FileRequired


class RegionalEnergySystemFilterForm(FlaskForm):
    csrf_token = HiddenField()

    regional_energy_system_ids = HiddenField("ID записей")

    name = StringField(
        "Региональная энергосистема",
        validators=[
            DataRequired(message="Поле «Региональная энергосистема» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    name_full = StringField(
        "Полное наименование",
        validators=[
            DataRequired(message="Поле «Полное наименование» обязательно."),
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
    union_energy_system = SelectField(
        "ОЭС",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Выберите ОЭС.")],
    )
    regional_districts = SelectMultipleField(
        "Субъекты РФ",
        choices=[],
        coerce=int,
        validators=[Optional()],
        render_kw={"multiple": True},
    )

    regional_energy_system_delete = HiddenField("Удалить")

    # Фильтры
    regional_energy_system_filter = StringField(
        "Фильтр по региональной энергосистеме",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по наименованию региональной энергосистемы"},
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


class AddRegionalEnergySystemForm(FlaskForm):
    csrf_token = HiddenField()

    name = StringField(
        "Региональная энергосистема",
        validators=[
            DataRequired(message="Поле «Региональная энергосистема» обязательно."),
            Length(min=3, max=255, message="Длина от 3 до 255 символов."),
        ],
    )
    name_full = StringField(
        "Полное наименование",
        validators=[
            DataRequired(message="Поле «Полное наименование» обязательно."),
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
    union_energy_system = SelectField(
        "ОЭС",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Выберите ОЭС.")],
    )
    regional_districts = SelectMultipleField(
        "Субъекты РФ",
        choices=[],
        coerce=int,
        validators=[Optional()],
        render_kw={"multiple": True},
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