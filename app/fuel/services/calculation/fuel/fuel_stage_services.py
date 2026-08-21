# -*- coding: utf-8 -*-
"""
Этап «Топливо» для страницы /fuel/calculation.

В отличие от старого прямого batch-вызова, сервис:
- проверяет, что перед запуском выполнен «Распред.»
  (ΣE по строкам, которые Распред пишет, близка к целевому Ераспред);
- запускает пакетный расчёт топлива по уже распределённым строкам;
- возвращает сводку для flash/UI.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session, joinedload

from app.extensions import db
from app.fuel.models.fue_distribution_parameter_model import DistributionParameter
from app.fuel.services.calculation.distribution.distribution_stage_services import (
    D03,
    DistributionStageService,
    d0,
)
from app.fuel.services.calculation.equipment_group_selection import (
    participating_group_ids_for_year,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_batch_calculation_services import (
    BatchCalculationResult,
    EquipmentGroupFuelBatchCalculationService,
)
from app.fuel.services.equipment_groups.composite_calc_consistency_check_services import (
    find_composite_energy_level_issues,
    flash_text_for_composite_energy_level_issues,
)


@dataclass
class FuelStageReadiness:
    ready: bool
    reason: str | None
    distribution_parameter_id: int
    distribution_name: str | None
    year_number: int
    selected_group_ids: list[int] = field(default_factory=list)
    e_target: Decimal | None = None
    sum_e_cyear: Decimal | None = None
    delta_e: Decimal | None = None


@dataclass
class FuelStageRunResult:
    distribution_parameter_id: int
    distribution_name: str | None
    year_number: int
    selected_group_ids: list[int] = field(default_factory=list)
    batch_result: BatchCalculationResult | None = None
    total_fuel_b: Decimal | None = None
    readiness: FuelStageReadiness | None = None


class FuelStageService:
    def __init__(self, session: Session | None = None):
        self.session = session or db.session
        self.distribution_service = DistributionStageService(session=self.session)
        self.batch_service = EquipmentGroupFuelBatchCalculationService(session=self.session)

    def get_readiness(self, distribution_parameter_id: int) -> FuelStageReadiness:
        row = self.session.get(
            DistributionParameter,
            distribution_parameter_id,
            options=[
                joinedload(DistributionParameter.union_energy_system),
                joinedload(DistributionParameter.year),
                joinedload(DistributionParameter.base_year),
            ],
        )
        if row is None:
            raise ValueError(f"Не найдена строка DistributionParameter id={distribution_parameter_id}")
        if row.year is None:
            raise ValueError(
                f"DistributionParameter id={distribution_parameter_id}: не задан справочный год (Year)"
            )

        effective_db_version = self.distribution_service._resolve_effective_db_version(
            row,
            None,
        )
        group_ids = self.distribution_service._select_equipment_group_ids(
            row=row,
            effective_db_version=effective_db_version,
        )
        group_ids = participating_group_ids_for_year(
            self.session,
            group_ids,
            year_number=int(row.year.number),
            effective_db_version=effective_db_version,
        )
        distribution_name = (
            row.union_energy_system.name if row.union_energy_system is not None else None
        )
        e_target = d0(row.e)

        if not group_ids:
            return FuelStageReadiness(
                ready=False,
                reason="Этап «Топливо» недоступен: по параметру распределения не выбрано ни одной группы.",
                distribution_parameter_id=row.id,
                distribution_name=distribution_name,
                year_number=row.year.number,
                selected_group_ids=[],
                e_target=e_target,
                sum_e_cyear=None,
                delta_e=None,
            )

        if e_target <= 0:
            return FuelStageReadiness(
                ready=False,
                reason="Этап «Топливо» недоступен: не задано положительное значение Ераспред.",
                distribution_parameter_id=row.id,
                distribution_name=distribution_name,
                year_number=row.year.number,
                selected_group_ids=group_ids,
                e_target=e_target,
                sum_e_cyear=None,
                delta_e=None,
            )

        sum_e_cyear, counted = self.distribution_service.sum_processed_calc_year_e(
            group_ids=group_ids,
            cyear=int(row.year.number),
            effective_db_version=effective_db_version,
        )
        if counted == 0:
            return FuelStageReadiness(
                ready=False,
                reason="Этап «Топливо» недоступен: нет данных расчётного года для контроля ΣE.",
                distribution_parameter_id=row.id,
                distribution_name=distribution_name,
                year_number=row.year.number,
                selected_group_ids=group_ids,
                e_target=e_target,
                sum_e_cyear=None,
                delta_e=None,
            )

        delta_e = abs(e_target - sum_e_cyear)
        ready = delta_e <= D03
        reason = None
        if not ready:
            reason = (
                "Этап «Топливо» недоступен: сначала выполните «Распред.». "
                f"Сейчас ΣE={sum_e_cyear:.1f}, Ераспред={e_target:.1f}, отклонение={delta_e:.1f}."
            )
            composite_hint = flash_text_for_composite_energy_level_issues(
                find_composite_energy_level_issues(
                    self.session,
                    database_version_id=effective_db_version,
                    year_number=int(row.year.number),
                    selected_group_ids=group_ids,
                )
            )
            if composite_hint:
                reason = f"{reason} {composite_hint}"

        return FuelStageReadiness(
            ready=ready,
            reason=reason,
            distribution_parameter_id=row.id,
            distribution_name=distribution_name,
            year_number=row.year.number,
            selected_group_ids=group_ids,
            e_target=e_target,
            sum_e_cyear=sum_e_cyear,
            delta_e=delta_e,
        )

    def run_for_distribution_parameter(self, distribution_parameter_id: int) -> FuelStageRunResult:
        readiness = self.get_readiness(distribution_parameter_id)
        if not readiness.ready:
            raise ValueError(readiness.reason or "Этап «Топливо» недоступен.")

        effective_db_version = self.distribution_service._resolve_effective_db_version(
            self.session.get(DistributionParameter, distribution_parameter_id),
            None,
        )
        batch_result = self.batch_service.calculate_for_many_groups(
            equipment_group_ids=readiness.selected_group_ids,
            year_number=readiness.year_number,
            database_version_id=effective_db_version,
            commit_each=True,
            final_commit=True,
            stop_on_error=False,
        )

        total_fuel_b = Decimal("0")
        for item in batch_result.items:
            if not item.success or not item.calculated:
                continue
            total_fuel_b += d0((item.calculated.get("energy") or {}).get("b"))

        return FuelStageRunResult(
            distribution_parameter_id=readiness.distribution_parameter_id,
            distribution_name=readiness.distribution_name,
            year_number=readiness.year_number,
            selected_group_ids=readiness.selected_group_ids,
            batch_result=batch_result,
            total_fuel_b=total_fuel_b,
            readiness=readiness,
        )
