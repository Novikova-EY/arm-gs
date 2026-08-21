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
    quick_fix_machine_details_related_seqs,
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
    parse_decimal_from_display,
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
from app.fuel.services.equipment_groups.equipment_group_rebind_services import (
    _get_machine_fuel_param,
    rebind_machine_to_equipment_group,
)
from app.generation.services.station_services.station_access_services import (
    can_fuel_user_add_machine_to_station,
    can_edit_decentralized_zone_machine_details,
)

_FUEL_MODULE_EDIT_ROLES = frozenset({"admin", "fuel-admin", "fuel-editor"})
_GENERATION_MODULE_EDIT_ROLES = frozenset({"admin", "generation-admin", "generation-editor"})
_DZ_MACHINE_MAIN_FIELDS = frozenset(
    {
        "machine_group",
        "machine_number",
        "machine_name",
        "note",
        "id_condition_type",
        "id_gen_company",
        "relabing_outcome",
    }
)

_MACHINE_FORM_FIELD_LABELS = {
    "machine_name": "Название агрегата",
    "machine_number": "Номер агрегата",
    "id_gen_company": "Организация-собственник",
    "id_condition_type": "Состояние агрегата",
    "id_energy_area": "Энергорайон агрегата",
    "id_machine_type": "Тип агрегата",
    "id_tes_machine_type": "Тип агрегата ТЭС",
    "id_equipment_group": "Тип группы оборудования",
    "id_fuel_equipment_group": "Группа оборудования",
    "thermal_power_gcalh": "Тепловая мощность, Гкал/час",
    "note": "Примечание",
    "external_code": "external_code",
    "fuel_so": "Топливо (по СО ЕЭС)",
    "p_ust": "Руст",
    "p_ogr": "Рогр",
    "p_rasp": "Ррасп",
    "year_name": "Название агрегата",
    "tes_type": "Тип ТЭС",
    "fuel_type": "Топливо",
    "date_exploitation": "Дата ввода в эксплуатацию",
    "date_exploitation_expected": "Ожидаемая дата ввода в эксплуатацию",
    "is_commissioning_q4": "Ввод 4 квартала",
    "date_commission_fact": "Фактическая дата ввода",
    "date_joining_expected": "Ожидаемая дата присоединения",
    "date_joining_fact": "Фактическая дата присоединения",
    "date_detatchment_fact": "Фактическая дата отсоединения",
    "date_decompressing_expected": "Ожидаемая дата вывода из эксплуатации",
    "date_decompressing_fact": "Фактическая дата вывода из эксплуатации",
    "date_modernization_power_change_expected": "Ожидаемая дата модернизации (изменение мощности)",
    "date_modernization_no_power_change_expected": "Ожидаемая дата модернизации (без изменения мощности)",
}

_VALIDATION_MESSAGE_RU = {
    "This field is required.": "Поле обязательно для заполнения.",
    "Not a valid integer value.": "Укажите целое число.",
    "Not a valid decimal value.": "Укажите число.",
    "Number must be at least 0.": "Число должно быть не меньше 0.",
    "Field cannot be longer than 80 characters.": "Слишком длинное значение (максимум 80 символов).",
    "Field cannot be longer than 1024 characters.": "Слишком длинное значение (максимум 1024 символов).",
}


def _localize_validation_message(message: str) -> str:
    text = str(message).strip()
    return _VALIDATION_MESSAGE_RU.get(text, text)


def _field_label_for_validation(form, field_key: str) -> str:
    normalized_key = str(field_key).split("-")[-1]
    if form is not None:
        field = getattr(form, normalized_key, None)
        label = getattr(getattr(field, "label", None), "text", None)
        if label:
            return str(label)
    return _MACHINE_FORM_FIELD_LABELS.get(normalized_key, normalized_key)


def _flatten_form_errors(errors, form=None):
    if not errors:
        return
    if isinstance(errors, dict):
        for key, value in errors.items():
            if isinstance(value, list):
                if not value:
                    continue
                if all(isinstance(item, str) for item in value):
                    yield key, value, form
                    continue
                nested_field = getattr(form, key, None) if form is not None else None
                for index, item in enumerate(value):
                    if not isinstance(item, dict):
                        continue
                    sub_form = None
                    if nested_field is not None and hasattr(nested_field, "entries"):
                        entries = nested_field.entries
                        if index < len(entries):
                            sub_form = entries[index]
                    yield from _flatten_form_errors(item, sub_form)
            elif isinstance(value, dict):
                yield from _flatten_form_errors(value, form)
    elif isinstance(errors, list):
        for item in errors:
            if isinstance(item, dict):
                yield from _flatten_form_errors(item, form)


def _collect_form_validation_messages(*forms) -> list[str]:
    messages: list[str] = []
    seen: set[str] = set()
    for form in forms:
        if form is None or not getattr(form, "errors", None):
            continue
        for field_key, errs, label_form in _flatten_form_errors(form.errors, form):
            label = _field_label_for_validation(label_form or form, field_key)
            for err in errs:
                text = f"{label}: {_localize_validation_message(err)}"
                if text in seen:
                    continue
                seen.add(text)
                messages.append(text)
    return messages


def _flash_form_validation_errors(*forms) -> None:
    messages = _collect_form_validation_messages(*forms)
    if not messages:
        flash("Ошибка в заполнении формы.", "danger")
        return
    for message in messages:
        flash(message, "danger")


def _machine_post_role_flags() -> dict[str, bool]:
    role_names = set(getattr(current_user, "role_names", []) or [])
    return {
        "can_edit_fuel": bool(role_names & _FUEL_MODULE_EDIT_ROLES),
        "can_edit_generation": bool(role_names & _GENERATION_MODULE_EDIT_ROLES),
    }


def _can_edit_machine_generation_fields(
    can_edit_generation: bool,
    can_edit_dz_machine: bool,
    *,
    was_new: bool = False,
    fuel_can_create_machine: bool = False,
) -> bool:
    if was_new and fuel_can_create_machine:
        return True
    return can_edit_generation or can_edit_dz_machine


