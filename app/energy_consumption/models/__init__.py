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
from app.energy_consumption.models.formula_text import (  # noqa: F401
    energy_consumption_summary_formula_text_model,
)
from app.economics.models import (  # noqa: F401 — таблицы «Экономика»
    federal_district_eat_consumption_parameter_model,
    russia_federation_consumption_parameter_model,
    consumption_formula_text_model,
    federal_district_accum_fixed_capital_parameter_model,
    russia_federation_accum_fixed_capital_parameter_model,
    accum_fixed_capital_formula_text_model,
    federal_district_product_output_parameter_model,
    russia_federation_product_output_parameter_model,
    product_output_formula_text_model,
    federal_district_population_parameter_model,
)
