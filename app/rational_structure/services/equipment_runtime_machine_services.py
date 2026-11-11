"""Источники строк наработки: агрегаты ТЭС, их карточки и годовые данные."""
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.common.services.excel_numeric_cell import parse_excel_numeric
from app.common.services.help_services import rounded_decimal
from app.extensions import db
from app.fuel.services.calculation.fuel_calculation_edit_data_services import build_fuel_nazvl_to_name_map
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_name_model import MachineName
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.generation.models.pgu_machine.pgu_machine_name_model import PGUMachineName
from app.generation.models.pgu_machine.pgu_machine_power_model import PGUMachinePower
from app.generation.models.station.station_model import Station
from app.rational_structure.models import EquipmentTechnicalCharacteristic, TechnicalInspectionCode
from app.rational_structure.services.equipment_runtime_columns import RUNTIME_CHARACTERISTIC_FIELDS
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroupType
from app.refdata.models.territories.regional_district_model import RegionalDistrict

# Крупные виды топлива из «Расход топлива, всего (B)». Марки угля входят в UGOL,
# поэтому повторно с газом/мазутом их не сравниваем.
MAIN_FUEL_FIELDS = ("gaz", "isk_gaz", "mazut", "torf", "slan", "proch", "ugol")


def main_fuel(params):
    if params is None:
        return None
    present = [(field, getattr(params, field)) for field in MAIN_FUEL_FIELDS
               if getattr(params, field) is not None and getattr(params, field) > 0]
    return max(present, key=lambda item: item[1])[0].upper() if present else None


def _group_data(version_id):
    groups = {group.id: group for group in db.session.scalars(
        select(EquipmentGroup).where(EquipmentGroup.database_version_id == version_id))}
    by_pair, labels = defaultdict(set), defaultdict(set)
    statement = (select(EquipmentGroupSet.equipment_group_id, EquipmentGroupSetStation.station_id,
                        EquipmentGroupSetStation.equipment_group_type_id, EquipmentGroupType.name)
                 .select_from(EquipmentGroupSet)
                 .join(EquipmentGroupSetStation,
                       EquipmentGroupSetStation.id == EquipmentGroupSet.equipment_group_set_station_id)
                 .outerjoin(EquipmentGroupType,
                            EquipmentGroupType.id == EquipmentGroupSetStation.equipment_group_type_id)
                 .where(EquipmentGroupSetStation.database_version_id == version_id))
    for group_id, station_id, type_id, label in db.session.execute(statement):
        if group_id in groups:
            by_pair[station_id, type_id].add(group_id)
            if label:
                labels[group_id, station_id].add(label)
    return groups, by_pair, labels


def _remaining_double_resource(characteristic, year):
    if characteristic is None:
        return None
    resource = parse_excel_numeric(characteristic.standard_service_life)
    if resource is None:
        return None
    resource = Decimal(str(resource))
    if resource > 100:
        total = characteristic.operating_hours_total
        return max(2 * resource - total, 0) if total is not None else None
    commissioning_year = characteristic.commissioning_year
    return commissioning_year + 2 * resource - year if commissioning_year is not None else None


def _resource_dismantling_year(characteristic, values, year):
    remaining = values["AO"]
    if remaining is None:
        return 0
    resource = parse_excel_numeric(characteristic.standard_service_life)
    if resource > 100:
        average = values["AN"]
        if not average:
            return 0
        return year + int(rounded_decimal(remaining / average, digits=0))
    return year + remaining


def _first_resource_year(characteristic, average, year):
    if characteristic is None:
        return None
    if average == 0:
        return characteristic.expected_service_life_year
    resource = parse_excel_numeric(characteristic.standard_service_life)
    if resource is None:
        return None
    resource = Decimal(str(resource))
    if resource > 100:
        total = characteristic.operating_hours_total
        if total is None:
            return None
        if total >= resource:
            return 0
        return year + int(rounded_decimal((resource - total) / average, digits=0))
    commissioning_year = characteristic.commissioning_year
    return commissioning_year + resource if commissioning_year is not None else None


