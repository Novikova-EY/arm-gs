from config import Config
from app.extensions import db
import traceback
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from sqlalchemy.orm.attributes import flag_modified
from flask import flash,request, render_template, request, flash, redirect, url_for
from app.logs.services.logging_service import log_to_db
from app.common.services.tranzaction_services import (
    _commit_with_retry,
    _locked_get,
    no_autoflush,
)
from app.generation.models.station.station_model import Station
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_tes_type_model import MachineTesType
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.machine.machine_fuel_model import MachineFuel
from app.generation.models.pgu_machine.pgu_machine_power_model import PGUMachinePower
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.generation.models.document.document_model import Document
from app.refdata.models.energy_systems.energy_area_model import EnergyArea
from app.refdata.models.refdata_for_stations.condition_type_model import ConditionType
from app.refdata.models.refdata_for_stations.machine.tes_machine_type_model import TesMachineType
from app.refdata.models.refdata_for_stations.machine.tes_type_model import TesType
from app.refdata.models.refdata_for_stations.machine.machine_type_model import MachineType
from app.refdata.models.refdata_for_stations.machine.pgu_tes_machine_type_model import PGUTesMachineType
from app.refdata.models.gen_companies.gen_company_model import GenCompany
from app.refdata.models.fuels.fuel_model import Fuel
from app.refdata.models.years.year_model import Year
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroup
from app.refdata.models.fuels.station_equpment_group_model import StationEquipmentGroup
from app.generation.forms.machine_forms import MachineFilterForm, EditMachineForm, PGUMachineFilterForm

from app.generation.services.station_services.station_services import (
    recalculate_station_power,
    get_machine_by_id,
    get_station_by_id,
    clear_station_aggregation_cache,
)
from app.common.services.help_services import (
    convert_to_date,
    rounded_decimal,
    format_decimal_for_display,
)
from app.common.services.get_services.years.years_get_services import (
    get_year_feature_dict,
)
from app.common.services.choices_cache_service import choices_cache
from app.common.services.database_version_filter import set_db_version_on_create, filter_by_db_version
from app.common.services.cache_services import CacheService

@no_autoflush
def handle_machine_get(station_id, machine_id, start_year, end_year, rounding_digits):
    perf_start = time.perf_counter()
    perf_last = perf_start
    perf_segments = []

    def perf_mark(stage: str):
        nonlocal perf_last
        now = time.perf_counter()
        perf_segments.append((stage, now - perf_last))
        perf_last = now

    # Оптимизированная загрузка станции с связанными данными
    station = Station.query.options(
        db.joinedload(Station.regional_district)
    ).get_or_404(station_id)
    perf_mark("station_load")
    
    # Проверяем, создается ли новый агрегат
    if machine_id == 0:
        machine = None
    else:
        # Оптимизированная загрузка агрегата с связанными данными (eager loading коллекций)
        machine = Machine.query.options(
            db.joinedload(Machine.condition_type),
            db.joinedload(Machine.gen_company),
            db.joinedload(Machine.machine_type),
            db.joinedload(Machine.tes_machine_type),
            db.joinedload(Machine.equipment_group),
            db.joinedload(Machine.station_equipment_group).joinedload(StationEquipmentGroup.equipment_group),
            db.joinedload(Machine.machine_powers),
            db.joinedload(Machine.machine_fuels),
            db.joinedload(Machine.machine_tes_types),
        ).get_or_404(machine_id)

    # Оптимизированная загрузка годов одним запросом
    years = Year.query.filter(Year.number >= start_year, Year.number <= end_year).all()
    year_dict = {y.number: y for y in years}
    year_features = get_year_feature_dict()
    perf_mark("years_load")
    
    # Устанавливаем year вручную для всех machine_powers, machine_fuels, machine_tes_types
    if machine is not None:
        # Собираем все year_number из machine_powers, machine_fuels, machine_tes_types
        year_numbers_for_machine = set()
        for mp in machine.machine_powers:
            if mp.year_number:
                year_numbers_for_machine.add(mp.year_number)
        for mf in machine.machine_fuels:
            if mf.year_number:
                year_numbers_for_machine.add(mf.year_number)
        for mt in machine.machine_tes_types:
            if mt.year_number:
                year_numbers_for_machine.add(mt.year_number)
        
        # Загружаем только нужные годы
        if year_numbers_for_machine:
            missing_years = year_numbers_for_machine - set(year_dict.keys())
            if missing_years:
                missing_years_list = Year.query.filter(Year.number.in_(missing_years)).all()
                for y in missing_years_list:
                    year_dict[y.number] = y
        
        # Устанавливаем year
        for mp in machine.machine_powers:
            if mp.year_number and mp.year_number in year_dict:
                mp.year = year_dict[mp.year_number]
        for mf in machine.machine_fuels:
            if mf.year_number and mf.year_number in year_dict:
                mf.year = year_dict[mf.year_number]
        for mt in machine.machine_tes_types:
            if mt.year_number and mt.year_number in year_dict:
                mt.year = year_dict[mt.year_number]

    # Если это новый агрегат, создаем пустые словари
    if machine is None:
        machine_powers = {}
        machine_fuels = {}
        machine_tes_types = {}
    else:
        # Фильтруем записи с None.year для предотвращения AttributeError
        # Логируем записи с проблемами для отладки
        for mp in machine.machine_powers:
            if mp.year is None:
                print(f"[WARNING] MachinePower ID={mp.id} has None.year for machine_id={mp.id_machine}")
        
        machine_powers = {mp.year.number: mp for mp in machine.machine_powers if mp.year is not None}
        machine_fuels = {mf.year.number: mf for mf in machine.machine_fuels if mf.year is not None}
        machine_tes_types = {mt.year.number: mt for mt in machine.machine_tes_types if mt.year is not None}

    main_form = MachineFilterForm(prefix="main_", obj=machine)
    advanced_form = EditMachineForm(prefix="adv_")
    perf_mark("forms_init")

    _fill_main_form_choices(main_form)
    # _fill_advanced_form_choices(advanced_form) - убрано, так как choices устанавливаются ниже

    pgu_machines_form = PGUMachineFilterForm(prefix="pgu_")
    # Для нового агрегата ПГУ машин нет
    if machine is None:
        pgu_machines = []
    else:
        # Оптимизированная загрузка ПГУ агрегатов
        pgu_machines_query = PGUMachine.query.options(
            db.joinedload(PGUMachine.condition_type),
            db.joinedload(PGUMachine.tes_machine_type)
        ).filter_by(id_parent_machine=machine.id)

        # Применяем фильтры, если они выбраны:
        if not choices_cache.is_empty_value(pgu_machines_form.id_condition_type.data):
            pgu_machines_query = pgu_machines_query.filter_by(id_condition_type=pgu_machines_form.id_condition_type.data)

        if not choices_cache.is_empty_value(pgu_machines_form.id_tes_machine_type.data):
            pgu_machines_query = pgu_machines_query.filter_by(id_tes_machine_type=pgu_machines_form.id_tes_machine_type.data)

        if not choices_cache.is_empty_value(pgu_machines_form.id_parent_machine.data):
            pgu_machines_query = pgu_machines_query.filter_by(id_parent_machine=pgu_machines_form.id_parent_machine.data)

        pgu_machines = pgu_machines_query.order_by(PGUMachine.machine_name).all()
    perf_mark("pgu_load")

    if main_form.id_condition_type.data is None:
        main_form.id_condition_type.data = choices_cache.EMPTY_VALUE_ID
    if main_form.id_gen_company.data is None:
        main_form.id_gen_company.data = choices_cache.EMPTY_VALUE_ID
    if main_form.id_machine_type.data is None:
        main_form.id_machine_type.data = choices_cache.EMPTY_VALUE_ID
    if main_form.id_tes_machine_type.data is None:
        main_form.id_tes_machine_type.data = choices_cache.EMPTY_VALUE_ID

    tes_type_choices = choices_cache.get_choices(TesType, TesType.id)
    fuel_choices = choices_cache.get_choices(Fuel, Fuel.id)
    perf_mark("choices_fetch")

    # В GET больше НЕ создаем отсутствующие записи в БД — только читаем и заполняем форму

    # Заполняем форму
    for year_num in range(start_year, end_year + 1):
        # Для нового агрегата используем пустые значения
        if machine is None:
            p_ust = p_ogr = p_rasp = None
            id_tes_type = 0
            id_fuel = 0
        else:
            mp = machine_powers.get(year_num)
            mt = machine_tes_types.get(year_num)
            mf = machine_fuels.get(year_num)
            p_ust = mp.p_ust if mp else None
            p_ogr = mp.p_ogr if mp else None
            p_rasp = mp.p_rasp if mp else None
            id_tes_type = (mt.id_tes_type if (mt and mt.id_tes_type is not None) else 0)
            id_fuel = (mf.id_fuel if (mf and mf.id_fuel is not None) else 0)

        power_entry = advanced_form.powers.append_entry()
        power_entry.year.data = year_num
        power_entry.p_ust.data = p_ust
        power_entry.p_ogr.data = p_ogr
        power_entry.p_rasp.data = p_rasp

        tes_entry = advanced_form.tes_types.append_entry()
        tes_entry.year.data = year_num
        tes_entry.tes_type.data = id_tes_type

        fuel_entry = advanced_form.fuels.append_entry()
        fuel_entry.year.data = year_num
        fuel_entry.fuel_type.data = id_fuel

    # Устанавливаем choices для всех записей после создания всех entries
    print(f"[DEBUG] Количество tes_types entries: {len(advanced_form.tes_types.entries)}")
    print(f"[DEBUG] Количество fuels entries: {len(advanced_form.fuels.entries)}")
    
    # Заполняем choices для всех entries через единую функцию
    _fill_advanced_form_choices(advanced_form)
    perf_mark("advanced_fill")

    # В GET не коммитим изменения — исключаем дорогостоящие записи и блокировки

    # Оптимизированная загрузка документов - только id и name с фильтрацией по версии
    all_documents = choices_cache.get_choices(Document, Document.name)
    # Преобразуем обратно в объекты для совместимости с шаблоном
    all_documents = [Document(id=doc_id, name=doc_name) for doc_id, doc_name in all_documents]
    perf_mark("documents_fetch")

    total_elapsed = time.perf_counter() - perf_start
    segments_repr = ", ".join(f"{name}={duration:.2f}s" for name, duration in perf_segments)
    print(f"[PERF] machine_details GET station={station_id} machine={machine_id} total={total_elapsed:.2f}s | {segments_repr}")

    return {
        "start_year": start_year,
        "end_year": end_year,
        "rounding_digits": rounding_digits,
        "main_form": main_form,
        "advanced_form": advanced_form,
        "station": station,
        "machine": machine,
        "year_features": year_features,
        "pgu_machines_form": pgu_machines_form,
        "pgu_machines": pgu_machines,
        "year_features": year_features,
        "all_documents": all_documents,
    }


