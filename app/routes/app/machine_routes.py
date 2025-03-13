from config import Config
from flask import render_template, request, session, redirect, url_for, flash
from . import app_bp
from app.models.logs_models import Log
from app.forms.machine_forms import MachineFilterForm, EditMachineForm
from app.models.stations_models import ConditionType, StationType, TesType, MachineType, TesMachineType, MachineTesType, Machine, MachinePower, MachineFuel
from app.models.fuels_models import Fuel
from app.models.years_models import Year, YearFeature
from app.models.energy_systems_models import EnergyArea
from app.models.gen_companies_models import GenCompany
from app.services.station_services import log_to_db, get_machine_by_id, get_station_by_id, convert_to_iso_date
from flask_login import login_required
from app.routes.auth import role_required
from app import db


def log_to_db(username, action, details=None):
    """Записывает лог действия пользователя в базу данных."""
    try:
        log_entry = Log(username=username, action=action, details=details)
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка записи лога: {e}")


@app_bp.route("/machine_details/<int:station_id>/<int:machine_id>", methods=["GET", "POST"])
@login_required
@role_required('super-admin')
def machine_details(station_id, machine_id):
    """Маршрут для отображения и редактирования агрегата электростанции с логированием."""
    # Получаем данные
    machine = get_machine_by_id(machine_id)
    station = get_station_by_id(station_id)
    
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, f"Открыта страница агрегата электростанции {station.name} ({station.regional_district.name})")

    try:

        # Инициализация форм
        main_form = MachineFilterForm(prefix="main_", obj=machine)
        advanced_form = EditMachineForm(prefix="adv_")

       # Собираем словари имеющихся записей
        machine_powers = {mp.year.number: mp for mp in machine.machine_powers}
        machine_fuels = {mf.year.number: mf for mf in machine.machine_fuels}
        machine_tes_types = {mt.year.number: mt for mt in machine.machine_tes_types}
        
        # Получаем нужные года
        start_year = request.args.get("start_year", Config.START_YEAR, type=int)
        end_year = request.args.get("end_year", Config.END_YEAR, type=int)
        years = Year.query.filter(Year.number >= start_year, Year.number <= end_year).all()
        year_dict = {y.number: y for y in years}
        year_features = {y.number: {"name": y.year_feature.name if y.year_feature else "Нет данных"} for y in years} if years else {}

        # Заполняем choices в основной форме
        main_form.id_condition_type.choices = [(c.id, c.name) for c in ConditionType.query.all()] or [(0, "не указано")]
        main_form.id_gen_company.choices = [(g.id, g.name) for g in GenCompany.query.all()] or [(0, "не указано")]
        main_form.id_energy_area.choices = [(ea.id, ea.name) for ea in EnergyArea.query.all()] or [(0, "не указано")]
        main_form.id_station_type.choices = [(st.id, st.name) for st in StationType.query.all()] or [(0, "не указано")]
        main_form.id_machine_type.choices = [(mt.id, mt.name) for mt in MachineType.query.all()] or [(0, "не указано")]
        main_form.id_tes_machine_type.choices = [(tmt.id, tmt.name) for tmt in TesMachineType.query.all()] or [(0, "не указано")]

        tes_type_choices = [(tt.id, tt.name) for tt in TesType.query.all()]
        if not tes_type_choices:
            tes_type_choices.append((0, "не указано"))

        fuel_choices = [(f.id, f.name) for f in Fuel.query.all()]
        if not fuel_choices:
            fuel_choices.append((0, "не указано"))

        # Заполняем choices для вложенных форм
        for entry in advanced_form.tes_types:
            entry.tes_type.choices = tes_type_choices

        for entry in advanced_form.fuels:
            entry.fuel_type.choices = fuel_choices

        ## Cначала** добавляем поля во вложенные FieldList (powers, tes_types, fuels)
        for year_num in range(start_year, end_year + 1):
            # Убедимся, что в словарях есть объекты для каждого года
            if year_num not in machine_powers:
                mp = MachinePower(id_machine=machine.id, year=year_dict.get(year_num))
                db.session.add(mp)
                machine_powers[year_num] = mp

            if year_num not in machine_tes_types:
                mtt = MachineTesType(id_machine=machine.id, year=year_dict.get(year_num))
                db.session.add(mtt)
                machine_tes_types[year_num] = mtt

            if year_num not in machine_fuels:
                mf = MachineFuel(id_machine=machine.id, year=year_dict.get(year_num))
                db.session.add(mf)
                machine_fuels[year_num] = mf


        # === Формируем поля (append_entry) и задаем им choices/data (для GET) ===
        for year_num in range(start_year, end_year + 1):
            y_obj = year_dict.get(year_num)

            # --- MachinePower ---
            mp = machine_powers.get(year_num)
            if not mp:
                mp = MachinePower(id_machine=machine.id, p_ust=0, p_ogr=0, p_rasp=0, year=y_obj)
                db.session.add(mp)

            power_entry = advanced_form.powers.append_entry()
            if request.method == "GET":
                power_entry.year.data = year_num
                power_entry.p_ust.data = mp.p_ust
                power_entry.p_ogr.data = mp.p_ogr
                power_entry.p_rasp.data = mp.p_rasp

            # --- MachineTesType ---
            mt = machine_tes_types.get(year_num)
            if not mt:
                mt = MachineTesType(id_machine=machine.id, id_tes_type=None, year=y_obj)
                db.session.add(mt)

            tes_entry = advanced_form.tes_types.append_entry()
            tes_entry.tes_type.choices = tes_type_choices
            if request.method == "GET":
                tes_entry.year.data = year_num
                tes_entry.tes_type.data = mt.id_tes_type if mt.id_tes_type is not None else None

            # --- MachineFuel ---
            mf = machine_fuels.get(year_num)
            if not mf:
                mf = MachineFuel(id_machine=machine.id, id_fuel=None, year=y_obj)
                db.session.add(mf)

            fuel_entry = advanced_form.fuels.append_entry()
            fuel_entry.fuel_type.choices = fuel_choices
            if request.method == "GET":
                fuel_entry.year.data = year_num
                fuel_entry.fuel_type.data = mf.id_fuel if mf.id_fuel else 0

        # === Если POST, то обработка данных и сохранение ===
        if request.method == "POST":
            main_form.process(request.form)
            advanced_form.process(request.form)

            # Получаем нужные года
            start_year = request.args.get("start_year", Config.START_YEAR, type=int)
            end_year = request.args.get("end_year", Config.END_YEAR, type=int)
            years = Year.query.filter(Year.number >= start_year, Year.number <= end_year).all()
            year_dict = {y.number: y for y in years}
            year_features = {y.number: {"name": y.year_feature.name if y.year_feature else "Нет данных"} for y in years} if years else {}

            # Заполняем choices в основной форме
            main_form.id_condition_type.choices = [(c.id, c.name) for c in ConditionType.query.all()] or [(0, "не указано")]
            main_form.id_gen_company.choices = [(g.id, g.name) for g in GenCompany.query.all()] or [(0, "не указано")]
            main_form.id_energy_area.choices = [(ea.id, ea.name) for ea in EnergyArea.query.all()] or [(0, "не указано")]
            main_form.id_station_type.choices = [(st.id, st.name) for st in StationType.query.all()] or [(0, "не указано")]
            main_form.id_machine_type.choices = [(mt.id, mt.name) for mt in MachineType.query.all()] or [(0, "не указано")]
            main_form.id_tes_machine_type.choices = [(tmt.id, tmt.name) for tmt in TesMachineType.query.all()] or [(0, "не указано")]
            tes_type_choices = [(tt.id, tt.name) for tt in TesType.query.all()]
            if not tes_type_choices:
                tes_type_choices.append((0, "не указано"))

            fuel_choices = [(f.id, f.name) for f in Fuel.query.all()]
            if not fuel_choices:
                fuel_choices.append((0, "не указано"))

            # Заполняем choices для вложенных форм
            for entry in advanced_form.tes_types:
                entry.tes_type.choices = tes_type_choices

            for entry in advanced_form.fuels:
                entry.fuel_type.choices = fuel_choices


            if not main_form.validate():
                print("Ошибки в main_form:", main_form.errors)
            if not advanced_form.validate():
                print("Ошибки в advanced_form:", advanced_form.errors)


            if main_form.validate() and advanced_form.validate():
                try:
                    changes = []

                    # Фиксируем изменения параметров агрегата
                    field_mappings = {
                        "id_condition_type": lambda x: ConditionType.query.get(x).name if x else "не указано",
                        "id_gen_company": lambda x: GenCompany.query.get(x).name if x else "не указано",
                        "id_station_type": lambda x: StationType.query.get(x).name if x else "не указано",
                        "id_machine_type": lambda x: MachineType.query.get(x).name if x else "не указано",
                        "id_tes_machine_type": lambda x: TesType.query.get(x).name if x else "не указано",
                        "machine_name": str,
                        "note": lambda x: x if x else "не указано"
                    }

                    for field, transform in field_mappings.items():
                        if f"main_{field}" in request.form:
                            old_value = getattr(machine, field)
                            new_value = getattr(main_form, field).data

                            if old_value != new_value and new_value is not None:
                                old_value_transformed = transform(old_value)
                                new_value_transformed = transform(new_value)

                                # Исключаем пустые изменения
                                if old_value_transformed != new_value_transformed:
                                    changes.append(f"{field}: {old_value_transformed} -> {new_value_transformed}")
                                    setattr(machine, field, new_value)

                    # Фиксируем изменения дат
                    date_fields = [
                        "date_exploitation", "date_commission_expected", "date_commission_fact",
                        "date_joining_expected", "date_joining_fact", "date_detatchment_fact",
                        "date_decompressing_expected", "date_decompressing_fact",
                        "date_modernization_expected", "date_relabing_fact", "date_update_fact"
                    ]

                    for field in date_fields:
                        if f"main_{field}" in request.form:
                            old_value = getattr(machine, field)
                            new_value = convert_to_iso_date(getattr(main_form, field).data)

                            if old_value != new_value and new_value is not None:
                                changes.append(f"{field}: {old_value} -> {new_value}")
                                setattr(machine, field, new_value)

                    # Фиксируем изменения вложенных данных (мощности, топлива, типы ТЭС)
                    for i, year_num in enumerate(range(start_year, end_year + 1)):
                        # MachinePower
                        mp_obj = machine.machine_powers[i]
                        
                        for attr in ["p_ust", "p_ogr", "p_rasp"]:
                            field_name = f"adv_powers-{i}-{attr}"
                            
                            if field_name in request.form:  # Проверяем, действительно ли значение было отправлено в POST-запросе
                                old_value = getattr(mp_obj, attr)
                                new_value = getattr(advanced_form.powers[i], attr).data
                                
                                if new_value is None:  # Если новое значение не задано, оставляем старое
                                    new_value = old_value
                                
                                # Сравниваем с округлением, чтобы избежать ложных изменений (60.0001 vs 60.0)
                                if old_value is not None and round(float(old_value), 4) != round(float(new_value), 4):
                                    changes.append(f"{year_num} - {attr}: {old_value} -> {new_value}")
                                    setattr(mp_obj, attr, new_value)


                        # MachineTesType
                        mt_obj = machine.machine_tes_types[i]
                        field_name = f"adv_tes_types-{i}-tes_type"

                        if field_name in request.form:  # Проверяем, было ли поле в POST-запросе
                            old_value = TesType.query.get(mt_obj.id_tes_type).name if mt_obj.id_tes_type else "не указано"
                            new_value_id = advanced_form.tes_types[i].tes_type.data
                            new_value = TesType.query.get(new_value_id).name if new_value_id else "не указано"

                            if old_value != new_value and new_value_id is not None:
                                changes.append(f"{year_num} - Тип ТЭС: {old_value} -> {new_value}")
                                mt_obj.id_tes_type = new_value_id


                        # MachineFuel
                        mf_obj = machine.machine_fuels[i]
                        if f"adv_fuels-{i}-fuel_type" in request.form:
                            old_value = Fuel.query.get(mf_obj.id_fuel).name if mf_obj.id_fuel else "не указано"
                            new_value_id = advanced_form.fuels[i].fuel_type.data
                            new_value = Fuel.query.get(new_value_id).name if new_value_id else "не указано"

                            if old_value != new_value and new_value_id is not None:
                                changes.append(f"{year_num} - Топливо: {old_value} -> {new_value}")
                                mf_obj.id_fuel = new_value_id

                    i = 0
                    for year_num in range(start_year, end_year + 1):
                        # MachinePower
                        mp_obj = machine_powers[year_num]
                        mp_obj.p_ust  = advanced_form.powers[i].p_ust.data
                        mp_obj.p_ogr  = advanced_form.powers[i].p_ogr.data
                        mp_obj.p_rasp = advanced_form.powers[i].p_rasp.data

                        # MachineTesType
                        mtt_obj = machine_tes_types[year_num]
                        mtt_obj.id_tes_type = advanced_form.tes_types[i].tes_type.data

                        # MachineFuel
                        mf_obj = machine_fuels[year_num]
                        mf_obj.id_fuel = advanced_form.fuels[i].fuel_type.data

                        i += 1

                    db.session.commit()
                    if changes:
                        log_to_db(user, f"Изменения в электростанции {station.name} ({station.regional_district.name}) в агрегате №{machine.machine_number} {machine.machine_name}", details="; ".join(changes))
                    flash("Данные агрегата успешно обновлены!", "success")
                    
                except Exception as e:
                    db.session.rollback()
                    log_to_db(user, f"Ошибка обновления агрегата №{machine.machine_number} {machine.machine_name} электростанции {station.name} ({station.regional_district.name})", details=str(e))
                    print(f"Ошибка при сохранении: {str(e)}")
                    flash(f"Ошибка при обновлении данных: {str(e)}", "danger")

        else:
            # 9. Если это GET-запрос: заполняем поля форм (obj=machine) или вручную
            #    в том числе динамические поля для каждого года
            main_form.process(obj=machine)

            i = 0
            for year_num in range(start_year, end_year + 1):
                mp_obj  = machine_powers[year_num]
                mtt_obj = machine_tes_types[year_num]
                mf_obj  = machine_fuels[year_num]

                # MachinePower
                advanced_form.powers[i].year.data   = year_num
                advanced_form.powers[i].p_ust.data  = mp_obj.p_ust
                advanced_form.powers[i].p_ogr.data  = mp_obj.p_ogr
                advanced_form.powers[i].p_rasp.data = mp_obj.p_rasp

                # MachineTesType
                advanced_form.tes_types[i].year.data = year_num
                advanced_form.tes_types[i].tes_type.choices = tes_type_choices
                advanced_form.tes_types[i].tes_type.data    = mtt_obj.id_tes_type

                # MachineFuel
                advanced_form.fuels[i].year.data = year_num
                advanced_form.fuels[i].fuel_type.choices = fuel_choices
                advanced_form.fuels[i].fuel_type.data    = mf_obj.id_fuel

                i += 1

        return render_template("stations/machine_details.html", 
                               start_year=start_year, 
                               end_year=end_year, 
                               form=main_form, 
                               advanced_form=advanced_form, 
                               station=station, 
                               machine=machine,
                               year_features=year_features)

    except Exception as e:
        flash(f"Неожиданная ошибка: {e}", "danger")
        log_to_db(user, f"Ошибка загрузки агрегата №{machine.machine_number} {machine.machine_name} электростанции {station.name} ({station.regional_district.name})", details=str(e))
        return render_template("stations/machine_details.html", 
                               start_year=start_year, 
                               end_year=end_year, 
                               form=main_form, 
                               advanced_form=advanced_form, 
                               station=station, 
                               machine=machine,
                               year_features=year_features), 500