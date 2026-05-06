"""Маршруты страницы «Электростанции»."""

from config import Config
from app.extensions import db
from flask import (
    render_template, request, redirect, url_for, flash, session, jsonify, current_app, abort
)
from sqlalchemy.orm import joinedload
from collections import defaultdict

from flask_login import login_required, current_user

from app.auth.routes.decorators import roles_required

# Блюпринт
from . import station_bp

# Модели
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.generation.models.station.station_model import Station
from app.common.services.choices_cache_service import choices_cache

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
    add_station_service,
)
from app.generation.services.station_services.export_cache import (
    build_export_key,
    set_export_payload,
)
from app.generation.services.station_services.filters_services import (
    has_any_filters,
    extract_filters_from_args, 
    extract_filters_from_form,
)
from app.common.services.get_services.years.years_get_services import (
    get_filter_start_year,
    get_filter_end_year,
)
from app.common.services.get_services.territories.regional_district_get_services import (
    get_regional_district_list_full,
)
from app.generation.routes.stations.station_details_routes import _render_machines_tbody_cached

# Логирование
from app.logs.services.logging_service import log_to_db

STATION_LIST_FILTERS_SESSION_KEY = "station_list_last_query_args"


def _serialize_request_args_for_session(args):
    """Сохраняет multi-value query args в session."""
    serialized = {}
    for key, values in args.lists():
        if key == "reset_filters":
            continue
        serialized[key] = [value for value in values if value is not None]
    return serialized


def _build_redirect_args_from_multi_dict(args_multi):
    """Преобразует dict[str, list[str]] в kwargs для url_for."""
    redirect_args = {}
    for key, values in args_multi.items():
        if not values:
            continue
        redirect_args[key] = values[0] if len(values) == 1 else values
    return redirect_args


@station_bp.route("/station_list", methods=["GET", "POST"])
@login_required  # Временно отключено для отладки
def station_list():
    """Маршрут для отображения списка всех электростанций."""
    import time

    start_data = time.time()

    user = session.get('username', 'Неизвестный пользователь')
    # log_to_db(user, "Открыта страница электростанций")  # Временно отключено для отладки

    # Создание формы
    form = StationFilterForm()

    if request.method == "POST":
        return redirect(url_for("station_bp.station_list", **extract_filters_from_form(request.form)))

    if request.args.get("reset_filters") == "1":
        session.pop(STATION_LIST_FILTERS_SESSION_KEY, None)
        return redirect(url_for("station_bp.station_list"))

    if not request.args:
        saved_args_multi = session.get(STATION_LIST_FILTERS_SESSION_KEY) or {}
        redirect_args = _build_redirect_args_from_multi_dict(saved_args_multi)
        if redirect_args:
            return redirect(url_for("station_bp.station_list", **redirect_args))
    else:
        session[STATION_LIST_FILTERS_SESSION_KEY] = _serialize_request_args_for_session(request.args)

    # Получение параметров запроса
    filters             = extract_filters_from_args(request.args)
    page                = filters.pop("page", 1)
    start_year          = filters.pop("start_year", get_filter_start_year())
    end_year            = filters.pop("end_year", get_filter_end_year())
    # По умолчанию ограничения мощности (Огр) скрыты, располагаемая мощность отображается
    show_p_ogr          = request.args.get("show_p_ogr", "0") == "1"
    show_p_rasp         = request.args.get("show_p_rasp", "1") == "1"
    # Новый параметр для управления отображением агрегированных сумм (по умолчанию скрыты)
    show_totals         = request.args.get("show_totals", "0") == "1"
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

    print(f"[DEBUG] [STATION_ROUTE] Начало загрузки данных станций")
    print(f"[DEBUG] [STATION_ROUTE] Фильтры: {filters}")
    print(f"[DEBUG] [STATION_ROUTE] per_page: {per_page}, page: {page}")
    
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
                show_totals=show_totals,
    )
    print(f"[DEBUG] [STATION_ROUTE] Получено станций: {len(data.get('stations', []))}")
    print(f"[DEBUG] [STATION_ROUTE] Общее количество: {data.get('total_count', 0)}")
    print(f"[TIME] get_station_list_data заняла: {time.time() - start_data:.2f} сек")

    if (not data.get("stations")) and data.get("total_count", 0) > 0 and page > 1:
        target_page = data.get("total_pages") or 1
        if target_page >= page:
            target_page = max(1, page - 1)
        args_multi = request.args.to_dict(flat=False)
        args_multi["page"] = [str(target_page)]
        redirect_args = _build_redirect_args_from_multi_dict(args_multi)
        return redirect(url_for("station_bp.station_list", **redirect_args))

    # Save ready dataset for export (per user and filters)
    try:
        export_key = build_export_key(
            {**filters},
            rounding_digits,
            start_year,
            end_year,
            show_p_ogr,
            show_p_rasp,
        )
        # We store only the data needed for export to keep memory usage low
        export_payload = {
            "data": data,
            "params": {
                "rounding_digits": rounding_digits,
                "start_year": start_year,
                "end_year": end_year,
                "show_p_ogr": show_p_ogr,
                "show_p_rasp": show_p_rasp,
            },
        }
        set_export_payload(session.get('username') or 'anonymous', export_key, export_payload)
    except Exception as _e:
        current_app.logger.warning(f"[EXPORT_CACHE] Failed to store export payload: {_e}")

    if data["page"] > data["total_pages"]:
        return redirect(url_for("station_bp.station_list", page=data["total_pages"], per_page=per_page))

    context = get_station_list_template_context(
                form,
                data,
                rounding_digits,
                {**filters, "start_year": start_year, "end_year": end_year},
                show_all=show_all,
                hierarchy_data=data.get("hierarchy_data"),
    )

    has_active_filters = has_any_filters(request.args)
    
    overall = time.time() - start_data
    print(f"[TIME] station_list загрузка заняла: {overall:.2f} сек")

    return render_template("generation/stations/stations.html", has_active_filters=has_active_filters, **context)


