# -*- coding: utf-8 -*-
"""
Мост между DistributionParameter, AccessFilterAdapter, отбором EquipmentGroup и
пакетным расчётом топлива (EquipmentGroupFuelBatchCalculationService).

Сервис только:
  получает строку DistributionParameter;
  определяет эффективную версию БД;
  разбирает filter_text через AccessFilterAdapter (сам filter_text не парсит);
  выбирает группы оборудования;
  запускает пакетный расчёт.

Не содержит математики топлива, UI, построения таблиц и import-логики.

Поля wname, uname, toplname, dopname в DistributionParameter — информационные
(трассируемость, UI, миграции); не участвуют в ветвлении бизнес-логики здесь.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from sqlalchemy import nullslast
from sqlalchemy.orm import Session, joinedload

from app.extensions import db
from app.common.services.database_version_filter import get_current_db_version_id
from app.fuel.models.fue_distribution_parameter_model import DistributionParameter
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.years.year_model import Year
from app.fuel.services.calculation.equipment_group_selection import (
    select_equipment_group_ids_for_calculation,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_batch_calculation_services import (
    BatchCalculationResult,
    EquipmentGroupFuelBatchCalculationService,
)


@dataclass
class DistributionRunResult:
    distribution_parameter_id: int
    distribution_name: str | None
    year_number: int
    selected_group_ids: list[int] = field(default_factory=list)
    batch_result: BatchCalculationResult | None = None


class DistributionParameterCalculationService:
    """
    Запуск пересчёта по «Параметры-распределения».

    Строка filter_text не парсится здесь — только через AccessFilterAdapter.build_expression(...).

    Логика:
    строка DistributionParameter
      -> filter_text / year / version
      -> отбор EquipmentGroup
      -> пакетный пересчёт топлива
    """

    def __init__(self, session: Session | None = None):
        self.session = session or db.session
        self.batch_service = EquipmentGroupFuelBatchCalculationService(session=self.session)

    def _resolve_effective_db_version(
        self,
        *,
        requested_database_version_id: int | None,
        row: DistributionParameter,
    ) -> int | None:
        if requested_database_version_id is not None:
            return requested_database_version_id
        if row.database_version_id is not None:
            return row.database_version_id
        return get_current_db_version_id()

    def _select_equipment_group_ids_for_distribution(
        self,
        *,
        row: DistributionParameter,
        effective_db_version: int | None,
    ) -> list[int]:
        return select_equipment_group_ids_for_calculation(
            self.session,
            filter_text=row.filter_text,
            effective_db_version=effective_db_version,
        )

    @staticmethod
    def _calendar_year_number(row: DistributionParameter) -> int:
        if row.year is None:
            raise ValueError(
                f"DistributionParameter id={row.id}: не задан справочный год (Year / id_year)"
            )
        return row.year.number

    def calculate_from_distribution_param(
        self,
        *,
        distribution_param_id: int,
        database_version_id: int | None = None,
        variant_number: int = 0,
        strict_formula_validation: bool = False,
        commit_each: bool = True,
        final_commit: bool = True,
        stop_on_error: bool = False,
    ) -> DistributionRunResult:
        row = self.session.get(
            DistributionParameter,
            distribution_param_id,
            options=[
                joinedload(DistributionParameter.union_energy_system),
                joinedload(DistributionParameter.year),
                joinedload(DistributionParameter.base_year),
            ],
        )
        if row is None:
            raise ValueError(
                f"Не найдена строка DistributionParameter id={distribution_param_id}"
            )

        effective_db_version = self._resolve_effective_db_version(
            requested_database_version_id=database_version_id,
            row=row,
        )

        group_ids = self._select_equipment_group_ids_for_distribution(
            row=row,
            effective_db_version=effective_db_version,
        )

        cal_year = self._calendar_year_number(row)

        batch_result = self.batch_service.calculate_for_many_groups(
            equipment_group_ids=group_ids,
            year_number=cal_year,
            database_version_id=effective_db_version,
            variant_number=variant_number,
            strict_formula_validation=strict_formula_validation,
            commit_each=commit_each,
            final_commit=final_commit,
            stop_on_error=stop_on_error,
        )

        ues = row.union_energy_system
        distribution_label = ues.name if ues is not None else None

        return DistributionRunResult(
            distribution_parameter_id=row.id,
            distribution_name=distribution_label,
            year_number=cal_year,
            selected_group_ids=group_ids,
            batch_result=batch_result,
        )

    def calculate_from_distribution_params(
        self,
        *,
        distribution_param_ids: Sequence[int] | None = None,
        name: str | None = None,
        year_number: int | None = None,
        database_version_id: int | None = None,
        variant_number: int = 0,
        strict_formula_validation: bool = False,
        commit_each: bool = True,
        final_commit: bool = True,
        stop_on_error: bool = False,
    ) -> list[DistributionRunResult]:
        query = (
            self.session.query(DistributionParameter)
            .outerjoin(
                UnionEnergySystem,
                DistributionParameter.id_union_energy_system == UnionEnergySystem.id,
            )
            .outerjoin(Year, DistributionParameter.id_year == Year.id)
        )

        if distribution_param_ids:
            query = query.filter(DistributionParameter.id.in_(distribution_param_ids))
        if name:
            query = query.filter(UnionEnergySystem.name == name)
        if year_number is not None:
            query = query.filter(Year.number == year_number)
        if database_version_id is not None:
            query = query.filter(
                (DistributionParameter.database_version_id == database_version_id)
                | (DistributionParameter.database_version_id.is_(None))
            )

        rows = query.order_by(
            nullslast(UnionEnergySystem.name.asc()),
            Year.number,
            DistributionParameter.id,
        ).all()

        results: list[DistributionRunResult] = []

        for row in rows:
            result = self.calculate_from_distribution_param(
                distribution_param_id=row.id,
                database_version_id=database_version_id,
                variant_number=variant_number,
                strict_formula_validation=strict_formula_validation,
                commit_each=commit_each,
                final_commit=False,
                stop_on_error=stop_on_error,
            )
            results.append(result)

        if final_commit and not commit_each:
            if any(
                run.batch_result and run.batch_result.error_count > 0
                for run in results
            ):
                self.session.rollback()
            else:
                self.session.commit()

        return results
