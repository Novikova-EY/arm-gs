# -*- coding: utf-8 -*-
# Зеркало регистрации gs_pd: те же модули, что и app.power_demand.models (без дубля таблиц).
from app.power_demand.models.energy_systems import (  # noqa: F401
    centralized_zone_demand_parameter_model,
    ees_demand_parameter_model,
    ees_russia_demand_parameter_model,
    ees_russia_with_nt_demand_parameter_model,
    energy_area_demand_parameter_model,
    energy_system_type_demand_parameter_model,
    energy_unit_demand_parameter_model,
    energy_zone_demand_parameter_model,
    regional_energy_system_demand_parameter_model,
    synchronous_area_demand_parameter_model,
    union_energy_system_demand_parameter_model,
)
from app.power_demand.models.territories import (  # noqa: F401
    federal_district_demand_parameter_model,
    regional_district_demand_parameter_model,
    russia_federation_demand_parameter_model,
    russia_federation_with_nt_demand_parameter_model,
)
