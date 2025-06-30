from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Tuple
from sqlalchemy.sql.elements import Label
from sqlalchemy import Table, func
from sqlalchemy.orm import Query

from app.services.station_services.help_services import (
    rounded_decimal,
)

from app import db
from app.models import (
    Station,
    Machine,
    MachinePower,
    StationType,
    FuelType,
    TesType,
    TesMachineType,
    MachineFuel,
    Fuel,
    MachineTesType,
    EnergyUnit,
    RegionalDistrict,
    FederalDistrict,
    RegionalEnergySystem,
    UnionEnergySystem,
    EnergySystemType,
)

MODEL_REGISTRY: Dict[str, Any] = {
    "station": Station,
    "machine": Machine,
    "machinepower": MachinePower,
    "energyunit": EnergyUnit,
    "regionaldistrict": RegionalDistrict,
    "federaldistrict": FederalDistrict,
    "regionalenergysystem": RegionalEnergySystem,
    "unionenergysystem": UnionEnergySystem,
    "energysystemtype": EnergySystemType,
}

JOIN_CHAINS: Dict[str, Dict[str, List[Tuple[Any, ...]]]] = {
    "energy_units": {
        "join_chain": [
            ("station", "id_energy_unit", "energyunit"),
        ]
    },
    "regional_districts": {
        "join_chain": [
            ("station", "id_regional_district", "regionaldistrict"),
        ]
    },
    "federal_districts": {
        "join_chain": [
            ("station", "id_regional_district", "regionaldistrict"),
            ("regionaldistrict", "id_federal_district", "federaldistrict"),
        ]
    },
    "regional_energy_systems": {
        "join_chain": [
            ("station", "id_regional_district", "regionaldistrict"),
            ("regionaldistrict", "id", "regional_district_regional_energy_system", "regional_district_id"),
            ("regional_energy_system_id", "regionalenergysystem"),
        ]
    },
    "union_energy_systems": {
        "join_chain": [
            ("station", "id_regional_district", "regionaldistrict"),
            ("regionaldistrict", "id", "regional_district_regional_energy_system", "regional_district_id"),
            ("regional_energy_system_id", "regionalenergysystem"),
            ("id_union_energy_system", "unionenergysystem"),
        ]
    },
    "energy_system_types": {
        "join_chain": [
            ("station", "id_regional_district", "regionaldistrict"),
            ("regionaldistrict", "id", "regional_district_regional_energy_system", "regional_district_id"),
            ("regional_energy_system_id", "regionalenergysystem"),
            ("id_union_energy_system", "unionenergysystem"),
            ("id_energy_system_type", "energysystemtype"),
        ]
    },
    "total_energy_system_types": {
        "join_chain": [
            ("station", "id_regional_district", "regionaldistrict"),
            ("regionaldistrict", "id", "regional_district_regional_energy_system", "regional_district_id"),
            ("regional_energy_system_id", "regionalenergysystem"),
            ("id_union_energy_system", "unionenergysystem"),
            ("id_energy_system_type", "energysystemtype"),
        ]
    },
}


def _apply_extra_joins(query: Query, extra_columns: Iterable[Any]) -> Query:
    """Добавляет корректные LEFT JOIN-ы для нужных справочников."""
    for col in extra_columns:
        base_col = col.element if isinstance(col, Label) else col
        try:
            tbl = base_col.class_
        except AttributeError:
            continue

        if tbl is StationType:
            query = query.outerjoin(StationType, StationType.id == Machine.id_station_type)

        elif tbl is TesType:
            query = (
                query.outerjoin(MachineTesType, MachineTesType.id_machine == Machine.id)
                     .outerjoin(TesType, TesType.id == MachineTesType.id_tes_type)
            )

        elif tbl is TesMachineType:
            query = query.outerjoin(TesMachineType, TesMachineType.id == Machine.id_tes_machine_type)

        elif tbl is FuelType:
            query = (
                query.outerjoin(MachineFuel, MachineFuel.id_machine == Machine.id)
                     .outerjoin(Fuel, Fuel.id == MachineFuel.id_fuel)
                     .outerjoin(FuelType, FuelType.id == Fuel.id_fuel_type)
            )

    return query


def _last_model_from_chain(chain: List[Tuple[Any, ...]]):
    step = chain[-1]
    if len(step) == 2:
        return MODEL_REGISTRY[step[1]]
    if len(step) == 3:
        return MODEL_REGISTRY[step[2]]
    raise ValueError("Не удалось определить конечную модель из join_chain")


def aggregate_by_all_generic(
    pagination: dict[str, Any],
    rounding_digits: int | None,
    start_year: int,
    end_year: int,
    join_info: dict[str, Any],
    level_prefix: str,
) -> dict[str, Any]:
    join_chain = join_info["join_chain"]
    last_model = _last_model_from_chain(join_chain)

    grouping_columns = [
        last_model.id,
        StationType.id,
        TesType.id,
        TesMachineType.id,
        FuelType.id,
    ]



    query = (
        db.session.query(
            MachinePower.year_number.label("year"),
            last_model.id.label("gid"),
            StationType.id.label("stid"),
            TesType.id.label("ttid"),
            TesMachineType.id.label("tmtid"),
            FuelType.id.label("ftid"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_ogr).label("p_ogr"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .join(Machine, MachinePower.id_machine == Machine.id)
        .join(Station, Machine.id_station == Station.id)
    )

    # Применяем JOIN-цепочку
    prev_model: Any = Station
    i = 0
    while i < len(join_chain):
        step = join_chain[i]
        if len(step) == 4:
            local_table, local_key, pivot_table, pivot_local = step
            pivot_alias = Table(pivot_table, db.metadata, autoload_with=db.engine)
            local_model = MODEL_REGISTRY[local_table]
            query = query.join(pivot_alias, getattr(local_model, local_key) == pivot_alias.c[pivot_local])
            i += 1
            next_step = join_chain[i]
            pivot_fk = next_step[-2] if len(next_step) == 3 else next_step[0]
            target_alias = next_step[-1]
            target_model = MODEL_REGISTRY[target_alias]
            query = query.join(target_model, pivot_alias.c[pivot_fk] == target_model.id)
            prev_model = target_model
        elif len(step) == 3:
            local_table, local_key, remote_alias = step
            local_model = MODEL_REGISTRY[local_table]
            remote_model = MODEL_REGISTRY[remote_alias]
            query = query.join(remote_model, getattr(local_model, local_key) == remote_model.id)
            prev_model = remote_model
        elif len(step) == 2:
            local_key, remote_alias = step
            remote_model = MODEL_REGISTRY[remote_alias]
            query = query.join(remote_model, getattr(prev_model, local_key) == remote_model.id)
            prev_model = remote_model
        else:
            raise ValueError(f"Unsupported join step: {step}")
        i += 1

    query = _apply_extra_joins(query, grouping_columns)
    query = query.filter(MachinePower.year_number.between(start_year, end_year))

    if pagination.get("machine_ids"):
        query = query.filter(Machine.id.in_(pagination["machine_ids"]))

    query = query.group_by(MachinePower.year_number, *grouping_columns)
    rows = query.all()
    print(f"[aggregate] LEVEL: {level_prefix} — Rows fetched: {len(rows)}")
    
    result: Dict[str, Any] = {}
    keys_defs = {
        "": lambda gid, stid, ttid, tmtid, ftid: (gid,),
        "by_station_types": lambda gid, stid, ttid, tmtid, ftid: (gid, stid or -1),
        "by_station_types_with_fuel": lambda gid, stid, ttid, tmtid, ftid: (gid, stid or -1, ftid or -1),
        "by_tes_types": lambda gid, stid, ttid, tmtid, ftid: (gid, ttid or -1),
        "by_tes_types_with_fuel": lambda gid, stid, ttid, tmtid, ftid: (gid, ttid or -1, ftid or -1),
        "by_tes_machine_types": lambda gid, stid, ttid, tmtid, ftid: (gid, tmtid or -1),
        "by_tes_machine_types_with_fuel": lambda gid, stid, ttid, tmtid, ftid: (gid, tmtid or -1, ftid or -1),
    }

    for suffix in keys_defs:
        prefix = f"{level_prefix}_{suffix}" if suffix else level_prefix
        result[f"{prefix}_yearly_p_ust"] = defaultdict(lambda: defaultdict(Decimal))
        result[f"{prefix}_yearly_p_ogr"] = defaultdict(lambda: defaultdict(Decimal))
        result[f"{prefix}_yearly_p_rasp"] = defaultdict(lambda: defaultdict(Decimal))

    for row in rows:
        year = int(row.year)
        gid, stid, ttid, tmtid, ftid = row.gid, row.stid, row.ttid, row.tmtid, row.ftid
        for suffix, key_fn in keys_defs.items():
            group_key = key_fn(gid, stid, ttid, tmtid, ftid)
            prefix = f"{level_prefix}_{suffix}" if suffix else level_prefix
            result[f"{prefix}_yearly_p_ust"][group_key][year] += rounded_decimal(row.p_ust, rounding_digits) or Decimal(0)
            result[f"{prefix}_yearly_p_ogr"][group_key][year] += rounded_decimal(row.p_ogr, rounding_digits) or Decimal(0)
            result[f"{prefix}_yearly_p_rasp"][group_key][year] += rounded_decimal(row.p_rasp, rounding_digits) or Decimal(0)

    return result

