from flask import (
    render_template, request, redirect, url_for, flash, session, current_app, send_file
)
from . import app_bp
from app.models.logs_models import Log
from app.models.energy_systems_models import RegionalEnergySystem
from app.models import Station, Machine, MachinePower, Year
from app.forms.station_forms import StationFilterForm
from app.services.station_services import (
    get_stations_list, get_union_energy_systems, get_regional_districts, get_energy_system_types, get_regional_districts,
    get_federal_districts, get_regional_energy_systems, get_station_type, get_tes_types, get_tes_machine_types,
    log_to_db, get_total_with_filter, import_station_list_from_excel, export_station_list_to_excel
)
from flask_login import login_required
from app.routes.auth import role_required

def log_to_db(username, action, details=None):
    """Записывает лог действия пользователя в базу данных."""
    try:
        log_entry = Log(username=username, action=action, details=details)
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка записи лога: {e}")


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
    per_page = request.args.get("per_page", 10, type=int)
    condition_type_filter = request.args.get("condition_type_filter", "")
    station_name_filter = request.args.get("station_name_filter", "").strip()
    start_year = request.args.get("start_year", type=int)
    end_year = request.args.get("end_year", type=int)
    station_type_filter = request.args.get("station_type_filter", "")
    tes_type_filter = request.args.get("tes_type_filter", "")
    tes_machine_type_filter = request.args.get("tes_type_filter", "")
    energy_system_type_filter = request.args.get("energy_system_type_filter", "")
    union_energy_system_filter = request.args.get("union_energy_system_filter", "")
    regional_energy_system_filter = request.args.get("regional_energy_system_filter", "")
    federal_district_filter = request.args.get("federal_district_filter", "")
    regional_district_filter = request.args.get("regional_district_filter", "")
    gen_company_filter = request.args.get("gen_company_filter", "").strip()
    station_type_filter = request.args.get("station_type_filter", "").strip()
    tes_type_filter = request.args.get("tes_type_filter", "").strip()
    tes_machine_type_filter = request.args.getlist('tes_machine_type_filter', type=int)
    station_fuel_type_filter = request.args.get("station_fuel_type_filter", "")
    
    # Проверка на пустое значение для start_year и end_year
    if start_year is None:
        start_year = 2021  # Значение по умолчанию
    if end_year is None:
        end_year = 2032  # Значение по умолчанию
        
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")

    if request.method == "POST":
    
        # Обновление параметров из формы
        page = request.form.get("page", 1, type=int)
        per_page = request.form.get("per_page", 10, type=int)
        sort_by = request.form.get("sort_by", "id")
        sort_dir = request.form.get("sort_dir", "asc")

        condition_type_filter = request.form.get("condition_type_filter", "")
        station_name_filter = request.args.get("station_name_filter", "").strip()
        station_type_filter = request.form.get("station_type_filter", "")
        tes_type_filter = request.form.get("tes_type_filter", "")
        tes_machine_type_filter = request.form.get("tes_type_filter", "")
        regional_energy_system_filter = request.form.get("regional_energy_system_filter", "")
        federal_energy_system_filter = request.form.get("federal_energy_system_filter", "")
        energy_system_type_filter = request.form.get("energy_system_type_filter", "")
        union_energy_system_filter = request.form.get("union_energy_system_filter", "")
        gen_company_filter = request.form.get("gen_company_filter", "").strip()
        station_type_filter = request.form.get("station_type_filter", "")
        tes_type_filter = request.form.get("tes_type_filter", "")
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
                                station_name_filter = station_name_filter,
                                regional_energy_system_filter = regional_energy_system_filter,
                                federal_energy_system_filter = federal_energy_system_filter,
                                energy_system_type_filter = energy_system_type_filter,
                                union_energy_system_filter = union_energy_system_filter,
                                gen_company_filter = gen_company_filter,
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
                                regional_district_filter,
                                sort_by, 
                                sort_dir)
    
    # Собираем уникальные компании для каждой станции
    for station in pagination.items:
        gen_companies = {machine.gen_company.name for machine in station.machines if machine.gen_company}
        station.gen_companies = ", ".join(gen_companies)

    # Собираем типы энергоблоков для каждой станции
    for station in pagination.items:
        station_type = {machine.station_type.name for machine in station.machines if machine.station_type}
        station.station_type = ", ".join(station_type)

    # Вычисление сумм для p_ust и p_rasp
    stations_yearly_p_ust = {}
    stations_yearly_p_ogr = {}
    stations_yearly_p_rasp = {}

    from decimal import Decimal

    stations_yearly_p_ust = {}
    stations_yearly_p_ogr = {}
    stations_yearly_p_rasp = {}

    for station in pagination.items:
        yearly_p_ust_station = {}
        yearly_p_ogr_station = {}
        yearly_p_rasp_station = {}

        for machine in station.machines:
            for machine_power in machine.machine_powers:
                year = machine_power.year.number

                p_ust = Decimal(str(machine_power.p_ust)) if machine_power.p_ust else Decimal(0)
                p_ogr = Decimal(str(machine_power.p_ogr)) if machine_power.p_ogr else Decimal(0)
                p_rasp = Decimal(str(machine_power.p_rasp)) if machine_power.p_rasp else Decimal(0)

                if year in yearly_p_ust_station:
                    yearly_p_ust_station[year] += p_ust
                    yearly_p_ogr_station[year] += p_ogr
                    yearly_p_rasp_station[year] += p_rasp
                else:
                    yearly_p_ust_station[year] = p_ust
                    yearly_p_ogr_station[year] = p_ogr
                    yearly_p_rasp_station[year] = p_rasp

        # Сохраняем суммы без округления
        stations_yearly_p_ust[station.id] = yearly_p_ust_station
        stations_yearly_p_ogr[station.id] = yearly_p_ogr_station
        stations_yearly_p_rasp[station.id] = yearly_p_rasp_station

   
    # Подготовка данных для формы
    energy_system_type_list = get_energy_system_types()
    
    union_energy_system_list, regional_energy_system_mapping = get_union_energy_systems()
    regional_energy_system_list = get_regional_energy_systems()

    federal_district_list, regional_district_mapping = get_federal_districts()
    regional_district_list = get_regional_districts()
    station_type_list = get_station_type()
    tes_type_list = get_tes_types()
    tes_machine_type_list = get_tes_machine_types()


    if tes_machine_type_filter:
        filtered_stations = []

        for station in pagination.items:
            # Отбираем только те машины, у которых тип есть в списке фильтра
            filtered_machines = [m for m in station.machines if m.id_tes_machine_type in tes_machine_type_filter]

            if filtered_machines:
                station.machines = filtered_machines
                filtered_stations.append(station)

        pagination.items = filtered_stations
        pagination.total = len(filtered_stations)

    return render_template(
        "stations/stations.html",
        form=form,
        station_list=pagination.items,
        pagination=pagination,
        start_year=start_year,
        end_year=end_year, 
        energy_system_type_list=energy_system_type_list,
        union_energy_system_list=union_energy_system_list,
        regional_energy_system_list=regional_energy_system_list,
        regional_energy_system_mapping=regional_energy_system_mapping,
        federal_district_list=federal_district_list,
        regional_district_list=regional_district_list,
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
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )

@app_bp.route("/station_details/<int:station_id>", methods=["GET", "POST"])
def station_details(station_id):
    """Маршрут для отображения сведений об электростанции."""
    
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, f"Открыта страница электростанции ID {station_id}")

    form = StationFilterForm()

    # Получение параметров запроса с дефолтными значениями
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 10, type=int)
    start_year = request.args.get("start_year", 2021, type=int)
    end_year = request.args.get("end_year", 2031, type=int)
    sort_by = request.args.get("sort_by", "id")
    sort_dir = request.args.get("sort_dir", "asc")


    # Если запрос `POST`, обновляем фильтры
    if request.method == "POST":
        # Обновляем параметры пагинации
        page = request.form.get("page", 1, type=int)
        per_page = request.form.get("per_page", 10, type=int)
        sort_by = request.form.get("sort_by", "id")
        sort_dir = request.form.get("sort_dir", "asc")

        return redirect(url_for("app_bp.station_details", 
                                station_id=station_id, 
                                page=page, 
                                per_page=per_page, 
                                start_year=start_year,
                                end_year=end_year, 
                                sort_by=sort_by, 
                                sort_dir=sort_dir))


    # Получаем данные по станции
    station = Station.query.get_or_404(station_id)
    # Собираем уникальные компании для каждой станции
    gen_companies = {machine.gen_company.name for machine in station.machines if machine.gen_company}
    station.gen_companies = ", ".join(gen_companies)

    # Собираем типы энергоблоков для каждой станции
    station_type = {machine.station_type.name for machine in station.machines if machine.station_type}
    station.station_type = ", ".join(station_type)

    # Получение данных для отображения
    pagination = get_stations_list(page, 
                                per_page,
                                start_year,
                                end_year, 
                                sort_by, 
                                sort_dir)


    # Вычисление сумм для p_ust и p_rasp
    stations_yearly_p_ust = {}
    stations_yearly_p_rasp = {}

    # Для каждой станции создаем отдельные словари
    yearly_p_ust_station = {}
    yearly_p_rasp_station = {}
    
    # Обрабатываем машины станции
    for machine in station.machines:
        for machine_power in machine.machine_powers:
            year = machine_power.year.number
            # Суммируем p_ust и p_rasp для каждого года
            if year in yearly_p_ust_station:
                yearly_p_ust_station[year] += machine_power.p_ust if machine_power.p_ust else 0
                yearly_p_rasp_station[year] += machine_power.p_rasp if machine_power.p_rasp else 0
            else:
                yearly_p_ust_station[year] = machine_power.p_ust if machine_power.p_ust else 0
                yearly_p_rasp_station[year] = machine_power.p_rasp if machine_power.p_rasp else 0
    
    # Сохраняем результаты для этой станции в общий словарь
    stations_yearly_p_ust = yearly_p_ust_station
    stations_yearly_p_rasp = yearly_p_rasp_station
    

    return render_template(
        "stations/station_details.html",
        form=form,
        station=station,
        pagination=pagination,
        stations_yearly_p_ust=stations_yearly_p_ust,
        stations_yearly_p_rasp=stations_yearly_p_rasp,
        start_year=start_year,
        end_year=end_year, 
        sort_by=sort_by,
        sort_dir=sort_dir,
        per_page=per_page
    )


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
                        'regional_district_filter', 'sort_by', 'sort_dir'
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
    