def _modernization_year(characteristic, values, year, general_scheme_end_year):
    first_resource = values["AQ"]
    if first_resource is None:
        return None
    if 0 < first_resource < year + 1:
        return 0
    supply = parse_excel_numeric(values.get("AU") or 0)
    if supply is None:
        return None
    if supply == 0:
        if general_scheme_end_year is None:
            return None
        return int(rounded_decimal(first_resource, digits=0)) if first_resource <= general_scheme_end_year else 0
    if characteristic is None or characteristic.commissioning_year is None:
        return None
    return 0 if characteristic.commissioning_year == supply else supply


def _modernization_sipr_year(values, sipr_end_year):
    modernization = parse_excel_numeric(values.get("AR"))
    if modernization is None or modernization <= 0:
        return modernization
    supply = parse_excel_numeric(values.get("AU")) or 0
    if supply != 0:
        return modernization
    if sipr_end_year is None:
        return None
    return max(modernization, sipr_end_year + 1)


def _dismantling_years(characteristic, values, is_coal, year, general_scheme_end_year, sipr_end_year):
    scheduled = values["AT"] or 0
    if is_coal is None:
        coal, gas = None, None
    elif is_coal:
        gas = 0
        if scheduled > 0:
            coal = scheduled
        elif characteristic is None or characteristic.commissioning_year is None or general_scheme_end_year is None:
            coal = None
        else:
            coal_year = characteristic.commissioning_year + 70
            coal = coal_year if coal_year <= general_scheme_end_year else 0
    else:
        coal = 0
        resource_year = values["AP"]
        if scheduled > 0:
            gas = scheduled
        elif resource_year <= 0:
            gas = 0
        elif general_scheme_end_year is None:
            gas = None
        else:
            gas = resource_year if resource_year <= general_scheme_end_year else 0
    if scheduled > 0:
        total = scheduled
    elif coal is None or gas is None:
        total = None
    elif coal > 0 or gas > 0:
        total = coal + gas
        if total < year + 1:
            total = sipr_end_year + 1 if sipr_end_year is not None else None
    else:
        total = 0
    return {"AW": coal, "AX": gas, "AY": total}


def _dismantling_transfers(values, general_scheme_end_year, sipr_end_year):
    total = values["AY"]
    supply = values["AU"] or 0
    if total is not None and total > 0 and supply > 0:
        if general_scheme_end_year is None:
            transferred = None
        else:
            transferred = supply + 15 if supply + 15 <= general_scheme_end_year else 0
    else:
        transferred = total
    scheduled = values["AT"] or 0
    if transferred is None or transferred <= 0 or scheduled != 0:
        sipr = transferred
    elif sipr_end_year is None:
        sipr = None
    else:
        sipr = max(transferred, sipr_end_year + 1)
    return {"AZ": transferred, "BA": sipr}


def _dismantling_without_modernization(values, sipr_end_year):
    dismantling = parse_excel_numeric(values.get("BA"))
    if dismantling is None:
        return None
    if dismantling <= 0:
        return dismantling
    modernization = values["AS"] or 0
    if modernization > 0:
        if sipr_end_year is None:
            return None
        if modernization > sipr_end_year and dismantling > sipr_end_year:
            return 0
    total = values["AY"]
    if total is None:
        return None
    return total if dismantling < total else dismantling


def _exceeded_double_resources(characteristic, is_coal, year):
    commissioning_year = characteristic.commissioning_year if characteristic is not None else None
    if is_coal is False:
        coal = "no"
    elif is_coal is None or commissioning_year is None:
        coal = None
    else:
        coal = "yes" if commissioning_year + 70 <= year else "no"
    resource = parse_excel_numeric(characteristic.standard_service_life) if characteristic is not None else None
    if resource is None:
        gas = None
    elif resource > 100:
        total = characteristic.operating_hours_total
        if is_coal is True:
            gas = "no"
        elif is_coal is None or total is None:
            gas = None
        else:
            gas = "yes" if total >= 2 * Decimal(str(resource)) else "no"
    elif commissioning_year is None:
        gas = None
    else:
        gas = "yes" if commissioning_year + 2 * Decimal(str(resource)) <= year else "no"
    return {"BD": coal, "BF": gas}


