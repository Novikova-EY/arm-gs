from config import Config
from app.extensions import db
import traceback
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from sqlalchemy.orm.attributes import flag_modified
from flask import flash, request, render_template, redirect, url_for
from flask_login import current_user
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
from app.generation.models.machine.machine_name_model import MachineName
from app.generation.models.pgu_machine.pgu_machine_power_model import PGUMachinePower
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.generation.models.pgu_machine.pgu_machine_name_model import PGUMachineName
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
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroupType
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
    format_decimal_trim_for_display,
    normalize_date_list,
)
from app.common.services.get_services.years.years_get_services import (
    get_year_feature_dict,
    get_year_list_full,
)
from app.common.services.database_version_services import (
    get_current_version_year_range_from_name,
)
from app.common.services.choices_cache_service import choices_cache, ChoicesCacheService
from app.common.services.database_version_filter import (
    set_db_version_on_create,
    filter_by_db_version,
    get_current_db_version_id,
)
from app.common.services.cache_services import CacheService
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.services.equipment_groups.equipment_group_set_services import (
    get_station_fuel_equipment_group_choice_tuples,
    sync_machine_fuel_equipment_group,
)

_FUEL_MODULE_EDIT_ROLES = frozenset({"admin", "fuel-admin", "fuel-editor"})
_GENERATION_MODULE_EDIT_ROLES = frozenset({"admin", "generation-admin", "generation-editor"})


def _machine_post_role_flags() -> dict[str, bool]:
    role_names = set(getattr(current_user, "role_names", []) or [])
    return {
        "can_edit_fuel": bool(role_names & _FUEL_MODULE_EDIT_ROLES),
        "can_edit_generation": bool(role_names & _GENERATION_MODULE_EDIT_ROLES),
    }


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
        # Загружаем только "узкие" связи агрегата; тяжелые коллекции подгружаем отдельными
        # отфильтрованными запросами ниже.
        machine = Machine.query.options(
            db.joinedload(Machine.condition_type),
            db.joinedload(Machine.gen_company),
            db.joinedload(Machine.machine_type),
            db.joinedload(Machine.tes_machine_type),
            db.joinedload(Machine.equipment_group),
            db.joinedload(Machine.machine_fuel_param).joinedload(
                MachineFuelParam.equipment_group
            ),
        ).get_or_404(machine_id)
    perf_mark("machine_load")

    # Легкая инициализация годов: вместо тяжелого get_year_list_full()
    # просто фиксируем диапазон отображаемых лет для шаблона.
    # Это убирает медленный запрос к таблице Year на каждом открытии карточки агрегата.
    years = list(range(start_year, end_year + 1))
    perf_mark("years_query")

    year_features = get_year_feature_dict()
    perf_mark("year_features")

    version_year_start, version_year_end = get_current_version_year_range_from_name()
    perf_mark("version_range")

    # Если это новый агрегат, создаем пустые словари
    if machine is None:
        machine_powers = {}
        machine_fuels = {}
        machine_tes_types = {}
        machine_names = {}
    else:
        # Отдельные оптимизированные запросы по годам и агрегату
        powers_q = (
            MachinePower.query
            .filter_by(id_machine=machine.id)
            .filter(
                MachinePower.year_number >= start_year,
                MachinePower.year_number <= end_year,
            )
        )
        machine_powers = {mp.year_number: mp for mp in powers_q.all()}

        fuels_q = (
            MachineFuel.query
            .filter_by(id_machine=machine.id)
            .filter(
                MachineFuel.year_number >= start_year,
                MachineFuel.year_number <= end_year,
            )
        )
        machine_fuels = {mf.year_number: mf for mf in fuels_q.all()}

        tes_q = (
            MachineTesType.query
            .filter_by(id_machine=machine.id)
            .filter(
                MachineTesType.year_number >= start_year,
                MachineTesType.year_number <= end_year,
            )
        )
        machine_tes_types = {mt.year_number: mt for mt in tes_q.all()}

        names_q = MachineName.query.filter_by(id_machine=machine.id)
        machine_names = {
            mn.year_number: mn
            for mn in names_q.all()
            if mn.year_number is not None
        }

    main_form = MachineFilterForm(prefix="main_", obj=machine)
    advanced_form = EditMachineForm(prefix="adv_")
    perf_mark("forms_init")

    _fill_main_form_choices(main_form)
    _fill_fuel_equipment_group_choices(main_form, station.id, machine)
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
    if not main_form.relabing_outcome.data:
        main_form.relabing_outcome.data = ""

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

        name_entry = advanced_form.machine_names.append_entry()
        name_entry.year.data = year_num
        mn = machine_names.get(year_num) if machine_names else None
        name_entry.year_name.data = (mn.name if mn and mn.name else None) or ""

    # Устанавливаем choices для всех записей после создания всех entries
    print(f"[DEBUG] Количество tes_types entries: {len(advanced_form.tes_types.entries)}")
    print(f"[DEBUG] Количество fuels entries: {len(advanced_form.fuels.entries)}")
    
    # Заполняем choices для всех entries через единую функцию
    _fill_advanced_form_choices(advanced_form)
    perf_mark("advanced_fill")

    # Для ТЭС, ГЭС и ГАЭС формируем "Название агрегата" на основе:
    # - имени текущего года версии БД
    # - и, при отличии, имени в плановом периоде: "<текущ. год> (<перспективный период>)"
    try:
        st_name = (station.station_type.name or "").strip().lower() if station.station_type else ""
    except Exception:
        st_name = ""
    if st_name == "тэс" and machine is not None:
        mfp_nt = getattr(machine, "machine_fuel_param", None)
        if mfp_nt is not None and mfp_nt.nt is not None:
            try:
                v = mfp_nt.nt
                main_form.thermal_power_gcalh.data = (
                    v if isinstance(v, Decimal) else Decimal(str(v))
                )
            except (InvalidOperation, ValueError):
                pass
    is_tes_or_ges = st_name in ("тэс", "гэс", "гаэс")
    version_year_for_base = version_year_start if version_year_start is not None else version_year_end
    if is_tes_or_ges and machine is not None and (version_year_for_base is not None or version_year_end is not None):
        # Базовое имя: из MachineName за год начала диапазона (текущий/факт), иначе за конец, иначе Machine.machine_name
        base_name = None
        if version_year_for_base is not None:
            mn_current = machine_names.get(version_year_for_base) if machine_names else None
            if mn_current and mn_current.name:
                base_name = mn_current.name.strip()
        if not base_name and version_year_end is not None:
            mn_current = machine_names.get(version_year_end) if machine_names else None
            if mn_current and mn_current.name:
                base_name = mn_current.name.strip()
        if not base_name and machine.machine_name:
            base_name = machine.machine_name.strip()

        display_name = base_name

        # Ищем отличающееся имя в плановом периоде (год с признаком "план" и другим названием)
        if base_name and year_features:
            # сортируем по возрастанию года
            for y in sorted(machine_names.keys()):
                label = year_features.get(y)
                if not label or "план" not in str(label).strip().lower():
                    continue
                mn_plan = machine_names.get(y)
                if not mn_plan or not mn_plan.name:
                    continue
                plan_name = mn_plan.name.strip()
                if plan_name and plan_name.lower() != base_name.lower():
                    display_name = f"{base_name} ({plan_name})"
                    break

        if display_name:
            main_form.machine_name.data = display_name

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
        "version_year_start": version_year_start,
        "version_year_end": version_year_end,
        "all_documents": all_documents,
    }


