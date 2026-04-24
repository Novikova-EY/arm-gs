# -*- coding: utf-8 -*-
"""Тонкая обёртка для UI этапа «Топливо»."""
from __future__ import annotations

from .fuel_stage_services import FuelStageService


def run_fuel_stage_batch(dp_id: int):
    """Запуск этапа «Топливо» по параметру распределения."""
    return FuelStageService().run_for_distribution_parameter(dp_id)
