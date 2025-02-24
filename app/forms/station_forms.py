from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, SelectField, TextAreaField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Length, Optional, NumberRange

class StationFilterForm(FlaskForm):
    """Форма фильтрации и управления списком субъектов РФ"""
    csrf_token = HiddenField()

    # ID электростанции (автогенерация)
    station_id = HiddenField("ID")

    # ID состояния станции
    id_condition_type = SelectField(
        'Состояние станции',
        coerce=int,
        choices=[],  # Список заполняется динамически (например, из базы данных)
        validators=[DataRequired(message="Пожалуйста, выберите тип состояния.")]
    )

    # Наименование диспетчерское (основное)
    name = StringField(
        'Наименование (основное)',
        validators=[DataRequired(), Length(max=80)]
    )

    # Наименование собственника
    name_owner = StringField(
        'Наименование собственника',
        validators=[DataRequired(), Length(max=80)]
    )

    # Наименование совмещенное
    name_compined = StringField(
        'Наименование совмещенное',
        validators=[DataRequired(), Length(max=80)]
    )

    # Наименование дополнительное
    name_additional = StringField(
        'Наименование дополнительное',
        validators=[DataRequired(), Length(max=80)]
    )

    # ID типа электростанции
    id_station_type = SelectField(
        'Тип электростанции',
        coerce=int,
        choices=[],  # Заполняется динамически
        validators=[Optional()]
    )

    # Список генерирующих компаний
    gen_companies = TextAreaField(
        'Генерирующие компании',
        validators=[Optional(), Length(max=256)]
    )

    # ID субъекта РФ
    id_regional_district = SelectField(
        'Субъект РФ',
        coerce=int,
        choices=[],  # Заполняется динамически
        validators=[Optional()]
    )

    # ОЭС 
    union_energy_system = SelectField(
        'ОЭС',
        coerce=int,
        choices=[],  # Заполняется динамически
        validators=[Optional()]
    )


    # Список видов топлива
    fuel_types = TextAreaField(
        'Виды топлива',
        validators=[Optional(), Length(max=256)]
    )

    # Номер КТО
    kto = StringField(
        'Номер КТО',
        validators=[DataRequired(), Length(max=80)]
    )

    # Местоположение
    location = StringField(
        'Местоположение',
        validators=[DataRequired(), Length(max=255)]
    )

    # ID группы электростанций
    id_group = SelectField(
        'Группа электростанций',
        coerce=int,
        choices=[],  # Заполняется динамически
        validators=[Optional()]
    )

    # Примечание
    note = StringField(
        'Примечание',
        validators=[Optional(), Length(max=80)]
    )
    
    # Фильтры
    condition_type_filter = StringField(
        "Фильтр по состоянию электростанции",
        validators=[Length(max=100)],
        render_kw={'multiple': True}
    )
    
    station_name_filter = StringField(
        "Фильтр по названию электростанции",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите название электростанции"}
    )

    gen_company_filter = StringField(
        "Фильтр по названию электростанции",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите название генерирующей компании"}
    )

    station_type_filter = StringField(
        "Фильтр по типу электростанции",
        validators=[Length(max=100)],
        render_kw={'multiple': True}
    )

    tes_type_filter = StringField(
        "Фильтр по типу ТЭС",
        validators=[Length(max=100)],
        render_kw={'multiple': True}
    )

    tes_machine_type_filter = StringField(
        "Фильтр по типу агрегата ТЭС",
        validators=[Length(max=100)],
        render_kw={'multiple': True}
    )

    regional_energy_system_filter = StringField(
        "Фильтр по региональным энергосистемам",
        validators=[Length(max=100)],
        render_kw={'multiple': True}
    )

    union_energy_system_filter = StringField(
        "Фильтр по ОЭС",
        validators=[Length(max=100)],
        render_kw={'multiple': True}
    )

    energy_type_system_filter = StringField(
        "Фильтр по типу энергосистемы",
        validators=[Length(max=100)],
        render_kw={'multiple': True}
    )

    regional_district_filter = StringField(
        "Фильтр по субъекту РФ",
        validators=[Length(max=100)],
        render_kw={'multiple': True}
    )

    federal_district_filter = StringField(
        "Фильтр по ФО",
        validators=[Length(max=100)],
        render_kw={'multiple': True}
    )

    gen_company_filter = StringField(
        "Фильтр по генерирующей компании",
        validators=[Length(max=100)],
        render_kw={'multiple': True}
    )

    fuel_type_filter = StringField(
        "Фильтр по виду топлива",
        validators=[Length(max=100)],
        render_kw={'multiple': True}
    )

    page = HiddenField(default=1)

    per_page = SelectField(
        'Количество строк на странице',
        choices=[
            (5, '5 строк'), 
            (10, '10 строк'), 
            (25, '25 строк'), 
            (50, '50 строк'), 
            (100, '100 строк'),
            (150, '150 строк'),
            (200, '200 строк')],
        coerce=int,
        validators=[Optional(), NumberRange(min=5, max=200)]
    )