def _validate_power_ranges(advanced_form, formdata):
    has_errors = False
    for power_form in advanced_form.powers:
        for field_name in ("p_ust", "p_ogr", "p_rasp"):
            field = getattr(power_form, field_name)
            raw_value = formdata.get(field.name)
            orig_value = formdata.get(f"{field.name}_orig")
            current = to_decimal(raw_value)
            original = to_decimal(orig_value)

            # Если в форме нет *_orig, считаем, что мы не знаем исходное значение
            # и НЕ блокируем сохранение (это важно для старых/негативных значений,
            # загруженных из БД, когда hidden‑поля еще не были добавлены).
            is_orig_missing = orig_value in (None, "", "—", "-")

            # Отрицательные значения в Рогр не блокируют сохранение:
            # показываем только предупреждение и не добавляем ошибку поля.
            if (
                field_name == "p_ogr"
                and current is not None
                and current < 0
                and not is_orig_missing
                and current != original
            ):
                flash(
                    "Введено отрицательное значение Рогр. "
                    "Сохранение выполнено, но проверьте корректность ограничения мощности.",
                    "warning",
                )
                continue

            # Для Руст и Ррасп продолжаем блокировать действительно новые отрицательные
            # значения, если известно исходное.
            if (
                field_name in ("p_ust", "p_rasp")
                and not is_orig_missing
                and current != original
                and current is not None
                and current < 0
            ):
                field.errors.append("Number must be at least 0.")
                has_errors = True

    return not has_errors


