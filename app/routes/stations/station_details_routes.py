from . import station_bp
from app import db
from config import Config
from decimal import Decimal
from flask import (
    render_template, request, redirect, url_for, flash, session, current_app, send_file, jsonify, abort
)
from collections import defaultdict
from app.services.logging_services.logging_service import log_to_db
from flask_login import login_required
from app.routes.auth import role_required
from flask import session
from app.forms.station_forms import StationFilterForm
from app.forms.machine_forms import MachineFilterSmallForm
from app.models import (
    RegionalDistrict, 
    StationGroup, 
    RegionalEnergySystem, 
    ConditionType, 
    GenCompany, 
    StationPower, 
    MachineTesType, 
    EnergyUnit,
    Machine
)
from app.services.logging_services.logging_service import log_to_db
from app.services.station_services.help_services import (
    get_union_energy_systems, 
    get_regional_districts, 
    get_energy_system_types, 
    get_regional_districts,
    get_federal_districts, 
    get_regional_energy_systems, 
    get_current_year,
    get_condition_type,
    get_station_groups,
    get_gen_companies,
    get_station_groups,
)
from app.services.station_services.station_services import (
    get_stations_list,
    get_station_by_id, 
    extract_filters_from_form, 
    extract_filters_from_args, 
    assign_machine_powers_by_year, 
    get_station_list_template_context, 
    recalculate_station_power,
    get_current_machine_tes_types_map, 
    recalculate_station_powers_by_filtered_machines
)
from app.services.station_services.filters_services import (
    filter_machines,
)
from app.services.station_services.groupped_services import (
    group_stations_hierarchy, 
    group_machines_by_group_and_fuel, 
)
from app.services.station_services.import_station_services import (
    import_station_list_from_excel, 
    import_fuel_tes_station_from_excel, 
)

@station_bp.route("/station_details/<int:station_id>", methods=["GET", "POST"])
@login_required
@role_required('super-admin')
def station_details(station_id):
    """Маршрут для отображения сведений об электростанции с логированием изменений."""

    user = session.get('username', 'Неизвестный пользователь')
    station = get_station_by_id(station_id)
    if not station:
        abort(404)
    regional_district_name = station.regional_district.name if station and station.regional_district else "не указано"
    log_to_db(user, f"Открыта страница электростанции {station.name} ({regional_district_name})")

    form = StationFilterForm()
    form_machines = MachineFilterSmallForm()

    # Получение параметров запроса с дефолтными значениями
    start_year = request.args.get("start_year", Config.START_YEAR, type=int)
    end_year = request.args.get("end_year", Config.END_YEAR, type=int)
    machine_ids_to_delete = request.form.getlist("machines_delete[]", type=int)

    # Получаем данные по станции
    condition_types = get_condition_type()
    station_groups = get_station_groups()
    gen_companies = get_gen_companies()

    recalculate_station_power(station, start_year, end_year)

    # Получаем мощности по годам из StationPower
    station.powers_by_year = {
        sp.year_number: {
            "p_ust": sp.p_ust,
            "p_ogr": sp.p_ogr,
            "p_rasp": sp.p_rasp
        }
        for sp in StationPower.query.filter_by(id_station=station.id).filter(
            StationPower.year_number >= start_year,
            StationPower.year_number <= end_year
        ).all()
    }

    current_year = get_current_year()

    # Получаем типы ТЭС для текущего года из MachineTesType
    machine_tes_types_map = get_current_machine_tes_types_map()

    # Загружаем списки данных из сервисов
    regional_districts_list, regional_district_names = get_regional_districts()
    federal_districts, regional_district_mapping = get_federal_districts()
    regional_energy_systems_list, regional_energy_system_names = get_regional_energy_systems()
    union_energy_systems, union_energy_system_names, _ = get_union_energy_systems()
    energy_system_types, energy_system_type_names = get_energy_system_types()

    # Заполняем список субъектов РФ
    form.id_regional_district.choices = [(d["id"], d["name"]) for d in regional_districts_list]
    form.id_condition_type.choices = [(ct.id, ct.name) for ct in condition_types]
    form.id_station_group.choices = [(ct.id, ct.name) for ct in station_groups]
    form_machines.id_gen_company.choices = [(gc.id, gc.name) for gc in gen_companies]
    
    form.id_energy_unit.choices = [(eu.id, eu.name) for eu in EnergyUnit.query.order_by(EnergyUnit.id).all()]
    energy_unit_names = [(f.id, f.name) for f in EnergyUnit.query.order_by(EnergyUnit.id).all()]

    try:
        rounding_digits = int(request.args.get('rounding_digits'))
    except (ValueError, TypeError):
        rounding_digits = 1

    if rounding_digits is None or rounding_digits < 0:
        rounding_digits = 1
    
    if request.method == "GET":
        form.process(obj=station)
        if form.id_condition_type.data is None:
            form.id_condition_type.data = 100
        if form.id_energy_unit.data is None:
            form.id_energy_unit.data = 100

    if request.method == "POST":

        if not form.validate():
            print("Ошибки в form:", form.errors)

        changes = []

        if machine_ids_to_delete:
            machines_to_delete = Machine.query.filter(Machine.id.in_(machine_ids_to_delete)).all()
            
            for machine in machines_to_delete:
                try:
                    # Удаление мощностей
                    for mp in machine.machine_powers:
                        db.session.delete(mp)
                    
                    # Удаление топлива
                    for mf in machine.machine_fuels:
                        db.session.delete(mf)

                    # Удаление типов ТЭС
                    for mtt in machine.machine_tes_types:
                        db.session.delete(mtt)

                    changes.append(f"Агрегат {machine.machine_number or '—'} и связанные данные удалены")
                    db.session.delete(machine)
                
                except Exception as e:
                    flash(f"Ошибка при удалении агрегата ID={machine.id}: {e}", "danger")
                    log_to_db(user, f"Ошибка удаления агрегата ID={machine.id}", details=str(e))

            db.session.commit()

            if changes:
                log_to_db(user, f"Агрегаты удалены на станции {station.name}", details="; ".join(changes))
                flash("Выбранные агрегаты и связанные данные были удалены!", "success")

        if form.validate_on_submit():
            try:
                # Проверяем название станции
                if station.name != form.name.data:
                    changes.append(f"Название: {station.name} → {form.name.data}")
                    station.name = form.name.data
                
                # Проверяем состояние станции
                new_condition_type_id = int(form.id_condition_type.data)
                new_condition_type = db.session.query(ConditionType).filter_by(id=new_condition_type_id).first()
                if new_condition_type:
                    old_value = station.condition_type.name if station.condition_type else "не указано"
                    new_value = new_condition_type.name
                    if old_value != new_value:
                        changes.append(f"Состояние: {old_value} → {new_value}")
                    station.id_condition_type = new_condition_type.id
                else:
                    flash("Ошибка: выбранное состояние не найдено!", "danger")


                # Проверяем группу станции
                new_group_id = form.id_station_group.data
                if new_group_id:
                    group_exists = db.session.query(StationGroup).filter_by(id=new_group_id).first()
                    if group_exists:
                        if station.id_group != new_group_id:
                            old_group = station.group.name if station.group else "не указано"
                            new_group = group_exists.name
                            changes.append(f"Группа: {old_group} → {new_group}")
                            station.id_group = new_group_id
                    else:
                        flash("Выбранная группа не существует!", "warning")

                # Проверяем примечание
                old_note = station.note.strip() if station.note and station.note.strip() else None
                new_note = form.note.data.strip() if form.note.data and form.note.data.strip() else None

                if old_note != new_note:
                    changes.append(f"Примечание: {station.note} → {new_note}")
                    station.note = new_note

                # Проверяем субъект РФ
                if station.id_regional_district != form.id_regional_district.data:
                    old_value = station.regional_district.name if station.regional_district else "не указано"
                    new_value = next((d["name"] for d in regional_districts_list if d["id"] == form.id_regional_district.data), "не указано")
                    changes.append(f"Субъект РФ: {old_value} → {new_value}")
                    station.id_regional_district = form.id_regional_district.data

                # Проверяем местоположение
                new_location = form.location.data.strip() if form.location.data.strip() else None
                if station.location != new_location:
                    changes.append(f"Местоположение: {station.location} → {new_location}")
                    station.location = new_location

                # Обновляем федеральный округ
                new_regional_district_obj = db.session.query(RegionalDistrict).filter_by(id=form.id_regional_district.data).first()

                if new_regional_district_obj:
                    old_federal_district = station.regional_district.federal_district.name if station.regional_district.federal_district else "не указано"
                    new_federal_district = new_regional_district_obj.federal_district.name if new_regional_district_obj.federal_district else "не указано"
                    if old_federal_district != new_federal_district:
                        changes.append(f"Федеральный округ: {old_federal_district} → {new_federal_district}")
                    station.regional_district = new_regional_district_obj

                # Обновляем энергосистему
                related_res_obj = db.session.query(RegionalEnergySystem).filter(
                    RegionalEnergySystem.id.in_(
                        regional_district_mapping.get(station.regional_district.id, [])
                    )
                ).first()


                related_res_obj = (
                    db.session.query(RegionalEnergySystem)
                    .join(RegionalDistrict, RegionalEnergySystem.regional_districts)
                    .filter(RegionalDistrict.id == station.id_regional_district)
                    .first()
                )

                if related_res_obj:
                    old_regional_energy_system = (
                        station.regional_district.regional_energy_systems[0].name
                        if station.regional_district.regional_energy_systems
                        else "не указано"
                    )
                    new_regional_energy_system = related_res_obj.name

                    if old_regional_energy_system != new_regional_energy_system:
                        changes.append(f"Региональная энергосистема: {old_regional_energy_system} → {new_regional_energy_system}")

                    old_union_energy_system = (
                        station.regional_district.regional_energy_systems[0].union_energy_system.name
                        if station.regional_district.regional_energy_systems and station.regional_district.regional_energy_systems[0].union_energy_system
                        else "не указано"
                    )
                    new_union_energy_system = (
                        related_res_obj.union_energy_system.name if related_res_obj.union_energy_system else "не указано"
                    )

                    if old_union_energy_system != new_union_energy_system:
                        changes.append(f"ОЭС: {old_union_energy_system} → {new_union_energy_system}")

                    station.regional_district.regional_energy_systems = [related_res_obj]


                # Сохраняем в БД
                db.session.commit()

                if changes:
                    log_to_db(user, f"Изменения в электростанции {station.name} ({regional_district_name})", details="; ".join(changes))

                flash("Изменения в электростанции успешно обновлены!", "success")
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))

            except Exception as e:
                db.session.rollback()
                print(f"Ошибка при обновлении: {str(e)}")
                flash(f"Ошибка при обновлении данных: {str(e)}", "danger")
                log_to_db(user, f"Ошибка обновления электростанции {station.name} ({regional_district_name})", details=str(e))

        if not form_machines.validate():
            print("Ошибки в form_machines:", form_machines.errors)

        if form_machines.validate_on_submit():
            for machine in station.machines:
                fuel_so_key = f"fuel_so_{machine.id}"
                gen_company_key = f"id_gen_company_{machine.id}"
                new_note_key = f"note_{machine.id}"

                new_fuel_so = request.form.get(fuel_so_key, "").strip()
                new_gen_company_id = request.form.get(gen_company_key, type=int)
                new_note = request.form.get(new_note_key, "").strip()

                if machine.fuel_so != new_fuel_so:
                    changes.append(f"Агрегат {machine.machine_number}: Топливо {machine.fuel_so} → {new_fuel_so}")
                    machine.fuel_so = new_fuel_so

                if machine.note != new_note:
                    changes.append(f"Агрегат {machine.machine_number}: Примечание {machine.note} → {new_note}")
                    machine.note = new_note

                # Обновляем собственника агрегата
                if new_gen_company_id:
                    new_gen_company = db.session.query(GenCompany).filter_by(id=new_gen_company_id).first()
                    if new_gen_company:
                        old_gen_company_name = machine.gen_company.name if machine.gen_company else "не указано"
                        if machine.gen_company is None or machine.gen_company.id != new_gen_company_id:
                            changes.append(f"Агрегат {machine.machine_number}: Собственник {old_gen_company_name} → {new_gen_company.name}")
                            machine.gen_company = new_gen_company
                    else:
                        flash(f"Ошибка: выбранная генерирующая компания не существует!", "danger")


            db.session.commit()

            if changes:
                log_to_db(user, f"Обновлены агрегаты станции {station.name}", details="; ".join(changes))
                flash("Изменения агрегатов сохранены!", "success")

            return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))

    
    return render_template(
        "stations/station_details.html",
        form=form,
        form_machines=form_machines,
        station=station,
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year, 
        energy_unit_names=energy_unit_names,
        current_year=current_year,
        machine_tes_types_map=machine_tes_types_map,
        federal_districts=federal_districts,
        regional_districts_list=regional_districts_list,
        regional_energy_systems_list=regional_energy_systems_list,
        union_energy_systems=union_energy_systems,
        energy_system_types=energy_system_types, )
