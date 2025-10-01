"""Маршруты страницы «Электростанции Российской Федерации»."""

from config import Config
from app.extensions import db
from flask import (
    render_template, request, redirect, url_for, flash, session, jsonify, current_app
)
from collections import defaultdict

from flask_login import login_required 

# Блюпринт
from . import station_bp

# Модели
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.generation.models.station.station_model import Station
from sqlalchemy.orm import joinedload

# Формы
from app.generation.forms.station_forms import(
    StationFilterForm, 
    AddStationForm
)

# Сервисы
from app.generation.services.station_services.station_services import (
    get_station_list_template_context, 
    get_station_list_template_context, 
    get_station_list_data,
)
from app.generation.services.station_services.filters_services import (
    has_any_filters,
    extract_filters_from_args, 
    extract_filters_from_form,
)
from app.common.services.get_services.territories.regional_district_get_services import (
    get_regional_district_list_full,
)

# Логирование
from app.logs.services.logging_service import log_to_db


@station_bp.route("/station_list", methods=["GET", "POST"])
@login_required
def station_list():
    """Маршрут для отображения списка всех электростанций."""
    import time

    start_data = time.time()

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта страница электростанций")

    # Создание формы
    form = StationFilterForm()

    if request.method == "POST":
        return redirect(url_for("station_bp.station_list", **extract_filters_from_form(request.form)))

    # Получение параметров запроса
    filters             = extract_filters_from_args(request.args)
    page                = filters.pop("page", 1)
    start_year          = filters.pop("start_year", Config.START_YEAR)
    end_year            = filters.pop("end_year", Config.END_YEAR)
    # По умолчанию ограничения мощности (Огр) скрыты, располагаемая мощность отображается
    show_p_ogr          = request.args.get("show_p_ogr", "0") == "1"
    show_p_rasp         = request.args.get("show_p_rasp", "1") == "1"
    per_page_param      = request.args.get("per_page", "10")

    show_all = per_page_param.lower() == "all"
    if show_all:
        per_page = "all"
    else:
        try:
            per_page = int(per_page_param)
        except ValueError:
            per_page = 10

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

    return render_template("generation/stations/stations.html", has_active_filters=has_active_filters, **context)


@station_bp.route('/stations/add', methods=['GET', 'POST'])
@login_required
def add_station():
    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта форма создания новой электростанции")

    form = AddStationForm()

    # Подготовка данных для формы
    regional_district_list = get_regional_district_list_full()
    form.id_regional_district.choices = [(rd.id, rd.name) for rd in regional_district_list]

    if form.validate_on_submit():
        try:
            new_station = Station(
                name=form.name.data,
                id_regional_district=form.id_regional_district.data
            )
            db.session.add(new_station)
            db.session.commit()

            flash("Новая станция успешно создана!", "success")
            log_to_db(user, f"Создана новая станция: {new_station.name}", entity_type="station", entity_id=new_station.id)

            return redirect(url_for("station_bp.station_details", station_id=new_station.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при создании станции: {str(e)}", "danger")
            log_to_db(user, "Ошибка создания новой станции", details=str(e))

    return render_template("generation/stations/station_add.html", form=form)


@station_bp.route("/get_energy_system_data/<int:regional_district_id>", methods=["GET"])
def get_energy_system_data(regional_district_id):
    """API endpoint для получения данных энергосистемы по субъекту РФ."""
    try:
        # Загружаем субъект РФ с предзагрузкой связанных данных
        regional_district = (
            db.session.query(RegionalDistrict)
            .options(
                joinedload(RegionalDistrict.federal_district),
                joinedload(RegionalDistrict.regional_energy_systems)
                    .joinedload(RegionalEnergySystem.union_energy_system)
                    .joinedload(UnionEnergySystem.energy_system_type)
            )
            .filter_by(id=regional_district_id)
            .first()
        )

        if not regional_district:
            return jsonify({"error": "Субъект РФ не найден"}), 404

        # Получаем федеральный округ
        federal_district = regional_district.federal_district.name if regional_district.federal_district else "Нет данных"

        # Получаем все возможные энергосистемы для данного субъекта РФ
        energy_systems = regional_district.regional_energy_systems

        if not energy_systems:
            return jsonify({
                "federal_district": federal_district,
                "regional_energy_system": "Нет данных",
                "union_energy_system": "Нет данных", 
                "energy_system_type": "Нет данных"
            })

        # Ищем основную РЭС (приоритет у той, что имеет ОЭС)
        main_res = None
        for res in energy_systems:
            if res.union_energy_system:
                main_res = res
                break
        
        if not main_res:
            main_res = energy_systems[0]

        # Определяем данные энергосистемы
        regional_energy_system = main_res.name if main_res else "Нет данных"
        union_energy_system = main_res.union_energy_system.name if main_res and main_res.union_energy_system else "Нет данных"
        energy_system_type = (
            main_res.union_energy_system.energy_system_type.name 
            if main_res and main_res.union_energy_system and main_res.union_energy_system.energy_system_type 
            else "Нет данных"
        )

        data = {
            "federal_district": federal_district,
            "regional_energy_system": regional_energy_system,
            "union_energy_system": union_energy_system,
            "energy_system_type": energy_system_type
        }

        return jsonify(data)

    except Exception as e:
        current_app.logger.error(f"Ошибка при получении данных энергосистемы для субъекта {regional_district_id}: {str(e)}")
        return jsonify({"error": "Внутренняя ошибка сервера"}), 500