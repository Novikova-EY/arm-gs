# -*- coding: utf-8 -*-
# Модели электроёмкости (долгосрочный спрос, схема gs_ec).
from app.energy_consumption.long_term_consumption.models import (  # noqa: F401
    federal_district_electrical_intensity_year_parameter_model,
    russia_federation_electrical_intensity_year_parameter_model,
    federal_district_electrical_intensity_coefficient_model,
    russia_federation_electrical_intensity_coefficient_model,
    federal_district_population_consumption_coefficient_model,
    federal_district_population_consumption_year_parameter_model,
)
from app.energy_consumption.long_term_consumption.models.formula_text import (  # noqa: F401
    electrical_intensity_formula_text_model,
)
