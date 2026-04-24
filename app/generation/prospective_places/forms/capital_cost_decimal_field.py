# -*- coding: utf-8 -*-
"""DecimalField для капзатрат без ПИР: без квантования по places и без лишних нулей в поле."""
from __future__ import annotations

from wtforms.fields import DecimalField

from app.generation.prospective_places.forms.decimal_input_display import format_decimal_plain_str


class CapitalCostDecimalField(DecimalField):
    """Как DecimalField с ``places=None``, но ``_value()`` убирает хвостовые нули."""

    def __init__(self, label=None, validators=None, **kwargs):
        kwargs.setdefault("places", None)
        super().__init__(label, validators, **kwargs)

    def _value(self):
        if self.raw_data:
            return self.raw_data[0]
        return format_decimal_plain_str(self.data)