def _get_or_create_station_equipment_group(station_id, equipment_group_id):
    if not station_id or not equipment_group_id:
        return None
    seg = StationEquipmentGroup.query.filter_by(
        id_station=station_id,
        id_equipment_group=equipment_group_id,
    ).first()
    if seg is None:
        seg = StationEquipmentGroup(
            id_station=station_id,
            id_equipment_group=equipment_group_id,
        )
        set_db_version_on_create(seg)
        db.session.add(seg)
        db.session.flush()
    return seg


def _validate_power_ranges(advanced_form, formdata):
    has_errors = False
    for power_form in advanced_form.powers:
        for field_name in ("p_ust", "p_ogr", "p_rasp"):
            field = getattr(power_form, field_name)
            raw_value = formdata.get(field.name)
            orig_value = formdata.get(f"{field.name}_orig")
            current = to_decimal(raw_value)
            original = to_decimal(orig_value)

            if current != original and current is not None and current < 0:
                field.errors.append("Number must be at least 0.")
                has_errors = True

    return not has_errors


@no_autoflush
def handle_machine_post(station_id, machine_id, form_data, user, start_year, end_year, rounding_digits):
    from werkzeug.datastructures import MultiDict

    normalized = MultiDict(form_data)
    for key, value in list(normalized.items()):
        if isinstance(value, str):
            if value.strip() in {"\u2014", "-", ""}:
                normalized[key] = ""
            # Не заменяем запятые на точки в поле change_document (проверяем окончание ключа)
            elif "," in value and not key.endswith("change_document"):
                normalized[key] = value.replace(",", ".")

    station = get_station_by_id(station_id)
    
    # Проверяем, создается ли новый агрегат
    is_new = machine_id == 0
    if is_new:
        machine = None
    else:
        machine = get_machine_by_id(machine_id)

    # Если поле "Организация-собственник" не пришло в POST (иногда Select2 не отправляет),
    # подставляем текущее значение агрегата, чтобы избежать ложной ошибки валидации.
    if machine is not None and "main_id_gen_company" not in normalized:
        if machine.id_gen_company is not None:
            normalized["main_id_gen_company"] = str(machine.id_gen_company)

    main_form = MachineFilterForm(formdata=normalized, prefix="main_")
    advanced_form = EditMachineForm(formdata=normalized, prefix="adv_")
    pgu_machines_form = PGUMachineFilterForm(formdata=normalized, prefix="pgu_")
    
    year_features = get_year_feature_dict()
    
    # Проверка версии из формы для предотвращения concurrent updates (только для существующих агрегатов)
    if not is_new and machine:
        form_version = request.form.get('version', type=int)
        print(f"[VERSION CHECK] Machine ID={machine.id}, form_version={form_version}, db_version={machine.version if hasattr(machine, 'version') else 'NO VERSION ATTR'}")
        
        if form_version and hasattr(machine, 'version') and machine.version != form_version:
            flash('Данные агрегата были изменены другим пользователем. Пожалуйста, обновите страницу.', 'warning')
            log_to_db(user, f"Обнаружен конфликт версий при обновлении агрегата №{machine.machine_number} (ожидаемая: {form_version}, текущая: {machine.version})", entity_type="machine", entity_id=machine.id)
            return redirect(url_for("station_bp.machine_details", 
                                    station_id=station.id, 
                                    machine_id=machine.id,
                                    start_year=start_year, 
                                    end_year=end_year, 
                                    rounding_digits=rounding_digits))

    _fill_main_form_choices(main_form)
    # Проверяем, нужно ли заполнять advanced_form choices
    print(f"[DEBUG] handle_machine_post: tes_types entries: {len(advanced_form.tes_types.entries)}")
    print(f"[DEBUG] handle_machine_post: fuels entries: {len(advanced_form.fuels.entries)}")
    # Всегда заполняем choices для вложенных полей перед validate, даже если entries уже есть
    _fill_advanced_form_choices(advanced_form)
    _fill_pgu_machines_form_choices(pgu_machines_form, machine_id=machine.id if machine else 0)

    pgu_ids_to_delete = request.form.getlist("pgu_machines_delete[]", type=int)

    # Удаляем ПГУ сразу, до валидации форм
    if pgu_ids_to_delete:
        pgu_to_delete = PGUMachine.query.filter(PGUMachine.id.in_(pgu_ids_to_delete)).all()
        deleted_names = []

        for pgu_machine in pgu_to_delete:
            try:
                # Блокируем запись для безопасного удаления
                locked_pgu = _locked_get(PGUMachine, pgu_machine.id)
                if locked_pgu:
                    for power in locked_pgu.pgu_machine_powers:
                        db.session.delete(power)
                    db.session.delete(locked_pgu)
                    deleted_names.append(locked_pgu.machine_name or f"ID={locked_pgu.id}")
            except Exception as e:
                flash(f"Ошибка при удалении ПГУ ID={pgu_machine.id}: {e}", "danger")
                log_to_db(
                    user, f"Ошибка удаления ПГУ ID={pgu_machine.id}", details=str(e),
                    entity_type="pgu_machine",
                    entity_id=pgu_machine.id)

        _commit_with_retry()
        # ВАЖНО: ПГУ влияет на агрегации/списки, поэтому чистим кэш после мутаций
        clear_station_aggregation_cache("after PGU delete")

        if deleted_names:
            log_to_db(user, f"Удаление ПГУ агрегатов на станции {station.name}", details="; ".join(deleted_names))
            flash("Выбранные ПГУ агрегаты успешно удалены!", "success")

        return redirect(url_for("station_bp.machine_details", 
                                station_id=station.id, 
                                machine_id=machine.id,
                                start_year=start_year, 
                                end_year=end_year, 
                                rounding_digits=rounding_digits))
    
    is_pgu_action = any([
        pgu_machines_form.id_pgu_machine.data,
        pgu_machines_form.machine_name.data,
        pgu_machines_form.machine_number.data
    ])

    main_valid = main_form.validate()
    adv_valid = advanced_form.validate()
    adv_valid = adv_valid and _validate_power_ranges(advanced_form, normalized)
    pgu_valid = pgu_machines_form.validate() if is_pgu_action else True

    if not (main_valid and adv_valid and pgu_valid):
        print("main_form.errors:", main_form.errors)
        print("advanced_form.errors:", advanced_form.errors)
        print("pgu_machines_form.errors:", pgu_machines_form.errors)
        print(f"[DEBUG] Ошибка валидации: tes_types entries: {len(advanced_form.tes_types.entries)}")
        print(f"[DEBUG] Ошибка валидации: fuels entries: {len(advanced_form.fuels.entries)}")
        flash(
            "Ошибка в заполнении формы. Обязательные поля: Название агрегата, Организация-собственник.",
            "danger",
        )
        # Оптимизированная загрузка документов - только id и name с фильтрацией по версии
        all_documents = choices_cache.get_choices(Document, Document.name)
        # Преобразуем обратно в объекты для совместимости с шаблоном
        all_documents = [Document(id=doc_id, name=doc_name) for doc_id, doc_name in all_documents]
        return render_template(
            "generation/stations/machine_details.html",
            start_year=start_year,
            end_year=end_year,
            rounding_digits=rounding_digits,
            main_form=main_form,
            advanced_form=advanced_form,
            pgu_machines_form=pgu_machines_form,
            station=station,
            machine=machine,
            year_features=year_features,
            all_documents=all_documents,
        )

    try:
        changes, pgu_changes = [], []

        with db.session.no_autoflush:
            # Создаем новый агрегат, если это новая запись
            if is_new:
                # Получаем обязательные поля из формы
                machine_number = main_form.machine_number.data or ""
                machine_name = main_form.machine_name.data or "Без названия"
                
                machine = Machine(
                    id_station=station_id,
                    machine_number=machine_number,
                    machine_name=machine_name
                )
                set_db_version_on_create(machine)
                db.session.add(machine)
                db.session.flush()  # Получаем ID для новой записи
            
            # Получаем кэшированные справочники для логирования
            condition_types = dict(choices_cache.get_choices(ConditionType, ConditionType.id))
            gen_companies = dict(choices_cache.get_choices(GenCompany, GenCompany.id))
            machine_types = dict(choices_cache.get_choices(MachineType, MachineType.id))
            tes_machine_types = dict(choices_cache.get_choices(TesMachineType, TesMachineType.id))
            equipment_groups = dict(choices_cache.get_choices(EquipmentGroup, EquipmentGroup.id))
            
            field_map = {
            "id_condition_type": lambda x: condition_types.get(x, "не указано") if x else "не указано",
            "id_gen_company": lambda x: gen_companies.get(x, "не указано") if x else "не указано",
            "id_machine_type": lambda x: machine_types.get(x, "не указано") if x else "не указано",
            "id_tes_machine_type": lambda x: tes_machine_types.get(x, "не указано") if x else "не указано",
            "id_equipment_group": lambda x: equipment_groups.get(x, "не указано") if x else "не указано",
            "machine_number": str,
            "machine_name": str,
            "note": lambda x: x or "не указано",
            "change_document": lambda x: x or "не указано",
            "machine_group": str,
        }

        # Список полей, которые являются внешними ключами и должны конвертировать 0 в None
        fk_fields = {'id_condition_type', 'id_gen_company', 'id_machine_type', 
                     'id_tes_machine_type', 'id_equipment_group'}
        
        for fld, to_str in field_map.items():
            old_v = getattr(machine, fld) if not is_new else None
            new_v = getattr(main_form, fld).data
            
            # Конвертируем 0 в None для полей внешних ключей
            if fld in fk_fields and choices_cache.is_empty_value(new_v):
                new_v = None
            
            if is_new:
                # Для нового агрегата пропускаем поля, которые уже установлены при создании
                if fld in ('machine_number', 'machine_name'):
                    # Поля уже установлены, только логируем
                    if new_v:
                        changes.append(f"{fld}: {to_str(new_v)}")
                else:
                    # Для остальных полей устанавливаем значения
                    if new_v:
                        changes.append(f"{fld}: {to_str(new_v)}")
                    setattr(machine, fld, new_v)
            else:
                # Для существующего агрегата проверяем изменения
                old_v_str = to_str(old_v)
                new_v_str = to_str(new_v)
                # Логируем только если строковые представления различаются
                if old_v_str != new_v_str:
                    changes.append(f"{fld}: {old_v_str} → {new_v_str}")
                    setattr(machine, fld, new_v)
                elif old_v != new_v:
                    # Если строки одинаковы, но значения разные, просто обновляем без логирования
                    setattr(machine, fld, new_v)

        # Синхронизируем station_equipment_group_id с выбранным типом оборудования
        seg = _get_or_create_station_equipment_group(
            station_id=machine.id_station,
            equipment_group_id=machine.id_equipment_group,
        )
        machine.station_equipment_group_id = seg.id if seg else None

        date_fields = [
            "date_exploitation", "date_commission_fact", "date_joining_expected", "date_joining_fact",
            "date_detatchment_fact", "date_decompressing_expected", "date_decompressing_fact",
            "date_modernization_expected", "date_relabing_fact", "date_update_fact",
        ]

        for fld in date_fields:
            raw_form_value = getattr(main_form, fld).data
            if fld in {"date_exploitation", "date_decompressing_expected", "date_modernization_expected"}:
                new_val = int(raw_form_value) if raw_form_value else None
            else:
                new_val = convert_to_date(raw_form_value)

            old_val = getattr(machine, fld) if not is_new else None
            old_val_str = old_val.strftime("%Y-%m-%d") if isinstance(old_val, (date, datetime)) else str(old_val) if old_val else None
            new_val_str = new_val.strftime("%Y-%m-%d") if isinstance(new_val, (date, datetime)) else str(new_val) if new_val else None

            if is_new:
                # Для нового агрегата просто устанавливаем значения
                if new_val:
                    changes.append(f"{fld}: {new_val_str}")
                setattr(machine, fld, new_val)
            else:
                # Для существующего агрегата проверяем изменения
                if old_val_str != new_val_str:
                    changes.append(f"{fld}: {old_val_str} → {new_val_str}")
                    setattr(machine, fld, new_val)

        # Для нового агрегата нужно flush, чтобы получить machine.id
        if is_new:
            db.session.flush()

        # Фильтруем записи с None.year для предотвращения AttributeError
        powers_map = {mp.year.number: mp for mp in machine.machine_powers if mp.year is not None}
        tes_map = {mt.year.number: mt for mt in machine.machine_tes_types if mt.year is not None}
        fuel_map = {mf.year.number: mf for mf in machine.machine_fuels if mf.year is not None}
        
        # Флаг для отслеживания изменений в связанных сущностях
        related_entities_changed = False
        
        # Получаем объекты Year для создания связанных записей
        years = Year.query.filter(Year.number >= start_year, Year.number <= end_year).all()
        year_dict = {y.number: y for y in years}

        for i, year_num in enumerate(range(start_year, end_year + 1)):
            # Проверяем только powers, так как это основная таблица для всех типов станций
            # tes_types и fuels могут быть пустыми для не-ТЭС станций
            if i >= len(advanced_form.powers):
                continue

            # Создаем записи, если их нет (для нового агрегата или недостающих годов)
            y_obj = year_dict.get(year_num)
            
            if year_num not in powers_map:
                mp = MachinePower(id_machine=machine.id, year=y_obj, year_number=year_num)
                set_db_version_on_create(mp)
                db.session.add(mp)
                powers_map[year_num] = mp
            
            if year_num not in tes_map:
                mt = MachineTesType(id_machine=machine.id, year=y_obj, year_number=year_num)
                set_db_version_on_create(mt)
                db.session.add(mt)
                tes_map[year_num] = mt
            
            if year_num not in fuel_map:
                mf = MachineFuel(id_machine=machine.id, year=y_obj, year_number=year_num)
                set_db_version_on_create(mf)
                db.session.add(mf)
                fuel_map[year_num] = mf

            mp, mt, mf = powers_map[year_num], tes_map[year_num], fuel_map[year_num]

            # Получаем raw значения из формы для определения, были ли поля изменены пользователем
            p_ust_raw = advanced_form.powers[i].p_ust.data
            p_ogr_raw = advanced_form.powers[i].p_ogr.data
            p_rasp_raw = advanced_form.powers[i].p_rasp.data
            
            # Конвертируем значения (пустые строки и специальные символы → None)
            p_ust_new = to_decimal(p_ust_raw)
            p_ogr_new = to_decimal(p_ogr_raw)
            p_rasp_new = to_decimal(p_rasp_raw)
            
            # Определяем, изменил ли пользователь поле:
            # - Если raw значение не пустое, считаем что пользователь ввел значение (даже если это "0")
            # - Если raw значение пустое, пользователь очистил поле
            user_modified_p_ogr = p_ogr_raw not in (None, '', '—', '-')
            user_modified_p_rasp = p_rasp_raw not in (None, '', '—', '-')
            
            # Для нового агрегата всегда используем значения из формы
            # Для существующего агрегата: если поле не изменено, оставляем старое значение
            if is_new:
                # Для нового агрегата используем значения из формы или 0
                p_ust = p_ust_new if p_ust_new is not None else Decimal(0)
                p_ogr = p_ogr_new if p_ogr_new is not None else Decimal(0)
                p_rasp = p_rasp_new if p_rasp_new is not None else Decimal(0)
            else:
                # Для существующего агрегата
                p_ust = p_ust_new if p_ust_new is not None else (mp.p_ust if mp.p_ust else Decimal(0))
                
                if user_modified_p_ogr:
                    p_ogr = p_ogr_new if p_ogr_new is not None else Decimal(0)
                else:
                    p_ogr = mp.p_ogr if mp.p_ogr is not None else Decimal(0)
                    
                if user_modified_p_rasp:
                    p_rasp = p_rasp_new if p_rasp_new is not None else Decimal(0)
                else:
                    p_rasp = mp.p_rasp if mp.p_rasp is not None else Decimal(0)
            
            # Передаем флаги в автозаполнение, чтобы не перезаписывать значения, введенные пользователем
            p_ust, p_ogr, p_rasp = autofill_powers_if_possible_decimal(
                p_ust, p_ogr, p_rasp, year_num,
                skip_ogr=user_modified_p_ogr,
                skip_rasp=user_modified_p_rasp
            )

            for attr, val in (("p_ust", p_ust), ("p_ogr", p_ogr), ("p_rasp", p_rasp)):
                old_val = getattr(mp, attr)
                
                # Для нового агрегата всегда записываем значения
                if is_new:
                    setattr(mp, attr, val)
                    flag_modified(mp, attr)
                    if val and val > 0:  # Логируем только ненулевые значения
                        changes.append(f"{attr}: {year_num} год - {format_decimal_for_display(val)}")
                    related_entities_changed = True
                else:
                    # Для существующего агрегата проверяем изменения
                    if not is_same_decimal(old_val, val):
                        setattr(mp, attr, val)
                        flag_modified(mp, attr)
                        changes.append(f"{attr}: {year_num} год - {format_decimal_for_display(old_val)} → {format_decimal_for_display(val)}")
                        related_entities_changed = True

            # Получаем значения типов ТЭС и топлива только если формы существуют
            # Для не-ТЭС станций эти формы могут быть пустыми
            new_tt = None
            new_fuel = None
            
            if i < len(advanced_form.tes_types):
                new_tt = advanced_form.tes_types[i].tes_type.data
                if choices_cache.is_empty_value(new_tt):
                    new_tt = None
                    
            if i < len(advanced_form.fuels):
                new_fuel = advanced_form.fuels[i].fuel_type.data
                if choices_cache.is_empty_value(new_fuel):
                    new_fuel = None

            # Обрабатываем типы ТЭС и топливо только для ТЭС станций
            # Распознаем ТЭС по id или по названию типа станции
            try:
                st_name = (station.station_type.name or '').strip().lower() if station.station_type else ''
            except Exception:
                st_name = ''
            is_tes_station = (st_name == 'тэс')
            if is_tes_station:
                # Получаем кэшированные справочники для ТЭС
                tes_types = dict(choices_cache.get_choices(TesType, TesType.id))
                fuels = dict(choices_cache.get_choices(Fuel, Fuel.id))
                
                if is_new:
                    # Для нового агрегата просто устанавливаем значения
                    mt.id_tes_type = new_tt
                    if new_tt is not None:
                        new_tes_name = tes_types.get(new_tt, f"[{new_tt}]")
                        changes.append(f"Тип ТЭС: {year_num} год - {new_tes_name}")
                    
                    mf.id_fuel = new_fuel
                    if new_fuel is not None:
                        new_fuel_name = fuels.get(new_fuel, f"[{new_fuel}]")
                        changes.append(f"Топливо: {year_num} год - {new_fuel_name}")
                    
                    related_entities_changed = True
                else:
                    # Для существующего агрегата проверяем изменения
                    if new_tt is not None and mt.id_tes_type != new_tt:
                        old_tes_name = tes_types.get(mt.id_tes_type, "не указано") if mt.id_tes_type else "не указано"
                        new_tes_name = tes_types.get(new_tt, "не указано") if new_tt else "не указано"
                        # Логируем только реальные изменения (исключаем не указано → не указано и идентичные названия)
                        if (old_tes_name or '').strip().lower() != (new_tes_name or '').strip().lower():
                            changes.append(f"Тип ТЭС: {year_num} год - {old_tes_name} → {new_tes_name}")
                        mt.id_tes_type = new_tt
                        related_entities_changed = True

                    if new_fuel is not None and mf.id_fuel != new_fuel:
                        old_fuel_name = fuels.get(mf.id_fuel, "не указано") if mf.id_fuel else "не указано"
                        new_fuel_name = fuels.get(new_fuel, "не указано") if new_fuel else "не указано"
                        # Логируем только реальные изменения (исключаем не указано → не указано и идентичные названия)
                        if (old_fuel_name or '').strip().lower() != (new_fuel_name or '').strip().lower():
                            changes.append(f"Топливо: {year_num} год - {old_fuel_name} → {new_fuel_name}")
                        mf.id_fuel = new_fuel
                        related_entities_changed = True
        
        # Если изменились связанные сущности, обновляем Machine для инкремента version
        if related_entities_changed:
            from sqlalchemy.sql import func
            machine.updated_at = func.now()
            flag_modified(machine, 'updated_at')

        if is_pgu_action and pgu_machines_form.id_pgu_machine.data:
            pgu_machine = PGUMachine.query.get(pgu_machines_form.id_pgu_machine.data)
            if pgu_machine:
                # Получаем кэшированные справочники для ПГУ
                condition_types = dict(choices_cache.get_choices(ConditionType, ConditionType.id))
                tes_machine_types = dict(choices_cache.get_choices(TesMachineType, TesMachineType.id))
                machines = dict(choices_cache.get_choices(Machine, Machine.machine_name, name_field='machine_name'))
                
                # Список полей внешних ключей ПГУ, которые должны конвертировать 0 в None
                pgu_fk_fields_inline = {'id_condition_type', 'id_tes_machine_type'}
                
                for fld, to_str in {
                    "id_condition_type": lambda x: condition_types.get(x, "не указано") if x else "не указано",
                    "id_parent_machine": lambda x: machines.get(x, "не указано") if x else "не указано",
                    "machine_number": str,
                    "machine_name": str,
                    "id_tes_machine_type": lambda x: tes_machine_types.get(x, "не указано") if x else "не указано",
                    "note": lambda x: x or "не указано",
                }.items():
                    old_val = getattr(pgu_machine, fld)
                    new_val = getattr(pgu_machines_form, fld).data
                    
                    # Конвертируем 0 в None для полей внешних ключей
                    if fld in pgu_fk_fields_inline and choices_cache.is_empty_value(new_val):
                        new_val = None
                    
                    old_val_str = to_str(old_val)
                    new_val_str = to_str(new_val)
                    # Логируем только если строковые представления различаются
                    if old_val_str != new_val_str:
                        pgu_changes.append(f"ПГУ {fld}: {old_val_str} → {new_val_str}")
                        setattr(pgu_machine, fld, new_val)
                    elif old_val != new_val:
                        # Если строки одинаковы, но значения разные, просто обновляем без логирования
                        setattr(pgu_machine, fld, new_val)

                for fld in date_fields:
                    old_val = getattr(pgu_machine, fld)
                    raw_val = getattr(pgu_machines_form, fld).data
                    new_val = int(raw_val) if raw_val and fld in {"date_exploitation", "date_decompressing_expected", "date_modernization_expected"} else convert_to_date(raw_val)
                    if str(old_val) != str(new_val):
                        pgu_changes.append(f"ПГУ {fld}: {old_val} → {new_val}")
                        setattr(pgu_machine, fld, new_val)

        # Вызываем важные функции для всех агрегатов, а не только для ПГУ
        autofill_tes_and_fuel_chain(
            machine,
            station,
            advanced_form,
            changes,
            start_year,
            end_year,
            powers_map=powers_map,
            tes_map=tes_map,
            fuel_map=fuel_map,
        )
        recalculate_station_power(station, start_year, end_year)
        recalculate_machine_years_by_p_ust(machine, changes, year_features)

        _commit_with_retry()
        # ВАЖНО: изменения Machine/его мощностей/топлива/ПГУ влияют на агрегации и кэш сортировки/страниц
        clear_station_aggregation_cache("after machine save")
        
        # Инвалидация кэша после успешного обновления
        from app.common.services.cache_decorator import invalidate_cache, invalidate_cache_pattern
        if changes or pgu_changes:
            invalidate_cache('machine', machine_id=machine.id)
            invalidate_cache('station_full', station_id=station.id)
            invalidate_cache_pattern('station_list:*')
            # Очищаем кэш choices при изменении данных
            clear_machine_choices_cache()

        if pgu_changes:
            log_to_db(user, f"Изменения по ПГУ агрегату {pgu_machine.machine_name} станции {station.name}", details="; ".join(pgu_changes))
            flash("Данные ПГУ агрегата успешно обновлены!", "success")

        if changes:
            if is_new:
                log_to_db(user, f"Создан новый агрегат на станции {station.name} ({station.regional_district.name})", details="; ".join(changes), entity_type="machine", entity_id=machine.id)
                flash("Новый агрегат успешно создан!", "success")
            else:
                log_to_db(user, f"Изменения в станции {station.name} ({station.regional_district.name}), агрегат №{machine.machine_number}", details="; ".join(changes), entity_type="machine", entity_id=machine.id)
                flash("Данные агрегата успешно обновлены!", "success")

        if not changes and not pgu_changes and not is_new:
            flash("Изменений не обнаружено", "info")

        return redirect(url_for("station_bp.machine_details", start_year=start_year, end_year=end_year, rounding_digits=rounding_digits, station_id=station.id, machine_id=machine.id))

    except Exception as exc:
        db.session.rollback()
        traceback.print_exc()
        flash(f"Ошибка при обновлении данных: {exc}", "danger")
        if is_new:
            log_to_db(user, f"Ошибка создания нового агрегата на станции {station.name}", details=str(exc))
            # Для нового агрегата при ошибке устанавливаем machine=None
            machine = None
        else:
            machine_info = f"№{machine.machine_number} {machine.machine_name}" if machine else "неизвестный агрегат"
            log_to_db(user, f"Ошибка обновления агрегата {machine_info} станции {station.name}", details=str(exc), entity_type="machine", entity_id=machine.id if machine else None)
        print(f"[DEBUG] Ошибка в handle_machine_post: tes_types entries: {len(advanced_form.tes_types.entries)}")
        print(f"[DEBUG] Ошибка в handle_machine_post: fuels entries: {len(advanced_form.fuels.entries)}")
        # Оптимизированная загрузка документов - только id и name с фильтрацией по версии
        all_documents = choices_cache.get_choices(Document, Document.name)
        # Преобразуем обратно в объекты для совместимости с шаблоном
        all_documents = [Document(id=doc_id, name=doc_name) for doc_id, doc_name in all_documents]
        return render_template(
            "generation/stations/machine_details.html",
            start_year=start_year,
            end_year=end_year,
            rounding_digits=rounding_digits,
            main_form=main_form,
            advanced_form=advanced_form,
            pgu_machines_form=pgu_machines_form,
            station=station,
            machine=machine,
            year_features=year_features,
            all_documents=all_documents,
        )


