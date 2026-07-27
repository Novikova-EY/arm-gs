"""Формы для справочника «Типы топлива». """

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from flask_wtf.file import FileField, FileAllowed, FileRequired


class FuelFilterForm(FlaskForm):
    """Форма списка/фильтрации топлива."""
    csrf_token = HiddenField()

    # Для пакетного обновления
    fuel_ids = HiddenField("ID записей")

    # Поля редактируемых строк (в шаблоне рендерятся массивами name="name[]" и т.д.)
    name = StringField(
        "Тип топлива",
        validators=[
            DataRequired(message="Поле «Тип топлива» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    kod = StringField(
        "Код",
        validators=[Optional(), Length(max=20)],
    )
    fuel_type = SelectField(
        "Вид топлива",
        choices=[],  # Наполняется в контроллере
        coerce=int,
        validators=[DataRequired(message="Выберите вид топлива.")],
    )
    parent = SelectField(
        "Родительский вид",
        choices=[],  # Наполняется в контроллере
        coerce=int,
        validators=[Optional()],
    )

    # Флаг удаления строки (в шаблоне как массив checkbox'ов)
    fuel_delete = HiddenField("Удалить")

    # Поля фильтра
    fuel_filter = StringField(
        "Фильтр по типам топлива",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по типам топлива"},
    )
    fuel_type_filter = StringField(
        "Фильтр по видам топлива",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по видам топлива"},
    )
    # Пагинация
    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddFuelForm(FlaskForm):
    """Форма добавления записи топлива."""
    csrf_token = HiddenField()

    name = StringField(
        "Тип топлива",
        validators=[
            DataRequired(message="Поле «Тип топлива» обязательно."),
            Length(min=3, max=255, message="Длина от 3 до 255 символов."),
        ],
    )
    kod = StringField(
        "Код",
        validators=[Optional(), Length(max=20)],
    )
    fuel_type = SelectField(
        "Вид топлива",
        choices=[],  # Наполняется в контроллере
        coerce=int,
        validators=[DataRequired(message="Выберите вид топлива.")],
    )
    parent = SelectField(
        "Родительский вид",
        choices=[],  # Наполняется в контроллере
        coerce=int,
        validators=[Optional()],
    )


class FileUploadForm(FlaskForm):
    """Форма загрузки файла со справочными данными по топливу."""
    csrf_token = HiddenField()

    file = FileField(
        "Файл",
        validators=[
            FileRequired(message="Выберите файл для загрузки."),
            FileAllowed(["csv", "xls", "xlsx"], message="Допустимые форматы: csv, xls, xlsx."),
        ],
    )