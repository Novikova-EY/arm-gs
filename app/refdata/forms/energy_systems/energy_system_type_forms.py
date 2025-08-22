# -*- coding: utf-8 -*-
"""
Формы для справочника «Типы энергосистем».
Используется Flask-WTF (CSRF включён глобально).
"""
from flask_wtf import FlaskForm
from wtforms import StringField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Length

class EnergySystemTypeFilterForm(FlaskForm):
    """Форма фильтрации/поиска в списке типов энергосистем."""
    energy_system_type_filter = StringField(
        "Поиск по наименованию",
        render_kw={"placeholder": "Поиск по наименованию типа энергосистемы"}
    )
    # скрытое поле для текущей страницы (помогает при POST/redirect)
    page = HiddenField()

class AddEnergySystemTypeForm(FlaskForm):
    """Форма создания/редактирования записи типа энергосистемы."""
    name = StringField(
        "Наименование типа энергосистемы",
        validators=[DataRequired(message="Укажите наименование."), Length(max=255)],
        render_kw={"placeholder": "Например: ОЭС, РЭС, СЭС ..."}
    )
    submit = SubmitField("Сохранить")
