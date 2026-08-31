import uuid

from config import Config
from app.extensions import db
from collections import defaultdict
from sqlalchemy import or_, extract, and_, func, select
from sqlalchemy.sql import exists
from sqlalchemy.orm import contains_eager, joinedload, selectinload

from app.common.services.database_version_filter import (
    filter_by_db_version,
    get_current_db_version_id,
)

from app.generation.models.station.station_model import Station
from app.generation.models.station.station_constants import STATION_SIGN_FILTER_UNSPECIFIED
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.machine.machine_fuel_model import MachineFuel
from app.generation.models.machine.machine_tes_type_model import MachineTesType
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.refdata.models.fuels.fuel_model import Fuel
from app.refdata.models.fuels.fuel_type_model import FuelType
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.gen_companies.gen_company_model import GenCompany
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.refdata_for_stations.machine.tes_type_model import TesType
from app.refdata.models.refdata_for_stations.machine.tes_machine_type_model import TesMachineType
from app.refdata.models.refdata_for_stations.condition_type_model import ConditionType
from app.refdata.models.refdata_for_stations.machine.pgu_tes_machine_type_model import (
    PGUTesMachineType,
)
from app.common.services.get_services.years.years_get_services import (
    get_current_year,
    get_filter_start_year,
    get_filter_end_year,
)

def build_machine_note_search_condition(machine_cls, pgu_cls, note_filter_value):
    """
    Примечание агрегата (Machine) или вложенного ПГУ содержит подстроку (без учёта регистра).
    Не включает примечание самой электростанции — только машины и ПГУ.
    """
    raw = (note_filter_value or "").strip()
    if not raw:
        return None
    note_pattern = f"%{raw}%"
    return or_(
        machine_cls.note.ilike(note_pattern),
        machine_cls.pgu_submachines.any(pgu_cls.note.ilike(note_pattern)),
    )


def _parse_year_filter(raw_list):
    """
    Парсит список значений фильтра по году. '' -> None (не указано), '2020' -> 2020.
    Возвращает None если список пуст.
    """
    if not raw_list:
        return None
    result = []
    for v in raw_list:
        s = str(v).strip() if v is not None else ""
        if s == "":
            result.append(None)
        else:
            try:
                result.append(int(s))
            except (ValueError, TypeError):
                pass
    return result if result else None


def _parse_int_list_filter(raw_list):
    """
    Список целых из query/form: несколько параметров и ввод «1, 2; 3» в одном значении.
    Пустой список, если ничего разобрать нельзя.
    """
    if not raw_list:
        return []
    result = []
    seen = set()
    for item in raw_list:
        if item is None:
            continue
        text = str(item).replace(",", " ").replace(";", " ")
        for part in text.split():
            try:
                n = int(part)
            except (TypeError, ValueError):
                continue
            if n in seen:
                continue
            seen.add(n)
            result.append(n)
    return result


def _args_getlist_raw(args, key):
    """Список значений query/form; пустые строки отбрасываем."""
    if hasattr(args, "getlist"):
        return [x for x in args.getlist(key) if x is not None and str(x).strip() != ""]
    val = args.get(key, None) if hasattr(args, "get") else None
    if val is None or (isinstance(val, str) and val.strip() == ""):
        return []
    return [val]


def _normalize_uuid_strings(raw_values):
    out = []
    for raw in raw_values:
        s = str(raw).strip()
        if not s:
            continue
        try:
            uuid.UUID(s)
        except (ValueError, TypeError):
            continue
        out.append(s)
    return out


def _parse_int_ids(id_list):
    ids = []
    for x in id_list or []:
        try:
            if x is None:
                continue
            ids.append(int(x))
        except (TypeError, ValueError):
            continue
    return ids


def _norm_ref_key(value):
    if value is None:
        return ""
    return str(value).strip().lower().strip("{}")


def _norm_name_key(value):
    return " ".join(str(value or "").split()).strip().lower()


def _identity_row_from_raw(raw, has_name, has_version):
    rid = raw[0]
    ru = raw[1]
    idx = 2
    name = None
    if has_name:
        name = raw[idx]
        idx += 1
    ver = raw[idx] if has_version else None
    return {
        "id": rid,
        "ref_uuid": _norm_ref_key(ru),
        "ref_uuid_raw": ru,
        "name": _norm_name_key(name),
        "name_raw": name,
        "database_version_id": ver,
    }


def _load_territorial_identity_rows(
    model_cls,
    *,
    ids=None,
    ref_uuids=None,
    names=None,
    current_version_only=False,
):
    """Строки справочника с id/ref_uuid/name/версией для сопоставления фильтров."""
    has_name = hasattr(model_cls, "name")
    has_version = hasattr(model_cls, "database_version_id")
    cols = [model_cls.id, model_cls.ref_uuid]
    if has_name:
        cols.append(model_cls.name)
    if has_version:
        cols.append(model_cls.database_version_id)
    q = db.session.query(*cols)
    if ids is not None:
        q = q.filter(model_cls.id.in_(ids))
    if ref_uuids is not None:
        q = q.filter(model_cls.ref_uuid.in_(ref_uuids))
    if names is not None and has_name:
        lowered = [str(n).strip().lower() for n in names if n]
        if lowered:
            q = q.filter(func.lower(func.trim(model_cls.name)).in_(lowered))
        else:
            return []
    if current_version_only:
        q = filter_by_db_version(q, model_cls)
    return [
        _identity_row_from_raw(raw, has_name, has_version) for raw in q.all()
    ]


def _choose_current_version_id(src, current_rows, current_version_id):
    """
    id той же сущности в текущей версии БД.

    Если исходный id уже из текущей версии — его и оставляем: при битых
    дубликатах ref_uuid (Забайкальский край / Калининградская область)
    словарь last-wins подменял субъект.
    """
    src_ver = src.get("database_version_id")
    if current_version_id is not None and src_ver == current_version_id:
        return src["id"]
    if current_version_id is None and src_ver is None:
        return src["id"]

    uuid_hits = [
        row for row in current_rows
        if src["ref_uuid"] and row["ref_uuid"] == src["ref_uuid"]
    ]
    if len(uuid_hits) == 1:
        return uuid_hits[0]["id"]
    if len(uuid_hits) > 1:
        named = [row for row in uuid_hits if src["name"] and row["name"] == src["name"]]
        if named:
            return min(named, key=lambda row: row["id"])["id"]
        return src["id"]

    name_hits = [
        row for row in current_rows
        if src["name"] and row["name"] == src["name"]
    ]
    if len(name_hits) == 1:
        return name_hits[0]["id"]
    return src["id"]


