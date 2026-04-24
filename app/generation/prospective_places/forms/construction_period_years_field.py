# -*- coding: utf-8 -*-
"""Поле «срок строительства, лет»: до одного знака после запятой, ввод с точкой."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from wtforms import ValidationError
from wtforms.fields import DecimalField
from wtforms.widgets import NumberInput

from app.generation.prospective_places.forms.decimal_input_display import format_decimal_plain_str


def validate_at_most_one_decimal_digit(form, field):
    if field.data is None:
        return
    exp = field.data.normalize().as_tuple().exponent
    if exp < -1:
        raise ValidationError("Допускается не более одного знака после запятой.")


class ConstructionPeriodYearsField(DecimalField):
    """DecimalField: шаг 0.1, без лишних нулей в значении поля при отображении."""

    def __init__(self, label=None, validators=None, **kwargs):
        kwargs.setdefault("places", None)
        w = kwargs.pop("widget", None) or NumberInput(step="0.1", min="0")
        super().__init__(label, validators, widget=w, **kwargs)

    def _value(self):
        if self.raw_data:
            return self.raw_data[0]
        return format_decimal_plain_str(self.data)

    def process_formdata(self, valuelist):
        """Принимает и запятую, и точку как разделитель."""
        if valuelist:
            raw = (valuelist[0] or "").strip().replace(",", ".")
            valuelist = [raw] if raw else []
        super().process_formdata(valuelist)
