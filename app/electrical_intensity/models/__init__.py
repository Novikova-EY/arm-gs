# -*- coding: utf-8 -*-
# Модели электроёмкости (долгосрочный спрос, схема gs_ei).
from app.electrical_intensity.models import (  # noqa: F401
    federal_district_electrical_intensity_year_parameter_model,
    russia_federation_electrical_intensity_year_parameter_model,
    federal_district_electrical_intensity_coefficient_model,
    russia_federation_electrical_intensity_coefficient_model,
    federal_district_population_consumption_coefficient_model,
    federal_district_population_consumption_year_parameter_model,
    federal_district_fd_total_consumption_coefficient_model,
)
from app.electrical_intensity.models.formula_text import (  # noqa: F401
    electrical_intensity_formula_text_model,
)