def _expand_identity_ids(src, all_rows):
    """Все id той же сущности во всех версиях БД (ref_uuid, при коллизии — имя)."""
    matched = []
    if src["ref_uuid"]:
        uuid_hits = [row for row in all_rows if row["ref_uuid"] == src["ref_uuid"]]
        by_version = defaultdict(list)
        for row in uuid_hits:
            by_version[row["database_version_id"]].append(row)
        for mates in by_version.values():
            if len(mates) == 1:
                matched.extend(mates)
                continue
            for row in mates:
                if row["id"] == src["id"] or (src["name"] and row["name"] == src["name"]):
                    matched.append(row)
    if not matched and src["name"]:
        matched = [row for row in all_rows if row["name"] == src["name"]]
    if not matched:
        return [src["id"]]
    out = []
    seen = set()
    for row in matched:
        rid = row["id"]
        if rid in seen:
            continue
        seen.add(rid)
        out.append(rid)
    return out


def _remap_ids_for_current_version_from_rows(ids, src_rows, current_rows, current_version_id):
    src_by_id = {row["id"]: row for row in src_rows}
    out = []
    seen = set()
    for orig in ids:
        src = src_by_id.get(orig)
        cid = orig if src is None else _choose_current_version_id(
            src, current_rows, current_version_id
        )
        if cid in seen:
            continue
        seen.add(cid)
        out.append(cid)
    return out


def _expand_ids_across_versions_from_rows(ids, src_rows, all_rows):
    src_by_id = {row["id"]: row for row in src_rows}
    out = []
    seen = set()
    for orig in ids:
        src = src_by_id.get(orig)
        expanded = [orig] if src is None else _expand_identity_ids(src, all_rows)
        for cid in expanded:
            if cid in seen:
                continue
            seen.add(cid)
            out.append(cid)
    return out


def _resolve_territorial_ids_by_ref_uuid(model_cls, uuid_strings):
    """Сопоставляет ref_uuid справочника с id строки в текущей версии БД."""
    uuids = _normalize_uuid_strings(uuid_strings)
    if not uuids:
        return []
    q = db.session.query(model_cls).filter(model_cls.ref_uuid.in_(uuids))
    q = filter_by_db_version(q, model_cls)
    rows = q.all()
    by_ref = defaultdict(list)
    for row in rows:
        key = _norm_ref_key(getattr(row, "ref_uuid", None))
        if key:
            by_ref[key].append(row)
    out = []
    seen = set()
    for raw in uuids:
        key = _norm_ref_key(raw)
        hits = by_ref.get(key) or []
        if len(hits) == 1:
            chosen = hits[0]
        elif len(hits) > 1:
            # Несколько субъектов с одним uuid — не схлопываем в один id.
            for hit in hits:
                cid = hit.id
                if cid not in seen:
                    seen.add(cid)
                    out.append(cid)
            continue
        else:
            continue
        cid = chosen.id
        if cid in seen:
            continue
        seen.add(cid)
        out.append(cid)
    return out


def _remap_territorial_ids_for_current_version(model_cls, id_list):
    """
    Подменяет id из URL (другой версии БД) на id той же сущности в текущей версии
    через стабильный ref_uuid.

    Если исходный id уже принадлежит текущей версии — оставляем его. Иначе при
    нескольких строках с одним ref_uuid выбираем совпадение по name, чтобы
    Забайкальский край не превращался в Калининградскую область.
    """
    ids = _parse_int_ids(id_list)
    if not ids:
        return []
    src_rows = _load_territorial_identity_rows(model_cls, ids=ids)
    if not src_rows:
        return ids
    ref_uuids = [row["ref_uuid_raw"] for row in src_rows if row.get("ref_uuid_raw")]
    names = [row["name"] for row in src_rows if row["name"]]
    current_rows = []
    if ref_uuids:
        current_rows.extend(
            _load_territorial_identity_rows(
                model_cls,
                ref_uuids=ref_uuids,
                current_version_only=True,
            )
        )
    if names:
        known = {row["id"] for row in current_rows}
        for row in _load_territorial_identity_rows(
            model_cls,
            names=names,
            current_version_only=True,
        ):
            if row["id"] not in known:
                current_rows.append(row)
                known.add(row["id"])
    from app.common.services.database_version_filter import get_current_db_version_id

    return _remap_ids_for_current_version_from_rows(
        ids,
        src_rows,
        current_rows,
        get_current_db_version_id(),
    )


def _expand_territorial_ids_across_versions(model_cls, id_list):
    """Все id той же сущности во всех версиях БД (для страницы проверки взаимосвязей)."""
    ids = _parse_int_ids(id_list)
    if not ids:
        return []
    src_rows = _load_territorial_identity_rows(model_cls, ids=ids)
    if not src_rows:
        return ids
    ref_uuids = [row["ref_uuid_raw"] for row in src_rows if row.get("ref_uuid_raw")]
    names = [row["name"] for row in src_rows if row["name"]]
    all_rows = list(src_rows)
    known = {row["id"] for row in all_rows}
    if ref_uuids:
        for row in _load_territorial_identity_rows(model_cls, ref_uuids=ref_uuids):
            if row["id"] not in known:
                all_rows.append(row)
                known.add(row["id"])
    if names:
        for row in _load_territorial_identity_rows(model_cls, names=names):
            if row["id"] not in known:
                all_rows.append(row)
                known.add(row["id"])
    return _expand_ids_across_versions_from_rows(ids, src_rows, all_rows)


def expand_versioned_ref_list_filters_across_versions(filters):
    """Расширяет id фильтров справочников на все версии БД с той же сущностью."""
    if not filters:
        return filters
    for fk, _refk, model_cls in _VERSIONED_REF_LIST_FILTER_SPEC:
        ids = filters.get(fk) or []
        if not ids:
            continue
        filters[fk] = _expand_territorial_ids_across_versions(model_cls, ids)
    return filters


_VERSIONED_REF_LIST_FILTER_SPEC = (
    ("energy_system_type_filter", "energy_system_type_ref", EnergySystemType),
    ("union_energy_system_filter", "union_energy_system_ref", UnionEnergySystem),
    ("regional_energy_system_filter", "regional_energy_system_ref", RegionalEnergySystem),
    ("federal_district_filter", "federal_district_ref", FederalDistrict),
    ("regional_district_filter", "regional_district_ref", RegionalDistrict),
    ("station_type_filter", "station_type_ref", StationType),
    ("fuel_type_filter", "fuel_type_ref", FuelType),
    ("tes_type_filter", "tes_type_ref", TesType),
    ("tes_machine_type_filter", "tes_machine_type_ref", TesMachineType),
    ("pgu_tes_machine_type_filter", "pgu_tes_machine_type_ref", PGUTesMachineType),
)

_REF_FILTER_PARAM_NAMES = tuple(r for _, r, __ in _VERSIONED_REF_LIST_FILTER_SPEC) + (
    "station_fuel_type_ref",
    "condition_type_ref",
)


