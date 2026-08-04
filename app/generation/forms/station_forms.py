from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, TextAreaField, HiddenField, SelectMultipleField
from wtforms.validators import DataRequired, Length, Optional, NumberRange

from app.generation.models.station.station_constants import STATION_SIGN_CHOICES

class StationFilterForm(FlaskForm):
    csrf_token = HiddenField()

    # ID  электростанции (автогенерация)
    station_id = HiddenField("ID")

    # ID состояния электростанции
    id_condition_type = SelectField(
        'Состояние электростанции',
        coerce=int,
        choices=[],  # Список заполняется динамически (например, из базы данных)
        validators=[DataRequired(message="Пожалуйста, выберите тип состояния.")]
    )

    # Наименование диспетчерское (основное)
    name = StringField(
        'Наименование (основное)',
        validators=[DataRequired(), Length(max=255)]
    )

    # Наименование собственника
    name_owner = StringField(
        'Наименование собственника',
        validators=[Optional(), Length(max=80)]
    )

    # Наименование совмещенное
    name_compined = StringField(
        'Наименование совмещенное',
        validators=[Optional(), Length(max=80)]
    )

    # Наименование дополнительное
    name_additional = StringField(
        'Наименование дополнительное',
        validators=[Optional(), Length(max=80)]
    )

    # Список генерирующих компаний
    station_type = TextAreaField(
        'Тип  электростанции',
        validators=[Optional(), Length(max=256)]
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

    # ID региональной энергосистемы
    id_regional_energy_system = SelectField(
        'Региональная энергосистема',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )

    id_energy_unit = SelectField(
        'Энергоузел  электростанции',
        coerce=lambda x: None if x is None or x == '' else (int(x) if x != '0' else 0),
        choices=[],        
        validators=[Optional()]
    )

    id_station_type = SelectField(
        'Тип  электростанции',
        coerce=lambda x: None if x is None or x == '' else (int(x) if x != '0' else 0),
        choices=[],
        validators=[Optional()]
    )

    station_sign = SelectField(
        'Признак электростанции',
        choices=STATION_SIGN_CHOICES,
        validators=[Optional()],
    )

    # Список видов топлива
    fuel_types = TextAreaField(
        'Виды топлива',
        validators=[Optional(), Length(max=256)]
    )

        # Местоположение
    fuel_so = StringField(
        'Топливо (по СО ЕЭС)',
        validators=[Optional(), Length(max=255)]
    )

    # Код КТО
    kto = StringField(
        'Код КТО',
        validators=[Optional(), Length(max=80)]
    )

    # Местоположение
    location = StringField(
        'Местоположение',
        validators=[Optional(), Length(max=255)]
    )

    # ID группы электростанций
    id_station_group = SelectField(
        'Группа электростанций',
        coerce=int,
        choices=[],  # Заполняется динамически
        validators=[Optional()]
    )

    # Примечание
    note = StringField(
        'Примечание',
        validators=[Optional(), Length(max=1000)]
    )

    external_code = StringField(
        'external_code',
        validators=[Optional(), Length(max=36)]
    )
    
    # Фильтры
    condition_type_filter = StringField(
        "Фильтр по состоянию  электростанции",
        validators=[Length(max=100)],
        render_kw={'multiple': True}
    )
    
    station_name_filter = StringField(
        "Фильтр по названию  электростанции",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите название  электростанции"}
    )

    gen_company_filter = StringField(
        "Фильтр по названию  электростанции",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите название генерирующей компании"}
    )

    note_filter = StringField(
        "Фильтр по примечанию",
        validators=[Optional(), Length(max=255)],
        render_kw={"placeholder": "Введите текст примечания"}
    )

    station_type_filter = StringField(
        "Фильтр по типу  электростанции",
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

    equipment_group_name_filter = StringField(
        "Фильтр по названию группы оборудования",
        validators=[Optional(), Length(max=255)],
        render_kw={"placeholder": "Группа оборудования"}
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


class AddStationForm(FlaskForm):
    # Подтверждение создания при дубликате
    confirm_duplicate = HiddenField(default="", validators=[Optional()])

    # Основные поля
    name = StringField(
        'Наименование (основное)',
        validators=[DataRequired(), Length(max=80)]
    )

    id_regional_district = SelectField(
        'Субъект РФ',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )

    id_station_type = SelectField(
        'Тип  электростанции',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )
