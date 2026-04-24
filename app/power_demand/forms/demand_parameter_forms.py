# -*- coding: utf-8 -*-
"""Формы раздела параметров нагрузки (CSRF)."""
from flask_wtf import FlaskForm


class EmptyCSRFForm(FlaskForm):
    """Пустая форма только для CSRF-токена (как в refdata HiddenField csrf)."""
    pass
