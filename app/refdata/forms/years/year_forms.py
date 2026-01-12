"""Формы для справочника «Годы»."""

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField, IntegerField
from wtforms.validators import DataRequired, Optional, NumberRange, Length


class YearFilterForm(FlaskForm):
    """Форма списка/фильтрации годов."""

    csrf_token = HiddenField()

    # Для пакетного обновления (в шаблоне используются массивы name="...[]")
    year_ids = HiddenField("ID записей")
    year_delete = HiddenField("Удалить")

    year_filter = StringField(
        "Фильтр по годам",
        validators=[Optional(), Length(max=50)],
        render_kw={"placeholder": "Поиск по году или признаку"},
    )

    # Пагинация
    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, "5 строк"), (10, "10 строк"), (25, "25 строк"), (50, "50 строк")],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddYearForm(FlaskForm):
    """Форма добавления записи года."""

    csrf_token = HiddenField()

    number = IntegerField(
        "Год",
        validators=[
            DataRequired(message="Поле «Год» обязательно."),
            NumberRange(min=1900, max=2200, message="Год должен быть в диапазоне 1900–2200."),
        ],
    )

    year_feature = SelectField(
        "Признак года",
        choices=[],  # Наполняется в контроллере
        coerce=int,
        validators=[DataRequired(message="Выберите признак года.")],
    )




