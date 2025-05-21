from . import station_bp
from config import Config
from app import db
from app.services.logging_services.logging_service import log_to_db
from flask_login import login_required
from app.routes.auth import role_required
from flask import (
    render_template, request, redirect, url_for, session, jsonify
)
from collections import defaultdict
from app.forms.station_forms import StationFilterForm
from app.models import (
    RegionalDistrict, 
)
from app.services.station_services.station_services import (
    get_stations_list,
    extract_filters_from_form, 
    extract_filters_from_args, 
    assign_machine_powers_by_year, 
    get_station_list_template_context, 
    recalculate_station_powers_by_filtered_machines,
    get_station_list_data
)
from app.services.station_services.filters_service import (
    filter_machines,
    has_any_filters,
)
from app.services.station_services.groupped_service import (
    group_stations_hierarchy, 
    group_machines_by_group_and_fuel, 
)

@station_bp.route("/station_list", methods=["GET", "POST"])
@login_required
@role_required('super-admin')
def station_list():
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница электростанций")

    form = StationFilterForm()

    if request.method == "POST":
        return redirect(url_for("station_bp.station_list", **extract_filters_from_form(request.form)))

    per_page_param = request.args.get("per_page", "10")
    show_all = per_page_param.lower() == "all"

    if show_all:
        per_page = None
    else:
        try:
            per_page = int(per_page_param)
        except ValueError:
            per_page = 10

    filters = extract_filters_from_args(request.args)
    page = filters.pop("page", 1)
    start_year = filters.pop("start_year", Config.START_YEAR)
    end_year = filters.pop("end_year", Config.END_YEAR)
    show_p_ogr = request.args.get("show_p_ogr") == "1"
    show_p_rasp = request.args.get("show_p_rasp") == "1"

    try:
        rounding_digits = int(request.args.get('rounding_digits'))
    except (ValueError, TypeError):
        rounding_digits = 1

    if rounding_digits is None or rounding_digits < 0:
        rounding_digits = 1

    data = get_station_list_data(
        filters=filters,
        per_page=per_page,
        page=page,
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        show_p_ogr=show_p_ogr,
        show_p_rasp=show_p_rasp,
    )

    if data["page"] > data["total_pages"]:
        return redirect(url_for("station_bp.station_list", page=data["total_pages"], per_page=per_page))

    context = get_station_list_template_context(
        form,
        data,
        rounding_digits,
        {**filters, "start_year": start_year, "end_year": end_year}
    )

    context.update({
        "stations_by_energy_unit": data["stations_by_energy_unit"],
        "aggregated_by_energy_unit": data["aggregated_by_energy_unit"],
        "aggregated_by_regional_energy_system": data["aggregated_by_regional_energy_system"],
        "aggregated_by_union_energy_system": data["aggregated_by_union_energy_system"],
        "aggregated_by_energy_system_type": data["aggregated_by_energy_system_type"],
        "rounding_digits": rounding_digits,
        "per_page": per_page,
    })

    has_active_filters = has_any_filters(request.args)

    return render_template("stations/stations.html", has_active_filters=has_active_filters, **context)