def _remap_versioned_ref_list_filters(filters, args):
    """Справочники с id в query/form: uuid из *_ref либо перенос pk между версиями БД."""
    for fk, refk, model_cls in _VERSIONED_REF_LIST_FILTER_SPEC:
        ref_raw = _args_getlist_raw(args, refk)
        if fk == "fuel_type_filter":
            ref_raw = ref_raw + _args_getlist_raw(args, "station_fuel_type_ref")
        if ref_raw:
            filters[fk] = _resolve_territorial_ids_by_ref_uuid(model_cls, ref_raw)
        else:
            filters[fk] = _remap_territorial_ids_for_current_version(
                model_cls, filters.get(fk) or []
            )


def _remap_condition_type_filter(filters, args):
    """Состояние агрегата: одно значение; в URL — condition_type_ref или condition_type_filter."""
    ref_raw = _args_getlist_raw(args, "condition_type_ref")
    if ref_raw:
        ids = _resolve_territorial_ids_by_ref_uuid(ConditionType, ref_raw)
        filters["condition_type_filter"] = ids[0] if ids else None
        return
    ct = filters.get("condition_type_filter")
    if ct is None:
        return
    mapped = _remap_territorial_ids_for_current_version(ConditionType, [ct])
    filters["condition_type_filter"] = mapped[0] if mapped else None


def extract_filters_from_args(args):
    # Нормализуем condition_type_filter: парсим int, игнорируем None/0
    condition_type = args.get("condition_type_filter", type=int)
    if condition_type in (None, 0):
        condition_type = None

    # Совместимость: поддержим оба параметра для вида топлива
    _fuel_type_filter = args.getlist("fuel_type_filter", type=int)
    if not _fuel_type_filter:
        _fuel_type_filter = args.getlist("station_fuel_type_filter", type=int)

    filters = {
        "page": args.get("page", 1, type=int),
        "start_year": args.get("start_year", get_filter_start_year(), type=int),
        "end_year": args.get("end_year", get_filter_end_year(), type=int),
        # Проверка качества заполнения топлива (для station_list)
        "fuel_check": args.get("fuel_check", "0") == "1",
        "condition_type_filter": condition_type,
        "energy_system_type_filter": args.getlist("energy_system_type_filter", type=int),
        "union_energy_system_filter": args.getlist("union_energy_system_filter", type=int),
        "regional_energy_system_filter": args.getlist("regional_energy_system_filter", type=int),
        "energy_unit_filter": args.getlist("energy_unit_filter", type=int),
        "federal_district_filter": args.getlist("federal_district_filter", type=int),
        "regional_district_filter": args.getlist("regional_district_filter", type=int),
        "gen_company_filter": args.get("gen_company_filter", "").strip(),
        "station_name_filter": args.get("station_name_filter", "").strip(),
        "note_filter": args.get("note_filter", "").strip(),
        "equipment_group_name_filter": args.get("equipment_group_name_filter", "").strip(),
        "numb1120_filter": _parse_int_list_filter(_args_getlist_raw(args, "numb1120_filter")),
        "station_type_filter": args.getlist("station_type_filter", type=int),
        "station_sign_filter": args.getlist("station_sign_filter"),
        "fuel_type_filter": _fuel_type_filter,
        "tes_type_filter": args.getlist("tes_type_filter", type=int),
        "tes_machine_type_filter": args.getlist("tes_machine_type_filter", type=int),
        "pgu_tes_machine_type_filter": args.getlist("pgu_tes_machine_type_filter", type=int),
        "date_commission_filter": _parse_year_filter(args.getlist("date_commission_filter")),
        "date_exploitation_filter": _parse_year_filter(args.getlist("date_exploitation_filter")),
        "date_decompressing_expected_filter": _parse_year_filter(args.getlist("date_decompressing_expected_filter")),
        "date_modernization_expected_filter": _parse_year_filter(args.getlist("date_modernization_expected_filter")),
        "date_modernization_no_power_expected_filter": _parse_year_filter(
            args.getlist("date_modernization_no_power_expected_filter")
        ),
        "relabing_outcome_filter": args.getlist("relabing_outcome_filter"),
        "machines_without_equipment_group": args.get("machines_without_equipment_group", "0") == "1",
        "missing_numb": str(args.get("missing_numb") or "0").lower() in (
            "1",
            "true",
            "yes",
            "on",
        ),
        # Станции с суммарной установленной мощностью (на as-of год) > 100 МВт
        "um_gt_100": args.get("um_gt_100", "0") == "1",
        "sort_by": args.get("sort_by", "id"),
        "sort_dir": args.get("sort_dir", "asc"),
        # Для страницы изменений мощности (station_changes): фильтр по мероприятиям
        "event_type_filter": args.getlist("event_type_filter"),
    }
    _remap_versioned_ref_list_filters(filters, args)
    _remap_condition_type_filter(filters, args)
    return filters


def extract_filters_from_form(form):
    return extract_filters_from_args(form)


def _build_year_filter_clause(column_or_pair, values, include_null_cond=None):
    """
    Строит условие фильтра по годам с поддержкой «не указано».
    column_or_pair: одна колонка или or_(col1, col2) для OR по двум полям.
    values: список [2020, None, 2021] — года и/или None для «не указано».
    include_null_cond: условие для «не указано» (and_(col1.is_(None), col2.is_(None))).
    """
    years_only = [y for y in values if y is not None]
    include_null = None in values
    conds = []
    if years_only:
        if hasattr(column_or_pair, "in_"):
            conds.append(column_or_pair.in_(years_only))
        else:
            conds.append(column_or_pair)
    if include_null and include_null_cond:
        conds.append(include_null_cond)
    if not conds:
        return None
    return or_(*conds)


def build_date_commission_filter(machine_cls, filters):
    """Фильтр «Ввод в работу»: date_commission_year или date_exploitation_expected."""
    vals = filters.get("date_commission_filter")
    if not vals:
        return None
    years_only = [y for y in vals if y is not None]
    include_null = None in vals
    conds = []
    if years_only:
        conds.append(
            or_(
                machine_cls.date_commission_year.in_(years_only),
                machine_cls.date_exploitation_expected.in_(years_only),
            )
        )
    if include_null:
        conds.append(
            and_(
                machine_cls.date_commission_year.is_(None),
                machine_cls.date_exploitation_expected.is_(None),
            )
        )
    return or_(*conds) if conds else None


def build_date_exploitation_filter(machine_cls, filters):
    """Фильтр «Ввод в экспл.»: date_exploitation или date_exploitation_expected."""
    vals = filters.get("date_exploitation_filter")
    if not vals:
        return None
    years_only = [y for y in vals if y is not None]
    include_null = None in vals
    conds = []
    if years_only:
        conds.append(
            or_(
                machine_cls.date_exploitation.in_(years_only),
                machine_cls.date_exploitation_expected.in_(years_only),
            )
        )
    if include_null:
        conds.append(
            and_(
                machine_cls.date_exploitation.is_(None),
                machine_cls.date_exploitation_expected.is_(None),
            )
        )
    return or_(*conds) if conds else None


