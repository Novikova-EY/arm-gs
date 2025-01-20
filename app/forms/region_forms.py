from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField
from wtforms.validators import Length, DataRequired, Optional, NumberRange

class RegionFilterForm(FlaskForm):
    """Форма фильтрации и управления списком субъектов РФ"""
    csrf_token = HiddenField()

    region_ids = HiddenField("ID")

    name = StringField(
        'Субъект РФ',
        validators=[
            DataRequired(message="Поле 'Субъект РФ' обязательно для заполнения."),
            Length(min=2, max=255, message="Длина имени должна быть от 2 до 255 символов.")
        ]
    )
    fo = SelectField(
        'ФО',
        choices=[],  # Заполняется в контроллере
        coerce=int,
        validators=[DataRequired(message="Пожалуйста, выберите ФО.")]
    )
    region_delete = HiddenField("Удалить")
   
    name_filter = StringField(
        "Субъект РФ",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите субъект РФ"}
    )

    page = HiddenField(default=1)
    
    per_page = SelectField(
        'Количество строк на странице',
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)]
    )

class AddRegionForm(FlaskForm):
    """Форма добавления нового субъекта РФ"""
    csrf_token = HiddenField()
    
    name = StringField(
        'Субъект РФ',
        validators=[
            DataRequired(message="Поле 'Субъект РФ' обязательно для заполнения."),
            Length(min=3, max=255, message="Длина имени должна быть от 3 до 255 символов.")
        ]
    )
    fo = SelectField(
        'ФО',
        choices=[],  # Заполняется в контроллере
        coerce=int,
        validators=[DataRequired(message="Пожалуйста, выберите ФО.")]
    )

class FileUploadForm(FlaskForm):
    """Форма для загрузки файлов"""
    csrf_token = HiddenField()
    
    file = HiddenField(
        'Файл',
        validators=[DataRequired(message="Файл обязателен для загрузки.")]
    )