def _can_edit_machine_main_field(
    field_name: str,
    *,
    can_edit_fuel: bool,
    can_edit_generation: bool,
    can_edit_dz_machine: bool,
    was_new: bool = False,
    fuel_can_create_machine: bool = False,
) -> bool:
    if field_name in ("id_tes_machine_type", "id_equipment_group"):
        return can_edit_fuel
    if field_name in _DZ_MACHINE_MAIN_FIELDS:
        return _can_edit_machine_generation_fields(
            can_edit_generation,
            can_edit_dz_machine,
            was_new=was_new,
            fuel_can_create_machine=fuel_can_create_machine,
        )
    if was_new and fuel_can_create_machine:
        return True
    return can_edit_generation


def _machine_external_code_conflict_id(machine, new_code: str) -> int | None:
    query = db.session.query(Machine.id).filter(
        Machine.external_code == new_code,
        Machine.id != machine.id,
    )
    version_id = getattr(machine, "database_version_id", None)
    if version_id is None:
        query = query.filter(Machine.database_version_id.is_(None))
    else:
        query = query.filter(Machine.database_version_id == version_id)
    return query.scalar()


def _station_is_tes_or_ges(station) -> bool:
    try:
        st_name = (station.station_type.name or "").strip().lower() if station.station_type else ""
    except Exception:
        st_name = ""
    return st_name in ("тэс", "гэс", "гаэс")


def _sync_main_machine_name_from_year_names(
    main_form,
    advanced_form,
    station,
    year_features,
    version_year_start,
    version_year_end,
) -> None:
    """Для ТЭС/ГЭС/ГАЭС: собрать обязательное поле machine_name из таблицы названий по годам."""
    if not _station_is_tes_or_ges(station):
        return

    entries = list(getattr(advanced_form.machine_names, "entries", []) or [])
    if not entries:
        return

    base_name = None
    for entry in entries:
        value = (entry.year_name.data or "").strip()
        if not value:
            continue
        year_num = entry.year.data
        label = year_features.get(year_num) if year_num is not None else None
        if label and "план" in str(label).strip().lower():
            continue
        base_name = value
        break

    if not base_name:
        for entry in entries:
            value = (entry.year_name.data or "").strip()
            if value:
                base_name = value
                break

    if not base_name:
        return

    plan_name = None
    for entry in entries:
        value = (entry.year_name.data or "").strip()
        if not value:
            continue
        year_num = entry.year.data
        label = year_features.get(year_num) if year_num is not None else None
        if not label or "план" not in str(label).strip().lower():
            continue
        if value.lower() == base_name.lower():
            continue
        plan_name = value
        break

    main_form.machine_name.data = f"{base_name} ({plan_name})" if plan_name else base_name


def _render_machine_details_form_response(
    *,
    main_form,
    advanced_form,
    pgu_machines_form,
    station,
    machine,
    start_year,
    end_year,
    rounding_digits,
    year_features,
    all_documents,
    fuel_can_create_machine,
    can_edit_dz_machine=False,
    pgu_machines=None,
):
    version_year_start, version_year_end = get_current_version_year_range_from_name()
    return render_template(
        "generation/stations/machine_details.html",
        start_year=start_year,
        end_year=end_year,
        rounding_digits=rounding_digits,
        main_form=main_form,
        advanced_form=advanced_form,
        pgu_machines_form=pgu_machines_form,
        pgu_machines=pgu_machines if pgu_machines is not None else [],
        station=station,
        machine=machine,
        year_features=year_features,
        version_year_start=version_year_start,
        version_year_end=version_year_end,
        all_documents=all_documents,
        machine_logs=[],
        can_create_machine=fuel_can_create_machine,
        can_edit_dz_machine=can_edit_dz_machine,
        can_save_machine_all_versions=False,
    )


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

    from app.common.services.database_version_filter import get_current_db_version_id
    from app.common.services.version_entity_resolve_services import (
        load_by_id_with_version,
    )

    current_version_id = get_current_db_version_id()

    station = load_by_id_with_version(
        Station,
        station_id,
        current_version_id,
        query_factory=lambda: Station.query.options(
            db.joinedload(Station.regional_district),
            db.joinedload(Station.regional_energy_system_obj),
        ).filter_by(id=station_id),
    )
    if not station:
        from flask import abort
        abort(404)
    perf_mark("station_load")

    # Проверяем, создается ли новый агрегат
    if machine_id == 0:
        machine = None
    else:
        machine = load_by_id_with_version(
            Machine,
            machine_id,
            current_version_id,
            query_factory=lambda: Machine.query.options(
                db.joinedload(Machine.condition_type),
                db.joinedload(Machine.gen_company),
                db.joinedload(Machine.machine_type),
                db.joinedload(Machine.tes_machine_type),
                db.joinedload(Machine.equipment_group),
                db.joinedload(Machine.machine_fuel_param).joinedload(
                    MachineFuelParam.equipment_group
                ),
            ).filter_by(id=machine_id),
        )
        if not machine:
            from flask import abort
            abort(404)
        if machine.id_station != station.id:
            station = load_by_id_with_version(
                Station,
                machine.id_station,
                current_version_id,
                query_factory=lambda: Station.query.options(
                    db.joinedload(Station.regional_district)
                ).filter_by(id=machine.id_station),
            )
            if not station:
                from flask import abort
                abort(404)
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
        "version_year_start": version_year_start,
        "version_year_end": version_year_end,
        "all_documents": all_documents,
        "can_create_machine": (
            machine is None
            and can_fuel_user_add_machine_to_station(current_user, station)
        ),
        "can_edit_dz_machine": (
            machine is not None
            and can_edit_decentralized_zone_machine_details(current_user, station)
        ),
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


def _persist_target_version_id(machine) -> int | None:
    """Версия БД, в которую сохраняется агрегат (для разрешения FK)."""
    from flask import g

    from app.common.services.database_version_filter import get_current_db_version_id

    version_id = getattr(g, "current_db_version", None)
    if version_id is None:
        version_id = getattr(machine, "database_version_id", None) or get_current_db_version_id()
    return version_id


