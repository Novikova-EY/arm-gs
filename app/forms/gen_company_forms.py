from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField
from wtforms.validators import Length, DataRequired, Optional, NumberRange

class GenCompanyFilterForm(FlaskForm):
    """Форма фильтрации и управления списком генерирующих компаний"""
    csrf_token = HiddenField()

    gen_company_ids = HiddenField("ID")

    name = StringField(
        'Наименование генерирующей компании',
        validators=[
            DataRequired(message="Поле 'Наименование генерирующей компании' обязательно для заполнения."),
            Length(min=2, max=255, message="Длина имени должна быть от 2 до 255 символов.")
        ]
    )
   
    gen_company_filter = StringField(
        "Название генерирующей компании",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите название генерирующей компании"}
    )

    page = HiddenField(default=1)
    
    per_page = SelectField(
        'Количество строк на странице',
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)]
    )

class AddGenCompanyForm(FlaskForm):
    """Форма добавления новой генерирующей компании"""
    csrf_token = HiddenField()
    
    name = StringField(
        'Наименование генерирующей компании',
        validators=[
            DataRequired(message="Поле 'Наименование генерирующей компании' обязательно для заполнения."),
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