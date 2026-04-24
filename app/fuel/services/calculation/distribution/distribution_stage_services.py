# -*- coding: utf-8 -*-
"""
Этап «Распред» для страницы /fuel/calculation.

Порт основной логики Access из обработчика Кнопка27_Click:
- берет агрегаты этапа «Коэфф» по параметру распределения;
- пересчитывает выработку `e` по строкам топлива расчётного года;
- бинарным поиском подбирает коэффициент `k` (или `kn`, если база пустая),
  чтобы сумма `e` приблизилась к целевому Ераспред.

Ограничения текущего порта:
- ограничения по областям (kobl / форма «Анализ_по_областям») в веб-версии пока отсутствуют;
- функция Access `Nivh(hb, ph)` в репозитории не найдена, поэтому пока используется
  нейтральный множитель 1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.common.services.database_version_filter import get_current_db_version_id
from app.extensions import db
from app.fuel.models.coefficient.distribution_coefficient_summary_model import (
    DistributionCoefficientSummary,
)
from app.fuel.models.fue_distribution_parameter_model import DistributionParameter
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.fuel.services.adapters.access_filter_adapter import AccessFilterAdapter
from app.fuel.services.calculation.coefficient.fuel_coefficient_calculation_services import (
    FuelCoefficientCalculationService,
)


D0 = Decimal("0")
D1 = Decimal("1")
D004 = Decimal("1.04")
D005 = Decimal("1.05")
D01 = Decimal("0.1")
D03 = Decimal("0.3")
D350 = Decimal("350")
D550 = Decimal("550")
D200 = Decimal("200")
D275 = Decimal("2.75")
D1000 = Decimal("1000")
D6000 = Decimal("6000")
D6500 = Decimal("6500")
D7000 = Decimal("7000")


def d0(value) -> Decimal:
    if value is None:
        return D0
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _obor_int(obor) -> int | None:
    if obor is None:
        return None
    if isinstance(obor, int) and not isinstance(obor, bool):
        return obor
    try:
        return int(str(obor).strip())
    except (TypeError, ValueError):
        return None


@dataclass
class DistributionStageRunResult:
    distribution_parameter_id: int
    distribution_name: str | None
    year_number: int
    selected_group_ids: list[int] = field(default_factory=list)
    processed_group_ids: list[int] = field(default_factory=list)
    skipped_group_ids: list[int] = field(default_factory=list)
    updated_fuel_rows: int = 0
    iterations: int = 0
    total_distributed_e: Decimal = D0
    final_k: Decimal | None = None
    final_kn: Decimal | None = None


class DistributionStageService:
    def __init__(self, session: Session | None = None):
        self.session = session or db.session

    def _resolve_effective_db_version(
        self,
        row: DistributionParameter,
        requested_database_version_id: int | None,
    ) -> int | None:
        if requested_database_version_id is not None:
            return requested_database_version_id
        if row.database_version_id is not None:
            return row.database_version_id
        return get_current_db_version_id()

    def _select_equipment_group_ids(
        self,
        *,
        row: DistributionParameter,
        effective_db_version: int | None,
    ) -> list[int]:
        query = self.session.query(EquipmentGroup.id)

        if effective_db_version is not None and hasattr(EquipmentGroup, "database_version_id"):
            query = query.filter(
                or_(
                    EquipmentGroup.database_version_id == effective_db_version,
                    EquipmentGroup.database_version_id.is_(None),
                )
            )

        expr = AccessFilterAdapter.build_expression(row.filter_text or "")
        if expr is not None:
            query = query.filter(expr)

        return [x[0] for x in query.order_by(EquipmentGroup.id).all()]

    def list_equipment_group_ids_for_distribution_parameter(
        self,
        distribution_parameter_id: int,
    ) -> list[int]:
        """
        Список id групп оборудования по фильтру параметра распределения (как для этапа «Распред»).
        """
        row = self.session.get(DistributionParameter, distribution_parameter_id)
        if row is None:
            return []
        effective = self._resolve_effective_db_version(row, None)
        return self._select_equipment_group_ids(row=row, effective_db_version=effective)

    @staticmethod
    def _pick_best_fuel_param_row(
        existing: EquipmentGroupFuelParam | None,
        candidate: EquipmentGroupFuelParam,
        effective_db_version: int | None,
    ) -> EquipmentGroupFuelParam:
        def tier(r: EquipmentGroupFuelParam) -> int:
            vid = getattr(r, "database_version_id", None)
            if effective_db_version is None:
                return 2
            if vid == effective_db_version:
                return 3
            if vid is None:
                return 2
            return 1

        if existing is None or tier(candidate) > tier(existing):
            return candidate
        return existing

    def _fuel_param_by_group_year(
        self,
        *,
        group_ids: list[int],
        byear: int | None,
        cyear: int,
        effective_db_version: int | None,
    ) -> dict[tuple[int, int], EquipmentGroupFuelParam]:
        if not group_ids:
            return {}

        if byear is not None:
            year_filter = EquipmentGroupFuelParam.year_number.in_([byear, cyear])
        else:
            year_filter = EquipmentGroupFuelParam.year_number == cyear

        rows = (
            self.session.query(EquipmentGroupFuelParam)
            .filter(
                EquipmentGroupFuelParam.equipment_group_id.in_(group_ids),
                year_filter,
            )
            .all()
        )

        by_key: dict[tuple[int, int], EquipmentGroupFuelParam] = {}
        for fuel_row in rows:
            if fuel_row.year_number is None:
                continue
            key = (fuel_row.equipment_group_id, int(fuel_row.year_number))
            by_key[key] = self._pick_best_fuel_param_row(
                by_key.get(key),
                fuel_row,
                effective_db_version,
            )
        return by_key

    def _latest_specific_row(
        self,
        *,
        equipment_group_id: int,
        target_year: int,
        effective_db_version: int | None,
    ) -> EquipmentGroupSpecificFuelConsumption | None:
        q = self.session.query(EquipmentGroupSpecificFuelConsumption).filter(
            EquipmentGroupSpecificFuelConsumption.equipment_group_id == equipment_group_id,
            EquipmentGroupSpecificFuelConsumption.year_number <= target_year,
        )

        if effective_db_version is not None and hasattr(
            EquipmentGroupSpecificFuelConsumption, "database_version_id"
        ):
            q = q.filter(
                or_(
                    EquipmentGroupSpecificFuelConsumption.database_version_id == effective_db_version,
                    EquipmentGroupSpecificFuelConsumption.database_version_id.is_(None),
                )
            )

        row = q.order_by(EquipmentGroupSpecificFuelConsumption.year_number.desc()).first()
        if row is not None:
            return row

        return (
            self.session.query(EquipmentGroupSpecificFuelConsumption)
            .filter(
                EquipmentGroupSpecificFuelConsumption.equipment_group_id == equipment_group_id,
                EquipmentGroupSpecificFuelConsumption.year_number <= target_year,
            )
            .order_by(EquipmentGroupSpecificFuelConsumption.year_number.desc())
            .first()
        )

    @staticmethod
    def _hours_from_fuel_row(row: EquipmentGroupFuelParam | None) -> Decimal:
        if row is None:
            return D0
        nust = d0(row.nust)
        if nust <= 0:
            return D0
        return d0(row.e) / nust * D1000

    @staticmethod
    def _distribution_bounds_from_ph(ph: Decimal, doptim: Decimal) -> tuple[Decimal, Decimal]:
        if ph > D1 - doptim and ph < D1:
            return ph * 2 - D1, D1
        if ph > D1 and ph < D1 + doptim:
            return D1, ph * 2 - D1
        return ph - doptim, ph + doptim

    @staticmethod
    def _koptim_from_bk(*, bk: Decimal, kmin: Decimal, kplus: Decimal) -> Decimal:
        if bk < D350:
            return kplus
        if bk > D550:
            return kmin
        return kmin + (kplus - kmin) * (D275 - bk / D200)

    @staticmethod
    def _nivh_factor(*, hb: Decimal, ph: Decimal) -> Decimal:
        # В репозитории и документации исходная Access-функция Nivh(...) не найдена.
        # Пока используем нейтральный множитель, чтобы реализовать сам этап распределения.
        _ = hb, ph
        return D1

    @staticmethod
    def _new_capacity_hours(
        *,
        obor,
        ch: Decimal,
        knps: Decimal,
        kngt: Decimal,
        knpg: Decimal,
    ) -> Decimal:
        oc = _obor_int(obor)
        if oc in (20, 90, 24, 89):
            return ch * kngt
        if oc in (21, 91):
            return ch * knpg
        return ch * knps

    @staticmethod
    def _clamp_hours(*, hours: Decimal, hb: Decimal, hd: Decimal) -> Decimal:
        if hb > D7000 and hours > hb:
            return hb
        if hb > D6500 and hb < D7000 and hd < D6000 and hours > hb * D005:
            return min(hb * D005, D7000)
        if hours > D7000:
            return D7000
        return hours

    @staticmethod
    def _calc_row_energy(
        *,
        cur_row: EquipmentGroupFuelParam,
        hb: Decimal,
        h_current: Decimal,
        ch: Decimal,
        nustb: Decimal,
    ) -> Decimal:
        oc = _obor_int(cur_row.obor)
        ewtp = d0(cur_row.ewtp)
        if oc is not None and 8 <= oc <= 10:
            return ewtp

        nust = d0(cur_row.nust)
        if nust > nustb and h_current > ch and nustb > 0:
            e1 = (nustb * h_current + (nust - nustb) * ch) / D1000
        else:
            _ = hb
            e1 = nust * h_current / D1000
        return max(e1, ewtp * D004)

    def _load_coeff_summary(
        self,
        *,
        distribution_parameter_id: int,
        cyear: int,
        effective_db_version: int | None,
    ) -> DistributionCoefficientSummary | None:
        q = self.session.query(DistributionCoefficientSummary).filter_by(
            distribution_parameter_id=distribution_parameter_id,
            year_number=cyear,
        )
        if effective_db_version is not None:
            q = q.filter(DistributionCoefficientSummary.database_version_id == effective_db_version)
        else:
            q = q.filter(DistributionCoefficientSummary.database_version_id.is_(None))

        found = q.order_by(DistributionCoefficientSummary.id.desc()).first()
        if found is not None:
            return found

        return (
            self.session.query(DistributionCoefficientSummary)
            .filter_by(
                distribution_parameter_id=distribution_parameter_id,
                year_number=cyear,
            )
            .order_by(DistributionCoefficientSummary.id.desc())
            .first()
        )

    def run_for_distribution_parameter(
        self,
        *,
        distribution_parameter_id: int,
        database_version_id: int | None = None,
        commit: bool = True,
    ) -> DistributionStageRunResult:
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

        effective_db_version = self._resolve_effective_db_version(row, database_version_id)
        group_ids = self._select_equipment_group_ids(
            row=row,
            effective_db_version=effective_db_version,
        )
        cyear = row.year.number
        byear = row.base_year.number if row.base_year is not None else None

        # Перед «Распред» обновляем агрегаты этапа «Коэфф» в той же сессии:
        # пересчитываются ewtp по строкам и сводка ph/hd/ch/kn*.
        FuelCoefficientCalculationService(session=self.session).run_for_distribution_parameter(
            distribution_parameter_id,
            commit=False,
        )
        coeff_summary = self._load_coeff_summary(
            distribution_parameter_id=row.id,
            cyear=cyear,
            effective_db_version=effective_db_version,
        )
        if coeff_summary is None:
            raise ValueError("Не удалось получить сводку этапа «Коэфф» для выполнения «Распред».")

        by_key = self._fuel_param_by_group_year(
            group_ids=group_ids,
            byear=byear,
            cyear=cyear,
            effective_db_version=effective_db_version,
        )

        e_target = d0(row.e)
        doptim = d0(row.doptim)
        bnust = d0(coeff_summary.bnust)
        ch = d0(coeff_summary.ch)
        ph = d0(coeff_summary.ph)
        hd = d0(coeff_summary.hd)

        k_value = d0(row.k)
        kn_value = d0(coeff_summary.kn if coeff_summary.kn is not None else row.kn)
        knps = d0(coeff_summary.knps if coeff_summary.knps is not None else row.knps)
        kngt = d0(coeff_summary.kngt if coeff_summary.kngt is not None else row.kngt)
        knpg = d0(coeff_summary.knpg if coeff_summary.knpg is not None else row.knpg)

        kl = k_value - D01
        kh = k_value + D01
        kln = kn_value - D01
        khn = kn_value + D01

        kmin_local, kplus_local = self._distribution_bounds_from_ph(ph, doptim)

        processed_group_ids: list[int] = []
        skipped_group_ids: list[int] = []
        updated_fuel_rows = 0
        total_distributed_e = D0
        iterations = 0

        for nit in range(1, 16):
            iterations = nit
            processed_group_ids = []
            skipped_group_ids = []
            updated_fuel_rows = 0
            total_distributed_e = D0

            for equipment_group_id in group_ids:
                cur_row = by_key.get((equipment_group_id, cyear))
                if cur_row is None:
                    skipped_group_ids.append(equipment_group_id)
                    continue

                spec = self._latest_specific_row(
                    equipment_group_id=equipment_group_id,
                    target_year=cyear,
                    effective_db_version=effective_db_version,
                )
                if spec is None:
                    skipped_group_ids.append(equipment_group_id)
                    continue

                base_row = by_key.get((equipment_group_id, byear)) if byear is not None else None
                hb = self._hours_from_fuel_row(base_row)
                nustb = d0(base_row.nust) if base_row is not None else D0

                cur_row.ewtp = d0(cur_row.qotr) * d0(spec.y) / D1000

                if hb == 0:
                    h_current = self._new_capacity_hours(
                        obor=cur_row.obor,
                        ch=ch,
                        knps=knps,
                        kngt=kngt,
                        knpg=knpg,
                    )
                else:
                    koptim = self._koptim_from_bk(
                        bk=d0(spec.bk),
                        kmin=kmin_local,
                        kplus=kplus_local,
                    )
                    ke = self._nivh_factor(hb=hb, ph=ph)
                    h_current = hb * koptim * k_value * ke
                    h_current = self._clamp_hours(hours=h_current, hb=hb, hd=hd)

                cur_row.e = self._calc_row_energy(
                    cur_row=cur_row,
                    hb=hb,
                    h_current=h_current,
                    ch=ch,
                    nustb=nustb,
                )

                processed_group_ids.append(equipment_group_id)
                updated_fuel_rows += 1
                total_distributed_e += d0(cur_row.e)

            if updated_fuel_rows == 0:
                break

            if abs(e_target - total_distributed_e) < D03:
                break

            if nit >= 15:
                break

            if bnust > 0:
                if e_target > total_distributed_e:
                    kl = k_value
                else:
                    kh = k_value
                k_value = (kl + kh) / 2
                continue

            if e_target > total_distributed_e:
                kln = kn_value
            else:
                khn = kn_value
            kn_mid = (kln + khn) / 2
            if kn_mid == 0:
                break

            scale = kn_value / kn_mid
            knps *= scale
            kngt *= scale
            knpg *= scale
            kn_value = kn_mid

        row.k = k_value
        row.kn = kn_value
        row.knps = knps
        row.kngt = kngt
        row.knpg = knpg
        self.session.add(row)

        if commit:
            self.session.commit()
        else:
            self.session.flush()

        ues = row.union_energy_system
        distribution_label = ues.name if ues is not None else None
        return DistributionStageRunResult(
            distribution_parameter_id=row.id,
            distribution_name=distribution_label,
            year_number=cyear,
            selected_group_ids=group_ids,
            processed_group_ids=processed_group_ids,
            skipped_group_ids=skipped_group_ids,
            updated_fuel_rows=updated_fuel_rows,
            iterations=iterations,
            total_distributed_e=total_distributed_e,
            final_k=k_value,
            final_kn=kn_value,
        )
