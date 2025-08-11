from config import Config
from app.extensions import db
import traceback
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from sqlalchemy.orm.attributes import flag_modified
from flask import flash,request, render_template, request, flash, redirect, url_for
from app.logs.services.logging_service import log_to_db
from app.refdata.models.energy_systems_models import *
from app.refdata.models.territories_models import *
from app.refdata.models.fuels_models import *
from app.refdata.models.gen_companies_models import *
from app.refdata.models.stations_refdata_models import *
from app.refdata.models.territories_models import *
from app.refdata.models.years_models import *
from app.generation.models.stations_models import *
from app.generation.models.machines_models import *
from app.generation.models.pgu_machines_models import *
from app.generation.models.boilers_models import *
from app.generation.forms.machine_forms import MachineFilterForm, EditMachineForm, PGUMachineFilterForm
from app.generation.services.station_services.help_services import (
    convert_to_date
)
from app.generation.services.station_services.station_services import (
    recalculate_station_power,
    get_machine_by_id,
    get_station_by_id,
)
from app.generation.services.station_services.help_services import (
    rounded_decimal,
    get_year_features,
    format_decimal_for_display,
)

def handle_machine_get(station_id, machine_id, start_year, end_year, rounding_digits):
    machine = get_machine_by_id(machine_id)
    station = get_station_by_id(station_id)

    years = Year.query.filter(Year.number >= start_year, Year.number <= end_year).all()
    year_dict = {y.number: y for y in years}
    year_features = get_year_features()

    machine_powers = {mp.year.number: mp for mp in machine.machine_powers}
    machine_fuels = {mf.year.number: mf for mf in machine.machine_fuels}
    machine_tes_types = {mt.year.number: mt for mt in machine.machine_tes_types}

    main_form = MachineFilterForm(prefix="main_", obj=machine)
    advanced_form = EditMachineForm(prefix="adv_")

    _fill_main_form_choices(main_form)
    _fill_advanced_form_choices(advanced_form)

    pgu_machines_form = PGUMachineFilterForm(prefix="pgu_")
    pgu_machines_query = PGUMachine.query.filter_by(id_parent_machine=machine.id)

    # Применяем фильтры, если они выбраны:
    if pgu_machines_form.id_condition_type.data and pgu_machines_form.id_condition_type.data != 0:
        pgu_machines_query = pgu_machines_query.filter_by(id_condition_type=pgu_machines_form.id_condition_type.data)

    if pgu_machines_form.id_tes_machine_type.data and pgu_machines_form.id_tes_machine_type.data != 0:
        pgu_machines_query = pgu_machines_query.filter_by(id_tes_machine_type=pgu_machines_form.id_tes_machine_type.data)

    if pgu_machines_form.id_parent_machine.data and pgu_machines_form.id_parent_machine.data != 0:
        pgu_machines_query = pgu_machines_query.filter_by(id_parent_machine=pgu_machines_form.id_parent_machine.data)

    pgu_machines = pgu_machines_query.order_by(PGUMachine.machine_name).all()

    if main_form.id_condition_type.data is None:
        main_form.id_condition_type.data = 100
    if main_form.id_gen_company.data is None:
        main_form.id_gen_company.data = 0
    if main_form.id_station_type.data is None:
        main_form.id_station_type.data = 100
    if main_form.id_machine_type.data is None:
        main_form.id_machine_type.data = 100
    if main_form.id_tes_machine_type.data is None:
        main_form.id_tes_machine_type.data = 100

    tes_type_choices = [(tt.id, tt.name) for tt in TesType.query.order_by(TesType.id).all()]
    fuel_choices = [(f.id, f.name) for f in Fuel.query.order_by(Fuel.id).all()]

    for year_num in range(start_year, end_year + 1):
        y_obj = year_dict.get(year_num)

        if year_num not in machine_powers:
            mp = MachinePower(id_machine=machine.id, year=y_obj)
            db.session.add(mp)
            machine_powers[year_num] = mp

        if year_num not in machine_tes_types:
            mt = MachineTesType(id_machine=machine.id, year=y_obj)
            db.session.add(mt)
            machine_tes_types[year_num] = mt

        if year_num not in machine_fuels:
            mf = MachineFuel(id_machine=machine.id, year=y_obj)
            db.session.add(mf)
            machine_fuels[year_num] = mf

    for year_num in range(start_year, end_year + 1):
        mp = machine_powers[year_num]
        mt = machine_tes_types[year_num]
        mf = machine_fuels[year_num]

        power_entry = advanced_form.powers.append_entry()
        power_entry.year.data = year_num
        power_entry.p_ust.data = mp.p_ust
        power_entry.p_ogr.data = mp.p_ogr
        power_entry.p_rasp.data = mp.p_rasp

        tes_entry = advanced_form.tes_types.append_entry()
        tes_entry.year.data = year_num
        tes_entry.tes_type.choices = tes_type_choices
        tes_entry.tes_type.data = mt.id_tes_type if mt.id_tes_type is not None else 100

        fuel_entry = advanced_form.fuels.append_entry()
        fuel_entry.year.data = year_num
        fuel_entry.fuel_type.choices = fuel_choices
        fuel_entry.fuel_type.data = mf.id_fuel if mf.id_fuel is not None else 100

    db.session.commit()

    return {
        "start_year": start_year,
        "end_year": end_year,
        "rounding_digits": rounding_digits,
        "main_form": main_form,
        "advanced_form": advanced_form,
        "station": station,
        "machine": machine,
        "year_features": year_features,
        "pgu_machines_form": pgu_machines_form,
        "pgu_machines": pgu_machines,
        "year_features": year_features,
    }


