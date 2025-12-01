# -*- coding: utf-8 -*-
"""
Формы для справочника «Типы энергосистем».
Используется Flask-WTF (CSRF включен глобально).
"""
from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Length

class EnergySystemTypeFilterForm(FlaskForm):
    """Форма фильтрации/поиска в списке типов энергосистем."""
    energy_system_type_filter = StringField(
        "Поиск по наименованию",
        render_kw={"placeholder": "Поиск по наименованию типа части энергосистемы России"}
    )
    # скрытое поле для текущей страницы (помогает при POST/redirect)
    page = HiddenField()

class AddEnergySystemTypeForm(FlaskForm):
    """Форма создания/редактирования записи части энергосистемы России."""
    name = StringField(
        "Наименование типа части энергосистемы России",
        validators=[DataRequired(message="Укажите наименование типа части энергосистемы России."), Length(max=255)],
        render_kw={"placeholder": "Наименование типа части энергосистемы России"}
    )
    submit = SubmitField("Сохранить")
