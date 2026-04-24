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
from typing import Optional
from app.logs.services.logging_service import log_to_db
from flask_login import login_required, current_user
from flask import session
from app.generation.forms.station_forms import StationFilterForm
from app.generation.forms.machine_forms import MachineFilterSmallForm
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
    _apply_machine_display_names,
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
        formatted_log = {
            'date': ts_msk.strftime('%Y-%m-%d') if ts_msk else '',
            'time': ts_msk.strftime('%H:%M:%S') if ts_msk else '',
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


def _load_station_with_version(query_factory, requested_version_id):
    """
    Возвращает станцию и фактический ID версии (None, если базовая).
    Без fallback: если запись отсутствует в запрошенной версии, возвращает None.
    """
    def _apply_version_filter(q, version_id):
        if not hasattr(Station, "database_version_id"):
            return q
        if version_id is None:
            return q.filter(Station.database_version_id.is_(None))
        return q.filter(Station.database_version_id == version_id)

    # Если запрашивается базовая версия (None)
    if requested_version_id is None:
        station = _apply_version_filter(query_factory(), None).first()
        if station:
            return station, station.database_version_id
        return None, None

    # Ищем станцию в запрошенной версии
    station = _apply_version_filter(query_factory(), requested_version_id).first()
    if station:
        return station, station.database_version_id

    return None, requested_version_id


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


@station_bp.route("/station_details/<int:station_id>", methods=["GET", "POST"])
@login_required
@handle_stale_data
def station_details(station_id):
    """Маршрут для отображения сведений об электростанции с логированием изменений."""

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
                # Прямая связь станции с РЭС + ОЭС + тип энергосистемы
                joinedload(Station.regional_energy_system_obj)
                    .joinedload(RegionalEnergySystem.union_energy_system)
                    .joinedload(UnionEnergySystem.energy_system_type),
                # Остальные связи станции
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

    station, station_version_id = _load_station_with_version(_station_query, current_version_id)
    
    if not station:
        abort(404)
    
    station.machines = _filter_items_by_version(station.machines, station_version_id)
    
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

    # Отложенное логирование открытия страницы - только для GET запросов
    # Выполняется после основной логики, чтобы не блокировать обработку
    if request.method == "GET":
        regional_district_name = station.regional_district.name if station and station.regional_district else "не указано"
        log_to_db(user, f"Открыта страница электростанции {station.name} ({regional_district_name})", entity_type="station", entity_id=station.id)

    form = StationFilterForm()
    form_machines = MachineFilterSmallForm()

    # Получение параметров запроса с дефолтными значениями
    start_year = request.args.get("start_year", get_filter_start_year(), type=int)
    end_year = request.args.get("end_year", get_filter_end_year(), type=int)
    machine_ids_to_delete = request.form.getlist("machines_delete[]", type=int)
    
    # Определяем, какая форма была отправлена
    submitted_keys = set(request.form.keys())
    print(f"[DEBUG] Отправленные поля формы: {submitted_keys}")
    is_station_form = any(k in submitted_keys for k in {"name", "id_condition_type", "id_station_type", "id_station_group", "id_energy_unit", "id_regional_district", "location", "note"})
    # Признаки формы агрегатов: удаление/поля агрегатов/примечание агрегата/собственник агрегата
    is_machines_form = ("machines_delete[]" in submitted_keys) or any(
        k.startswith(prefix)
        for k in submitted_keys
        for prefix in ("fuel_so_", "id_gen_company_", "note_")
    )
    print(f"[DEBUG] is_station_form = {is_station_form}, is_machines_form = {is_machines_form}")

    # Используем кэшированные справочники для оптимизации
    form_data = CacheService.get_station_details_form_data()
    condition_types = form_data['condition_types']
    station_groups = form_data['station_groups']
    gen_companies = form_data['gen_companies']

    # Оптимизированный пересчет мощностей - только если нужно
    if request.method == "GET":
        recalculate_station_power(station, start_year, end_year)

    # Получаем мощности по годам из StationPower
    station_power_query = (
        StationPower.query.filter_by(id_station=station.id)
        .filter(
            StationPower.year_number >= start_year,
            StationPower.year_number <= end_year
        )
    )
    station_power_query = filter_by_explicit_db_version(
        station_power_query,
        StationPower,
        station_version_id,
    )
    station.powers_by_year = {
        sp.year_number: {
            "p_ust": sp.p_ust,
            "p_ogr": sp.p_ogr,
            "p_rasp": sp.p_rasp
        }
        for sp in station_power_query.all()
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

    # Список (id, name) — без ORM, чтобы избежать DetachedInstanceError при кэше
    regional_energy_system_choices = get_regional_energy_system_choices()
    regional_energy_system_names = get_regional_energy_systems_map()

    # Карта для автоподстановки ОЭС и типа энергосистемы по выбранной РЭС
    res_auto_map = {}
    res_to_ues = get_res_to_ues_id_map()
    res_to_est = get_res_to_est_id_map()
    for res_id, _res_name in regional_energy_system_choices:
        ues_id = res_to_ues.get(res_id)
        est_id = res_to_est.get(res_id)
        ues_name = union_energy_system_names.get(ues_id, "Нет данных") if ues_id else "Нет данных"
        est_name = energy_system_type_names.get(est_id, "Нет данных") if est_id else "Нет данных"
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

    # Для форм используем choices в версии станции (иначе валидатор ругается на "невалидный выбор")
    form.id_station_type.choices = _get_versioned_choices(StationType, StationType.id, station_version_id)
    form.id_energy_unit.choices = _get_versioned_choices(EnergyUnit, EnergyUnit.id, station_version_id)

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
        # Для energy_unit и station_type оставляем None как есть, 
        # так как теперь coerce возвращает None для пустых значений

    if request.method == "POST":
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
                    # Дополнительно: если вместе с формой агрегатов пришли поля станции (например, id_energy_unit), сохраняем их тоже
                    try:
                        if any(k in submitted_keys for k in {"name", "id_condition_type", "id_station_type", "id_station_group", "id_energy_unit", "id_regional_district", "location", "note"}):
                            # Привязываем POST-данные к форме станции и валидируем
                            form.process(formdata=request.form)
                            if not form.validate():
                                print("Ошибки в form (в составе machinesForm):", form.errors)
                            else:
                                station_changes = update_station_from_form_service(user, station, form, regional_district_list)
                                if station_changes:
                                    flash("Изменения в электростанции успешно обновлены!", "success")
                                    invalidate_cache('station_full', station_id=station.id)
                                    invalidate_cache_pattern('station_list:*')
                    except Exception as e:
                        import traceback
                        traceback.print_exc()
                        flash(f"Ошибка при обновлении полей станции: {e}", "danger")
                    return redirect(url_for("station_bp.station_details", station_id=station.id, **request.args))
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    flash(f"Ошибка при обновлении агрегатов: {e}", "danger")
                    # При ошибке продолжаем выполнение для показа формы с ошибками
        
        # Обработка отправки основной формы станции
        # ВАЖНО: Обрабатываем только если НЕ было удаления агрегатов
        elif is_station_form:
            # Привязываем форму к POST-данным, иначе поля (в т.ч. id_energy_unit) остаются пустыми
            form.process(formdata=request.form)
            print(f"[DEBUG] Форма станции отправлена. id_energy_unit.data = {form.id_energy_unit.data}, id_station_type.data = {form.id_station_type.data}")
            print(f"[DEBUG] Валидация формы: validate() = {form.validate()}, validate_on_submit() = {form.validate_on_submit()}")
            if not form.validate():
                print("Ошибки в form:", form.errors)
                print(f"[DEBUG] Данные формы: {form.data}")
                print(f"[DEBUG] CSRF токен: {form.csrf_token.data}")
                print(f"[DEBUG] CSRF токен из request: {request.form.get('csrf_token')}")
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
        # Используем только entity_type + entity_id (индексированные поля).
        # Log.details.ilike("%station_id=...") вызывает полное сканирование таблицы и занимает 100+ сек.
        # Логи по станции пишутся с entity_type="station", entity_id=station.id.
        logs_filter = and_(
            Log.entity_type == "station",
            Log.entity_id == station.id,
        )
        station_logs_raw = (
            db.session.query(Log)
            .filter(logs_filter)
            .filter(~Log.action.ilike("%Открыта страница электростанции%"))
            .order_by(Log.timestamp.desc())
            .limit(20)  # Ограничиваем количество для ускорения
            .all()
        )
        station_logs_formatted = _format_logs_for_display(station_logs_raw)
    print(f"[DIAG] Логи: {(time.perf_counter() - t0)*1000:.0f} мс")
    
    logs_count = len(station_logs_formatted)
    
    # Кнопка «Добавить агрегат» и редактирование доступны admin, generation-admin, generation-editor
    edit_roles = ['admin', 'generation-admin', 'generation-editor', 'generation_admin', 'generation_editor']
    can_edit = current_user.is_authenticated and any(role in current_user.role_names for role in edit_roles)
    # Создание группы оборудования — как в fuel_bp.add_equipment_group (только администраторы)
    can_add_equipment_group = current_user.is_authenticated and getattr(
        current_user, "has_admin", False
    )

    # Группы оборудования станции (по версии)
    target_version_id = current_version_id if current_version_id is not None else station_version_id

    t1 = time.perf_counter()
    try:
        from app.fuel.services.stations.stations_equipment_groups_services import (
            build_station_equipment_groups_v2,
        )
        v2_groups_map = build_station_equipment_groups_v2([station])
        v2_info = v2_groups_map.get(station.id) or {"groups": [], "total_rows": 0}
        station.equipment_group_v2_groups = v2_info["groups"]
        station.equipment_group_v2_total_rows = v2_info["total_rows"]
    except Exception as exc:
        current_app.logger.warning(
            f"[station_details] Failed to build v2 equipment groups: {exc}"
        )
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
    html = render_template(
        "generation/stations/station_details.html",
        form=form,
        form_machines=form_machines,
        station=station,
        rounding_digits=rounding_digits,
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
        can_add_equipment_group=can_add_equipment_group,
        initial_machines_tbody_html=initial_machines_tbody_html,
        year_features=year_features,
        # Pass backend timings to the template (fallback to 0 if not computed)
        backend_prepare_ms=int((before_render_at - route_started_at) * 1000),
        res_auto_map=res_auto_map,
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
    """AJAX endpoint для загрузки всех логов станции."""
    from flask import jsonify
    
    current_version_id = get_current_db_version_id()

    def _station_query():
        return Station.query.filter_by(id=station_id)

    station, _ = _load_station_with_version(_station_query, current_version_id)
    if not station:
        abort(404)
    
    # Получаем параметр offset для пагинации
    offset = request.args.get("offset", 0, type=int)
    limit = request.args.get("limit", 150, type=int)  # По умолчанию загружаем еще 150
    
    # Используем только entity_type + entity_id (индексированные поля).
    # Log.details.ilike("%station_id=...") вызывает полное сканирование таблицы.
    logs_filter = and_(
        Log.entity_type == "station",
        Log.entity_id == station.id,
    )
    logs_query = (
        db.session.query(Log)
        .filter(logs_filter)
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


@station_bp.route(
    "/station_details/<int:station_id>/equipment_groups_v2/<int:equipment_group_id>/rename",
    methods=["POST"],
)
@login_required
@handle_stale_data
def rename_station_equipment_group_v2(station_id, equipment_group_id):
    """Переименование группы оборудования на странице станции."""
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

    # Проверяем, что группа принадлежит этой станции
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
        station_external_code = (station.external_code or "").strip()
        if not station_external_code:
            flash("У станции отсутствует external_code, невозможно применить изменения во всех версиях.", "warning")
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
    """Удаление «пустой» привязки типа группы оборудования к станции (без группы в топливе)."""
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
                "Привязка типа группы оборудования к станции удалена"
                + (" во всех версиях БД." if all_versions else "."),
                "success",
            )
            log_to_db(
                current_user,
                "Удаление привязки типа группы оборудования к станции (EquipmentGroupSetStation)",
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
    rounding_digits = request.args.get("rounding_digits", 0, type=int)

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
        station_id: ID станции
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

    station, station_version_id = _load_station_with_version(_station_tbody_query, version_id)
    if not station:
        abort(404)

    # Загружаем мощности и топливо только в нужном диапазоне лет, батчем по всем машинам
    machine_ids = [m.id for m in (station.machines or [])]
    powers_by_year = {}
    powers_by_machine_year = {}
    fuels_by_machine_year = {}

    if machine_ids:
        # Суммируем в Decimal, чтобы избежать артефактов float (18,779999999998)
        _agg_decimal = defaultdict(lambda: {"p_ust": Decimal(0), "p_ogr": Decimal(0), "p_rasp": Decimal(0)})
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
            agg = _agg_decimal[y]
            if mp.p_ust:
                agg["p_ust"] += Decimal(str(mp.p_ust))
            if mp.p_ogr:
                agg["p_ogr"] += Decimal(str(mp.p_ogr))
            if mp.p_rasp:
                agg["p_rasp"] += Decimal(str(mp.p_rasp))
        # Итоги оставляем как Decimal — форматирование выполняет шаблон
        for y, data in _agg_decimal.items():
            powers_by_year[y] = {
                "p_ust": data["p_ust"],
                "p_ogr": data["p_ogr"],
                "p_rasp": data["p_rasp"],
            }

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

    # Отображаемое название: как на machine_details — MachineName за год версии, иначе machine_name; при отличии в плане — "<текущ.> (<план>)"
    _apply_machine_display_names(station.machines)
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

    from app.common.services.help_services import format_decimal_for_display

    def format_decimal_with_rounding(value):
        return format_decimal_for_display(value, digits=rounding_digits)

    gen_company_choices = [(0, "не указано")] + [
        (gc.id, gc.name) for gc in get_gen_company_list_full()
    ]

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
