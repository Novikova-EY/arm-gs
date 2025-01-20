from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField
from wtforms.validators import Length, DataRequired, Optional, NumberRange

class FoFilterForm(FlaskForm):
    """Форма фильтрации и управления списком ФО"""
    csrf_token = HiddenField()

    fo_ids = HiddenField("ID")

    name = StringField(
        'Наименование ФО',
        validators=[
            DataRequired(message="Поле 'Наименование ФО' обязательно для заполнения."),
            Length(min=2, max=255, message="Длина имени должна быть от 2 до 255 символов.")
        ]
    )
   
    fo_filter = StringField(
        "Название ФО",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите название ФО"}
    )

    page = HiddenField(default=1)
    
    per_page = SelectField(
        'Количество строк на странице',
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)]
    )

class AddFoForm(FlaskForm):
    """Форма добавления нового ФО"""
    csrf_token = HiddenField()
    
    name = StringField(
        'Наименование ФО',
        validators=[
            DataRequired(message="Поле 'Наименование ФО' обязательно для заполнения."),
            Length(min=3, max=255, message="Длина имени должна быть от 3 до 255 символов.")
        ]
    )

class FileUploadForm(FlaskForm):
    """Форма для загрузки файлов"""
    csrf_token = HiddenField()
    
    file = HiddenField(
        'Файл',
        validators=[DataRequired(message="Файл обязателен для загрузки.")]
    )