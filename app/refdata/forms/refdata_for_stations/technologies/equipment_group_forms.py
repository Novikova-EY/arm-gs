"""Формы для справочника «Типы групп оборудования (EquipmentGroup)».
"""

from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, SelectField
from wtforms.validators import DataRequired, Optional, Length, NumberRange


class EquipmentGroupFilterForm(FlaskForm):
    csrf_token = HiddenField()

    # Пакетное обновление
    equipment_group_ids = HiddenField("ID записей")
    
    name = StringField(
        "Тип группы оборудования",
        validators=[
            DataRequired(message="Поле «Тип группы оборудования» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    
    technology_type = SelectField(
        "Тип технологии",
        choices=[],  # Наполняется в контроллере
        coerce=int,
        validators=[Optional()],
    )
    
    technology_availability = SelectField(
        "Доступность технологии",
        choices=[],  # Наполняется в контроллере
        coerce=int,
        validators=[Optional()],
    )
    
    delete = HiddenField("Удалить")

    # Фильтры
    equipment_group_filter = StringField(
        "Фильтр по наименованию",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по типам групп оборудования"},
    )
    
    technology_type_filter = StringField(
        "Фильтр по типу технологии",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по типам технологии"},
    )
    
    technology_availability_filter = StringField(
        "Фильтр по доступности технологии",
        validators=[Optional(), Length(max=100)],
        render_kw={"placeholder": "Поиск по доступности технологии"},
    )

    # Пагинация
    page = HiddenField(default=1)
    per_page = SelectField(
        "Количество строк на странице",
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)],
    )


class AddEquipmentGroupForm(FlaskForm):
    csrf_token = HiddenField()

    name = StringField(
        "Тип группы оборудования",
        validators=[
            DataRequired(message="Поле «Тип группы оборудования» обязательно."),
            Length(min=2, max=255, message="Длина от 2 до 255 символов."),
        ],
    )
    
    technology_type = SelectField(
        "Тип технологии",
        choices=[],  # Наполняется в контроллере
        coerce=int,
        validators=[Optional()],
    )
    
    technology_availability = SelectField(
        "Доступность технологии",
        choices=[],  # Наполняется в контроллере
        coerce=int,
        validators=[Optional()],
    )


