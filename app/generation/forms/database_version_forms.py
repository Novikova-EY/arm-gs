# -*- coding: utf-8 -*-
"""Формы для управления версиями базы данных."""

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, Optional, Length, NumberRange


class DatabaseVersionFilterForm(FlaskForm):
    """Форма списка/фильтрации версий базы данных."""
    csrf_token = HiddenField()

    # Для пакетного обновления
    version_ids = HiddenField("ID записей")

    # Поля редактируемых строк
    version_number = IntegerField(
        "Номер версии",
        validators=[
            DataRequired(message="Поле «Номер версии» обязательно."),
            NumberRange(min=1, message="Номер версии должен быть больше 0."),
        ],
    )
    
    name = StringField(
        "Название версии",
        validators=[
            DataRequired(message="Поле «Название версии» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )

    description = TextAreaField(
        "Описание",
        validators=[Optional(), Length(max=1000)],
    )

    # Флаг удаления строки
    version_delete = HiddenField("Удалить")

    # Поля фильтра
    version_filter = StringField(
        "Фильтр по названию",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по названию версии"},
    )

    # Пагинация
    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddDatabaseVersionForm(FlaskForm):
    """Форма добавления новой версии базы данных."""
    csrf_token = HiddenField()

    version_number = IntegerField(
        "Номер версии",
        validators=[
            DataRequired(message="Поле «Номер версии» обязательно."),
            NumberRange(min=1, message="Номер версии должен быть больше 0."),
        ],
    )

    name = StringField(
        "Название версии",
        validators=[
            DataRequired(message="Поле «Название версии» обязательно."),
            Length(min=3, max=255, message="Длина от 3 до 255 символов."),
        ],
    )

    description = TextAreaField(
        "Описание",
        validators=[Optional(), Length(max=1000)],
        render_kw={"placeholder": "Краткое описание версии (необязательно)"},
    )
    
    parent_version_id = SelectField(
        "Создать на основе версии",
        coerce=lambda x: int(x) if x and x != 'None' and x != '' else None,
        validators=[Optional()],
        render_kw={"class": "form-control"}
    )


