# app/auth/forms/users_forms.py
from flask_wtf import FlaskForm

class UsersBulkForm(FlaskForm):
    """Мини-форма только ради CSRF. Поля не описываем — всё остальное читаем из request.form."""
    pass
