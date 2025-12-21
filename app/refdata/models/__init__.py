# -*- coding: utf-8 -*-
# Регистрируем ВСЕ модели refdata в одном месте, чтобы they were mapped.

# --- Территории ---
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.territories.federal_district_model import FederalDistrict

# --- Энергосистемы ---
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.regional_district_regional_energy_system_model import regional_district_regional_energy_system
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.energy_systems.energy_area_model import EnergyArea
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea

# --- Прочие справочники ---
from app.refdata.models.refdata_for_stations.condition_type_model import ConditionType
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroup
from app.refdata.models.refdata_for_stations.machine.machine_type_model import MachineType
from app.refdata.models.refdata_for_stations.machine.pgu_tes_machine_type_model import PGUTesMachineType
from app.refdata.models.refdata_for_stations.machine.tes_machine_type_model import TesMachineType
from app.refdata.models.refdata_for_stations.machine.tes_type_model import TesType

# --- Годы ---
from app.refdata.models.years.year_model import Year
from app.refdata.models.years.year_feature_model import YearFeature
from app.refdata.models.years.year_service_model import YearService