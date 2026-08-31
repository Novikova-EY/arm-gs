from app.generation.routes.stations import station_bp
from app.extensions import db
from config import Config
from flask import (
    render_template, request, redirect, url_for, flash, session, current_app, send_file, jsonify, abort, make_response
)
import time
from functools import lru_cache
from collections import defaultdict
from typing import Optional
from app.logs.services.logging_service import log_to_db
from flask_login import login_required, current_user
from flask import session
from app.generation.forms.station_forms import StationFilterForm
from app.generation.forms.machine_forms import MachineFilterSmallForm
from app.generation.models.station.station_constants import STATION_SIGN_UNSPECIFIED
from app.generation.models.station.station_model import Station
from app.generation.models.station.station_group_model import StationGroup
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_tes_type_model import MachineTesType
from app.generation.models.station.station_gaes_charge_consumption_model import (
    StationGaesChargeConsumption,
)
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.machine.machine_fuel_model import MachineFuel
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.generation.models.pgu_machine.pgu_machine_power_model import PGUMachinePower
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.common.services.choices_cache_service import choices_cache
from app.refdata.models.refdata_for_stations.condition_type_model import ConditionType
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.gen_companies.gen_company_model import GenCompany
from app.refdata.models.fuels.fuel_model import Fuel
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy import or_, and_
from app.logs.models.log_model import Log
from datetime import timezone
from zoneinfo import ZoneInfo
from app.common.services.database_version_filter import (
    filter_by_db_version,
    filter_by_explicit_db_version,
    get_current_db_version_id,
)

MOSCOW = ZoneInfo("Europe/Moscow")


def _is_gaes_station(station: Station) -> bool:
    try:
        st = station.station_type
        if not st or not st.name:
            return False
        return st.name.strip().lower() == "гаэс"
    except Exception:
        return False


def _save_station_meta_from_form(
    user,
    station: Station,
    form,
    regional_district_list,
    *,
    can_edit: bool,
    can_edit_fuel: bool,
    can_edit_fuel_dz: bool = False,
):
    """Сохраняет поля карточки станции с учётом раздельных прав (генерация / топливо)."""
    can_edit_external_code = current_user.is_authenticated and getattr(current_user, "is_admin", False)

    if can_edit_fuel_dz and not can_edit:
        form.process(formdata=request.form)
        if not form.validate():
            print("Ошибки в form (station meta fuel dz):", form.errors)
            return []
        return update_station_from_form_service(
            user,
            station,
            form,
            regional_district_list,
            can_edit_generation=False,
            can_edit_fuel=True,
            can_edit_fuel_dz=True,
        )

    if can_edit_fuel and not can_edit:
        if "station_sign" not in request.form and not (
            can_edit_external_code
            and ("external_code" in request.form or "kto" in request.form)
        ):
            return []
        form.process(formdata=request.form)
        return update_station_from_form_service(
            user,
            station,
            form,
            regional_district_list,
            can_edit_generation=False,
            can_edit_fuel=True,
        )

    if not can_edit:
        return []

    form.process(formdata=request.form)
    if not form.validate():
        print("Ошибки в form (station meta):", form.errors)
        return []
    return update_station_from_form_service(
        user,
        station,
        form,
        regional_district_list,
        can_edit_generation=True,
        can_edit_fuel=can_edit_fuel,
    )


_ALLOWED_STATION_ROUNDINGS = frozenset({-1, 0, 1, 2, 3})


def _station_rounding_from_args(param: str):
    raw = request.args.get(param)
    if raw is None or raw == "":
        return None
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return None
    return v if v in _ALLOWED_STATION_ROUNDINGS else None


def get_station_details_rounding_triplet() -> tuple[int, int, int]:
    """Округление для агрегатов, выработки и потребления ГАЭС (независимые query-параметры)."""
    rd_main = _station_rounding_from_args("rounding_digits")
    if rd_main is None:
        rd_main = 1

    rd_gen = _station_rounding_from_args("rounding_digits_gen")
    if rd_gen is None:
        rd_gen = _station_rounding_from_args("rounding_digits")
    if rd_gen is None:
        rd_gen = rd_main

    rd_gaes = _station_rounding_from_args("rounding_digits_gaes")
    if rd_gaes is None:
        rd_gaes = _station_rounding_from_args("rounding_digits")
    if rd_gaes is None:
        rd_gaes = rd_main

    return rd_main, rd_gen, rd_gaes


def _rounding_for_station_energy_fragment(primary_param: str) -> int:
    """AJAX «выработка» / «ГАЭС заряд»: primary_param или legacy rounding_digits."""
    v = _station_rounding_from_args(primary_param)
    if v is not None:
        return v
    v = _station_rounding_from_args("rounding_digits")
    if v is not None:
        return v
    return 1


from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
    get_energy_system_type_list_full,
    get_energy_system_type_map,
)
from app.common.services.get_services.energy_systems.energy_unit_get_services import (
    get_energy_unit_list_full,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_list_full,
    get_union_energy_systems_map,
    get_ues_to_res_ids_map,
)
from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
    get_regional_energy_system_choices,
    get_regional_energy_systems_map,
    get_res_to_ues_id_map,
    get_res_to_est_id_map,
)
from app.common.services.get_services.territories.regional_district_get_services import (
    get_regional_district_list_full,
    get_rd_to_fd_id_map,
)
from app.common.services.get_services.territories.federal_district_get_services import (
    get_federal_district_list_full,
    get_fd_to_rd_ids_map,
)
from app.common.services.get_services.stations.station_group_get_services import (
    get_station_group_list_full,
)
from app.common.services.get_services.stations.condition_type_get_services import (
    get_condition_type_list_full,
)
from app.common.services.get_services.years.years_get_services import (
    get_current_year,
    get_filter_start_year,
    get_filter_end_year,
    get_year_feature_dict,
    get_year_list_full,
)
from app.generation.services.station_services.station_power_aggregation import (
    load_station_powers_by_year,
    aggregate_powers_from_machine_power_rows,
)
from app.generation.services.station_services.station_services import (
    get_stations_list,
    get_station_by_id, 
    assign_machine_powers_by_year, 
    get_station_list_template_context, 
    get_current_machine_tes_types_map, 
    update_station_from_form_service,
    delete_machines_service,
    update_machines_from_form_service,
    save_station_energy_generation_service,
    station_annual_energy_by_year,
    save_station_gaes_charge_consumption_service,
    _apply_machine_display_names,
    _apply_machine_gen_companies_for_version,
    get_gen_company_choices_for_version,
)
from app.generation.services.station_services.station_access_services import (
    can_fuel_user_add_machine_to_station,
    can_fuel_user_edit_decentralized_station_details,
    get_decentralized_zone_energy_system_type_name,
    is_decentralized_zone_station,
)
from app.generation.services.station_services.groupped_services import (
    machine_year_then_number_sort_key,
)
from app.generation.services.station_services.import_station_services import (
    import_station_list_from_excel, 
    import_fuel_tes_station_from_excel, 
)
from app.common.services.cache_services import CacheService
from app.common.middleware import handle_stale_data
from app.common.services.cache_decorator import invalidate_cache, invalidate_cache_pattern
from app.refdata.routes.refdata_all_versions_guard import (
    block_all_versions_without_admin,
)
from app.generation.services.machine_services.machine_all_versions_services import (
    update_station_machines_all_versions_from_form,
)


def _handle_station_machines_all_versions_save(
    user,
    station: Station,
    *,
    start_year: int,
    end_year: int,
    is_gaes_station: bool,
) -> bool:
    """
    Синхронизация кода КТО, выработки (и заряда ГАЭС для станций ГАЭС)
    station_details во всех версиях БД.
    Возвращает True, если запрос был с all_versions=1 (вызвавший обработку или отказ).
    """
    if request.values.get("all_versions") != "1":
        return False

    if block_all_versions_without_admin(current_user):
        return True

    if request.values.get("all_versions_confirm") != "1":
        flash(
            "Сохранение во всех версиях БД отменено: не пройдено подтверждение.",
            "warning",
        )
        log_to_db(
            user,
            "Отклонено сохранение station_details во всех версиях БД: "
            "отсутствует подтверждение all_versions_confirm",
            entity_type="station",
            entity_id=station.id,
        )
        return True

    sync_station_general_info = False
    sync_station_kto = True
    sync_station_energy = True
    sync_station_gaes_charge = bool(is_gaes_station)

    request_meta = {
        "path": request.path,
        "query": (request.query_string.decode("utf-8", errors="replace")[:500] if request.query_string else ""),
        "remote_addr": request.remote_addr,
        "user_agent": (request.headers.get("User-Agent") or "")[:300],
    }
    try:
        result = update_station_machines_all_versions_from_form(
            user=user,
            station=station,
            form_data=request.form,
            start_year=start_year,
            end_year=end_year,
            sync_station_energy=sync_station_energy,
            sync_station_gaes_charge=sync_station_gaes_charge,
            sync_station_general_info=sync_station_general_info,
            sync_station_kto=sync_station_kto,
            sync_machines=False,
            request_meta=request_meta,
        )
        vt = result.get("versions_touched", 0)
        ue = result.get("updated_energy_rows", 0)
        ug = result.get("updated_gaes_rows", 0)
        uk = result.get("updated_kto_stations", 0)
        warnings = result.get("warnings") or []

        if result.get("no_changes") and not warnings:
            flash("Изменений для синхронизации во всех версиях нет.", "info")
        elif result.get("no_changes"):
            for msg in warnings:
                flash(msg, "warning")
        else:
            parts = [
                f"затронуто версий БД: {vt}",
                f"станций (код КТО): {uk}",
                f"строк выработки: {ue}",
            ]
            if sync_station_gaes_charge:
                parts.append(f"строк заряда ГАЭС: {ug}")
            tables_label = (
                "Код КТО, таблицы выработки и заряда ГАЭС применены"
                if sync_station_gaes_charge
                else "Код КТО и таблица выработки применены"
            )
            flash(
                f"{tables_label} во всех версиях БД ("
                + ", ".join(parts)
                + ").",
                "success",
            )
            for msg in warnings:
                flash(msg, "warning")
            invalidate_cache("station_full", station_id=station.id)
            invalidate_cache_pattern("station_list:*")
    except Exception as e:
        import traceback

        db.session.rollback()
        traceback.print_exc()
        current_app.logger.exception(
            "[station_details] all_versions save failed station_id=%s", station.id
        )
        flash(f"Ошибка при сохранении во всех версиях БД: {e}", "danger")

    return True


