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
from flask_login import login_required
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
from app.refdata.models.refdata_for_stations.condition_type_model import ConditionType
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
    recalculate_station_powers_by_filtered_machines
)
from app.generation.services.station_services.import_station_services import (
    import_station_list_from_excel, 
    import_fuel_tes_station_from_excel, 
)
from app.common.services.cache_services import CacheService

@station_bp.route("/station_details/<int:station_id>", methods=["GET", "POST"])
@login_required
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
            selectinload(Station.machines)
                .selectinload(Machine.machine_powers).joinedload(MachinePower.year),
            selectinload(Station.machines)
                .selectinload(Machine.machine_fuels).joinedload(MachineFuel.fuel).joinedload(Fuel.fuel_type),
            selectinload(Station.machines)
                .selectinload(Machine.machine_tes_types).joinedload(MachineTesType.tes_type),
            selectinload(Station.machines)
                .joinedload(Machine.gen_company),
            selectinload(Station.machines)
                .joinedload(Machine.station_type),
            selectinload(Station.machines)
                .joinedload(Machine.tes_machine_type)
        )
        .filter_by(id=station_id)
        .first()
    )
    
    if not station:
        abort(404)
    # Сортировка агрегатов по группе, топливу и числовому номеру (естественная сортировка)
    if station and station.machines:
        def _machine_sort_key(m):
            group_key = (m.machine_group or '').lower()
            fuel_key = (m.fuel_so or '').lower()
            num_key = float('inf')
            try:
                if m.machine_number:
                    s = str(m.machine_number).strip()
                    if s.isdigit():
                        num_key = int(s)
            except Exception:
                num_key = float('inf')
            return (group_key, fuel_key, num_key)
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
    is_station_form = any(k in submitted_keys for k in {"name", "id_condition_type", "id_station_group", "id_energy_unit", "id_regional_district", "location", "note"})
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

    # Заполняем список субъектов РФ
    form.id_regional_district.choices = [(rd.id, rd.name) for rd in regional_district_list]
    form.id_condition_type.choices = [(ct.id, ct.name) for ct in condition_types]
    form.id_station_group.choices = [(ct.id, ct.name) for ct in station_groups]
    form_machines.id_gen_company.choices = [(gc.id, gc.name) for gc in gen_companies]
    
    # Используем кэшированные энергоузлы
    energy_units = form_data['energy_units']
    form.id_energy_unit.choices = [(eu.id, eu.name) for eu in energy_units]
    energy_unit_names = [(eu.id, eu.name) for eu in energy_units]

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

    if request.method == "POST":

        # Обработка отправки основной формы станции
        if is_station_form:
            if not form.validate():
                print("Ошибки в form:", form.errors)
            changes = []
            if form.validate_on_submit():
                try:
                    # Проверяем название станции
                    if station.name != form.name.data:
                        changes.append(f"Название: {station.name} → {form.name.data}")
                        station.name = form.name.data
                    
                    # Проверяем состояние станции
                    new_condition_type_id = int(form.id_condition_type.data)
                    new_condition_type = db.session.query(ConditionType).filter_by(id=new_condition_type_id).first()
                    if new_condition_type:
                        old_value = station.condition_type.name if station.condition_type else "не указано"
                        new_value = new_condition_type.name
                        if old_value != new_value:
                            changes.append(f"Состояние: {old_value} → {new_value}")
                        station.id_condition_type = new_condition_type.id
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
                    old_note = station.note.strip() if station.note and station.note.strip() else None
                    new_note = form.note.data.strip() if form.note.data and form.note.data.strip() else None

                    if old_note != new_note:
                        changes.append(f"Примечание: {station.note} → {new_note}")
                        station.note = new_note

                    # Проверяем субъект РФ
                    if station.id_regional_district != form.id_regional_district.data:
                        old_value = station.regional_district.name if station.regional_district else "не указано"
                        new_value = next((d["name"] for d in regional_district_list if d["id"] == form.id_regional_district.data), "не указано")
                        changes.append(f"Субъект РФ: {old_value} → {new_value}")
                        station.id_regional_district = form.id_regional_district.data

                    # Проверяем местоположение
                    new_location = form.location.data.strip() if form.location.data.strip() else None
                    if station.location != new_location:
                        changes.append(f"Местоположение: {station.location} → {new_location}")
                        station.location = new_location

                    # Обновляем связанные данные при изменении субъекта РФ
                    if station.id_regional_district != form.id_regional_district.data:
                        # Загружаем новый субъект РФ с предзагрузкой связанных данных
                        new_regional_district_obj = (
                            db.session.query(RegionalDistrict)
                            .options(
                                joinedload(RegionalDistrict.federal_district),
                                joinedload(RegionalDistrict.regional_energy_systems)
                                    .joinedload(RegionalEnergySystem.union_energy_system)
                                    .joinedload(UnionEnergySystem.energy_system_type)
                            )
                            .filter_by(id=form.id_regional_district.data)
                            .first()
                        )

                        if new_regional_district_obj:
                            # Обновляем федеральный округ
                            old_federal_district = station.regional_district.federal_district.name if station.regional_district and station.regional_district.federal_district else "не указано"
                            new_federal_district = new_regional_district_obj.federal_district.name if new_regional_district_obj.federal_district else "не указано"
                            if old_federal_district != new_federal_district:
                                changes.append(f"Федеральный округ: {old_federal_district} → {new_federal_district}")

                            # Обновляем энергосистемы
                            old_energy_systems = station.regional_district.regional_energy_systems if station.regional_district else []
                            new_energy_systems = new_regional_district_obj.regional_energy_systems

                            if old_energy_systems != new_energy_systems:
                                # Логируем изменения в энергосистемах
                                old_res_name = old_energy_systems[0].name if old_energy_systems else "не указано"
                                new_res_name = new_energy_systems[0].name if new_energy_systems else "не указано"
                                if old_res_name != new_res_name:
                                    changes.append(f"Региональная энергосистема: {old_res_name} → {new_res_name}")

                                old_ues_name = (
                                    old_energy_systems[0].union_energy_system.name 
                                    if old_energy_systems and old_energy_systems[0].union_energy_system 
                                    else "не указано"
                                )
                                new_ues_name = (
                                    new_energy_systems[0].union_energy_system.name 
                                    if new_energy_systems and new_energy_systems[0].union_energy_system 
                                    else "не указано"
                                )
                                if old_ues_name != new_ues_name:
                                    changes.append(f"ОЭС: {old_ues_name} → {new_ues_name}")

                                old_est_name = (
                                    old_energy_systems[0].union_energy_system.energy_system_type.name 
                                    if old_energy_systems and old_energy_systems[0].union_energy_system and old_energy_systems[0].union_energy_system.energy_system_type 
                                    else "не указано"
                                )
                                new_est_name = (
                                    new_energy_systems[0].union_energy_system.energy_system_type.name 
                                    if new_energy_systems and new_energy_systems[0].union_energy_system and new_energy_systems[0].union_energy_system.energy_system_type 
                                    else "не указано"
                                )
                                if old_est_name != new_est_name:
                                    changes.append(f"Часть энергосистемы России: {old_est_name} → {new_est_name}")

                            # Обновляем связь со станцией
                            station.regional_district = new_regional_district_obj


                    # Сохраняем в БД
                    db.session.commit()

                    if changes:
                        log_to_db(user, f"Изменения в электростанции {station.name} ({regional_district_name})", details="; ".join(changes), entity_type="station", entity_id=station.id)

                    flash("Изменения в электростанции успешно обновлены!", "success")
                    return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))

                except Exception as e:
                    db.session.rollback()
                    print(f"Ошибка при обновлении: {str(e)}")
                    flash(f"Ошибка при обновлении данных: {str(e)}", "danger")
                    log_to_db(user, f"Ошибка обновления электростанции {station.name} ({regional_district_name})", details=str(e), entity_type="station", entity_id=station.id)
        # Обработка отправки формы агрегатов
        if is_machines_form:
            if not form_machines.validate():
                print("Ошибки в form_machines:", form_machines.errors)

            changes = []

            if machine_ids_to_delete:
                machines_to_delete = Machine.query.filter(Machine.id.in_(machine_ids_to_delete)).all()
                affected_station_ids = set()

                for machine in machines_to_delete:
                    try:
                        affected_station_ids.add(machine.id_station)

                        # Удаление мощностей
                        for mp in machine.machine_powers:
                            db.session.delete(mp)

                        # Удаление топлива
                        for mf in machine.machine_fuels:
                            db.session.delete(mf)

                        # Удаление типов ТЭС
                        for mtt in machine.machine_tes_types:
                            db.session.delete(mtt)

                        changes.append(f"Агрегат {machine.machine_number or '—'} и связанные данные удалены")
                        db.session.delete(machine)

                    except Exception as e:
                        flash(f"Ошибка при удалении агрегата ID={machine.id}: {e}", "danger")
                        log_to_db(user, f"Ошибка удаления агрегата ID={machine.id}", details=str(e))

                # Проверка: если на станции больше нет агрегатов — удалить station_powers
                for station_id in affected_station_ids:
                    remaining_machines = Machine.query.filter_by(id_station=station_id).count()
                    if remaining_machines == 0:
                        powers_to_delete = StationPower.query.filter_by(id_station=station_id).all()
                        for sp in powers_to_delete:
                            db.session.delete(sp)
                        changes.append(f"Мощности станции ID={station_id} удалены, так как все агрегаты были удалены")

                db.session.commit()

                if changes:
                    log_to_db(user, f"Агрегаты удалены на станции {station.name}", details="; ".join(changes), entity_type="station", entity_id=station.id)
                    flash("Выбранные агрегаты и связанные данные были удалены!", "success")

            if form_machines.validate_on_submit():
                for machine in station.machines:
                    fuel_so_key = f"fuel_so_{machine.id}"
                    gen_company_key = f"id_gen_company_{machine.id}"
                    new_note_key = f"note_{machine.id}"

                    new_fuel_so = request.form.get(fuel_so_key, "").strip()
                    new_gen_company_id = request.form.get(gen_company_key, type=int)
                    new_note = request.form.get(new_note_key, "").strip()

                    if machine.fuel_so != new_fuel_so:
                        changes.append(f"Агрегат {machine.machine_number}: Топливо {machine.fuel_so} → {new_fuel_so}")
                        machine.fuel_so = new_fuel_so

                    if machine.note != new_note:
                        changes.append(f"Агрегат {machine.machine_number}: Примечание {machine.note} → {new_note}")
                        machine.note = new_note

                    # Обновляем собственника агрегата
                    if new_gen_company_id:
                        new_gen_company = db.session.query(GenCompany).filter_by(id=new_gen_company_id).first()
                        if new_gen_company:
                            old_gen_company_name = machine.gen_company.name if machine.gen_company else "не указано"
                            if machine.gen_company is None or machine.gen_company.id != new_gen_company_id:
                                changes.append(f"Агрегат {machine.machine_number}: Собственник {old_gen_company_name} → {new_gen_company.name}")
                                machine.gen_company = new_gen_company
                        else:
                            flash(f"Ошибка: выбранная генерирующая компания не существует!", "danger")

                db.session.commit()

                if changes:
                    log_to_db(user, f"Обновлены агрегаты станции {station.name}", details="; ".join(changes), entity_type="station", entity_id=station.id)
                    flash("Изменения агрегатов сохранены!", "success")

                return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))

    # Timing: measure preparation time right before render
    before_render_at = time.perf_counter()

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
        station_logs=(
            db.session.query(Log)
            .filter(
                or_(
                    Log.action.ilike(f"%станции {station.name}%"),
                    Log.details.ilike(f"%station_id={station.id}%")
                )
            )
            .filter(~Log.action.ilike("%Открыта страница электростанции%"))
            .order_by(Log.timestamp.desc())
            .limit(200)
            .all()
        ),
        # Pass backend timings to the template (fallback to 0 if not computed)
        backend_prepare_ms=int((before_render_at - route_started_at) * 1000),
    )

    after_render_at = time.perf_counter()

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

    return response


