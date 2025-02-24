from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField
from wtforms.validators import Length, DataRequired, Optional, NumberRange

class OesFilterForm(FlaskForm):
    """Форма фильтрации и управления списком типов топлива"""
    csrf_token = HiddenField()

    fuel_ids = HiddenField("ID")

    name = StringField(
        'Тип топлива',
        validators=[
            DataRequired(message="Поле 'Тип топлива' обязательно для заполнения."),
            Length(min=2, max=255, message="Длина имени должна быть от 2 до 255 символов.")
        ]
    )
    
    fuel_type = SelectField(
        'Вид топлива',
        choices=[],  # Заполняется в контроллере
        coerce=int,
        validators=[DataRequired(message="Пожалуйста, выберите вид топлива.")]
    )

    fuel_delete = HiddenField("Удалить")
   
    fuel_filter = StringField(
        "Фильтр по типам топлива",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите тип топлива"}
    )

    fuel_type_filter = StringField(
        "Фильтр по видам топлива",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите вид топлива"}
    )

    page = HiddenField(default=1)
    
    per_page = SelectField(
        'Количество строк на странице',
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)]
    )

class AddOesForm(FlaskForm):
    """Форма добавления нового типа топлива"""
    csrf_token = HiddenField()
    
    name = StringField(
        'Тип топлива',
        validators=[
            DataRequired(message="Поле 'Тип топлива' обязательно для заполнения."),
            Length(min=3, max=255, message="Длина имени должна быть от 3 до 255 символов.")
        ]
    )
    fuel_type = SelectField(
        'Вид топлива',
        choices=[],  # Заполняется в контроллере
        coerce=int,
        validators=[DataRequired(message="Пожалуйста, выберите вид топлива.")]
    )

class FileUploadForm(FlaskForm):
    """Форма для загрузки файлов"""
    csrf_token = HiddenField()
    
    file = HiddenField(
        'Файл',
        validators=[DataRequired(message="Файл обязателен для загрузки.")]
    )