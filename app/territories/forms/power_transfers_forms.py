# -*- coding: utf-8 -*-
"""Формы страницы перетоков мощности энергоузлов."""
from flask_wtf import FlaskForm
from wtforms import HiddenField, SelectField, StringField
from wtforms.validators import DataRequired, Optional, Length


class PowerTransferFilterForm(FlaskForm):
    csrf_token = HiddenField()

    power_transfer_filter = StringField(
        "Поиск",
        validators=[Optional(), Length(max=200)],
        render_kw={"placeholder": "Поиск по энергоузлу, субъекту РФ, направлению"},
    )


class AddPowerTransferForm(FlaskForm):
    csrf_token = HiddenField()

    id_energy_unit = SelectField(
        "Энергоузел",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Выберите энергоузел.")],
    )
    id_regional_district = SelectField(
        "Субъект РФ",
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Выберите субъект РФ.")],
    )
    direction = StringField(
        "Направление",
        validators=[Optional(), Length(max=2000)],
        render_kw={"placeholder": "Направление перетока"},
    )