@no_autoflush
def handle_pgu_machine_get(station_id, machine_id, pgu_machine_id, start_year, end_year):
    station = Station.query.get_or_404(station_id)
    parent_machine = Machine.query.get_or_404(machine_id)
    year_features = get_year_feature_dict()

    if pgu_machine_id == 0:
        pgu_machine = None
        pgu_form = PGUMachineFilterForm(prefix='pgu_')
    else:
        pgu_machine = PGUMachine.query.get_or_404(pgu_machine_id)
        pgu_form = PGUMachineFilterForm(obj=pgu_machine, prefix='pgu_')

    from app.generation.services.machine_services.machine_services import _fill_pgu_machines_form_choices
    _fill_pgu_machines_form_choices(pgu_form, machine_id)

    pgu_machine = PGUMachine.query.get(pgu_machine_id) if pgu_machine_id else None

    existing_powers = {}
    if pgu_machine:
        for power in pgu_machine.pgu_machine_powers:
            existing_powers[power.year_number] = power

    if not pgu_form.powers.entries:
        for year in range(start_year, end_year + 1):
            value = existing_powers.get(year).p_ust if existing_powers.get(year) else 0
            pgu_form.powers.append_entry({"year": year, "p_ust": value})

    context = {
        "station": station,
        "parent_machine": parent_machine,
        "pgu_form": pgu_form,
        "start_year": start_year,
        "end_year": end_year,
        "pgu_machine_id": pgu_machine_id,
        "pgu_machine":pgu_machine,
        "year_features": year_features,
    }
    return context


@no_autoflush
def handle_pgu_machine_post(station_id, machine_id, pgu_machine_id, form_data, user, start_year, end_year):
    station = get_station_by_id(station_id)
    parent_machine = get_machine_by_id(machine_id)

    pgu_form = PGUMachineFilterForm(form_data, prefix='pgu_')
    _fill_pgu_machines_form_choices(pgu_form, machine_id)

    if not pgu_form.validate():
        flash(
            "Ошибка в заполнении формы. Обязательные поля: Название агрегата, Организация-собственник.",
            "danger",
        )
        return render_template(
            "generation/stations/pgu_machine_details.html",
            station=station,
            parent_machine=parent_machine,
            pgu_form=pgu_form,
            start_year=start_year,
            end_year=end_year,
            pgu_machine_id=pgu_machine_id,
        )

    try:
        changes = []
        is_new = pgu_machine_id == 0
        
        with db.session.no_autoflush:
            if is_new:
                pgu_machine = PGUMachine(id_parent_machine=machine_id)
                set_db_version_on_create(pgu_machine)
                db.session.add(pgu_machine)
                db.session.flush()  # Получаем ID для новой записи
            else:
                pgu_machine = PGUMachine.query.get_or_404(pgu_machine_id)
                
                # Проверка версии из формы для предотвращения concurrent updates
                form_version = request.form.get('version', type=int)
                if form_version and hasattr(pgu_machine, 'version') and pgu_machine.version != form_version:
                    flash('Данные ПГУ агрегата были изменены другим пользователем. Пожалуйста, обновите страницу.', 'warning')
                    log_to_db(user, f"Обнаружен конфликт версий при обновлении ПГУ агрегата {pgu_machine.machine_name} (ожидаемая: {form_version}, текущая: {pgu_machine.version})", entity_type="pgu_machine", entity_id=pgu_machine.id)
                    return redirect(url_for('station_bp.pgu_machine_details',
                                            station_id=station.id,
                                            machine_id=parent_machine.id,
                                            pgu_machine_id=pgu_machine.id,
                                            start_year=start_year,
                                            end_year=end_year))

            # Логирование изменений полей
            from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroup
            from app.refdata.models.refdata_for_stations.machine.pgu_tes_machine_type_model import PGUTesMachineType
            
            # Получаем кэшированные справочники для ПГУ
            condition_types = dict(choices_cache.get_choices(ConditionType, ConditionType.id))
            pgu_tes_machine_types = dict(choices_cache.get_choices(PGUTesMachineType, PGUTesMachineType.id))
            
            field_map = {
            "id_condition_type": lambda x: condition_types.get(x, "не указано") if x else "не указано",
            "machine_number": str,
            "machine_name": str,
            "id_pgu_tes_machine_type": lambda x: pgu_tes_machine_types.get(x, "не указано") if x else "не указано",
            "note": lambda x: x or "не указано",
        }

            # Список полей, которые являются внешними ключами и должны конвертировать 0 в None
            pgu_fk_fields = {'id_condition_type', 'id_pgu_tes_machine_type'}
            
            for fld, to_str in field_map.items():
                old_v = getattr(pgu_machine, fld) if not is_new else None
                new_v = getattr(pgu_form, fld).data
                
                # Конвертируем 0 в None для полей внешних ключей
                if fld in pgu_fk_fields and choices_cache.is_empty_value(new_v):
                    new_v = None
                
                if is_new:
                    if new_v:
                        changes.append(f"{fld}: {to_str(new_v)}")
                    setattr(pgu_machine, fld, new_v)
                else:
                    old_v_str = to_str(old_v)
                    new_v_str = to_str(new_v)
                    # Логируем только если строковые представления различаются
                    if old_v_str != new_v_str:
                        changes.append(f"{fld}: {old_v_str} → {new_v_str}")
                        setattr(pgu_machine, fld, new_v)
                    elif old_v != new_v:
                        # Если строки одинаковы, но значения разные, просто обновляем без логирования
                        setattr(pgu_machine, fld, new_v)

            # Логирование изменений дат
            date_fields = [
                "date_exploitation", "date_commission_fact", "date_joining_expected", "date_joining_fact",
                "date_detatchment_fact", "date_decompressing_expected", "date_decompressing_fact",
                "date_modernization_expected", "date_relabing_fact", "date_update_fact",
            ]

            for fld in date_fields:
                raw_form_value = getattr(pgu_form, fld).data
                if fld in {"date_exploitation", "date_decompressing_expected", "date_modernization_expected"}:
                    new_val = int(raw_form_value) if raw_form_value else None
                else:
                    new_val = convert_to_date(raw_form_value)

                old_val = getattr(pgu_machine, fld) if not is_new else None
                old_val_str = old_val.strftime("%Y-%m-%d") if isinstance(old_val, (date, datetime)) else str(old_val) if old_val else None
                new_val_str = new_val.strftime("%Y-%m-%d") if isinstance(new_val, (date, datetime)) else str(new_val) if new_val else None

                if is_new:
                    if new_val:
                        changes.append(f"{fld}: {new_val_str}")
                    setattr(pgu_machine, fld, new_val)
                else:
                    if old_val_str != new_val_str:
                        changes.append(f"{fld}: {old_val_str} → {new_val_str}")
                        setattr(pgu_machine, fld, new_val)

            db.session.flush()

            # Получаем существующие мощности для сравнения
            existing_powers = {}
            if not is_new:
                for power in PGUMachinePower.query.filter_by(id_pgu_machine=pgu_machine.id).all():
                    existing_powers[power.year_number] = power.p_ust

            # Удаляем старые мощности и добавляем новые
            PGUMachinePower.query.filter_by(id_pgu_machine=pgu_machine.id).delete()

            for power_entry in pgu_form.powers.entries:
                year = power_entry.year.data
                p_ust = to_decimal(power_entry.p_ust.data)
                
                # Логируем изменения мощности
                if is_new:
                    if p_ust and p_ust > 0:
                        changes.append(f"p_ust: {year} год - {format_decimal_for_display(p_ust)}")
                else:
                    old_p_ust = existing_powers.get(year)
                    if not is_same_decimal(old_p_ust, p_ust):
                        changes.append(f"p_ust: {year} год - {format_decimal_for_display(old_p_ust)} → {format_decimal_for_display(p_ust)}")
                
                pgu_power = PGUMachinePower(id_pgu_machine=pgu_machine.id, year_number=year, p_ust=p_ust)
                set_db_version_on_create(pgu_power)
                db.session.add(pgu_power)

            powers_seq = [(pe.year.data, to_decimal(pe.p_ust.data)) for pe in pgu_form.powers.entries]

            # ============================================================
            # ВАЖНО: может быть заполнено ТОЛЬКО ОДНО из трех полей:
            # - date_exploitation (год ввода)
            # - date_decompressing_expected (год вывода)
            # - date_modernization_expected (год модернизации)
            #
            # Приоритет: вывод -> ввод -> модернизация
            # ============================================================
            decomp_year = _calculate_decompressing_expected_year_from_powers(powers_seq)
            expl_year = _calculate_exploitation_year_from_powers(powers_seq)
            modern_year = _calculate_modernization_expected_year_from_powers(powers_seq)

            selected_kind = None
            selected_year = None
            if decomp_year is not None:
                selected_kind, selected_year = "decomp", decomp_year
            elif expl_year is not None:
                selected_kind, selected_year = "expl", expl_year
            elif modern_year is not None:
                selected_kind, selected_year = "modern", modern_year

            def _set_int_field(attr: str, value: int | None, label: str):
                old_val = getattr(pgu_machine, attr)
                if old_val != value:
                    changes.append(f"{label}: {old_val} → {value if value is not None else '—'}")
                    setattr(pgu_machine, attr, value)

            if selected_kind == "decomp":
                _set_int_field("date_decompressing_expected", selected_year, "date_decompressing_expected")
                _set_int_field("date_exploitation", None, "date_exploitation")
                _set_int_field("date_modernization_expected", None, "date_modernization_expected")
            elif selected_kind == "expl":
                _set_int_field("date_exploitation", selected_year, "date_exploitation")
                _set_int_field("date_decompressing_expected", None, "date_decompressing_expected")
                _set_int_field("date_modernization_expected", None, "date_modernization_expected")
            elif selected_kind == "modern":
                _set_int_field("date_modernization_expected", selected_year, "date_modernization_expected")
                _set_int_field("date_decompressing_expected", None, "date_decompressing_expected")
                _set_int_field("date_exploitation", None, "date_exploitation")
            else:
                # Ничего не вычислили — не меняем поля автоматически
                pass

        _commit_with_retry()
        
        # ВАЖНО: ПГУ влияет на агрегаты/агрегации — чистим кэш после мутаций
        clear_station_aggregation_cache("after PGU save")
        
        # Инвалидация кэша после успешного обновления
        from app.common.services.cache_decorator import invalidate_cache, invalidate_cache_pattern
        invalidate_cache('machine', machine_id=parent_machine.id)
        invalidate_cache('station_full', station_id=station.id)
        invalidate_cache_pattern('station_list:*')
        # Очищаем кэш choices при изменении данных
        clear_machine_choices_cache()

        # Логирование
        if is_new:
            log_to_db(
                user, 
                f"Добавлен ПГУ агрегат '{pgu_form.machine_name.data}' на станции {station.name}", 
                details="; ".join(changes) if changes else f"ID: {pgu_machine.id}"
            )
            flash(f"Агрегат ПГУ успешно добавлен!", "success")
        else:
            if changes:
                log_to_db(
                    user, 
                    f"Изменения на станции {station.name} в агрегате ПГУ '{pgu_machine.machine_name}' (UID: {pgu_machine.id}) ", 
                    details="; ".join(changes)
                )
                flash(f"Агрегат ПГУ успешно обновлен!", "success")
            else:
                flash("Изменений не обнаружено", "info")

        return redirect(url_for('station_bp.pgu_machine_details',
                                station_id=station.id,
                                machine_id=parent_machine.id,
                                pgu_machine_id=pgu_machine.id,
                                **request.args))

    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        flash(f"Ошибка при сохранении: {e}", "danger")
        log_to_db(user, f"Ошибка при сохранении ПГУ агрегата на станции {station.name}", details=str(e))
        return render_template(
            "generation/stations/pgu_machine_details.html",
            station=station,
            parent_machine=parent_machine,
            pgu_form=pgu_form,
            start_year=start_year,
            end_year=end_year,
            pgu_machine_id=pgu_machine_id,
        )
    

_choices_cache = {}

def _clear_choices_cache():
    """Очищает кэш choices (вызывать при изменении справочных данных)"""
    global _choices_cache
    _choices_cache.clear()

def clear_machine_choices_cache():
    """Публичная функция для очистки кэша choices из других модулей"""
    _clear_choices_cache()
    # Также очищаем CacheService для унификации
    CacheService.clear_cache()

def _fill_main_form_choices(form):
    """Заполняет choices для основной формы с использованием унифицированного кэширования"""
    # Добавляем дефолтное значение "не указано", чтобы оно отображалось в select
    # и могло выступать "пустым" значением до обязательного выбора пользователем.
    form.id_gen_company.choices = choices_cache.get_choices_with_default(GenCompany, GenCompany.id)
    form.id_energy_area.choices = choices_cache.get_choices(EnergyArea, EnergyArea.id)
    form.id_machine_type.choices = choices_cache.get_choices(MachineType, MachineType.id)
    form.id_tes_machine_type.choices = choices_cache.get_choices(TesMachineType, TesMachineType.id)
    form.id_equipment_group.choices = choices_cache.get_choices(EquipmentGroup, EquipmentGroup.id)
    
    form.id_condition_type.choices = choices_cache.get_choices(ConditionType, ConditionType.id)
    if form.id_condition_type.data is None:
        form.id_condition_type.data = choices_cache.EMPTY_VALUE_ID