@station_bp.route('/stations/add', methods=['GET', 'POST'])
@login_required
def add_station():
    edit_roles = ['admin', 'generation-admin', 'generation-editor']
    can_edit = current_user.is_authenticated and any(role in current_user.role_names for role in edit_roles)
    if not can_edit:
        flash("Недостаточно прав для добавления электростанции.", "warning")
        return redirect(url_for("station_bp.station_list"))

    user = session.get('username', 'Неизвестный пользователь')
    log_to_db(user, "Открыта форма создания новой электростанции")

    form = AddStationForm()

    # Подготовка данных для формы с фильтрацией по версии БД
    regional_district_list = get_regional_district_list_full()
    form.id_regional_district.choices = regional_district_list
    
    # Заполняем список типов станций с фильтрацией по версии БД
    from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
    form.id_station_type.choices = choices_cache.get_choices(StationType, StationType.id)

    # Устанавливаем значение по умолчанию на вариант "не указано", если он есть
    if form.id_regional_district.data in (None, ""):
        not_specified_rd_id = next(
            (
                choice[0]
                for choice in regional_district_list
                if isinstance(choice, (list, tuple))
                and len(choice) >= 2
                and isinstance(choice[1], str)
                and choice[1].strip().lower() == "не указано"
            ),
            None,
        )
        if not_specified_rd_id is not None:
            form.id_regional_district.data = not_specified_rd_id

    if form.validate_on_submit():
        force_create = request.form.get("confirm_duplicate") in ("1", "true", "True")
        try:
            new_station = add_station_service(
                user=user,
                name=form.name.data,
                id_regional_district=form.id_regional_district.data,
                id_station_type=form.id_station_type.data,
                force_create=force_create,
            )
            flash("Новая станция успешно создана!", "success")
            return redirect(url_for("station_bp.station_details", station_id=new_station.id))
        except ValueError as e:
            if str(e) == "STATION_DUPLICATE":
                return render_template(
                    "generation/stations/station_add.html",
                    form=form,
                    show_duplicate_confirm=True,
                )
            flash(str(e), "danger")
        except Exception as e:
            flash(f"Ошибка при создании станции: {str(e)}", "danger")

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


@station_bp.route('/clear_cache', methods=['POST'])
@login_required
@roles_required(["admin"])
def clear_station_cache():
    """Очищает кэш станций."""
    try:
        from app.generation.services.station_services.aggregation_cache import clear_aggregation_cache
        
        # Очищаем кэш агрегаций и отсортированных списков станций
        clear_aggregation_cache()
        _render_machines_tbody_cached.cache_clear()
        
        flash('Кэш станций успешно очищен', 'success')
        current_app.logger.info("Кэш станций очищен пользователем")
        
        return jsonify({
            'success': True,
            'message': 'Кэш станций успешно очищен'
        })
        
    except Exception as e:
        current_app.logger.error(f"Ошибка при очистке кэша станций: {str(e)}")
        flash('Ошибка при очистке кэша', 'error')
        
        return jsonify({
            'success': False,
            'message': 'Ошибка при очистке кэша'
        }), 500


@station_bp.route('/refresh_cache', methods=['POST'])
@login_required
@roles_required(["admin"])
def refresh_station_cache():
    """Принудительно обновляет кэш станций."""
    try:
        from app.generation.services.station_services.aggregation_cache import warmup_station_cache
        
        # Принудительно обновляем кэш
        warmup_station_cache(force=True)
        
        flash('Кэш станций успешно обновлен', 'success')
        current_app.logger.info("Кэш станций принудительно обновлен пользователем")
        
        return jsonify({
            'success': True,
            'message': 'Кэш станций успешно обновлен'
        })
        
    except Exception as e:
        current_app.logger.error(f"Ошибка при обновлении кэша станций: {str(e)}")
        flash('Ошибка при обновлении кэша', 'error')
        
        return jsonify({
            'success': False,
            'message': 'Ошибка при обновлении кэша'
        }), 500


@station_bp.route('/clear_refdata_cache', methods=['POST'])
@login_required
@roles_required(["admin"])
def clear_refdata_cache():
    """Очищает кэш справочников (choices_cache)."""
    try:
        choices_cache.clear_cache()
        _render_machines_tbody_cached.cache_clear()
        current_app.logger.info("Кэш справочников очищен администратором")
        return jsonify({
            'success': True,
            'message': 'Кэш справочников очищен',
        })
    except Exception as exc:
        current_app.logger.error(f"Ошибка при очистке кэша справочников: {exc}")
        return jsonify({
            'success': False,
            'message': 'Ошибка при очистке кэша справочников'
        }), 500