def load_runtime_machine_rows(version_id, year, general_scheme_end_year, sipr_end_year):
    if version_id is None:
        return []
    machines = list(db.session.scalars(
        select(Machine)
        .join(Station, Station.id == Machine.id_station)
        .join(StationType, StationType.id == Station.id_station_type)
        .where(Machine.database_version_id == version_id, Station.database_version_id == version_id,
               StationType.name == "ТЭС")
        .options(joinedload(Machine.machine_station).joinedload(Station.regional_district)
                 .joinedload(RegionalDistrict.energy_zone), joinedload(Machine.gen_company),
                 joinedload(Machine.machine_fuel_param))
        .order_by(Station.name, Machine.machine_number, Machine.id)))
    if not machines:
        return []
    machine_ids = {machine.id for machine in machines}
    parts = defaultdict(list)
    for part in db.session.scalars(select(PGUMachine).where(
            PGUMachine.database_version_id == version_id, PGUMachine.id_parent_machine.in_(machine_ids))
            .order_by(PGUMachine.machine_number, PGUMachine.id)):
        parts[part.id_parent_machine].append(part)
    powers = dict(db.session.execute(select(MachinePower.id_machine, MachinePower.p_ust).where(
        MachinePower.database_version_id == version_id, MachinePower.year_number == year)).all())
    part_powers = dict(db.session.execute(select(PGUMachinePower.id_pgu_machine, PGUMachinePower.p_ust).where(
        PGUMachinePower.database_version_id == version_id, PGUMachinePower.year_number == year)).all())
    names = dict(db.session.execute(select(MachineName.id_machine, MachineName.name).where(
        MachineName.database_version_id == version_id, MachineName.year_number == year)).all())
    part_names = dict(db.session.execute(select(PGUMachineName.id_pgu_machine, PGUMachineName.name).where(
        PGUMachineName.database_version_id == version_id, PGUMachineName.year_number == year)).all())
    codes = defaultdict(set)
    for code in db.session.scalars(select(TechnicalInspectionCode).where(
            TechnicalInspectionCode.database_version_id == version_id)):
        if code.equipment_code.strip():
            codes[code.machine_id, code.pgu_machine_id].add(code.equipment_code.strip())
    characteristics = list(db.session.scalars(select(EquipmentTechnicalCharacteristic).where(
        EquipmentTechnicalCharacteristic.database_version_id == version_id,
        EquipmentTechnicalCharacteristic.equipment_type.in_(("steam", "gas")))))
    kinds = defaultdict(set)
    kind_years = {}
    annual_hours = defaultdict(list)
    selected_characteristics = defaultdict(list)
    for characteristic in characteristics:
        code = characteristic.equipment_code.strip()
        if characteristic.report_year == year:
            selected_characteristics[code].append(characteristic)
        if year - 2 <= characteristic.report_year <= year and characteristic.operating_hours_year not in (None, 0):
            annual_hours[code].append(characteristic.operating_hours_year)
        if characteristic.match_status == "matched" and characteristic.machine_id in machine_ids:
            codes[characteristic.machine_id, characteristic.pgu_machine_id].add(code)
        priority = (characteristic.report_year == year, characteristic.report_year)
        if code not in kind_years or priority > kind_years[code]:
            kind_years[code] = priority
            kinds[code].clear()
        if priority == kind_years[code]:
            kinds[code].add(characteristic.equipment_kind or characteristic.equipment_type_label)
    groups, by_pair, group_labels = _group_data(version_id)
    fuel_names = build_fuel_nazvl_to_name_map(version_id)
    fuel_codes = {params.equipment_group_id: main_fuel(params) for params in db.session.scalars(
        select(EquipmentGroupFuelParam).where(EquipmentGroupFuelParam.database_version_id == version_id,
                                             EquipmentGroupFuelParam.year_number == year))}
    fuels = {group_id: fuel_names.get((code or "").casefold()) for group_id, code in fuel_codes.items()}
    rows = []
    for machine in machines:
        station = machine.machine_station
        region = station.regional_district
        group_id = None
        binding = machine.machine_fuel_param
        if binding and binding.database_version_id == version_id and binding.equipment_group_id:
            group_id = binding.equipment_group_id if binding.equipment_group_id in groups else None
        else:
            candidates = by_pair[station.id, machine.id_equipment_group]
            if len(candidates) == 1:
                group_id = next(iter(candidates))
        common = {"A": region.energy_zone.number if region and region.energy_zone else None,
                  "B": region.name if region else None,
                  "F": machine.gen_company.name if machine.gen_company else None,
                  "G": station.name,
                  "K": ", ".join(sorted(group_labels[group_id, station.id])) or None,
                  "AM": fuels.get(group_id)}
        outcome = (machine.relabing_outcome or "").strip()
        for equipment in parts[machine.id] or (machine,):
            part_id = equipment.id if isinstance(equipment, PGUMachine) else None
            equipment_codes = sorted(codes[machine.id, part_id]) or [None]
            for code in equipment_codes:
                values = {}
                characteristic = selected_characteristics[code][0] if len(selected_characteristics[code]) == 1 else None
                values.update({key: getattr(characteristic, field) if characteristic is not None else None
                               for key, field in RUNTIME_CHARACTERISTIC_FIELDS.items()})
                modernization_years = [value for value in (
                    equipment.date_modernization_power_change_expected,
                    equipment.date_modernization_no_power_change_expected) if value is not None]
                values.update(common, C=code, D=year, E=", ".join(sorted(kinds[code])) or None,
                              H=equipment.machine_number,
                              L=(part_names if part_id else names).get(equipment.id) or equipment.machine_name,
                              N=(part_powers if part_id else powers).get(equipment.id),
                              AN=sum(annual_hours[code]) / len(annual_hours[code]) if annual_hours[code] else 0,
                              AO=_remaining_double_resource(characteristic, year),
                              planned_modernization_year=min(modernization_years) if modernization_years else None,
                              AT=equipment.date_decompressing_expected if outcome == "окончательный вывод" else None,
                              AU=equipment.date_exploitation_expected if outcome in ("", "не указано", "новый ввод") else None,
                              AV=equipment.date_decompressing_expected if outcome == "замена" else None)
                values["AP"] = _resource_dismantling_year(characteristic, values, year)
                values["AQ"] = _first_resource_year(characteristic, values["AN"], year)
                values["AR"] = _modernization_year(characteristic, values, year, general_scheme_end_year)
                values["AS"] = _modernization_sipr_year(values, sipr_end_year)
                fuel_code = fuel_codes.get(group_id)
                is_coal = fuel_code == "UGOL" if fuel_code else None
                values.update(_dismantling_years(
                    characteristic, values, is_coal, year, general_scheme_end_year, sipr_end_year))
                values.update(_dismantling_transfers(values, general_scheme_end_year, sipr_end_year))
                values["BC"] = _dismantling_without_modernization(values, sipr_end_year)
                values.update(_exceeded_double_resources(characteristic, is_coal, year))
                rows.append({"station_id": station.id, "machine_id": machine.id, "pgu_machine_id": part_id,
                             "energy_zone_id": region.id_energy_zone if region else None,
                             "technology_type_id": machine.id_technology_type,
                             "equipment_group_type_id": machine.id_equipment_group,
                             "fuel_code": fuel_code,
                             "parent_machine_number": machine.machine_number,
                             "parent_machine_name": names.get(machine.id) or machine.machine_name,
                             "values": values, "formulas": {}, "errors": []})
    return rows
