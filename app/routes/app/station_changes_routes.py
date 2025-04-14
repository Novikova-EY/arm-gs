from config import Config
from flask import (
    render_template, request, redirect, url_for, flash, session, current_app, send_file, jsonify
)
from . import app_bp
from app import db
from app.models.logs_models import Log
from app.forms.station_forms import StationFilterForm
from app.forms.machine_forms import MachineFilterSmallForm
from app.models import Station, Machine, RegionalDistrict, StationGroup, RegionalEnergySystem, ConditionType, GenCompany
from app.services.station_services import (
    get_stations_list, get_union_energy_systems, get_regional_districts, get_energy_system_types, get_regional_districts,
    get_federal_districts, get_regional_energy_systems, get_station_type, get_tes_types, get_tes_machine_types,
    log_to_db, import_station_list_from_excel, export_station_list_to_excel, get_year_features, 
    aggregate_station_power_values, aggregate_power_by_regional_district, get_station_by_id, get_condition_type, 
    get_station_types_list, aggregate_power_by_regional_energy_system, get_station_groups, get_gen_companies,
    import_fuel_tes_station_from_excel, group_machines_by_group_and_fuel, 
)
from flask_login import login_required
from app.routes.auth import role_required
from sqlalchemy import func

def log_to_db(username, action, details=None):
    """Записывает лог действия пользователя в базу данных."""
    try:
        log_entry = Log(username=username, action=action, details=details)
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка записи лога: {e}")


from flask import session