def build_date_decompressing_filter(machine_cls, filters):
    """Фильтр «Вывод из экспл.»: date_decompressing_fact (год) или date_decompressing_expected.

    Для фактической даты применяется то же правило, что в карточке/списке:
    01.01.XX относится к году XX-1.
    """
    vals = filters.get("date_decompressing_expected_filter")
    if not vals:
        return None
    years_only = [y for y in vals if y is not None]
    include_null = None in vals
    conds = []
    if years_only:
        # Как у модернизации: 01.01.(Y+1) → Y, иначе календарный год Y (не 01.01).
        pats = []
        for y in years_only:
            pats.append(rf"01\.01\.{y + 1}\b")
            pats.append(rf"(?<!01\.01\.){y}(?!\d)")
        fact_regex = "(" + "|".join(pats) + ")"
        conds.append(
            or_(
                machine_cls.date_decompressing_expected.in_(years_only),
                machine_cls.date_decompressing_fact.op("~")(fact_regex),
            )
        )
    if include_null:
        conds.append(
            and_(
                machine_cls.date_decompressing_fact.is_(None),
                machine_cls.date_decompressing_expected.is_(None),
            )
        )
    return or_(*conds) if conds else None


def build_date_modernization_filter(machine_cls, filters):
    """Фильтр «Модерн.»: ожидаемые годы модернизации (с/без изм. мощности), date_relabing_fact (правило 01.01.год → год-1)."""
    vals = filters.get("date_modernization_expected_filter")
    if not vals:
        return None
    years_only = [y for y in vals if y is not None]
    include_null = None in vals
    conds = []
    if years_only:
        pats = []
        for y in years_only:
            pats.append(rf"01\.01\.{y + 1}\b")
            pats.append(rf"(?<!01\.01\.){y}(?!\d)")
        conds.append(
            or_(
                machine_cls.date_modernization_power_change_expected.in_(years_only),
                machine_cls.date_modernization_no_power_change_expected.in_(years_only),
                machine_cls.date_relabing_fact.op("~")("(" + "|".join(pats) + ")"),
            )
        )
    if include_null:
        conds.append(
            and_(
                machine_cls.date_modernization_power_change_expected.is_(None),
                machine_cls.date_modernization_no_power_change_expected.is_(None),
                machine_cls.date_relabing_fact.is_(None),
            )
        )
    return or_(*conds) if conds else None


def build_date_modernization_no_power_filter(machine_cls, filters):
    """Фильтр колонки «Модерн. без изм. мощ-ти»: только date_modernization_no_power_change_expected."""
    vals = filters.get("date_modernization_no_power_expected_filter")
    if not vals:
        return None
    return _build_year_filter_clause(
        machine_cls.date_modernization_no_power_change_expected,
        vals,
        include_null_cond=machine_cls.date_modernization_no_power_change_expected.is_(None),
    )


def build_relabing_outcome_filter(machine_cls, filters):
    """Фильтр «Вид изменений»: значения Machine.relabing_outcome; пустое значение — «не указано»."""
    raw = filters.get("relabing_outcome_filter") or []
    if not raw:
        return None
    specifics = [str(v).strip() for v in raw if v is not None and str(v).strip() != ""]
    unspecified = any(v is None or str(v).strip() == "" for v in raw)
    parts = []
    if specifics:
        parts.append(machine_cls.relabing_outcome.in_(specifics))
    if unspecified:
        parts.append(
            or_(
                machine_cls.relabing_outcome.is_(None),
                func.trim(machine_cls.relabing_outcome) == "",
            )
        )
    return or_(*parts) if parts else None


def build_machines_without_equipment_group_filter(machine_cls):
    """Агрегаты без явной топливной группы на карточке в текущей версии БД.

    «Группа оборудования» — MachineFuelParam.equipment_group_id, не тип
    Machine.id_equipment_group. Явная привязка: группа текущей версии,
    связанная с электростанцией агрегата (в том числе общая на две станции).
    """
    from app.fuel.models.fue_equipment_group_model import EquipmentGroup
    from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
    from app.fuel.models.fue_equipment_group_set_station_model import (
        EquipmentGroupSetStation,
    )
    from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam

    version_id = get_current_db_version_id()
    if version_id is None:
        group_version = EquipmentGroup.database_version_id.is_(None)
    else:
        group_version = EquipmentGroup.database_version_id == version_id

    set_own = EquipmentGroupSet.__table__.alias("fue_eg_set_own")
    link_own = EquipmentGroupSetStation.__table__.alias("fue_eg_link_own")

    machine_t = machine_cls.__table__
    machine_station_id = (
        select(machine_t.c.id_station)
        .where(machine_t.c.id == MachineFuelParam.machine_id)
        .correlate(MachineFuelParam)
        .scalar_subquery()
    )

    linked_to_machine_station_stmt = (
        select(1)
        .select_from(
            set_own.join(
                link_own,
                link_own.c.id == set_own.c.equipment_group_set_station_id,
            )
        )
        .where(
            set_own.c.equipment_group_id == MachineFuelParam.equipment_group_id,
            link_own.c.station_id == machine_station_id,
        )
    )
    if version_id is None:
        linked_to_machine_station_stmt = linked_to_machine_station_stmt.where(
            link_own.c.database_version_id.is_(None)
        )
    else:
        linked_to_machine_station_stmt = linked_to_machine_station_stmt.where(
            link_own.c.database_version_id == version_id
        )
    linked_to_machine_station = exists(linked_to_machine_station_stmt)
    has_clear_fuel_group = exists().where(
        and_(
            MachineFuelParam.machine_id == machine_cls.id,
            MachineFuelParam.equipment_group_id.isnot(None),
            MachineFuelParam.equipment_group_id != 0,
            EquipmentGroup.id == MachineFuelParam.equipment_group_id,
            group_version,
            linked_to_machine_station,
        )
    )
    return ~has_clear_fuel_group


def build_station_sign_sql_filter(filters):
    """Фильтр по Station.station_sign; __unspecified__ — пустое значение."""
    raw = filters.get("station_sign_filter") or []
    if not raw:
        return None

    specifics = [
        str(value).strip()
        for value in raw
        if str(value).strip() and str(value).strip() != STATION_SIGN_FILTER_UNSPECIFIED
    ]
    include_unspecified = STATION_SIGN_FILTER_UNSPECIFIED in raw

    parts = []
    if specifics:
        parts.append(Station.station_sign.in_(specifics))
    if include_unspecified:
        parts.append(
            or_(
                Station.station_sign.is_(None),
                func.trim(Station.station_sign) == "",
            )
        )
    return or_(*parts) if parts else None


def apply_station_sign_sql_filter(query, filters):
    condition = build_station_sign_sql_filter(filters)
    if condition is not None:
        return query.filter(condition)
    return query