def _resolve_fk_for_machine_persist(model_cls, anchor_id, version_id):
    """
    Сопоставляет id справочника с целевой версией БД.
    Возвращает (resolved_id, ok). ok=False — поле не менять (нет соответствия в версии).
    """
    if anchor_id in (None, 0, ""):
        return None, True
    from app.common.services.version_entity_resolve_services import (
        resolve_entity_id_by_external_code_for_version,
        resolve_gen_company_id_for_version,
        resolve_refdata_fk_id_for_version,
    )

    anchor_int = int(anchor_id)
    if model_cls is EquipmentGroup:
        from app.common.services.version_entity_resolve_services import (
            resolve_fuel_equipment_group_id_for_version,
        )

        resolved = resolve_fuel_equipment_group_id_for_version(anchor_int, version_id)
        if resolved is not None:
            return resolved, True
        src = db.session.get(model_cls, anchor_int)
        if src and getattr(src, "database_version_id", None) == version_id:
            return anchor_int, True
        return None, False
    if model_cls is GenCompany:
        resolved = resolve_gen_company_id_for_version(anchor_int, version_id)
    else:
        resolved = resolve_refdata_fk_id_for_version(model_cls, anchor_int, version_id)
        if resolved is None:
            resolved = resolve_entity_id_by_external_code_for_version(
                model_cls, anchor_int, version_id
            )

    if resolved is not None:
        return resolved, True
    src = db.session.get(model_cls, anchor_int)
    if src and getattr(src, "database_version_id", None) == version_id:
        return anchor_int, True
    return None, False


def _station_type_name_lower(station) -> str:
    try:
        return (station.station_type.name or "").strip().lower() if station.station_type else ""
    except Exception:
        return ""


@no_autoflush
def persist_machine_details_all_versions_subset(
    station,
    machine,
    *,
    main_form,
    advanced_form,
    start_year: int,
    end_year: int,
    can_edit_fuel: bool,
) -> tuple[list, list]:
    """
    Сохранение machine_details во всех версиях БД: только «Группа оборудования»
    и «Тип группы оборудования».
    """
    changes: list[str] = []
    related_entities_changed = False

    equipment_groups = dict(
        choices_cache.get_choices(EquipmentGroupType, EquipmentGroupType.id)
    )

    if can_edit_fuel:
        old_v = machine.id_equipment_group
        new_v = main_form.id_equipment_group.data
        if choices_cache.is_empty_value(new_v):
            new_v = None
        elif new_v:
            version_id = _persist_target_version_id(machine)
            resolved, ok = _resolve_fk_for_machine_persist(
                EquipmentGroupType, new_v, version_id
            )
            if not ok:
                new_v = old_v
            else:
                new_v = resolved

        old_v_str = _equipment_group_type_log_label(old_v, equipment_groups)
        new_v_str = _equipment_group_type_log_label(new_v, equipment_groups)
        if old_v_str != new_v_str:
            changes.append(f"id_equipment_group: {old_v_str} → {new_v_str}")
            machine.id_equipment_group = new_v
        elif old_v != new_v:
            machine.id_equipment_group = new_v

    version_id = getattr(machine, "database_version_id", None) or get_current_db_version_id()
    type_before_fuel = machine.id_equipment_group

    old_fuel_eg_id = None
    if machine.id:
        mfp_before = _get_machine_fuel_param_for_version(machine.id, version_id)
        if mfp_before:
            old_fuel_eg_id = mfp_before.equipment_group_id

    _apply_fuel_equipment_group_from_form(
        machine,
        station,
        main_form,
        can_edit_fuel=can_edit_fuel,
        version_id=version_id,
    )

    if machine.id_equipment_group != type_before_fuel:
        changes.append(
            "id_equipment_group: "
            f"{_equipment_group_type_log_label(type_before_fuel, equipment_groups)}"
            " → "
            f"{_equipment_group_type_log_label(machine.id_equipment_group, equipment_groups)}"
        )
        related_entities_changed = True

    mfp_after = _get_machine_fuel_param_for_version(machine.id, version_id)
    new_fuel_eg_id = mfp_after.equipment_group_id if mfp_after else None
    if old_fuel_eg_id != new_fuel_eg_id:
        def _eg_label(eg_id):
            if not eg_id:
                return "—"
            eg = EquipmentGroup.query.get(eg_id)
            return (eg.name if eg else None) or f"id={eg_id}"

        changes.append(
            "Группа оборудования (топливный модуль): "
            f"{_eg_label(old_fuel_eg_id)} → {_eg_label(new_fuel_eg_id)}"
        )
        related_entities_changed = True

    if related_entities_changed or changes:
        from sqlalchemy.sql import func

        machine.updated_at = func.now()
        flag_modified(machine, "updated_at")

    return changes, []


# Ожидаемые годы, которые автозаполнение на карточке видит только в пределах
# отображаемого диапазона start_year..end_year. Пустое значение из формы при
# сохранении не должно затирать год вне этого диапазона.
_YEAR_FIELDS_PROTECTED_OUTSIDE_DISPLAY_RANGE = frozenset({
    "date_exploitation_expected",
    "date_decompressing_expected",
    "date_modernization_power_change_expected",
    "date_modernization_no_power_change_expected",
})


def _should_keep_year_outside_display_range(
    *,
    field_name: str,
    new_val,
    old_val,
    start_year: int,
    end_year: int,
    is_new: bool,
) -> bool:
    """True → не применять new_val=None, сохранить old_val."""
    if is_new or new_val is not None:
        return False
    if field_name not in _YEAR_FIELDS_PROTECTED_OUTSIDE_DISPLAY_RANGE:
        return False
    if old_val is None:
        return False
    try:
        old_year = int(old_val)
    except (TypeError, ValueError):
        return False
    return old_year < start_year or old_year > end_year


