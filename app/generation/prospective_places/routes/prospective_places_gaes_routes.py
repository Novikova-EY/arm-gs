# -*- coding: utf-8 -*-
"""Маршруты для перспективных площадок ГАЭС (дубликат логики ГЭС)."""
from . import prospective_places_bp
from .prospective_places_routes import no_compress
from flask import render_template, send_file, request, redirect, url_for, flash, g
from flask_login import login_required, current_user
from sqlalchemy.orm import joinedload
from io import BytesIO
from datetime import datetime

from app.extensions import db
from app.logs.services.logging_service import log_to_db
from app.common.services.get_services.years.years_get_services import (
    get_ges_tep_current_price_year_number,
)
from app.generation.prospective_places.services.gaes.machine_prospective_place_gaes_sort import (
    sort_machines_by_station_block_number,
)
from app.generation.prospective_places.services.gaes.prospective_places_filters_gaes_services import (
    build_gaes_stations_grouped_by_place_type,
)
from app.generation.prospective_places.services.gaes.prospective_places_gaes_capacity_display import (
    format_gaes_planned_capacity_display,
    inject_gaes_planned_capacity_display_html,
)
from app.generation.prospective_places.forms.decimal_input_display import (
    decimal_for_form_strip_trailing_zeros,
    format_construction_period_years_display,
    normalize_construction_period_years,
)
from app.common.services.get_services.years.years_get_services import (
    get_ges_tep_current_price_year_number,
)
from app.generation.prospective_places.services.tep_capital_cost_current_year_services import (
    apply_derived_specific_capital_investment_to_gaes_tep_source_row,
    fmt_specific_capital_investment_thous_rub_per_kw_derived,
    get_tep_price_coefficient_by_year_map,
    resolve_year_id_for_calendar_year_number,
)


def _gaes_tep_derive_template_context():
    """Контекст для расчёта удельных капвложений на карточке ГАЭС (как в таблице ТЭП)."""
    from app.common.services.get_services.years.years_get_services import get_year_list_full

    ty = get_ges_tep_current_price_year_number()
    coeff = get_tep_price_coefficient_by_year_map()
    coeff_json = {str(k): float(v) for k, v in coeff.items()}
    years_full = get_year_list_full()
    yid_to_num = {
        str(y.id): int(y.number) for y in years_full if y is not None and y.number is not None
    }
    ty_id = resolve_year_id_for_calendar_year_number(ty)
    return {
        "gaes_tep_target_price_year_display": str(ty) if ty is not None else "—",
        "gaes_tep_price_derive_config": {
            "targetYear": ty,
            "targetYearId": ty_id,
            "coeffByYear": coeff_json,
            "yearIdToNumber": yid_to_num,
        },
    }


def _gaes_tep_year_select_choices():
    from app.common.services.get_services.years.years_get_services import get_year_list_full

    years = get_year_list_full()
    return [("", "— не указано —")] + [(str(y.id), str(y.number)) for y in years]


def _gaes_tep_price_coeff_can_edit() -> bool:
    if not current_user.is_authenticated:
        return False
    edit_roles = ("admin", "generation-admin", "generation-editor")
    return any(role in current_user.role_names for role in edit_roles)


def _set_gaes_tep_year_choices(form):
    ch = _gaes_tep_year_select_choices()
    form.id_year_capital_cost_wo_pir_total.choices = ch
    form.id_year_capital_cost_wo_pir_ges_with_reservoir.choices = ch
    form.id_year_capital_cost_wo_pir_svm.choices = ch
    form.id_year_specific_semifixed_operating_costs.choices = ch


def _load_prospective_places_gaes_stations_and_filters():
    """Станции и контекст фильтров по request.args (список и страницы ТЭП)."""
    from app.generation.prospective_places.models import StationProspectivePlaceGAES, ProspectivePlaceGaesTepSource
    from app.refdata.models.energy_systems.regional_energy_system_model import (
        RegionalEnergySystem,
    )
    from app.generation.prospective_places.services.gaes.prospective_places_filters_gaes_services import (
        extract_prospective_places_filters,
        apply_prospective_places_gaes_filters,
        get_prospective_places_gaes_filter_context,
        apply_prospective_places_gaes_station_order,
    )

    filters = extract_prospective_places_filters(request.args)
    query = (
        StationProspectivePlaceGAES.query
        .options(
            joinedload(StationProspectivePlaceGAES.regional_district),
            joinedload(StationProspectivePlaceGAES.prospective_place_type_gaes),
            joinedload(StationProspectivePlaceGAES.regional_energy_system).joinedload(
                RegionalEnergySystem.union_energy_system
            ),
            joinedload(StationProspectivePlaceGAES.gaes_tep_source_indicators).joinedload(
                ProspectivePlaceGaesTepSource.prospective_place_type_gaes
            ),
            joinedload(StationProspectivePlaceGAES.gaes_tep_source_indicators).joinedload(
                ProspectivePlaceGaesTepSource.station_prospective_place_gaes
            ),
            joinedload(StationProspectivePlaceGAES.gaes_tep_source_indicators).joinedload(
                ProspectivePlaceGaesTepSource.year_capital_cost_wo_pir_total
            ),
            joinedload(StationProspectivePlaceGAES.gaes_tep_source_indicators).joinedload(
                ProspectivePlaceGaesTepSource.year_capital_cost_wo_pir_ges_with_reservoir
            ),
            joinedload(StationProspectivePlaceGAES.gaes_tep_source_indicators).joinedload(
                ProspectivePlaceGaesTepSource.year_capital_cost_wo_pir_svm
            ),
            joinedload(StationProspectivePlaceGAES.gaes_tep_source_indicators).joinedload(
                ProspectivePlaceGaesTepSource.year_specific_semifixed_operating_costs
            ),
            joinedload(StationProspectivePlaceGAES.gaes_tep_source_indicators).joinedload(
                ProspectivePlaceGaesTepSource.year_specific_capital_investment
            ),
        )
    )
    query = apply_prospective_places_gaes_station_order(query)
    query = apply_prospective_places_gaes_filters(query, filters)
    stations = query.all()
    for station in stations:
        sort_machines_by_station_block_number(station)
    filter_context = get_prospective_places_gaes_filter_context(filters)
    return stations, filters, filter_context