def get_station_sign_filter_choices() -> list[tuple[str, str]]:
    """Уникальные значения признака эл.ст. в текущей версии БД + «не указано»."""
    q = db.session.query(Station.station_sign).distinct()
    q = filter_by_db_version(q, Station)

    choices: list[tuple[str, str]] = []
    seen: set[str] = set()

    for (sign,) in q.all():
        if sign is None or not str(sign).strip():
            continue
        normalized = str(sign).strip()
        if normalized in seen:
            continue
        seen.add(normalized)
        choices.append((normalized, normalized))

    choices.sort(key=lambda item: item[1].casefold())
    return [(STATION_SIGN_FILTER_UNSPECIFIED, "не указано"), *choices]


def build_date_filters_for_pgu(pgu_cls, filters):
    """
    Применяет фильтры по датам для PGUMachine.
    Возвращает список условий для добавления в query.
    """
    conds = []
    # Ввод в работу: date_commission_year или date_exploitation_expected
    vals = filters.get("date_commission_filter")
    if vals:
        years_only = [y for y in vals if y is not None]
        include_null = None in vals
        parts = []
        if years_only:
            parts.append(
                or_(
                    pgu_cls.date_commission_year.in_(years_only),
                    pgu_cls.date_exploitation_expected.in_(years_only),
                )
            )
        if include_null:
            parts.append(
                and_(
                    pgu_cls.date_commission_year.is_(None),
                    pgu_cls.date_exploitation_expected.is_(None),
                )
            )
        if parts:
            conds.append(or_(*parts))
    vals = filters.get("date_exploitation_filter")
    if vals:
        years_only = [y for y in vals if y is not None]
        include_null = None in vals
        parts = []
        if years_only:
            parts.append(
                or_(
                    pgu_cls.date_exploitation.in_(years_only),
                    pgu_cls.date_exploitation_expected.in_(years_only),
                )
            )
        if include_null:
            parts.append(
                and_(
                    pgu_cls.date_exploitation.is_(None),
                    pgu_cls.date_exploitation_expected.is_(None),
                )
            )
        if parts:
            conds.append(or_(*parts))
    vals = filters.get("date_decompressing_expected_filter")
    if vals:
        years_only = [y for y in vals if y is not None]
        include_null = None in vals
        parts = []
        if years_only:
            pats = []
            for y in years_only:
                pats.append(rf"01\.01\.{y + 1}\b")
                pats.append(rf"(?<!01\.01\.){y}(?!\d)")
            fact_regex = "(" + "|".join(pats) + ")"
            parts.append(
                or_(
                    pgu_cls.date_decompressing_expected.in_(years_only),
                    pgu_cls.date_decompressing_fact.op("~")(fact_regex),
                )
            )
        if include_null:
            parts.append(
                and_(
                    pgu_cls.date_decompressing_fact.is_(None),
                    pgu_cls.date_decompressing_expected.is_(None),
                )
            )
        if parts:
            conds.append(or_(*parts))
    vals = filters.get("date_modernization_expected_filter")
    if vals:
        years_only = [y for y in vals if y is not None]
        include_null = None in vals
        parts = []
        if years_only:
            pats = []
            for y in years_only:
                pats.append(rf"01\.01\.{y + 1}\b")
                pats.append(rf"(?<!01\.01\.){y}(?!\d)")
            parts.append(
                or_(
                    pgu_cls.date_modernization_power_change_expected.in_(years_only),
                    pgu_cls.date_modernization_no_power_change_expected.in_(years_only),
                    pgu_cls.date_relabing_fact.op("~")("(" + "|".join(pats) + ")"),
                )
            )
        if include_null:
            parts.append(
                and_(
                    pgu_cls.date_modernization_power_change_expected.is_(None),
                    pgu_cls.date_modernization_no_power_change_expected.is_(None),
                    pgu_cls.date_relabing_fact.is_(None),
                )
            )
        if parts:
            conds.append(or_(*parts))
    vals = filters.get("date_modernization_no_power_expected_filter")
    if vals:
        years_only = [y for y in vals if y is not None]
        include_null = None in vals
        parts = []
        if years_only:
            parts.append(pgu_cls.date_modernization_no_power_change_expected.in_(years_only))
        if include_null:
            parts.append(pgu_cls.date_modernization_no_power_change_expected.is_(None))
        if parts:
            conds.append(or_(*parts))
    return conds


def get_pgu_date_cond_for_filter(pgu_cls, filters, filter_key):
    """
    Возвращает условие PGUMachine для конкретного фильтра по дате.
    filter_key: 'date_commission_filter', 'date_exploitation_filter', и т.д.
    """
    if filter_key == "date_commission_filter":
        vals = filters.get("date_commission_filter")
        if not vals:
            return None
        years_only = [y for y in vals if y is not None]
        include_null = None in vals
        parts = []
        if years_only:
            parts.append(or_(pgu_cls.date_commission_year.in_(years_only), pgu_cls.date_exploitation_expected.in_(years_only)))
        if include_null:
            parts.append(and_(pgu_cls.date_commission_year.is_(None), pgu_cls.date_exploitation_expected.is_(None)))
        return or_(*parts) if parts else None
    if filter_key == "date_exploitation_filter":
        vals = filters.get("date_exploitation_filter")
        if not vals:
            return None
        years_only = [y for y in vals if y is not None]
        include_null = None in vals
        parts = []
        if years_only:
            parts.append(or_(pgu_cls.date_exploitation.in_(years_only), pgu_cls.date_exploitation_expected.in_(years_only)))
        if include_null:
            parts.append(and_(pgu_cls.date_exploitation.is_(None), pgu_cls.date_exploitation_expected.is_(None)))
        return or_(*parts) if parts else None
    if filter_key == "date_decompressing_expected_filter":
        vals = filters.get("date_decompressing_expected_filter")
        if not vals:
            return None
        years_only = [y for y in vals if y is not None]
        include_null = None in vals
        parts = []
        if years_only:
            pats = []
            for y in years_only:
                pats.append(rf"01\.01\.{y + 1}\b")
                pats.append(rf"(?<!01\.01\.){y}(?!\d)")
            fact_regex = "(" + "|".join(pats) + ")"
            parts.append(
                or_(
                    pgu_cls.date_decompressing_expected.in_(years_only),
                    pgu_cls.date_decompressing_fact.op("~")(fact_regex),
                )
            )
        if include_null:
            parts.append(and_(pgu_cls.date_decompressing_fact.is_(None), pgu_cls.date_decompressing_expected.is_(None)))
        return or_(*parts) if parts else None
    if filter_key == "date_modernization_expected_filter":
        vals = filters.get("date_modernization_expected_filter")
        if not vals:
            return None
        years_only = [y for y in vals if y is not None]
        include_null = None in vals
        parts = []
        if years_only:
            pats = []
            for y in years_only:
                pats.append(rf"01\.01\.{y + 1}\b")
                pats.append(rf"(?<!01\.01\.){y}(?!\d)")
            parts.append(
                or_(
                    pgu_cls.date_modernization_power_change_expected.in_(years_only),
                    pgu_cls.date_modernization_no_power_change_expected.in_(years_only),
                    pgu_cls.date_relabing_fact.op("~")("(" + "|".join(pats) + ")"),
                )
            )
        if include_null:
            parts.append(
                and_(
                    pgu_cls.date_modernization_power_change_expected.is_(None),
                    pgu_cls.date_modernization_no_power_change_expected.is_(None),
                    pgu_cls.date_relabing_fact.is_(None),
                )
            )
        return or_(*parts) if parts else None
    if filter_key == "date_modernization_no_power_expected_filter":
        vals = filters.get("date_modernization_no_power_expected_filter")
        if not vals:
            return None
        years_only = [y for y in vals if y is not None]
        include_null = None in vals
        parts = []
        if years_only:
            parts.append(pgu_cls.date_modernization_no_power_change_expected.in_(years_only))
        if include_null:
            parts.append(pgu_cls.date_modernization_no_power_change_expected.is_(None))
        return or_(*parts) if parts else None
    return None


def fetch_filtered_machines_with_rowspans(station_ids: list[int], filters: dict):
    """
    Загружает агрегаты с применением SQL-фильтров и рассчитывает group_rowspan и fuel_rowspan.
    """
    from app.common.services.get_services.years.years_get_services import (
        get_filter_start_year,
        get_filter_end_year,
    )

    query = Machine.query.options(
        joinedload(Machine.tes_machine_type),
        joinedload(Machine.machine_station).joinedload(Station.station_type),
        joinedload(Machine.machine_tes_types).joinedload(MachineTesType.tes_type),
    ).filter(Machine.id_station.in_(station_ids))

    # Фильтрация по типу ТЭС — по диапазону годов фильтров (ввод/вывод в периоде)
    if filters.get("tes_type_filter"):
        _sy = int(filters.get("start_year") or get_filter_start_year())
        _ey = int(filters.get("end_year") or get_filter_end_year())
        query = query.filter(
            Machine.machine_tes_types.any(
                and_(
                    MachineTesType.year_number.between(_sy, _ey),
                    MachineTesType.id_tes_type.in_(filters["tes_type_filter"])
                )
            )
        )

    # Фильтрация по типу агрегата
    if filters.get("tes_machine_type_filter"):
        query = query.filter(
            Machine.id_tes_machine_type.in_(filters["tes_machine_type_filter"])
        )

    # Фильтрация по виду топлива
    if filters.get("fuel_type_filter"):
        query = query.filter(
            Machine.machine_fuels.any(
                MachineFuel.fuel.has(
                    Fuel.fuel_type.has(
                        FuelType.id.in_(filters["fuel_type_filter"])
                    )
                )
            )
        )

    # Фильтрация по датам (ввода в работу, ввода в экспл., вывода, модернизации)
    if filters.get("date_commission_filter"):
        vals = filters["date_commission_filter"]
        years_only = [y for y in vals if y is not None]
        include_null = None in vals
        conds = []
        if years_only:
            conds.append(
                or_(
                    Machine.date_commission_year.in_(years_only),
                    Machine.date_exploitation_expected.in_(years_only),
                )
            )
        if include_null:
            conds.append(
                and_(
                    Machine.date_commission_year.is_(None),
                    Machine.date_exploitation_expected.is_(None),
                )
            )
        if conds:
            query = query.filter(or_(*conds))

    if filters.get("date_exploitation_filter"):
        vals = filters["date_exploitation_filter"]
        years_only = [y for y in vals if y is not None]
        include_null = None in vals
        conds = []
        if years_only:
            conds.append(
                or_(
                    Machine.date_exploitation.in_(years_only),
                    Machine.date_exploitation_expected.in_(years_only),
                )
            )
        if include_null:
            conds.append(
                and_(
                    Machine.date_exploitation.is_(None),
                    Machine.date_exploitation_expected.is_(None),
                )
            )
        if conds:
            query = query.filter(or_(*conds))

    dm_decomp = build_date_decompressing_filter(Machine, filters)
    if dm_decomp is not None:
        query = query.filter(dm_decomp)

    dm_cond = build_date_modernization_filter(Machine, filters)
    if dm_cond is not None:
        query = query.filter(dm_cond)

    dmn_cond = build_date_modernization_no_power_filter(Machine, filters)
    if dmn_cond is not None:
        query = query.filter(dmn_cond)

    ro_cond = build_relabing_outcome_filter(Machine, filters)
    if ro_cond is not None:
        query = query.filter(ro_cond)

    machines = query.all()

    # Привязываем к станциям
    station_machine_map = defaultdict(list)
    for m in machines:
        station_machine_map[m.id_station].append(m)

    # Для каждой электростанции сортируем и проставляем rowspan
    for machine_list in station_machine_map.values():
        machine_list.sort(key=lambda m: (
            (m.machine_group or '').lower(),
            (m.fuel_so or '').lower(),
            int(m.machine_number) if m.machine_number and str(m.machine_number).strip().isdigit() else float('inf')
        ))

        group_dict = defaultdict(list)
        for m in machine_list:
            group_key = (m.machine_group or '').strip()
            group_dict[group_key].append(m)
        for group in group_dict.values():
            group[0].group_rowspan = len(group)
            for m in group[1:]:
                m.group_rowspan = 0

        fuel_dict = defaultdict(list)
        for m in machine_list:
            fuel_key = (m.fuel_so or '').strip()
            fuel_dict[fuel_key].append(m)
        for group in fuel_dict.values():
            group[0].fuel_rowspan = len(group)
            for m in group[1:]:
                m.fuel_rowspan = 0

    all_machines = []
    for lst in station_machine_map.values():
        all_machines.extend(lst)

    return all_machines


