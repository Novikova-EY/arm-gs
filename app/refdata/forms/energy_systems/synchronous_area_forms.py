"""Формы для «Синхронные зоны»."""
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField, IntegerField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from flask_wtf.file import FileField, FileAllowed, FileRequired


class SynchronousAreaFilterForm(FlaskForm):
    csrf_token = HiddenField()

    synchronous_area_ids = HiddenField("ID записей")

    number = StringField(
        "Номер синхронной зоны",
        validators=[
            DataRequired(message="Поле «Номер синхронной зоны» обязательно."),
            Length(min=1, max=255, message="Длина от 1 до 255 символов."),
        ],
    )
    name = StringField(
        "Наименование синхронной зоны",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Введите наименование синхронной зоны"},
    )
    regional_district = SelectField(
        "Субъект РФ",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Выберите субъект РФ.")],
    )

    synchronous_area_delete = HiddenField("Удалить")

    # Порядок отображения (для единообразия с другими справочниками; в списке редактируется напрямую)
    display_order = IntegerField(
        "Порядок отображения",
        validators=[Optional()],
    )

    # Фильтр
    synchronous_area_filter = StringField(
        "Фильтр по синхронным зонам",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по наименованию синхронной зоны"},
    )

    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddSynchronousAreaForm(FlaskForm):
    csrf_token = HiddenField()

    number = StringField(
        "Номер синхронной зоны",
        validators=[
            DataRequired(message="Поле «Номер синхронной зоны» обязательно."),
            Length(min=1, max=255, message="Длина от 1 до 255 символов."),
        ],
    )
    name = StringField(
        "Наименование синхронной зоны",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Введите наименование синхронной зоны"},
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