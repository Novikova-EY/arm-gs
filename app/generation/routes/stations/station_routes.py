from . import station_bp
from config import Config
from app.extensions import db
from app.logs.services.logging_service import log_to_db
from flask_login import login_required
from app.auth.routes import roles_required
from flask import (
    render_template, request, redirect, url_for, session, jsonify, session  
)
from collections import defaultdict
from app.generation.forms.station_forms import(
    StationFilterForm, 
    AddStationForm
)
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.generation.models.station.station_model import Station
from app.generation.services.station_services.station_services import (
    get_stations_list,
    assign_machine_powers_by_year, 
    get_station_list_template_context, 
    recalculate_station_powers_by_filtered_machines,
    get_station_list_data,
)
from app.generation.services.station_services.filters_services import (
    has_any_filters,
    extract_filters_from_args, 
    extract_filters_from_form,
)
from . import station_bp
from app.extensions import db
from config import Config
from decimal import Decimal
from flask import (
    render_template, request, redirect, url_for, flash, session, current_app, send_file, jsonify
)
from flask import session
from app.generation.forms.machine_forms import MachineFilterSmallForm
from app.generation.services.station_services.help_services import (
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
from app.generation.services.station_services.station_services import (
    get_stations_list,
    get_station_by_id, 
    assign_machine_powers_by_year, 
    get_station_list_template_context, 
    recalculate_station_power,
    get_current_machine_tes_types_map, 
    recalculate_station_powers_by_filtered_machines
)
from app.generation.services.station_services.import_station_services import (
    import_station_list_from_excel, 
    import_fuel_tes_station_from_excel, 
)


@station_bp.route("/station_list", methods=["GET", "POST"])
@login_required
def station_list():
    import time

    start_data = time.time()

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница электростанций")

    form = StationFilterForm()

    if request.method == "POST":
        return redirect(url_for("station_bp.station_list", **extract_filters_from_form(request.form)))

    per_page_param = request.args.get("per_page", "10")
    show_all = per_page_param.lower() == "all"

    if show_all:
        per_page = "all"
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
    show_p_rasp = request.args.get("show_p_rasp", "1") == "1"

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
        show_all=show_all,
    )
    print(f"⏱ get_station_list_data заняла: {time.time() - start_data:.2f} сек")

    if data["page"] > data["total_pages"]:
        return redirect(url_for("station_bp.station_list", page=data["total_pages"], per_page=per_page))

    context = get_station_list_template_context(
        form,
        data,
        rounding_digits,
        {**filters, "start_year": start_year, "end_year": end_year},
        show_all=show_all,
    )

    has_active_filters = has_any_filters(request.args)
    
    overall = time.time() - start_data
    print(f"⏱⏱ station_list загрузка заняла: {overall:.2f} сек")

    return render_template("stations/stations.html", has_active_filters=has_active_filters, **context)


@station_bp.route('/stations/add', methods=['GET', 'POST'])
@login_required
def add_station():
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта форма создания новой электростанции")

    form = AddStationForm()

    # Получение справочников
    regional_districts_list, _ = get_regional_districts()
    form.id_regional_district.choices = [(d["id"], d["name"]) for d in regional_districts_list]

    if form.validate_on_submit():
        try:
            new_station = Station(
                name=form.name.data,
                id_regional_district=form.id_regional_district.data
            )
            db.session.add(new_station)
            db.session.commit()

            flash("Новая станция успешно создана!", "success")
            log_to_db(user, f"Создана новая станция: {new_station.name}")

            return redirect(url_for("station_bp.station_details", station_id=new_station.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при создании станции: {str(e)}", "danger")
            log_to_db(user, "Ошибка создания новой станции", details=str(e))

    return render_template("stations/station_add.html", form=form)


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