@no_autoflush
def handle_machine_post(station_id, machine_id, form_data, user, start_year, end_year, rounding_digits):
    from werkzeug.datastructures import MultiDict

    normalized = MultiDict(form_data)
    # Поля, в которых запятая — десятичный разделитель (только числовые)
    _numeric_key_suffixes = ("p_ust", "p_ogr", "p_rasp")
    for key, value in list(normalized.items()):
        if isinstance(value, str):
            if value.strip() in {"\u2014", "-", ""}:
                normalized[key] = ""
            # Заменяем запятую на точку только в числовых полях мощности и тепловой мощности
            # В текстовых (machine_name, note и т.п.) запятая — часть названия (напр. ТГ-3,5АС)
            elif "," in value and (
                key.endswith(_numeric_key_suffixes) or key.endswith("thermal_power_gcalh")
            ):
                normalized[key] = value.replace(",", ".")

    station = get_station_by_id(station_id)

    _rpf = _machine_post_role_flags()
    can_edit_fuel = _rpf["can_edit_fuel"]
    can_edit_generation = _rpf["can_edit_generation"]
    if not can_edit_fuel and not can_edit_generation:
        flash("Недостаточно прав для изменения данных агрегата.", "danger")
        return redirect(
            url_for(
                "station_bp.machine_details",
                station_id=station_id,
                machine_id=machine_id,
                start_year=start_year,
                end_year=end_year,
                rounding_digits=rounding_digits,
            )
        )

    # Проверяем, создается ли новый агрегат
    is_new = machine_id == 0
    if is_new:
        machine = None
    else:
        machine = get_machine_by_id(machine_id)

    # Если обязательные поля не пришли в POST (иногда Select2/textarea не отправляют),
    # подставляем текущие значения агрегата, чтобы избежать ложной ошибки валидации.
    def _ensure_form_value(field_name: str, fallback_value: str | None):
        if fallback_value in (None, ""):
            return
        variants = {field_name}
        if "-" in field_name:
            variants.add(field_name.replace("-", "_"))
        else:
            variants.add(field_name.replace("_", "-"))

        for variant in variants:
            current_val = normalized.get(variant)
            if current_val is None or (isinstance(current_val, str) and current_val.strip() == ""):
                normalized[variant] = fallback_value

    if machine is not None:
        probe_form = MachineFilterForm(prefix="main_")
        gen_company_name = probe_form.id_gen_company.name
        machine_name_field = probe_form.machine_name.name
        machine_number_field = probe_form.machine_number.name

        if machine.id_gen_company is not None:
            _ensure_form_value(gen_company_name, str(machine.id_gen_company))

        if machine.machine_name:
            _ensure_form_value(machine_name_field, machine.machine_name)

        if machine.machine_number:
            _ensure_form_value(machine_number_field, str(machine.machine_number))

    main_form = MachineFilterForm(formdata=normalized, prefix="main_")
    advanced_form = EditMachineForm(formdata=normalized, prefix="adv_")
    pgu_machines_form = PGUMachineFilterForm(formdata=normalized, prefix="pgu_")
    
    year_features = get_year_feature_dict()
    
    redirect_args = request.args.to_dict(flat=False)
    redirect_args["start_year"] = start_year
    redirect_args["end_year"] = end_year
    redirect_args["rounding_digits"] = rounding_digits

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
                                    **redirect_args))

    _fill_main_form_choices(main_form)
    _fill_fuel_equipment_group_choices(main_form, station.id, machine)
    # Проверяем, нужно ли заполнять advanced_form choices
    print(f"[DEBUG] handle_machine_post: tes_types entries: {len(advanced_form.tes_types.entries)}")
    print(f"[DEBUG] handle_machine_post: fuels entries: {len(advanced_form.fuels.entries)}")
    # Всегда заполняем choices для вложенных полей перед validate, даже если entries уже есть
    _fill_advanced_form_choices(advanced_form)
    _fill_pgu_machines_form_choices(pgu_machines_form, machine_id=machine.id if machine else 0)

    pgu_ids_to_delete = request.form.getlist("pgu_machines_delete[]", type=int)

    # Удаляем ПГУ сразу, до валидации форм
    if pgu_ids_to_delete and not can_edit_generation:
        flash("Недостаточно прав для удаления ПГУ агрегатов.", "danger")
        return redirect(
            url_for(
                "station_bp.machine_details",
                station_id=station_id,
                machine_id=machine_id,
                start_year=start_year,
                end_year=end_year,
                rounding_digits=rounding_digits,
            )
        )

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
                                **redirect_args))
    
    is_pgu_action = any([
        pgu_machines_form.id_pgu_machine.data,
        pgu_machines_form.machine_name.data,
        pgu_machines_form.machine_number.data
    ])

    main_valid = main_form.validate()
    adv_valid = advanced_form.validate()
    adv_valid = adv_valid and _validate_power_ranges(advanced_form, normalized)
    pgu_valid = pgu_machines_form.validate() if (is_pgu_action and can_edit_generation) else True

    if not (main_valid and adv_valid and pgu_valid):
        print("main_form.errors:", main_form.errors)
        print("advanced_form.errors:", advanced_form.errors)
        print("pgu_machines_form.errors:", pgu_machines_form.errors)
        print(f"[DEBUG] Ошибка валидации: tes_types entries: {len(advanced_form.tes_types.entries)}")
        print(f"[DEBUG] Ошибка валидации: fuels entries: {len(advanced_form.fuels.entries)}")
        flash(
            "Ошибка в заполнении формы.",
            "danger",
        )
        # Оптимизированная загрузка документов - только id и name с фильтрацией по версии
        all_documents = choices_cache.get_choices(Document, Document.name)
        # Преобразуем обратно в объекты для совместимости с шаблоном
        all_documents = [Document(id=doc_id, name=doc_name) for doc_id, doc_name in all_documents]
        _fill_fuel_equipment_group_choices(main_form, station.id, machine)
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

        # Создаем новый агрегат, если это новая запись
        if is_new and not can_edit_generation:
            flash("Создание агрегата доступно только ролям модуля «Генерация».", "danger")
            return redirect(
                url_for(
                    "station_bp.machine_details",
                    station_id=station_id,
                    machine_id=0,
                    start_year=start_year,
                    end_year=end_year,
                    rounding_digits=rounding_digits,
                )
            )

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

        # Определяем тип станции для логики обработки названий
        try:
            st_name = (station.station_type.name or '').strip().lower() if station.station_type else ''
        except Exception:
            st_name = ''
        is_tes_or_ges = st_name in ('тэс', 'гэс', 'гаэс')

        # Получаем кэшированные справочники для логирования
        condition_types = dict(choices_cache.get_choices(ConditionType, ConditionType.id))
        gen_companies = dict(choices_cache.get_choices(GenCompany, GenCompany.id))
        machine_types = dict(choices_cache.get_choices(MachineType, MachineType.id))
        tes_machine_types = dict(choices_cache.get_choices(TesMachineType, TesMachineType.id))
        equipment_groups = dict(choices_cache.get_choices(EquipmentGroupType, EquipmentGroupType.id))

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
            "relabing_outcome": lambda x: x or "не указано",
            "machine_group": str,
        }

        # Список полей, которые являются внешними ключами и должны конвертировать 0 в None
        fk_fields = {
            'id_condition_type',
            'id_gen_company',
            'id_machine_type',
            'id_tes_machine_type',
            'id_equipment_group',
        }
        
        for fld, to_str in field_map.items():
            if fld in ("id_tes_machine_type", "id_equipment_group") and not can_edit_fuel:
                continue
            if fld not in ("id_tes_machine_type", "id_equipment_group") and not can_edit_generation:
                continue
            old_v = getattr(machine, fld) if not is_new else None
            if is_tes_or_ges and fld == "machine_name":
                # Для ТЭС/ГЭС/ГАЭС название агрегата формируется из machine_names
                # и не должно обновлять Machine.machine_name из формы.
                continue

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

        date_fields = [
            "date_exploitation",
            "date_exploitation_expected",
            "date_commission_fact",
            "date_joining_expected",
            "date_joining_fact",
            "date_detatchment_fact",
            "date_decompressing_expected",
            "date_decompressing_fact",
            "date_modernization_power_change_expected",
            "date_modernization_no_power_change_expected",
            "date_relabing_fact",
            "date_update_fact",
        ]

        # Годы диапазона текущей версии БД — нужны для ограничений по ожидаемому году вывода
        version_year_start, version_year_end = get_current_version_year_range_from_name()

        if can_edit_generation:
            for fld in date_fields:
                raw_form_value = getattr(main_form, fld).data

                # Если указана фактическая дата вывода из эксплуатации, ожидаемый год вывода должен быть пустым
                if fld == "date_decompressing_expected" and main_form.date_decompressing_fact.data:
                    raw_form_value = None

                if fld in {
                    "date_exploitation",
                    "date_exploitation_expected",
                    "date_decompressing_expected",
                    "date_modernization_power_change_expected",
                    "date_modernization_no_power_change_expected",
                }:
                    new_val = int(raw_form_value) if raw_form_value else None
                elif fld in {"date_relabing_fact", "date_update_fact"}:
                    # Для полей с несколькими датами нормализуем список дат в единый формат
                    new_val = normalize_date_list(raw_form_value) if raw_form_value else None
                else:
                    new_val = convert_to_date(raw_form_value)

                # Ограничение: ожидаемый год вывода из эксплуатации не может быть > последнего года версии БД
                if (
                    fld == "date_decompressing_expected"
                    and isinstance(new_val, int)
                    and version_year_end is not None
                    and new_val > version_year_end
                ):
                    new_val = None

                old_val = getattr(machine, fld) if not is_new else None
                if isinstance(old_val, (date, datetime)):
                    old_val_str = old_val.strftime("%Y-%m-%d")
                else:
                    old_val_str = str(old_val) if old_val is not None else None

                if isinstance(new_val, (date, datetime)):
                    new_val_str = new_val.strftime("%Y-%m-%d")
                else:
                    new_val_str = str(new_val) if new_val is not None else None

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

            # Отдельная обработка поля year-ввода в работу (целое число, не дата)
            raw_commission_year = main_form.date_commission_year.data
            new_commission_year = int(raw_commission_year) if raw_commission_year else None
            old_commission_year = getattr(machine, "date_commission_year", None) if not is_new else None
            old_commission_year_str = str(old_commission_year) if old_commission_year is not None else None
            new_commission_year_str = str(new_commission_year) if new_commission_year is not None else None

            if is_new:
                if new_commission_year is not None:
                    changes.append(f"date_commission_year: {new_commission_year_str}")
                setattr(machine, "date_commission_year", new_commission_year)
            else:
                if old_commission_year_str != new_commission_year_str:
                    changes.append(f"date_commission_year: {old_commission_year_str} → {new_commission_year_str}")
                    setattr(machine, "date_commission_year", new_commission_year)

        # Для нового агрегата нужно flush, чтобы получить machine.id
        if is_new:
            db.session.flush()

        # При изменении типа группы оборудования или планового года ввода
        # синхронизируем конкретную fuel-группу агрегата (обычная / "(нов)").
        version_id = getattr(machine, "database_version_id", None) or get_current_db_version_id()

        old_fuel_eg_id = None
        if machine.id:
            mfp_before = _get_machine_fuel_param_for_version(machine.id, version_id)
            if mfp_before:
                old_fuel_eg_id = mfp_before.equipment_group_id

        sync_machine_fuel_equipment_group(
            machine,
            version_id=version_id,
        )

        if can_edit_fuel:
            raw_fuel_eg = main_form.id_fuel_equipment_group.data
            if not choices_cache.is_empty_value(raw_fuel_eg):
                allowed_ids = {gid for gid, _ in get_station_fuel_equipment_group_choice_tuples(
                    station.id, version_id
                )}
                if raw_fuel_eg in allowed_ids:
                    mfp = _get_machine_fuel_param_for_version(machine.id, version_id)
                    if mfp is None:
                        mfp = MachineFuelParam(machine_id=machine.id)
                        if version_id is not None:
                            mfp.database_version_id = version_id
                        elif get_current_db_version_id() is not None:
                            set_db_version_on_create(mfp)
                        db.session.add(mfp)
                        db.session.flush()
                    if mfp.equipment_group_id != raw_fuel_eg:
                        mfp.equipment_group_id = raw_fuel_eg
                        db.session.add(mfp)

        mfp_after = _get_machine_fuel_param_for_version(machine.id, version_id)
        new_fuel_eg_id = mfp_after.equipment_group_id if mfp_after else None
        if old_fuel_eg_id != new_fuel_eg_id:
            def _eg_label(eg_id):
                if not eg_id:
                    return "—"
                eg = EquipmentGroup.query.get(eg_id)
                return (eg.name if eg else None) or f"id={eg_id}"

            changes.append(
                f"Группа оборудования (топливный модуль): {_eg_label(old_fuel_eg_id)} → {_eg_label(new_fuel_eg_id)}"
            )

        if st_name == "тэс" and machine.id and can_edit_fuel:
            raw_th = main_form.thermal_power_gcalh.data
            new_nt = None
            if raw_th is not None and str(raw_th).strip() not in ("",):
                try:
                    new_nt = raw_th if isinstance(raw_th, Decimal) else Decimal(str(raw_th).replace(",", "."))
                except (InvalidOperation, ValueError):
                    new_nt = None
            if new_nt is not None:
                new_nt = new_nt.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

            def _nt_to_dec(v):
                if v is None:
                    return None
                if isinstance(v, Decimal):
                    return v.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
                return Decimal(str(v)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

            mfp_nt = _get_machine_fuel_param_for_version(machine.id, version_id)
            old_nt = _nt_to_dec(mfp_nt.nt) if mfp_nt and mfp_nt.nt is not None else None
            if mfp_nt is None and new_nt is not None:
                mfp_nt = MachineFuelParam(machine_id=machine.id)
                if version_id is not None:
                    mfp_nt.database_version_id = version_id
                elif get_current_db_version_id() is not None:
                    set_db_version_on_create(mfp_nt)
                db.session.add(mfp_nt)
                db.session.flush()
            if mfp_nt is not None and old_nt != new_nt:
                mfp_nt.nt = new_nt
                db.session.add(mfp_nt)
                _old_l = "—" if old_nt is None else format_decimal_trim_for_display(old_nt, digits=0)
                _new_l = "—" if new_nt is None else format_decimal_trim_for_display(new_nt, digits=0)
                changes.append(f"Тепловая мощность, Гкал/ч: {_old_l} → {_new_l}")

        # Фильтруем записи с None.year для предотвращения AttributeError
        powers_map = {mp.year.number: mp for mp in machine.machine_powers if mp.year is not None}
        tes_map = {mt.year.number: mt for mt in machine.machine_tes_types if mt.year is not None}
        fuel_map = {mf.year.number: mf for mf in machine.machine_fuels if mf.year is not None}
        names_map = {mn.year_number: mn for mn in machine.machine_names if mn.year_number is not None}
        
        # Флаг для отслеживания изменений в связанных сущностях
        related_entities_changed = False
        
        # Получаем объекты Year для создания связанных записей
        years = Year.query.filter(Year.number >= start_year, Year.number <= end_year).all()
        year_dict = {y.number: y for y in years}

        # Определяем тип станции и "текущий год" версии БД
        try:
            st_name = (station.station_type.name or '').strip().lower() if station.station_type else ''
        except Exception:
            st_name = ''
        is_tes_or_ges = st_name in ('тэс', 'гэс', 'гаэс')
        version_year_start, version_year_end = get_current_version_year_range_from_name()
        current_year_for_version = version_year_end
        # Последнее ненулевое "эффективное" название для автозаполнения (как для мощностей)
        last_effective_name = None

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

            if year_num not in names_map:
                mn_obj = MachineName(id_machine=machine.id, year_number=year_num)
                set_db_version_on_create(mn_obj)
                db.session.add(mn_obj)
                names_map[year_num] = mn_obj

            mp, mt, mf = powers_map[year_num], tes_map[year_num], fuel_map[year_num]
            mn_obj = names_map[year_num]

            if can_edit_generation:
                # Получаем raw значения из формы для определения, были ли поля изменены пользователем
                p_ust_raw = advanced_form.powers[i].p_ust.data
                p_ogr_raw = advanced_form.powers[i].p_ogr.data
                p_rasp_raw = advanced_form.powers[i].p_rasp.data
                # Сырые значения из формы и *_orig для защиты от перезаписи при правке других полей
                p_ust_form_raw = normalized.get(advanced_form.powers[i].p_ust.name)
                p_ogr_form_raw = normalized.get(advanced_form.powers[i].p_ogr.name)
                p_rasp_form_raw = normalized.get(advanced_form.powers[i].p_rasp.name)
                p_ust_orig_raw = normalized.get(f"{advanced_form.powers[i].p_ust.name}_orig")
                p_ogr_orig_raw = normalized.get(f"{advanced_form.powers[i].p_ogr.name}_orig")
                p_rasp_orig_raw = normalized.get(f"{advanced_form.powers[i].p_rasp.name}_orig")
                
                # Конвертируем значения (пустые строки и специальные символы → None)
                p_ust_new = to_decimal(p_ust_raw)
                p_ogr_new = to_decimal(p_ogr_raw)
                p_rasp_new = to_decimal(p_rasp_raw)
                
                # Определяем, изменил ли пользователь поля мощности относительно *_orig
                # Если *_orig отсутствует, считаем поле измененным только при наличии ввода.
                def _power_field_changed(raw_value, orig_value):
                    if orig_value in (None, '', '—', '-'):
                        return raw_value not in (None, '', '—', '-')
                    return not is_same_decimal(to_decimal(raw_value), to_decimal(orig_value))

                power_fields_changed = (
                    _power_field_changed(p_ust_form_raw, p_ust_orig_raw)
                    or _power_field_changed(p_ogr_form_raw, p_ogr_orig_raw)
                    or _power_field_changed(p_rasp_form_raw, p_rasp_orig_raw)
                )
                # Сохраняем прежнюю логику автозаполнения:
                # если пользователь не трогал мощности, ничего не пересчитываем.
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
                    if not power_fields_changed:
                        # Не трогаем мощности, если пользователь их не менял
                        p_ust = mp.p_ust
                        p_ogr = mp.p_ogr
                        p_rasp = mp.p_rasp
                        skip_ogr = True
                        skip_rasp = True
                    else:
                        p_ust = p_ust_new if p_ust_new is not None else (mp.p_ust if mp.p_ust else Decimal(0))
                        if user_modified_p_ogr:
                            p_ogr = p_ogr_new if p_ogr_new is not None else Decimal(0)
                        else:
                            p_ogr = mp.p_ogr if mp.p_ogr is not None else Decimal(0)
                        if user_modified_p_rasp:
                            p_rasp = p_rasp_new if p_rasp_new is not None else Decimal(0)
                        else:
                            p_rasp = mp.p_rasp if mp.p_rasp is not None else Decimal(0)
                        skip_ogr = user_modified_p_ogr
                        skip_rasp = user_modified_p_rasp

                # Передаем флаги в автозаполнение, чтобы не перезаписывать значения, введенные пользователем
                if is_new:
                    skip_ogr = user_modified_p_ogr
                    skip_rasp = user_modified_p_rasp
                p_ust, p_ogr, p_rasp = autofill_powers_if_possible_decimal(
                    p_ust, p_ogr, p_rasp, year_num,
                    skip_ogr=skip_ogr,
                    skip_rasp=skip_rasp
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
            # Распознаем тип станции по названию
            try:
                st_name = (station.station_type.name or '').strip().lower() if station.station_type else ''
            except Exception:
                st_name = ''
            is_tes_station = (st_name == 'тэс')
            if is_tes_station and can_edit_fuel:
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

            # Название по году (machine_names)
            if can_edit_generation and i < len(advanced_form.machine_names):
                raw_name = (advanced_form.machine_names[i].year_name.data or "").strip() or None

                # Для нового агрегата ТЭС/ГЭС, если для "текущего года" название по годам не задано,
                # автоматически подставляем общее machine_name
                if (
                    is_new
                    and is_tes_or_ges
                    and current_year_for_version is not None
                    and year_num == current_year_for_version
                    and not raw_name
                ):
                    raw_name = (machine.machine_name or "").strip() or None

                # Логика как для мощности:
                # - если пользователь ввел новое название в каком‑то году, протягиваем его на все последующие годы;
                # - значения для годов > текущего года версии БД не сохраняем.
                if is_tes_or_ges and current_year_for_version is not None:
                    if year_num > current_year_for_version:
                        effective_name = None
                    else:
                        if raw_name:
                            last_effective_name = raw_name
                        effective_name = last_effective_name if last_effective_name else raw_name
                else:
                    # Для остальных типов станций — без автоподстановки, по году
                    effective_name = raw_name

                old_name = mn_obj.name if mn_obj.name else None
                if old_name != effective_name:
                    mn_obj.name = effective_name
                    flag_modified(mn_obj, "name")
                    if is_new and effective_name:
                        changes.append(f"Название по году {year_num}: {effective_name}")
                    elif not is_new:
                        changes.append(f"Название по году {year_num}: {old_name or '—'} → {effective_name or '—'}")
                    related_entities_changed = True

        # Для ТЭС/ГЭС/ГАЭС: поле "Название агрегата" (текущее + в скобках перспективное)
        # проверяем с Machine.machine_name и при несовпадении сохраняем в Machine.machine_name.
        if is_tes_or_ges and can_edit_generation:
            # Берем значение из формы (то, что отображалось пользователю)
            form_display_name = (main_form.machine_name.data or "").strip() or None
            version_year_for_base = version_year_start if version_year_start is not None else version_year_end
            if not form_display_name and (version_year_for_base is not None or version_year_end is not None):
                # Fallback: пересчитываем из machine_names, если в форме пусто
                base_name = None
                if version_year_for_base is not None:
                    mn_current = names_map.get(version_year_for_base) if names_map else None
                    if mn_current and mn_current.name:
                        base_name = mn_current.name.strip()
                if not base_name and version_year_end is not None:
                    mn_current = names_map.get(version_year_end) if names_map else None
                    if mn_current and mn_current.name:
                        base_name = mn_current.name.strip()
                if not base_name and machine.machine_name:
                    base_name = machine.machine_name.strip()
                form_display_name = base_name
                if base_name and year_features:
                    for y in sorted(names_map.keys()):
                        label = year_features.get(y)
                        if not label or "план" not in str(label).strip().lower():
                            continue
                        mn_plan = names_map.get(y)
                        if not mn_plan or not mn_plan.name:
                            continue
                        plan_name = mn_plan.name.strip()
                        if plan_name and plan_name.lower() != base_name.lower():
                            form_display_name = f"{base_name} ({plan_name})"
                            break

            if form_display_name and form_display_name != (machine.machine_name or None):
                changes.append(
                    f"machine_name: {(machine.machine_name or '—')} → {form_display_name}"
                )
                machine.machine_name = form_display_name

        # Если изменились связанные сущности, обновляем Machine для инкремента version
        if related_entities_changed:
            from sqlalchemy.sql import func
            machine.updated_at = func.now()
            flag_modified(machine, 'updated_at')

        if is_pgu_action and can_edit_generation and pgu_machines_form.id_pgu_machine.data:
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
                    new_val = int(raw_val) if raw_val and fld in {
                        "date_exploitation",
                        "date_decompressing_expected",
                        "date_modernization_power_change_expected",
                        "date_modernization_no_power_change_expected",
                    } else convert_to_date(raw_val)
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
            names_map=names_map,
            can_edit_fuel=can_edit_fuel,
            can_edit_generation=can_edit_generation,
        )
        recalculate_station_power(station, start_year, end_year)
        if can_edit_generation:
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

        return redirect(url_for("station_bp.machine_details",
                                station_id=station.id,
                                machine_id=machine.id,
                                **redirect_args))

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
        _fill_fuel_equipment_group_choices(main_form, station.id, machine)
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
    version_year_start, version_year_end = get_current_version_year_range_from_name()

    if pgu_machine_id == 0:
        pgu_machine = None
        pgu_form = PGUMachineFilterForm(prefix='pgu_')
    else:
        pgu_machine = PGUMachine.query.get_or_404(pgu_machine_id)
        pgu_form = PGUMachineFilterForm(obj=pgu_machine, prefix='pgu_')

    from app.generation.services.machine_services.machine_services import _fill_pgu_machines_form_choices
    _fill_pgu_machines_form_choices(pgu_form, machine_id, parent_machine=parent_machine)
    pgu_form.id_machine.data = machine_id

    pgu_machine = PGUMachine.query.get(pgu_machine_id) if pgu_machine_id else None

    existing_powers = {}
    pgu_machine_names = {}
    if pgu_machine:
        for power in pgu_machine.pgu_machine_powers:
            existing_powers[power.year_number] = power
        names_q = PGUMachineName.query.filter_by(id_pgu_machine=pgu_machine.id)
        pgu_machine_names = {
            mn.year_number: mn
            for mn in names_q.all()
            if mn.year_number is not None
        }

    # Заполняем powers и pgu_machine_names из БД. Не полагаемся на obj=pgu_machine:
    # модель использует year_number/name, форма — year/year_name, маппинг не совпадает.
    del pgu_form.powers.entries[:]
    for year in range(start_year, end_year + 1):
        value = existing_powers.get(year).p_ust if existing_powers.get(year) else 0
        pgu_form.powers.append_entry({"year": year, "p_ust": value})

    # Всегда заполняем pgu_machine_names из pgu_machine_names dict (из БД)
    del pgu_form.pgu_machine_names.entries[:]
    for year_num in range(start_year, end_year + 1):
        name_entry = pgu_form.pgu_machine_names.append_entry()
        name_entry.year.data = year_num
        pmn = pgu_machine_names.get(year_num) if pgu_machine_names else None
        name_entry.year_name.data = (pmn.name if pmn and pmn.name else None) or ""

    # Для ТЭС/ГЭС/ГАЭС формируем "Название агрегата" из pgu_machine_names (как для Machine)
    try:
        st_name = (station.station_type.name or "").strip().lower() if station.station_type else ""
    except Exception:
        st_name = ""
    is_tes_or_ges = st_name in ("тэс", "гэс", "гаэс")
    version_year_for_base = version_year_start if version_year_start is not None else version_year_end
    if is_tes_or_ges and pgu_machine is not None and (version_year_for_base is not None or version_year_end is not None):
        def _valid_name(s):
            return s and not (len(s) == 4 and s.isdigit())

        base_name = None
        if version_year_for_base is not None:
            pmn_current = pgu_machine_names.get(version_year_for_base) if pgu_machine_names else None
            if pmn_current and pmn_current.name and _valid_name(pmn_current.name.strip()):
                base_name = pmn_current.name.strip()
        if not base_name and version_year_end is not None:
            pmn_current = pgu_machine_names.get(version_year_end) if pgu_machine_names else None
            if pmn_current and pmn_current.name and _valid_name(pmn_current.name.strip()):
                base_name = pmn_current.name.strip()
        if not base_name and pgu_machine.machine_name and _valid_name(pgu_machine.machine_name.strip()):
            base_name = pgu_machine.machine_name.strip()
        if not base_name and pgu_machine_names:
            for y in sorted(pgu_machine_names.keys(), reverse=True):
                pmn = pgu_machine_names.get(y)
                if pmn and pmn.name and _valid_name(pmn.name.strip()):
                    base_name = pmn.name.strip()
                    break
        display_name = base_name
        if base_name and year_features:
            for y in sorted(pgu_machine_names.keys()):
                label = year_features.get(y)
                if not label or "план" not in str(label).strip().lower():
                    continue
                pmn_plan = pgu_machine_names.get(y)
                if not pmn_plan or not pmn_plan.name:
                    continue
                plan_name = pmn_plan.name.strip()
                if plan_name and plan_name.lower() != base_name.lower():
                    display_name = f"{base_name} ({plan_name})"
                    break
        if display_name:
            pgu_form.machine_name.data = display_name
            # Исправить отображение в заголовке, если в БД ошибочно сохранен год как название
            if pgu_machine.machine_name != display_name and (
                not pgu_machine.machine_name or (len(pgu_machine.machine_name.strip()) == 4 and pgu_machine.machine_name.strip().isdigit())
            ):
                pgu_machine.machine_name = display_name

    all_documents = choices_cache.get_choices(Document, Document.name)
    all_documents = [Document(id=doc_id, name=doc_name) for doc_id, doc_name in all_documents]

    context = {
        "station": station,
        "parent_machine": parent_machine,
        "pgu_form": pgu_form,
        "start_year": start_year,
        "end_year": end_year,
        "pgu_machine_id": pgu_machine_id,
        "pgu_machine": pgu_machine,
        "year_features": year_features,
        "version_year_start": version_year_start,
        "version_year_end": version_year_end,
        "all_documents": all_documents,
    }
    return context


def _normalize_pgu_form_data(form_data, start_year, end_year):
    """Нормализация данных формы: запятая→точка в p_ust; валидный int для year в pgu_machine_names."""
    from werkzeug.datastructures import ImmutableMultiDict
    import re
    items = []
    for key in form_data:
        for value in form_data.getlist(key):
            if '-p_ust' in key or key.endswith('p_ust'):
                if isinstance(value, str) and ',' in value:
                    value = value.replace(',', '.')
            # Нормализуем только сами поля `...-year`.
            # Важно не задевать `...-year_name`, иначе строки вроде `V 64.3А`
            # ошибочно попадают в ветку обработки года и затираются номером года.
            if re.search(r'(?:machine_names|powers)-\d+-year$', key):
                if isinstance(value, str):
                    value = value.strip()
                    m = re.search(r'(?:machine_names|powers)-(\d+)-year', key)
                    idx = int(m.group(1)) if m else 0
                    if value in ('', '—', '-') or not value:
                        value = str(start_year + idx)
                    elif '.' in value:
                        try:
                            value = str(int(float(value)))
                        except (ValueError, TypeError):
                            value = str(start_year + idx)
            items.append((key, value))
    return ImmutableMultiDict(items)


@no_autoflush
def handle_pgu_machine_post(station_id, machine_id, pgu_machine_id, form_data, user, start_year, end_year, rounding_digits=1):
    station = Station.query.get_or_404(station_id)
    parent_machine = Machine.query.get_or_404(machine_id)
    redirect_args = request.args.to_dict(flat=False)
    redirect_args["start_year"] = start_year
    redirect_args["end_year"] = end_year
    redirect_args["rounding_digits"] = rounding_digits

    form_data = _normalize_pgu_form_data(form_data, start_year, end_year)
    pgu_form = PGUMachineFilterForm(form_data, prefix='pgu_')
    _fill_pgu_machines_form_choices(pgu_form, machine_id, parent_machine=parent_machine)

    # Для ТЭС/ГЭС/ГАЭС machine_name формируется из таблицы pgu_machine_names.
    # Если в форме machine_name пусто, подставляем из первого непустого названия по году,
    # иначе "Без названия" — чтобы валидатор DataRequired не падал (данные обработаются ниже).
    try:
        st_name = (station.station_type.name or "").strip().lower() if station.station_type else ""
    except Exception:
        st_name = ""
    # ТЭЦ, КЭС — подтипы ТЭС; для них тоже название из таблицы по годам
    if st_name in ("тэс", "гэс", "гаэс", "тэц", "кэс") and not (pgu_form.machine_name.data or "").strip():
        for name_entry in pgu_form.pgu_machine_names.entries:
            raw = (name_entry.year_name.data or "").strip()
            if raw:
                pgu_form.machine_name.data = raw
                break
        else:
            pgu_form.machine_name.data = "Без названия"

    if not pgu_form.validate():
        err_msgs = []
        _field_labels = {"machine_name": "Название агрегата", "p_ust": "Мощность"}
        for field_name, errors in pgu_form.errors.items():
            if errors:
                label = _field_labels.get(field_name.split("-")[-1], field_name)
                err_msgs.append(f"{label}: {'; '.join(str(e) for e in errors)}")
        flash(
            "Ошибка в заполнении формы." + (" " + err_msgs[0] if err_msgs else ""),
            "danger",
        )
        _, version_year_end = get_current_version_year_range_from_name()
        year_features = get_year_feature_dict()
        # Заполняем pgu_machine_names и powers при ошибке валидации, если пусто
        if not pgu_form.pgu_machine_names.entries:
            for year_num in range(start_year, end_year + 1):
                name_entry = pgu_form.pgu_machine_names.append_entry()
                name_entry.year.data = year_num
                name_entry.year_name.data = ""
        if not pgu_form.powers.entries:
            for year_num in range(start_year, end_year + 1):
                power_entry = pgu_form.powers.append_entry()
                power_entry.year.data = year_num
                power_entry.p_ust.data = Decimal("0")
        all_documents = choices_cache.get_choices(Document, Document.name)
        all_documents = [Document(id=doc_id, name=doc_name) for doc_id, doc_name in all_documents]
        pgu_machine_for_template = PGUMachine.query.get(pgu_machine_id) if pgu_machine_id else None
        return render_template(
            "generation/stations/pgu_machine_details.html",
            station=station,
            parent_machine=parent_machine,
            pgu_form=pgu_form,
            start_year=start_year,
            end_year=end_year,
            pgu_machine_id=pgu_machine_id,
            pgu_machine=pgu_machine_for_template,
            pgu_machine_logs=[],
            year_features=year_features,
            version_year_end=version_year_end,
            rounding_digits=rounding_digits,
            all_documents=all_documents,
        )

    try:
        changes = []
        is_new = pgu_machine_id == 0
        
        with db.session.no_autoflush:
            if is_new:
                machine_name = (pgu_form.machine_name.data or "").strip() or "Без названия"
                machine_number = (pgu_form.machine_number.data or "").strip() or None
                pgu_machine = PGUMachine(
                    id_parent_machine=machine_id,
                    machine_name=machine_name,
                    machine_number=machine_number,
                )
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
                                            **redirect_args))

            # Логирование изменений полей
            from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroupType
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
            "change_document": lambda x: x or "не указано",
        }

            # Список полей, которые являются внешними ключами и должны конвертировать 0 в None
            pgu_fk_fields = {'id_condition_type', 'id_pgu_tes_machine_type'}

            # Для ТЭС/ГЭС/ГАЭС machine_name формируется из pgu_machine_names, не из формы
            try:
                st_name = (station.station_type.name or "").strip().lower() if station.station_type else ""
            except Exception:
                st_name = ""
            is_tes_or_ges = st_name in ("тэс", "гэс", "гаэс")
            
            for fld, to_str in field_map.items():
                if is_tes_or_ges and fld == "machine_name":
                    continue
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
                "date_exploitation",
                "date_commission_year",
                "date_exploitation_expected",
                "date_commission_fact",
                "date_joining_expected",
                "date_joining_fact",
                "date_detatchment_fact",
                "date_decompressing_expected",
                "date_decompressing_fact",
                "date_modernization_power_change_expected",
                "date_modernization_no_power_change_expected",
                "date_relabing_fact",
                "date_update_fact",
            ]

            int_year_fields = {
                "date_exploitation",
                "date_commission_year",
                "date_exploitation_expected",
                "date_decompressing_expected",
                "date_modernization_power_change_expected",
                "date_modernization_no_power_change_expected",
            }

            for fld in date_fields:
                raw_form_value = getattr(pgu_form, fld).data

                if fld in int_year_fields:
                    try:
                        new_val = int(raw_form_value) if raw_form_value else None
                    except (ValueError, TypeError):
                        new_val = None
                elif fld in {"date_relabing_fact", "date_update_fact"}:
                    # Для полей с несколькими датами нормализуем список дат в единый формат
                    new_val = normalize_date_list(raw_form_value) if raw_form_value else None
                else:
                    new_val = convert_to_date(raw_form_value)

                old_val = getattr(pgu_machine, fld) if not is_new else None
                if isinstance(old_val, (date, datetime)):
                    old_val_str = old_val.strftime("%Y-%m-%d")
                else:
                    old_val_str = str(old_val) if old_val is not None else None

                if isinstance(new_val, (date, datetime)):
                    new_val_str = new_val.strftime("%Y-%m-%d")
                else:
                    new_val_str = str(new_val) if new_val is not None else None

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
            # FK: (year_number, database_version_id) должен существовать в gs_sys_years
            version_id = get_current_db_version_id()
            valid_years = set(
                y[0] for y in
                db.session.query(Year.number).filter_by(database_version_id=version_id).all()
            ) if version_id else set()

            PGUMachinePower.query.filter_by(id_pgu_machine=pgu_machine.id).delete()

            for power_entry in pgu_form.powers.entries:
                year = power_entry.year.data
                if valid_years and year not in valid_years:
                    continue  # Год отсутствует в gs_sys_years — пропускаем (FK)
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

            # Сохранение названий по годам (pgu_machine_names)
            year_features = get_year_feature_dict()
            version_year_start, version_year_end = get_current_version_year_range_from_name()
            names_map = {mn.year_number: mn for mn in pgu_machine.pgu_machine_names if mn.year_number is not None}
            last_effective_name = None

            for i, name_entry in enumerate(pgu_form.pgu_machine_names.entries):
                year_num = name_entry.year.data
                if valid_years and year_num not in valid_years:
                    continue  # Год отсутствует в gs_sys_years — пропускаем (FK)
                raw_name = (name_entry.year_name.data or "").strip() or None
                # Не сохранять как название значение, похожее на год (4 цифры) — возможно, year попал в year_name
                if raw_name and len(raw_name) == 4 and raw_name.isdigit():
                    raw_name = None

                if is_new and is_tes_or_ges and version_year_end is not None and year_num == version_year_end and not raw_name:
                    raw_name = (pgu_form.machine_name.data or "").strip() or None

                if is_tes_or_ges and version_year_end is not None:
                    if year_num > version_year_end:
                        effective_name = None
                    else:
                        if raw_name:
                            last_effective_name = raw_name
                        effective_name = last_effective_name if last_effective_name else raw_name
                else:
                    effective_name = raw_name

                if year_num not in names_map:
                    pmn_obj = PGUMachineName(id_pgu_machine=pgu_machine.id, year_number=year_num)
                    set_db_version_on_create(pmn_obj)
                    db.session.add(pmn_obj)
                    db.session.flush()
                    names_map[year_num] = pmn_obj

                pmn_obj = names_map[year_num]
                old_name = pmn_obj.name if pmn_obj.name else None
                if old_name != effective_name:
                    pmn_obj.name = effective_name
                    flag_modified(pmn_obj, "name")
                    if is_new and effective_name:
                        changes.append(f"Название по году {year_num}: {effective_name}")
                    elif not is_new:
                        changes.append(f"Название по году {year_num}: {old_name or '—'} → {effective_name or '—'}")

            # Для ТЭС/ГЭС/ГАЭС пересчитываем machine_name из pgu_machine_names
            version_year_for_base = version_year_start if version_year_start is not None else version_year_end
            if is_tes_or_ges and (version_year_for_base is not None or version_year_end is not None):
                base_name = None
                if version_year_for_base is not None and names_map:
                    pmn_current = names_map.get(version_year_for_base)
                    if pmn_current and pmn_current.name:
                        cand = pmn_current.name.strip()
                        if cand and not (len(cand) == 4 and cand.isdigit()):
                            base_name = cand
                if not base_name and version_year_end is not None and names_map:
                    pmn_current = names_map.get(version_year_end)
                    if pmn_current and pmn_current.name:
                        cand = pmn_current.name.strip()
                        if cand and not (len(cand) == 4 and cand.isdigit()):
                            base_name = cand
                if not base_name and pgu_machine.machine_name:
                    cand = pgu_machine.machine_name.strip()
                    if cand and not (len(cand) == 4 and cand.isdigit()):
                        base_name = cand
                if not base_name and names_map:
                    for y in sorted(names_map.keys(), reverse=True):
                        pmn = names_map.get(y)
                        if pmn and pmn.name:
                            cand = pmn.name.strip()
                            if cand and not (len(cand) == 4 and cand.isdigit()):
                                base_name = cand
                                break
                display_name = base_name
                if base_name and year_features:
                    for y in sorted(names_map.keys()):
                        label = year_features.get(y)
                        if not label or "план" not in str(label).strip().lower():
                            continue
                        pmn_plan = names_map.get(y)
                        if not pmn_plan or not pmn_plan.name:
                            continue
                        plan_name = pmn_plan.name.strip()
                        if plan_name and plan_name.lower() != base_name.lower():
                            display_name = f"{base_name} ({plan_name})"
                            break
                if display_name and display_name != (pgu_machine.machine_name or None):
                    changes.append(f"machine_name: {(pgu_machine.machine_name or '—')} → {display_name}")
                    pgu_machine.machine_name = display_name

            # Поля date_exploitation, date_exploitation_expected, date_decompressing_expected,
            # date_modernization_power_change_expected, date_modernization_no_power_change_expected
            # сохраняются только из формы (в т.ч. то, что определил фронт).

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
                details="; ".join(changes) if changes else f"ID: {pgu_machine.id}",
                entity_type="pgu_machine",
                entity_id=pgu_machine.id,
            )
            flash(f"Агрегат ПГУ успешно добавлен!", "success")
        else:
            if changes:
                log_to_db(
                    user, 
                    f"Изменения на станции {station.name} в агрегате ПГУ '{pgu_machine.machine_name}' (UID: {pgu_machine.id}) ", 
                    details="; ".join(changes),
                    entity_type="pgu_machine",
                    entity_id=pgu_machine.id,
                )
                flash(f"Агрегат ПГУ успешно обновлен!", "success")
            else:
                flash("Изменений не обнаружено", "info")

        return redirect(url_for('station_bp.pgu_machine_details',
                                station_id=station.id,
                                machine_id=parent_machine.id,
                                pgu_machine_id=pgu_machine.id,
                                **redirect_args))

    except Exception as e:
        db.session.rollback()
        traceback.print_exc()
        flash(f"Ошибка при сохранении: {e}", "danger")
        log_to_db(user, f"Ошибка при сохранении ПГУ агрегата на станции {station.name}", details=str(e))
        _, version_year_end = get_current_version_year_range_from_name()
        year_features = get_year_feature_dict()
        all_documents = choices_cache.get_choices(Document, Document.name)
        all_documents = [Document(id=doc_id, name=doc_name) for doc_id, doc_name in all_documents]
        return render_template(
            "generation/stations/pgu_machine_details.html",
            station=station,
            parent_machine=parent_machine,
            pgu_form=pgu_form,
            start_year=start_year,
            end_year=end_year,
            pgu_machine_id=pgu_machine_id,
            pgu_machine=None,
            pgu_machine_logs=[],
            year_features=year_features,
            version_year_end=version_year_end,
            rounding_digits=rounding_digits,
            all_documents=all_documents,
        )
    