def _log_prospective_gaes_page_view(action_title: str) -> None:
    log_to_db(
        current_user,
        action_title,
        details=f"url={request.full_path}",
        entity_type="prospective_place_gaes",
    )


@prospective_places_bp.route("/gaes/")
@login_required
def prospective_places_gaes():
    """Характеристика актуальных площадок размещения новых ГАЭС."""
    stations, filters, filter_context = _load_prospective_places_gaes_stations_and_filters()
    gaes_place_type_groups = build_gaes_stations_grouped_by_place_type(stations)
    inject_gaes_planned_capacity_display_html(gaes_place_type_groups)
    _log_prospective_gaes_page_view("Открыта страница: перспективные площадки ГАЭС (список)")

    return render_template(
        "generation/prospective_places/gaes/prospective_places_gaes.html",
        stations=stations,
        gaes_place_type_groups=gaes_place_type_groups,
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
                "prospective_place_type_filter",
            ]
        ),
        **filter_context,
    )


@prospective_places_bp.route("/gaes/tep-main/")
@login_required
def prospective_places_gaes_tep_main():
    """Перечень исходных ТЭП по всем площадкам ГАЭС (как список, полная таблица)."""
    from app.generation.prospective_places.services.tep_capital_cost_current_year_services import (
        get_tep_main_radio_price_year_number,
        tep_main_rows_have_mixed_source_price_years,
    )
    from app.generation.prospective_places.services.gaes.prospective_places_gaes_tep_view_services import (
        build_tep_groups_by_station_place_type,
        collect_all_gaes_tep_rows,
    )

    stations, filters, filter_context = _load_prospective_places_gaes_stations_and_filters()
    gaes_place_type_groups = build_gaes_stations_grouped_by_place_type(stations)
    all_tep_rows = []
    for g in gaes_place_type_groups:
        all_tep_rows.extend(collect_all_gaes_tep_rows(g["stations"]))
    current_y = get_ges_tep_current_price_year_number()
    tep_price_label_year = get_tep_main_radio_price_year_number(
        all_tep_rows,
        current_target_year=current_y,
    )
    tep_main_force_source_only = tep_main_rows_have_mixed_source_price_years(all_tep_rows)
    tep_groups, _ = build_tep_groups_by_station_place_type(
        gaes_place_type_groups,
        tep_main_current_year_prices=True,
        tep_main_scaling_target_year=tep_price_label_year,
    )
    _log_prospective_gaes_page_view("Открыта страница: перспективные площадки ГАЭС (перечень ТЭП)")

    return render_template(
        "generation/prospective_places/gaes/prospective_places_gaes_tep.html",
        **filter_context,
        tep_groups=tep_groups,
        page_title="Перечень исходных ТЭП перспективных площадок ГАЭС",
        page_subtitle="",
        toolbar_mode="tep_main",
        tep_price_label_year=tep_price_label_year,
        tep_main_force_source_only=tep_main_force_source_only,
        ges_tep_price_coeff_can_edit=_gaes_tep_price_coeff_can_edit(),
        has_active_filters=any(
            filters.get(k)
            for k in [
                "energy_system_type_filter",
                "union_energy_system_filter",
                "regional_energy_system_filter",
                "federal_district_filter",
                "regional_district_filter",
                "site_name_filter",
                "prospective_place_type_filter",
            ]
        ),
    )


@prospective_places_bp.route("/gaes/tep-reserve/")
@login_required
def prospective_places_gaes_tep_reserve():
    """Старый URL: перечень ТЭП единый для всех площадок ГАЭС."""
    dest = url_for("prospective_places_bp.prospective_places_gaes_tep_main")
    qs = request.query_string.decode("utf-8")
    if qs:
        dest = f"{dest}?{qs}"
    return redirect(dest)


