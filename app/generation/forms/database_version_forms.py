# -*- coding: utf-8 -*-
"""Формы для управления версиями базы данных."""

from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField, IntegerField, TextAreaField
from wtforms.validators import DataRequired, Optional, Length, NumberRange, ValidationError, Regexp


class DatabaseVersionFilterForm(FlaskForm):
    """Форма списка/фильтрации версий базы данных."""
    csrf_token = HiddenField()

    # Для пакетного обновления
    version_ids = HiddenField("ID записей")

    # Поля редактируемых строк
    version_number = StringField(
        "Номер версии",
        validators=[
            DataRequired(message="Поле «Номер версии» обязательно."),
            Length(min=1, max=30, message="Длина номера версии от 1 до 30 символов."),
            Regexp(
                r"^[A-Za-zА-Яа-я0-9 ()\-]+$",
                message="Номер версии должен содержать только буквы, цифры, пробелы, дефисы и круглые скобки.",
            ),
        ],
        render_kw={
            "maxlength": 30,
            "pattern": "[A-Za-zА-Яа-я0-9 ()\\-]+",
            "title": "До 30 символов: буквы, цифры, пробелы, дефисы и круглые скобки.",
        },
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

    version_number = StringField(
        "Номер версии",
        validators=[
            DataRequired(message="Поле «Номер версии» обязательно."),
            Length(min=1, max=30, message="Длина номера версии от 1 до 30 символов."),
            Regexp(
                r"^[A-Za-zА-Яа-я0-9 ()\-]+$",
                message="Номер версии должен содержать только буквы, цифры, пробелы, дефисы и круглые скобки.",
            ),
        ],
        render_kw={
            "maxlength": 30,
            "pattern": "[A-Za-zА-Яа-я0-9 ()\\-]+",
            "title": "До 30 символов: буквы, цифры, пробелы, дефисы и круглые скобки.",
        },
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
        coerce=str,
        validators=[DataRequired(message="Поле «Создать на основе версии» обязательно.")],
        render_kw={
            "class": "form-select",
            "required": True
        }
    )

    refdata_source_version_id = SelectField(
        "Версия для копирования справочников",
        coerce=lambda x: int(x) if x and x not in ('None', '', None) else None,
        validators=[Optional()],
        render_kw={
            "class": "form-select",
            "data-required-parent": "empty"
        }
    )

    extend_years = IntegerField(
        "Продлить период (лет)",
        validators=[
            Optional(),
            NumberRange(min=0, max=100, message="Количество лет для продления должно быть в диапазоне от 0 до 100."),
        ],
        render_kw={"class": "form-control"},
    )

    def validate_refdata_source_version_id(self, field):
        parent_value = (self.parent_version_id.data or "").strip()
        if parent_value == "empty" and not field.data:
            raise ValidationError("Поле «Версия для копирования справочников» обязательно для пустой версии.")

    def validate_extend_years(self, field):
        """
        При создании на основе существующей версии просим указать,
        на сколько лет продлить период (можно 0 — без продления).
        """
        parent_value = (self.parent_version_id.data or "").strip()
        if parent_value and parent_value not in ("empty", "None", "none"):
            if field.data is None:
                raise ValidationError("Укажите, на сколько лет продлить период (можно 0 — без продления).")

