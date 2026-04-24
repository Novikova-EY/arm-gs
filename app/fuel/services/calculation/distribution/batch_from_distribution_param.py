# -*- coding: utf-8 -*-
"""
Тонкая обёртка для UI этапа «Распред»: пакетный пересчёт по параметру распределения.
"""
from __future__ import annotations

from .distribution_parameter_calculation_services import DistributionParameterCalculationService


def run_distribution_parameter_batch(dp_id: int):
    """
    Запускает calculate_from_distribution_param для параметра распределения.

    Возвращает (run, n_ok, n_err) для flash-сообщений.
    """
    run = DistributionParameterCalculationService().calculate_from_distribution_param(
        distribution_param_id=dp_id,
    )
    br = run.batch_result
    n_ok = br.success_count if br else 0
    n_err = br.error_count if br else 0
    return run, n_ok, n_err