@prospective_places_bp.route("/gaes/<int:id>/", methods=["GET", "POST"])
@login_required
def prospective_place_gaes_details(id):
    """Карточка перспективной площадки ГАЭС (заполнение и редактирование полей)."""
    from app.generation.prospective_places.models import (
        StationProspectivePlaceGAES,
        ProspectivePlaceGaesTepSource,
        ProspectivePlaceTypeGAES,
    )
    from app.generation.prospective_places.forms import (
        ProspectivePlaceGAESEditForm,
        ProspectivePlaceGaesTepSourceEditForm,
    )
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
        StationProspectivePlaceGAES.query
        .options(
            joinedload(StationProspectivePlaceGAES.regional_district),
            joinedload(StationProspectivePlaceGAES.prospective_place_type_gaes),
            joinedload(StationProspectivePlaceGAES.regional_energy_system).joinedload(
                RegionalEnergySystem.union_energy_system
            ),
            joinedload(StationProspectivePlaceGAES.gaes_tep_source_indicators).joinedload(
                ProspectivePlaceGaesTepSource.prospective_place_type_gaes
            ),
            joinedload(StationProspectivePlaceGAES.gaes_tep_source_indicators).joinedload(
                ProspectivePlaceGaesTepSource.year_capital_cost_wo_pir_total
            ),
            joinedload(StationProspectivePlaceGAES.gaes_tep_source_indicators).joinedload(
                ProspectivePlaceGaesTepSource.year_capital_cost_wo_pir_ges_with_reservoir
            ),
            joinedload(StationProspectivePlaceGAES.gaes_tep_source_indicators).joinedload(
                ProspectivePlaceGaesTepSource.year_capital_cost_wo_pir_svm
            ),
            joinedload(StationProspectivePlaceGAES.gaes_tep_source_indicators).joinedload(
                ProspectivePlaceGaesTepSource.year_specific_semifixed_operating_costs
            ),
            joinedload(StationProspectivePlaceGAES.gaes_tep_source_indicators).joinedload(
                ProspectivePlaceGaesTepSource.year_specific_capital_investment
            ),
        )
        .get_or_404(id)
    )
    sort_machines_by_station_block_number(place)

    edit_roles = ["admin", "generation-admin", "generation-editor"]
    can_edit = current_user.is_authenticated and any(
        role in current_user.role_names for role in edit_roles
    )

    form = ProspectivePlaceGAESEditForm()
    rd_list = get_regional_district_list_full()
    form.id_regional_district.choices = [("", "— Не указано —")] + [
        (str(rd_id), name) for rd_id, name in rd_list
    ]
    res_list = get_regional_energy_system_choices()
    form.id_regional_energy_system.choices = [("", "— Не указано —")] + [
        (str(res_id), name) for res_id, name in res_list
    ]
    ppt_list = ProspectivePlaceTypeGAES.query.order_by(ProspectivePlaceTypeGAES.name).all()
    form.id_prospective_place_type_gaes.choices = [("", "— Не указано —")] + [
        (str(p.id), p.name) for p in ppt_list
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
        form.project_initiator.data = place.project_initiator
        form.water_body.data = place.water_body
        form.planned_capacity_mw.data = place.planned_capacity_mw
        form.general_scheme_commissioning_period.data = place.general_scheme_commissioning_period
        form.construction_period_years.data = place.construction_period_years
        form.id_prospective_place_type_gaes.data = place.id_prospective_place_type_gaes
        form.display_order.data = place.display_order

    tep_form_entries = []
    indicators = list(place.gaes_tep_source_indicators or [])
    _tep_idx = 0

    def _gaes_tep_form_factory():
        nonlocal _tep_idx
        pfx = f"tep_r{_tep_idx}" if can_edit else None
        _tep_idx += 1
        if pfx:
            return ProspectivePlaceGaesTepSourceEditForm(prefix=pfx), pfx
        return ProspectivePlaceGaesTepSourceEditForm(), None

    if not indicators:
        if can_edit:
            f, pfx = _gaes_tep_form_factory()
            _set_gaes_tep_year_choices(f)
            tep_form_entries.append(
                {
                    "form": f,
                    "form_prefix": pfx,
                    "machine_id": 0,
                }
            )
    else:
        for tr in indicators:
            f, pfx = _gaes_tep_form_factory()
            _set_gaes_tep_year_choices(f)
            if request.method == "GET" or not can_edit:
                _populate_gaes_tep_form_from_row(f, tr)
            tep_form_entries.append(
                {
                    "form": f,
                    "form_prefix": pfx,
                    "machine_id": tr.id,
                }
            )
        if can_edit and request.args.get("new_tep") == "1":
            f, pfx = _gaes_tep_form_factory()
            _set_gaes_tep_year_choices(f)
            tep_form_entries.append(
                {
                    "form": f,
                    "form_prefix": pfx,
                    "machine_id": 0,
                }
            )

    if request.method == "POST" and can_edit:
        place_ok = form.validate()
        tep_ok = [entry["form"].validate() for entry in tep_form_entries]
        if place_ok and all(tep_ok):
            try:
                place.site_name = (form.site_name.data or "").strip() or None
                place.id_regional_district = form.id_regional_district.data
                place.id_regional_energy_system = form.id_regional_energy_system.data
                place.geo_location = (form.geo_location.data or "").strip() or None
                place.project_initiator = (form.project_initiator.data or "").strip() or None
                place.water_body = (form.water_body.data or "").strip() or None
                place.planned_capacity_mw = form.planned_capacity_mw.data
                place.general_scheme_commissioning_period = (
                    (form.general_scheme_commissioning_period.data or "").strip() or None
                )
                place.construction_period_years = normalize_construction_period_years(
                    form.construction_period_years.data
                )
                place.id_prospective_place_type_gaes = form.id_prospective_place_type_gaes.data
                place.display_order = form.display_order.data
                for t in place.gaes_tep_source_indicators:
                    t.id_prospective_place_type_gaes = place.id_prospective_place_type_gaes

                for entry in tep_form_entries:
                    tform = entry["form"]
                    machine_id = entry["machine_id"]
                    if machine_id:
                        tep_row = ProspectivePlaceGaesTepSource.query.filter(
                            ProspectivePlaceGaesTepSource.id == machine_id,
                            ProspectivePlaceGaesTepSource.id_station_prospective_place_gaes
                            == place.id,
                        ).first()
                        if not tep_row:
                            raise ValueError("Запись перечня ТЭП не найдена (несогласованные данные).")
                    else:
                        tep_row = None
                    if machine_id and tep_row is not None:
                        _apply_gaes_tep_form_to_row(tep_row, tform, place)
                    else:
                        tep_new = ProspectivePlaceGaesTepSource(
                            id_station_prospective_place_gaes=place.id,
                        )
                        _apply_gaes_tep_form_to_row(tep_new, tform, place)
                        db.session.add(tep_new)

                db.session.commit()
                log_to_db(
                    current_user,
                    "Изменена перспективная площадка ГАЭС (карточка и перечень ТЭП)",
                    details=f"id={place.id}; site_name={place.site_name!r}",
                    entity_type="prospective_place_gaes",
                    entity_id=place.id,
                )
                flash("Перспективная площадка и перечень ТЭП успешно сохранены.", "success")
                return redirect(url_for("prospective_places_bp.prospective_place_gaes_details", id=place.id))
            except Exception as e:
                db.session.rollback()
                flash(f"Ошибка при сохранении: {str(e)}", "danger")
        else:
            flash("Исправьте ошибки в полях и повторите сохранение.", "danger")

    ctx = _gaes_tep_derive_template_context()
    return render_template(
        "generation/prospective_places/gaes/prospective_place_gaes_details.html",
        place=place,
        form=form,
        can_edit=can_edit,
        res_auto_map=res_auto_map,
        tep_form_entries=tep_form_entries,
        **ctx,
    )


def _populate_gaes_tep_form_from_row(form, tep_row):
    """Заполняет ProspectivePlaceGaesTepSourceEditForm из ProspectivePlaceGaesTepSource."""
    if not tep_row:
        return
    form.installed_capacity_mw_generator_mode.data = tep_row.installed_capacity_mw_generator_mode
    form.startup_complex_capacity_mw_generator_mode.data = tep_row.startup_complex_capacity_mw_generator_mode
    form.stage_1_capacity_mw_generator_mode.data = tep_row.stage_1_capacity_mw_generator_mode
    form.stage_2_capacity_mw_generator_mode.data = tep_row.stage_2_capacity_mw_generator_mode
    form.unit_capacity_mw_generator_mode.data = tep_row.unit_capacity_mw_generator_mode
    form.installed_capacity_mw_pump_mode.data = tep_row.installed_capacity_mw_pump_mode
    form.startup_complex_capacity_mw_pump_mode.data = tep_row.startup_complex_capacity_mw_pump_mode
    form.stage_1_capacity_mw_pump_mode.data = tep_row.stage_1_capacity_mw_pump_mode
    form.stage_2_capacity_mw_pump_mode.data = tep_row.stage_2_capacity_mw_pump_mode
    form.unit_capacity_mw_pump_mode.data = tep_row.unit_capacity_mw_pump_mode
    form.units_count.data = tep_row.units_count
    form.hydro_turbine_type.data = tep_row.hydro_turbine_type
    form.ccium_turbine_mode.data = (
        tep_row.ccium_turbine_mode
    )
    form.ccium_pump_mode.data = (
        tep_row.ccium_pump_mode
    )
    form.construction_period_years.data = tep_row.construction_period_years
    form.construction_increment_year_01_mw.data = tep_row.construction_increment_year_01_mw
    form.construction_increment_year_02_mw.data = tep_row.construction_increment_year_02_mw
    form.construction_increment_year_03_mw.data = tep_row.construction_increment_year_03_mw
    form.construction_increment_year_04_mw.data = tep_row.construction_increment_year_04_mw
    form.construction_increment_year_05_mw.data = tep_row.construction_increment_year_05_mw
    form.construction_increment_year_06_mw.data = tep_row.construction_increment_year_06_mw
    form.construction_increment_year_07_mw.data = tep_row.construction_increment_year_07_mw
    form.construction_increment_year_08_mw.data = tep_row.construction_increment_year_08_mw
    form.construction_increment_year_09_mw.data = tep_row.construction_increment_year_09_mw
    form.construction_increment_year_10_mw.data = tep_row.construction_increment_year_10_mw
    form.construction_increment_year_11_mw.data = tep_row.construction_increment_year_11_mw
    form.construction_increment_year_12_mw.data = tep_row.construction_increment_year_12_mw
    form.capital_cost_wo_pir_total_million_rub.data = decimal_for_form_strip_trailing_zeros(
        tep_row.capital_cost_wo_pir_total_million_rub
    )
    form.id_year_capital_cost_wo_pir_total.data = tep_row.id_year_capital_cost_wo_pir_total
    form.capital_cost_wo_pir_ges_with_reservoir_million_rub.data = (
        decimal_for_form_strip_trailing_zeros(
            tep_row.capital_cost_wo_pir_ges_with_reservoir_million_rub
        )
    )
    form.id_year_capital_cost_wo_pir_ges_with_reservoir.data = (
        tep_row.id_year_capital_cost_wo_pir_ges_with_reservoir
    )
    form.capital_cost_wo_pir_svm_million_rub.data = decimal_for_form_strip_trailing_zeros(
        tep_row.capital_cost_wo_pir_svm_million_rub
    )
    form.id_year_capital_cost_wo_pir_svm.data = tep_row.id_year_capital_cost_wo_pir_svm
    form.specific_semifixed_operating_costs_thous_rub_per_kw.data = (
        tep_row.specific_semifixed_operating_costs_thous_rub_per_kw
    )
    form.id_year_specific_semifixed_operating_costs.data = (
        tep_row.id_year_specific_semifixed_operating_costs
    )
    form.generation_average_multiyear_billion_kwh.data = tep_row.generation_average_multiyear_billion_kwh
    form.generation_average_multiyear_million_kwh_stage_1.data = (
        tep_row.generation_average_multiyear_million_kwh_stage_1
    )
    form.generation_average_multiyear_million_kwh_stage_2.data = (
        tep_row.generation_average_multiyear_million_kwh_stage_2
    )
    form.generation_medium_water_50pct_billion_kwh.data = tep_row.generation_medium_water_50pct_billion_kwh
    form.generation_low_water_95pct_billion_kwh.data = tep_row.generation_low_water_95pct_billion_kwh
    form.annual_charging_electricity_consumption_million_kwh.data = (
        tep_row.annual_charging_electricity_consumption_million_kwh
    )
    form.annual_charging_electricity_consumption_million_kwh_stage_1.data = (
        tep_row.annual_charging_electricity_consumption_million_kwh_stage_1
    )
    form.annual_charging_electricity_consumption_million_kwh_stage_2.data = (
        tep_row.annual_charging_electricity_consumption_million_kwh_stage_2
    )
    form.note.data = tep_row.note
    coeff = get_tep_price_coefficient_by_year_map()
    ty = get_ges_tep_current_price_year_number()
    s_derived = fmt_specific_capital_investment_thous_rub_per_kw_derived(
        tep_row,
        installed_capacity_attr="installed_capacity_mw_generator_mode",
        target_year=ty,
        coeff_by_year=coeff,
    )
    form.specific_capital_investment_thous_rub_per_kw.data = None if s_derived == "—" else s_derived
    form.id_year_specific_capital_investment.data = tep_row.id_year_capital_cost_wo_pir_ges_with_reservoir


def _planned_capacity_mw_int_from_installed_str(value) -> int | None:
    """Целое МВт для поля площадки из строки «Установленная мощность в генераторном режиме» (ТЭП)."""
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    s = s.replace("\u00a0", "").replace(" ", "").replace(",", ".")
    try:
        return int(round(float(s)))
    except (ValueError, TypeError, OverflowError):
        return None


def _apply_gaes_tep_form_to_row(row, form, place):
    """Заполняет ProspectivePlaceGaesTepSource из ProspectivePlaceGaesTepSourceEditForm.

    Тип площадки задается на карточке площадки; при сохранении ТЭП копируется с площадки.
    """
    def _s(val):
        return (val or "").strip() or None

    row.id_prospective_place_type_gaes = place.id_prospective_place_type_gaes
    row.installed_capacity_mw_generator_mode = _s(form.installed_capacity_mw_generator_mode.data)
    row.startup_complex_capacity_mw_generator_mode = _s(form.startup_complex_capacity_mw_generator_mode.data)
    row.stage_1_capacity_mw_generator_mode = _s(form.stage_1_capacity_mw_generator_mode.data)
    row.stage_2_capacity_mw_generator_mode = _s(form.stage_2_capacity_mw_generator_mode.data)
    row.unit_capacity_mw_generator_mode = _s(form.unit_capacity_mw_generator_mode.data)
    row.installed_capacity_mw_pump_mode = _s(form.installed_capacity_mw_pump_mode.data)
    row.startup_complex_capacity_mw_pump_mode = _s(form.startup_complex_capacity_mw_pump_mode.data)
    row.stage_1_capacity_mw_pump_mode = _s(form.stage_1_capacity_mw_pump_mode.data)
    row.stage_2_capacity_mw_pump_mode = _s(form.stage_2_capacity_mw_pump_mode.data)
    row.unit_capacity_mw_pump_mode = _s(form.unit_capacity_mw_pump_mode.data)
    row.units_count = form.units_count.data
    row.hydro_turbine_type = _s(form.hydro_turbine_type.data)
    row.ccium_turbine_mode = _s(
        form.ccium_turbine_mode.data
    )
    row.ccium_pump_mode = _s(
        form.ccium_pump_mode.data
    )
    row.construction_period_years = normalize_construction_period_years(
        form.construction_period_years.data
    )
    row.construction_increment_year_01_mw = _s(form.construction_increment_year_01_mw.data)
    row.construction_increment_year_02_mw = _s(form.construction_increment_year_02_mw.data)
    row.construction_increment_year_03_mw = _s(form.construction_increment_year_03_mw.data)
    row.construction_increment_year_04_mw = _s(form.construction_increment_year_04_mw.data)
    row.construction_increment_year_05_mw = _s(form.construction_increment_year_05_mw.data)
    row.construction_increment_year_06_mw = _s(form.construction_increment_year_06_mw.data)
    row.construction_increment_year_07_mw = _s(form.construction_increment_year_07_mw.data)
    row.construction_increment_year_08_mw = _s(form.construction_increment_year_08_mw.data)
    row.construction_increment_year_09_mw = _s(form.construction_increment_year_09_mw.data)
    row.construction_increment_year_10_mw = _s(form.construction_increment_year_10_mw.data)
    row.construction_increment_year_11_mw = _s(form.construction_increment_year_11_mw.data)
    row.construction_increment_year_12_mw = _s(form.construction_increment_year_12_mw.data)
    row.capital_cost_wo_pir_total_million_rub = form.capital_cost_wo_pir_total_million_rub.data
    row.id_year_capital_cost_wo_pir_total = form.id_year_capital_cost_wo_pir_total.data
    row.capital_cost_wo_pir_ges_with_reservoir_million_rub = (
        form.capital_cost_wo_pir_ges_with_reservoir_million_rub.data
    )
    row.id_year_capital_cost_wo_pir_ges_with_reservoir = (
        form.id_year_capital_cost_wo_pir_ges_with_reservoir.data
    )
    row.capital_cost_wo_pir_svm_million_rub = form.capital_cost_wo_pir_svm_million_rub.data
    row.id_year_capital_cost_wo_pir_svm = form.id_year_capital_cost_wo_pir_svm.data
    row.specific_semifixed_operating_costs_thous_rub_per_kw = _s(
        form.specific_semifixed_operating_costs_thous_rub_per_kw.data
    )
    row.id_year_specific_semifixed_operating_costs = (
        form.id_year_specific_semifixed_operating_costs.data
    )
    row.generation_average_multiyear_billion_kwh = _s(form.generation_average_multiyear_billion_kwh.data)
    row.generation_average_multiyear_million_kwh_stage_1 = _s(
        form.generation_average_multiyear_million_kwh_stage_1.data
    )
    row.generation_average_multiyear_million_kwh_stage_2 = _s(
        form.generation_average_multiyear_million_kwh_stage_2.data
    )
    row.generation_medium_water_50pct_billion_kwh = _s(form.generation_medium_water_50pct_billion_kwh.data)
    row.generation_low_water_95pct_billion_kwh = _s(form.generation_low_water_95pct_billion_kwh.data)
    row.annual_charging_electricity_consumption_million_kwh = _s(
        form.annual_charging_electricity_consumption_million_kwh.data
    )
    row.annual_charging_electricity_consumption_million_kwh_stage_1 = _s(
        form.annual_charging_electricity_consumption_million_kwh_stage_1.data
    )
    row.annual_charging_electricity_consumption_million_kwh_stage_2 = _s(
        form.annual_charging_electricity_consumption_million_kwh_stage_2.data
    )
    apply_derived_specific_capital_investment_to_gaes_tep_source_row(row)
    row.note = _s(form.note.data)
    place.planned_capacity_mw = _planned_capacity_mw_int_from_installed_str(
        row.installed_capacity_mw_generator_mode
    )


@prospective_places_bp.route("/gaes/<int:place_id>/machine/<int:machine_id>/", methods=["GET", "POST"])
@login_required
def machine_prospective_place_gaes_details(place_id, machine_id):
    """Добавление/редактирование записи перечня ТЭП (machine_id=0 — добавить)."""
    from app.generation.prospective_places.models import (
        StationProspectivePlaceGAES,
        ProspectivePlaceGaesTepSource,
    )
    from app.generation.prospective_places.forms import ProspectivePlaceGaesTepSourceEditForm

    edit_roles = ["admin", "generation-admin", "generation-editor"]
    can_edit = current_user.is_authenticated and any(
        role in current_user.role_names for role in edit_roles
    )
    if not can_edit:
        flash("Недостаточно прав для редактирования записи перечня ТЭП.", "warning")
        return redirect(url_for("prospective_places_bp.prospective_place_gaes_details", id=place_id))

    place = StationProspectivePlaceGAES.query.get_or_404(place_id)
    tep_row = ProspectivePlaceGaesTepSource.query.filter(
        ProspectivePlaceGaesTepSource.id == machine_id,
        ProspectivePlaceGaesTepSource.id_station_prospective_place_gaes == place_id,
    ).first() if machine_id else None

    if machine_id and not tep_row:
        flash("Запись перечня ТЭП не найдена.", "danger")
        return redirect(url_for("prospective_places_bp.prospective_place_gaes_details", id=place_id))

    if request.method == "GET":
        return redirect(url_for("prospective_places_bp.prospective_place_gaes_details", id=place_id))

    form = ProspectivePlaceGaesTepSourceEditForm()
    _set_gaes_tep_year_choices(form)

    if form.validate_on_submit() and can_edit:
        try:
            is_new_tep = tep_row is None
            if tep_row:
                _apply_gaes_tep_form_to_row(tep_row, form, place)
            else:
                tep_row = ProspectivePlaceGaesTepSource(
                    id_station_prospective_place_gaes=place_id,
                )
                _apply_gaes_tep_form_to_row(tep_row, form, place)
                db.session.add(tep_row)
            db.session.commit()
            log_to_db(
                current_user,
                "Создана позиция перечня ТЭП (ГАЭС)" if is_new_tep else "Изменена позиция перечня ТЭП (ГАЭС)",
                details=(
                    f"id_tep={tep_row.id}; id_place={place_id}; site_name={place.site_name!r}"
                ),
                entity_type="gaes_tep_source",
                entity_id=tep_row.id,
            )
            flash("Запись перечня ТЭП успешно сохранена.", "success")
            return redirect(url_for("prospective_places_bp.prospective_place_gaes_details", id=place_id))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при сохранении: {str(e)}", "danger")

    ctx = _gaes_tep_derive_template_context()
    return render_template(
        "generation/prospective_places/gaes/machine_prospective_place_gaes_details.html",
        place=place,
        tep_row=tep_row,
        form=form,
        **ctx,
    )


@prospective_places_bp.route("/gaes/add/", methods=["GET", "POST"])
@login_required
def add_prospective_place_gaes():
    """Добавление новой перспективной площадки ГАЭС."""
    edit_roles = ["admin", "generation-admin", "generation-editor"]
    can_edit = current_user.is_authenticated and any(
        role in current_user.role_names for role in edit_roles
    )
    if not can_edit:
        flash("Недостаточно прав для добавления перспективной площадки.", "warning")
        return redirect(url_for("prospective_places_bp.prospective_places_gaes"))

    from app.generation.prospective_places.forms import ProspectivePlaceGAESAddForm
    from app.generation.prospective_places.models import StationProspectivePlaceGAES
    from app.common.services.get_services.territories.regional_district_get_services import (
        get_regional_district_list_full,
    )

    form = ProspectivePlaceGAESAddForm()
    rd_list = get_regional_district_list_full()
    form.id_regional_district.choices = [("", "— Выберите субъект РФ —")] + [
        (str(rd_id), name) for rd_id, name in rd_list
    ]

    if form.validate_on_submit():
        site_name = (form.site_name.data or "").strip()
        id_regional_district = form.id_regional_district.data

        # Проверка уникальности по (site_name, id_regional_district)
        q = StationProspectivePlaceGAES.query
        if site_name:
            q = q.filter(StationProspectivePlaceGAES.site_name == site_name)
        else:
            q = q.filter(
                db.or_(
                    StationProspectivePlaceGAES.site_name.is_(None),
                    StationProspectivePlaceGAES.site_name == "",
                )
            )
        if id_regional_district is not None:
            q = q.filter(
                StationProspectivePlaceGAES.id_regional_district == id_regional_district
            )
        else:
            q = q.filter(StationProspectivePlaceGAES.id_regional_district.is_(None))

        if q.first():
            flash(
                "Перспективная площадка с таким наименованием и субъектом РФ уже существует.",
                "danger",
            )
            return render_template(
                "generation/prospective_places/gaes/prospective_place_gaes_add.html",
                form=form,
            )

        try:
            place = StationProspectivePlaceGAES(
                site_name=site_name or None,
                id_regional_district=id_regional_district,
            )
            db.session.add(place)
            db.session.commit()
            log_to_db(
                current_user,
                "Создана перспективная площадка ГАЭС",
                details=f"id={place.id}; site_name={place.site_name!r}",
                entity_type="prospective_place_gaes",
                entity_id=place.id,
            )
            flash("Перспективная площадка успешно создана.", "success")
            return redirect(url_for("prospective_places_bp.prospective_places_gaes"))
        except Exception as e:
            db.session.rollback()
            flash(f"Ошибка при создании: {str(e)}", "danger")

    return render_template(
        "generation/prospective_places/gaes/prospective_place_gaes_add.html",
        form=form,
    )


@prospective_places_bp.route("/gaes/export/", methods=["GET"])
@login_required
@no_compress
def export_prospective_places_gaes():
    """Экспорт списка ГАЭС: те же группы, строки и 12 колонок, что на /gaes/ (без дополнительных листов)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
    from openpyxl.utils import get_column_letter

    stations, _filters, _fc = _load_prospective_places_gaes_stations_and_filters()

    if request.args.get("export_mode") == "tep_main":
        from app.common.services.get_services.years.years_get_services import (
            get_ges_tep_current_price_year_number,
        )
        from app.generation.prospective_places.services.tep_capital_cost_current_year_services import (
            get_tep_main_radio_price_year_number,
        )
        from app.generation.prospective_places.services.gaes.export_prospective_places_gaes_tep_main_excel import (
            write_tep_main_screen_sheet,
        )
        from app.generation.prospective_places.services.gaes.prospective_places_gaes_tep_view_services import (
            build_tep_groups_by_station_place_type,
            collect_all_gaes_tep_rows,
        )

        source_prices = request.args.get("tep_main_view") == "source"
        gaes_place_type_groups = build_gaes_stations_grouped_by_place_type(stations)
        all_tep_rows = []
        for g in gaes_place_type_groups:
            all_tep_rows.extend(collect_all_gaes_tep_rows(g["stations"]))
        current_y = get_ges_tep_current_price_year_number()
        tep_price_label_year = get_tep_main_radio_price_year_number(
            all_tep_rows,
            current_target_year=current_y,
        )
        tep_groups, _ = build_tep_groups_by_station_place_type(
            gaes_place_type_groups,
            tep_main_current_year_prices=not source_prices,
            tep_main_scaling_target_year=tep_price_label_year if not source_prices else None,
        )
        wb = Workbook()
        ws = wb.active
        ws.title = "Перечень ТЭП перспективных площадок ГАЭС"
        write_tep_main_screen_sheet(ws, tep_groups, source_prices=source_prices)
        output = BytesIO()
        wb.save(output)
        output.seek(0)
        filename = (
            f"gaes_tep_main_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
        )
        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=filename,
        )

    gaes_place_type_groups = build_gaes_stations_grouped_by_place_type(stations)

    def _planned_capacity_cell(station):
        return format_gaes_planned_capacity_display(station, line_break="\n") or "—"

    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    header_fill = PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid")
    header_font = Font(bold=True)
    group_font = Font(bold=True, size=12)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    total_cols = 11
    headers = [
        "№ п/п",
        "Наименование площадки",
        "Инициатор проекта",
        "Планируемая установленная генерирующая мощность ГАЭС, МВт",
        "Годовая выработка электрической энергии ГАЭС, млн кВтч",
        "Объединенная энергосистема (ОЭС)",
        "Субъект Российской Федерации",
        "Водный объект",
        (
            "Географическое расположение площадки "
            "(кадастровый номер земельного участка или координаты)"
        ),
        (
            "Генеральная схема до 2042 года (Период ввода в эксплуатацию).\n"
            "Распоряжение Правительства от 30.12.2024 №4153-р"
        ),
        (
            "Срок строительства по Протоколу Минэнерго от 25.05.2022 №РГ/07-0003пр "
            "(без учета срока выполнения ПИР- 2 года), лет"
        ),
    ]

    def _ues_name(s):
        return (
            s.regional_energy_system.union_energy_system.name
            if s.regional_energy_system and s.regional_energy_system.union_energy_system
            else None
        ) or "—"

    def _rd_name(s):
        return (s.regional_district.name_full if s.regional_district else None) or "—"

    def _fmt_multiyear_generation(val):
        if val is None or val == "":
            return "—"
        return str(val).replace(".", ",")

    wb = Workbook()
    ws = wb.active
    ws.title = "Характеристика актуальных площадок размещения новых ГАЭС"

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border

    row_num = 2
    idx = 0

    if not gaes_place_type_groups:
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=total_cols)
        c = ws.cell(row=row_num, column=1, value="Нет данных")
        c.alignment = center_align
        c.border = thin_border
        c.font = Font(italic=True, color="808080")
    else:
        for group in gaes_place_type_groups:
            ws.merge_cells(
                start_row=row_num, start_column=1, end_row=row_num, end_column=total_cols
            )
            gc = ws.cell(row=row_num, column=1, value=group["type_label"])
            gc.font = group_font
            gc.alignment = center_align
            gc.border = thin_border
            row_num += 1

            for station in group["stations"]:
                idx += 1
                ues = _ues_name(station)
                rd = _rd_name(station)
                site = station.site_name or "—"
                initiator = station.project_initiator or "—"
                water = station.water_body or "—"
                geo = station.geo_location or "—"
                planned = _planned_capacity_cell(station)
                gen_scheme = station.general_scheme_commissioning_period or "—"
                constr = format_construction_period_years_display(
                    station.construction_period_years
                ) or "—"

                indicators = station.gaes_tep_source_indicators or []
                if indicators:
                    first_row = row_num
                    for loop_idx, tr in enumerate(indicators):
                        gen_mw = _fmt_multiyear_generation(
                            tr.generation_average_multiyear_billion_kwh
                        )
                        if loop_idx == 0:
                            ws.cell(row=row_num, column=1, value=idx).border = thin_border
                            ws.cell(row=row_num, column=1).alignment = center_align
                            ws.cell(row=row_num, column=2, value=site).border = thin_border
                            ws.cell(row=row_num, column=2).alignment = center_align
                            ws.cell(row=row_num, column=3, value=initiator).border = thin_border
                            ws.cell(row=row_num, column=3).alignment = center_align
                            ws.cell(row=row_num, column=4, value=planned).border = thin_border
                            ws.cell(row=row_num, column=4).alignment = center_align
                        ws.cell(row=row_num, column=5, value=gen_mw).border = thin_border
                        ws.cell(row=row_num, column=5).alignment = center_align
                        if loop_idx == 0:
                            ws.cell(row=row_num, column=6, value=ues).border = thin_border
                            ws.cell(row=row_num, column=6).alignment = center_align
                            ws.cell(row=row_num, column=7, value=rd).border = thin_border
                            ws.cell(row=row_num, column=7).alignment = center_align
                            ws.cell(row=row_num, column=8, value=water).border = thin_border
                            ws.cell(row=row_num, column=8).alignment = center_align
                            ws.cell(row=row_num, column=9, value=geo).border = thin_border
                            ws.cell(row=row_num, column=9).alignment = center_align
                            ws.cell(row=row_num, column=10, value=gen_scheme).border = thin_border
                            ws.cell(row=row_num, column=10).alignment = center_align
                            ws.cell(row=row_num, column=11, value=constr).border = thin_border
                            ws.cell(row=row_num, column=11).alignment = center_align
                        row_num += 1
                    last_row = row_num - 1
                    if last_row > first_row:
                        for c in range(1, 5):
                            ws.merge_cells(
                                start_row=first_row,
                                start_column=c,
                                end_row=last_row,
                                end_column=c,
                            )
                        for c in range(6, 10):
                            ws.merge_cells(
                                start_row=first_row,
                                start_column=c,
                                end_row=last_row,
                                end_column=c,
                            )
                        ws.merge_cells(
                            start_row=first_row,
                            start_column=10,
                            end_row=last_row,
                            end_column=10,
                        )
                        ws.merge_cells(
                            start_row=first_row,
                            start_column=11,
                            end_row=last_row,
                            end_column=11,
                        )
                else:
                    ws.cell(row=row_num, column=1, value=idx).border = thin_border
                    ws.cell(row=row_num, column=1).alignment = center_align
                    ws.cell(row=row_num, column=2, value=site).border = thin_border
                    ws.cell(row=row_num, column=2).alignment = center_align
                    ws.cell(row=row_num, column=3, value=initiator).border = thin_border
                    ws.cell(row=row_num, column=3).alignment = center_align
                    ws.cell(row=row_num, column=4, value=planned).border = thin_border
                    ws.cell(row=row_num, column=4).alignment = center_align
                    em2 = ws.cell(row=row_num, column=5, value="—")
                    em2.border = thin_border
                    em2.alignment = center_align
                    em2.font = Font(color="808080")
                    ws.cell(row=row_num, column=6, value=ues).border = thin_border
                    ws.cell(row=row_num, column=6).alignment = center_align
                    ws.cell(row=row_num, column=7, value=rd).border = thin_border
                    ws.cell(row=row_num, column=7).alignment = center_align
                    ws.cell(row=row_num, column=8, value=water).border = thin_border
                    ws.cell(row=row_num, column=8).alignment = center_align
                    ws.cell(row=row_num, column=9, value=geo).border = thin_border
                    ws.cell(row=row_num, column=9).alignment = center_align
                    ws.cell(row=row_num, column=10, value=gen_scheme).border = thin_border
                    ws.cell(row=row_num, column=10).alignment = center_align
                    ws.cell(row=row_num, column=11, value=constr).border = thin_border
                    ws.cell(row=row_num, column=11).alignment = center_align
                    row_num += 1

    widths = [6, 22, 16, 20, 16, 18, 22, 14, 22, 18, 14]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"prospective_places_gaes_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )

