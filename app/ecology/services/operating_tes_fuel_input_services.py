# -*- coding: utf-8 -*-
"""Топливные показатели действующих и планируемых групп по территориям макета."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import String, and_, case, cast, func, or_
from sqlalchemy.orm import aliased

from app.common.services.database_version_filter import get_current_db_version_id
from app.ecology.services.ecology_decimal_helpers import decimal_or_none as _to_decimal
from app.ecology.services.operating_tes_constants import (
    FUEL_EXTRA_SUM_FIELDS,
    FUEL_MAIN_SUM_FIELDS,
    FUEL_PARAM_FIELDS,
    TOP_INPUT_FIELD,
    VED_INDUSTRIAL,
    VED_INDUSTRY,
)
from app.extensions import db
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import (
    EquipmentGroupExtraFuelParam,
)
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.fuel.models.external_mapping.fue_em_union_energy_system_model import (
    UnionEnergySystemExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_territories_energy_model import (
    TerritoriesEnergyExternalMapping,
)
from app.generation.models.station.station_model import Station
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.energy_systems.regional_district_regional_energy_system_model import (
    regional_district_regional_energy_system,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    restrict_equipment_group_query_to_current_version,
)
from app.refdata.models.energy_systems.regional_energy_system_model import (
    RegionalEnergySystem,
)
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem

_BUCKET_FIELDS = FUEL_MAIN_SUM_FIELDS + FUEL_EXTRA_SUM_FIELDS


def _norm(text: str | None) -> str:
    return (
        (text or "")
        .casefold()
        .replace("ё", "е")
        .replace("-", " ")
        .replace("  ", " ")
        .strip()
    )


def match_ues_slug(name: str | None) -> str | None:
    n = _norm(name)
    if not n or "не указано" in n or "титес" in n.replace("э", "е"):
        return None
    if "северо" in n and "запад" in n:
        return "severo-zapad"
    if "средн" in n and "волг" in n:
        return "srednyaya-volga"
    if n == "центр" or n.startswith("центр ") or "оэс центр" in n:
        return "centr"
    if n in {"юг", "оэс юга", "оэс юг"} or (n.startswith("юг") and "сибир" not in n):
        return "yug"
    if "урал" in n:
        return "ural"
    if "сибир" in n:
        return "sibir"
    if "восток" in n:
        return "vostok"
    return None


def match_special_slug(ues_name: str | None, res_name: str | None) -> str | None:
    blob = _norm(f"{ues_name or ''} {res_name or ''}")
    tites = "титес" in blob.replace("э", "е")
    if "норильск" in blob or (tites and "сибир" in blob):
        return "norilsk"
    if (
        (tites and "восток" in blob)
        or "изолир" in blob
        or "из.узл" in blob
        or "из узл" in blob
    ):
        return "isolated-dv"
    return None


def empty_fuel_bucket() -> dict[str, Decimal]:
    return {field: Decimal("0") for field in _BUCKET_FIELDS}


def _ved_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _distribute(
    buckets: dict[str, Any],
    ved: int | None,
    territory_slugs: set[str],
    values: dict[str, Decimal],
    cap_class: str | None = None,
) -> None:
    targets = ["vsego"]
    if ved in VED_INDUSTRY:
        targets.append("minen")
    elif ved in VED_INDUSTRIAL:
        targets.append("prompred")
    targets.extend(sorted(territory_slugs))
    for slug in targets:
        if cap_class:
            _add(buckets[slug][cap_class], values)
        else:
            _add(buckets[slug], values)


def _load_group_territory_slugs(group_ids: set[int]) -> dict[int, set[str]]:
    if not group_ids:
        return {}
    # Субъект может входить в несколько РЭС: такая связь не определяет территорию ГО.
    district_res = regional_district_regional_energy_system
    unique_subject_res = (
        db.session.query(
            district_res.c.regional_district_id,
            func.min(district_res.c.regional_energy_system_id).label("res_id"),
        )
        .group_by(district_res.c.regional_district_id)
        .having(func.count() == 1)
        .subquery()
    )
    group_unit = aliased(EnergyUnit)
    rows = (
        db.session.query(
            EquipmentGroup.id,
            group_unit.name,
            UnionEnergySystem.name,
            RegionalEnergySystem.name,
            EnergyUnit.name,
            UnionEnergySystemExternalMapping.external_nameoes,
            UnionEnergySystemExternalMapping.external_name,
            TerritoriesEnergyExternalMapping.external_name,
        )
        .select_from(EquipmentGroup)
        .outerjoin(group_unit, group_unit.id == EquipmentGroup.energy_unit_id)
        .outerjoin(EquipmentGroupSet, EquipmentGroupSet.equipment_group_id == EquipmentGroup.id)
        .outerjoin(
            EquipmentGroupSetStation,
            and_(
                EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id,
                EquipmentGroupSetStation.database_version_id.is_not_distinct_from(
                    EquipmentGroup.database_version_id
                ),
            ),
        )
        .outerjoin(
            Station,
            and_(
                Station.id == EquipmentGroupSetStation.station_id,
                Station.database_version_id.is_not_distinct_from(
                    EquipmentGroup.database_version_id
                ),
            ),
        )
        .outerjoin(EnergyUnit, EnergyUnit.id == Station.id_energy_unit)
        .outerjoin(
            unique_subject_res,
            unique_subject_res.c.regional_district_id
            == func.coalesce(EquipmentGroup.regional_district_id, Station.id_regional_district),
        )
        .outerjoin(
            RegionalEnergySystem,
            RegionalEnergySystem.id == func.coalesce(
                EquipmentGroup.regional_energy_system_id,
                Station.id_regional_energy_system,
                EnergyUnit.id_regional_energy_system,
                unique_subject_res.c.res_id,
            ),
        )
        .outerjoin(
            UnionEnergySystem,
            UnionEnergySystem.id == RegionalEnergySystem.id_union_energy_system,
        )
        .outerjoin(
            UnionEnergySystemExternalMapping,
            UnionEnergySystemExternalMapping.external_id == cast(EquipmentGroup.oes, String),
        )
        .outerjoin(
            TerritoriesEnergyExternalMapping,
            TerritoriesEnergyExternalMapping.external_id == cast(EquipmentGroup.obl, String),
        )
        .filter(EquipmentGroup.id.in_(group_ids))
        .all()
    )
    result = defaultdict(set)
    for group_id, group_unit_name, ues, res, unit, external_ues, external_name, subject in rows:
        # Николаевский столбец определяется только полем «Энергорайон» карточки ГО.
        if "николаев" in _norm(group_unit_name):
            result[group_id].add("nikolaevsky")
            continue
        slug = (
            match_special_slug(unit, None)
            or match_special_slug(external_ues, external_name)
            or match_special_slug(ues, res)
            or match_special_slug(subject, None)
            or match_ues_slug(ues)
            or match_ues_slug(external_ues)
        )
        if slug:
            result[group_id].add(slug)
    return result


def equipment_group_operating_clause(*, operating: bool = True):
    """d = 1 – действующая ТЭС; новые – d IS NULL или d ≠ 1."""
    if operating:
        return EquipmentGroup.d == 1
    return or_(EquipmentGroup.d.is_(None), EquipmentGroup.d != 1)


def _capacity_class_expr():
    """До 100 МВт включительно / более 100 МВт по Nуст группы."""
    return case(
        (
            or_(
                EquipmentGroupFuelParam.nust.is_(None),
                EquipmentGroupFuelParam.nust <= 100,
            ),
            "le100",
        ),
        else_="gt100",
    )


def empty_capacity_buckets() -> dict[str, dict[str, Decimal]]:
    return {"le100": empty_fuel_bucket(), "gt100": empty_fuel_bucket()}


def combine_capacity_buckets(
    by_class: dict[str, dict[str, Decimal]] | None,
) -> dict[str, Decimal]:
    combined = empty_fuel_bucket()
    if not by_class:
        return combined
    for bucket in by_class.values():
        _add(combined, bucket)
    return combined


def load_operating_tes_fuel_inputs(
    years: list[int],
    *,
    operating: bool = True,
    by_capacity: bool = False,
) -> dict[int, dict[str, Any]]:
    """year → territory_slug → поля топлива (тыс. т у.т. / млн кВтч / тыс. Гкал).

    «Всего» охватывает все участвующие группы, как «Россия, всего» в Топливе.
    Если by_capacity=True, значение территории – {le100, gt100} → bucket.
    """
    wanted = [int(y) for y in years if y is not None]
    if by_capacity:
        result: dict[int, dict[str, Any]] = {
            year: defaultdict(empty_capacity_buckets) for year in wanted
        }
    else:
        result = {year: defaultdict(empty_fuel_bucket) for year in wanted}
    if not wanted:
        return result
    rows = load_group_fuel_rows(wanted, operating=operating, by_capacity=by_capacity)
    main_n = len(FUEL_MAIN_SUM_FIELDS)
    offset = 4 if by_capacity else 3
    territory_slugs = _load_group_territory_slugs({row[2] for row in rows})
    for row in rows:
        year = int(row[0])
        ved = _ved_int(row[1])
        group_id = row[2]
        cap_class = str(row[3]) if by_capacity else None
        values: dict[str, Decimal] = {}
        for i, field in enumerate(FUEL_MAIN_SUM_FIELDS):
            values[field] = _to_decimal(row[offset + i]) or Decimal("0")
        for i, field in enumerate(FUEL_EXTRA_SUM_FIELDS):
            values[field] = _to_decimal(row[offset + main_n + i]) or Decimal("0")
        _distribute(
            result[year], ved, territory_slugs.get(group_id, set()), values, cap_class=cap_class
        )
    return {year: dict(buckets) for year, buckets in result.items()}


def load_group_fuel_rows(wanted, *, operating=None, by_capacity=False, fuel_scope=None):
    """Суммы по году, принадлежности и группе до распределения по территориям."""
    version_id = get_current_db_version_id()
    main_sums = [
        func.coalesce(func.sum(getattr(EquipmentGroupFuelParam, f)), 0)
        for f in FUEL_MAIN_SUM_FIELDS
    ]
    extra_sums = [
        func.coalesce(func.sum(getattr(EquipmentGroupExtraFuelParam, f)), 0)
        for f in FUEL_EXTRA_SUM_FIELDS
    ]
    cap_expr = _capacity_class_expr() if by_capacity else None
    select_cols = [
        EquipmentGroupFuelParam.year_number,
        EquipmentGroupFuelParam.ved,
        EquipmentGroup.id,
    ]
    if cap_expr is not None:
        select_cols.append(cap_expr.label("capacity_class"))
    select_cols.extend(main_sums)
    select_cols.extend(extra_sums)
    query = (
        db.session.query(*select_cols)
        .join(
            EquipmentGroup,
            EquipmentGroup.id == EquipmentGroupFuelParam.equipment_group_id,
        )
        .outerjoin(
            EquipmentGroupExtraFuelParam,
            and_(
                EquipmentGroupExtraFuelParam.equipment_group_id
                == EquipmentGroupFuelParam.equipment_group_id,
                EquipmentGroupExtraFuelParam.year_number
                == EquipmentGroupFuelParam.year_number,
                EquipmentGroupExtraFuelParam.database_version_id.is_not_distinct_from(
                    EquipmentGroupFuelParam.database_version_id
                ),
            ),
        )
        .filter(EquipmentGroupFuelParam.year_number.in_(wanted))
        # Тот же состав, что в «Россия, всего»: все группы с VED > 0,
        # независимо от наличия связи со станцией, но строго в своей версии.
        .filter(EquipmentGroupFuelParam.ved > 0)
        .filter(
            EquipmentGroupFuelParam.database_version_id.is_not_distinct_from(
                EquipmentGroup.database_version_id
            )
        )
    )
    if operating is not None:
        query = query.filter(equipment_group_operating_clause(operating=operating))
    if fuel_scope == "operating":
        query = query.filter(
            EquipmentGroup.d == 1, EquipmentGroup.r == 1,
            EquipmentGroupFuelParam.nust.is_not(None),
        )
    elif fuel_scope in ("new_lt100", "new_ge100"):
        query = query.filter(
            or_(
                and_(EquipmentGroup.d == 1, EquipmentGroup.r == 2),
                and_(EquipmentGroup.d.is_(None), EquipmentGroup.r.is_(None)),
            ),
            EquipmentGroupFuelParam.nust.is_not(None),
            EquipmentGroupFuelParam.nust < 100 if fuel_scope == "new_lt100"
            else EquipmentGroupFuelParam.nust >= 100,
        )
    elif fuel_scope is not None:
        raise ValueError("Неизвестный раздел сводки")
    query = restrict_equipment_group_query_to_current_version(query, version_id)
    group_cols = [
        EquipmentGroupFuelParam.year_number,
        EquipmentGroupFuelParam.ved,
        EquipmentGroup.id,
    ]
    if cap_expr is not None:
        group_cols.append(cap_expr)
    query = query.group_by(*group_cols)
    return query.all()


def _add(target: dict[str, Decimal], values: dict[str, Decimal]) -> None:
    for field, amount in values.items():
        target[field] = target.get(field, Decimal("0")) + amount


def fuel_amount_for_key(bucket: dict[str, Decimal] | None, fuel_key: str) -> Decimal | None:
    if not bucket:
        return None
    field = FUEL_PARAM_FIELDS.get(fuel_key)
    if not field:
        return None
    value = bucket.get(field)
    if value is None or value == 0:
        return None
    return value


def apply_input_override_to_bucket(bucket: dict[str, Decimal], row_key: str, value: Decimal | None) -> None:
    if value is None:
        return
    top_field = TOP_INPUT_FIELD.get(row_key)
    if top_field == "e":
        bucket["e"] = value * Decimal("1000")
        return
    if top_field:
        bucket[top_field] = value
        return
    field = FUEL_PARAM_FIELDS.get(row_key)
    if field:
        bucket[field] = value


def bucket_field_amount(bucket: dict[str, Decimal] | None, field: str) -> Decimal | None:
    if not bucket or not field:
        return None
    value = bucket.get(field)
    if value is None or value == 0:
        return None
    return value


# На странице топлива: e – млн кВтч. В макете экологии – млрд.кВтч.
_TOP_INPUT_DIVISOR = {
    "ee_generation": Decimal("1000"),
}


def bucket_top_input_amount(bucket: dict[str, Decimal] | None, row_key: str) -> Decimal | None:
    field = TOP_INPUT_FIELD.get(row_key)
    if not field:
        return None
    value = bucket_field_amount(bucket, field)
    if value is None:
        return None
    divisor = _TOP_INPUT_DIVISOR.get(row_key)
    if divisor:
        return value / divisor
    return value


def _collapse_indent(attr: str, collapse_under: dict[str, str]) -> int:
    indent = 0
    cur = attr
    seen: set[str] = set()
    while cur in collapse_under and cur not in seen:
        seen.add(cur)
        cur = collapse_under[cur]
        indent += 1
    return indent


def get_fuel_module_consumption_row_specs() -> list[dict[str, Any]]:
    """Строки раздела «Расход топлива, тыс. т у.т.» как на /fuel/calculation/equipment_group_fuel_params_edit_data."""
    from app.ecology.services.operating_tes_constants import KIND_TOTAL, KIND_VALUE
    from app.fuel.services.calculation.fuel_calculation_edit_data_services import (
        assemble_fuel_edit_data_param_columns,
        build_fuel_param_columns_hierarchy,
    )

    full_columns, _extra = assemble_fuel_edit_data_param_columns()
    hier = build_fuel_param_columns_hierarchy(full_columns)
    collapse_under = hier.get("collapse_under") or {}
    group_parents = set(hier.get("group_parents") or [])
    specs: list[dict[str, Any]] = []
    started = False
    for attr, label, _is_numeric in hier.get("fuel_param_columns") or full_columns:
        if attr == "b":
            started = True
            specs.append(
                {
                    "key": "b",
                    "label": "Расход топлива",
                    "unit": "тыс. т у.т.",
                    "indent": 0,
                    "kind": KIND_TOTAL,
                }
            )
            continue
        if not started:
            continue
        indent = _collapse_indent(attr, collapse_under)
        specs.append(
            {
                "key": attr,
                "label": label,
                "indent": indent,
                "kind": KIND_TOTAL if attr in group_parents else KIND_VALUE,
            }
        )
    return specs
