# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from sqlalchemy.orm import Session

from app.extensions import db
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import (
    EquipmentGroupExtraFuelParam,
)
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.services.equipment_groups.equipment_group_fuel_calculation_services import (
    TOPLS,
    UGLI,
    UGLI1,
    EquipmentGroupFuelCalculationService,
)

_MAIN_FUEL_KEYS: tuple[str, ...] = tuple(sorted(TOPLS | UGLI))
_EXTRA_FUEL_KEYS: tuple[str, ...] = tuple(sorted(UGLI1))


def _numeric_to_json(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def fuel_calculation_snapshot_for_api(
    *,
    fuel_param: EquipmentGroupFuelParam,
    extra_param: EquipmentGroupExtraFuelParam | None,
    specific_fuel_consumption_row_year_number: int | None,
    fuel_formula_row_year_number: int | None,
) -> dict[str, Any]:
    """
    Снимок строк параметров после calculate_group_year — для ответа пакетного API.
    Числа — строки, как в Decimal.__str__, чтобы не терять точность.
    specific_fuel_consumption_row_year_number / fuel_formula_row_year_number — годы исходных строк
    Seek-окна [base_year, year], как в EquipmentGroupFuelCalculationService.
    """
    energy_keys = ("ewtp", "eotp", "eust", "eurt", "tust", "b")
    balance_keys = ("e", "q", "qotr", "turt")
    out: dict[str, Any] = {
        "year_number": fuel_param.year_number,
        "name": fuel_param.name,
        "source_row_years": {
            "specific_fuel_consumption": specific_fuel_consumption_row_year_number,
            "fuel_formula": fuel_formula_row_year_number,
        },
        "energy": {k: _numeric_to_json(getattr(fuel_param, k)) for k in energy_keys},
        "energy_balance_inputs": {k: _numeric_to_json(getattr(fuel_param, k)) for k in balance_keys},
        "main_fuels": {k: _numeric_to_json(getattr(fuel_param, k)) for k in _MAIN_FUEL_KEYS},
        "extra_fuels": {},
    }
    if extra_param is not None:
        out["extra_fuels"] = {
            k: _numeric_to_json(getattr(extra_param, k))
            for k in _EXTRA_FUEL_KEYS
            if hasattr(extra_param, k)
        }
    return out


@dataclass
class BatchCalculationItemResult:
    equipment_group_id: int
    success: bool
    error: str | None = None
    calculated: dict[str, Any] | None = None  # снимок полей после расчёта (при success)


@dataclass
class BatchCalculationResult:
    total: int = 0
    success_count: int = 0
    error_count: int = 0
    items: list[BatchCalculationItemResult] = field(default_factory=list)

    @property
    def ok_ids(self) -> list[int]:
        return [x.equipment_group_id for x in self.items if x.success]

    @property
    def failed_ids(self) -> list[int]:
        return [x.equipment_group_id for x in self.items if not x.success]


class EquipmentGroupFuelBatchCalculationService:
    """
    Пакетный пересчет топлива для групп оборудования.
    Использует EquipmentGroupFuelCalculationService.calculate_group_year(...).
    """

    def __init__(self, session: Session | None = None):
        self.session = session or db.session
        self.single_service = EquipmentGroupFuelCalculationService(session=self.session)

    def calculate_for_many_groups(
        self,
        *,
        equipment_group_ids: Sequence[int],
        year_number: int,
        database_version_id: int | None = None,
        variant_number: int = 0,
        strict_formula_validation: bool = False,
        commit_each: bool = False,
        final_commit: bool = True,
        stop_on_error: bool = False,
        chunk_size: int = 200,
        base_year_number: int | None = None,
    ) -> BatchCalculationResult:
        result = BatchCalculationResult(total=len(equipment_group_ids))

        for index, equipment_group_id in enumerate(equipment_group_ids, start=1):
            try:
                if commit_each:
                    fuel_param = self.single_service.calculate_group_year(
                        equipment_group_id=equipment_group_id,
                        year_number=year_number,
                        database_version_id=database_version_id,
                        variant_number=variant_number,
                        strict_formula_validation=strict_formula_validation,
                        commit=True,
                        base_year_number=base_year_number,
                    )
                else:
                    with self.session.begin_nested():
                        fuel_param = self.single_service.calculate_group_year(
                            equipment_group_id=equipment_group_id,
                            year_number=year_number,
                            database_version_id=database_version_id,
                            variant_number=variant_number,
                            strict_formula_validation=strict_formula_validation,
                            commit=False,
                            base_year_number=base_year_number,
                        )

                extra_row = (
                    self.session.query(EquipmentGroupExtraFuelParam)
                    .filter(
                        EquipmentGroupExtraFuelParam.equipment_group_id == equipment_group_id,
                        EquipmentGroupExtraFuelParam.year_number == year_number,
                    )
                    .one_or_none()
                )
                cons = self.single_service._select_actual_consumption_row(
                    equipment_group_id=equipment_group_id,
                    target_year=year_number,
                    database_version_id=database_version_id,
                    byear=base_year_number,
                )
                frm = self.single_service._select_actual_formula_row(
                    equipment_group_id=equipment_group_id,
                    target_year=year_number,
                    variant_number=variant_number,
                    database_version_id=database_version_id,
                    byear=base_year_number,
                )
                calculated = fuel_calculation_snapshot_for_api(
                    fuel_param=fuel_param,
                    extra_param=extra_row,
                    specific_fuel_consumption_row_year_number=(
                        cons.year_number if cons is not None else None
                    ),
                    fuel_formula_row_year_number=frm.year_number if frm is not None else None,
                )

                result.items.append(
                    BatchCalculationItemResult(
                        equipment_group_id=equipment_group_id,
                        success=True,
                        calculated=calculated,
                    )
                )
                result.success_count += 1

                if not commit_each and chunk_size > 0 and index % chunk_size == 0:
                    self.session.flush()
                    self.session.expire_all()

            except Exception as exc:
                if commit_each:
                    self.session.rollback()

                result.items.append(
                    BatchCalculationItemResult(
                        equipment_group_id=equipment_group_id,
                        success=False,
                        error=str(exc),
                    )
                )
                result.error_count += 1

                if stop_on_error:
                    raise

        if final_commit and not commit_each:
            self.session.commit()

        return result

    def calculate_for_many_group_objects(
        self,
        *,
        groups: Iterable[EquipmentGroup],
        year_number: int,
        database_version_id: int | None = None,
        variant_number: int = 0,
        strict_formula_validation: bool = False,
        commit_each: bool = False,
        final_commit: bool = True,
        stop_on_error: bool = False,
        chunk_size: int = 200,
        base_year_number: int | None = None,
    ) -> BatchCalculationResult:
        equipment_group_ids = [group.id for group in groups]
        return self.calculate_for_many_groups(
            equipment_group_ids=equipment_group_ids,
            year_number=year_number,
            database_version_id=database_version_id,
            variant_number=variant_number,
            strict_formula_validation=strict_formula_validation,
            commit_each=commit_each,
            final_commit=final_commit,
            stop_on_error=stop_on_error,
            chunk_size=chunk_size,
            base_year_number=base_year_number,
        )
