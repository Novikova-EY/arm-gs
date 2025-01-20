from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SelectMultipleField, HiddenField
from wtforms.validators import Length, DataRequired, Optional, NumberRange


class ResFilterForm(FlaskForm):
    """Форма фильтрации и управления списком региональных энергосистем"""
    csrf_token = HiddenField()

    res_ids = HiddenField("ID")

    name = StringField(
        'Региональная энергосистема',
        validators=[
            DataRequired(message="Поле 'Региональная энергосистема' обязательно для заполнения."),
            Length(min=2, max=255, message="Длина имени должна быть от 2 до 255 символов.")
        ]
    )

    oes = SelectField(
        'ОЭС',
        choices=[],  # Заполняется в контроллере
        coerce=int,
        validators=[DataRequired(message="Пожалуйста, выберите ОЭС.")]
    )

    regions = SelectMultipleField(
        'Субъекты РФ',
        choices=[],  # Заполняется в контроллере
        coerce=int,
        validators=[Optional()],  # Выбор субъектов необязателен
        render_kw={'multiple': True}  # Позволяет выбирать несколько значений
    )

    res_delete = HiddenField("Удалить")

    res_filter = StringField(
        "Фильтр по региональной энергосистеме",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите региональную энергосистему"}
    )

    oes_filter = StringField(
        "Фильтр по ОЭС",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите ОЭС"}
    )

    page = HiddenField(default=1)

    per_page = SelectField(
        'Количество строк на странице',
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)]
    )


class AddResForm(FlaskForm):
    """Форма добавления новой региональной энергосистемы"""
    csrf_token = HiddenField()

    name = StringField(
        'Региональная энергосистема',
        validators=[
            DataRequired(message="Поле 'Региональная энергосистема' обязательно для заполнения."),
            Length(min=3, max=255, message="Длина имени должна быть от 3 до 255 символов.")
        ]
    )

    oes = SelectField(
        'ОЭС',
        choices=[],  # Заполняется в контроллере
        coerce=int,
        validators=[DataRequired(message="Пожалуйста, выберите ОЭС.")]
    )

    regions = SelectMultipleField(
        'Субъекты РФ',
        choices=[],  # Заполняется в контроллере
        coerce=int,
        validators=[DataRequired(message="Пожалуйста, выберите субъекты РФ.")],
        render_kw={'multiple': True}  # Позволяет выбирать несколько значений
    )


class FileUploadForm(FlaskForm):
    """Форма для загрузки файлов"""
    csrf_token = HiddenField()

    file = HiddenField(
        'Файл',
        validators=[DataRequired(message="Файл обязателен для загрузки.")]
    )
