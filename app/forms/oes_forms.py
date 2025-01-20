from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField
from wtforms.validators import Length, DataRequired, Optional, NumberRange

class OesFilterForm(FlaskForm):
    """Форма фильтрации и управления списком ОЭС"""
    csrf_token = HiddenField()

    oes_ids = HiddenField("ID")

    name = StringField(
        'Наименование ОЭС',
        validators=[
            DataRequired(message="Поле 'Наименование ОЭС' обязательно для заполнения."),
            Length(min=2, max=255, message="Длина имени должна быть от 2 до 255 символов.")
        ]
    )
    
    oes_type = SelectField(
        'Тип энергосистемы',
        choices=[],  # Заполняется в контроллере
        coerce=int,
        validators=[DataRequired(message="Пожалуйста, выберите тип энергосистемы.")]
    )

    oes_delete = HiddenField("Удалить")
   
    oes_filter = StringField(
        "Название ОЭС",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите название ОЭС"}
    )

    page = HiddenField(default=1)
    
    per_page = SelectField(
        'Количество строк на странице',
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)]
    )

class AddOesForm(FlaskForm):
    """Форма добавления новой ОЭС"""
    csrf_token = HiddenField()
    
    name = StringField(
        'Наименование ОЭС',
        validators=[
            DataRequired(message="Поле 'Наименование ОЭС' обязательно для заполнения."),
            Length(min=3, max=255, message="Длина имени должна быть от 3 до 255 символов.")
        ]
    )
    oes_type = SelectField(
        'Тип энергосистемы',
        choices=[],  # Заполняется в контроллере
        coerce=int,
        validators=[DataRequired(message="Пожалуйста, выберите тип энергосистемы.")]
    )

class FileUploadForm(FlaskForm):
    """Форма для загрузки файлов"""
    csrf_token = HiddenField()
    
    file = HiddenField(
        'Файл',
        validators=[DataRequired(message="Файл обязателен для загрузки.")]
    )