def _station_log_entity_ids(station: Station) -> list[int]:
    """Идентификаторы всех копий станции во всех версиях БД (по external_code)."""
    from app.common.services.version_entity_resolve_services import (
        entity_log_ids_by_external_code,
    )

    return entity_log_ids_by_external_code(Station, station.id)


def _station_logs_base_query(station: Station):
    """Запрос логов станции по всем версиям БД (общий external_code)."""
    entity_ids = _station_log_entity_ids(station)
    return (
        db.session.query(Log)
        .filter(
            Log.entity_type == "station",
            Log.entity_id.in_(entity_ids),
        )
        .filter(~Log.action.ilike("%Открыта страница  электростанции%"))
        .order_by(Log.timestamp.desc())
    )


def _load_station_logs_merged(station: Station, *, limit: int, offset: int = 0) -> list:
    from app.energy_consumption.services.energy_consumption_summary_logging import (
        load_merged_station_gaes_charge_logs_raw,
    )

    return load_merged_station_gaes_charge_logs_raw(
        _station_log_entity_ids(station),
        limit=limit,
        offset=offset,
        station_logs_query=_station_logs_base_query(station),
    )


def _count_station_logs_merged(station: Station) -> int:
    from app.energy_consumption.services.energy_consumption_summary_logging import (
        count_merged_station_gaes_charge_logs,
    )

    return count_merged_station_gaes_charge_logs(
        _station_log_entity_ids(station),
        station_logs_query=_station_logs_base_query(station),
    )


def _format_logs_for_display(logs):
    """
    Предварительное форматирование логов для оптимизации рендеринга шаблона.
    Форматирует даты и применяет lower() в Python вместо Jinja2.
    
    Returns: список словарей с предформатированными данными
    """
    if not logs:
        return []
    
    # Получаем все уникальные версии БД одним запросом для оптимизации
    from app.common.models.database_version_model import DatabaseVersion
    version_ids = {log.database_version_id for log in logs if log.database_version_id}
    versions_map = {}
    if version_ids:
        # Используем оптимизированный запрос с загрузкой только нужных полей
        try:
            versions = db.session.query(DatabaseVersion.id, DatabaseVersion.version_number).filter(
                DatabaseVersion.id.in_(version_ids)
            ).all()
            versions_map = {v.id: v.version_number for v in versions}
        except Exception:
            # Если ошибка - просто показываем ID версии вместо названия
            versions_map = {vid: str(vid) for vid in version_ids}
    
    def _suppress_noop_changes(details_text: str) -> str:
        if not details_text:
            return ''
        def _norm(s: str) -> str:
            if s is None:
                return ''
            s2 = s.replace('\u00A0', ' ').replace('\xa0', ' ').strip().lower()
            while '  ' in s2:
                s2 = s2.replace('  ', ' ')
            return s2
        parts = [p.strip() for p in details_text.split(';')]
        filtered = []
        for p in parts:
            if not p:
                continue
            if '→' in p:
                left, right = p.split('→', 1)
                if _norm(left) == _norm(right):
                    # пропускаем "X → X" и "не указано → не указано"
                    continue
                left_value = left.rsplit('-', 1)[-1].strip() if '-' in left else left
                right_value = right
                if _norm(left_value) == _norm(right_value):
                    # пропускаем "X → X" и "не указано → не указано"
                    continue
            filtered.append(p)
        return '; '.join(filtered)

    formatted_logs = []
    for log in logs:
        details_clean = _suppress_noop_changes(log.details or '')
        ts = log.timestamp
        if ts is not None:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ts_msk = ts.astimezone(MOSCOW)
        else:
            ts_msk = None
        date_str = ts_msk.strftime('%Y-%m-%d') if ts_msk else ''
        time_str = ts_msk.strftime('%H:%M:%S') if ts_msk else ''
        formatted_log = {
            'date': date_str,
            'time': time_str,
            'datetime': f'{date_str} {time_str}'.strip(),
            'username': log.username or '',
            'username_lower': (log.username or '').lower(),
            'action': log.action or '',
            'action_lower': (log.action or '').lower(),
            'details': details_clean,
            'details_lower': details_clean.lower(),
            'database_version': versions_map.get(log.database_version_id, '—') if log.database_version_id else '—',
        }
        formatted_logs.append(formatted_log)
    return formatted_logs


def _load_station_with_version(query_factory, requested_version_id, station_id=None):
    from app.common.services.version_entity_resolve_services import load_station_with_version

    return load_station_with_version(
        query_factory, requested_version_id, station_id=station_id
    )


def _filter_items_by_version(items, version_id):
    if not items:
        return []
    if version_id is None:
        return [
            item for item in items
            if getattr(item, "database_version_id", None) is None
        ]
    return [
        item for item in items
        if getattr(item, "database_version_id", None) == version_id
    ]


def _prospective_place_version_for_station_link(place) -> Optional[int]:
    """Та же версия БД, что используется для списка станций на карточке площадки."""
    vid = getattr(place, "database_version_id", None)
    if vid is not None:
        return vid
    return get_current_db_version_id()


def _station_prospective_place_tep_links(station: Station, station_version_id: Optional[int]) -> list[dict]:
    """
    Карточки перспективных площадок с тем же external_code и согласованной версией БД.
    Обратное соответствие правилу привязки на экранах prospective_places.
    """
    ec = (getattr(station, "external_code", None) or "").strip()
    if not ec:
        return []

    from app.generation.prospective_places.models import (
        StationProspectivePlaceAES,
        StationProspectivePlaceGES,
        StationProspectivePlaceGAES,
    )

    tuples: list[tuple[int, object, str, str]] = []
    sort_key = {"aes": 0, "ges": 1, "gaes": 2}

    for place_row in StationProspectivePlaceAES.query.filter(
        StationProspectivePlaceAES.external_code == ec,
    ).all():
        if _prospective_place_version_for_station_link(place_row) == station_version_id:
            sn = ((getattr(place_row, "site_name", None) or "").strip() or "—")
            tuples.append(
                (
                    sort_key["aes"],
                    place_row,
                    "prospective_places_bp.prospective_place_aes_details",
                    f"АЭС — {sn}",
                )
            )

    for place_row in StationProspectivePlaceGES.query.filter(
        StationProspectivePlaceGES.external_code == ec,
    ).all():
        if _prospective_place_version_for_station_link(place_row) == station_version_id:
            sn = ((getattr(place_row, "site_name", None) or "").strip() or "—")
            tuples.append(
                (
                    sort_key["ges"],
                    place_row,
                    "prospective_places_bp.prospective_place_ges_details",
                    f"ГЭС — {sn}",
                )
            )

    for place_row in StationProspectivePlaceGAES.query.filter(
        StationProspectivePlaceGAES.external_code == ec,
    ).all():
        if _prospective_place_version_for_station_link(place_row) == station_version_id:
            sn = ((getattr(place_row, "site_name", None) or "").strip() or "—")
            tuples.append(
                (
                    sort_key["gaes"],
                    place_row,
                    "prospective_places_bp.prospective_place_gaes_details",
                    f"ГАЭС — {sn}",
                )
            )

    tuples.sort(key=lambda t: (t[0], getattr(t[1], "id", 0)))

    out: list[dict] = []
    seen_ids: set[tuple[str, int]] = set()
    for _k, place_row, endpoint, menu_label in tuples:
        pid = int(getattr(place_row, "id"))
        dedup = (endpoint, pid)
        if dedup in seen_ids:
            continue
        seen_ids.add(dedup)
        out.append(
            {
                "url": url_for(endpoint, id=pid, **request.args),
                "menu_label": menu_label,
            }
        )
    return out


