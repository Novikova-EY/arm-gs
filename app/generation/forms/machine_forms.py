from flask_wtf import FlaskForm
from wtforms import Form, StringField, TextAreaField, IntegerField, FloatField, FieldList, FormField, SelectField, HiddenField, SubmitField, DecimalField
from wtforms.validators import DataRequired, Optional, NumberRange, Length
from app.validators.validate_year_or_date import (
    validate_year_or_date,
    validate_year_or_date_list,
)
from decimal import Decimal

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
        # По умолчанию в choices показывается "не указано",
        # но перед сохранением пользователь обязан выбрать реальную организацию.
        validators=[DataRequired(message="Укажите организацию-собственника")]
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
        validators=[Optional(), Length(max=80)]
    )

    machine_name = TextAreaField(
        'Название агрегата',
        validators=[DataRequired(), Length(max=1024)]
    )

    machine_group = StringField(
        'Номер/название группы агрегата',
        validators=[Optional(), Length(max=80)]
    )

    fuel_so = StringField(
        'Топливо (по СО ЕЭС)',
        validators=[Optional(), Length(max=80)]
    )

    id_machine_type = SelectField(
        'Тип агрегата',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )

    id_tes_machine_type = SelectField(
        'Тип агрегата ТЭС',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )

    id_equipment_group = SelectField(
        'Тип технологии (EquipmentGroup)',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )

    date_exploitation = StringField(
        'Фактический год ввода в эксплуатацию',
        validators=[Optional(), Length(max=80), validate_year_or_date]
    )
    date_exploitation_expected = StringField(
        'Ожидаемый год ввода в эксплуатацию',
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
        validators=[Optional(), Length(max=255), validate_year_or_date_list]
    )
    date_update_fact = StringField(
        'Фактическая дата уточнения',
        validators=[Optional(), Length(max=255), validate_year_or_date_list]
    )

    note = StringField(
        'Примечание',
        validators=[Optional(), Length(max=512)]
    )

    change_document = StringField(
        'Документ-основание для изменения параметров агрегата',
        validators=[Optional()]
    )


class PGUMachinePowerForm(Form):
    year = IntegerField('Год', validators=[Optional()])
    p_ust = DecimalField('Мощность Руст', validators=[Optional()], default=Decimal("0"))


class PGUMachineFilterForm(FlaskForm):
    class Meta:
        csrf = False
        
    id_pgu_machine = HiddenField("ID")

    id_condition_type = SelectField(
        'Состояние агрегата станции',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )

    id_parent_machine = SelectField(
        'Агрегат',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )

    id_tes_machine_type = SelectField(
        'Тип агрегата ТЭС',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )

    id_pgu_tes_machine_type = SelectField(
        'Тип агрегата ПГУ',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )
    
    machine_number = StringField(
        'Номер агрегата',
        validators=[Optional(), Length(max=80)]
    )

    machine_name = TextAreaField(
        'Название агрегата',
        validators=[DataRequired(), Length(max=1024)]
    )

    powers = FieldList(FormField(PGUMachinePowerForm), min_entries=0)

    date_exploitation = StringField(
        'Фактический год ввода в эксплуатацию',
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
        validators=[Optional(), Length(max=255), validate_year_or_date_list]
    )
    date_update_fact = StringField(
        'Фактическая дата уточнения',
        validators=[Optional(), Length(max=255), validate_year_or_date_list]
    )

    note = StringField(
        'Примечание',
        validators=[Optional(), Length(max=512)]
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

    id_machine_type = SelectField(
        'Тип агрегата',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )

    id_tes_machine_type = SelectField(
        'Тип агрегата ТЭС',
        coerce=int,
        choices=[],
        validators=[Optional()]
    )


class MachinePowerForm(FlaskForm):
    class Meta:
        csrf = False  # Отключаем CSRF для вложенной формы

    year = IntegerField('Год', render_kw={'readonly': True})
    p_ust = DecimalField('Pуст', validators=[Optional()], places=15, default=0)
    p_ogr = DecimalField('Pуст', validators=[Optional()], places=15, default=0)
    p_rasp = DecimalField('Pуст', validators=[Optional()], places=15, default=0)


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


