from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SelectMultipleField, HiddenField
from wtforms.validators import Length, DataRequired, Optional, NumberRange


class EnergyUnitFilterForm(FlaskForm):
    csrf_token = HiddenField()

    energy_unit_ids = HiddenField("ID")

    name = StringField(
        'Энергоузел',
        validators=[
            DataRequired(message="Поле 'Энергоузел' обязательно для заполнения."),
            Length(min=2, max=255, message="Длина имени должна быть от 2 до 255 символов.")
        ]
    )

    regional_district = SelectField(
        'Субъект РФ',
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Пожалуйста, выберите субъект РФ.")],
    )

    regional_energy_system = SelectField(
        'Региональная энергосистема',
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Пожалуйста, выберите региональную энергосистему.")],
    )

    union_energy_system = SelectField(
        'ОЭС',
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Пожалуйста, выберите ОЭС.")],
    )
    
    energy_unit_delete = HiddenField("Удалить")

    energy_unit_filter = StringField(
        "Фильтр по энергоузлам",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите энергоузел"}
    )

    regional_district_filter = StringField(
        "Фильтр по субъекту РФ",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите субъект РФ"}
    )

    regional_energy_system_filter = StringField(
        "Фильтр по региональной энергосистеме",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите региональную энергосистему"}
    )

    union_energy_system_filter = StringField(
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


class AddEnergyUnitForm(FlaskForm):
    """Форма добавления нового энергоузла"""
    csrf_token = HiddenField()

    name = StringField(
        'Энергоузел',
        validators=[
            DataRequired(message="Поле 'Энергоузел' обязательно для заполнения."),
            Length(min=3, max=255, message="Длина имени должна быть от 3 до 255 символов.")
        ]
    )

    regional_district = SelectField(
        'Субъект РФ',
        choices=[],
        coerce=int,
        validators=[DataRequired(message="Пожалуйста, выберите субъект РФ.")],
    )

    regional_energy_system = SelectField(
        'Региональная энергосистема',
        choices=[],
        coerce=int,
        validators=[Optional()],
    )

    union_energy_system = SelectField(
        'ОЭС',
        choices=[],
        coerce=int,
        validators=[Optional()],
    )

    energy_area_filter = StringField(
        "Фильтр по энергорайонам",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите энергорайон"}
    )

    regional_district_filter = StringField(
        "Фильтр по субъекту РФ",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите субъект РФ"}
    )

    regional_energy_system_filter = StringField(
        "Фильтр по региональной энергосистеме",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите региональную энергосистему"}
    )

    union_energy_system_filter = StringField(
        "Фильтр по ОЭС",
        validators=[Length(max=100)],
        render_kw={"placeholder": "Введите ОЭС"}
    )
