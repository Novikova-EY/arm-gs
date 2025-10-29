from app.generation.routes.stations import station_bp
from app.extensions import db
from config import Config
from decimal import Decimal
from flask import (
    render_template, request, redirect, url_for, flash, session, current_app, send_file, jsonify, abort, make_response
)
import time
from functools import lru_cache
from collections import defaultdict
from app.logs.services.logging_service import log_to_db
from flask_login import login_required, current_user
from flask import session
from app.generation.forms.station_forms import StationFilterForm
from app.generation.forms.machine_forms import MachineFilterSmallForm
from app.logs.services.logging_service import (
    log_to_db,
)
from app.generation.models.station.station_model import Station
from app.generation.models.station.station_group_model import StationGroup
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_tes_type_model import MachineTesType
from app.generation.models.station.station_power_model import StationPower
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
from sqlalchemy import or_
from app.logs.models.log_model import Log

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
    get_regional_energy_system_list_full,
    get_regional_energy_systems_map,
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
)
from app.common.services.get_services.gen_companies.gen_company_get_services import (
    get_gen_company_list_full,
) 
from app.generation.services.station_services.station_services import (
    get_stations_list,
    get_station_by_id, 
    assign_machine_powers_by_year, 
    get_station_list_template_context, 
    recalculate_station_power,
    get_current_machine_tes_types_map, 
    recalculate_station_powers_by_filtered_machines,
    update_station_from_form_service,
    delete_machines_service,
    update_machines_from_form_service,
)
from app.generation.services.station_services.import_station_services import (
    import_station_list_from_excel, 
    import_fuel_tes_station_from_excel, 
)
from app.common.services.cache_services import CacheService
from app.common.middleware import handle_stale_data
from app.common.services.cache_decorator import invalidate_cache, invalidate_cache_pattern


def _format_logs_for_display(logs):
    """
    Предварительное форматирование логов для оптимизации рендеринга шаблона.
    Форматирует даты и применяет lower() в Python вместо Jinja2.
    
    Returns: список словарей с предформатированными данными
    """
    formatted_logs = []
    for log in logs:
        formatted_log = {
            'date': log.timestamp.strftime('%Y-%m-%d') if log.timestamp else '',
            'time': log.timestamp.strftime('%H:%M:%S') if log.timestamp else '',
            'username': log.username or '',
            'username_lower': (log.username or '').lower(),
            'action': log.action or '',
            'action_lower': (log.action or '').lower(),
            'details': log.details or '',
            'details_lower': (log.details or '').lower(),
        }
        formatted_logs.append(formatted_log)
    return formatted_logs