@app_bp.route("/station_changes", methods=["GET", "POST"])
@login_required
@role_required('super-admin')
def station_changes():
    """Маршрут для отображения списка изменений установленной мощности электростанций."""
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница электростанций")

    form = StationFilterForm()

    # Получение параметров запроса
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", "10")
    if per_page == "all":
        per_page = None
    else:
        per_page = int(per_page)
    
    start_year = request.args.get("start_year", Config.START_YEAR, type=int)
    end_year = request.args.get("end_year", Config.END_YEAR, type=int)

    condition_type_filter = request.args.get("condition_type_filter", "")
    energy_system_type_filter = request.args.getlist("energy_system_type_filter", type=int)
    union_energy_system_filter = request.args.getlist("union_energy_system_filter", type=int)
    regional_energy_system_filter = request.args.getlist("regional_energy_system_filter", type=int)
    federal_district_filter = request.args.getlist("federal_district_filter", type=int)
    regional_district_filter = request.args.getlist("regional_district_filter", type=int)
    gen_company_filter = request.args.get("gen_company_filter", "").strip()
    station_name_filter = request.args.get("station_name_filter", "").strip()
    station_type_filter = request.args.getlist("station_type_filter", type=int)
    tes_type_filter = request.args.getlist("tes_type_filter", type=int)
    tes_machine_type_filter = request.args.getlist('tes_machine_type_filter', type=int)
    station_fuel_type_filter = request.args.get("station_fuel_type_filter", "")
        
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    if request.method == "POST":
    
        # Обновление параметров из формы
        page = request.form.get("page", 1, type=int)
        per_page = request.form.get("per_page", 10, type=int)
        sort_by = request.form.get("sort_by", "id")
        sort_dir = request.form.get("sort_dir", "asc")

        condition_type_filter = request.form.get("condition_type_filter", "")
        energy_system_type_filter = request.form.getlist("energy_system_type_filter", type=int)
        union_energy_system_filter = request.form.getlist("union_energy_system_filter", type=int)
        regional_energy_system_filter = request.form.getlist("regional_energy_system_filter", type=int)
        federal_district_filter = request.args.getlist("federal_district_filter", type=int)
        regional_district_filter = request.args.getlist("regional_district_filter", type=int)
        gen_company_filter = request.form.get("gen_company_filter", "").strip()
        station_name_filter = request.args.get("station_name_filter", "").strip()
        station_type_filter = request.form.getlist("station_type_filter", type=int)
        tes_type_filter = request.form.getlist("tes_type_filter", type=int)
        tes_machine_type_filter = request.args.getlist('tes_machine_type_filter', type=int)
        station_fuel_type_filter = request.form.get("station_fuel_type_filter", "")

        # Получение данных из формы
        station_ids = request.form.getlist("station_ids[]")
        station_names = request.form.getlist("station_names[]")
        union_energy_system_ids = request.form.getlist("union_energy_system_ids[]")            

        from collections import defaultdict

        # Группируем субъектов РФ по энергосистемам
        regional_districts_mapping = defaultdict(list)

        # Получаем список всех ID энергосистем
        station_values = request.form.getlist("station_ids[]")

        # Группируем субъектов по энергосистемам
        for system_id in station_values:
            selected_districts = request.form.getlist(f"regional_districts_{system_id}[]")  # Получаем все субъекты для конкретной энергосистемы
            regional_districts_mapping[int(system_id)] = [int(d) for d in selected_districts if d.isdigit()]

        # Формируем данные для обновления
        station_data = []
        for station_id, station_name, union_energy_system_id in zip(
            station_ids, station_names, union_energy_system_ids
        ):
            station_data.append({
                "id": int(station_id) if station_id else None,
                "name": station_name.strip(),
                "union_energy_system_id": int(union_energy_system_id) if union_energy_system_id else None,
                "regional_districts": regional_districts_mapping.get(int(station_id), [])  # Получаем список субъектов
            })

        return redirect(url_for("app_bp.get_stations_list",
                                page=page,
                                per_page=per_page,
                                condition_type_filter = condition_type_filter,
                                energy_system_type_filter = energy_system_type_filter,
                                union_energy_system_filter = union_energy_system_filter,
                                regional_energy_system_filter = regional_energy_system_filter,
                                federal_district_filter = federal_district_filter,
                                regional_district_filter = regional_district_filter,
                                gen_company_filter = gen_company_filter,
                                station_name_filter = station_name_filter,
                                station_type_filter = station_type_filter,
                                tes_type_filter = tes_type_filter,
                                tes_machine_type_filter = tes_machine_type_filter,
                                sort_by=sort_by,
                                sort_dir=sort_dir
        ))

    # Получение данных для отображения
    pagination = get_stations_list(page, 
                                per_page,
                                condition_type_filter,
                                gen_company_filter,
                                station_name_filter,
                                station_type_filter,
                                tes_type_filter,
                                tes_machine_type_filter,
                                energy_system_type_filter,
                                union_energy_system_filter,
                                regional_energy_system_filter,
                                federal_district_filter,
                                regional_district_filter
                                )

    # Фильтруем машины В КОНТРОЛЛЕРЕ
    if tes_type_filter or tes_machine_type_filter:
        for station in pagination["stations"]:
            station.machines = [
                machine for machine in station.machines
                if (not tes_type_filter or machine.id_tes_type in tes_type_filter) and
                (not tes_machine_type_filter or machine.id_tes_machine_type in tes_machine_type_filter)
            ]

        # Удаляем станции без машин
        filtered_stations = [station for station in pagination["stations"] if station.machines]

        # Пересчитываем количество станций В БД с учетом фильтров
        total_count_query = db.session.query(func.count(Station.id)).join(Station.machines)

        if tes_type_filter:
            total_count_query = total_count_query.filter(Machine.id_tes_type.in_(tes_type_filter))

        if tes_machine_type_filter:
            total_count_query = total_count_query.filter(Machine.id_tes_machine_type.in_(tes_machine_type_filter))

        # Общее число станций в БД (не только на текущей странице)
        total_count = total_count_query.scalar()

        # Пересчитываем количество страниц
        total_pages = max(1, (total_count + per_page - 1) // per_page) if per_page else 1

        # Если после фильтрации страница пустая и есть предыдущие страницы — показываем предыдущую
        if not filtered_stations and page > 1:
            return redirect(url_for('your_view_function', page=page - 1, per_page=per_page))

        # Обновляем данные в pagination
        pagination["stations"] = filtered_stations
        pagination["total_count"] = total_count
        pagination["total_pages"] = total_pages

    if pagination["page"] > pagination["total_pages"]:
        pagination["page"] = pagination["total_pages"]

    print("Общее количество станций:", pagination["total_count"])
    print("Элементов на странице:", len(pagination["stations"]))
    print("Текущая страница:", pagination["page"])
    print("Всего страниц:", pagination["total_pages"])

    # Собираем типы энергоблоков для каждой станции
    for station in pagination["stations"]:
        get_station_types_list(station)
    
    pagination["stations"] = group_machines_by_group_and_fuel(pagination["stations"])

    # Сортировка машин внутри каждой станции по id_station_type
    for station in pagination["stations"]:
        station.machines.sort(key=lambda machine: machine.id_station_type)
   
    # Подготовка данных для формы
    energy_system_type_list, energy_system_type_names = get_energy_system_types()

    union_energy_system_list, union_energy_system_names, regional_energy_system_mapping = get_union_energy_systems()
    regional_energy_system_list, regional_energy_system_names = get_regional_energy_systems()
    federal_district_list, regional_district_mapping = get_federal_districts()

    regional_district_list, regional_district_names  = get_regional_districts()
    regional_district_dict = {int(regional_district["id"]): regional_district for regional_district in regional_district_list}

    station_type_list = get_station_type()
    tes_type_list = get_tes_types()
    tes_machine_type_list = get_tes_machine_types()
    year_features = get_year_features()

    station_power_values = aggregate_station_power_values(pagination["stations"])
    stations_yearly_p_ust = station_power_values['stations']['p_ust']
    stations_yearly_p_ogr = station_power_values['stations']['p_ogr']
    stations_yearly_p_rasp = station_power_values['stations']['p_rasp']

    regional_district_power_values = aggregate_power_by_regional_district(pagination["stations"])
    regional_districts_yearly_p_ust = regional_district_power_values['regional_districts']['p_ust']
    regional_districts_yearly_p_ogr = regional_district_power_values['regional_districts']['p_ogr']
    regional_districts_yearly_p_rasp = regional_district_power_values['regional_districts']['p_rasp']

    regional_districts_yearly_p_ust = {int(k): v for k, v in regional_districts_yearly_p_ust.items()}
    regional_districts_yearly_p_ogr = {int(k): v for k, v in regional_districts_yearly_p_ogr.items()}
    regional_districts_yearly_p_rasp = {int(k): v for k, v in regional_districts_yearly_p_rasp.items()}

    regional_energy_system_power_values = aggregate_power_by_regional_energy_system(pagination["stations"])
    regional_energy_systems_yearly_p_ust = regional_energy_system_power_values['regional_energy_systems']['p_ust']
    regional_energy_systems_yearly_p_ogr = regional_energy_system_power_values['regional_energy_systems']['p_ogr']
    regional_energy_systems_yearly_p_rasp = regional_energy_system_power_values['regional_energy_systems']['p_rasp']

    regional_energy_systems_yearly_p_ust = {int(k): v for k, v in regional_energy_systems_yearly_p_ust.items()}
    regional_energy_systems_yearly_p_ogr = {int(k): v for k, v in regional_energy_systems_yearly_p_ogr.items()}
    regional_energy_systems_yearly_p_rasp = {int(k): v for k, v in regional_energy_systems_yearly_p_rasp.items()}

    return render_template(
        "stations/stations.html",
        form=form,
        stations_grouped=pagination["grouped_stations"],
        total_count=pagination["total_count"],
        total_pages=pagination["total_pages"],
        current_page=pagination["page"],
        per_page=pagination["per_page"],
        start_year=start_year,
        end_year=end_year, 
        energy_system_type_list=energy_system_type_list,
        energy_system_type_names=energy_system_type_names,
        union_energy_system_list=union_energy_system_list,
        union_energy_system_names=union_energy_system_names,
        regional_energy_system_list=regional_energy_system_list,
        regional_energy_system_names=regional_energy_system_names,
        regional_energy_system_mapping=regional_energy_system_mapping,
        federal_district_list=federal_district_list,
        regional_district_list=regional_district_list,
        regional_district_names=regional_district_names,
        regional_district_dict=regional_district_dict,
        regional_district_mapping=regional_district_mapping,
        station_type_list=station_type_list,
        tes_type_list=tes_type_list,
        tes_machine_type_list=tes_machine_type_list,
        condition_type_filter=condition_type_filter,
        gen_company_filter=gen_company_filter,
        station_name_filter=station_name_filter,
        station_type_filter=station_type_filter,
        tes_type_filter=tes_type_filter,
        tes_machine_type_filter=tes_machine_type_filter,
        energy_system_type_filter=energy_system_type_filter,
        union_energy_system_filter=union_energy_system_filter,
        regional_energy_system_filter=regional_energy_system_filter,
        federal_district_filter=federal_district_filter,
        regional_district_filter=regional_district_filter,
        station_fuel_type_filter=station_fuel_type_filter,
        stations_yearly_p_ust=stations_yearly_p_ust,
        stations_yearly_p_ogr=stations_yearly_p_ogr,
        stations_yearly_p_rasp=stations_yearly_p_rasp,
        regional_districts_yearly_p_ust=regional_districts_yearly_p_ust,
        regional_districts_yearly_p_ogr=regional_districts_yearly_p_ogr,
        regional_districts_yearly_p_rasp=regional_districts_yearly_p_rasp,
        regional_energy_systems_yearly_p_ust=regional_energy_systems_yearly_p_ust,
        regional_energy_systems_yearly_p_ogr=regional_energy_systems_yearly_p_ogr,
        regional_energy_systems_yearly_p_rasp=regional_energy_systems_yearly_p_rasp,
        year_features=year_features,
    )