_choices_cache = {}

def _clear_choices_cache():
    """Очищает кэш choices (вызывать при изменении справочных данных)"""
    global _choices_cache
    _choices_cache.clear()

def clear_machine_choices_cache():
    """Публичная функция для очистки кэша choices из других модулей"""
    _clear_choices_cache()
    # Также очищаем базовый кэш и глобальный кэш выборок, чтобы обновились все справочники
    CacheService.clear_cache()
    ChoicesCacheService.clear_cache()

def _get_machine_fuel_param_for_version(
    machine_id: int,
    version_id: int | None,
) -> MachineFuelParam | None:
    q = MachineFuelParam.query.filter(MachineFuelParam.machine_id == machine_id)
    if version_id is None:
        q = q.filter(MachineFuelParam.database_version_id.is_(None))
    else:
        q = q.filter(MachineFuelParam.database_version_id == version_id)
    return q.first()


def _fill_fuel_equipment_group_choices(main_form, station_id: int, machine=None):
    """Список итоговых групп оборудования станции (топливный модуль) + авто-привязка."""
    version_id = get_current_db_version_id()
    tuples = get_station_fuel_equipment_group_choice_tuples(station_id, version_id)
    auto_label = "— по типу группы и плановому году (авто)"
    main_form.id_fuel_equipment_group.choices = [
        (choices_cache.EMPTY_VALUE_ID, auto_label)
    ] + tuples

    sel = main_form.id_fuel_equipment_group.data
    if sel and not choices_cache.is_empty_value(sel):
        ids = {c[0] for c in main_form.id_fuel_equipment_group.choices}
        if sel not in ids:
            eg = EquipmentGroup.query.get(sel)
            label = ((eg.name if eg else None) or "").strip() or f"Группа #{sel}"
            main_form.id_fuel_equipment_group.choices.append((sel, label))

    if main_form.id_fuel_equipment_group.data is None:
        mfp = None
        if machine and getattr(machine, "id", None):
            mfp = getattr(machine, "machine_fuel_param", None)
        if mfp and mfp.equipment_group_id:
            main_form.id_fuel_equipment_group.data = mfp.equipment_group_id
        else:
            main_form.id_fuel_equipment_group.data = choices_cache.EMPTY_VALUE_ID


