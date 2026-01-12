"""Формы для «Объединенные энергосистемы (ОЭС)»."""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField, IntegerField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from flask_wtf.file import FileField, FileAllowed, FileRequired


class UnionEnergySystemFilterForm(FlaskForm):
    csrf_token = HiddenField()

    union_energy_system_ids = HiddenField("ID записей")

    name = StringField(
        "Наименование ОЭС",
        validators=[
            DataRequired(message="Поле «Наименование ОЭС» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    name_full = StringField(
        "Полное наименование ОЭС",
        validators=[
            DataRequired(message="Поле «Полное наименование ОЭС» обязательно."),
            Length(min=3, max=255, message="Длина от 3 до 255 символов."),
        ],
    )
    energy_system_type = SelectField(
        "Тип энергосистемы",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Выберите тип энергосистемы.")],
    )
    display_order = IntegerField(
        "Порядок отображения",
        validators=[Optional()],
    )

    union_energy_system_delete = HiddenField("Удалить")

    # Фильтры
    union_energy_system_filter = StringField(
        "Фильтр по ОЭС",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по наименованию ОЭС"},
    )

    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddUnionEnergySystemForm(FlaskForm):
    csrf_token = HiddenField()

    name = StringField(
        "Наименование ОЭС",
        validators=[
            DataRequired(message="Поле «Наименование ОЭС» обязательно."),
            Length(min=3, max=255, message="Длина от 3 до 255 символов."),
        ],
    )
    name_full = StringField(
        "Полное наименование ОЭС",
        validators=[
            DataRequired(message="Поле «Полное наименование ОЭС» обязательно."),
            Length(min=3, max=255, message="Длина от 3 до 255 символов."),
        ],
    )
    energy_system_type = SelectField(
        "Тип энергосистемы",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Выберите тип энергосистемы.")],
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