@no_autoflush
def persist_machine_details_from_validated_forms(
    station,
    machine,
    *,
    main_form,
    advanced_form,
    pgu_machines_form,
    normalized,
    user,
    start_year: int,
    end_year: int,
    can_edit_fuel: bool,
    can_edit_generation: bool,
    can_edit_dz_machine: bool = False,
    is_pgu_action: bool,
    year_features,
    skip_pgu: bool = False,
    was_new: bool = False,
    fuel_can_create_machine: bool = False,
) -> tuple[list, list]:
    """Apply validated machine_details forms to one machine (no commit)."""
    from sqlalchemy.orm.attributes import flag_modified
    is_new = was_new
    station_id = station.id
    machine_id = machine.id
    changes, pgu_changes = [], []
    pgu_machine = None
    # Определяем тип электростанции для логики обработки названий
    try:
        st_name = (station.station_type.name or '').strip().lower() if station.station_type else ''
    except Exception:
        st_name = ''
    is_tes_or_ges = st_name in ('тэс', 'гэс', 'гаэс')
    can_edit_generation_fields = _can_edit_machine_generation_fields(
        can_edit_generation,
        can_edit_dz_machine,
        was_new=was_new,
        fuel_can_create_machine=fuel_can_create_machine,
    )

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
        "id_equipment_group": lambda x: _equipment_group_type_log_label(x, equipment_groups),
        "machine_number": lambda x: (str(x).strip() if x is not None and str(x).strip() != "" else "не указано"),
        "machine_name": str,
        "note": lambda x: x or "не указано",
        "change_document": lambda x: x or "не указано",
        "relabing_outcome": lambda x: x or "не указано",
        "machine_group": str,
    }

    if current_user.is_authenticated and getattr(current_user, "is_admin", False):
        old_code = (getattr(machine, "external_code", None) or "").strip()
        new_code = (main_form.external_code.data or "").strip()
        if not new_code:
            if not was_new:
                raise ValueError("external_code не может быть пустым.")
        elif old_code != new_code:
            conflict_id = _machine_external_code_conflict_id(machine, new_code)
            if conflict_id is not None:
                raise ValueError(
                    f"Код {new_code!r} уже используется агрегатом id={conflict_id} "
                    f"в версии БД {getattr(machine, 'database_version_id', None)}"
                )
            changes.append(f"external_code: {old_code or 'не указано'} → {new_code}")
            machine.external_code = new_code

    # Список полей, которые являются внешними ключами и должны конвертировать 0 в None
    fk_fields = {
        'id_condition_type',
        'id_gen_company',
        'id_machine_type',
        'id_tes_machine_type',
        'id_equipment_group',
    }
    
    for fld, to_str in field_map.items():
        if not _can_edit_machine_main_field(
            fld,
            can_edit_fuel=can_edit_fuel,
            can_edit_generation=can_edit_generation,
            can_edit_dz_machine=can_edit_dz_machine,
            was_new=was_new,
            fuel_can_create_machine=fuel_can_create_machine,
        ):
            continue
        old_v = getattr(machine, fld) if not is_new else None
        if is_tes_or_ges and fld == "machine_name":
            # Для ТЭС/ГЭС/ГАЭС название агрегата формируется из machine_names
            # и не должно обновлять Machine.machine_name из формы.
            continue

        new_v = getattr(main_form, fld).data

        # Пустой номер агрегата — валидное значение при редактировании (храним "").
        if fld == "machine_number":
            if new_v is None or (isinstance(new_v, str) and new_v.strip() == ""):
                new_v = ""
            else:
                new_v = str(new_v).strip()

        # Конвертируем 0 в None для полей внешних ключей
        if fld in fk_fields and choices_cache.is_empty_value(new_v):
            new_v = None

        if fld in fk_fields and new_v:
            version_id = _persist_target_version_id(machine)
            fk_models = {
                "id_condition_type": ConditionType,
                "id_gen_company": GenCompany,
                "id_machine_type": MachineType,
                "id_tes_machine_type": TesMachineType,
                "id_equipment_group": EquipmentGroupType,
            }
            resolved, ok = _resolve_fk_for_machine_persist(
                fk_models[fld], new_v, version_id
            )
            if not ok:
                from flask import flash

                flash(
                    f"{_MACHINE_FORM_FIELD_LABELS.get(fld, fld)}: выбранное значение "
                    f"недоступно в текущей версии БД и не было сохранено.",
                    "warning",
                )
                continue
            new_v = resolved

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

    if can_edit_generation_fields:
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
                if _should_keep_year_outside_display_range(
                    field_name=fld,
                    new_val=new_val,
                    old_val=old_val,
                    start_year=start_year,
                    end_year=end_year,
                    is_new=is_new,
                ):
                    continue
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

        # Ввод 4 квартала — только при заполненном ожидаемом годе ввода
        has_expected_year = bool(getattr(machine, "date_exploitation_expected", None))
        new_q4 = bool(main_form.is_commissioning_q4.data) if has_expected_year else False
        old_q4 = bool(getattr(machine, "is_commissioning_q4", False)) if not is_new else False
        if is_new:
            if new_q4:
                changes.append("Ввод 4 квартала: да")
            setattr(machine, "is_commissioning_q4", new_q4)
        elif old_q4 != new_q4:
            changes.append(
                f"Ввод 4 квартала: {'да' if old_q4 else 'нет'} → {'да' if new_q4 else 'нет'}"
            )
            setattr(machine, "is_commissioning_q4", new_q4)

    # Для нового агрегата нужно flush, чтобы получить machine.id
    if is_new:
        db.session.flush()

    # При изменении типа группы оборудования или планового года ввода
    # синхронизируем конкретную fuel-группу агрегата (обычная / "(нов)").
    version_id = getattr(machine, "database_version_id", None) or get_current_db_version_id()
    type_before_fuel = machine.id_equipment_group

    old_fuel_eg_id = None
    if machine.id:
        mfp_before = _get_machine_fuel_param_for_version(machine.id, version_id)
        if mfp_before:
            old_fuel_eg_id = mfp_before.equipment_group_id

    if can_edit_fuel and st_name == "тэс":
        _apply_fuel_equipment_group_from_form(
            machine,
            station,
            main_form,
            can_edit_fuel=True,
            version_id=version_id,
        )
    else:
        sync_machine_fuel_equipment_group(
            machine,
            version_id=version_id,
        )

    if machine.id_equipment_group != type_before_fuel:
        changes.append(
            "id_equipment_group: "
            f"{_equipment_group_type_log_label(type_before_fuel, equipment_groups)}"
            " → "
            f"{_equipment_group_type_log_label(machine.id_equipment_group, equipment_groups)}"
        )

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

    # Определяем тип электростанции и "текущий год" версии БД
    try:
        st_name = (station.station_type.name or '').strip().lower() if station.station_type else ''
    except Exception:
        st_name = ''
    is_tes_or_ges = st_name in ('тэс', 'гэс', 'гаэс')
    version_year_start, version_year_end = get_current_version_year_range_from_name()
    current_year_for_version = version_year_end
    # Последнее ненулевое "эффективное" название для автозаполнения (как для мощностей)
    last_effective_name = None

    def _power_field_changed(raw_value, orig_value):
        if orig_value in (None, "", "—", "-"):
            return raw_value not in (None, "", "—", "-")
        return not is_same_decimal(to_decimal(raw_value), to_decimal(orig_value))

    any_power_changed = False
    if can_edit_generation_fields and not is_new:
        for i, year_num in enumerate(range(start_year, end_year + 1)):
            if i >= len(advanced_form.powers):
                break
            pf = advanced_form.powers[i]
            if (
                _power_field_changed(
                    normalized.get(pf.p_ust.name),
                    normalized.get(f"{pf.p_ust.name}_orig"),
                )
                or _power_field_changed(
                    normalized.get(pf.p_ogr.name),
                    normalized.get(f"{pf.p_ogr.name}_orig"),
                )
                or _power_field_changed(
                    normalized.get(pf.p_rasp.name),
                    normalized.get(f"{pf.p_rasp.name}_orig"),
                )
            ):
                any_power_changed = True
                break

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

        if can_edit_generation_fields:
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

            power_fields_changed = any_power_changed or (
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
            elif new_tt is not None:
                resolved_tt, ok = _resolve_fk_for_machine_persist(
                    TesType, new_tt, _persist_target_version_id(machine)
                )
                if not ok:
                    new_tt = mt.id_tes_type
                else:
                    new_tt = resolved_tt
                
        if i < len(advanced_form.fuels):
            new_fuel = advanced_form.fuels[i].fuel_type.data
            if choices_cache.is_empty_value(new_fuel):
                new_fuel = None
            elif new_fuel is not None:
                resolved_fuel, ok = _resolve_fk_for_machine_persist(
                    Fuel, new_fuel, _persist_target_version_id(machine)
                )
                if not ok:
                    new_fuel = mf.id_fuel
                else:
                    new_fuel = resolved_fuel

        # Обрабатываем типы ТЭС и топливо только для ТЭС станций
        # Распознаем тип электростанции по названию
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
        if can_edit_generation_fields and i < len(advanced_form.machine_names):
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
    if is_tes_or_ges and can_edit_generation_fields:
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

    if not skip_pgu and is_pgu_action and can_edit_generation and pgu_machines_form.id_pgu_machine.data:
        pgu_machine = PGUMachine.query.get(pgu_machines_form.id_pgu_machine.data)
        if pgu_machine:
            # Получаем кэшированные справочники для ПГУ
            condition_types = dict(choices_cache.get_choices(ConditionType, ConditionType.id))
            tes_machine_types = dict(choices_cache.get_choices(TesMachineType, TesMachineType.id))
            machines = dict(choices_cache.get_choices(Machine, Machine.machine_name, name_field='machine_name'))
            
            # Список полей внешних ключей ПГУ, которые должны конвертировать 0 в None
            pgu_fk_fields_inline = {'id_condition_type', 'id_tes_machine_type', 'id_parent_machine'}
            pgu_fk_models = {
                'id_condition_type': ConditionType,
                'id_tes_machine_type': TesMachineType,
                'id_parent_machine': Machine,
            }
            
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

                if fld in pgu_fk_models and new_val:
                    resolved, ok = _resolve_fk_for_machine_persist(
                        pgu_fk_models[fld], new_val, _persist_target_version_id(machine)
                    )
                    if not ok:
                        continue
                    new_val = resolved
                
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
        can_edit_generation=can_edit_generation_fields,
    )
    return changes, pgu_changes