def _fill_main_form_choices(form):
    """Заполняет choices для основной формы с использованием унифицированного кэширования"""
    # Добавляем дефолтное значение "не указано", чтобы оно отображалось в select
    # и могло выступать "пустым" значением до обязательного выбора пользователем.
    form.id_gen_company.choices = choices_cache.get_choices_with_default(GenCompany, GenCompany.id)
    form.id_energy_area.choices = choices_cache.get_choices(EnergyArea, EnergyArea.id)
    form.id_machine_type.choices = choices_cache.get_choices(MachineType, MachineType.id)
    form.id_tes_machine_type.choices = choices_cache.get_choices(TesMachineType, TesMachineType.id)
    form.id_equipment_group.choices = choices_cache.get_choices_with_default(EquipmentGroupType, EquipmentGroupType.id)
    
    form.id_condition_type.choices = choices_cache.get_choices(ConditionType, ConditionType.id)
    if form.id_condition_type.data is None:
        form.id_condition_type.data = choices_cache.EMPTY_VALUE_ID
    if form.id_equipment_group.data is None:
        form.id_equipment_group.data = choices_cache.EMPTY_VALUE_ID


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


def _fill_pgu_machines_form_choices(form, machine_id, parent_machine=None):
    """Заполняет choices для формы ПГУ с использованием унифицированного кэширования.
    Для pgu_machine_details parent_machine передается — используем только его, без загрузки всех агрегатов."""
    if parent_machine is not None:
        form.id_parent_machine.choices = [(parent_machine.id, parent_machine.machine_name or "—")]
    else:
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