def get_filtered_station_ids(
    condition_type_filter=None,
    gen_company_filter=None,
    station_name_filter=None,
    station_type_filter=None,
    tes_type_filter=None,
    tes_machine_type_filter=None,
    energy_system_type_filter=None,
    union_energy_system_filter=None,
    regional_energy_system_filter=None,
    federal_district_filter=None,
    regional_district_filter=None,
    date_commission_filter=None,
    date_exploitation_filter=None,
):

    # 1) Начинаем с запроса Station
    query = db.session.query(Station.id)
    
    # Если нужны фильтры по агрегатам, делаем join
    needs_machine_join = bool(
        tes_type_filter or tes_machine_type_filter or gen_company_filter or condition_type_filter
        or date_commission_filter or date_exploitation_filter
    )
    if needs_machine_join:
        query = query.join(Station.machines)

    from app.common.services.get_services.years.years_get_services import (
        get_filter_start_year,
        get_filter_end_year,
    )
    _sy = get_filter_start_year()
    _ey = get_filter_end_year()

    # 2) Применяем фильтры.
    if station_type_filter:
        query = query.filter(Station.id_station_type.in_(station_type_filter))
    if tes_type_filter:
        query = query.filter(
            exists().where(
                MachineTesType.id_machine == Machine.id,
                MachineTesType.year_number.between(_sy, _ey),
                MachineTesType.id_tes_type.in_(tes_type_filter)
            )
        )

    # Фильтрация по названию генерирующей компании
    if gen_company_filter:
        gen_companies = GenCompany.query.filter(GenCompany.name.ilike(f"%{gen_company_filter}%")).all()
        gen_company_ids = [company.id for company in gen_companies]
        
        query = query.join(Station.machines).filter(Machine.id_gen_company.in_(gen_company_ids))

    # Фильтрация по названию  электростанции
    if station_name_filter:
        query = query.filter(Station.name.ilike(f"%{station_name_filter}%"))
    
    # Фильтрация по типу энергосистемы
    if energy_system_type_filter:
        query = query.filter(
            Station.regional_energy_system_obj.has(
                RegionalEnergySystem.union_energy_system.has(
                    UnionEnergySystem.energy_system_type.has(
                        EnergySystemType.id.in_(energy_system_type_filter)
                    )
                )
            )
        )

    # Фильтрация по объединенной энергосистеме
    if union_energy_system_filter:
        if not isinstance(union_energy_system_filter, list):
            union_energy_system_filter = [union_energy_system_filter]

        # Как Station.union_energy_system: прямая РЭС, иначе fallback через субъект
        # (только если РЭС не задана — иначе Красноярский край тянет и ОЭС Сибири, и ТИТЭС).
        query = query.filter(
            or_(
                Station.regional_energy_system_obj.has(
                    RegionalEnergySystem.id_union_energy_system.in_(union_energy_system_filter)
                ),
                and_(
                    Station.id_regional_energy_system.is_(None),
                    Station.regional_district.has(
                        RegionalDistrict.regional_energy_systems.any(
                            RegionalEnergySystem.id_union_energy_system.in_(
                                union_energy_system_filter
                            )
                        )
                    ),
                ),
            )
        )

    # Фильтрация по региональной энергосистеме
    if regional_energy_system_filter:
        if not isinstance(regional_energy_system_filter, list):
            regional_energy_system_filter = [regional_energy_system_filter]

        query = query.filter(
            Station.id_regional_energy_system.in_(regional_energy_system_filter)
        )

    # Фильтрация по ФО
    if federal_district_filter:
        if not isinstance(federal_district_filter, list):
            federal_district_filter = [federal_district_filter]

        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.federal_district.has(
                    FederalDistrict.id.in_(federal_district_filter)  # Используем .in_()
                )
            )
        )

    # Фильтрация по субъекту РФ
    if regional_district_filter:
        if not isinstance(regional_district_filter, list):
            regional_district_filter = [regional_district_filter]

        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.id.in_(regional_district_filter)  # Используем .in_()
            )
        )

    # Фильтрация по состоянию  электростанции
    if condition_type_filter:
        query = query.join(Station.machines).filter(Machine.id_condition_type == condition_type_filter)

    # 3) Делаем distinct(Station.id), чтобы каждая станция была 1 раз
    query = query.distinct(Station.id)

    # 4) Возвращаем подзапрос 
    return query.subquery()


def get_stations_all(
    energy_system_type_filter=None,
    union_energy_system_filter=None,
    regional_energy_system_filter=None,
    federal_district_filter=None,
    regional_district_filter=None,
    start_year=None,
    end_year=None,
):
    """
    Фильтрует электростанции по переданным параметрам и по диапазону лет (если заданы).
    Если заданы start_year и end_year, фильтруются только агрегаты с мощностью в указанный период.
    Также отбрасываются агрегаты с планируемым выводом до START_YEAR_SIPR.
    """
    query = db.session.query(Station).distinct().join(Station.machines)

    # Важно: т.к. мы join-им machines и используем contains_eager, то любые joinedload по другим связям
    # приведут к раздуванию результата. Для связанных справочников используем selectinload.
    query = query.options(
        contains_eager(Station.machines),
        selectinload(Station.regional_district)
            .selectinload(RegionalDistrict.regional_energy_systems)
            .selectinload(RegionalEnergySystem.union_energy_system)
            .selectinload(UnionEnergySystem.energy_system_type),
        selectinload(Station.energy_unit),
        selectinload(Station.station_type),
    )

    # Фильтрация по типу энергосистемы
    if energy_system_type_filter:
        if not isinstance(energy_system_type_filter, list):
            energy_system_type_filter = [energy_system_type_filter]
        query = query.filter(
            Station.regional_energy_system_obj.has(
                RegionalEnergySystem.union_energy_system.has(
                    UnionEnergySystem.energy_system_type.has(
                        EnergySystemType.id.in_(energy_system_type_filter)
                    )
                )
            )
        )

    # Фильтрация по объединенной энергосистеме
    if union_energy_system_filter:
        if not isinstance(union_energy_system_filter, list):
            union_energy_system_filter = [union_energy_system_filter]

        # Как Station.union_energy_system: прямая РЭС, иначе fallback через субъект
        # (только если РЭС не задана — иначе Красноярский край тянет и ОЭС Сибири, и ТИТЭС).
        query = query.filter(
            or_(
                Station.regional_energy_system_obj.has(
                    RegionalEnergySystem.id_union_energy_system.in_(union_energy_system_filter)
                ),
                and_(
                    Station.id_regional_energy_system.is_(None),
                    Station.regional_district.has(
                        RegionalDistrict.regional_energy_systems.any(
                            RegionalEnergySystem.id_union_energy_system.in_(
                                union_energy_system_filter
                            )
                        )
                    ),
                ),
            )
        )

    # Фильтрация по региональной энергосистеме
    if regional_energy_system_filter:
        if not isinstance(regional_energy_system_filter, list):
            regional_energy_system_filter = [regional_energy_system_filter]

        query = query.filter(
            Station.id_regional_energy_system.in_(regional_energy_system_filter)
        )

    # Фильтрация по федеральному округу
    if federal_district_filter:
        if not isinstance(federal_district_filter, list):
            federal_district_filter = [federal_district_filter]

        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.federal_district.has(
                    FederalDistrict.id.in_(federal_district_filter)
                )
            )
        )

    # Фильтрация по субъекту РФ
    if regional_district_filter:
        if not isinstance(regional_district_filter, list):
            regional_district_filter = [regional_district_filter]

        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.id.in_(regional_district_filter)
            )
        )

    # Фильтрация по годам, если заданы
    if start_year is not None and end_year is not None:
        query = query.join(Machine.machine_powers).filter(
            MachinePower.year_number.between(Config.START_YEAR_SIPR, Config.END_YEAR_SIPR)
        ).distinct()

    return query


