from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, FloatField, FieldList, FormField, SelectField, HiddenField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange, Length

from app.validators.validate_year_or_date import validate_year_or_date


from flask_wtf import FlaskForm
from wtforms import (
    StringField, IntegerField, FieldList, FormField, 
    SelectField, HiddenField
)
from wtforms.validators import DataRequired, Optional, NumberRange, Length

from app.validators.validate_year_or_date import validate_year_or_date


class MachineFilterForm(FlaskForm):
    csrf_token = HiddenField()

    id_machine = HiddenField("ID")

    id_condition_type = SelectField(
        'Состояние агрегата станции',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )

    id_gen_company = SelectField(
        'Организация-собственник',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )

    id_station = SelectField(
        'Электростанция',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )

    id_energy_area = SelectField(
        'Энергорайон агрегата станции',
        coerce=int,
        choices=[],        
        validators=[Optional()]
    )

    machine_number = StringField(
        'Номер агрегата',
        validators=[DataRequired(), Length(max=80)]
    )

    machine_name = StringField(
        'Название агрегата',
        validators=[DataRequired(), Length(max=80)]
    )

    machine_group = StringField(
        'Номер/название группы агрегата',
        validators=[Optional(), Length(max=80)]
    )

    fuel_so = StringField(
        'Топливо (по СО ЕЭС)',
        validators=[Optional(), Length(max=80)]
    )

    id_station_type = SelectField(
        'Тип электростанции',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )

    id_machine_type = SelectField(
        'Тип агрегата',
        coerce=int,
        choices=[],  # заполняем динамически
        validators=[Optional()]
    )

    id_tes_machine_type = SelectField(
        'Тип агрегата ТЭС',
        coerce=int,
        choices=[],  # заполняем динамически
        validators=[Optional()]
    )

    date_exploitation = StringField(
        'Год ввода в эксплуатацию',
        validators=[Optional(), Length(max=80), validate_year_or_date]
    )
    date_commission_expected = StringField(
        'Ожидаемый год ввода в работу',
        validators=[Optional(), Length(max=80), validate_year_or_date]
    )
    date_commission_fact = StringField(
        'Фактическая дата ввода в работу',
        validators=[Optional(), Length(max=80), validate_year_or_date]
    )
    date_joining_expected = StringField(
        'Ожидаемая дата присоединения',
        validators=[Optional(), Length(max=80), validate_year_or_date]
    )
    date_joining_fact = StringField(
        'Фактическая дата присоединения',
        validators=[Optional(), Length(max=80), validate_year_or_date]
    )
    date_detatchment_fact = StringField(
        'Фактическая дата отсоединения',
        validators=[Optional(), Length(max=80), validate_year_or_date]
    )
    date_decompressing_expected = StringField(
        'Ожидаемый год вывода из эксплуатации',
        validators=[Optional(), Length(max=80), validate_year_or_date]
    )
    date_decompressing_fact = StringField(
        'Фактическая дата вывода из эксплуатации',
        validators=[Optional(), Length(max=80), validate_year_or_date]
    )
    date_modernization_expected = StringField(
        'Ожидаемый год модернизации',
        validators=[Optional(), Length(max=80), validate_year_or_date]
    )
    date_relabing_fact = StringField(
        'Фактическая дата перемаркировки',
        validators=[Optional(), Length(max=80), validate_year_or_date]
    )
    date_update_fact = StringField(
        'Фактическая дата уточнения',
        validators=[Optional(), Length(max=80), validate_year_or_date]
    )

    note = StringField(
        'Примечание',
        validators=[Optional(), Length(max=80)]
    )

class MachineFilterSmallForm(FlaskForm):
    csrf_token = HiddenField()

    id_machine = HiddenField("ID")

    id_gen_company = SelectField(
        'Организация-собственник',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )

    fuel_so = StringField(
        'Топливо (по СО ЕЭС)',
        validators=[Optional(), Length(max=80)]
    )

    id_station_type = SelectField(
        'Тип электростанции',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )

    id_machine_type = SelectField(
        'Тип агрегата',
        coerce=int,
        choices=[],  # заполняем динамически
        validators=[Optional()]
    )

    id_tes_machine_type = SelectField(
        'Тип агрегата ТЭС',
        coerce=int,
        choices=[],  # заполняем динамически
        validators=[Optional()]
    )



class MachinePowerForm(FlaskForm):
    class Meta:
        csrf = False  # Отключаем CSRF для вложенной формы

    year = IntegerField('Год', render_kw={'readonly': True})
    p_ust = FloatField('Руст', validators=[Optional(), NumberRange(min=0)])
    p_ogr = FloatField('Рогр', validators=[Optional(), NumberRange(min=0)])
    p_rasp = FloatField('Ррасп', validators=[Optional(), NumberRange(min=0)])



class MachineFuelForm(FlaskForm):
    class Meta:
        csrf = False
    year = IntegerField('Год', render_kw={'readonly': True})
    fuel_type = SelectField('Топливо', coerce=int, validators=[Optional()])


class MachineTesTypeForm(FlaskForm):
    class Meta:
        csrf = False
    year = IntegerField('Год', render_kw={'readonly': True})
    tes_type = SelectField('Тип ТЭС', coerce=int, validators=[Optional()])


class EditMachineForm(FlaskForm):
    powers = FieldList(FormField(MachinePowerForm), min_entries=0)
    fuels = FieldList(FormField(MachineFuelForm), min_entries=0)
    tes_types = FieldList(FormField(MachineTesTypeForm), min_entries=0)

