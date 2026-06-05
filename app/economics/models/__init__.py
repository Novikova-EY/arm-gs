# -*- coding: utf-8 -*-
# Модели раздела «Экономика» (таблицы схемы gs_ekp).
from app.economics.models import (  # noqa: F401
    federal_district_accum_fixed_capital_parameter_model,
    federal_district_eat_consumption_parameter_model,
    federal_district_product_output_parameter_model,
    federal_district_population_parameter_model,
    federal_district_accum_monetary_income_parameter_model,
    russia_federation_accum_fixed_capital_parameter_model,
    russia_federation_consumption_parameter_model,
    russia_federation_product_output_parameter_model,
)
from app.economics.models.formula_text import (  # noqa: F401
    accum_fixed_capital_formula_text_model,
    consumption_formula_text_model,
    product_output_formula_text_model,
)
