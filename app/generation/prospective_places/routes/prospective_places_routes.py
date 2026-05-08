# -*- coding: utf-8 -*-
"""Маршруты для перспективных площадок размещения электростанций."""
from . import prospective_places_bp
from flask import render_template, send_file, request, redirect, url_for, flash, g
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from io import BytesIO
from datetime import datetime
from functools import wraps

from app.extensions import db
from app.logs.services.logging_service import log_to_db
from app.generation.prospective_places.services.aes.machine_prospective_place_aes_sort import (
    sort_machines_by_station_block_number,
)


def _log_prospective_aes_tep_page_view(action_title: str) -> None:
    log_to_db(
        current_user,
        action_title,
        details=f"url={request.full_path}",
        entity_type="prospective_place_aes",
    )


def _aes_tep_price_coeff_can_edit() -> bool:
    if not current_user.is_authenticated:
        return False
    edit_roles = ("admin", "generation-admin", "generation-editor")
    return any(role in current_user.role_names for role in edit_roles)


def no_compress(f):
    """Декоратор для отключения сжатия Flask-Compress для маршрута экспорта."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        g.no_compress = True
        return f(*args, **kwargs)
    return decorated_function


def _prospective_place_can_edit() -> bool:
    if not current_user.is_authenticated:
        return False
    edit_roles = ("admin", "generation-admin", "generation-editor")
    return any(role in current_user.role_names for role in edit_roles)


def _station_choice_label(station) -> str:
    return ((getattr(station, "name", None) or "").strip() or "—")


def _version_id_for_station_link(place) -> int | None:
    """Версия БД для списка станций и валидации связи.

    У перспективной площадки database_version_id часто NULL: тогда показываем
    электростанции текущей активной версии (как на остальных экранах), а не
    только записи с NULL (их обычно нет).
    """
    from app.common.services.database_version_filter import get_current_db_version_id

    vid = getattr(place, "database_version_id", None)
    if vid is not None:
        return vid
    return get_current_db_version_id()


def _get_station_link_context(place) -> dict:
    from app.common.services.database_version_filter import filter_by_explicit_db_version
    from app.generation.models.station.station_model import Station

    version_id = _version_id_for_station_link(place)
    stations = list(
        filter_by_explicit_db_version(
            Station.query.options(joinedload(Station.regional_district)),
            Station,
            version_id,
        )
        .order_by(Station.name, Station.id)
        .all()
    )

    linked_station = None
    place_external_code = (getattr(place, "external_code", None) or "").strip()
    if place_external_code:
        linked_station = next(
            (
                station
                for station in stations
                if ((getattr(station, "external_code", None) or "").strip() == place_external_code)
            ),
            None,
        )
        if linked_station is None:
            linked_station = (
                filter_by_explicit_db_version(
                    Station.query.options(joinedload(Station.regional_district)),
                    Station,
                    version_id,
                )
                .filter(Station.external_code == place_external_code)
                .first()
            )
            if linked_station and all(st.id != linked_station.id for st in stations):
                stations.append(linked_station)
                stations.sort(
                    key=lambda st: (((st.name or "").strip()).lower(), st.id)
                )

    return {
        "station_link_choices": [
            ("", "не указано"),
            *[(str(st.id), _station_choice_label(st)) for st in stations],
        ],
        "linked_station_id": str(linked_station.id) if linked_station else "",
        "linked_station_display": (
            _station_choice_label(linked_station) if linked_station else "не указано"
        ),
    }


def _assign_prospective_place_station(place, station_id: int | None):
    from app.common.services.database_version_filter import filter_by_explicit_db_version
    from app.generation.models.station.station_model import Station

    if station_id is None:
        place.external_code = None
        return None

    station = (
        filter_by_explicit_db_version(
            Station.query,
            Station,
            _version_id_for_station_link(place),
        )
        .filter(Station.id == station_id)
        .first()
    )
    if not station:
        raise LookupError("Выбранная электростанция не найдена для соответствующей версии БД.")

    station_external_code = (getattr(station, "external_code", None) or "").strip()
    if not station_external_code:
        raise ValueError("У выбранной электростанции отсутствует external_code, связь невозможна.")

    place.external_code = station_external_code
    return station


def _navigation_redirect_to_station(place, *, back_endpoint: str, back_id: int):
    """GET с параметром station_id: открыть карточку электростанции в версии БД площадки."""
    from app.common.middleware.database_version_middleware import set_session_version
    from app.common.services.database_version_filter import filter_by_explicit_db_version
    from app.generation.models.station.station_model import Station

    station_id_raw = (request.args.get("station_id") or "").strip()
    try:
        station_id = int(station_id_raw) if station_id_raw else None
    except ValueError:
        station_id = None

    def _back():
        return redirect(url_for(back_endpoint, id=back_id))

    if station_id is None:
        flash("Выберите электростанцию или укажите связь перед переходом.", "warning")
        return _back()

    station = (
        filter_by_explicit_db_version(
            Station.query,
            Station,
            _version_id_for_station_link(place),
        )
        .filter(Station.id == station_id)
        .first()
    )
    if not station:
        flash("Электростанция не найдена для версии БД этой площадки.", "danger")
        return _back()

    effective_version_id = _version_id_for_station_link(place)
    if effective_version_id is not None:
        set_session_version(effective_version_id)

    return redirect(url_for("station_bp.station_details", station_id=station.id))


def _load_prospective_places_aes_stations_and_filters():
    """Станции и контекст фильтров по request.args (список и страницы ТЭП)."""
    from app.generation.prospective_places.models import StationProspectivePlaceAES, MachineProspectivePlaceAES
    from app.refdata.models.energy_systems.regional_energy_system_model import (
        RegionalEnergySystem,
    )
    from app.generation.prospective_places.services.aes.prospective_places_filters_services import (
        extract_prospective_places_filters,
        apply_prospective_places_filters,
        get_prospective_places_filter_context,
        apply_prospective_places_aes_station_order,
    )

    filters = extract_prospective_places_filters(request.args)
    query = (
        StationProspectivePlaceAES.query
        .options(
            joinedload(StationProspectivePlaceAES.regional_district),
            joinedload(StationProspectivePlaceAES.regional_energy_system).joinedload(
                RegionalEnergySystem.union_energy_system
            ),
            joinedload(StationProspectivePlaceAES.machine_prospective_places).joinedload(
                MachineProspectivePlaceAES.prospective_place_type
            ),
            joinedload(StationProspectivePlaceAES.machine_prospective_places).joinedload(
                MachineProspectivePlaceAES.station_prospective_place_aes
            ),
            joinedload(StationProspectivePlaceAES.machine_prospective_places).joinedload(
                MachineProspectivePlaceAES.year_specific_fuel_cost
            ),
            joinedload(StationProspectivePlaceAES.machine_prospective_places).joinedload(
                MachineProspectivePlaceAES.year_specific_fixed_operating_costs
            ),
            joinedload(StationProspectivePlaceAES.machine_prospective_places).joinedload(
                MachineProspectivePlaceAES.year_specific_capital_investment
            ),
            joinedload(StationProspectivePlaceAES.machine_prospective_places).joinedload(
                MachineProspectivePlaceAES.year_specific_decommissioning
            ),
        )
    )
    query = apply_prospective_places_aes_station_order(query)
    query = apply_prospective_places_filters(query, filters)
    stations = query.all()
    for station in stations:
        sort_machines_by_station_block_number(station)
    filter_context = get_prospective_places_filter_context(filters)
    return stations, filters, filter_context


@prospective_places_bp.route("/")
@login_required
def prospective_places_start():
    """Главная страница модуля «Характеристика актуальных площадок размещения новых электростанций»."""
    return render_template("generation/prospective_places/prospective_places_start.html")


@prospective_places_bp.route("/aes/")
@login_required
def prospective_places_aes():
    """Характеристика актуальных площадок размещения новых АЭС."""
    stations, filters, filter_context = _load_prospective_places_aes_stations_and_filters()

    return render_template(
        "generation/prospective_places/aes/prospective_places_aes.html",
        stations=stations,
        total_count=len(stations),
        has_active_filters=any(
            filters.get(k)
            for k in [
                "energy_system_type_filter",
                "union_energy_system_filter",
                "regional_energy_system_filter",
                "federal_district_filter",
                "regional_district_filter",
                "site_name_filter",
                "unit_type_filter",
                "possible_implementation_period_filter",
                "prospective_place_type_filter",
                "selection_factor_filter",
            ]
        ),
        **filter_context,
    )


@prospective_places_bp.route("/aes/tep-main/")
@login_required
def prospective_places_aes_tep_main():
    """ТЭП основных площадок — отдельная страница (как список, другая таблица)."""
    from app.common.services.get_services.years.years_get_services import (
        get_ges_tep_current_price_year_number,
    )
    from app.generation.prospective_places.services.tep_capital_cost_current_year_services import (
        aes_tep_rows_have_mixed_source_price_years,
        get_aes_tep_main_radio_price_year_number,
    )
    from app.generation.prospective_places.services.aes.prospective_places_aes_tep_view_services import (
        build_tep_view_rows,
        collect_main_and_reserve_machines,
        total_capacity_mw_sum,
    )

    stations, filters, filter_context = _load_prospective_places_aes_stations_and_filters()
    machines_main, _ = collect_main_and_reserve_machines(stations)

    current_y = get_ges_tep_current_price_year_number()
    tep_price_label_year = get_aes_tep_main_radio_price_year_number(
        machines_main,
        current_target_year=current_y,
    )
    tep_main_force_source_only = aes_tep_rows_have_mixed_source_price_years(machines_main)
    tep_rows_current = build_tep_view_rows(
        machines_main,
        tep_main_current_year_prices=True,
        tep_main_scaling_target_year=tep_price_label_year,
    )
    tep_rows_source = build_tep_view_rows(
        machines_main,
        tep_main_current_year_prices=False,
    )
    _log_prospective_aes_tep_page_view("Открыта страница: ТЭП основных перспективных площадок АЭС")

    return render_template(
        "generation/prospective_places/aes/prospective_places_aes_tep.html",
        tep_rows_current=tep_rows_current,
        tep_rows_source=tep_rows_source,
        tep_total_mw=total_capacity_mw_sum(machines_main),
        page_title="Перечень исходных ТЭП перспективных площадок АЭС",
        page_subtitle="",
        toolbar_mode="tep_main",
        aes_tep_export_scope="main",
        tep_price_label_year=tep_price_label_year,
        tep_main_force_source_only=tep_main_force_source_only,
        ges_tep_price_coeff_can_edit=_aes_tep_price_coeff_can_edit(),
        has_active_filters=any(
            filters.get(k)
            for k in [
                "energy_system_type_filter",
                "union_energy_system_filter",
                "regional_energy_system_filter",
                "federal_district_filter",
                "regional_district_filter",
                "site_name_filter",
                "unit_type_filter",
                "possible_implementation_period_filter",
                "prospective_place_type_filter",
                "selection_factor_filter",
            ]
        ),
        **filter_context,
    )


@prospective_places_bp.route("/aes/tep-reserve/")
@login_required
def prospective_places_aes_tep_reserve():
    """ТЭП резервных площадок — отдельная страница (как список, другая таблица)."""
    from app.common.services.get_services.years.years_get_services import (
        get_ges_tep_current_price_year_number,
    )
    from app.generation.prospective_places.services.tep_capital_cost_current_year_services import (
        aes_tep_rows_have_mixed_source_price_years,
        get_aes_tep_main_radio_price_year_number,
    )
    from app.generation.prospective_places.services.aes.prospective_places_aes_tep_view_services import (
        build_tep_view_rows,
        collect_main_and_reserve_machines,
        total_capacity_mw_sum,
    )

    stations, filters, filter_context = _load_prospective_places_aes_stations_and_filters()
    _, machines_reserve = collect_main_and_reserve_machines(stations)

    current_y = get_ges_tep_current_price_year_number()
    tep_price_label_year = get_aes_tep_main_radio_price_year_number(
        machines_reserve,
        current_target_year=current_y,
    )
    tep_main_force_source_only = aes_tep_rows_have_mixed_source_price_years(machines_reserve)
    tep_rows_current = build_tep_view_rows(
        machines_reserve,
        tep_main_current_year_prices=True,
        tep_main_scaling_target_year=tep_price_label_year,
    )
    tep_rows_source = build_tep_view_rows(
        machines_reserve,
        tep_main_current_year_prices=False,
    )
    _log_prospective_aes_tep_page_view("Открыта страница: ТЭП резервных перспективных площадок АЭС")

    return render_template(
        "generation/prospective_places/aes/prospective_places_aes_tep.html",
        tep_rows_current=tep_rows_current,
        tep_rows_source=tep_rows_source,
        tep_total_mw=total_capacity_mw_sum(machines_reserve),
        page_title="ТЭП резервных перспективных площадок АЭС",
        page_subtitle="",
        toolbar_mode="tep_reserve",
        aes_tep_export_scope="reserve",
        tep_price_label_year=tep_price_label_year,
        tep_main_force_source_only=tep_main_force_source_only,
        ges_tep_price_coeff_can_edit=_aes_tep_price_coeff_can_edit(),
        has_active_filters=any(
            filters.get(k)
            for k in [
                "energy_system_type_filter",
                "union_energy_system_filter",
                "regional_energy_system_filter",
                "federal_district_filter",
                "regional_district_filter",
                "site_name_filter",
                "unit_type_filter",
                "possible_implementation_period_filter",
                "prospective_place_type_filter",
                "selection_factor_filter",
            ]
        ),
        **filter_context,
    )


@prospective_places_bp.route("/aes/<int:id>/", methods=["GET", "POST"])
@login_required
def prospective_place_aes_details(id):
    """Карточка перспективной площадки АЭС (заполнение и редактирование полей)."""
    from app.generation.prospective_places.models import (
        StationProspectivePlaceAES,
        MachineProspectivePlaceAES,
    )
    from app.generation.prospective_places.forms import ProspectivePlaceAESEditForm
    from app.refdata.models.energy_systems.regional_energy_system_model import (
        RegionalEnergySystem,
    )
    from app.common.services.get_services.territories.regional_district_get_services import (
        get_regional_district_list_full,
    )
    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_regional_energy_system_choices,
        get_res_to_ues_id_map,
    )
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
        get_union_energy_systems_map,
    )

    place = (
        StationProspectivePlaceAES.query
        .options(
            joinedload(StationProspectivePlaceAES.regional_district),
            joinedload(StationProspectivePlaceAES.regional_energy_system).joinedload(
                RegionalEnergySystem.union_energy_system
            ),
            joinedload(StationProspectivePlaceAES.machine_prospective_places).joinedload(
                MachineProspectivePlaceAES.prospective_place_type
            ),
            joinedload(StationProspectivePlaceAES.machine_prospective_places).joinedload(
                MachineProspectivePlaceAES.year_specific_fuel_cost
            ),
            joinedload(StationProspectivePlaceAES.machine_prospective_places).joinedload(
                MachineProspectivePlaceAES.year_specific_fixed_operating_costs
            ),
            joinedload(StationProspectivePlaceAES.machine_prospective_places).joinedload(
                MachineProspectivePlaceAES.year_specific_capital_investment
            ),
            joinedload(StationProspectivePlaceAES.machine_prospective_places).joinedload(
                MachineProspectivePlaceAES.year_specific_decommissioning
            ),
        )
        .get_or_404(id)
    )
    sort_machines_by_station_block_number(place)

    can_edit = _prospective_place_can_edit()

    form = ProspectivePlaceAESEditForm()
    rd_list = get_regional_district_list_full()
    form.id_regional_district.choices = [("", "— Не указано —")] + [
        (str(rd_id), name) for rd_id, name in rd_list
    ]
    res_list = get_regional_energy_system_choices()
    form.id_regional_energy_system.choices = [("", "— Не указано —")] + [
        (str(res_id), name) for res_id, name in res_list
    ]

    # Карта для автоподстановки ОЭС по выбранной РЭС (на лету)
    res_to_ues = get_res_to_ues_id_map()
    ues_names = get_union_energy_systems_map()
    res_auto_map = {"": "Нет данных"}
    for res_id, _ in res_list:
        ues_id = res_to_ues.get(res_id)
        ues_name = ues_names.get(ues_id, "Нет данных") if ues_id else "Нет данных"
        res_auto_map[str(res_id)] = ues_name

    if request.method == "GET":
        form.site_name.data = place.site_name
        form.id_regional_district.data = place.id_regional_district
        form.id_regional_energy_system.data = place.id_regional_energy_system
        form.geo_location.data = place.geo_location
        form.planned_capacity_mw.data = place.planned_capacity_mw
        form.planned_unit_capacity_mw.data = place.planned_unit_capacity_mw
        form.selection_factor.data = place.selection_factor

    if form.validate_on_submit() and can_edit:
        try:
            place.site_name = (form.site_name.data or "").strip() or None
            place.id_regional_district = form.id_regional_district.data
            place.id_regional_energy_system = form.id_regional_energy_system.data
            place.geo_location = (form.geo_location.data or "").strip() or None
            place.planned_capacity_mw = form.planned_capacity_mw.data
            place.planned_unit_capacity_mw = form.planned_unit_capacity_mw.data
            place.selection_factor = (form.selection_factor.data or "").strip() or None
            db.session.commit()
            flash("Перспективная площадка успешно сохранена.", "success")
            return redirect(url_for("prospective_places_bp.prospective_place_aes_details", id=place.id))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при сохранении: {str(e)}", "danger")

    # Сумма мощности энергоблоков (МВт) для строки «Всего»
    total_capacity_mw = 0
    for mp in place.machine_prospective_places:
        try:
            val = (mp.unit_capacity_mw or "").strip()
            if val:
                total_capacity_mw += float(val.replace(",", "."))
        except (ValueError, TypeError):
            pass

    # Столбцы, объединяемые при одинаковых значениях во всех строках
    def _norm(v):
        return ("—" if v is None else (v or "").strip()) or "—"

    def _all_same(getter):
        mp_list = place.machine_prospective_places
        if not mp_list:
            return None
        vals = [_norm(getter(mp)) for mp in mp_list]
        return vals[0] if len(set(vals)) == 1 else None

    merged_values = {
        "unit_type": _all_same(lambda mp: mp.unit_type),
        "service_life_years": _all_same(lambda mp: str(mp.service_life_years) if mp.service_life_years is not None else None),
        "construction_period_years": _all_same(lambda mp: str(mp.construction_period_years) if mp.construction_period_years is not None else None),
        "max_annual_operating_hours": _all_same(lambda mp: mp.max_annual_operating_hours),
        "specific_fuel_cost_rub_per_kwh": _all_same(lambda mp: mp.specific_fuel_cost_rub_per_kwh),
        "specific_fixed_operating_costs_thous_rub_per_kw": _all_same(lambda mp: mp.specific_fixed_operating_costs_thous_rub_per_kw),
        "relative_auxiliary_power_consumption_pct": _all_same(lambda mp: mp.relative_auxiliary_power_consumption_pct),
        "specific_capital_investment_thous_rub_per_kw": _all_same(lambda mp: mp.specific_capital_investment_thous_rub_per_kw),
        "specific_decommissioning_cost_thous_rub_per_kw": _all_same(lambda mp: mp.specific_decommissioning_cost_thous_rub_per_kw),
        "emergency_state_probability": _all_same(lambda mp: mp.emergency_state_probability),
        "ozp": _all_same(lambda mp: mp.ozp),
        "vlp": _all_same(lambda mp: mp.vlp),
    }
    station_link_ctx = _get_station_link_context(place)

    return render_template(
        "generation/prospective_places/aes/prospective_place_aes_details.html",
        place=place,
        form=form,
        can_edit=can_edit,
        res_auto_map=res_auto_map,
        total_capacity_mw=total_capacity_mw,
        merged_values=merged_values,
        **station_link_ctx,
    )


@prospective_places_bp.route("/aes/<int:id>/link-station/", methods=["POST"])
@login_required
def prospective_place_aes_link_station(id):
    from app.generation.prospective_places.models import StationProspectivePlaceAES

    if not _prospective_place_can_edit():
        flash("Недостаточно прав для изменения связи с электростанцией.", "warning")
        return redirect(url_for("prospective_places_bp.prospective_place_aes_details", id=id))

    place = StationProspectivePlaceAES.query.get_or_404(id)
    station_id_raw = (request.form.get("linked_station_id") or "").strip()

    try:
        station_id = int(station_id_raw) if station_id_raw else None
    except ValueError:
        flash("Некорректно выбрана электростанция.", "danger")
        return redirect(url_for("prospective_places_bp.prospective_place_aes_details", id=id))

    try:
        station = _assign_prospective_place_station(place, station_id)
        db.session.commit()
        if station is None:
            flash("Связь с электростанцией снята.", "success")
        else:
            flash("Связь с электростанцией сохранена.", "success")
        log_to_db(
            current_user,
            "Изменена связь перспективной площадки АЭС с электростанцией",
            details=(
                f"id_place={place.id}; site_name={place.site_name!r}; "
                f"station_id={(station.id if station else None)}"
            ),
            entity_type="prospective_place_aes",
            entity_id=place.id,
        )
    except (LookupError, ValueError) as e:
        db.session.rollback()
        flash(str(e), "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка при сохранении связи: {str(e)}", "danger")

    return redirect(url_for("prospective_places_bp.prospective_place_aes_details", id=id))


@prospective_places_bp.route("/aes/<int:id>/go-station/", methods=["GET"])
@login_required
def prospective_place_aes_go_station(id):
    from app.generation.prospective_places.models import StationProspectivePlaceAES

    place = StationProspectivePlaceAES.query.get_or_404(id)
    return _navigation_redirect_to_station(
        place,
        back_endpoint="prospective_places_bp.prospective_place_aes_details",
        back_id=id,
    )


@prospective_places_bp.route("/aes/<int:place_id>/machine/<int:machine_id>/", methods=["GET", "POST"])
@login_required
def machine_prospective_place_aes_details(place_id, machine_id):
    """Добавление/редактирование энергоблока перспективной площадки АЭС (machine_id=0 — добавить)."""
    from app.generation.prospective_places.models import (
        StationProspectivePlaceAES,
        MachineProspectivePlaceAES,
    )
    from app.generation.prospective_places.forms import MachineProspectivePlaceAESEditForm
    from app.generation.prospective_places.models.aes.prospective_place_type_aes_model import ProspectivePlaceTypeAES
    from app.common.services.get_services.years.years_get_services import get_year_list_full

    def _aes_machine_year_choices():
        years = get_year_list_full()
        return [("", "— не указано —")] + [(str(y.id), str(y.number)) for y in years]

    def _set_aes_machine_year_fields(form):
        ch = _aes_machine_year_choices()
        form.id_year_specific_fuel_cost.choices = ch
        form.id_year_specific_fixed_operating_costs.choices = ch
        form.id_year_specific_capital_investment.choices = ch
        form.id_year_specific_decommissioning.choices = ch

    edit_roles = ["admin", "generation-admin", "generation-editor"]
    can_edit = current_user.is_authenticated and any(
        role in current_user.role_names for role in edit_roles
    )
    if not can_edit:
        flash("Недостаточно прав для редактирования энергоблока.", "warning")
        return redirect(url_for("prospective_places_bp.prospective_place_aes_details", id=place_id))

    place = StationProspectivePlaceAES.query.get_or_404(place_id)
    machine = (
        MachineProspectivePlaceAES.query.options(
            joinedload(MachineProspectivePlaceAES.year_specific_fuel_cost),
            joinedload(MachineProspectivePlaceAES.year_specific_fixed_operating_costs),
            joinedload(MachineProspectivePlaceAES.year_specific_capital_investment),
            joinedload(MachineProspectivePlaceAES.year_specific_decommissioning),
        ).filter(
            MachineProspectivePlaceAES.id == machine_id,
            MachineProspectivePlaceAES.id_station_prospective_place_aes == place_id,
        ).first()
        if machine_id
        else None
    )

    if machine_id and not machine:
        flash("Энергоблок не найден.", "danger")
        return redirect(url_for("prospective_places_bp.prospective_place_aes_details", id=place_id))

    form = MachineProspectivePlaceAESEditForm()
    ppt_list = ProspectivePlaceTypeAES.query.order_by(ProspectivePlaceTypeAES.name).all()
    form.id_prospective_place_type.choices = [("", "— Не указано —")] + [
        (str(p.id), p.name) for p in ppt_list
    ]
    _set_aes_machine_year_fields(form)

    if request.method == "GET":
        if machine:
            form.id_prospective_place_type.data = machine.id_prospective_place_type
            form.station_block_number.data = str(machine.station_block_number) if machine.station_block_number is not None else None
            form.unit_type.data = machine.unit_type
            form.unit_capacity_mw.data = machine.unit_capacity_mw
            form.max_annual_operating_hours.data = machine.max_annual_operating_hours
            form.specific_fuel_cost_rub_per_kwh.data = machine.specific_fuel_cost_rub_per_kwh
            form.id_year_specific_fuel_cost.data = machine.id_year_specific_fuel_cost
            form.specific_fixed_operating_costs_thous_rub_per_kw.data = machine.specific_fixed_operating_costs_thous_rub_per_kw
            form.id_year_specific_fixed_operating_costs.data = machine.id_year_specific_fixed_operating_costs
            form.relative_auxiliary_power_consumption_pct.data = machine.relative_auxiliary_power_consumption_pct
            form.specific_capital_investment_thous_rub_per_kw.data = machine.specific_capital_investment_thous_rub_per_kw
            form.id_year_specific_capital_investment.data = machine.id_year_specific_capital_investment
            form.specific_decommissioning_cost_thous_rub_per_kw.data = machine.specific_decommissioning_cost_thous_rub_per_kw
            form.id_year_specific_decommissioning.data = machine.id_year_specific_decommissioning
            form.emergency_state_probability.data = machine.emergency_state_probability
            form.ozp.data = machine.ozp
            form.vlp.data = machine.vlp
            form.note.data = machine.note
            form.possible_implementation_period.data = str(machine.possible_implementation_period) if machine.possible_implementation_period is not None else None
            form.service_life_years.data = machine.service_life_years
            form.construction_period_years.data = machine.construction_period_years

    if form.validate_on_submit() and can_edit:
        try:
            if machine:
                machine.id_prospective_place_type = form.id_prospective_place_type.data
                machine.station_block_number = (form.station_block_number.data or "").strip() or None
                machine.unit_type = (form.unit_type.data or "").strip() or None
                machine.unit_capacity_mw = (form.unit_capacity_mw.data or "").strip() or None
                machine.max_annual_operating_hours = (form.max_annual_operating_hours.data or "").strip() or None
                machine.specific_fuel_cost_rub_per_kwh = (form.specific_fuel_cost_rub_per_kwh.data or "").strip() or None
                machine.id_year_specific_fuel_cost = form.id_year_specific_fuel_cost.data
                machine.specific_fixed_operating_costs_thous_rub_per_kw = (form.specific_fixed_operating_costs_thous_rub_per_kw.data or "").strip() or None
                machine.id_year_specific_fixed_operating_costs = form.id_year_specific_fixed_operating_costs.data
                machine.relative_auxiliary_power_consumption_pct = (form.relative_auxiliary_power_consumption_pct.data or "").strip() or None
                machine.specific_capital_investment_thous_rub_per_kw = (form.specific_capital_investment_thous_rub_per_kw.data or "").strip() or None
                machine.id_year_specific_capital_investment = form.id_year_specific_capital_investment.data
                machine.specific_decommissioning_cost_thous_rub_per_kw = (form.specific_decommissioning_cost_thous_rub_per_kw.data or "").strip() or None
                machine.id_year_specific_decommissioning = form.id_year_specific_decommissioning.data
                machine.emergency_state_probability = (form.emergency_state_probability.data or "").strip() or None
                machine.ozp = (form.ozp.data or "").strip() or None
                machine.vlp = (form.vlp.data or "").strip() or None
                machine.note = (form.note.data or "").strip() or None
                machine.possible_implementation_period = (form.possible_implementation_period.data or "").strip() or None
                machine.service_life_years = form.service_life_years.data
                machine.construction_period_years = form.construction_period_years.data
            else:
                machine = MachineProspectivePlaceAES(
                    id_station_prospective_place_aes=place_id,
                    id_prospective_place_type=form.id_prospective_place_type.data,
                    station_block_number=(form.station_block_number.data or "").strip() or None,
                    unit_type=(form.unit_type.data or "").strip() or None,
                    unit_capacity_mw=(form.unit_capacity_mw.data or "").strip() or None,
                    max_annual_operating_hours=(form.max_annual_operating_hours.data or "").strip() or None,
                    specific_fuel_cost_rub_per_kwh=(form.specific_fuel_cost_rub_per_kwh.data or "").strip() or None,
                    id_year_specific_fuel_cost=form.id_year_specific_fuel_cost.data,
                    specific_fixed_operating_costs_thous_rub_per_kw=(form.specific_fixed_operating_costs_thous_rub_per_kw.data or "").strip() or None,
                    id_year_specific_fixed_operating_costs=form.id_year_specific_fixed_operating_costs.data,
                    relative_auxiliary_power_consumption_pct=(form.relative_auxiliary_power_consumption_pct.data or "").strip() or None,
                    specific_capital_investment_thous_rub_per_kw=(form.specific_capital_investment_thous_rub_per_kw.data or "").strip() or None,
                    id_year_specific_capital_investment=form.id_year_specific_capital_investment.data,
                    specific_decommissioning_cost_thous_rub_per_kw=(form.specific_decommissioning_cost_thous_rub_per_kw.data or "").strip() or None,
                    id_year_specific_decommissioning=form.id_year_specific_decommissioning.data,
                    emergency_state_probability=(form.emergency_state_probability.data or "").strip() or None,
                    ozp=(form.ozp.data or "").strip() or None,
                    vlp=(form.vlp.data or "").strip() or None,
                    note=(form.note.data or "").strip() or None,
                    possible_implementation_period=(form.possible_implementation_period.data or "").strip() or None,
                    service_life_years=form.service_life_years.data,
                    construction_period_years=form.construction_period_years.data,
                )
                db.session.add(machine)
            db.session.commit()
            flash("Энергоблок успешно сохранен.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при сохранении: {str(e)}", "danger")

    return render_template(
        "generation/prospective_places/aes/machine_prospective_place_aes_details.html",
        place=place,
        machine=machine,
        form=form,
    )


@prospective_places_bp.route(
    "/aes/<int:place_id>/machine/<int:machine_id>/delete/",
    methods=["POST"],
)
@login_required
def delete_machine_prospective_place_aes(place_id, machine_id):
    """Удаление энергоблока перспективной площадки АЭС."""
    edit_roles = ["admin", "generation-admin", "generation-editor"]
    can_edit = current_user.is_authenticated and any(
        role in current_user.role_names for role in edit_roles
    )
    if not can_edit:
        flash("Недостаточно прав для удаления энергоблока.", "warning")
        return redirect(url_for("prospective_places_bp.prospective_place_aes_details", id=place_id))

    from app.generation.prospective_places.models import MachineProspectivePlaceAES

    machine = MachineProspectivePlaceAES.query.filter(
        MachineProspectivePlaceAES.id == machine_id,
        MachineProspectivePlaceAES.id_station_prospective_place_aes == place_id,
    ).first()
    if not machine:
        flash("Энергоблок не найден.", "danger")
        return redirect(url_for("prospective_places_bp.prospective_place_aes_details", id=place_id))

    try:
        db.session.delete(machine)
        db.session.commit()
        flash("Энергоблок удален.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка при удалении: {str(e)}", "danger")

    return redirect(url_for("prospective_places_bp.prospective_place_aes_details", id=place_id))


@prospective_places_bp.route("/aes/add/", methods=["GET", "POST"])
@login_required
def add_prospective_place_aes():
    """Добавление новой перспективной площадки АЭС."""
    edit_roles = ["admin", "generation-admin", "generation-editor"]
    can_edit = current_user.is_authenticated and any(
        role in current_user.role_names for role in edit_roles
    )
    if not can_edit:
        flash("Недостаточно прав для добавления перспективной площадки.", "warning")
        return redirect(url_for("prospective_places_bp.prospective_places_aes"))

    from app.generation.prospective_places.forms import ProspectivePlaceAESAddForm
    from app.generation.prospective_places.models import StationProspectivePlaceAES
    from app.common.services.get_services.territories.regional_district_get_services import (
        get_regional_district_list_full,
    )

    form = ProspectivePlaceAESAddForm()
    rd_list = get_regional_district_list_full()
    form.id_regional_district.choices = [("", "— Выберите субъект РФ —")] + [
        (str(rd_id), name) for rd_id, name in rd_list
    ]

    if form.validate_on_submit():
        site_name = (form.site_name.data or "").strip()
        id_regional_district = form.id_regional_district.data

        # Проверка уникальности по (site_name, id_regional_district)
        q = StationProspectivePlaceAES.query
        if site_name:
            q = q.filter(StationProspectivePlaceAES.site_name == site_name)
        else:
            q = q.filter(
                db.or_(
                    StationProspectivePlaceAES.site_name.is_(None),
                    StationProspectivePlaceAES.site_name == "",
                )
            )
        if id_regional_district is not None:
            q = q.filter(
                StationProspectivePlaceAES.id_regional_district == id_regional_district
            )
        else:
            q = q.filter(StationProspectivePlaceAES.id_regional_district.is_(None))

        if q.first():
            flash(
                "Перспективная площадка с таким наименованием и субъектом РФ уже существует.",
                "danger",
            )
            return render_template(
                "generation/prospective_places/aes/prospective_place_aes_add.html",
                form=form,
            )

        try:
            place = StationProspectivePlaceAES(
                site_name=site_name or None,
                id_regional_district=id_regional_district,
            )
            db.session.add(place)
            db.session.commit()
            flash("Перспективная площадка успешно создана.", "success")
            return redirect(url_for("prospective_places_bp.prospective_places_aes"))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при создании: {str(e)}", "danger")

    return render_template(
        "generation/prospective_places/aes/prospective_place_aes_add.html",
        form=form,
    )


def _br_to_newline(s):
    """Преобразует <br> и переносы в \\n для Excel."""
    if not s:
        return s
    s = str(s)
    for br in ("<br>", "<br/>", "<br />", "<BR>", "<Br>"):
        s = s.replace(br, "\n")
    return s.replace("\r\n", "\n").replace("\r", "\n")


def _write_machines_sheet(ws, machines, include_place_name=False, include_note=True):
    """Записывает лист с энергоблоками в формате страницы площадки (aes/1/)."""
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    from openpyxl.utils import get_column_letter

    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    header_fill = PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid")
    header_font = Font(bold=True)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
    right_align = Alignment(horizontal="right", vertical="center", wrap_text=True)

    # 18 колонок без place_name, 19 с place_name; без Примечания - на 1 меньше
    h1_base = [
        "№ п/п",
        "Тип площадки",
        "Станционный номер блока",
        "Тип энергоблока",
        "Мощность энергоблока, МВт",
        "Возможный срок реализации",
        "Срок эксплуатации АЭС, лет",
        "Срок строительства АЭС, лет",
        "Предельное годовое число часов использования мощности энергоблока, час",
        "Удельная топливная составляющая эксплуатационных затрат в ценах текущего года, тыс. руб./кВт",
        "Удельные условно постоянные эксплуатационные затраты (без амортизационных отчислений), руб./кВтч",
        "Относительная величина расхода электрической энергии на собственные нужды АЭС, %",
        "Удельные капиталовложения в строительство АЭС в ценах текущего года (без НДС), тыс. руб./кВт",
        "Удельные затраты на вывод из эксплуатации, тыс. руб./кВт",
        "Вероятность аварийного состояния",
        "Относительная продолжительность плановых простоев:",
        None,
        "Примечание" if include_note else None,
    ]
    h1_base = [h for h in h1_base if h is not None]
    if include_place_name:
        h1_base.insert(1, "Наименование площадки")
    headers_row1 = h1_base
    headers_row2 = [None] * 16 + ["ОЗП", "ВЛП"] + ([] if not include_note else [None])
    if include_place_name:
        headers_row2 = [None] * 17 + ["ОЗП", "ВЛП"] + ([] if not include_note else [None])
    headers_row2 = [h for h in headers_row2 if h is not None]

    total_cols = (19 if include_place_name else 18) - (0 if include_note else 1)
    for col, val in enumerate(headers_row1, 1):
        if val:
            cell = ws.cell(row=1, column=col, value=val)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = thin_border
    ozp_col = 17 if include_place_name else 16
    vlp_col = 18 if include_place_name else 17
    for col in (ozp_col, vlp_col):
        cell = ws.cell(row=2, column=col, value="ОЗП" if col == ozp_col else "ВЛП")
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border

    last_single = 17 if include_place_name else 16
    ozp_vlp_start = 17 if include_place_name else 16
    for col in range(1, last_single):
        ws.merge_cells(start_row=1, start_column=col, end_row=2, end_column=col)
    ws.merge_cells(start_row=1, start_column=ozp_vlp_start, end_row=1, end_column=ozp_vlp_start + 1)
    if include_note:
        note_col = 19 if include_place_name else 18
        ws.merge_cells(start_row=1, start_column=note_col, end_row=2, end_column=note_col)

    total_capacity_mw = 0
    for mp in machines:
        try:
            val = (mp.unit_capacity_mw or "").strip()
            if val:
                total_capacity_mw += float(val.replace(",", "."))
        except (ValueError, TypeError):
            pass

    row_num = 3
    for idx, mp in enumerate(machines, 1):
        row_data = [
            str(idx).replace(".", ","),
        ]
        if include_place_name:
            row_data.append(mp.station_prospective_place_aes.site_name or "—")
        row_data.extend([
            ((mp.prospective_place_type.name if mp.prospective_place_type else None) or "—").replace(".", ","),
            (mp.station_block_number or "—").replace(".", ","),
            (mp.unit_type or "—").replace(".", ","),
            (mp.unit_capacity_mw or "—").replace(".", ","),
            (mp.possible_implementation_period or "—"),
            (str(mp.service_life_years) if mp.service_life_years is not None else "—"),
            (str(mp.construction_period_years) if mp.construction_period_years is not None else "—"),
            (mp.max_annual_operating_hours or "—").replace(".", ","),
            (mp.specific_fuel_cost_rub_per_kwh or "—").replace(".", ","),
            (mp.specific_fixed_operating_costs_thous_rub_per_kw or "—").replace(".", ","),
            (mp.relative_auxiliary_power_consumption_pct or "—").replace(".", ","),
            (mp.specific_capital_investment_thous_rub_per_kw or "—").replace(".", ","),
            (mp.specific_decommissioning_cost_thous_rub_per_kw or "—").replace(".", ","),
            (mp.emergency_state_probability or "—").replace(".", ","),
            (mp.ozp or "—").replace(".", ","),
            (mp.vlp or "—").replace(".", ","),
        ])
        if include_note:
            row_data.append((mp.note or "—").replace(".", ","))
        left_align_cols = list((2, 5) if include_place_name else (2, 4))
        if include_note:
            left_align_cols.append(total_cols)
        for col, val in enumerate(row_data, 1):
            cell = ws.cell(row=row_num, column=col, value=val)
            cell.border = thin_border
            cell.alignment = center_align if col not in left_align_cols else left_align
        row_num += 1

    if machines:
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=4)
        cell = ws.cell(row=row_num, column=1, value="Всего:")
        cell.font = header_font
        cell.alignment = right_align
        cell.border = thin_border
        cell.fill = PatternFill(start_color="E2E3E5", end_color="E2E3E5", fill_type="solid")
        ws.cell(row=row_num, column=5, value=int(round(total_capacity_mw, 0)))
        ws.cell(row=row_num, column=5).border = thin_border
        ws.cell(row=row_num, column=5).alignment = center_align
        ws.cell(row=row_num, column=5).fill = PatternFill(start_color="E2E3E5", end_color="E2E3E5", fill_type="solid")
        ws.merge_cells(start_row=row_num, start_column=6, end_row=row_num, end_column=total_cols)
        for c in range(6, total_cols + 1):
            ws.cell(row=row_num, column=c).border = thin_border
            ws.cell(row=row_num, column=c).fill = PatternFill(start_color="E2E3E5", end_color="E2E3E5", fill_type="solid")
    else:
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=total_cols)
        cell = ws.cell(row=row_num, column=1, value="Нет данных")
        cell.alignment = center_align
        cell.border = thin_border

    widths_full = [6, 25, 18, 12, 18, 12, 10, 10, 12, 18, 18, 12, 18, 18, 18, 8, 8, 25, 25] if include_place_name else [6, 18, 12, 18, 12, 10, 10, 12, 18, 18, 12, 18, 18, 18, 8, 8, 25, 25]
    widths = widths_full[:total_cols]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


@prospective_places_bp.route("/aes/export/", methods=["GET"])
@login_required
@no_compress
def export_prospective_places_aes():
    """Экспорт перспективных площадок АЭС в Excel (форматирование как на экране, с объединенными ячейками)."""
    from app.generation.prospective_places.models import StationProspectivePlaceAES, MachineProspectivePlaceAES
    from app.refdata.models.energy_systems.regional_energy_system_model import (
        RegionalEnergySystem,
    )
    from app.generation.prospective_places.services.aes.prospective_places_filters_services import (
        extract_prospective_places_filters,
        apply_prospective_places_filters,
        apply_prospective_places_aes_station_order,
    )
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    from openpyxl.utils import get_column_letter

    filters = extract_prospective_places_filters(request.args)
    query = (
        StationProspectivePlaceAES.query
        .options(
            joinedload(StationProspectivePlaceAES.regional_district),
            joinedload(StationProspectivePlaceAES.regional_energy_system).joinedload(
                RegionalEnergySystem.union_energy_system
            ),
            joinedload(StationProspectivePlaceAES.machine_prospective_places).joinedload(
                MachineProspectivePlaceAES.prospective_place_type
            ),
            joinedload(StationProspectivePlaceAES.machine_prospective_places).joinedload(
                MachineProspectivePlaceAES.station_prospective_place_aes
            ),
            joinedload(StationProspectivePlaceAES.machine_prospective_places).joinedload(
                MachineProspectivePlaceAES.year_specific_fuel_cost
            ),
            joinedload(StationProspectivePlaceAES.machine_prospective_places).joinedload(
                MachineProspectivePlaceAES.year_specific_fixed_operating_costs
            ),
            joinedload(StationProspectivePlaceAES.machine_prospective_places).joinedload(
                MachineProspectivePlaceAES.year_specific_capital_investment
            ),
            joinedload(StationProspectivePlaceAES.machine_prospective_places).joinedload(
                MachineProspectivePlaceAES.year_specific_decommissioning
            ),
        )
    )
    query = apply_prospective_places_aes_station_order(query)
    query = apply_prospective_places_filters(query, filters)
    stations = query.all()
    for station in stations:
        sort_machines_by_station_block_number(station)

    if request.args.get("export_mode") == "aes_tep":
        from io import BytesIO
        from openpyxl import Workbook
        from app.common.services.get_services.years.years_get_services import (
            get_ges_tep_current_price_year_number,
        )
        from app.generation.prospective_places.services.tep_capital_cost_current_year_services import (
            get_aes_tep_main_radio_price_year_number,
        )
        from app.generation.prospective_places.services.aes.prospective_places_aes_tep_view_services import (
            build_tep_view_rows,
        )
        from app.generation.prospective_places.services.aes.export_prospective_places_aes_tep_excel import (
            write_aes_tep_screen_sheet,
        )
        from app.generation.prospective_places.models.aes.prospective_place_type_aes_model import ProspectivePlaceTypeAES

        scope = (request.args.get("aes_tep_scope") or "main").strip().lower()
        source_prices = request.args.get("tep_main_view") == "source"
        main_types = ProspectivePlaceTypeAES.query.filter(ProspectivePlaceTypeAES.name.ilike("%основн%")).all()
        reserve_types = ProspectivePlaceTypeAES.query.filter(ProspectivePlaceTypeAES.name.ilike("%резерв%")).all()
        main_type_ids = {t.id for t in main_types}
        reserve_type_ids = {t.id for t in reserve_types}
        machines_export: list = []
        for s in stations:
            for mp in s.machine_prospective_places:
                if scope == "reserve" and mp.id_prospective_place_type in reserve_type_ids:
                    machines_export.append(mp)
                elif scope != "reserve" and mp.id_prospective_place_type in main_type_ids:
                    machines_export.append(mp)
        current_y = get_ges_tep_current_price_year_number()
        typ_year = get_aes_tep_main_radio_price_year_number(
            machines_export,
            current_target_year=current_y,
        )
        tep_rows = build_tep_view_rows(
            machines_export,
            tep_main_current_year_prices=not source_prices,
            tep_main_scaling_target_year=typ_year if not source_prices else None,
        )
        wb = Workbook()
        ws = wb.active
        title_scope = "резервные" if scope == "reserve" else "основные"
        write_aes_tep_screen_sheet(
            ws,
            tep_rows,
            sheet_title=f"ТЭП {title_scope} АЭС",
            show_price_year_columns=source_prices,
        )
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        filename = f"aes_tep_{scope}_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )

    wb = Workbook()
    ws = wb.active
    ws.title = "Характеристика актуальных площадок размещения новых АЭС"

    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    header_fill = PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid")
    header_font = Font(bold=True)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_align = Alignment(horizontal="left", vertical="center", wrap_text=True)

    headers = [
        "№ п/п",
        "Наименование площадки размещения АЭС",
        "Объединенная энергосистема (ОЭС)",
        "Субъект Российской Федерации",
        "Географическое расположение площадки",
        "Планируемая установленная генерирующая мощность АЭС, МВт",
        "Планируемая единичная мощность энергоблока, МВт",
        "Тип энергоблока",
        "Станционный номер блока",
        "Возможный срок реализации",
        "Тип площадки",
        "Фактор отбора",
    ]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border

    row_num = 2
    station_cols = [1, 2, 3, 4, 5, 6, 7, 12]  # столбцы с данными электростанции (rowspan при нескольких машинах)

    for idx, s in enumerate(stations, 1):
        ues_name = (s.regional_energy_system.union_energy_system.name if s.regional_energy_system and s.regional_energy_system.union_energy_system else None) or "—"
        rd_name = (s.regional_district.name_full if s.regional_district else None) or "—"
        site_name = s.site_name or "—"
        geo = s.geo_location or "—"
        planned_cap = s.planned_capacity_mw or "—"
        planned_unit = s.planned_unit_capacity_mw or "—"
        sel_factor_raw = s.selection_factor or "—"
        sel_factor = _br_to_newline(sel_factor_raw)

        if s.machine_prospective_places:
            first_row = row_num
            for mp in s.machine_prospective_places:
                unit_type = mp.unit_type or "—"
                block_num = mp.station_block_number or "—"
                period = mp.possible_implementation_period or "—"
                ppt_name = (mp.prospective_place_type.name if mp.prospective_place_type else None) or "—"
                row_data = [idx, site_name, ues_name, rd_name, geo, planned_cap, planned_unit, unit_type, block_num, period, ppt_name, sel_factor]
                for col, val in enumerate(row_data, 1):
                    cell = ws.cell(row=row_num, column=col, value=val)
                    cell.border = thin_border
                    cell.alignment = center_align if col != 2 and col != 4 else left_align
                row_num += 1

            # Объединение ячеек для столбцов электростанции
            if row_num - 1 > first_row:
                for sc in station_cols:
                    ws.merge_cells(start_row=first_row, start_column=sc, end_row=row_num - 1, end_column=sc)
        else:
            row_data = [idx, site_name, ues_name, rd_name, geo, planned_cap, planned_unit, "—", "—", "—", "—", sel_factor]
            for col, val in enumerate(row_data, 1):
                cell = ws.cell(row=row_num, column=col, value=val)
                cell.border = thin_border
                cell.alignment = center_align if col != 2 and col != 4 else left_align
            row_num += 1

    widths = [6, 25, 15, 20, 20, 12, 12, 18, 12, 14, 15, 14]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # Лист 2: энергоблоки основных площадок, лист 3: резервных
    from app.generation.prospective_places.models.aes.prospective_place_type_aes_model import ProspectivePlaceTypeAES
    main_types = ProspectivePlaceTypeAES.query.filter(
        ProspectivePlaceTypeAES.name.ilike("%основн%")
    ).all()
    reserve_types = ProspectivePlaceTypeAES.query.filter(
        ProspectivePlaceTypeAES.name.ilike("%резерв%")
    ).all()
    main_type_ids = {t.id for t in main_types}
    reserve_type_ids = {t.id for t in reserve_types}

    machines_main = []
    machines_reserve = []
    for s in stations:
        for mp in s.machine_prospective_places:
            ppt_id = mp.id_prospective_place_type
            if ppt_id in main_type_ids:
                machines_main.append(mp)
            elif ppt_id in reserve_type_ids:
                machines_reserve.append(mp)

    ws_main = wb.create_sheet("Исх ТЭП_основные площадки", 1)
    _write_machines_sheet(ws_main, machines_main, include_place_name=True, include_note=False)

    ws_reserve = wb.create_sheet("Исх ТЭП_резервные площадки", 2)
    _write_machines_sheet(ws_reserve, machines_reserve, include_place_name=True, include_note=False)

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"prospective_places_aes_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


@prospective_places_bp.route("/tes/")
@login_required
def prospective_places_tes():
    """Характеристика актуальных площадок размещения новых ТЭС."""
    return render_template("generation/prospective_places/tes/prospective_places_tes.html")