def has_any_filters(args):
    """
    Проверяет, применены ли какие-либо фильтры.
    Возвращает True, если хотя бы один фильтр активен.
    """
    if hasattr(args, "getlist") and any(args.getlist(k) for k in _REF_FILTER_PARAM_NAMES):
        return True
    return any([
        # Территориальные фильтры
        args.getlist('energy_system_type_filter'),
        args.getlist('union_energy_system_filter'),
        args.getlist('regional_energy_system_filter'),
        args.getlist('federal_district_filter'),
        args.getlist('regional_district_filter'),
        # Фильтры по названиям
        args.get('station_name_filter'),
        args.get('gen_company_filter'),
        args.get('note_filter'),
        args.get('equipment_group_name_filter'),
        args.getlist('numb1120_filter'),
        # Фильтры по типам
        args.getlist('station_type_filter'),
        args.getlist('station_sign_filter'),
        args.getlist('tes_type_filter'),
        args.getlist('tes_machine_type_filter'),
        args.getlist('fuel_type_filter'),
        args.getlist('station_fuel_type_filter'),
        args.getlist('pgu_tes_machine_type_filter'),
        # Фильтры по датам
        args.getlist('date_commission_filter'),
        args.getlist('date_exploitation_filter'),
        args.getlist('date_decompressing_expected_filter'),
        args.getlist('date_modernization_expected_filter'),
        args.getlist('date_modernization_no_power_expected_filter'),
        args.getlist('relabing_outcome_filter'),
        # Фильтр по состоянию
        args.get('condition_type_filter'),
    ])


def get_territorial_filter_reference_data():
    """
    Списки и маппинги для каскадных фильтров первой строки station_list
    (тип энергосистемы, ОЭС, РЭС, ФО, субъект РФ).

    Структура совместима с блоком #filters-data и station_filters_first_row.js.
    """
    from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
        get_energy_system_type_list_full,
        get_est_to_ues_ids_map,
        get_est_to_res_ids_map,
        get_est_to_rd_ids_map,
        get_est_to_fd_ids_map,
    )
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
        get_union_energy_system_list_full,
        get_ues_to_res_ids_map,
        get_ues_to_est_id_map,
        get_ues_to_rd_ids_map,
        get_ues_to_fd_ids_map,
    )
    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_regional_energy_system_list_full,
        get_res_to_ues_id_map,
        get_res_to_est_id_map,
        get_res_to_rd_ids_map,
        get_res_to_fd_ids_map,
    )
    from app.common.services.get_services.territories.federal_district_get_services import (
        get_federal_district_list_full,
        get_fd_to_rd_ids_map,
        get_fd_to_res_ids_map,
        get_fd_to_ues_ids_map,
        get_fd_to_est_ids_map,
    )
    from app.common.services.get_services.territories.regional_district_get_services import (
        get_regional_district_list_full,
        get_rd_to_fd_id_map,
        get_rd_to_res_ids_map,
        get_rd_to_ues_ids_map,
        get_rd_to_est_ids_map,
    )

    energy_system_type_objects = get_energy_system_type_list_full()
    energy_system_type_list = [{"id": est.id, "name": est.name} for est in energy_system_type_objects]

    union_energy_system_objects = get_union_energy_system_list_full()
    union_energy_system_list = [{"id": ues.id, "name": ues.name} for ues in union_energy_system_objects]

    regional_energy_system_objects = get_regional_energy_system_list_full()
    regional_energy_system_list = [{"id": res.id, "name": res.name} for res in regional_energy_system_objects]
    regional_energy_system_mapping = get_ues_to_res_ids_map()

    federal_district_objects = get_federal_district_list_full()
    federal_district_list = [{"id": fd.id, "name": fd.name} for fd in federal_district_objects]

    regional_district_tuples = get_regional_district_list_full()
    regional_district_list = [{"id": rd_id, "name": rd_name} for rd_id, rd_name in regional_district_tuples]
    regional_district_mapping = get_fd_to_rd_ids_map()

    est_to_ues_mapping = get_est_to_ues_ids_map()
    est_to_res_mapping = get_est_to_res_ids_map()
    est_to_rd_mapping = get_est_to_rd_ids_map()
    est_to_fd_mapping = get_est_to_fd_ids_map()
    ues_to_est_mapping = get_ues_to_est_id_map()
    ues_to_res_mapping = regional_energy_system_mapping
    ues_to_rd_mapping = get_ues_to_rd_ids_map()
    ues_to_fd_mapping = get_ues_to_fd_ids_map()
    res_to_est_mapping = get_res_to_est_id_map()
    res_to_ues_mapping_one = get_res_to_ues_id_map()
    res_to_rd_mapping = get_res_to_rd_ids_map()
    res_to_fd_mapping = get_res_to_fd_ids_map()
    rd_to_fd_mapping_one = get_rd_to_fd_id_map()
    rd_to_res_mapping = get_rd_to_res_ids_map()
    rd_to_ues_mapping = get_rd_to_ues_ids_map()
    rd_to_est_mapping = get_rd_to_est_ids_map()
    fd_to_rd_mapping = regional_district_mapping
    fd_to_res_mapping = get_fd_to_res_ids_map()
    fd_to_ues_mapping = get_fd_to_ues_ids_map()
    fd_to_est_mapping = get_fd_to_est_ids_map()

    return {
        "energy_system_type_list": energy_system_type_list,
        "union_energy_system_list": union_energy_system_list,
        "regional_energy_system_list": regional_energy_system_list,
        "federal_district_list": federal_district_list,
        "regional_district_list": regional_district_list,
        "energy_system_type_filter": [],
        "union_energy_system_filter": [],
        "regional_energy_system_filter": [],
        "federal_district_filter": [],
        "regional_district_filter": [],
        "regional_energy_system_mapping": regional_energy_system_mapping,
        "regional_district_mapping": regional_district_mapping,
        "est_to_ues_mapping": est_to_ues_mapping,
        "est_to_res_mapping": est_to_res_mapping,
        "est_to_rd_mapping": est_to_rd_mapping,
        "est_to_fd_mapping": est_to_fd_mapping,
        "ues_to_est_mapping": ues_to_est_mapping,
        "ues_to_res_mapping": ues_to_res_mapping,
        "ues_to_rd_mapping": ues_to_rd_mapping,
        "ues_to_fd_mapping": ues_to_fd_mapping,
        "res_to_est_mapping": res_to_est_mapping,
        "res_to_ues_mapping_one": res_to_ues_mapping_one,
        "res_to_rd_mapping": res_to_rd_mapping,
        "res_to_fd_mapping": res_to_fd_mapping,
        "rd_to_fd_mapping_one": rd_to_fd_mapping_one,
        "rd_to_res_mapping": rd_to_res_mapping,
        "rd_to_ues_mapping": rd_to_ues_mapping,
        "rd_to_est_mapping": rd_to_est_mapping,
        "fd_to_rd_mapping": fd_to_rd_mapping,
        "fd_to_res_mapping": fd_to_res_mapping,
        "fd_to_ues_mapping": fd_to_ues_mapping,
        "fd_to_est_mapping": fd_to_est_mapping,
    }