def handle_machine_post(station_id, machine_id, form_data, user, start_year, end_year, rounding_digits):
    from werkzeug.datastructures import MultiDict

    normalized = MultiDict(form_data)
    for key, value in list(normalized.items()):
        if isinstance(value, str):
            if value.strip() in {"\u2014", "-", ""}:
                normalized[key] = ""
            elif "," in value:
                normalized[key] = value.replace(",", ".")

    main_form = MachineFilterForm(formdata=normalized, prefix="main_")
    advanced_form = EditMachineForm(formdata=normalized, prefix="adv_")
    pgu_machines_form = PGUMachineFilterForm(formdata=normalized, prefix="pgu_")

    station = get_station_by_id(station_id)
    machine = get_machine_by_id(machine_id)
    year_features = get_year_features()

    _fill_main_form_choices(main_form)
    _fill_advanced_form_choices(advanced_form)
    _fill_pgu_machines_form_choices(pgu_machines_form, machine_id=machine.id)

    pgu_ids_to_delete = request.form.getlist("pgu_machines_delete[]", type=int)

    # Удаляем ПГУ сразу, до валидации форм
    if pgu_ids_to_delete:
        pgu_to_delete = PGUMachine.query.filter(PGUMachine.id.in_(pgu_ids_to_delete)).all()
        deleted_names = []

        for pgu_machine in pgu_to_delete:
            try:
                for power in pgu_machine.pgu_machine_powers:
                    db.session.delete(power)
                db.session.delete(pgu_machine)
                deleted_names.append(pgu_machine.machine_name or f"ID={pgu_machine.id}")
            except Exception as e:
                flash(f"Ошибка при удалении ПГУ ID={pgu_machine.id}: {e}", "danger")
                log_to_db(user, f"Ошибка удаления ПГУ ID={pgu_machine.id}", details=str(e))

        db.session.commit()

        if deleted_names:
            log_to_db(user, f"Удаление ПГУ агрегатов на станции {station.name}", details="; ".join(deleted_names))
            flash("Выбранные ПГУ агрегаты успешно удалены!", "success")

        return redirect(url_for("station_bp.machine_details", 
                                station_id=station.id, 
                                machine_id=machine.id,
                                start_year=start_year, 
                                end_year=end_year, 
                                rounding_digits=rounding_digits))
    
    is_pgu_action = any([
        pgu_machines_form.id_pgu_machine.data,
        pgu_machines_form.machine_name.data,
        pgu_machines_form.machine_number.data
    ])

    main_valid = main_form.validate()
    adv_valid = advanced_form.validate()
    pgu_valid = pgu_machines_form.validate() if is_pgu_action else True

    if not (main_valid and adv_valid and pgu_valid):
        print("main_form.errors:", main_form.errors)
        print("advanced_form.errors:", advanced_form.errors)
        print("pgu_machines_form.errors:", pgu_machines_form.errors)
        flash("Ошибка в заполнении формы. Проверьте поля.", "danger")
        return render_template(
            "stations/machine_details.html",
            start_year=start_year,
            end_year=end_year,
            rounding_digits=rounding_digits,
            main_form=main_form,
            advanced_form=advanced_form,
            pgu_machines_form=pgu_machines_form,
            station=station,
            machine=machine,
            year_features=year_features,
        )

    try:
        changes, pgu_changes = [], []

        field_map = {
            "id_condition_type": lambda x: ConditionType.query.get(x).name if x else "не указано",
            "id_gen_company": lambda x: GenCompany.query.get(x).name if x else "не указано",
            "id_station_type": lambda x: StationType.query.get(x).name if x else "не указано",
            "id_machine_type": lambda x: MachineType.query.get(x).name if x else "не указано",
            "id_tes_machine_type": lambda x: TesMachineType.query.get(x).name if x else "не указано",
            "machine_name": str,
            "note": lambda x: x or "не указано",
            "machine_group": str,
        }

        for fld, to_str in field_map.items():
            old_v, new_v = getattr(machine, fld), getattr(main_form, fld).data
            if old_v != new_v:
                changes.append(f"{fld}: {to_str(old_v)} → {to_str(new_v)}")
                setattr(machine, fld, new_v)

        date_fields = [
            "date_exploitation", "date_commission_fact", "date_joining_expected", "date_joining_fact",
            "date_detatchment_fact", "date_decompressing_expected", "date_decompressing_fact",
            "date_modernization_expected", "date_relabing_fact", "date_update_fact",
        ]

        for fld in date_fields:
            raw_form_value = getattr(main_form, fld).data
            if fld in {"date_exploitation", "date_decompressing_expected", "date_modernization_expected"}:
                new_val = int(raw_form_value) if raw_form_value else None
            else:
                new_val = convert_to_date(raw_form_value)

            old_val = getattr(machine, fld)
            old_val_str = old_val.strftime("%Y-%m-%d") if isinstance(old_val, (date, datetime)) else str(old_val) if old_val else None
            new_val_str = new_val.strftime("%Y-%m-%d") if isinstance(new_val, (date, datetime)) else str(new_val) if new_val else None

            if old_val_str != new_val_str:
                changes.append(f"{fld}: {old_val_str} → {new_val_str}")
                setattr(machine, fld, new_val)

        powers_map = {mp.year.number: mp for mp in machine.machine_powers}
        tes_map = {mt.year.number: mt for mt in machine.machine_tes_types}
        fuel_map = {mf.year.number: mf for mf in machine.machine_fuels}

        for i, year_num in enumerate(range(start_year, end_year + 1)):
            if i >= len(advanced_form.powers) or i >= len(advanced_form.tes_types) or i >= len(advanced_form.fuels):
                continue

            mp, mt, mf = powers_map.get(year_num), tes_map.get(year_num), fuel_map.get(year_num)
            if not mp or not mt or not mf:
                continue

            p_ust = to_decimal(advanced_form.powers[i].p_ust.data) or mp.p_ust
            p_ogr = to_decimal(advanced_form.powers[i].p_ogr.data) or mp.p_ogr
            p_rasp = to_decimal(advanced_form.powers[i].p_rasp.data) or mp.p_rasp

            p_ust, p_ogr, p_rasp = autofill_powers_if_possible_decimal(p_ust, p_ogr, p_rasp, year_num)

            for attr, val in (("p_ust", p_ust), ("p_ogr", p_ogr), ("p_rasp", p_rasp)):
                old_val = getattr(mp, attr)
                if not is_same_decimal(old_val, val):
                    setattr(mp, attr, val)
                    flag_modified(mp, attr)
                    changes.append(f"{year_num} – {attr}: {format_decimal_for_display(old_val)} → {format_decimal_for_display(val)}")

            new_tt = advanced_form.tes_types[i].tes_type.data
            new_fuel = advanced_form.fuels[i].fuel_type.data

            if mt.id_tes_type != new_tt and new_tt is not None:
                changes.append(f"{year_num} – Тип ТЭС: {mt.id_tes_type} → {new_tt}")
                mt.id_tes_type = new_tt

            if mf.id_fuel != new_fuel and new_fuel is not None:
                changes.append(f"{year_num} – Топливо: {mf.id_fuel} → {new_fuel}")
                mf.id_fuel = new_fuel

        if is_pgu_action and pgu_machines_form.id_pgu_machine.data:
            pgu_machine = PGUMachine.query.get(pgu_machines_form.id_pgu_machine.data)
            if pgu_machine:
                for fld, to_str in {
                    "id_condition_type": lambda x: ConditionType.query.get(x).name if x else "не указано",
                    "id_parent_machine": lambda x: Machine.query.get(x).machine_name if x else "не указано",
                    "machine_number": str,
                    "machine_name": str,
                    "id_tes_machine_type": lambda x: TesMachineType.query.get(x).name if x else "не указано",
                    "note": lambda x: x or "не указано",
                }.items():
                    old_val, new_val = getattr(pgu_machine, fld), getattr(pgu_machines_form, fld).data
                    if old_val != new_val:
                        pgu_changes.append(f"ПГУ {fld}: {old_val} → {new_val}")
                        setattr(pgu_machine, fld, new_val)

                for fld in date_fields:
                    old_val = getattr(pgu_machine, fld)
                    raw_val = getattr(pgu_machines_form, fld).data
                    new_val = int(raw_val) if raw_val and fld in {"date_exploitation", "date_decompressing_expected", "date_modernization_expected"} else convert_to_date(raw_val)
                    if str(old_val) != str(new_val):
                        pgu_changes.append(f"ПГУ {fld}: {old_val} → {new_val}")
                        setattr(pgu_machine, fld, new_val)

        autofill_tes_and_fuel_chain(machine, advanced_form, changes, start_year, end_year)
        recalculate_station_power(station, start_year, end_year)
        recalculate_machine_years_by_p_ust(machine, changes, year_features)

        db.session.commit()

        if pgu_changes:
            log_to_db(user, f"Изменения по ПГУ агрегату {pgu_machine.machine_name} станции {station.name}", details="; ".join(pgu_changes))
            flash("Данные ПГУ агрегата успешно обновлены!", "success")

        if changes:
            log_to_db(user, f"Изменения в станции {station.name} ({station.regional_district.name}), агрегат №{machine.machine_number}", details="; ".join(changes))
            flash("Данные агрегата успешно обновлены!", "success")

        if not changes and not pgu_changes:
            flash("Изменений не обнаружено", "info")

        return redirect(url_for("station_bp.machine_details", start_year=start_year, end_year=end_year, rounding_digits=rounding_digits, station_id=station.id, machine_id=machine.id))

    except Exception as exc:
        db.session.rollback()
        traceback.print_exc()
        flash(f"Ошибка при обновлении данных: {exc}", "danger")
        log_to_db(user, f"Ошибка обновления агрегата №{machine.machine_number} {machine.machine_name} станции {station.name}", details=str(exc))
        return render_template(
            "stations/machine_details.html",
            start_year=start_year,
            end_year=end_year,
            rounding_digits=rounding_digits,
            main_form=main_form,
            advanced_form=advanced_form,
            pgu_machines_form=pgu_machines_form,
            station=station,
            machine=machine,
            year_features=year_features,
        )


