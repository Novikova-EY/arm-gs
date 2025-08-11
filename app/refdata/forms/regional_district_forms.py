from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, HiddenField
from wtforms.validators import Length, DataRequired, Optional, NumberRange

class RegionalDistrictFilterForm(FlaskForm):
    csrf_token = HiddenField()

    regional_district_ids = HiddenField("ID")

    name = StringField(
        'Наименование субъекта РФ',
        validators=[
            DataRequired(message="Поле 'Наименование субъекта РФ' обязательно для заполнения."),
            Length(min=2, max=255, message="Длина имени должна быть от 2 до 255 символов.")
        ]
    )

    name_full = StringField(
        'Полное наименование субъекта РФ',
        validators=[
            DataRequired(message="Поле 'Полное наименование субъекта РФ' обязательно для заполнения."),
            Length(min=2, max=255, message="Длина имени должна быть от 2 до 255 символов.")
        ]
    )

    federal_district = SelectField(
        'Наименование ФО',
        choices=[],  # Заполняется в контроллере
        coerce=int,
        validators=[DataRequired(message="Пожалуйста, выберите ФО.")]
    )

    regional_district_delete = HiddenField("Удалить")
   
    regional_district_filter = StringField(
        "Фильтр по наименованию субъекта РФ",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите наименованию субъекта РФ"}
    )

    federal_district_filter = StringField(
        "Фильтр по наименованию ФО",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите наименование ФО"}
    )

    page = HiddenField(default=1)
    
    per_page = SelectField(
        'Количество строк на странице',
        choices=[(5, '5 строк'), (10, '10 строк'), (25, '25 строк'), (50, '50 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=50)]
    )

class AddRegionalDistrictForm(FlaskForm):
    """Форма добавления нового субъекта РФ"""
    csrf_token = HiddenField()
    
    name = StringField(
        'Наименование субъекта РФ',
        validators=[
            DataRequired(message="Поле 'Наименование субъекта РФ обязательно для заполнения."),
            Length(min=3, max=255, message="Длина имени должна быть от 3 до 255 символов.")
        ]
    )

    name_full = StringField(
        'Полное наименование субъекта РФ',
        validators=[
            DataRequired(message="Поле 'Полное наименование субъекта РФ' обязательно для заполнения."),
            Length(min=3, max=255, message="Длина имени должна быть от 3 до 255 символов.")
        ]
    )

    federal_district = SelectField(
        'Наименование ФО',
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