def _fill_advanced_form_choices(form):
    """Заполняет choices для расширенной формы с использованием кэширования"""
    tes_choices = choices_cache.get_choices(TesType, TesType.id)
    fuel_choices = choices_cache.get_choices(Fuel, Fuel.id)

    print(f"[DEBUG] _fill_advanced_form_choices: tes_types entries: {len(form.tes_types.entries)}")
    print(f"[DEBUG] _fill_advanced_form_choices: fuels entries: {len(form.fuels.entries)}")

    # Устанавливаем choices только если они еще не установлены или пусты
    for i, entry in enumerate(form.tes_types):
        print(f"[DEBUG] tes_entry {i}: year={entry.year.data}, tes_type.data={entry.tes_type.data}, choices уже установлены: {hasattr(entry.tes_type, 'choices') and entry.tes_type.choices}")
        if not hasattr(entry.tes_type, 'choices') or not entry.tes_type.choices:
            entry.tes_type.choices = tes_choices
        if entry.tes_type.data is None:
            entry.tes_type.data = choices_cache.EMPTY_VALUE_ID 

    for i, entry in enumerate(form.fuels):
        print(f"[DEBUG] fuel_entry {i}: year={entry.year.data}, fuel_type.data={entry.fuel_type.data}, choices уже установлены: {hasattr(entry.fuel_type, 'choices') and entry.fuel_type.choices}")
        if not hasattr(entry.fuel_type, 'choices') or not entry.fuel_type.choices:
            entry.fuel_type.choices = fuel_choices
        if entry.fuel_type.data is None:
            entry.fuel_type.data = choices_cache.EMPTY_VALUE_ID