def station_list_old():
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница электростанций")

    form = StationFilterForm()

    if request.method == "POST":
        return redirect(url_for("station_bp.station_list", **extract_filters_from_form(request.form)))

    per_page_param = request.args.get("per_page", "10")
    show_all = per_page_param.lower() == "all"

    if show_all:
        per_page = None
    else:
        try:
            per_page = int(per_page_param)
        except ValueError:
            per_page = 10
    
    # --- Получаем фильтры ---
    filters = extract_filters_from_args(request.args)
    page = filters.pop("page", 1)
    start_year = filters.pop("start_year", Config.START_YEAR)
    end_year = filters.pop("end_year", Config.END_YEAR)
    rounding_digits_raw = request.args.get('rounding_digits', '1')
    show_p_ogr = request.args.get("show_p_ogr") == "1"
    show_p_rasp = request.args.get("show_p_rasp") == "1"
        
    try:
        rounding_digits = int(rounding_digits_raw)
    except (ValueError, TypeError):
        rounding_digits = 1

    # Специальная логика: если выбрано "Не округлять" (0), то оставляем None
    if rounding_digits == 0:
        rounding_digits = None

    # Загружаем все станции без пагинации
    all_data = get_stations_list(
        page=1,
        rounding_digits=rounding_digits,
        **filters
    )

    # Фильтрация агрегатов до пагинации
    filtered_stations = filter_machines(
        all_data["stations"],
        filters.get("tes_type_filter", []),
        filters.get("tes_machine_type_filter", []),
        filters.get("date_exploitation_filter", []),
        filters.get("date_decompressing_expected_filter", []),
        filters.get("date_modernization_expected_filter", []),
    )

    # Теперь — ручная пагинация
    total_count = len(filtered_stations)
    if show_all:
        paginated_stations = filtered_stations
        total_pages = 1
    else:
        total_pages = max(1, (total_count + per_page - 1) // per_page)
        paginated_stations = filtered_stations[(page - 1) * per_page : page * per_page]


    pagination = {
        "stations": paginated_stations,
        "total_count": total_count,
        "total_pages": total_pages,
        "page": page,
        "per_page": per_page,
    }

    # --- Подготовка агрегатов ---
    for station in pagination["stations"]:
        station.machines = group_machines_by_group_and_fuel([station])[0].machines

    # --- Загружаем мощности агрегатов ---
    all_machines = []
    for station in pagination["stations"]:
        all_machines.extend(station.machines)

    recalculate_station_powers_by_filtered_machines(pagination["stations"], start_year, end_year, rounding_digits)

    for machine in all_machines:
        assign_machine_powers_by_year(machine, start_year, end_year, rounding_digits)

    # --- Группируем станции ---
    grouped_result = group_stations_hierarchy(paginated_stations, include_names=True)

    pagination.update({
        "grouped_stations": grouped_result["grouped_stations"],
        "aggregated_by_energy_unit": grouped_result["aggregated_by_energy_unit"],
        "aggregated_by_regional_district": grouped_result["aggregated_by_regional_district"],
        "aggregated_by_regional_energy_system": grouped_result["aggregated_by_regional_energy_system"],
        "aggregated_by_union_energy_system": grouped_result["aggregated_by_union_energy_system"],
        "aggregated_by_energy_system_type": grouped_result["aggregated_by_energy_system_type"],
        "aggregated_total": grouped_result["aggregated_total"],
    })

    # --- Проверка: если страница вышла за предел ---
    if pagination["page"] > pagination["total_pages"]:
        return redirect(url_for("station_bp.station_list", page=pagination["total_pages"], per_page=per_page))

    # --- Формируем контекст для шаблона ---
    context = get_station_list_template_context(
        form,
        pagination,
        rounding_digits,
        {**filters, "start_year": start_year, "end_year": end_year}
    )

    # --- Для удобного доступа к станциям по энергоузлам ---
    stations_by_energy_unit = defaultdict(list)
    for station in pagination["stations"]:
        stations_by_energy_unit[station.id_energy_unit].append(station)

    context.update({
        "stations_by_energy_unit": stations_by_energy_unit,
        "aggregated_by_energy_unit": grouped_result["aggregated_by_energy_unit"],
        "aggregated_by_regional_energy_system": grouped_result["aggregated_by_regional_energy_system"],
        "aggregated_by_union_energy_system": grouped_result["aggregated_by_union_energy_system"],
        "aggregated_by_energy_system_type": grouped_result["aggregated_by_energy_system_type"],
        "rounding_digits": rounding_digits,
        "per_page": per_page,
    })

    return render_template("stations/stations.html", **context)


@station_bp.route("/get_energy_system_data/<int:regional_district_id>", methods=["GET"])
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
