# -*- coding: utf-8 -*-
"""
Сервисы страницы «Расчёт» (/fuel/calculation) по вкладкам этапов:

- coefficient — «Коэфф»
- distribution — «Распред»
- fuel — «Топливо»
"""
from app.fuel.services.calculation.coefficient import (  # noqa: F401
    CoeffStageRunResult,
    FuelCoefficientCalculationService,
    d0,
)
from app.fuel.services.calculation.distribution import (  # noqa: F401
    DistributionParameterCalculationService,
    DistributionRunResult,
    run_distribution_parameter_batch,
)
from app.fuel.services.calculation.fuel import run_fuel_stage_batch  # noqa: F401