def _fill_pgu_machines_form_choices(form, machine_id):
    """Заполняет choices для формы ПГУ с использованием унифицированного кэширования"""
    form.id_parent_machine.choices = choices_cache.get_choices(Machine, Machine.machine_name, name_field='machine_name')
    form.id_condition_type.choices = choices_cache.get_choices(ConditionType, ConditionType.id)
    form.id_pgu_tes_machine_type.choices = choices_cache.get_choices(PGUTesMachineType, PGUTesMachineType.id)
    
    if form.id_condition_type.data is None:
        form.id_condition_type.data = choices_cache.EMPTY_VALUE_ID
    if form.id_pgu_tes_machine_type.data is None:
        form.id_pgu_tes_machine_type.data = choices_cache.EMPTY_VALUE_ID


def is_empty(val):
    try:
        if val is None:
            return True
        if isinstance(val, Decimal):
            return float(val) == 0.0
        return Decimal(val) == 0
    except (InvalidOperation, TypeError, ValueError):
        return True


def to_decimal(val):
    try:
        if val in (None, '', '—', '-'):
            return None
        if isinstance(val, str):
            val = val.replace(',', '.')
        return Decimal(val)
    except (InvalidOperation, TypeError):
        return None
    

def _calculate_decompressing_expected_year_from_powers(powers_sequence: list[tuple[int, Decimal | None]]) -> int | None:
    """
    Ожидаемый год вывода из эксплуатации = первый год, когда мощность становится 0.
    При переходе >0 (год N) -> 0 (год N+1) возвращаем N+1.
    """
    if not powers_sequence:
        return None

    seq = sorted(
        [(int(y), (p if isinstance(p, Decimal) else None)) for y, p in powers_sequence if y is not None],
        key=lambda t: t[0],
    )
    if len(seq) < 2:
        return None

    for i in range(len(seq) - 1):
        _, p_cur = seq[i]
        y_next, p_next = seq[i + 1]

        cur_pos = isinstance(p_cur, Decimal) and p_cur > 0
        next_pos = isinstance(p_next, Decimal) and p_next > 0
        if cur_pos and not next_pos:
            return y_next

    return None


def _calculate_exploitation_year_from_powers(powers_sequence: list[tuple[int, Decimal | None]]) -> int | None:
    """
    Год ввода (для ПГУ используем `date_exploitation`) по мощности:
    - если p_ust[N] == 0 и p_ust[N+1] > 0 -> возвращаем N+1
    - если такого перехода нет, но есть ненулевая мощность -> возвращаем первый год с p_ust > 0
    """
    if not powers_sequence:
        return None

    seq = sorted(
        [(int(y), (p if isinstance(p, Decimal) else None)) for y, p in powers_sequence if y is not None],
        key=lambda t: t[0],
    )
    if not seq:
        return None

    def _pos(p: Decimal | None) -> bool:
        return isinstance(p, Decimal) and p > 0

    for i in range(len(seq) - 1):
        _, p_cur = seq[i]
        y_next, p_next = seq[i + 1]
        if (not _pos(p_cur)) and _pos(p_next):
            return y_next

    for y, p in seq:
        if _pos(p):
            return y

    return None


def _calculate_modernization_expected_year_from_powers(powers_sequence: list[tuple[int, Decimal | None]]) -> int | None:
    """
    Ожидаемый год модернизации по мощности:
    если p_ust[N] > 0 и p_ust[N+1] > 0 и значения различаются -> возвращаем N+1 (первый такой случай).
    """
    if not powers_sequence:
        return None

    seq = sorted(
        [(int(y), (p if isinstance(p, Decimal) else None)) for y, p in powers_sequence if y is not None],
        key=lambda t: t[0],
    )
    if len(seq) < 2:
        return None

    def _pos(p: Decimal | None) -> bool:
        return isinstance(p, Decimal) and p > 0

    for i in range(len(seq) - 1):
        _, p_cur = seq[i]
        y_next, p_next = seq[i + 1]
        if _pos(p_cur) and _pos(p_next) and p_cur != p_next:
            return y_next

    return None


def is_same_decimal(a, b, tol=6):
    if a is None and (b is None or Decimal(b) == 0):
        return True
    if b is None and (a is None or Decimal(a) == 0):
        return True
    return rounded_decimal(a, tol) == rounded_decimal(b, tol)


def autofill_powers_if_possible_decimal(p_ust, p_ogr, p_rasp, year_num=None, skip_ogr=False, skip_rasp=False):
    """
    Автозаполнение мощностей по формуле: Руст = Рогр + Ррасп
    
    Args:
        p_ust: Установленная мощность
        p_ogr: Ограничение мощности
        p_rasp: Располагаемая мощность
        year_num: Номер года (для сообщений)
        skip_ogr: Если True, не автозаполнять Рогр (пользователь ввел значение явно)
        skip_rasp: Если True, не автозаполнять Ррасп (пользователь ввел значение явно)
    """
    try:
        if p_ust > 0:
            if not is_empty(p_rasp) and is_empty(p_ogr) and not skip_ogr:
                calculated = p_ust - p_rasp
                if rounded_decimal(p_ogr, 6) != rounded_decimal(calculated, 6):
                    if year_num is not None:
                        flash(f"🧠 {year_num} год: автозаполнено Рогр = {calculated} (из Руст − Ррасп)", "info")
                    return p_ust, calculated, p_rasp
            elif not is_empty(p_ogr) and is_empty(p_rasp) and not skip_rasp:
                calculated = p_ust - p_ogr
                if rounded_decimal(p_rasp, 6) != rounded_decimal(calculated, 6):
                    if year_num is not None:
                        flash(f"🧠 {year_num} год: автозаполнено Ррасп = {calculated} (из Руст − Рогр)", "info")
                    return p_ust, p_ogr, calculated
            elif is_empty(p_ogr) and is_empty(p_rasp) and not skip_ogr and not skip_rasp:
                if year_num is not None:
                    flash(f"🧠 {year_num} год: автозаполнено Ррасп = 0 и Рогр = {p_ust}", "info")
                return p_ust, p_ust, Decimal(0)
        return p_ust, p_ogr, p_rasp

    except (InvalidOperation, TypeError) as e:
        if year_num is not None:
            flash(f"[WARNING] {year_num} год: ошибка автозаполнения мощностей ({e})", "warning")
        return p_ust, p_ogr, p_rasp
    

