# -*- coding: utf-8 -*-
"""
Этап «Распред» для страницы /fuel/calculation.

Порт основной логики Access из обработчика Кнопка27_Click:
- берет агрегаты этапа «Коэфф» по параметру распределения;
- пересчитывает выработку `e` по строкам топлива расчётного года;
- бинарным поиском подбирает коэффициент `k` (или `kn`, если база пустая),
  чтобы сумма `e` приблизилась к целевому Ераспред.

Опционально (флаг apply_restrictions — аналог открытого окна «Анализ_по_областям»):
- умножает часы на kobl по субъекту (obl) из gs_fue_restrictions;
- после сходимости K пересчитывает kobl по emin/emax (Ограничения_Click)
  и повторяет внешний цикл до 14 раз (Access: irestr < 15).

Ограничения текущего порта:
- интерактивный MsgBox Access «нет располагаемой мощности → HFIX=1» в веб не переносится
  (учитывается уже установленный флаг hfix).
"""
from __future__ import annotations

import re
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
from app.fuel.models.fue_restriction_model import FuelRestriction
from app.fuel.services.calculation.coefficient.fuel_coefficient_calculation_services import (
    CoeffStageRunResult,
    FuelCoefficientCalculationService,
)
from app.fuel.services.calculation.equipment_group_selection import (
    select_equipment_group_ids_for_calculation,
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


def _parse_oes_from_filter(filter_text: object) -> int | None:
    """Access: ioes = InStr(filter1, \"oes\"); codeoes = Mid(..., 1)."""
    if filter_text is None:
        return None
    m = re.search(r"oes\s*=\s*(\d+)", str(filter_text), flags=re.IGNORECASE)
    if not m:
        return None
    try:
        return int(m.group(1))
    except (TypeError, ValueError):
        return None


def _is_hfix(row: EquipmentGroupFuelParam | None) -> bool:
    if row is None:
        return False
    try:
        return int(row.hfix) == 1
    except (TypeError, ValueError):
        return False


@dataclass
class DistributionStageRunResult:
    distribution_parameter_id: int
    distribution_name: str | None
    year_number: int
    selected_group_ids: list[int] = field(default_factory=list)
    processed_group_ids: list[int] = field(default_factory=list)
    skipped_group_ids: list[int] = field(default_factory=list)
    updated_fuel_rows: int = 0
    # Максимум проходов внутренней бисекции K/kn по всем внешним циклам (до 16).
    iterations: int = 0
    restriction_outer_iterations: int = 0
    apply_restrictions: bool = False
    total_distributed_e: Decimal = D0
    final_k: Decimal | None = None
    final_kn: Decimal | None = None
    # Автозапуск «Коэфф» перед Распред (для блока «Результат последнего этапа «Коэфф»»).
    coeff_run: CoeffStageRunResult | None = None


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
        return select_equipment_group_ids_for_calculation(
            self.session,
            filter_text=row.filter_text,
            effective_db_version=effective_db_version,
        )

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
        """
        Часы базы для Распред.

        Access: ``hb = z(w("h"))`` — NULL→0 (ветка «новая мощность»).
        В АРМ после импорта ``h`` часто пуст при заполненных e/nust; без восстановления
        все станции уходят в kn*=0 и E=EWTP·1.04. Если h не задан — H = E/NUST·1000
        (как после calce в Access: ``H = E/NUST*1000``).
        """
        if row is None:
            return D0
        h = d0(row.h)
        if h > 0:
            return h
        nust = d0(row.nust)
        if nust > 0:
            e = d0(row.e)
            if e > 0:
                return e / nust * D1000
        return D0

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
        # Access Модуль1.Nivh: при ph>1.15 поправка по hb; иначе 1.
        if ph <= Decimal("1.15"):
            return D1
        de = ph - D1 - Decimal("0.05")
        if hb > D6000:
            nivh = D1
        elif hb < Decimal("2000"):
            nivh = D1 + de
        else:
            nivh = D1 + de * (Decimal("1.5") - hb / Decimal("4000"))
        return nivh / (D1 + de * Decimal("0.5"))

    @staticmethod
    def _new_capacity_hours(
        *,
        obor,
        ch: Decimal,
        knps: Decimal,
        kngt: Decimal,
        knpg: Decimal,
    ) -> Decimal:
        # Access: ГТ только obor 20|90 → kngt; 24|89 идут в knps («иначе»).
        oc = _obor_int(obor)
        if oc in (20, 90):
            return ch * kngt
        if oc in (21, 91):
            return ch * knpg
        return ch * knps

    @staticmethod
    def _clamp_hours(*, hours: Decimal, hb: Decimal, hd: Decimal) -> Decimal:
        # Access: hb > 6000 And hb < 7000 And hd < 6000 ...
        if hb > D7000 and hours > hb:
            return hb
        if hb > D6000 and hb < D7000 and hd < D6000 and hours > hb * D005:
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
        hfix: bool = False,
    ) -> Decimal:
        oc = _obor_int(cur_row.obor)
        ewtp = d0(cur_row.ewtp)
        if oc is not None and 8 <= oc <= 10:
            return ewtp

        nust = d0(cur_row.nust)
        # Access: ... And HFIX <> 1 — без формулы прироста мощности при фиксированных часах
        if (not hfix) and nust > nustb and h_current > ch and nustb > 0:
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

    def _load_restriction_rows(
        self,
        *,
        oes_code: int,
        cyear: int,
        effective_db_version: int | None = None,
    ) -> list[FuelRestriction]:
        ydec = Decimal(cyear)
        odec = Decimal(oes_code)
        q = self.session.query(FuelRestriction).filter(
            FuelRestriction.year == ydec,
            FuelRestriction.oes == odec,
        )
        if effective_db_version is not None:
            q = q.filter(
                FuelRestriction.database_version_id == effective_db_version
            )
        return q.order_by(FuelRestriction.obl.asc(), FuelRestriction.id.asc()).all()

    @staticmethod
    def _kobl_map_from_rows(rows: list[FuelRestriction]) -> dict[int, Decimal]:
        out: dict[int, Decimal] = {}
        for r in rows:
            if r.obl is None:
                continue
            out[int(r.obl)] = d0(r.kobl) if r.kobl is not None else D1
        return out

    @staticmethod
    def _kobl_for_group(
        *,
        obl: int | None,
        oes_code: int,
        kobl_by_obl: dict[int, Decimal],
    ) -> Decimal:
        if obl is not None and int(obl) in kobl_by_obl:
            return kobl_by_obl[int(obl)]
        return kobl_by_obl.get(100 + int(oes_code), D1)

    def _recalculate_restriction_kobl(
        self,
        *,
        restriction_rows: list[FuelRestriction],
        oes_code: int,
        cyear: int,
        filter_group_ids: set[int],
        lim_reset: bool,
        by_key: dict[tuple[int, int], EquipmentGroupFuelParam],
        groups_by_id: dict[int, EquipmentGroup],
    ) -> None:
        """
        Порт Ограничения_Click: пересчёт ecur/ecurdis/H/Hdis/etp/kobl по emin/emax.
        """
        all_oes_groups = (
            self.session.query(EquipmentGroup)
            .filter(EquipmentGroup.oes == oes_code)
            .all()
        )
        all_oes_ids = [g.id for g in all_oes_groups]
        all_by_key = self._fuel_param_by_group_year(
            group_ids=all_oes_ids,
            byear=None,
            cyear=cyear,
            effective_db_version=None,
        )
        all_groups = {g.id: g for g in all_oes_groups}

        def _sum_for_obl(
            *,
            obl_code: int,
            only_filter: bool,
        ) -> tuple[Decimal, Decimal, Decimal]:
            sum_e = D0
            sum_n = D0
            sum_etp = D0
            source_ids = filter_group_ids if only_filter else set(all_oes_ids)
            source_map = by_key if only_filter else all_by_key
            source_groups = groups_by_id if only_filter else all_groups
            for gid in source_ids:
                g = source_groups.get(gid)
                if g is None or g.obl is None or int(g.obl) != obl_code:
                    continue
                if not only_filter:
                    if g.vedomstvo is None or int(g.vedomstvo) <= 0:
                        continue
                row = source_map.get((gid, cyear))
                if row is None:
                    continue
                sum_e += d0(row.e)
                sum_n += d0(row.nust)
                sum_etp += d0(row.ewtp)
            return sum_e, sum_n, sum_etp

        residual_obl = 100 + int(oes_code)
        fltr_obls: list[int] = []
        deltaoes = D0

        for restr in restriction_rows:
            if restr.obl is None:
                continue
            obl_i = int(restr.obl)
            if obl_i == residual_obl:
                continue
            fltr_obls.append(obl_i)

            ecur, nsum, _ = _sum_for_obl(obl_code=obl_i, only_filter=False)
            ecurdis, ndis, etp = _sum_for_obl(obl_code=obl_i, only_filter=True)

            if lim_reset:
                restr.kobl = D1
            kobl = d0(restr.kobl) if restr.kobl is not None else D1

            restr.ecur = ecur
            restr.h = (ecur / nsum * D1000) if nsum > 0 else D0
            restr.ecurdis = ecurdis
            restr.hdis = (ecurdis / ndis * D1000) if ndis > 0 else D0
            restr.etp = etp

            emin = d0(restr.emin)
            emax = d0(restr.emax)
            if emin > 0 and ecur < emin and ecurdis > 0:
                kobl = kobl * (emin - ecur + ecurdis) / ecurdis
                deltaoes += emin - ecur
            if emax > 0 and ecur > emax and ecurdis > 0:
                kobl = kobl * (emax - ecur + ecurdis) / ecurdis
                deltaoes += emax - ecur
            restr.kobl = kobl
            self.session.add(restr)

        residual = next(
            (r for r in restriction_rows if r.obl is not None and int(r.obl) == residual_obl),
            None,
        )
        if residual is not None:
            sum_e = D0
            sum_n = D0
            sum_edis = D0
            sum_etp = D0
            fltr_set = set(fltr_obls)
            for gid, g in all_groups.items():
                if g.obl is None or int(g.obl) in fltr_set:
                    continue
                if g.vedomstvo is None or int(g.vedomstvo) <= 0:
                    continue
                row = all_by_key.get((gid, cyear))
                if row is None:
                    continue
                sum_e += d0(row.e)
                sum_n += d0(row.nust)
            for gid in filter_group_ids:
                g = groups_by_id.get(gid)
                if g is None or g.obl is None or int(g.obl) in fltr_set:
                    continue
                # Access sumprochdis: (ved>0) and filter1
                if g.vedomstvo is None or int(g.vedomstvo) <= 0:
                    continue
                row = by_key.get((gid, cyear))
                if row is None:
                    continue
                sum_edis += d0(row.e)
                sum_etp += d0(row.ewtp)

            # Access не сбрасывает kobl=1 для «прочих» при lim=0 — только домножает.
            kobl = d0(residual.kobl) if residual.kobl is not None else D1
            residual.ecur = sum_e
            residual.h = (sum_e / sum_n * D1000) if sum_n > 0 else D0
            residual.ecurdis = sum_edis
            residual.etp = sum_etp
            if sum_edis > 0:
                kobl = kobl * (sum_edis - deltaoes) / sum_edis
            residual.kobl = kobl
            self.session.add(residual)

        self.session.flush()

    def run_for_distribution_parameter(
        self,
        *,
        distribution_parameter_id: int,
        database_version_id: int | None = None,
        apply_restrictions: bool = False,
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

        coeff_run = FuelCoefficientCalculationService(
            session=self.session
        ).run_for_distribution_parameter(
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

        groups_by_id: dict[int, EquipmentGroup] = {}
        if group_ids:
            for g in self.session.query(EquipmentGroup).filter(EquipmentGroup.id.in_(group_ids)).all():
                groups_by_id[g.id] = g

        oes_code = _parse_oes_from_filter(row.filter_text)
        restriction_rows: list[FuelRestriction] = []
        kobl_by_obl: dict[int, Decimal] = {}
        if apply_restrictions:
            if oes_code is None:
                raise ValueError(
                    "Не удалось извлечь oes из filter_text параметра распределения "
                    "для учёта ограничений."
                )
            restriction_rows = self._load_restriction_rows(
                oes_code=oes_code,
                cyear=cyear,
                effective_db_version=effective_db_version,
            )
            if not restriction_rows:
                raise ValueError(
                    f"Нет строк ограничений для oes={oes_code}, year={cyear}. "
                    "Откройте «Ограничения» и проверьте данные."
                )
            # Access: при открытом окне первый проход берёт текущие kobl из формы
            # (пересчёт Ограничения_Click — только после enddis, уже с lim=1).
            kobl_by_obl = self._kobl_map_from_rows(restriction_rows)

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

        kmin_local, kplus_local = self._distribution_bounds_from_ph(ph, doptim)

        processed_group_ids: list[int] = []
        skipped_group_ids: list[int] = []
        updated_fuel_rows = 0
        total_distributed_e = D0
        iterations = 0  # max nit по всем внешним циклам (не только последний)
        # Access: irestr=1 … If irestr < 15 Then GoTo BDis → 14 внешних прохода.
        outer_max = 14 if apply_restrictions else 1
        restriction_outer_iterations = 0

        for outer in range(1, outer_max + 1):
            restriction_outer_iterations = outer
            kl = k_value - D01
            kh = k_value + D01
            kln = kn_value - D01
            khn = kn_value + D01
            outer_nit = 0

            # Access: выход после прохода при nit > 15 → максимум 16 итераций.
            for nit in range(1, 17):
                outer_nit = nit
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

                    hfix = _is_hfix(cur_row)
                    if hfix:
                        # Access: If hfix=1 Then GoTo calce — часы не трогаем формулой
                        h_current = self._hours_from_fuel_row(cur_row)
                    elif hb == 0:
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
                        kobl = D1
                        if apply_restrictions and oes_code is not None:
                            g = groups_by_id.get(equipment_group_id)
                            kobl = self._kobl_for_group(
                                obl=g.obl if g is not None else None,
                                oes_code=oes_code,
                                kobl_by_obl=kobl_by_obl,
                            )
                        h_current = hb * koptim * k_value * ke * kobl
                        h_current = self._clamp_hours(hours=h_current, hb=hb, hd=hd)

                    cur_row.e = self._calc_row_energy(
                        cur_row=cur_row,
                        hb=hb,
                        h_current=h_current,
                        ch=ch,
                        nustb=nustb,
                        hfix=hfix,
                    )
                    # Access: If NUST>0 Then H = E/NUST*1000
                    nust = d0(cur_row.nust)
                    if nust > 0:
                        cur_row.h = d0(cur_row.e) / nust * D1000
                    else:
                        cur_row.h = h_current

                    processed_group_ids.append(equipment_group_id)
                    updated_fuel_rows += 1
                    total_distributed_e += d0(cur_row.e)

                if updated_fuel_rows == 0:
                    break

                if abs(e_target - total_distributed_e) < D03:
                    break

                if nit > 15:
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

            if outer_nit > iterations:
                iterations = outer_nit

            if not apply_restrictions:
                break

            # Access enddis + Ограничения_Click + повтор BDis
            row.lim = 1
            self._recalculate_restriction_kobl(
                restriction_rows=restriction_rows,
                oes_code=oes_code,  # type: ignore[arg-type]
                cyear=cyear,
                filter_group_ids=set(group_ids),
                lim_reset=False,
                by_key=by_key,
                groups_by_id=groups_by_id,
            )
            kobl_by_obl = self._kobl_map_from_rows(restriction_rows)

        if not apply_restrictions:
            row.lim = 0

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
            restriction_outer_iterations=restriction_outer_iterations if apply_restrictions else 0,
            apply_restrictions=apply_restrictions,
            total_distributed_e=total_distributed_e,
            final_k=k_value,
            final_kn=kn_value,
            coeff_run=coeff_run,
        )
