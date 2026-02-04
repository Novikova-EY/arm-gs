"""Формы для справочника «Виды топлива». """

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField, IntegerField
from wtforms.validators import DataRequired, Optional, Length, NumberRange
from flask_wtf.file import FileField, FileAllowed, FileRequired


class FuelTypeFilterForm(FlaskForm):
    """Форма списка/фильтрации вида топлива."""
    csrf_token = HiddenField()

    # Для пакетного обновления
    fuel_ids = HiddenField("ID записей")

    # Поля редактируемых строк (в шаблоне рендерятся массивами name="name[]" и т.д.)
    name = StringField(
        "Вид топлива",
        validators=[
            DataRequired(message="Поле «Вид топлива» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )

    # Флаг удаления строки (в шаблоне как массив checkbox'ов)
    fuel_delete = HiddenField("Удалить")

    # Поля фильтра
    fuel_type_filter = StringField(
        "Фильтр по видам топлива",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по видам топлива"},
    )
    # Порядок отображения (для единообразия с другими справочниками; в списке редактируется напрямую)
    display_order = IntegerField(
        "Порядок отображения",
        validators=[Optional()],
    )
    # Пагинация
    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddFuelTypeForm(FlaskForm):
    """Форма добавления записи вида топлива."""
    csrf_token = HiddenField()

    name = StringField(
        "Вид топлива",
        validators=[
            DataRequired(message="Поле Вид топлива» обязательно."),
            Length(min=3, max=255, message="Длина от 3 до 255 символов."),
        ],
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