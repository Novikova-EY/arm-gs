# -*- coding: utf-8 -*-
# Регистрация таблиц потребления электроэнергии (схема gs_ec).
from app.energy_consumption.models.energy_systems import (  # noqa: F401
    centralized_zone_energy_consumption_parameter_model,
    ees_energy_consumption_parameter_model,
    ees_russia_energy_consumption_parameter_model,
    energy_area_energy_consumption_parameter_model,
    energy_system_type_energy_consumption_parameter_model,
    energy_unit_energy_consumption_parameter_model,
    energy_zone_energy_consumption_parameter_model,
    regional_energy_system_energy_consumption_parameter_model,
    synchronous_area_energy_consumption_parameter_model,
    union_energy_system_energy_consumption_parameter_model,
)
from app.energy_consumption.models.territories import (  # noqa: F401
    federal_district_energy_consumption_parameter_model,
    regional_district_energy_consumption_parameter_model,
    russia_federation_energy_consumption_parameter_model,
)