def _coerce_decimal(val):
    if val is None:
        return None
    if isinstance(val, Decimal):
        return val
    try:
        if isinstance(val, str):
            val = val.replace(",", ".")
        return Decimal(val)
    except (InvalidOperation, TypeError, ValueError):
        return None


def is_same_decimal(a, b):
    a_dec = _coerce_decimal(a)
    b_dec = _coerce_decimal(b)

    if a_dec is None and (b_dec is None or b_dec == 0):
        return True
    if b_dec is None and (a_dec is None or a_dec == 0):
        return True

    if a_dec is None or b_dec is None:
        return False

    return a_dec == b_dec


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
    names_map=None,
    *,
    can_edit_fuel: bool = True,
    can_edit_generation: bool = True,
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
    if names_map is None:
        names_map = {mn.year_number: mn for mn in getattr(machine, "machine_names", []) if mn.year_number is not None}

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
        mn = names_map.get(year_num)

        p_ust = mp.p_ust or Decimal(0)
        p_ogr = mp.p_ogr or Decimal(0)
        p_rasp = mp.p_rasp or Decimal(0)

        if is_empty(p_ust) and is_empty(p_ogr) and is_empty(p_rasp):
            if can_edit_fuel:
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
                        flash(
                            f"🧠 {year_num} год: Топливо установлено: 'не указано' (все мощности = 0)",
                            "info",
                        )

            # Если по году все мощности равны нулю, дополнительно очищаем название по году
            if can_edit_generation and mn is not None and (mn.name or "").strip():
                old_name = mn.name.strip()
                mn.name = ""
                changes.append(f"Название по году: {year_num} год - {old_name} → —")
                # Обновляем форму, если соответствующая запись существует
                j = year_num - start_year
                if 0 <= j < len(advanced_form.machine_names):
                    advanced_form.machine_names[j].year_name.data = ""
        else:
            if can_edit_fuel:
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
        [
            (mp.year.number, mp.p_ust)
            for mp in machine.machine_powers
            if isinstance(mp.p_ust, Decimal) and mp.year is not None
        ],
        key=lambda t: t[0],
    )

    # Ограничиваем расчет только годами с признаком "план"
    try:
        plan_years_set = {
            y
            for y, name in (year_features or {}).items()
            if str(name or "").strip().lower() == "план"
        }
    except Exception:
        plan_years_set = set()

    if plan_years_set:
        years_by_ust = [(y, p) for y, p in years_by_ust if y in plan_years_set]

    # Дополнительно ограничиваем верхнюю границу годом из названия версии БД (если удалось его распарсить)
    _, version_year_end = get_current_version_year_range_from_name()
    if version_year_end:
        years_by_ust = [(y, p) for y, p in years_by_ust if y <= version_year_end]
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
    # ВАЖНО: авто по мощности — только ОДНО из трёх полей:
    # - date_exploitation_expected (ожидаемый год ввода)
    # - date_decompressing_expected (ожидаемый год вывода)
    # - date_modernization_power_change_expected (ожидаемый год модернизации с изменением мощности)
    # date_modernization_no_power_change_expected не вычисляется по мощности; при выборе одного из трёх
    # выше очищается вместе с «другой» модернизацией.
    #
    # Выбор делаем по приоритету событий мощности:
    # 1) вывод (>0 -> 0) — самый приоритетный
    # 2) ввод (0 -> >0)
    # 3) модернизация (>0 -> >0 и изменилось значение)
    # ============================================================
    # Если указана фактическая дата вывода, ожидаемый год не автоопределяем по мощности
    has_decompressing_fact = bool(
        getattr(machine, "date_decompressing_fact", None)
        and str(machine.date_decompressing_fact or "").strip()
    )
    effective_decomp_year = (
        new_decomp_year
        if (
            new_decomp_year is not None
            and new_decomp_year < Config.END_YEAR
            and not has_decompressing_fact
        )
        else None
    )

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
        if machine.date_modernization_power_change_expected is not None:
            changes.append(
                f"Ожидаемый год модернизации с изменением мощности: {machine.date_modernization_power_change_expected} → —"
            )
            machine.date_modernization_power_change_expected = None
        if machine.date_modernization_no_power_change_expected is not None:
            changes.append(
                f"Ожидаемый год модернизации без изменения мощности: {machine.date_modernization_no_power_change_expected} → —"
            )
            machine.date_modernization_no_power_change_expected = None

    elif selected_kind == "expl":
        if machine.date_exploitation_expected != selected_year:
            changes.append(f"Ожидаемый год ввода: {machine.date_exploitation_expected} → {selected_year}")
            flash(f"🧠 Ожидаемый год ввода автоматически определен: {selected_year}", "info")
            machine.date_exploitation_expected = selected_year
        if machine.date_decompressing_expected is not None:
            changes.append(f"Год вывода: {machine.date_decompressing_expected} → —")
            machine.date_decompressing_expected = None
        if machine.date_modernization_power_change_expected is not None:
            changes.append(
                f"Ожидаемый год модернизации с изменением мощности: {machine.date_modernization_power_change_expected} → —"
            )
            machine.date_modernization_power_change_expected = None
        if machine.date_modernization_no_power_change_expected is not None:
            changes.append(
                f"Ожидаемый год модернизации без изменения мощности: {machine.date_modernization_no_power_change_expected} → —"
            )
            machine.date_modernization_no_power_change_expected = None

    elif selected_kind == "modern":
        if machine.date_modernization_power_change_expected != selected_year:
            changes.append(
                f"Ожидаемый год модернизации с изменением мощности: {machine.date_modernization_power_change_expected} → {selected_year}"
            )
            # Синее информационное сообщение при автоматическом расчёте года модернизации с изменением мощности
            flash(
                f"Ожидаемый год модернизации с изменением мощности автоматически определён: {selected_year}",
                "primary",
            )
            machine.date_modernization_power_change_expected = selected_year
        if machine.date_modernization_no_power_change_expected is not None:
            changes.append(
                f"Ожидаемый год модернизации без изменения мощности: {machine.date_modernization_no_power_change_expected} → —"
            )
            machine.date_modernization_no_power_change_expected = None
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