def handle_pgu_machine_get(station_id, machine_id, pgu_machine_id, start_year, end_year):
    station = Station.query.get_or_404(station_id)
    parent_machine = Machine.query.get_or_404(machine_id)
    year_features = get_year_features()

    if pgu_machine_id == 0:
        pgu_machine = None
        pgu_form = PGUMachineFilterForm(prefix='pgu_')
    else:
        pgu_machine = PGUMachine.query.get_or_404(pgu_machine_id)
        pgu_form = PGUMachineFilterForm(obj=pgu_machine, prefix='pgu_')

    from app.generation.services.machine_services.machine_services import _fill_pgu_machines_form_choices
    _fill_pgu_machines_form_choices(pgu_form, machine_id)

    pgu_machine = PGUMachine.query.get(pgu_machine_id) if pgu_machine_id else None

    existing_powers = {}
    if pgu_machine:
        for power in pgu_machine.pgu_machine_powers:
            existing_powers[power.year_number] = power

    if not pgu_form.powers.entries:
        for year in range(start_year, end_year + 1):
            value = existing_powers.get(year).p_ust if existing_powers.get(year) else 0
            pgu_form.powers.append_entry({"year": year, "p_ust": value})

    context = {
        "station": station,
        "parent_machine": parent_machine,
        "pgu_form": pgu_form,
        "start_year": start_year,
        "end_year": end_year,
        "pgu_machine_id": pgu_machine_id,
        "pgu_machine":pgu_machine,
        "year_features": year_features,
    }
    return context


def handle_pgu_machine_post(station_id, machine_id, pgu_machine_id, form_data, user, start_year, end_year):
    station = get_station_by_id(station_id)
    parent_machine = get_machine_by_id(machine_id)

    pgu_form = PGUMachineFilterForm(form_data, prefix='pgu_')
    _fill_pgu_machines_form_choices(pgu_form, machine_id)

    if not pgu_form.validate():
        flash("Ошибка в заполнении формы.", "danger")
        return render_template(
            "stations/pgu_machine_details.html",
            station=station,
            parent_machine=parent_machine,
            pgu_form=pgu_form,
            start_year=start_year,
            end_year=end_year,
            pgu_machine_id=pgu_machine_id,
        )

    try:
        if pgu_machine_id == 0:
            pgu_machine = PGUMachine(id_parent_machine=machine_id)
            db.session.add(pgu_machine)
        else:
            pgu_machine = PGUMachine.query.get_or_404(pgu_machine_id)

        for field in [
            'id_condition_type', 'machine_number', 'machine_name', 'id_pgu_tes_machine_type', 'note',
            'date_exploitation', 'date_commission_fact', 'date_joining_expected', 'date_joining_fact',
            'date_detatchment_fact', 'date_decompressing_expected', 'date_decompressing_fact',
            'date_modernization_expected', 'date_relabing_fact', 'date_update_fact'
        ]:
            value = getattr(pgu_form, field).data
            if 'date' in field and field not in {'date_exploitation', 'date_decompressing_expected', 'date_modernization_expected'}:
                value = convert_to_date(value)
            elif field in {'date_exploitation', 'date_decompressing_expected', 'date_modernization_expected'}:
                value = int(value) if value else None
            setattr(pgu_machine, field, value)

        db.session.flush()

        PGUMachinePower.query.filter_by(id_pgu_machine=pgu_machine.id).delete()

        for power_entry in pgu_form.powers.entries:
            year = power_entry.year.data
            p_ust = to_decimal(power_entry.p_ust.data)
            db.session.add(PGUMachinePower(id_pgu_machine=pgu_machine.id, year_number=year, p_ust=p_ust))

        db.session.commit()

        action = "Добавлен" if pgu_machine_id == 0 else "Обновлён"
        log_to_db(user, f"{action} ПГУ агрегат '{pgu_machine.machine_name}'", details=f"ID: {pgu_machine.id}")
        flash(f"Агрегат ПГУ успешно сохранён!", "success")

        return redirect(url_for('station_bp.machine_details',
                                station_id=station.id,
                                machine_id=parent_machine.id,
                                start_year=start_year,
                                end_year=end_year))

    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка при сохранении: {e}", "danger")
        return render_template(
            "stations/pgu_machine_details.html",
            station=station,
            parent_machine=parent_machine,
            pgu_form=pgu_form,
            start_year=start_year,
            end_year=end_year,
            pgu_machine_id=pgu_machine_id,
        )
    

def _fill_main_form_choices(form):
    form.id_gen_company.choices = [(0, "не указано")] + [(g.id, g.name) for g in GenCompany.query.order_by(GenCompany.id).all()]
    form.id_energy_area.choices = [(ea.id, ea.name) for ea in EnergyArea.query.order_by(EnergyArea.id).all()]
    form.id_station_type.choices = [(st.id, st.name) for st in StationType.query.order_by(StationType.id).all()]
    form.id_machine_type.choices = [(mt.id, mt.name) for mt in MachineType.query.order_by(MachineType.id).all()]
    form.id_tes_machine_type.choices = [(tmt.id, tmt.name) for tmt in TesMachineType.query.order_by(TesMachineType.id).all()]
    
    form.id_condition_type.choices = [
        (c.id, c.name) for c in ConditionType.query.order_by(ConditionType.id).all()
    ]
    if form.id_condition_type.data is None:
        form.id_condition_type.data = 100


def _fill_advanced_form_choices(form):
    tes_types = TesType.query.order_by(TesType.id).all()
    fuel_types = Fuel.query.order_by(Fuel.id).all()

    tes_choices = [(tt.id, tt.name) for tt in tes_types]
    fuel_choices = [(f.id, f.name) for f in fuel_types]

    for entry in form.tes_types:
        entry.tes_type.choices = tes_choices
        if entry.tes_type.data is None:
            entry.tes_type.data = 100 

    for entry in form.fuels:
        entry.fuel_type.choices = fuel_choices
        if entry.fuel_type.data is None:
            entry.fuel_type.data = 100


def _fill_pgu_machines_form_choices(form, machine_id):
    form.id_parent_machine.choices = [
        (m.id, m.machine_name) for m in Machine.query.order_by(Machine.machine_name).all()
    ]

    form.id_condition_type.choices = [
        (c.id, c.name) for c in ConditionType.query.order_by(ConditionType.id).all()
    ]
    if form.id_condition_type.data is None:
        form.id_condition_type.data = 100

    form.id_pgu_tes_machine_type.choices = [
        (t.id, t.name) for t in PGUTesMachineType.query.order_by(PGUTesMachineType.id).all()
    ]
    if form.id_pgu_tes_machine_type.data is None:
        form.id_pgu_tes_machine_type.data = 100


def is_empty(val):
    try:
        if val is None:
            return True
        if isinstance(val, Decimal):
            return float(val) == 0.0
        return Decimal(val) == 0
    except (InvalidOperation, TypeError, ValueError):
        return True


def to_decimal(val):
    try:
        if val in (None, '', '—', '-'):
            return None
        if isinstance(val, str):
            val = val.replace(',', '.')
        return Decimal(val)
    except (InvalidOperation, TypeError):
        return None
    

def is_same_decimal(a, b, tol=6):
    if a is None and (b is None or Decimal(b) == 0):
        return True
    if b is None and (a is None or Decimal(a) == 0):
        return True
    return rounded_decimal(a, tol) == rounded_decimal(b, tol)


def autofill_powers_if_possible_decimal(p_ust, p_ogr, p_rasp, year_num=None):
    try:
        if p_ust > 0:
            if not is_empty(p_rasp) and is_empty(p_ogr):
                calculated = p_ust - p_rasp
                if rounded_decimal(p_ogr, 6) != rounded_decimal(calculated, 6):
                    if year_num is not None:
                        flash(f"🧠 {year_num} год: автозаполнено Рогр = {calculated} (из Руст − Ррасп)", "info")
                    return p_ust, calculated, p_rasp
            elif not is_empty(p_ogr) and is_empty(p_rasp):
                calculated = p_ust - p_ogr
                if rounded_decimal(p_rasp, 6) != rounded_decimal(calculated, 6):
                    if year_num is not None:
                        flash(f"🧠 {year_num} год: автозаполнено Ррасп = {calculated} (из Руст − Рогр)", "info")
                    return p_ust, p_ogr, calculated
            elif is_empty(p_ogr) and is_empty(p_rasp):
                if year_num is not None:
                    flash(f"🧠 {year_num} год: автозаполнено Ррасп = 0 и Рогр = {p_ust}", "info")
                return p_ust, p_ust, Decimal(0)
        return p_ust, p_ogr, p_rasp

    except (InvalidOperation, TypeError) as e:
        if year_num is not None:
            flash(f"⚠️ {year_num} год: ошибка автозаполнения мощностей ({e})", "warning")
        return p_ust, p_ogr, p_rasp
    

def autofill_tes_and_fuel_chain(machine, advanced_form, changes, start_year, end_year):
    """
    Автоматически заполняет тип ТЭС и топливо по принципу цепной передачи:
    - если p_ust > 0 и текущий тип == 100, а предыдущий ≠100 → копируем
    - если все мощности == 0 → тип ТЭС и топливо = 100
    """
    from flask import flash

    prev_tes_type = None
    prev_fuel_type = None

    powers_map = {mp.year.number: mp for mp in machine.machine_powers}
    tes_map = {mt.year.number: mt for mt in machine.machine_tes_types}
    fuel_map = {mf.year.number: mf for mf in machine.machine_fuels}

    fuel_names = {f.id: f.name for f in Fuel.query.all()}
    tes_names = {t.id: t.name for t in TesType.query.all()}

    for i, year_num in enumerate(range(start_year, end_year + 1)):
        if year_num not in powers_map or year_num not in tes_map or year_num not in fuel_map:
            continue

        mp = powers_map[year_num]
        mt = tes_map[year_num]
        mf = fuel_map[year_num]

        p_ust = mp.p_ust or Decimal(0)
        p_ogr = mp.p_ogr or Decimal(0)
        p_rasp = mp.p_rasp or Decimal(0)

        if is_empty(p_ust) and is_empty(p_ogr) and is_empty(p_rasp):
            if mt.id_tes_type != 100:
                changes.append(f"{year_num} - Тип ТЭС: {mt.id_tes_type} → 'не указано'")
                mt.id_tes_type = 100
                flash(f"🧠 {year_num} год: Тип ТЭС установлен: 'не указано' (все мощности = 0)", "info")

            if mf.id_fuel != 100:
                changes.append(f"{year_num} - Топливо: {mf.id_fuel} → 'не указано'")
                mf.id_fuel = 100
                flash(f"🧠 {year_num} год: Топливо установлено: 'не указано' (все мощности = 0)", "info")
        else:
            if mt.id_tes_type in (None, 100) and prev_tes_type not in (None, 100):
                changes.append(f"{year_num} - Тип ТЭС: {mt.id_tes_type} → {prev_tes_type}")
                mt.id_tes_type = prev_tes_type
                tes_name = tes_names.get(prev_tes_type, f"[{prev_tes_type}]")
                flash(f"🧠 {year_num} год: Тип ТЭС скопирован из предыдущего года ({tes_name})", "info")

            if mf.id_fuel in (None, 100) and prev_fuel_type not in (None, 100):
                changes.append(f"{year_num} - Топливо: {mf.id_fuel} → {prev_fuel_type}")
                mf.id_fuel = prev_fuel_type
                fuel_name = fuel_names.get(prev_fuel_type, f"[{prev_fuel_type}]")
                flash(f"🧠 {year_num} год: Топливо скопировано из предыдущего года ({fuel_name})", "info")

        # Обновляем форму
        j = year_num - start_year
        if 0 <= j < len(advanced_form.tes_types):
            advanced_form.tes_types[j].tes_type.data = mt.id_tes_type
        if 0 <= j < len(advanced_form.fuels):
            advanced_form.fuels[j].fuel_type.data = mf.id_fuel

        prev_tes_type = mt.id_tes_type
        prev_fuel_type = mf.id_fuel


def recalculate_machine_years_by_p_ust(machine, changes, year_features):
    years_by_ust = sorted(
        [(mp.year.number, mp.p_ust) for mp in machine.machine_powers if isinstance(mp.p_ust, Decimal)],
        key=lambda t: t[0],
    )
    if not years_by_ust:
        return

    nonzero = [(y, p) for y, p in years_by_ust if p and p > 0]
    if not nonzero:
        return

    new_expl_year = nonzero[0][0]
    last_nz_index = max(i for i, (_, p) in enumerate(years_by_ust) if p > 0)
    new_decomp_year = years_by_ust[last_nz_index][0]

    # --- Год ввода: не задаём, если уже есть ---
    if machine.date_exploitation is None:
        machine.date_exploitation = new_expl_year
        changes.append(f"Год ввода: — → {new_expl_year}")
        flash(f"🧠 Год ввода автоматически определён: {new_expl_year}", "info")

    # --- Год вывода ---
    if new_decomp_year < Config.END_YEAR:
        if machine.date_decompressing_expected != new_decomp_year:
            changes.append(f"Год вывода: {machine.date_decompressing_expected} → {new_decomp_year}")
            flash(f"🧠 Год вывода автоматически определён: {new_decomp_year}", "info")
            machine.date_decompressing_expected = new_decomp_year
    else:
        if machine.date_decompressing_expected is not None:
            changes.append(f"Год вывода: {machine.date_decompressing_expected} → —")
            flash(f"🧠 Год вывода удалён: агрегат продолжает работать", "info")
            machine.date_decompressing_expected = None

    # Модернизация по плану
    nonzero_plan_years = [
        (y, p) for y, p in years_by_ust
        if year_features.get(y) and getattr(year_features[y], "name", None) == "план" and p and p > 0
    ]

    found = False

    for i in range(1, len(nonzero_plan_years)):
        prev_y, prev_p = nonzero_plan_years[i - 1]
        curr_y, curr_p = nonzero_plan_years[i]
        if prev_p != curr_p:
            if machine.date_modernization_expected != curr_y:
                changes.append(f"Год модернизации: {machine.date_modernization_expected} → {curr_y}")
                flash(f"🧠 Год модернизации автоматически определён: {curr_y}", "info")
                machine.date_modernization_expected = curr_y
            found = True
            break

    if not found and machine.date_modernization_expected is not None:
        flash("⚠️ Расчётный год модернизации не найден, но в данных указано значение. Проверьте корректность вручную.", "warning")