def autofill_tes_and_fuel_chain(
    machine,
    station,
    advanced_form,
    changes,
    start_year,
    end_year,
    powers_map=None,
    tes_map=None,
    fuel_map=None,
):
    """
    Автоматически заполняет тип ТЭС и топливо по принципу цепной передачи:
    - если p_ust > 0 и текущий тип == 0, а предыдущий ≠0 → копируем
    - если все мощности == 0 → тип ТЭС и топливо = 0
    """
    from flask import flash

    # Логика типов ТЭС и топлива актуальна только для станций типа ТЭС (id_station_type == 4)
    # Для ГЭС/СЭС/ВЭС и прочих типов — ничего не делаем и не логируем
    try:
        # Используем переданный объект station. Распознаем ТЭС по id или названию
        try:
            st_name = (station.station_type.name or '').strip().lower() if station.station_type else ''
        except Exception:
            st_name = ''
        is_tes_station = (st_name == 'тэс')
        if not is_tes_station:
            return
    except Exception:
        # В случае отсутствия атрибута/ошибок — безопасно выходим
        return

    def resolve_default_id(names_dict):
        for value, label in names_dict.items():
            if isinstance(label, str) and label.strip().lower() == "не указано":
                return value
        return choices_cache.EMPTY_VALUE_ID

    def is_empty_choice(value, default_id):
        if choices_cache.is_empty_value(value):
            return True
        if value == default_id:
            return True
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return True
            if stripped.isdigit():
                return int(stripped) == default_id
        try:
            return int(value) == default_id
        except (TypeError, ValueError):
            return False

    prev_tes_type = None
    prev_fuel_type = None

    if machine is None and (powers_map is None or tes_map is None or fuel_map is None):
        # Нет данных для автозаполнения
        return

    if powers_map is None:
        powers_map = {mp.year.number: mp for mp in machine.machine_powers if mp.year is not None}
    if tes_map is None:
        tes_map = {mt.year.number: mt for mt in machine.machine_tes_types if mt.year is not None}
    if fuel_map is None:
        fuel_map = {mf.year.number: mf for mf in machine.machine_fuels if mf.year is not None}

    fuel_names = dict(choices_cache.get_choices(Fuel, Fuel.id))
    tes_names = dict(choices_cache.get_choices(TesType, TesType.id))
    tes_default_id = resolve_default_id(tes_names)
    fuel_default_id = resolve_default_id(fuel_names)

    for i, year_num in enumerate(range(start_year, end_year + 1)):
        if year_num not in powers_map or year_num not in tes_map or year_num not in fuel_map:
            continue

        mp = powers_map[year_num]
        mt = tes_map[year_num]
        mf = fuel_map[year_num]

        p_ust = mp.p_ust or Decimal(0)
        p_ogr = mp.p_ogr or Decimal(0)
        p_rasp = mp.p_rasp or Decimal(0)

        if is_empty(p_ust) and is_empty(p_ogr) and is_empty(p_rasp):
            tes_empty = is_empty_choice(mt.id_tes_type, tes_default_id)
            if not tes_empty:
                new_tes_type = tes_default_id
                if mt.id_tes_type != new_tes_type:
                    old_tes_name = tes_names.get(mt.id_tes_type, f"[{mt.id_tes_type}]")
                    changes.append(f"Тип ТЭС: {year_num} год - {old_tes_name} → не указано")
                    mt.id_tes_type = new_tes_type
                    flash(f"🧠 {year_num} год: Тип ТЭС установлен: 'не указано' (все мощности = 0)", "info")

            fuel_empty = is_empty_choice(mf.id_fuel, fuel_default_id)
            if not fuel_empty:
                new_fuel_type = fuel_default_id
                if mf.id_fuel != new_fuel_type:
                    old_fuel_name = fuel_names.get(mf.id_fuel, f"[{mf.id_fuel}]")
                    changes.append(f"Топливо: {year_num} год - {old_fuel_name} → не указано")
                    mf.id_fuel = new_fuel_type
                    flash(f"🧠 {year_num} год: Топливо установлено: 'не указано' (все мощности = 0)", "info")
        else:
            if is_empty_choice(mt.id_tes_type, tes_default_id) and not is_empty_choice(prev_tes_type, tes_default_id):
                tes_name = tes_names.get(prev_tes_type, f"[{prev_tes_type}]")
                changes.append(f"Тип ТЭС: {year_num} год - не указано → {tes_name}")
                mt.id_tes_type = prev_tes_type
                flash(f"🧠 {year_num} год: Тип ТЭС скопирован из предыдущего года ({tes_name})", "info")

            if is_empty_choice(mf.id_fuel, fuel_default_id) and not is_empty_choice(prev_fuel_type, fuel_default_id):
                fuel_name = fuel_names.get(prev_fuel_type, f"[{prev_fuel_type}]")
                changes.append(f"Топливо: {year_num} год - не указано → {fuel_name}")
                mf.id_fuel = prev_fuel_type
                flash(f"🧠 {year_num} год: Топливо скопировано из предыдущего года ({fuel_name})", "info")

        # Обновляем форму
        j = year_num - start_year
        if 0 <= j < len(advanced_form.tes_types):
            advanced_form.tes_types[j].tes_type.data = mt.id_tes_type
        if 0 <= j < len(advanced_form.fuels):
            advanced_form.fuels[j].fuel_type.data = mf.id_fuel

        prev_tes_type = mt.id_tes_type
        prev_fuel_type = mf.id_fuel


def recalculate_machine_years_by_p_ust(machine, changes, year_features):
    def is_positive_power(power: Decimal) -> bool:
        return isinstance(power, Decimal) and power > 0

    def all_future_zero_powers(powers_sequence, start_index):
        if start_index >= len(powers_sequence) - 1:
            return False
        return all(not is_positive_power(power) for _, power in powers_sequence[start_index + 1 :])

    years_by_ust = sorted(
        [(mp.year.number, mp.p_ust) for mp in machine.machine_powers if isinstance(mp.p_ust, Decimal) and mp.year is not None],
        key=lambda t: t[0],
    )
    if not years_by_ust:
        return

    nonzero = [(y, p) for y, p in years_by_ust if p and p > 0]
    if not nonzero:
        return

    # Новые значения по заданным правилам
    new_expected_expl_year = None       # Ожидаемый год ввода в эксплуатацию
    new_decomp_year = None              # Ожидаемый год вывода из эксплуатации
    new_modern_year = None              # Ожидаемый год модернизации

    # Проходим по соседним годам N и N+1
    for i in range(len(years_by_ust) - 1):
        year_n, p_n = years_by_ust[i]
        year_n1, p_n1 = years_by_ust[i + 1]

        n_pos = is_positive_power(p_n)
        n1_pos = is_positive_power(p_n1)

        # 1) Если Руст года N ≠ 0, а года N+1 == 0 → ожидаемый год вывода = N+1
        if n_pos and not n1_pos and new_decomp_year is None:
            new_decomp_year = year_n1

        # 2) Если Руст года N == 0, а года N+1 ≠ 0 → ожидаемый год ввода = N+1
        if (not n_pos) and n1_pos and new_expected_expl_year is None:
            new_expected_expl_year = year_n1

        # 3) Если Руст года N ≠ 0 и года N+1 ≠ 0, но они не равны →
        #    ожидаемый год модернизации = N+1
        if n_pos and n1_pos and p_n1 != p_n and new_modern_year is None:
            new_modern_year = year_n1

    # --- Фактический год ввода ---
    # По требованиям UI/бизнес-логики НЕ рассчитываем автоматически.
    # Поле `date_exploitation` заполняется пользователем вручную.

    # ============================================================
    # ВАЖНО: может быть заполнено ТОЛЬКО ОДНО из трех полей:
    # - date_exploitation_expected (ожидаемый год ввода)
    # - date_decompressing_expected (ожидаемый год вывода)
    # - date_modernization_expected (ожидаемый год модернизации)
    #
    # Выбор делаем по приоритету событий мощности:
    # 1) вывод (>0 -> 0) — самый приоритетный
    # 2) ввод (0 -> >0)
    # 3) модернизация (>0 -> >0 и изменилось значение)
    # ============================================================
    effective_decomp_year = new_decomp_year if (new_decomp_year is not None and new_decomp_year < Config.END_YEAR) else None

    selected_kind = None
    selected_year = None
    if effective_decomp_year is not None:
        selected_kind, selected_year = "decomp", effective_decomp_year
    elif new_expected_expl_year is not None:
        selected_kind, selected_year = "expl", new_expected_expl_year
    elif new_modern_year is not None:
        selected_kind, selected_year = "modern", new_modern_year

    if selected_kind == "decomp":
        if machine.date_decompressing_expected != selected_year:
            changes.append(f"Год вывода: {machine.date_decompressing_expected} → {selected_year}")
            flash(f"🧠 Ожидаемый год вывода автоматически определен: {selected_year}", "info")
            machine.date_decompressing_expected = selected_year
        # очищаем остальные два поля (взаимоисключаемость)
        if machine.date_exploitation_expected is not None:
            changes.append(f"Ожидаемый год ввода: {machine.date_exploitation_expected} → —")
            machine.date_exploitation_expected = None
        if machine.date_modernization_expected is not None:
            changes.append(f"Год модернизации: {machine.date_modernization_expected} → —")
            machine.date_modernization_expected = None

    elif selected_kind == "expl":
        if machine.date_exploitation_expected != selected_year:
            changes.append(f"Ожидаемый год ввода: {machine.date_exploitation_expected} → {selected_year}")
            flash(f"🧠 Ожидаемый год ввода автоматически определен: {selected_year}", "info")
            machine.date_exploitation_expected = selected_year
        if machine.date_decompressing_expected is not None:
            changes.append(f"Год вывода: {machine.date_decompressing_expected} → —")
            machine.date_decompressing_expected = None
        if machine.date_modernization_expected is not None:
            changes.append(f"Год модернизации: {machine.date_modernization_expected} → —")
            machine.date_modernization_expected = None

    elif selected_kind == "modern":
        if machine.date_modernization_expected != selected_year:
            changes.append(f"Год модернизации: {machine.date_modernization_expected} → {selected_year}")
            flash(f"🧠 Ожидаемый год модернизации автоматически определен: {selected_year}", "info")
            machine.date_modernization_expected = selected_year
        if machine.date_decompressing_expected is not None:
            changes.append(f"Год вывода: {machine.date_decompressing_expected} → —")
            machine.date_decompressing_expected = None
        if machine.date_exploitation_expected is not None:
            changes.append(f"Ожидаемый год ввода: {machine.date_exploitation_expected} → —")
            machine.date_exploitation_expected = None

    else:
        # Ничего не выбрано — не трогаем текущие значения.
        # Ранее тут было предупреждение про модернизацию; теперь оно не нужно,
        # чтобы не мешать логике взаимоисключаемости.
        pass


