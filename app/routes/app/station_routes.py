from config import Config
from flask import (
    render_template, request, redirect, url_for, flash, session, current_app, send_file, jsonify
)
from . import app_bp
from app.models.logs_models import Log
from app.forms.station_forms import StationFilterForm
from app.models import Station, Machine, RegionalDistrict, StationGroup, RegionalEnergySystem, ConditionType
from app.services.station_services import (
    get_stations_list, get_union_energy_systems, get_regional_districts, get_energy_system_types, get_regional_districts,
    get_federal_districts, get_regional_energy_systems, get_station_type, get_tes_types, get_tes_machine_types,
    log_to_db, import_station_list_from_excel, export_station_list_to_excel, get_year_features, 
    aggregate_station_power_values, aggregate_power_by_regional_district, get_station_by_id, get_condition_type, 
    get_station_types_list, get_gen_companies_list, aggregate_power_by_regional_energy_system, get_station_groups
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

@app_bp.route("/station_list", methods=["GET", "POST"])
@login_required
@role_required('super-admin')
def station_list():
    """Маршрут для отображения списка электростанций."""
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

    # ✅ Фильтруем машины В КОНТРОЛЛЕРЕ
    if tes_type_filter or tes_machine_type_filter:
        for station in pagination["stations"]:
            station.machines = [
                machine for machine in station.machines
                if (not tes_type_filter or machine.id_tes_type in tes_type_filter) and
                (not tes_machine_type_filter or machine.id_tes_machine_type in tes_machine_type_filter)
            ]

        # ✅ Удаляем станции без машин
        filtered_stations = [station for station in pagination["stations"] if station.machines]

        # ✅ Пересчитываем количество станций В БД с учетом фильтров
        total_count_query = db.session.query(func.count(Station.id)).join(Station.machines)

        if tes_type_filter:
            total_count_query = total_count_query.filter(Machine.id_tes_type.in_(tes_type_filter))

        if tes_machine_type_filter:
            total_count_query = total_count_query.filter(Machine.id_tes_machine_type.in_(tes_machine_type_filter))

        # ✅ Общее число станций в БД (не только на текущей странице)
        total_count = total_count_query.scalar()

        # ✅ Пересчитываем количество страниц
        total_pages = max(1, (total_count + per_page - 1) // per_page) if per_page else 1

        # ✅ Если после фильтрации страница пустая и есть предыдущие страницы — показываем предыдущую
        if not filtered_stations and page > 1:
            return redirect(url_for('your_view_function', page=page - 1, per_page=per_page))

        # ✅ Обновляем данные в pagination
        pagination["stations"] = filtered_stations
        pagination["total_count"] = total_count
        pagination["total_pages"] = total_pages

    if pagination["page"] > pagination["total_pages"]:
        pagination["page"] = pagination["total_pages"]

    print("Общее количество станций:", pagination["total_count"])
    print("Элементов на странице:", len(pagination["stations"]))
    print("Текущая страница:", pagination["page"])
    print("Всего страниц:", pagination["total_pages"])

    # Собираем уникальные компании для каждой станции
    for station in pagination["stations"]:
        get_gen_companies_list(station)

    # Собираем типы энергоблоков для каждой станции
    for station in pagination["stations"]:
        get_station_types_list(station)

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

@app_bp.route("/stations_grouped_values", methods=["GET", "POST"])
@login_required
@role_required('super-admin')
def stations_grouped_values():
    """Маршрут для отображения списка электростанций."""
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
        

    # Получение данных для отображения
    pagination = get_stations_list(
        page=None,
        per_page=None,
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
        regional_district_filter=regional_district_filter
    )

    # Подготовка данных для формы
    energy_system_type_list, energy_system_type_names = get_energy_system_types()

    union_energy_system_list, union_energy_system_names, regional_energy_system_mapping = get_union_energy_systems()
    regional_energy_system_list, regional_energy_system_names = get_regional_energy_systems()
    federal_district_list, regional_district_mapping = get_federal_districts()

    regional_district_list, regional_district_names  = get_regional_districts()
    regional_district_dict = {int(regional_district["id"]): regional_district for regional_district in regional_district_list}

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
        "stations/stations_grouped_values.html",
        form=form,
        stations_grouped=pagination["grouped_stations"],
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

@app_bp.route("/station_details/<int:station_id>", methods=["GET", "POST"])
@login_required
@role_required('super-admin')
def station_details(station_id):
    """Маршрут для отображения сведений об электростанции с логированием изменений."""

    user = session.get('username', 'Неизвестный пользователь')
    station = get_station_by_id(station_id)
    regional_district_name = station.regional_district.name if station and station.regional_district else "не указано"
    log_to_db(user, f"Открыта страница электростанции {station.name} ({regional_district_name})")

    form = StationFilterForm()

    # Получение параметров запроса с дефолтными значениями
    start_year = request.args.get("start_year", 2021, type=int)
    end_year = request.args.get("end_year", 2031, type=int)

    # Получаем данные по станции
    station.gen_companies = get_gen_companies_list(station)
    station.station_type = get_station_types_list(station)
    condition_types = get_condition_type()
    station_groups = get_station_groups()

    station_power_values = aggregate_station_power_values([station])
    stations_yearly_p_ust = station_power_values['stations']['p_ust']
    stations_yearly_p_ogr = station_power_values['stations']['p_ogr']
    stations_yearly_p_rasp = station_power_values['stations']['p_rasp']

    # Загружаем списки данных из сервисов
    regional_districts_list, regional_district_names = get_regional_districts()
    federal_districts, regional_district_mapping = get_federal_districts()
    regional_energy_systems_list, regional_energy_system_names = get_regional_energy_systems()
    union_energy_systems, union_energy_system_names, _ = get_union_energy_systems()
    energy_system_types, energy_system_type_names = get_energy_system_types()

    # Заполняем список субъектов РФ
    form.id_regional_district.choices = [(d["id"], d["name"]) for d in regional_districts_list]
    form.id_condition_type.choices = [(ct.id, ct.name) for ct in condition_types] or [(0, "не указано")]
    form.id_station_group.choices = [(ct.id, ct.name) for ct in station_groups] or [(0, "не указано")]

    if request.method == "GET":
        form.process(obj=station)

    if request.method == "POST":

        if not form.validate():
            print("Ошибки в form:", form.errors)

        if form.validate_on_submit():
            try:
                changes = []
                
                if station.name != form.name.data:
                    changes.append(f"Название: {station.name} → {form.name.data}")
                    station.name = form.name.data
                
                new_condition_type_id = int(form.id_condition_type.data)  # Преобразуем в int
                new_condition_type = db.session.query(ConditionType).filter_by(id=new_condition_type_id).first()
                if new_condition_type:
                    old_value = station.condition_type.name if station.condition_type else "не указано"
                    new_value = new_condition_type.name
                    if old_value != new_value:
                        changes.append(f"Состояние: {old_value} → {new_value}")
                    station.id_condition_type = new_condition_type.id  # Обновляем ID состояния
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
                new_note = form.note.data.strip() if form.note.data.strip() else None
                if station.note != new_note:
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
                    station.location = new_location  # ✅ Записываем None вместо ''

                # Обновляем федеральный округ
                new_regional_district_obj = db.session.query(RegionalDistrict).filter_by(id=form.id_regional_district.data).first()

                if new_regional_district_obj:
                    old_federal_district = station.regional_district.federal_district.name if station.regional_district.federal_district else "не указано"
                    new_federal_district = new_regional_district_obj.federal_district.name if new_regional_district_obj.federal_district else "не указано"
                    if old_federal_district != new_federal_district:
                        changes.append(f"Федеральный округ: {old_federal_district} → {new_federal_district}")
                    station.regional_district = new_regional_district_obj  # ✅ Теперь присваиваем ORM-объект

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

                    station.regional_district.regional_energy_systems = [related_res_obj]  # ✅ Теперь ORM-объект


                # Сохраняем в БД
                db.session.commit()

                if changes:
                    log_to_db(user, f"Изменения в электростанции {station.name} ({regional_district_name})", details="; ".join(changes))

                flash("Изменения в электростанции успешно обновлены!", "success")
                return redirect(url_for("app_bp.station_details", station_id=station.id, **request.args))

            except Exception as e:
                db.session.rollback()
                print(f"❌ Ошибка при обновлении: {str(e)}")
                flash(f"Ошибка при обновлении данных: {str(e)}", "danger")
                log_to_db(user, f"Ошибка обновления электростанции {station.name} ({regional_district_name})", details=str(e))

   
    return render_template(
        "stations/station_details.html",
        form=form,
        station=station,
        start_year=start_year,
        end_year=end_year, 
        stations_yearly_p_ust=stations_yearly_p_ust,
        stations_yearly_p_ogr=stations_yearly_p_ogr,
        stations_yearly_p_rasp=stations_yearly_p_rasp,
        federal_districts=federal_districts,
        regional_districts_list=regional_districts_list,
        regional_energy_systems_list=regional_energy_systems_list,
        union_energy_systems=union_energy_systems,
        energy_system_types=energy_system_types, )


@app_bp.route("/get_energy_system_data/<int:regional_district_id>", methods=["GET"])
def get_energy_system_data(regional_district_id):
    regional_district = db.session.query(RegionalDistrict).filter_by(id=regional_district_id).first()

    if not regional_district:
        return jsonify({"error": "Регион не найден"}), 404

    federal_district = regional_district.federal_district.name if regional_district.federal_district else "Нет данных"

    # Получаем все возможные энергосистемы для данного субъекта РФ
    energy_systems = regional_district.regional_energy_systems

    if not energy_systems:
        return jsonify({"error": "Нет данных по энергосистеме"}), 404

    # Ищем правильную РЭС (если их несколько)
    regional_energy_system = next((res.name for res in energy_systems if res.union_energy_system), energy_systems[0].name)

    # Определяем ОЭС по найденной РЭС
    union_energy_system = next((res.union_energy_system.name for res in energy_systems if res.union_energy_system), "Нет данных")

    # Определяем тип энергосистемы
    energy_system_type = next((res.union_energy_system.energy_system_type.name for res in energy_systems if res.union_energy_system), "Нет данных")

    data = {
        "federal_district": federal_district,
        "regional_energy_system": regional_energy_system,
        "union_energy_system": union_energy_system,
        "energy_system_type": energy_system_type
    }

    return jsonify(data)




from app import db
from flask import request, send_file
from datetime import datetime

@app_bp.route("/import_stations_to_sql", methods=["POST"])
def import_station_list_to_sql_routes():
    """Маршрут для импорта данных электростанций из Excel."""
    
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Начат импорт данных электростанций из Excel")

    if 'file' not in request.files:
        flash("Файл не найден.", "danger")
        return redirect(url_for("app_bp.station_list"))

    file = request.files['file']
    if file.mimetype not in ["application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"]:
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("app_bp.station_list"))

    if not file.filename.endswith((".xlsx", ".xls")):
        flash("Неверный формат файла.", "danger")
        return redirect(url_for("app_bp.station_list"))

    try:
        result = import_station_list_from_excel(file, user)
        flash(result['message'], "success")
    except ValueError as e:
        flash(str(e), "danger")
    except Exception as e:
        current_app.logger.error(f"Ошибка импорта: {e}")
        flash("Ошибка импорта данных.", "danger")

    return redirect(url_for("app_bp.station_list"))


@app_bp.route('/export_stations', methods=['GET'])
def export_station_list():
    """Маршрут для экспорта данных в Excel."""
    user = session.get('username', 'Неизвестный пользователь')
    
    filters = {key: request.args.getlist(key) if key == 'tes_machine_type_filter' else request.args.get(key) 
                    for key in [
                        'condition_type_filter', 'gen_company_filter', 'station_name_filter', 
                        'station_type_filter', 'tes_type_filter', 'tes_machine_type_filter', 
                        'energy_system_type_filter', 'union_energy_system_filter', 
                        'regional_energy_system_filter', 'federal_district_filter', 
                        'regional_district_filter'
                    ]}


    try:
        # Получение данных для экспорта
        excel_data = export_station_list_to_excel(user, filters)
        log_to_db(user, "Экспорт завершён", f"Фильтр: {filters}")

        # Проверка наличия данных
        if excel_data is None or excel_data.getbuffer().nbytes == 0:
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("app_bp.station_list"))
        
        # Формирование имени файла
        filename = f"Приложение А_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        if not excel_data or excel_data.getbuffer().nbytes == 0:
            print("Ошибка: Файл пустой или None")
            flash("Нет данных для экспорта.", "warning")
            return redirect(url_for("app_bp.station_list", **filters))

        # Возврат файла через send_file
        return send_file(
            excel_data,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        current_app.logger.error(f"Ошибка экспорта: {e}")
        print(f"Ошибка экспорта: {e}")
        flash("Ошибка экспорта данных. Пожалуйста, попробуйте снова.", "danger")
        return redirect(url_for("app_bp.station_list", **filters))
    