@station_bp.route("/station_details/<int:station_id>", methods=["GET", "POST"])
@login_required
@handle_stale_data
def station_details(station_id):
    """Маршрут для отображения сведений об электростанции с логированием изменений."""

    user = session.get('username', 'Неизвестный пользователь')
    route_started_at = time.perf_counter()
    
    # Оптимизированная загрузка станции с предзагрузкой связанных объектов
    station = (
        db.session.query(Station)
        .options(
            joinedload(Station.regional_district).joinedload(RegionalDistrict.regional_energy_systems),
            joinedload(Station.regional_district).joinedload(RegionalDistrict.federal_district),
            joinedload(Station.energy_unit),
            joinedload(Station.condition_type),
            joinedload(Station.group),
            joinedload(Station.station_type),
            selectinload(Station.machines)
                .selectinload(Machine.machine_powers).joinedload(MachinePower.year),
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
        .first()
    )
    
    if not station:
        abort(404)
    
    # Диагностика для понимания объема данных
    machines_count = len(station.machines) if station.machines else 0
    # Подсчитываем мощности
    powers_count = 0
    for machine in (station.machines or []):
        powers_count += len(machine.machine_powers) if hasattr(machine, 'machine_powers') else 0
    
    # Сортировка агрегатов по станционному номеру (естественная сортировка)
    if station and station.machines:
        def _machine_sort_key(m):
            num_key = float('inf')
            try:
                if m.machine_number:
                    s = str(m.machine_number).strip()
                    if s.isdigit():
                        num_key = int(s)
            except Exception:
                num_key = float('inf')
            return num_key
        try:
            station.machines.sort(key=_machine_sort_key)
        except Exception:
            pass

    regional_district_name = station.regional_district.name if station and station.regional_district else "не указано"
    log_to_db(user, f"Открыта страница электростанции {station.name} ({regional_district_name})", entity_type="station", entity_id=station.id)

    form = StationFilterForm()
    form_machines = MachineFilterSmallForm()

    # Получение параметров запроса с дефолтными значениями
    start_year = request.args.get("start_year", Config.START_YEAR, type=int)
    end_year = request.args.get("end_year", Config.END_YEAR, type=int)
    machine_ids_to_delete = request.form.getlist("machines_delete[]", type=int)
    
    # Определяем, какая форма была отправлена
    submitted_keys = set(request.form.keys())
    is_station_form = any(k in submitted_keys for k in {"name", "id_condition_type", "id_station_type", "id_station_group", "id_energy_unit", "id_regional_district", "location", "note"})
    # Признаки формы агрегатов: удаление/поля агрегатов/примечание агрегата/собственник агрегата
    is_machines_form = ("machines_delete[]" in submitted_keys) or any(
        k.startswith(prefix)
        for k in submitted_keys
        for prefix in ("fuel_so_", "id_gen_company_", "note_")
    )

    # Используем кэшированные справочники для оптимизации
    form_data = CacheService.get_station_details_form_data()
    condition_types = form_data['condition_types']
    station_groups = form_data['station_groups']
    gen_companies = form_data['gen_companies']

    # Оптимизированный пересчет мощностей - только если нужно
    if request.method == "GET":
        recalculate_station_power(station, start_year, end_year)

    # Получаем мощности по годам из StationPower
    station.powers_by_year = {
        sp.year_number: {
            "p_ust": sp.p_ust,
            "p_ogr": sp.p_ogr,
            "p_rasp": sp.p_rasp
        }
        for sp in StationPower.query.filter_by(id_station=station.id).filter(
            StationPower.year_number >= start_year,
            StationPower.year_number <= end_year
        ).all()
    }

    current_year = get_current_year()

    # Получаем типы ТЭС для текущего года из MachineTesType
    machine_tes_types_map = get_current_machine_tes_types_map()

    # Загружаем списки данных из сервисов
    energy_system_type_list = get_energy_system_type_list_full()
    energy_system_type_names = get_energy_system_type_map()

    union_energy_system_list = get_union_energy_system_list_full()
    union_energy_system_names = get_union_energy_systems_map()
    regional_energy_system_mapping = get_ues_to_res_ids_map()

    regional_energy_system_list = get_regional_energy_system_list_full()
    regional_energy_system_names = get_regional_energy_systems_map()

    federal_district_list = get_federal_district_list_full()
    regional_district_mapping = get_fd_to_rd_ids_map()

    regional_district_list = get_regional_district_list_full()
    regional_district_names = get_rd_to_fd_id_map()

    # Заполняем список субъектов РФ с фильтрацией по версии БД
    form.id_regional_district.choices = [(rd.id, rd.name) for rd in regional_district_list]
    form.id_condition_type.choices = choices_cache.get_choices(ConditionType, ConditionType.id)
    form.id_station_group.choices = choices_cache.get_choices(StationGroup, StationGroup.id)
    
    # Заполняем список типов станций с фильтрацией по версии БД
    form.id_station_type.choices = choices_cache.get_choices_with_default(StationType, StationType.id, '— не указано —')
    form_machines.id_gen_company.choices = choices_cache.get_choices(GenCompany, GenCompany.id)
    
    # Используем кэшированные энергоузлы с фильтрацией по версии БД
    energy_units = form_data['energy_units']
    form.id_energy_unit.choices = choices_cache.get_choices_with_default(EnergyUnit, EnergyUnit.id, '— не указано —')
    energy_unit_names = [(0, '— не указано —')] + [(eu.id, eu.name) for eu in energy_units]

    try:
        rounding_digits = int(request.args.get('rounding_digits'))
    except (ValueError, TypeError):
        rounding_digits = 1

    if rounding_digits is None or rounding_digits < 0:
        rounding_digits = 1
    
    if request.method == "GET":
        form.process(obj=station)
        if form.id_condition_type.data is None:
            form.id_condition_type.data = 0
        if form.id_energy_unit.data is None:
            form.id_energy_unit.data = 0
        if form.id_station_type.data is None:
            form.id_station_type.data = 0

    if request.method == "POST":
        # Отладочный вывод для проверки POST-данных

        # ВАЖНО: Сначала обрабатываем форму агрегатов (включая удаление),
        # чтобы избежать конфликта с формой станции
        if is_machines_form:
            
            if not form_machines.validate():
                print("Ошибки в form_machines:", form_machines.errors)

            if machine_ids_to_delete:
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

            if form_machines.validate_on_submit():
                try:
                    changes = update_machines_from_form_service(user, station, form_machines, request.form)
                    if changes:
                        flash("Изменения агрегатов сохранены!", "success")
                        # Инвалидация кэша после обновления агрегатов
                        invalidate_cache('station_full', station_id=station.id)
                        invalidate_cache_pattern('station_list:*')
                    return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
                except Exception as e:
                    flash(f"Ошибка при обновлении агрегатов: {e}", "danger")
        
        # Обработка отправки основной формы станции
        # ВАЖНО: Обрабатываем только если НЕ было удаления агрегатов
        elif is_station_form:
            if not form.validate():
                print("Ошибки в form:", form.errors)
            if form.validate_on_submit():
                try:
                    # Проверка версии из формы для предотвращения concurrent updates
                    form_version = request.form.get('version', type=int)
                    if form_version and hasattr(station, 'version') and station.version != form_version:
                        flash('Данные были изменены другим пользователем. Пожалуйста, обновите страницу.', 'warning')
                        log_to_db(user, f"Обнаружен конфликт версий при обновлении станции {station.name} (ожидаемая: {form_version}, текущая: {station.version})", entity_type="station", entity_id=station.id)
                        return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
                    
                    changes = update_station_from_form_service(user, station, form, regional_district_list)
                    if changes:
                        flash("Изменения в электростанции успешно обновлены!", "success")
                        # Инвалидация кэша после успешного обновления
                        invalidate_cache('station_full', station_id=station.id)
                        invalidate_cache_pattern('station_list:*')
                    return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
                except Exception as e:
                    print(f"Ошибка при обновлении: {str(e)}")
                    flash(f"Ошибка при обновлении данных: {str(e)}", "danger")

    # Timing: measure preparation time right before render
    before_render_at = time.perf_counter()
    
    # Подсчет объема данных для диагностики рендеринга
    machines_count = len(station.machines) if station.machines else 0
    years_range = end_year - start_year + 1
    cells_count = machines_count * years_range
    
    # Загружаем и форматируем логи для подсчета
    station_logs_raw = (
        db.session.query(Log)
        .filter(
            or_(
                Log.action.ilike(f"%станции {station.name}%"),
                Log.details.ilike(f"%station_id={station.id}%")
            )
        )
        .filter(~Log.action.ilike("%Открыта страница электростанции%"))
        .order_by(Log.timestamp.desc())
        .limit(20)  # Уменьшено со 200 до 50 для ускорения рендеринга
        .all()
    )
    station_logs_formatted = _format_logs_for_display(station_logs_raw)
    logs_count = len(station_logs_formatted)
    
    print(f"[RENDER START] Агрегатов: {machines_count}, Лет: {years_range}, Ячеек: {cells_count}, Логов: {logs_count}")

    # Render template (measure render time separately)
    html = render_template(
        "generation/stations/station_details.html",
        form=form,
        form_machines=form_machines,
        station=station,
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year, 
        energy_unit_names=energy_unit_names,
        current_year=current_year,
        machine_tes_types_map=machine_tes_types_map,
        federal_districts=federal_district_list,
        regional_districts_list=regional_district_list,
        regional_energy_systems_list=regional_energy_system_list,
        union_energy_systems=union_energy_system_list,
        energy_system_types=energy_system_type_list,
        station_logs=station_logs_formatted,
        # Pass backend timings to the template (fallback to 0 if not computed)
        backend_prepare_ms=int((before_render_at - route_started_at) * 1000),
    )

    after_render_at = time.perf_counter()
    
    # Диагностика размера результата
    html_size_kb = len(html) / 1024
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
    """AJAX endpoint для загрузки всех логов станции."""
    from flask import jsonify
    
    station = Station.query.get_or_404(station_id)
    
    # Получаем параметр offset для пагинации
    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", 150, type=int)  # По умолчанию загружаем еще 150
    
    logs_query = (
        db.session.query(Log)
        .filter(
            or_(
                Log.action.ilike(f"%станции {station.name}%"),
                Log.details.ilike(f"%station_id={station.id}%")
            )
        )
        .filter(~Log.action.ilike("%Открыта страница электростанции%"))
        .order_by(Log.timestamp.desc())
    )
    
    # Получаем общее количество
    total_count = logs_query.count()
    
    # Применяем offset и limit
    logs_raw = logs_query.offset(offset).limit(limit).all()
    logs_formatted = _format_logs_for_display(logs_raw)
    
    return jsonify({
        'logs': logs_formatted,
        'offset': offset,
        'limit': limit,
        'count': len(logs_formatted),
        'total': total_count,
        'has_more': (offset + len(logs_formatted)) < total_count
    })


@station_bp.route("/station_details_tbody/<int:station_id>", methods=["GET"])
@login_required
def station_details_tbody(station_id):
    """Возвращает только tbody таблицы агрегатов для ленивой подгрузки.

    Параметры:
    - start_year, end_year, rounding_digits (query params)
    """
    start_time = time.time()
    
    start_year = request.args.get("start_year", Config.START_YEAR, type=int)
    end_year = request.args.get("end_year", Config.END_YEAR, type=int)
    rounding_digits = request.args.get("rounding_digits", 0, type=int)

    # Обновляем кэш раз в минуту через bucket
    cache_bucket = int(time.time() // 120)
    
    # Проверяем права пользователя
    edit_roles = ['admin', 'generation-admin', 'generation-editor']
    can_edit = any(role in current_user.role_names for role in edit_roles) if current_user.is_authenticated else False

    html = _render_machines_tbody_cached(station_id, start_year, end_year, rounding_digits, can_edit, cache_bucket)
    resp = make_response(html)
    resp.headers["Cache-Control"] = "public, max-age=120"
    
    elapsed = time.time() - start_time
    print(f"[TIME] station_details_tbody (ID: {station_id}) заняла: {elapsed:.2f} сек")
    
    return resp


@lru_cache(maxsize=128)
def _render_machines_tbody_cached(station_id: int, start_year: int, end_year: int, rounding_digits: int, can_edit: bool, cache_bucket: int) -> str:
    """Кэшируемый рендер tbody (cache_bucket обеспечивает инвалидацию раз в минуту).
    
    Args:
        station_id: ID станции
        start_year: начальный год
        end_year: конечный год
        rounding_digits: количество знаков после запятой
        can_edit: имеет ли пользователь права редактирования
        cache_bucket: bucket для инвалидации кэша
    """
    # Минимально необходимая предзагрузка
    station = (
        db.session.query(Station)
        .options(
            joinedload(Station.station_type),
            selectinload(Station.machines).joinedload(Machine.gen_company),
            selectinload(Station.machines).joinedload(Machine.tes_machine_type),
        )
        .filter_by(id=station_id)
        .first()
    )
    if not station:
        abort(404)

    # Загружаем мощности и топливо только в нужном диапазоне лет, батчем по всем машинам
    machine_ids = [m.id for m in (station.machines or [])]
    powers_by_year = {}
    powers_by_machine_year = {}
    fuels_by_machine_year = {}

    if machine_ids:
        # MachinePower
        mp_list = (
            db.session.query(MachinePower)
            .filter(MachinePower.id_machine.in_(machine_ids))
            .filter(MachinePower.year_number >= start_year, MachinePower.year_number <= end_year)
            .all()
        )
        for mp in mp_list:
            y = mp.year_number
            powers_by_machine_year.setdefault(mp.id_machine, {})[y] = mp
            agg = powers_by_year.setdefault(y, {"p_ust": 0, "p_ogr": 0, "p_rasp": 0})
            if mp.p_ust:
                agg["p_ust"] += float(mp.p_ust)
            if mp.p_ogr:
                agg["p_ogr"] += float(mp.p_ogr)
            if mp.p_rasp:
                agg["p_rasp"] += float(mp.p_rasp)

        # MachineFuel
        mf_list = (
            db.session.query(MachineFuel)
            .options(joinedload(MachineFuel.fuel).joinedload(Fuel.fuel_type))
            .filter(MachineFuel.id_machine.in_(machine_ids))
            .filter(MachineFuel.year_number >= start_year, MachineFuel.year_number <= end_year)
            .all()
        )
        for mf in mf_list:
            y = mf.year_number
            fuels_by_machine_year.setdefault(mf.id_machine, {})[y] = mf

        # PGU Machines and their powers
        pgu_list = (
            db.session.query(PGUMachine)
            .filter(PGUMachine.id_parent_machine.in_(machine_ids))
            .all()
        )
        pgu_ids = [p.id for p in pgu_list]
        pgu_powers = []
        if pgu_ids:
            pgu_powers = (
                db.session.query(PGUMachinePower)
                .filter(PGUMachinePower.id_pgu_machine.in_(pgu_ids))
                .filter(PGUMachinePower.year_number >= start_year, PGUMachinePower.year_number <= end_year)
                .all()
            )
        # Map powers by PGU id and year
        pgu_powers_by_year = {}
        for pp in pgu_powers:
            pgu_powers_by_year.setdefault(pp.id_pgu_machine, {})[pp.year_number] = pp
        # Attach powers map and group PGUs by parent machine
        pgu_by_parent = defaultdict(list)
        for p in pgu_list:
            p.powers_by_year = pgu_powers_by_year.get(p.id, {})
            pgu_by_parent[p.id_parent_machine].append(p)

    # Сортируем агрегаты по станционному номеру
    if station and station.machines:
        def _machine_sort_key(m):
            num_key = float('inf')
            try:
                if m.machine_number:
                    s = str(m.machine_number).strip()
                    if s.isdigit():
                        num_key = int(s)
            except Exception:
                num_key = float('inf')
            return num_key
        try:
            station.machines.sort(key=_machine_sort_key)
        except Exception:
            pass

    # Временно «подкладываем» атрибут для совместимости с шаблоном
    station.powers_by_year = powers_by_year
    # Прикрепляем срезы к машинам
    for m in station.machines:
        m.machine_powers = list((powers_by_machine_year.get(m.id, {}) or {}).values())
        m.machine_fuels = list((fuels_by_machine_year.get(m.id, {}) or {}).values())
        # PGU attachments
        m.pgu_machines = pgu_by_parent.get(m.id, [])
        # base_rows = 1 + кол-во ПГУ
        try:
            m.base_rows = 1 + len(m.pgu_machines)
        except Exception:
            m.base_rows = 1

    # Создаем кастомный фильтр для округления
    from app.common.services.help_services import format_decimal_for_display
    
    def format_decimal_with_rounding(value):
        return format_decimal_for_display(value, digits=rounding_digits)
    
    return render_template(
        "generation/stations/_machines_tbody.html",
        station=station,
        start_year=start_year,
        end_year=end_year,
        rounding_digits=rounding_digits,
        format_decimal=format_decimal_with_rounding,
        gen_company_choices=[(gc.id, gc.name) for gc in db.session.query(GenCompany).order_by(GenCompany.name).all()],
        can_edit=can_edit,
    )
