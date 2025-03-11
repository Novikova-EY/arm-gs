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
    
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, f"Открыта страница агрегата электростанции ID {machine_id}")

    try:
        # Получаем данные
        machine = get_machine_by_id(machine_id)
        station = get_station_by_id(station_id)

        # Инициализация форм
        main_form = MachineFilterForm(prefix="main_", obj=machine)
        advanced_form = EditMachineForm(prefix="adv_")

        start_year = request.args.get("start_year", Config.START_YEAR, type=int)
        end_year = request.args.get("end_year", Config.END_YEAR, type=int)

        # Заполняем choices в основной форме
        main_form.id_condition_type.choices = [(c.id, c.name) for c in ConditionType.query.all()]
        main_form.id_gen_company.choices = [(g.id, g.name) for g in GenCompany.query.all()]
        main_form.id_energy_area.choices = [(ea.id, ea.name) for ea in EnergyArea.query.all()]
        main_form.id_station_type.choices = [(st.id, st.name) for st in StationType.query.all()]
        main_form.id_machine_type.choices = [(mt.id, mt.name) for mt in MachineType.query.all()]

        # Получаем список всех доступных типов ТЭС
        tes_type_choices = [(t.id, t.name) for t in TesType.query.all()]

        # Определяем значение по умолчанию: сначала берём у машины, если нет - у станции
        default_tes_type = machine.id_tes_type if machine and machine.id_tes_type else (station.id_tes_type if station and hasattr(station, 'id_tes_type') else 0)

        for entry in advanced_form.tes_types:
            entry.tes_type.choices = tes_type_choices if tes_type_choices else [(default_tes_type, "не указано")]
            
            # Если данных нет, явно устанавливаем значение из default_tes_type
            if entry.tes_type.data is None or entry.tes_type.data == '':
                entry.tes_type.data = default_tes_type

        fuel_choices = [(f.id, f.name) for f in Fuel.query.all()] or [(0, "не указано")]

        # Создаём словарь: {год: id топлива}
        default_fuel_types_by_year = {mf.year.number: mf.id_fuel for mf in machine.machine_fuels}

        for entry in advanced_form.fuels:
            entry.fuel_type.choices = fuel_choices  # Заполняем `choices` топливом

            year = entry.year.data  # Берём год из формы
            if year in default_fuel_types_by_year:
                entry.fuel_type.data = default_fuel_types_by_year[year]  # Устанавливаем топливо из БД

        # Получаем нужные года
        years = Year.query.filter(Year.number >= start_year, Year.number <= end_year).all()
        year_dict = {y.number: y for y in years}

        # Получаем все года с их признаками
        years = Year.query.filter(Year.number >= start_year, Year.number <= end_year).all()

        # Создаем словарь year_features с безопасной обработкой пустого запроса
        year_features = {y.number: {"name": y.year_feature.name if y.year_feature else "Нет данных"} for y in years} if years else {}


        # Уже существующие записи в БД
        machine_powers = {mp.year.number: mp for mp in machine.machine_powers}
        machine_fuels = {mf.year.number: mf for mf in machine.machine_fuels}
        machine_tes_types = {mt.year.number: mt for mt in machine.machine_tes_types}

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

        print("DEBUG: year_features:", year_features)
        # === Если POST, то обработка данных и сохранение ===
        if request.method == "POST":
            main_form.process(request.form)
            advanced_form.process(request.form)

            # Повторное заполнение choices перед валидацией формы
            main_form.id_condition_type.choices = [(c.id, c.name) for c in ConditionType.query.all()] or [(0, "не указано")]
            main_form.id_gen_company.choices = [(g.id, g.name) for g in GenCompany.query.all()] or [(0, "не указано")]
            main_form.id_energy_area.choices = [(ea.id, ea.name) for ea in EnergyArea.query.all()] or [(0, "не указано")]
            main_form.id_station_type.choices = [(st.id, st.name) for st in StationType.query.all()] or [(0, "не указано")]
            main_form.id_machine_type.choices = [(mt.id, mt.name) for mt in MachineType.query.all()] or [(6, "не указано")]

            # Получаем список всех доступных типов ТЭС
            tes_type_choices = [(t.id, t.name) for t in TesType.query.all()]

            # Определяем значение по умолчанию: сначала берём у машины, если нет - у станции
            default_tes_type = machine.id_tes_type if machine and machine.id_tes_type else (station.id_tes_type if station and hasattr(station, 'id_tes_type') else 0)

            for entry in advanced_form.tes_types:
                entry.tes_type.choices = tes_type_choices if tes_type_choices else [(default_tes_type, "не указано")]
                
                # Если данных нет, явно устанавливаем значение из default_tes_type
                if entry.tes_type.data is None or entry.tes_type.data == '':
                    entry.tes_type.data = default_tes_type

            # Получаем все года с их признаками
            years = Year.query.filter(Year.number >= start_year, Year.number <= end_year).all()

            # Создаем словарь year_features с безопасной обработкой пустого запроса
            year_features = {y.number: {"name": y.year_feature.name if y.year_feature else "Нет данных"} for y in years} if years else {}


            fuel_choices = [(f.id, f.name) for f in Fuel.query.all()] or [(0, "не указано")]
            for entry in advanced_form.fuels:
                entry.fuel_type.choices = [(f.id, f.name) for f in Fuel.query.all()] or [(0, "не указано")]

            if main_form.validate() and advanced_form.validate():
                
                try:
                    # Обновляем Machine
                    machine.id_condition_type = main_form.id_condition_type.data
                    machine.id_gen_company = main_form.id_gen_company.data
                    machine.id_station_type = main_form.id_station_type.data
                    machine.id_machine_type = main_form.id_machine_type.data
                    machine.id_tes_machine_type = main_form.id_tes_machine_type.data
                    machine.machine_name = main_form.machine_name.data
                    machine.note = main_form.note.data

                    # Преобразуем даты
                    machine.date_exploitation = convert_to_iso_date(main_form.date_exploitation.data)

                    # Обновляем мощности
                    for power_field in advanced_form.powers:
                        year_num = power_field.year.data
                        machine_powers[year_num].p_ust = power_field.p_ust.data
                        machine_powers[year_num].p_ogr = power_field.p_ogr.data
                        machine_powers[year_num].p_rasp = power_field.p_rasp.data

                    # Обновляем тип ТЭС
                    for tes_field in advanced_form.tes_types:
                        year_num = tes_field.year.data
                        machine_tes_types[year_num].id_tes_type = tes_field.tes_type.data

                    db.session.commit()
                    flash("Данные агрегата успешно обновлены!", "success")
                    

                except Exception as e:
                    db.session.rollback()
                    print(f"Ошибка БД: {e}")
                    flash("Ошибка при обновлении данных. Попробуйте позже.", "danger")

        return render_template("stations/machine_details.html", 
                               start_year=start_year, 
                               end_year=end_year, 
                               form=main_form, 
                               advanced_form=advanced_form, 
                               default_tes_type=default_tes_type,
                               station=station, 
                               machine=machine,
                               year_features=year_features)

    except Exception as e:
        flash(f"Неожиданная ошибка: {e}", "danger")
        return render_template("stations/machine_details.html", 
                               start_year=start_year, 
                               end_year=end_year, 
                               default_tes_type=default_tes_type, 
                               form=main_form, 
                               advanced_form=advanced_form, 
                               station=station, 
                               machine=machine,
                               year_features=year_features), 500