@station_bp.route("/station_details_tbody/<int:station_id>", methods=["GET"])
@login_required
def station_details_tbody(station_id):
    """Возвращает только tbody таблицы агрегатов для ленивой подгрузки.

    Параметры:
    - start_year, end_year, rounding_digits (query params)
    """
    start_year = request.args.get("start_year", Config.START_YEAR, type=int)
    end_year = request.args.get("end_year", Config.END_YEAR, type=int)
    rounding_digits = request.args.get("rounding_digits", 0, type=int)

    # Обновляем кэш раз в минуту через bucket
    cache_bucket = int(time.time() // 120)

    html = _render_machines_tbody_cached(station_id, start_year, end_year, rounding_digits, cache_bucket)
    resp = make_response(html)
    resp.headers["Cache-Control"] = "public, max-age=120"
    return resp


@lru_cache(maxsize=128)
def _render_machines_tbody_cached(station_id: int, start_year: int, end_year: int, rounding_digits: int, cache_bucket: int) -> str:
    """Кэшируемый рендер tbody (cache_bucket обеспечивает инвалидацию раз в минуту)."""
    # Минимально необходимая предзагрузка
    station = (
        db.session.query(Station)
        .options(
            selectinload(Station.machines).joinedload(Machine.gen_company),
            selectinload(Station.machines).joinedload(Machine.station_type),
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

    # Сортируем агрегаты по группе, топливу и числовому номеру
    if station and station.machines:
        def _machine_sort_key(m):
            group_key = (m.machine_group or '').lower()
            fuel_key = (m.fuel_so or '').lower()
            num_key = float('inf')
            try:
                if m.machine_number:
                    s = str(m.machine_number).strip()
                    if s.isdigit():
                        num_key = int(s)
            except Exception:
                num_key = float('inf')
            return (group_key, fuel_key, num_key)
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
    )