@station_bp.route("/station_details/<int:station_id>", methods=["GET", "POST"])
@login_required
@handle_stale_data
def station_details(station_id):
    """Маршрут для отображения сведений об  электростанции с логированием изменений."""

    user = session.get('username', 'Неизвестный пользователь')
    route_started_at = time.perf_counter()

    current_version_id = get_current_db_version_id()

    def _station_query():
        return (
            db.session.query(Station)
            .options(
                # Территориальная привязка
                joinedload(Station.regional_district).joinedload(RegionalDistrict.regional_energy_systems),
                joinedload(Station.regional_district).joinedload(RegionalDistrict.federal_district),
                # Прямая связь электростанции с РЭС + ОЭС + тип энергосистемы
                joinedload(Station.regional_energy_system_obj)
                    .joinedload(RegionalEnergySystem.union_energy_system)
                    .joinedload(UnionEnergySystem.energy_system_type),
                # Остальные связи электростанции
                joinedload(Station.energy_unit),
                joinedload(Station.condition_type),
                joinedload(Station.group),
                joinedload(Station.station_type),
                selectinload(Station.machines)
                    .selectinload(Machine.machine_powers),
                selectinload(Station.machines)
                    .selectinload(Machine.machine_fuels).joinedload(MachineFuel.fuel).joinedload(Fuel.fuel_type),
                selectinload(Station.machines)
                    .selectinload(Machine.machine_tes_types).joinedload(MachineTesType.tes_type),
                selectinload(Station.machines)
                    .joinedload(Machine.gen_company),
                selectinload(Station.machines)
                    .joinedload(Machine.tes_machine_type)
            )
            .filter_by(id=station_id)
        )

    # Сначала резолвим id в текущую версию БД (по external_code), затем уже
    # канонизируем URL — иначе redirect по годам при смене версии оставляет
    # в адресной строке чужой id из другой версии.
    station, station_version_id = _load_station_with_version(
        _station_query, current_version_id, station_id=station_id
    )

    if not station:
        abort(404)

    if request.method == "GET":
        from app.generation.services.station_services.generation_year_filter_services import (
            resolve_generation_year_filters_for_request,
        )

        start_year, end_year, year_redirect = resolve_generation_year_filters_for_request()
        id_mismatch = station.id != station_id
        if id_mismatch or year_redirect is not None:
            q = request.args.to_dict(flat=True)
            if year_redirect is not None:
                q["start_year"] = start_year
                q["end_year"] = end_year
            return redirect(
                url_for(
                    "station_bp.station_details",
                    station_id=station.id,
                    **q,
                )
            )

    station.machines = _filter_items_by_version(station.machines, station_version_id)
    
    # Диагностика для понимания объема данных
    machines_count = len(station.machines) if station.machines else 0
    # Подсчитываем мощности
    powers_count = 0
    for machine in (station.machines or []):
        powers_count += len(machine.machine_powers) if hasattr(machine, 'machine_powers') else 0
    
    # Сортировка агрегатов: ВЭС/СЭС по году ввода, ТЭС по станционному номеру; архивные — в конце
    if station and station.machines:
        try:
            station.machines.sort(key=lambda m: (
                1 if bool(getattr(m, "is_archived", False)) else 0,
                machine_year_then_number_sort_key(m),
            ))
        except Exception:
            pass

    # Отложенное логирование открытия страницы - только для GET запросов
    # Выполняется после основной логики, чтобы не блокировать обработку
    if request.method == "GET":
        regional_district_name = station.regional_district.name if station and station.regional_district else "не указано"
        log_to_db(user, f"Открыта страница  электростанции {station.name} ({regional_district_name})", entity_type="station", entity_id=station.id)

    form = StationFilterForm()
    form_machines = MachineFilterSmallForm()

    edit_roles = ["admin", "generation-admin", "generation-editor", "generation_admin", "generation_editor"]
    fuel_edit_roles = ["admin", "fuel-admin", "fuel-editor"]
    can_edit = current_user.is_authenticated and any(
        role in current_user.role_names for role in edit_roles
    )
    can_edit_fuel = current_user.is_authenticated and any(
        role in current_user.role_names for role in fuel_edit_roles
    )
    can_add_machine = can_fuel_user_add_machine_to_station(current_user, station)
    can_edit_fuel_dz = can_fuel_user_edit_decentralized_station_details(current_user, station)
    can_edit_station_energy = can_edit or can_edit_fuel_dz
    is_station_decentralized_zone = is_decentralized_zone_station(station)
    decentralized_zone_energy_system_type_name = (
        get_decentralized_zone_energy_system_type_name(station_version_id)
        if is_station_decentralized_zone
        else None
    )

    # Получение параметров запроса с дефолтными значениями
    start_year = request.args.get("start_year", get_filter_start_year(), type=int)
    end_year = request.args.get("end_year", get_filter_end_year(), type=int)
    machine_ids_to_delete = request.form.getlist("machines_delete[]", type=int)
    
    # Определяем, какая форма была отправлена
    submitted_keys = set(request.form.keys())
    print(f"[DEBUG] Отправленные поля формы: {submitted_keys}")
    is_station_form = any(
        k in submitted_keys
        for k in {
            "name",
            "id_condition_type",
            "id_station_type",
            "id_station_group",
            "id_energy_unit",
            "id_regional_energy_system",
            "id_regional_district",
            "location",
            "note",
            "station_sign",
            "external_code",
            "kto",
        }
    )
    # Признаки формы агрегатов: удаление/архив/поля агрегатов/примечание агрегата/собственник агрегата
    is_machines_form = (
        ("machines_delete[]" in submitted_keys)
        or ("machines_archive[]" in submitted_keys)
        or ("machines_archive_form" in submitted_keys)
        or any(
            k.startswith(prefix)
            for k in submitted_keys
            for prefix in ("fuel_so_", "id_gen_company_", "note_")
        )
    )
    is_station_energy_form = request.form.get("station_energy_generation_submit") == "1"
    is_station_gaes_charge_form = request.form.get("station_gaes_charge_submit") == "1"
    is_station_gaes_combined_energy_form = (
        request.form.get("station_gaes_combined_energy_submit") == "1"
    )
    is_unified_station_page_save = request.form.get("station_details_unified_save") == "1"
    print(
        f"[DEBUG] is_station_form = {is_station_form}, is_machines_form = {is_machines_form}, "
        f"is_station_energy_form = {is_station_energy_form}, is_station_gaes_charge_form = {is_station_gaes_charge_form}, "
        f"is_station_gaes_combined_energy_form = {is_station_gaes_combined_energy_form}, "
        f"is_unified_station_page_save = {is_unified_station_page_save}"
    )

    is_gaes_station = _is_gaes_station(station)

    # Используем кэшированные справочники для оптимизации
    form_data = CacheService.get_station_details_form_data()
    condition_types = form_data['condition_types']
    station_groups = form_data['station_groups']
    gen_companies = form_data['gen_companies']

    # Итоги мощностей станции считаем из MachinePower (без отдельной таблицы)
    station.powers_by_year = load_station_powers_by_year(
        station.id,
        start_year,
        end_year,
        station_version_id,
    )

    station.station_energy_by_year = station_annual_energy_by_year(
        station.id, start_year, end_year, station_version_id
    )

    if is_gaes_station:
        gaes_charge_query = (
            StationGaesChargeConsumption.query.filter_by(id_station=station.id)
            .filter(
                StationGaesChargeConsumption.year_number >= start_year,
                StationGaesChargeConsumption.year_number <= end_year,
            )
        )
        gaes_charge_query = filter_by_explicit_db_version(
            gaes_charge_query,
            StationGaesChargeConsumption,
            station_version_id,
        )
        station.station_gaes_charge_by_year = {
            row.year_number: row.charge_consumption for row in gaes_charge_query.all()
        }
    else:
        station.station_gaes_charge_by_year = {}

    current_year = get_current_year()

    # Получаем типы ТЭС для текущего года из MachineTesType
    machine_tes_types_map = get_current_machine_tes_types_map()

    # Загружаем списки данных из сервисов
    energy_system_type_list = get_energy_system_type_list_full()
    energy_system_type_names = get_energy_system_type_map()

    union_energy_system_list = get_union_energy_system_list_full()
    union_energy_system_names = get_union_energy_systems_map()
    regional_energy_system_mapping = get_ues_to_res_ids_map()

    # Список (id, name) — без ORM, чтобы избежать DetachedInstanceError при кэше
    regional_energy_system_choices = get_regional_energy_system_choices()
    regional_energy_system_names = get_regional_energy_systems_map()

    # Карта для автоподстановки ОЭС и типа энергосистемы по выбранной РЭС
    res_auto_map = {}
    res_to_ues = get_res_to_ues_id_map()
    res_to_est = get_res_to_est_id_map()
    dz_energy_system_type_name = get_decentralized_zone_energy_system_type_name(station_version_id)
    for res_id, res_name in regional_energy_system_choices:
        ues_id = res_to_ues.get(res_id)
        est_id = res_to_est.get(res_id)
        ues_name = union_energy_system_names.get(ues_id, "Нет данных") if ues_id else "Нет данных"
        est_name = energy_system_type_names.get(est_id, "Нет данных") if est_id else "Нет данных"
        if isinstance(res_name, str) and res_name.strip().lower() == "не указано":
            est_name = dz_energy_system_type_name
        res_auto_map[res_id] = {
            "union_energy_system": ues_name,
            "energy_system_type": est_name,
        }

    federal_district_list = get_federal_district_list_full()
    regional_district_mapping = get_fd_to_rd_ids_map()

    regional_district_list = get_regional_district_list_full()
    regional_district_names = get_rd_to_fd_id_map()

    # Заполняем список субъектов РФ с фильтрацией по версии БД
    # regional_district_list теперь содержит кортежи (id, name) вместо ORM-объектов
    form.id_regional_district.choices = regional_district_list
    # Список региональных энергосистем для выпадающего списка (id, name) — только из БД по текущей версии.
    # Приводим к кортежам (int, str), т.к. get_regional_energy_system_choices() возвращает Row-объекты.
    form.id_regional_energy_system.choices = [(int(r[0]), r[1]) for r in regional_energy_system_choices]
    form.id_condition_type.choices = choices_cache.get_choices(ConditionType, ConditionType.id)
    form.id_station_group.choices = choices_cache.get_choices(StationGroup, StationGroup.id)
    
    form_machines.id_gen_company.choices = choices_cache.get_choices_with_default(
        GenCompany,
        GenCompany.id,
        default_text="не указано"
    )

    def _get_versioned_choices(model_class, order_by_field, version_id, name_field="name"):
        query = model_class.query.order_by(order_by_field)
        query = filter_by_explicit_db_version(query, model_class, version_id)
        return [(item.id, getattr(item, name_field)) for item in query.all()]

    # Для форм используем choices в версии электростанции (иначе валидатор ругается на "невалидный выбор")
    form.id_station_type.choices = _get_versioned_choices(StationType, StationType.id, station_version_id)
    form.id_energy_unit.choices = _get_versioned_choices(EnergyUnit, EnergyUnit.id, station_version_id)

    rounding_digits, rounding_digits_gen, rounding_digits_gaes = get_station_details_rounding_triplet()

    if request.method == "GET":
        form.process(obj=station)
        if form.id_condition_type.data is None:
            form.id_condition_type.data = 0
        if not form.station_sign.data:
            form.station_sign.data = STATION_SIGN_UNSPECIFIED
        # Для energy_unit и station_type оставляем None как есть, 
        # так как теперь coerce возвращает None для пустых значений

    if request.method == "POST":
        station_meta_field_keys = {
            "name",
            "id_condition_type",
            "id_station_type",
            "id_station_group",
            "id_energy_unit",
            "id_regional_energy_system",
            "id_regional_district",
            "location",
            "note",
            "station_sign",
            "external_code",
            "kto",
        }

        # Единая отправка: карточка станции + агрегаты + выработка (+ потребление ГАЭС) одной кнопкой / Enter
        if is_unified_station_page_save:
            if not can_edit and not can_edit_fuel:
                flash("Недостаточно прав для сохранения.", "danger")
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))

            form_version = request.form.get("version", type=int)
            if form_version and hasattr(station, "version") and station.version != form_version:
                flash("Данные были изменены другим пользователем. Пожалуйста, обновите страницу.", "warning")
                log_to_db(
                    user,
                    f"Обнаружен конфликт версий при сохранении страницы электростанции {station.name} (ожидаемая: {form_version}, текущая: {station.version})",
                    entity_type="station",
                    entity_id=station.id,
                )
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))

            if machine_ids_to_delete:
                if not getattr(current_user, "is_admin", False):
                    flash("Удаление агрегатов доступно только администратору.", "danger")
                else:
                    try:
                        changes = delete_machines_service(user, station, machine_ids_to_delete)
                        if changes:
                            flash("Выбранные агрегаты и связанные данные были удалены!", "success")
                            for machine_id in machine_ids_to_delete:
                                invalidate_cache("machine", machine_id=machine_id)
                                invalidate_cache("station_full", station_id=station.id)
                                invalidate_cache_pattern("station_list:*")
                    except Exception as e:
                        import traceback

                        traceback.print_exc()
                        flash(f"Ошибка при удалении агрегата(ов): {e}", "danger")

            machines_all_versions_handled = False
            if can_edit and (is_machines_form or request.values.get("all_versions") == "1"):
                machines_all_versions_handled = _handle_station_machines_all_versions_save(
                    user,
                    station,
                    start_year=start_year,
                    end_year=end_year,
                    is_gaes_station=is_gaes_station,
                )
                if not machines_all_versions_handled:
                    if not form_machines.validate():
                        print("Ошибки в form_machines:", form_machines.errors)
                        flash(
                            "Не удалось сохранить агрегаты: ошибка проверки формы. "
                            "Обновите страницу и попробуйте снова.",
                            "danger",
                        )
                    elif form_machines.validate_on_submit():
                        try:
                            changes = update_machines_from_form_service(
                                user, station, form_machines, request.form
                            )
                            if changes:
                                flash("Изменения агрегатов сохранены!", "success")
                                invalidate_cache("station_full", station_id=station.id)
                                invalidate_cache_pattern("station_list:*")
                        except Exception as e:
                            import traceback

                            traceback.print_exc()
                            flash(f"Ошибка при обновлении агрегатов: {e}", "danger")

            if (
                any(k in submitted_keys for k in station_meta_field_keys)
                and request.values.get("all_versions") != "1"
            ):
                try:
                    station_changes = _save_station_meta_from_form(
                        user,
                        station,
                        form,
                        regional_district_list,
                        can_edit=can_edit,
                        can_edit_fuel=can_edit_fuel,
                        can_edit_fuel_dz=can_edit_fuel_dz,
                    )
                    if station_changes:
                        flash("Изменения в  электростанции успешно обновлены!", "success")
                        invalidate_cache("station_full", station_id=station.id)
                        invalidate_cache_pattern("station_list:*")
                except Exception as e:
                    import traceback

                    traceback.print_exc()
                    flash(f"Ошибка при обновлении полей электростанции: {e}", "danger")

            if can_edit and is_station_gaes_combined_energy_form and request.values.get("all_versions") != "1":
                if not is_gaes_station:
                    flash("Совместное сохранение доступно только для электростанций типа ГАЭС.", "warning")
                else:
                    try:
                        gen_changes = save_station_energy_generation_service(
                            user,
                            station,
                            station_version_id,
                            start_year,
                            end_year,
                            request.form,
                        )
                        gaes_changes = save_station_gaes_charge_consumption_service(
                            user,
                            station,
                            station_version_id,
                            start_year,
                            end_year,
                            request.form,
                        )
                        if gen_changes or gaes_changes:
                            parts = []
                            if gen_changes:
                                parts.append("Выработка электроэнергии сохранена.")
                            if gaes_changes:
                                parts.append("Потребление электроэнергии ГАЭС на заряд сохранено.")
                            flash(" ".join(parts), "success")
                            invalidate_cache("station_full", station_id=station.id)
                            invalidate_cache_pattern("station_list:*")
                    except Exception as e:
                        import traceback

                        traceback.print_exc()
                        flash(f"Ошибка при сохранении выработки/потребления: {e}", "danger")
            elif can_edit_station_energy and is_station_energy_form:
                try:
                    gen_changes = save_station_energy_generation_service(
                        user,
                        station,
                        station_version_id,
                        start_year,
                        end_year,
                        request.form,
                    )
                    if gen_changes:
                        flash("Выработка электроэнергии сохранена!", "success")
                        invalidate_cache("station_full", station_id=station.id)
                        invalidate_cache_pattern("station_list:*")
                except Exception as e:
                    import traceback

                    traceback.print_exc()
                    flash(f"Ошибка при сохранении выработки электроэнергии: {e}", "danger")
            elif can_edit and is_station_gaes_charge_form:
                if not is_gaes_station:
                    flash("Блок доступен только для электростанций типа ГАЭС.", "warning")
                else:
                    try:
                        gaes_changes = save_station_gaes_charge_consumption_service(
                            user,
                            station,
                            station_version_id,
                            start_year,
                            end_year,
                            request.form,
                        )
                        if gaes_changes:
                            flash("Потребление электроэнергии ГАЭС на заряд сохранено!", "success")
                            invalidate_cache("station_full", station_id=station.id)
                            invalidate_cache_pattern("station_list:*")
                    except Exception as e:
                        import traceback

                        traceback.print_exc()
                        flash(f"Ошибка при сохранении потребления ГАЭС на заряд: {e}", "danger")

            return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))

        # ВАЖНО: Сначала обрабатываем форму агрегатов (включая удаление),
        # чтобы избежать конфликта с формой электростанции
        if is_machines_form:
            
            if not form_machines.validate():
                print("Ошибки в form_machines:", form_machines.errors)

            if machine_ids_to_delete:
                if not getattr(current_user, "is_admin", False):
                    flash("Удаление агрегатов доступно только администратору.", "danger")
                    return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
                try:
                    changes = delete_machines_service(user, station, machine_ids_to_delete)
                    if changes:
                        flash("Выбранные агрегаты и связанные данные были удалены!", "success")
                        # Инвалидация кэша после удаления агрегатов
                        for machine_id in machine_ids_to_delete:
                            invalidate_cache('machine', machine_id=machine_id)
                        invalidate_cache('station_full', station_id=station.id)
                        invalidate_cache_pattern('station_list:*')
                        # Важно: делаем редирект после удаления
                        return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    flash(f"Ошибка при удалении агрегата(ов): {e}", "danger")

            machines_all_versions_handled = _handle_station_machines_all_versions_save(
                user,
                station,
                start_year=start_year,
                end_year=end_year,
                is_gaes_station=is_gaes_station,
            )
            if form_machines.validate_on_submit() and not machines_all_versions_handled:
                try:
                    changes = update_machines_from_form_service(user, station, form_machines, request.form)
                    if changes:
                        flash("Изменения агрегатов сохранены!", "success")
                        # Инвалидация кэша после обновления агрегатов
                        invalidate_cache('station_full', station_id=station.id)
                        invalidate_cache_pattern('station_list:*')
                    # Дополнительно: если вместе с формой агрегатов пришли поля электростанции (например, id_energy_unit), сохраняем их тоже
                    try:
                        if any(
                            k in submitted_keys
                            for k in {
                                "name",
                                "id_condition_type",
                                "id_station_type",
                                "id_station_group",
                                "id_energy_unit",
                                "id_regional_energy_system",
                                "id_regional_district",
                                "location",
                                "note",
                                "external_code",
                                "kto",
                            }
                        ):
                            # Привязываем POST-данные к форме электростанции и валидируем
                            form.process(formdata=request.form)
                            if not form.validate():
                                print("Ошибки в form (в составе machinesForm):", form.errors)
                            else:
                                station_changes = update_station_from_form_service(user, station, form, regional_district_list)
                                if station_changes:
                                    flash("Изменения в  электростанции успешно обновлены!", "success")
                                    invalidate_cache('station_full', station_id=station.id)
                                    invalidate_cache_pattern('station_list:*')
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        flash(f"Ошибка при обновлении полей электростанции: {e}", "danger")
                    return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    flash(f"Ошибка при обновлении агрегатов: {e}", "danger")
                    # При ошибке продолжаем выполнение для показа формы с ошибками

        elif is_station_gaes_combined_energy_form:
            if not is_gaes_station:
                flash("Совместное сохранение доступно только для электростанций типа ГАЭС.", "warning")
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
            if not can_edit:
                flash("Недостаточно прав для сохранения.", "danger")
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
            form_version = request.form.get("version", type=int)
            if form_version and hasattr(station, "version") and station.version != form_version:
                flash("Данные были изменены другим пользователем. Пожалуйста, обновите страницу.", "warning")
                log_to_db(
                    user,
                    f"Обнаружен конфликт версий при сохранении выработки/потребления ГАЭС {station.name} (ожидаемая: {form_version}, текущая: {station.version})",
                    entity_type="station",
                    entity_id=station.id,
                )
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
            try:
                gen_changes = save_station_energy_generation_service(
                    user,
                    station,
                    station_version_id,
                    start_year,
                    end_year,
                    request.form,
                )
                gaes_changes = save_station_gaes_charge_consumption_service(
                    user,
                    station,
                    station_version_id,
                    start_year,
                    end_year,
                    request.form,
                )
                if gen_changes or gaes_changes:
                    parts = []
                    if gen_changes:
                        parts.append("Выработка электроэнергии сохранена.")
                    if gaes_changes:
                        parts.append("Потребление электроэнергии ГАЭС на заряд сохранено.")
                    flash(" ".join(parts), "success")
                    invalidate_cache("station_full", station_id=station.id)
                    invalidate_cache_pattern("station_list:*")
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
            except Exception as e:
                import traceback
                traceback.print_exc()
                flash(f"Ошибка при сохранении: {e}", "danger")
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))

        elif is_station_energy_form:
            if not can_edit_station_energy:
                flash("Недостаточно прав для сохранения выработки электроэнергии.", "danger")
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
            form_version = request.form.get("version", type=int)
            if form_version and hasattr(station, "version") and station.version != form_version:
                flash("Данные были изменены другим пользователем. Пожалуйста, обновите страницу.", "warning")
                log_to_db(
                    user,
                    f"Обнаружен конфликт версий при сохранении выработки электроэнергии {station.name} (ожидаемая: {form_version}, текущая: {station.version})",
                    entity_type="station",
                    entity_id=station.id,
                )
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
            try:
                gen_changes = save_station_energy_generation_service(
                    user,
                    station,
                    station_version_id,
                    start_year,
                    end_year,
                    request.form,
                )
                if gen_changes:
                    flash("Выработка электроэнергии сохранена!", "success")
                    invalidate_cache("station_full", station_id=station.id)
                    invalidate_cache_pattern("station_list:*")
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
            except Exception as e:
                import traceback
                traceback.print_exc()
                flash(f"Ошибка при сохранении выработки электроэнергии: {e}", "danger")
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))

        elif is_station_gaes_charge_form:
            if not is_gaes_station:
                flash("Блок доступен только для электростанций типа ГАЭС.", "warning")
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
            if not can_edit:
                flash("Недостаточно прав для сохранения потребления на заряд ГАЭС.", "danger")
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
            form_version = request.form.get("version", type=int)
            if form_version and hasattr(station, "version") and station.version != form_version:
                flash("Данные были изменены другим пользователем. Пожалуйста, обновите страницу.", "warning")
                log_to_db(
                    user,
                    f"Обнаружен конфликт версий при сохранении потребления ГАЭС на заряд {station.name} (ожидаемая: {form_version}, текущая: {station.version})",
                    entity_type="station",
                    entity_id=station.id,
                )
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
            try:
                gaes_changes = save_station_gaes_charge_consumption_service(
                    user,
                    station,
                    station_version_id,
                    start_year,
                    end_year,
                    request.form,
                )
                if gaes_changes:
                    flash("Потребление электроэнергии ГАЭС на заряд сохранено!", "success")
                    invalidate_cache("station_full", station_id=station.id)
                    invalidate_cache_pattern("station_list:*")
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
            except Exception as e:
                import traceback
                traceback.print_exc()
                flash(f"Ошибка при сохранении потребления ГАЭС на заряд: {e}", "danger")
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))

        # Обработка отправки основной формы электростанции
        # ВАЖНО: Обрабатываем только если НЕ было удаления агрегатов
        elif is_station_form:
            if not can_edit and not can_edit_fuel:
                flash("Недостаточно прав для сохранения.", "danger")
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
            try:
                form_version = request.form.get("version", type=int)
                if form_version and hasattr(station, "version") and station.version != form_version:
                    flash(
                        "Данные были изменены другим пользователем. Пожалуйста, обновите страницу.",
                        "warning",
                    )
                    log_to_db(
                        user,
                        f"Обнаружен конфликт версий при обновлении электростанции {station.name} (ожидаемая: {form_version}, текущая: {station.version})",
                        entity_type="station",
                        entity_id=station.id,
                    )
                    return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))

                changes = _save_station_meta_from_form(
                    user,
                    station,
                    form,
                    regional_district_list,
                    can_edit=can_edit,
                    can_edit_fuel=can_edit_fuel,
                    can_edit_fuel_dz=can_edit_fuel_dz,
                )
                if changes:
                    flash("Изменения в  электростанции успешно обновлены!", "success")
                    invalidate_cache("station_full", station_id=station.id)
                    invalidate_cache_pattern("station_list:*")
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
            except Exception as e:
                print(f"Ошибка при обновлении: {str(e)}")
                flash(f"Ошибка при обновлении данных: {str(e)}", "danger")
                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))

    # Timing: measure preparation time right before render
    before_render_at = time.perf_counter()
    
    # Подсчет объема данных для диагностики рендеринга
    machines_count = len(station.machines) if station.machines else 0
    years_range = end_year - start_year + 1
    cells_count = machines_count * years_range
    
    # [DIAG] Загружаем и форматируем логи
    t0 = time.perf_counter()
    station_logs_formatted = []
    if request.method == "GET":
        # entity_id — id станции в версии, из которой сохраняли; ищем по всем копиям (external_code).
        station_logs_raw = _load_station_logs_merged(station, limit=20)
        station_logs_formatted = _format_logs_for_display(station_logs_raw)
    print(f"[DIAG] Логи: {(time.perf_counter() - t0)*1000:.0f} мс")
    
    logs_count = len(station_logs_formatted)
    
    # can_edit задан выше (нужен для POST до разметки)
    # Создание группы оборудования — как в fuel_bp.add_equipment_group (только администраторы)
    can_add_equipment_group = current_user.is_authenticated and getattr(
        current_user, "has_admin", False
    )
    can_save_machines_all_versions = current_user.is_authenticated and getattr(
        current_user, "has_admin", False
    )
    can_save_equipment_group_all_versions = current_user.is_authenticated and getattr(
        current_user, "has_admin", False
    )

    # Группы оборудования электростанции (по версии) — только для ТЭС
    is_tes_station = (
        station.station_type
        and station.station_type.name
        and station.station_type.name.lower() == "тэс"
    )

    t1 = time.perf_counter()
    if is_tes_station:
        try:
            from app.fuel.services.stations.stations_equipment_groups_services import (
                build_station_equipment_groups_v2,
            )
            v2_groups_map = build_station_equipment_groups_v2(
                [station], version_id=station_version_id
            )
            v2_info = v2_groups_map.get(station.id) or {"groups": [], "total_rows": 0}
            station.equipment_group_v2_groups = v2_info["groups"]
            station.equipment_group_v2_total_rows = v2_info["total_rows"]
        except Exception as exc:
            current_app.logger.warning(
                f"[station_details] Failed to build v2 equipment groups: {exc}"
            )
            station.equipment_group_v2_groups = []
            station.equipment_group_v2_total_rows = 0
    else:
        station.equipment_group_v2_groups = []
        station.equipment_group_v2_total_rows = 0
    print(f"[DIAG] build_station_equipment_groups_v2: {(time.perf_counter() - t1)*1000:.0f} мс (групп: {len(station.equipment_group_v2_groups)})")


    initial_machines_tbody_html = None
    if request.method == "GET" and not can_edit:
        t2 = time.perf_counter()
        cache_bucket = int(time.time() // 120)
        initial_machines_tbody_html = _render_machines_tbody_cached(
            station.id,
            start_year,
            end_year,
            rounding_digits,
            can_edit,
            cache_bucket,
            current_version_id,
        )
        print(f"[DIAG] _render_machines_tbody_cached: {(time.perf_counter() - t2)*1000:.0f} мс")
    
    print(f"[RENDER START] Агрегатов: {machines_count}, Лет: {years_range}, Ячеек: {cells_count}, Логов: {logs_count}")

    # Render template (measure render time separately)
    t3 = time.perf_counter()
    year_features = get_year_feature_dict()
    print(f"[DIAG] get_year_feature_dict: {(time.perf_counter() - t3)*1000:.0f} мс")
    t4 = time.perf_counter()
    from app.common.services.help_services import format_decimal_for_display

    def format_station_energy_gen_display(val):
        return format_decimal_for_display(val, digits=rounding_digits_gen)

    def format_station_energy_gaes_display(val):
        return format_decimal_for_display(val, digits=rounding_digits_gaes)

    station_prospective_place_tep_links = _station_prospective_place_tep_links(
        station, station_version_id
    )

    _years_from_db = [y.number for y in get_year_list_full()]
    filter_year_list = (
        _years_from_db
        if _years_from_db
        else list(range(get_filter_start_year(), get_filter_end_year() + 1))
    )

    html = render_template(
        "generation/stations/station_details.html",
        form=form,
        form_machines=form_machines,
        station=station,
        rounding_digits=rounding_digits,
        rounding_digits_gen=rounding_digits_gen,
        rounding_digits_gaes=rounding_digits_gaes,
        start_year=start_year,
        end_year=end_year, 
        current_year=current_year,
        machine_tes_types_map=machine_tes_types_map,
        federal_districts=federal_district_list,
        regional_districts_list=regional_district_list,
        regional_energy_systems_list=[{"id": res_id, "name": res_name} for res_id, res_name in regional_energy_system_choices],
        union_energy_systems=union_energy_system_list,
        energy_system_types=energy_system_type_list,
        station_logs=station_logs_formatted,
        can_edit=can_edit,
        can_edit_fuel=can_edit_fuel,
        can_edit_fuel_dz=can_edit_fuel_dz,
        can_edit_station_energy=can_edit_station_energy,
        can_add_machine=can_add_machine,
        is_station_decentralized_zone=is_station_decentralized_zone,
        decentralized_zone_energy_system_type_name=decentralized_zone_energy_system_type_name,
        can_save_machines_all_versions=can_save_machines_all_versions,
        can_save_equipment_group_all_versions=can_save_equipment_group_all_versions,
        can_add_equipment_group=can_add_equipment_group,
        initial_machines_tbody_html=initial_machines_tbody_html,
        year_features=year_features,
        format_station_energy_gen_display=format_station_energy_gen_display,
        format_station_energy_gaes_display=format_station_energy_gaes_display,
        is_gaes_station=is_gaes_station,
        # Pass backend timings to the template (fallback to 0 if not computed)
        backend_prepare_ms=int((before_render_at - route_started_at) * 1000),
        res_auto_map=res_auto_map,
        station_prospective_place_tep_links=station_prospective_place_tep_links,
        filter_year_list=filter_year_list,
    )

    after_render_at = time.perf_counter()
    
    # Диагностика размера результата
    html_size_kb = len(html) / 1024
    jinja_ms = (after_render_at - t4) * 1000
    print(f"[DIAG] render_template (Jinja): {jinja_ms:.0f} мс")
    print(f"[RENDER DONE] Размер HTML: {html_size_kb:.1f} KB, время: {(after_render_at - before_render_at):.2f} сек")

    backend_prepare_ms = int((before_render_at - route_started_at) * 1000)
    backend_render_ms = int((after_render_at - before_render_at) * 1000)
    backend_total_ms = int((after_render_at - route_started_at) * 1000)

    # Re-render timings into response via headers; also, append a small marker script variable
    response = make_response(html)
    # Standard Server-Timing header for tooling support
    response.headers["Server-Timing"] = (
        f"prepare;desc=ORM+logic;dur={backend_prepare_ms}, "
        f"render;desc=Jinja;dur={backend_render_ms}, "
        f"total;desc=Total;dur={backend_total_ms}"
    )
    # Explicit headers for easy debugging
    response.headers["X-Backend-Timing-Prepare"] = str(backend_prepare_ms)
    response.headers["X-Backend-Timing-Render"] = str(backend_render_ms)
    response.headers["X-Backend-Timing-Total"] = str(backend_total_ms)
    
    # Логируем время выполнения с деталями
    years_count = end_year - start_year + 1
    print(f"[TIME] station_details (ID: {station_id}) заняла: {backend_total_ms/1000:.2f} сек (подготовка: {backend_prepare_ms}мс, рендер: {backend_render_ms}мс) | Лет: {years_count}")

    return response


@station_bp.route("/station_logs/<int:station_id>", methods=["GET"])
@login_required
def station_logs(station_id):
    """AJAX endpoint для загрузки всех логов электростанции."""
    from flask import jsonify
    
    current_version_id = get_current_db_version_id()

    def _station_query():
        return Station.query.filter_by(id=station_id)

    station, _ = _load_station_with_version(
        _station_query, current_version_id, station_id=station_id
    )
    if not station:
        abort(404)

    # Получаем параметр offset для пагинации
    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", 150, type=int)  # По умолчанию загружаем еще 150
    
    total_count = _count_station_logs_merged(station)
    logs_raw = _load_station_logs_merged(station, limit=limit, offset=offset)
    logs_formatted = _format_logs_for_display(logs_raw)
    
    return jsonify({
        'logs': logs_formatted,
        'offset': offset,
        'limit': limit,
        'count': len(logs_formatted),
        'total': total_count,
        'has_more': (offset + len(logs_formatted)) < total_count
    })


@station_bp.route(
    "/station_details/<int:station_id>/equipment_groups_v2/<int:equipment_group_id>/rename",
    methods=["POST"],
)
@login_required
@handle_stale_data
def rename_station_equipment_group_v2(station_id, equipment_group_id):
    """Переименование группы оборудования на странице электростанции."""
    # Переименование группы — доступно admin, generation-admin, generation-editor
    edit_roles = ["admin", "generation-admin", "generation-editor", "generation_admin", "generation_editor"]
    can_edit = current_user.is_authenticated and any(
        role in current_user.role_names for role in edit_roles
    )
    if not can_edit:
        abort(403)

    new_name = (request.form.get("equipment_group_name") or "").strip()
    all_versions = request.values.get("all_versions") == "1"
    if not new_name:
        flash("Название группы не может быть пустым.", "warning")
        return redirect(
            url_for("station_bp.station_details", station_id=station_id, **request.args)
        )

    from app.fuel.models.fue_equipment_group_model import EquipmentGroup
    from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
    from app.fuel.models.fue_equipment_group_set_station_model import (
        EquipmentGroupSetStation,
    )
    from app.fuel.services.equipment_groups.equipment_group_merge_services import (
        rename_or_merge_equipment_group_for_station,
        rename_or_merge_equipment_group_all_versions,
    )

    current_version_id = get_current_db_version_id()

    station = Station.query.filter_by(id=station_id).first()
    if not station:
        abort(404)

    # Проверяем, что группа принадлежит этой электростанции
    link_query = (
        db.session.query(EquipmentGroupSetStation)
        .join(
            EquipmentGroupSet,
            EquipmentGroupSet.equipment_group_set_station_id
            == EquipmentGroupSetStation.id,
        )
        .filter(
            EquipmentGroupSetStation.station_id == station_id,
            EquipmentGroupSet.equipment_group_id == equipment_group_id,
        )
    )
    link_query = filter_by_explicit_db_version(
        link_query, EquipmentGroupSetStation, current_version_id
    )
    first_link = link_query.first()
    if not first_link:
        flash("Группа оборудования не связана с этой станцией.", "warning")
        return redirect(
            url_for("station_bp.station_details", station_id=station_id, **request.args)
        )
    equipment_group_type_id = first_link.equipment_group_type_id

    equipment_group = EquipmentGroup.query.filter_by(id=equipment_group_id).first()
    if not equipment_group:
        flash("Группа оборудования не найдена.", "warning")
        return redirect(
            url_for("station_bp.station_details", station_id=station_id, **request.args)
        )

    if all_versions:
        if block_all_versions_without_admin(current_user):
            return redirect(
                url_for("station_bp.station_details", station_id=station_id, **request.args)
            )
        station_external_code = (station.external_code or "").strip()
        if not station_external_code:
            flash("У электростанции отсутствует external_code, невозможно применить изменения во всех версиях.", "warning")
            return redirect(
                url_for("station_bp.station_details", station_id=station_id, **request.args)
            )
        result = rename_or_merge_equipment_group_all_versions(
            station_external_code=station_external_code,
            equipment_group_id=equipment_group_id,
            equipment_group_type_id=equipment_group_type_id,
            new_name=new_name,
        )
        db.session.commit()
        station_name = station.name or f"ID={station_id}"
        log_to_db(
            current_user,
            "Переименование/объединение групп оборудования во всех версиях БД",
            details=(
                f"Станция: {station_name} (id={station_id}); "
                f"Группа id={equipment_group_id}: '{result.get('old_name', '')}' → '{result.get('new_name', new_name)}'; "
                f"Затронуто версий: {result.get('versions_touched', 0)}, "
                f"переименовано: {result.get('renamed_count', 0)}, "
                f"объединено: {result.get('merged_count', 0)}, удалено дубликатов: {result.get('removed_count', 0)}"
            ),
            entity_type="station",
            entity_id=station_id,
        )
        vt = result.get("versions_touched", 0)
        if vt > 0:
            flash(
                f"Изменения применены во всех версиях БД: затронуто версий {vt}, "
                f"переименовано {result.get('renamed_count', 0)}, объединено {result.get('merged_count', 0)}.",
                "success",
            )
        else:
            flash(
                "Не найдено групп с таким наименованием в версиях БД для обработки.",
                "info",
            )
        return redirect(
            url_for("station_bp.station_details", station_id=station_id, **request.args)
        )

    result = rename_or_merge_equipment_group_for_station(
        station_id=station_id,
        equipment_group_id=equipment_group_id,
        new_name=new_name,
        current_version_id=current_version_id,
    )
    db.session.commit()

    # Логирование в журнал изменений
    station_name = station.name or f"ID={station_id}"
    if result["merged"]:
        details_parts = [
            f"Станция: {station_name} (id={station_id})",
            f"Объединение групп оборудования: '{result['old_name']}' (id={result['deleted_group_id']}) → '{result['new_name']}' (id={result['primary_id']})",
            f"Удалена дублирующая группа id={result['deleted_group_id']}",
            f"Переназначено связей EquipmentGroupSet: {len(result.get('reassigned_set_ids', []))} (id: {result.get('reassigned_set_ids', [])})",
        ]
        if result.get("merged_fields"):
            details_parts.append(
                f"Объединенные параметры EquipmentGroup: {', '.join(result['merged_fields'])}"
            )
        log_to_db(
            current_user,
            "Объединение групп оборудования при переименовании",
            details="; ".join(details_parts),
            entity_type="station",
            entity_id=station_id,
        )
        flash(
            "Группа оборудования объединена с существующей группой с таким же наименованием.",
            "success",
        )
    else:
        log_to_db(
            current_user,
            "Переименование группы оборудования",
            details=(
                f"Станция: {station_name} (id={station_id}); "
                f"Группа id={equipment_group_id}: '{result.get('old_name', '')}' → '{result.get('new_name', new_name)}'"
            ),
            entity_type="station",
            entity_id=station_id,
        )
        flash("Название группы оборудования обновлено.", "success")
    return redirect(
        url_for("station_bp.station_details", station_id=station_id, **request.args)
    )


@station_bp.route(
    "/station_details/<int:station_id>/equipment_group_type_links/delete",
    methods=["POST"],
)
@login_required
@handle_stale_data
def delete_station_equipment_group_type_links(station_id):
    """Удаление «пустой» привязки типа группы оборудования к электростанции (без группы в топливе)."""
    edit_roles = [
        "admin",
        "generation-admin",
        "generation-editor",
        "generation_admin",
        "generation_editor",
    ]
    can_edit = current_user.is_authenticated and any(
        role in current_user.role_names for role in edit_roles
    )
    if not can_edit:
        abort(403)

    station = Station.query.filter_by(id=station_id).first()
    if not station:
        abort(404)

    all_versions = request.values.get("all_versions") == "1"
    id_list = request.form.getlist("equipment_group_set_station_id")

    from app.fuel.services.equipment_groups.equipment_group_edit_services import (
        delete_station_equipment_group_type_station_links,
    )

    try:
        result = delete_station_equipment_group_type_station_links(
            station_id=station_id,
            equipment_group_set_station_ids=id_list,
            all_versions=all_versions,
        )
        if not result.get("ok"):
            flash(
                "Не удалось удалить привязку: неверные данные или связь уже изменена. Обновите страницу.",
                "warning",
            )
        else:
            db.session.commit()
            invalidate_cache("station_full", station_id=station.id)
            invalidate_cache_pattern("station_list:*")
            station_name = station.name or f"ID={station_id}"
            flash(
                "Привязка типа группы оборудования к электростанции удалена"
                + (" во всех версиях БД." if all_versions else "."),
                "success",
            )
            log_to_db(
                current_user,
                "Удаление привязки типа группы оборудования к электростанции (EquipmentGroupSetStation)",
                details=(
                    f"Станция: {station_name} (id={station_id}); "
                    f"удалено связей станция–тип: {result.get('deleted_set_stations', 0)}, "
                    f"удалено EquipmentGroupSet: {result.get('deleted_sets', 0)}; "
                    f"во всех версиях: {all_versions}"
                ),
                entity_type="station",
                entity_id=station_id,
            )
    except Exception as e:
        db.session.rollback()
        flash(f"Ошибка при удалении привязки: {e}", "danger")

    return redirect(
        url_for("station_bp.station_details", station_id=station_id, **request.args)
    )


@station_bp.route("/station_details_tbody/<int:station_id>", methods=["GET"])
@login_required
def station_details_tbody(station_id):
    """Возвращает только tbody таблицы агрегатов для ленивой подгрузки.

    Параметры:
    - start_year, end_year, rounding_digits (query params)
    """
    start_time = time.time()
    
    start_year = request.args.get("start_year", get_filter_start_year(), type=int)
    end_year = request.args.get("end_year", get_filter_end_year(), type=int)
    rd_tb = _station_rounding_from_args("rounding_digits")
    rounding_digits = rd_tb if rd_tb is not None else 1

    # Проверяем права пользователя (включая generation-admin, generation-editor)
    edit_roles = ['admin', 'generation-admin', 'generation-editor', 'generation_admin', 'generation_editor']
    can_edit = any(role in current_user.role_names for role in edit_roles) if current_user.is_authenticated else False

    current_version_id = get_current_db_version_id()
    if can_edit:
        # Для редакторов отключаем кэш tbody, чтобы новые агрегаты появлялись сразу
        html = _render_machines_tbody(
            station_id,
            start_year,
            end_year,
            rounding_digits,
            can_edit,
            current_version_id,
        )
        resp = make_response(html)
        resp.headers["Cache-Control"] = "no-store"
    else:
        # Обновляем кэш раз в минуту через bucket
        cache_bucket = int(time.time() // 120)
        html = _render_machines_tbody_cached(
            station_id,
            start_year,
            end_year,
            rounding_digits,
            can_edit,
            cache_bucket,
            current_version_id,
        )
        resp = make_response(html)
        resp.headers["Cache-Control"] = "public, max-age=120"
    
    elapsed = time.time() - start_time
    print(f"[TIME] station_details_tbody (ID: {station_id}) заняла: {elapsed:.2f} сек")
    
    return resp


@station_bp.route("/station_details/<int:station_id>/station_energy_row", methods=["GET"])
@login_required
def station_details_station_energy_row(station_id):
    """HTML одной строки таблицы выработки электроэнергии (для обновления при смене округления)."""
    start_year = request.args.get("start_year", get_filter_start_year(), type=int)
    end_year = request.args.get("end_year", get_filter_end_year(), type=int)
    rounding_digits = _rounding_for_station_energy_fragment("rounding_digits_gen")
    edit_roles = [
        "admin",
        "generation-admin",
        "generation-editor",
        "generation_admin",
        "generation_editor",
    ]
    can_edit = current_user.is_authenticated and any(
        role in current_user.role_names for role in edit_roles
    )
    current_version_id = get_current_db_version_id()

    def _station_query():
        return db.session.query(Station).filter_by(id=station_id)

    station, station_version_id = _load_station_with_version(
        _station_query, current_version_id, station_id=station_id
    )
    if not station:
        abort(404)

    can_edit_fuel_dz = can_fuel_user_edit_decentralized_station_details(current_user, station)
    can_edit_energy = can_edit or can_edit_fuel_dz

    station.station_energy_by_year = station_annual_energy_by_year(
        station.id, start_year, end_year, station_version_id
    )

    from app.common.services.help_services import format_decimal_for_display

    def format_station_energy_gen_display(val):
        return format_decimal_for_display(val, digits=rounding_digits)

    html = render_template(
        "generation/stations/_station_energy_generation_row.html",
        station=station,
        start_year=start_year,
        end_year=end_year,
        can_edit=can_edit_energy,
        format_station_energy_gen_display=format_station_energy_gen_display,
    )
    resp = make_response(html)
    resp.headers["Cache-Control"] = "no-store" if can_edit_energy else "public, max-age=120"
    return resp


@station_bp.route("/station_details/<int:station_id>/station_gaes_charge_row", methods=["GET"])
@login_required
def station_details_station_gaes_charge_row(station_id):
    """HTML строки таблицы потребления ГАЭС на заряд (обновление при смене округления)."""
    start_year = request.args.get("start_year", get_filter_start_year(), type=int)
    end_year = request.args.get("end_year", get_filter_end_year(), type=int)
    rounding_digits = _rounding_for_station_energy_fragment("rounding_digits_gaes")
    edit_roles = [
        "admin",
        "generation-admin",
        "generation-editor",
        "generation_admin",
        "generation_editor",
    ]
    can_edit = current_user.is_authenticated and any(
        role in current_user.role_names for role in edit_roles
    )
    current_version_id = get_current_db_version_id()

    def _station_query():
        return (
            db.session.query(Station)
            .options(joinedload(Station.station_type))
            .filter_by(id=station_id)
        )

    station, station_version_id = _load_station_with_version(
        _station_query, current_version_id, station_id=station_id
    )
    if not station:
        abort(404)
    if not _is_gaes_station(station):
        return make_response("", 204)

    gaes_q = (
        StationGaesChargeConsumption.query.filter_by(id_station=station.id).filter(
            StationGaesChargeConsumption.year_number >= start_year,
            StationGaesChargeConsumption.year_number <= end_year,
        )
    )
    gaes_q = filter_by_explicit_db_version(
        gaes_q,
        StationGaesChargeConsumption,
        station_version_id,
    )
    station.station_gaes_charge_by_year = {
        row.year_number: row.charge_consumption for row in gaes_q.all()
    }

    from app.common.services.help_services import format_decimal_for_display

    def format_station_energy_gaes_display(val):
        return format_decimal_for_display(val, digits=rounding_digits)

    html = render_template(
        "generation/stations/_station_gaes_charge_consumption_row.html",
        station=station,
        start_year=start_year,
        end_year=end_year,
        can_edit=can_edit,
        format_station_energy_gaes_display=format_station_energy_gaes_display,
    )
    resp = make_response(html)
    resp.headers["Cache-Control"] = "no-store" if can_edit else "public, max-age=120"
    return resp


@lru_cache(maxsize=128)
def _render_machines_tbody_cached(
    station_id: int,
    start_year: int,
    end_year: int,
    rounding_digits: int,
    can_edit: bool,
    cache_bucket: int,
    version_id: Optional[int],) -> str:
    """Кэшируемый рендер tbody (cache_bucket обеспечивает инвалидацию раз в минуту).
    
    Args:
        station_id: ID электростанции
        start_year: начальный год
        end_year: конечный год
        rounding_digits: количество знаков после запятой
        can_edit: имеет ли пользователь права редактирования
        cache_bucket: bucket для инвалидации кэша
        version_id: версия БД для разделения кэша
    """
    # version_id участвует в ключе LRU-кэша (для читаемости подавляем предупреждение об использовании)
    _ = version_id

    return _render_machines_tbody(
        station_id,
        start_year,
        end_year,
        rounding_digits,
        can_edit,
        version_id,
    )


def _render_machines_tbody(
    station_id: int,
    start_year: int,
    end_year: int,
    rounding_digits: int,
    can_edit: bool,
    version_id: Optional[int],
) -> str:
    def _station_tbody_query():
        return (
            db.session.query(Station)
            .options(
                joinedload(Station.station_type),
                selectinload(Station.machines).joinedload(Machine.gen_company),
                selectinload(Station.machines).joinedload(Machine.tes_machine_type),
                selectinload(Station.machines).joinedload(Machine.equipment_group),
            )
            .filter_by(id=station_id)
        )

    station, station_version_id = _load_station_with_version(
        _station_tbody_query, version_id, station_id=station_id
    )
    if not station:
        abort(404)

    station.machines = _filter_items_by_version(station.machines, station_version_id)

    # Загружаем мощности и топливо только в нужном диапазоне лет, батчем по всем машинам
    machine_ids = [m.id for m in (station.machines or [])]
    powers_by_year = {}
    powers_by_machine_year = {}
    fuels_by_machine_year = {}

    if machine_ids:
        # MachinePower
        mp_query = (
            db.session.query(MachinePower)
            .filter(MachinePower.id_machine.in_(machine_ids))
            .filter(MachinePower.year_number >= start_year, MachinePower.year_number <= end_year)
        )
        mp_query = filter_by_explicit_db_version(mp_query, MachinePower, station_version_id)
        mp_list = mp_query.all()
        for mp in mp_list:
            y = mp.year_number
            powers_by_machine_year.setdefault(mp.id_machine, {})[y] = mp
        # В суммы станции не включаем архивные агрегаты
        active_machine_ids = {
            m.id for m in (station.machines or []) if not bool(getattr(m, "is_archived", False))
        }
        powers_by_year = aggregate_powers_from_machine_power_rows(
            [mp for mp in mp_list if mp.id_machine in active_machine_ids],
            start_year=start_year,
            end_year=end_year,
        )

        # MachineFuel
        mf_query = (
            db.session.query(MachineFuel)
            .options(joinedload(MachineFuel.fuel).joinedload(Fuel.fuel_type))
            .filter(MachineFuel.id_machine.in_(machine_ids))
            .filter(MachineFuel.year_number >= start_year, MachineFuel.year_number <= end_year)
        )
        mf_query = filter_by_explicit_db_version(mf_query, MachineFuel, station_version_id)
        mf_list = mf_query.all()
        for mf in mf_list:
            y = mf.year_number
            fuels_by_machine_year.setdefault(mf.id_machine, {})[y] = mf

        # PGU Machines and their powers
        pgu_query = (
            db.session.query(PGUMachine)
            .options(
                joinedload(PGUMachine.tes_machine_type),
                joinedload(PGUMachine.pgu_tes_machine_type),
            )
            .filter(PGUMachine.id_parent_machine.in_(machine_ids))
        )
        pgu_query = filter_by_explicit_db_version(pgu_query, PGUMachine, station_version_id)
        pgu_list = pgu_query.all()
        pgu_ids = [p.id for p in pgu_list]
        pgu_powers = []
        if pgu_ids:
            pgu_powers_query = (
                db.session.query(PGUMachinePower)
                .filter(PGUMachinePower.id_pgu_machine.in_(pgu_ids))
                .filter(PGUMachinePower.year_number >= start_year, PGUMachinePower.year_number <= end_year)
            )
            pgu_powers_query = filter_by_explicit_db_version(
                pgu_powers_query,
                PGUMachinePower,
                station_version_id,
            )
            pgu_powers = pgu_powers_query.all()
        # Map powers by PGU id and year
        pgu_powers_by_year = {}
        for pp in pgu_powers:
            pgu_powers_by_year.setdefault(pp.id_pgu_machine, {})[pp.year_number] = pp
        # Attach powers map and group PGUs by parent machine
        pgu_by_parent = defaultdict(list)
        for p in pgu_list:
            p.powers_by_year = pgu_powers_by_year.get(p.id, {})
            pgu_by_parent[p.id_parent_machine].append(p)

    # Сортировка агрегатов: ВЭС/СЭС по году ввода, ТЭС по станционному номеру; архивные — в конце
    if station and station.machines:
        try:
            station.machines.sort(key=lambda m: (
                1 if bool(getattr(m, "is_archived", False)) else 0,
                machine_year_then_number_sort_key(m),
            ))
        except Exception:
            pass

    # Временно «подкладываем» атрибут для совместимости с шаблоном
    station.powers_by_year = powers_by_year

    # Отображаемое название: как на machine_details — MachineName за год версии, иначе machine_name; при отличии в плане — "<текущ.> (<план>)"
    _apply_machine_display_names(station.machines)
    _apply_machine_gen_companies_for_version(station.machines, station_version_id)
    # Прикрепляем срезы к машинам
    for m in station.machines:
        m.machine_powers = list((powers_by_machine_year.get(m.id, {}) or {}).values())
        assign_machine_powers_by_year(m, start_year, end_year, rounding_digits)
        m.machine_fuels = list((fuels_by_machine_year.get(m.id, {}) or {}).values())
        # PGU attachments
        m.pgu_machines = pgu_by_parent.get(m.id, [])
        # base_rows = 1 + кол-во ПГУ
        try:
            m.base_rows = 1 + len(m.pgu_machines)
        except Exception:
            m.base_rows = 1

    from app.common.services.help_services import format_decimal_for_display

    def format_decimal_with_rounding(value):
        return format_decimal_for_display(value, digits=rounding_digits)

    gen_company_choices = get_gen_company_choices_for_version(station_version_id)

    return render_template(
        "generation/stations/_machines_tbody.html",
        station=station,
        start_year=start_year,
        end_year=end_year,
        rounding_digits=rounding_digits,
        format_decimal=format_decimal_with_rounding,
        gen_company_choices=gen_company_choices,
        can_edit=can_edit,
    )
