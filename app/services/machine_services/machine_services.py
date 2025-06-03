from config import Config
from app import db
import traceback
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from sqlalchemy.orm.attributes import flag_modified
from flask import request, render_template, request, flash, redirect, url_for
from app.services.logging_services.logging_service import log_to_db
from app.models import *
from app.forms.machine_forms import MachineFilterForm, EditMachineForm
from app.services.station_services.help_services import (
    convert_to_date
)
from app.services.station_services.station_services import (
    recalculate_station_power,
    get_machine_by_id,
    get_station_by_id,
)
from app.services.station_services.help_services import (
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

    station = get_station_by_id(station_id)
    machine = get_machine_by_id(machine_id)
    year_features = get_year_features()

    _fill_main_form_choices(main_form)
    _fill_advanced_form_choices(advanced_form)

    if not main_form.validate() or not advanced_form.validate():
        flash("Ошибка в заполнении формы. Проверьте поля.", "danger")
        return render_template(
            "stations/machine_details.html",
            start_year=start_year,
            end_year=end_year,
            rounding_digits=rounding_digits,
            main_form=main_form,
            advanced_form=advanced_form,
            station=station,
            machine=machine,
            year_features=year_features,
        )

    try:
        changes = []

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
            "date_exploitation",
            "date_commission_fact",
            "date_joining_expected",
            "date_joining_fact",
            "date_detatchment_fact",
            "date_decompressing_expected",
            "date_decompressing_fact",
            "date_modernization_expected",
            "date_relabing_fact",
            "date_update_fact",
        ]

        for fld in date_fields:
            raw_form_value = getattr(main_form, fld).data
            if fld in {"date_exploitation", "date_decompressing_expected", "date_modernization_expected"}:
                # Эти поля — числа (годы)
                new_val = int(raw_form_value) if raw_form_value else None
                old_val = getattr(machine, fld)
                if old_val != new_val:
                    changes.append(f"{fld}: {old_val} → {new_val}")
                    setattr(machine, fld, new_val)
            else:
                # Остальные — даты (строки, которые превращаются в datetime.date)
                new_val = convert_to_date(raw_form_value)
                old_val = getattr(machine, fld)

                # Приведение к строкам для логирования
                old_val_str = old_val.strftime("%Y-%m-%d") if isinstance(old_val, (date, datetime)) else str(old_val) if old_val else None
                new_val_str = new_val.strftime("%Y-%m-%d") if isinstance(new_val, (date, datetime)) else str(new_val) if new_val else None

                if old_val_str != new_val_str:
                    changes.append(f"{fld}: {old_val_str} → {new_val_str}")
                    setattr(machine, fld, new_val)

        # Гарантируем правильную привязку по годам
        powers_map = {mp.year.number: mp for mp in machine.machine_powers}
        tes_map = {mt.year.number: mt for mt in machine.machine_tes_types}
        fuel_map = {mf.year.number: mf for mf in machine.machine_fuels}

        for i, year_num in enumerate(range(start_year, end_year + 1)):
            mp = powers_map[year_num]
            mt = tes_map[year_num]
            mf = fuel_map[year_num]

            p_ust_raw = to_decimal(advanced_form.powers[i].p_ust.data)
            p_ogr_raw = to_decimal(advanced_form.powers[i].p_ogr.data)
            p_rasp_raw = to_decimal(advanced_form.powers[i].p_rasp.data)

            p_ust = p_ust_raw if p_ust_raw is not None else mp.p_ust
            p_ogr = p_ogr_raw if p_ogr_raw is not None else mp.p_ogr
            p_rasp = p_rasp_raw if p_rasp_raw is not None else mp.p_rasp

            p_ust, p_ogr, p_rasp = autofill_powers_if_possible_decimal(p_ust, p_ogr, p_rasp, year_num)

            for attr, val in (("p_ust", p_ust), ("p_ogr", p_ogr), ("p_rasp", p_rasp)):
                old_val = getattr(mp, attr)
                if is_same_decimal(old_val, val):
                    continue
                setattr(mp, attr, val)
                flag_modified(mp, attr)

                old_val_str = format_decimal_for_display(old_val, digits=0)
                new_val_str = format_decimal_for_display(val, digits=0)
                changes.append(f"{year_num} – {attr}: {old_val_str} → {new_val_str}")

            err = None
            if p_rasp > p_ust:
                err = f"Ошибка: в {year_num} году Ррасп ({p_rasp}) > Руст ({p_ust})"
            elif p_ogr > p_ust:
                err = f"Ошибка: в {year_num} году Рогр ({p_ogr}) > Руст ({p_ust})"
            elif abs(p_ogr - (p_ust - p_rasp)) > Decimal("0.000001"):
                err = f"Ошибка: в {year_num} году Рогр ({p_ogr}) ≠ Руст ({p_ust}) − Ррасп ({p_rasp})"

            new_tt = advanced_form.tes_types[i].tes_type.data
            new_fuel = advanced_form.fuels[i].fuel_type.data

            if mt.id_tes_type != new_tt and new_tt is not None:
                changes.append(f"{year_num} – Тип ТЭС: {mt.id_tes_type} → {new_tt}")
                mt.id_tes_type = new_tt

            if mf.id_fuel != new_fuel and new_fuel is not None:
                changes.append(f"{year_num} – Топливо: {mf.id_fuel} → {new_fuel}")
                mf.id_fuel = new_fuel

            if err:
                flash(err, "danger")
                return render_template(
                    "stations/machine_details.html",
                    start_year=start_year,
                    end_year=end_year,
                    rounding_digits=rounding_digits,
                    main_form=main_form,
                    advanced_form=advanced_form,
                    station=station,
                    machine=machine,
                    year_features=year_features,
                )

        autofill_tes_and_fuel_chain(machine, advanced_form, changes, start_year, end_year)
        recalculate_station_power(station, start_year, end_year)
        recalculate_machine_years_by_p_ust(machine, changes, year_features)

        db.session.commit()
        if changes:
            log_to_db(
                user,
                f"Изменения в станции {station.name} ({station.regional_district.name}), агрегат №{machine.machine_number}",
                details="; ".join(changes),
            )
            flash("Данные агрегата успешно обновлены!", "success")
        else:
            flash("Изменений не обнаружено", "info")

        return redirect(url_for("station_bp.machine_details",
                                start_year=start_year,
                                end_year=end_year,
                                rounding_digits=rounding_digits,
                                station_id=station.id,
                                machine_id=machine.id))

    except Exception as exc:
        db.session.rollback()
        traceback.print_exc()
        flash(f"Ошибка при обновлении данных: {exc}", "danger")
        log_to_db(
            user,
            f"Ошибка обновления агрегата №{machine.machine_number} {machine.machine_name} станции {station.name}",
            details=str(exc),
        )
        return render_template(
            "stations/machine_details.html",
            start_year=start_year,
            end_year=end_year,
            rounding_digits=rounding_digits,
            main_form=main_form,
            advanced_form=advanced_form,
            station=station,
            machine=machine,
            year_features=year_features,
        )



def _fill_main_form_choices(form):
    form.id_condition_type.choices = [(c.id, c.name) for c in ConditionType.query.order_by(ConditionType.id).all()]
    form.id_gen_company.choices = [(0, "не указано")] + [(g.id, g.name) for g in GenCompany.query.order_by(GenCompany.id).all()]
    form.id_energy_area.choices = [(ea.id, ea.name) for ea in EnergyArea.query.order_by(EnergyArea.id).all()]
    form.id_station_type.choices = [(st.id, st.name) for st in StationType.query.order_by(StationType.id).all()]
    form.id_machine_type.choices = [(mt.id, mt.name) for mt in MachineType.query.order_by(MachineType.id).all()]
    form.id_tes_machine_type.choices = [(tmt.id, tmt.name) for tmt in TesMachineType.query.order_by(TesMachineType.id).all()]


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


from flask import flash

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