@no_autoflush
def handle_machine_post(station_id, machine_id, form_data, user, start_year, end_year, rounding_digits):
    from werkzeug.datastructures import MultiDict

    normalized = MultiDict(form_data)
    # Поля, в которых запятая — десятичный разделитель (только числовые)
    _numeric_key_suffixes = ("p_ust", "p_ogr", "p_rasp", "thermal_power_gcalh")
    for key, value in list(normalized.items()):
        if isinstance(value, str):
            if value.strip() in {"\u2014", "-", ""}:
                normalized[key] = ""
            # Запятая/пробелы тысяч → каноническое число (format_decimal даёт «1 234,0»)
            elif _is_machine_power_numeric_form_key(key, _numeric_key_suffixes):
                normalized[key] = _canonical_numeric_form_value(value)

    station = get_station_by_id(station_id)

    _rpf = _machine_post_role_flags()
    can_edit_fuel = _rpf["can_edit_fuel"]
    can_edit_generation = _rpf["can_edit_generation"]
    fuel_can_create_machine = (
        machine_id == 0
        and can_fuel_user_add_machine_to_station(current_user, station)
    )
    can_edit_dz_machine = (
        machine_id != 0
        and can_edit_decentralized_zone_machine_details(current_user, station)
    )
    can_edit_generation_effective = (
        can_edit_generation or fuel_can_create_machine or can_edit_dz_machine
    )
    if not can_edit_fuel and not can_edit_generation_effective:
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

        # machine_number is Optional: do NOT restore previous value when the user
        # explicitly cleared the field (empty string). Only fill if the key is absent.
        if machine.machine_number:
            variants = {machine_number_field}
            if "-" in machine_number_field:
                variants.add(machine_number_field.replace("-", "_"))
            else:
                variants.add(machine_number_field.replace("_", "-"))
            if all(normalized.get(v) is None for v in variants):
                normalized[machine_number_field] = str(machine.machine_number)

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
    if pgu_ids_to_delete and not can_edit_generation_effective:
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
            log_to_db(user, f"Удаление ПГУ агрегатов на электростанции {station.name}", details="; ".join(deleted_names))
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

    version_year_start, version_year_end = get_current_version_year_range_from_name()
    _sync_main_machine_name_from_year_names(
        main_form,
        advanced_form,
        station,
        year_features,
        version_year_start,
        version_year_end,
    )

    main_valid = main_form.validate()
    adv_valid = advanced_form.validate()
    adv_valid = adv_valid and _validate_power_ranges(advanced_form, normalized)
    pgu_valid = pgu_machines_form.validate() if (is_pgu_action and can_edit_generation_effective) else True

    if not (main_valid and adv_valid and pgu_valid):
        print("main_form.errors:", main_form.errors)
        print("advanced_form.errors:", advanced_form.errors)
        print("pgu_machines_form.errors:", pgu_machines_form.errors)
        print(f"[DEBUG] Ошибка валидации: tes_types entries: {len(advanced_form.tes_types.entries)}")
        print(f"[DEBUG] Ошибка валидации: fuels entries: {len(advanced_form.fuels.entries)}")
        _flash_form_validation_errors(
            main_form,
            advanced_form,
            pgu_machines_form if is_pgu_action else None,
        )
        # Оптимизированная загрузка документов - только id и name с фильтрацией по версии
        all_documents = choices_cache.get_choices(Document, Document.name)
        # Преобразуем обратно в объекты для совместимости с шаблоном
        all_documents = [Document(id=doc_id, name=doc_name) for doc_id, doc_name in all_documents]
        _fill_fuel_equipment_group_choices(main_form, station.id, machine)
        return _render_machine_details_form_response(
            main_form=main_form,
            advanced_form=advanced_form,
            pgu_machines_form=pgu_machines_form,
            station=station,
            machine=machine,
            start_year=start_year,
            end_year=end_year,
            rounding_digits=rounding_digits,
            year_features=year_features,
            all_documents=all_documents,
            fuel_can_create_machine=fuel_can_create_machine,
            can_edit_dz_machine=can_edit_dz_machine,
        )

    try:
        quick_fix_machine_details_related_seqs()

        if is_new and not can_edit_generation_effective:
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
            machine_number = main_form.machine_number.data or ""
            machine_name = main_form.machine_name.data or "Без названия"
            machine = Machine(
                id_station=station_id,
                machine_number=machine_number,
                machine_name=machine_name,
            )
            set_db_version_on_create(machine)
            db.session.add(machine)
            db.session.flush()

        if request.values.get("all_versions") == "1" and is_new:
            flash("Сохранение во всех версиях недоступно для нового агрегата.", "warning")
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

        if request.values.get("all_versions") == "1" and not is_new:
            from app.refdata.routes.refdata_all_versions_guard import (
                block_all_versions_without_admin,
            )
            from app.generation.services.machine_services.machine_details_all_versions_services import (
                save_machine_details_across_versions,
            )

            if block_all_versions_without_admin(current_user):
                return redirect(
                    url_for(
                        "station_bp.machine_details",
                        station_id=station.id,
                        machine_id=machine.id,
                        **redirect_args,
                    )
                )
            if request.values.get("all_versions_confirm") != "1":
                flash(
                    "Сохранение во всех версиях БД отменено: не пройдено подтверждение.",
                    "warning",
                )
                log_to_db(
                    user,
                    "Отклонено сохранение machine_details во всех версиях БД: "
                    "отсутствует подтверждение all_versions_confirm",
                    entity_type="machine",
                    entity_id=machine.id,
                )
                return redirect(
                    url_for(
                        "station_bp.machine_details",
                        station_id=station.id,
                        machine_id=machine.id,
                        **redirect_args,
                    )
                )
            return save_machine_details_across_versions(
                user=user,
                anchor_station_id=station.id,
                anchor_machine_id=machine.id,
                main_form=main_form,
                advanced_form=advanced_form,
                pgu_machines_form=pgu_machines_form,
                normalized=normalized,
                start_year=start_year,
                end_year=end_year,
                redirect_args=redirect_args,
                can_edit_fuel=can_edit_fuel,
                can_edit_generation=can_edit_generation_effective,
                is_pgu_action=is_pgu_action,
                year_features=year_features,
                anchor_station=station,
                anchor_machine=machine,
            )

        changes, pgu_changes = persist_machine_details_from_validated_forms(
            station,
            machine,
            main_form=main_form,
            advanced_form=advanced_form,
            pgu_machines_form=pgu_machines_form,
            normalized=normalized,
            user=user,
            start_year=start_year,
            end_year=end_year,
            can_edit_fuel=can_edit_fuel,
            can_edit_generation=can_edit_generation,
            can_edit_dz_machine=can_edit_dz_machine,
            is_pgu_action=is_pgu_action,
            year_features=year_features,
            was_new=is_new,
            fuel_can_create_machine=fuel_can_create_machine,
        )

        if can_edit_generation or can_edit_dz_machine or fuel_can_create_machine:
            recalculate_machine_years_by_p_ust(machine, changes, year_features)

        _commit_with_retry()
        clear_station_aggregation_cache("after machine save")

        from app.common.services.cache_decorator import (
            invalidate_cache,
            invalidate_cache_pattern,
        )

        if changes or pgu_changes:
            invalidate_cache("machine", machine_id=machine.id)
            invalidate_cache("station_full", station_id=station.id)
            invalidate_cache_pattern("station_list:*")
            clear_machine_choices_cache()

        if pgu_changes:
            log_to_db(
                user,
                f"Изменения по ПГУ агрегату {pgu_machines_form.machine_name.data or 'ПГУ'} "
                f"электростанции {station.name}",
                details="; ".join(pgu_changes),
            )
            flash("Данные ПГУ агрегата успешно обновлены!", "success")

        if changes:
            if is_new:
                log_to_db(
                    user,
                    f"Создан новый агрегат на электростанции {station.name} "
                    f"({station.regional_district.name})",
                    details="; ".join(changes),
                    entity_type="machine",
                    entity_id=machine.id,
                )
                flash("Новый агрегат успешно создан!", "success")
            else:
                log_to_db(
                    user,
                    f"Изменения в электростанции {station.name} "
                    f"({station.regional_district.name}), агрегат №{machine.machine_number}",
                    details="; ".join(changes),
                    entity_type="machine",
                    entity_id=machine.id,
                )
                flash("Данные агрегата успешно обновлены!", "success")

        if not changes and not pgu_changes and not is_new:
            flash("Изменений не обнаружено", "info")

        return redirect(
            url_for(
                "station_bp.machine_details",
                station_id=station.id,
                machine_id=machine.id,
                **redirect_args,
            )
        )

    except Exception as exc:
        db.session.rollback()
        traceback.print_exc()
        flash(f"Ошибка при обновлении данных: {exc}", "danger")
        if is_new:
            log_to_db(user, f"Ошибка создания нового агрегата на электростанции {station.name}", details=str(exc))
            # Для нового агрегата при ошибке устанавливаем machine=None
            machine = None
        else:
            machine_info = f"№{machine.machine_number} {machine.machine_name}" if machine else "неизвестный агрегат"
            log_to_db(user, f"Ошибка обновления агрегата {machine_info} электростанции {station.name}", details=str(exc), entity_type="machine", entity_id=machine.id if machine else None)
        print(f"[DEBUG] Ошибка в handle_machine_post: tes_types entries: {len(advanced_form.tes_types.entries)}")
        print(f"[DEBUG] Ошибка в handle_machine_post: fuels entries: {len(advanced_form.fuels.entries)}")
        # Оптимизированная загрузка документов - только id и name с фильтрацией по версии
        all_documents = choices_cache.get_choices(Document, Document.name)
        # Преобразуем обратно в объекты для совместимости с шаблоном
        all_documents = [Document(id=doc_id, name=doc_name) for doc_id, doc_name in all_documents]
        _fill_fuel_equipment_group_choices(main_form, station.id, machine)
        return _render_machine_details_form_response(
            main_form=main_form,
            advanced_form=advanced_form,
            pgu_machines_form=pgu_machines_form,
            station=station,
            machine=machine,
            start_year=start_year,
            end_year=end_year,
            rounding_digits=rounding_digits,
            year_features=year_features,
            all_documents=all_documents,
            fuel_can_create_machine=fuel_can_create_machine,
            can_edit_dz_machine=can_edit_dz_machine,
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
            if '-p_ust' in key or key.endswith('p_ust') or key.endswith('p_ust_orig'):
                if isinstance(value, str):
                    value = _canonical_numeric_form_value(value)
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
        _flash_form_validation_errors(pgu_form)
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

                if (
                    not is_new
                    and _should_keep_year_outside_display_range(
                        field_name=fld,
                        new_val=new_val,
                        old_val=old_val,
                        start_year=start_year,
                        end_year=end_year,
                        is_new=is_new,
                    )
                ):
                    continue

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

            # Обновляем только годы в отображаемом диапазоне; мощности вне
            # start_year..end_year сохраняем (иначе сужение диапазона уничтожает данные).
            PGUMachinePower.query.filter(
                PGUMachinePower.id_pgu_machine == pgu_machine.id,
                PGUMachinePower.year_number >= start_year,
                PGUMachinePower.year_number <= end_year,
            ).delete(synchronize_session=False)

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
                f"Добавлен ПГУ агрегат '{pgu_form.machine_name.data}' на электростанции {station.name}", 
                details="; ".join(changes) if changes else f"ID: {pgu_machine.id}",
                entity_type="pgu_machine",
                entity_id=pgu_machine.id,
            )
            flash(f"Агрегат ПГУ успешно добавлен!", "success")
        else:
            if changes:
                log_to_db(
                    user, 
                    f"Изменения на электростанции {station.name} в агрегате ПГУ '{pgu_machine.machine_name}' (UID: {pgu_machine.id}) ", 
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
        log_to_db(user, f"Ошибка при сохранении ПГУ агрегата на электростанции {station.name}", details=str(e))
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
    return _get_machine_fuel_param(machine_id, version_id)


def _equipment_group_type_log_label(val, equipment_groups: dict) -> str:
    if not val:
        return "не указано"
    return equipment_groups.get(val) or f"id={val}"


def _apply_fuel_equipment_group_from_form(
    machine,
    station,
    main_form,
    *,
    can_edit_fuel: bool,
    version_id: int | None,
) -> None:
    """
    Явный выбор группы на machine_details сохраняется как перенос привязки.
    Авто («по типу») — прежняя синхронизация с EquipmentGroupSet по типу.
    """
    explicit_id = None
    if can_edit_fuel:
        raw_fuel_eg = main_form.id_fuel_equipment_group.data
        if not choices_cache.is_empty_value(raw_fuel_eg):
            persist_version_id = _persist_target_version_id(machine)
            resolved_eg, ok = _resolve_fk_for_machine_persist(
                EquipmentGroup, raw_fuel_eg, persist_version_id
            )
            if ok and resolved_eg is not None:
                allowed_ids = {
                    gid
                    for gid, _ in get_station_fuel_equipment_group_choice_tuples(
                        station.id, persist_version_id
                    )
                }
                if resolved_eg in allowed_ids:
                    explicit_id = resolved_eg
                    version_id = persist_version_id

    if explicit_id is not None:
        rebind_machine_to_equipment_group(
            machine=machine,
            target_group_id=explicit_id,
            version_id=version_id,
        )
        return

    sync_machine_fuel_equipment_group(machine, version_id=version_id)


def _fill_fuel_equipment_group_choices(main_form, station_id: int, machine=None):
    """Список итоговых групп оборудования электростанции (топливный модуль) + авто-привязка."""
    version_id = get_current_db_version_id()
    tuples = get_station_fuel_equipment_group_choice_tuples(station_id, version_id)
    auto_label = "— по типу группы и плановому году (авто)"
    main_form.id_fuel_equipment_group.choices = [
        (choices_cache.EMPTY_VALUE_ID, auto_label)
    ] + tuples

    if choices_cache.is_empty_value(main_form.id_fuel_equipment_group.data):
        mfp = None
        if machine and getattr(machine, "id", None):
            mfp = getattr(machine, "machine_fuel_param", None)
            if mfp is None:
                mfp = _get_machine_fuel_param(machine.id, version_id)
        allowed_ids = {c[0] for c in tuples}
        if mfp and mfp.equipment_group_id and mfp.equipment_group_id in allowed_ids:
            main_form.id_fuel_equipment_group.data = mfp.equipment_group_id
        else:
            main_form.id_fuel_equipment_group.data = choices_cache.EMPTY_VALUE_ID

    sel = main_form.id_fuel_equipment_group.data
    if sel and not choices_cache.is_empty_value(sel):
        ids = {c[0] for c in main_form.id_fuel_equipment_group.choices}
        if sel not in ids:
            # Группа не связана с этой станцией (и не в кластере составной) — не подставлять.
            main_form.id_fuel_equipment_group.data = choices_cache.EMPTY_VALUE_ID


def _fill_main_form_choices(form):
    """Заполняет choices для основной формы с использованием унифицированного кэширования"""
    # Добавляем дефолтное значение "не указано", чтобы оно отображалось в select
    # и могло выступать "пустым" значением до обязательного выбора пользователем.
    form.id_gen_company.choices = choices_cache.get_choices_with_default(GenCompany, GenCompany.id)
    form.id_energy_area.choices = choices_cache.get_choices_with_default(EnergyArea, EnergyArea.id)
    form.id_machine_type.choices = choices_cache.get_choices(MachineType, MachineType.id)
    form.id_tes_machine_type.choices = choices_cache.get_choices(TesMachineType, TesMachineType.id)
    form.id_equipment_group.choices = choices_cache.get_choices_with_default(EquipmentGroupType, EquipmentGroupType.id)
    
    form.id_condition_type.choices = choices_cache.get_choices(ConditionType, ConditionType.id)
    if form.id_condition_type.data is None:
        form.id_condition_type.data = choices_cache.EMPTY_VALUE_ID
    if form.id_equipment_group.data is None:
        form.id_equipment_group.data = choices_cache.EMPTY_VALUE_ID
    if form.id_energy_area.data is None:
        form.id_energy_area.data = choices_cache.EMPTY_VALUE_ID


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


def _is_machine_power_numeric_form_key(key: str, suffixes: tuple[str, ...]) -> bool:
    base = key[:-5] if key.endswith("_orig") else key
    return base.endswith(suffixes)


def _canonical_numeric_form_value(value: str) -> str:
    """Строка для DecimalField: без пробелов тысяч, точка как разделитель."""
    try:
        parsed = parse_decimal_from_display(value)
    except (InvalidOperation, TypeError, ValueError):
        return value
    if parsed is None:
        return ""
    return format(parsed, "f")


def to_decimal(val):
    try:
        return parse_decimal_from_display(val)
    except (InvalidOperation, TypeError, ValueError):
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
        p_ust_d = _coerce_decimal(p_ust)
        p_ogr_d = _coerce_decimal(p_ogr)
        p_rasp_d = _coerce_decimal(p_rasp)

        if p_ust_d is not None and p_ust_d > 0:
            if not is_empty(p_rasp_d) and is_empty(p_ogr_d) and not skip_ogr:
                calculated = p_ust_d - p_rasp_d
                if rounded_decimal(p_ogr_d, 6) != rounded_decimal(calculated, 6):
                    if year_num is not None:
                        flash(f"🧠 {year_num} год: автозаполнено Рогр = {calculated} (из Руст − Ррасп)", "info")
                    return p_ust_d, calculated, p_rasp_d
            elif not is_empty(p_ogr_d) and is_empty(p_rasp_d) and not skip_rasp:
                calculated = p_ust_d - p_ogr_d
                if rounded_decimal(p_rasp_d, 6) != rounded_decimal(calculated, 6):
                    if year_num is not None:
                        flash(f"🧠 {year_num} год: автозаполнено Ррасп = {calculated} (из Руст − Рогр)", "info")
                    return p_ust_d, p_ogr_d, calculated
            elif is_empty(p_ogr_d) and is_empty(p_rasp_d) and not skip_ogr and not skip_rasp:
                if year_num is not None:
                    flash(f"🧠 {year_num} год: автозаполнено Ррасп = 0 и Рогр = {p_ust_d}", "info")
                return p_ust_d, p_ust_d, Decimal(0)
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

    def _entry_index(year_num: int) -> int:
        return year_num - start_year

    def _user_set_tes_in_form(year_num: int) -> bool:
        idx = _entry_index(year_num)
        entries = getattr(advanced_form.tes_types, "entries", None) or []
        if idx < 0 or idx >= len(entries):
            return False
        val = entries[idx].tes_type.data
        return not is_empty_choice(val, tes_default_id)

    def _user_set_fuel_in_form(year_num: int) -> bool:
        idx = _entry_index(year_num)
        entries = getattr(advanced_form.fuels, "entries", None) or []
        if idx < 0 or idx >= len(entries):
            return False
        val = entries[idx].fuel_type.data
        return not is_empty_choice(val, fuel_default_id)

    def _user_set_name_in_form(year_num: int) -> bool:
        idx = _entry_index(year_num)
        entries = getattr(advanced_form.machine_names, "entries", None) or []
        if idx < 0 or idx >= len(entries):
            return False
        return bool((entries[idx].year_name.data or "").strip())

    def _effective_powers_for_year(year_num: int, mp):
        """Мощности для autofill: сначала из формы (продлённые на фронте), затем из БД."""
        idx = _entry_index(year_num)
        entries = getattr(advanced_form.powers, "entries", None) or []
        if 0 <= idx < len(entries):
            entry = entries[idx]
            p_ust = to_decimal(entry.p_ust.data)
            p_ogr = to_decimal(entry.p_ogr.data)
            p_rasp = to_decimal(entry.p_rasp.data)
            return (
                p_ust if p_ust is not None else (mp.p_ust or Decimal(0)),
                p_ogr if p_ogr is not None else (mp.p_ogr or Decimal(0)),
                p_rasp if p_rasp is not None else (mp.p_rasp or Decimal(0)),
            )
        return mp.p_ust or Decimal(0), mp.p_ogr or Decimal(0), mp.p_rasp or Decimal(0)

    for i, year_num in enumerate(range(start_year, end_year + 1)):
        if year_num not in powers_map or year_num not in tes_map or year_num not in fuel_map:
            continue

        mp = powers_map[year_num]
        mt = tes_map[year_num]
        mf = fuel_map[year_num]
        mn = names_map.get(year_num)

        p_ust, p_ogr, p_rasp = _effective_powers_for_year(year_num, mp)

        if is_empty(p_ust) and is_empty(p_ogr) and is_empty(p_rasp):
            if can_edit_fuel:
                if not _user_set_tes_in_form(year_num):
                    tes_empty = is_empty_choice(mt.id_tes_type, tes_default_id)
                    if not tes_empty:
                        new_tes_type = tes_default_id
                        if mt.id_tes_type != new_tes_type:
                            old_tes_name = tes_names.get(mt.id_tes_type, f"[{mt.id_tes_type}]")
                            changes.append(f"Тип ТЭС: {year_num} год - {old_tes_name} → не указано")
                            mt.id_tes_type = new_tes_type
                            flash(f"🧠 {year_num} год: Тип ТЭС установлен: 'не указано' (все мощности = 0)", "info")

                if not _user_set_fuel_in_form(year_num):
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
            if (
                can_edit_generation
                and not _user_set_name_in_form(year_num)
                and mn is not None
                and (mn.name or "").strip()
            ):
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
        if getattr(machine, "is_commissioning_q4", False):
            changes.append("Ввод 4 квартала: да → нет")
            machine.is_commissioning_q4 = False
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
        if getattr(machine, "is_commissioning_q4", False):
            changes.append("Ввод 4 квартала: да → нет")
            machine.is_commissioning_q4 = False

    else:
        # Ничего не выбрано — не трогаем текущие значения.
        # Ранее тут было предупреждение про модернизацию; теперь оно не нужно,
        # чтобы не мешать логике взаимоисключаемости.
        pass


