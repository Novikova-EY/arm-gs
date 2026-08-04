# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.common.services.database_version_filter import get_current_db_version_id
from app.fuel.models.fue_distribution_parameter_model import DistributionParameter
from app.fuel.models.coefficient.distribution_coefficient_summary_model import (
    DistributionCoefficientSummary,
)
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)
from app.fuel.services.calculation.equipment_group_selection import (
    select_equipment_group_ids_for_calculation,
)


def d0(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _obor_int(obor) -> int | None:
    """Код obor из БД (иногда приходит не как int) для сравнения с литералами Access."""
    if obor is None:
        return None
    if isinstance(obor, int) and not isinstance(obor, bool):
        return obor
    try:
        return int(str(obor).strip())
    except (TypeError, ValueError):
        return None


def _access_k_coefficients_from_h(row: DistributionParameter, ch: Decimal) -> tuple[Decimal, Decimal, Decimal]:
    """
    Access: knps = hnps/ch, kngt = hngt/ch, knpg = hnpg/ch (обработчики hn*_AfterUpdate / BeforeUpdate).
    При ch <= 0 коэффициенты обнуляем.
    """
    hnps = d0(row.hnps)
    hngt = d0(row.hngt)
    hnpg = d0(row.hnpg)
    if ch <= 0:
        return Decimal("0"), Decimal("0"), Decimal("0")
    return hnps / ch, hngt / ch, hnpg / ch


@dataclass
class CoeffStageRunResult:
    distribution_parameter_id: int
    total_groups: int
    updated_fuel_rows: int
    summary_id: int | None


class FuelCoefficientCalculationService:
    def __init__(self, session=None):
        self.session = session or db.session

    def _resolve_effective_db_version(self, row: DistributionParameter) -> int | None:
        return row.database_version_id or get_current_db_version_id()

    @staticmethod
    def _pick_best_fuel_param_row(
        existing: EquipmentGroupFuelParam | None,
        candidate: EquipmentGroupFuelParam,
        effective_db_version: int | None,
    ) -> EquipmentGroupFuelParam:
        """Одна строка на (группа, год): версия = effective > NULL > иная (как запасной вариант)."""

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
        group_ids: list[int],
        byear: int | None,
        cyear: int,
        effective_db_version: int | None,
    ) -> dict[tuple[int, int], EquipmentGroupFuelParam]:
        """
        Словарь (equipment_group_id, year_number) -> строка топлива.

        Не отсекаем топливо только по database_version_id: в данных часто версия строки
        gs_fue_equipment_group_fuel_param не совпадает с версией параметра распределения,
        из‑за чего этап «Коэфф» не видел ни одной строки года.
        """
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
        for r in rows:
            if r.year_number is None:
                continue
            k = (r.equipment_group_id, int(r.year_number))
            by_key[k] = self._pick_best_fuel_param_row(
                by_key.get(k), r, effective_db_version
            )
        return by_key

    def _select_group_ids(self, row: DistributionParameter, effective_db_version: int | None) -> list[int]:
        return select_equipment_group_ids_for_calculation(
            self.session,
            filter_text=row.filter_text,
            effective_db_version=effective_db_version,
        )

    def _latest_specific_row(self, equipment_group_id: int, target_year: int, effective_db_version: int | None):
        q = self.session.query(EquipmentGroupSpecificFuelConsumption).filter(
            EquipmentGroupSpecificFuelConsumption.equipment_group_id == equipment_group_id,
            EquipmentGroupSpecificFuelConsumption.year_number <= target_year,
        )

        if effective_db_version is not None and hasattr(EquipmentGroupSpecificFuelConsumption, "database_version_id"):
            q = q.filter(
                or_(
                    EquipmentGroupSpecificFuelConsumption.database_version_id == effective_db_version,
                    EquipmentGroupSpecificFuelConsumption.database_version_id.is_(None),
                )
            )

        row = q.order_by(EquipmentGroupSpecificFuelConsumption.year_number.desc()).first()
        if row is not None:
            return row
        # Запасной вариант без фильтра по версии (см. комментарий к _fuel_param_by_group_year).
        return (
            self.session.query(EquipmentGroupSpecificFuelConsumption)
            .filter(
                EquipmentGroupSpecificFuelConsumption.equipment_group_id == equipment_group_id,
                EquipmentGroupSpecificFuelConsumption.year_number <= target_year,
            )
            .order_by(EquipmentGroupSpecificFuelConsumption.year_number.desc())
            .first()
        )

    def list_groups_missing_specific_for_distribution_parameter(
        self,
        distribution_parameter_id: int,
    ) -> dict:
        """
        Группы фильтра для контроля Skip на Коэфф / Распред / Топливо:
        - без строки топлива за расчётный год;
        - с топливом за расчётный год, но без удельника year ≤ расчётного.
        """
        row = self.session.get(
            DistributionParameter,
            distribution_parameter_id,
            options=[
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

        effective_db_version = self._resolve_effective_db_version(row)
        group_ids = self._select_group_ids(row, effective_db_version)
        cyear = int(row.year.number)

        def _groups_payload(ids: list[int]) -> list[dict]:
            if not ids:
                return []
            eg_rows = (
                self.session.query(EquipmentGroup)
                .filter(EquipmentGroup.id.in_(ids))
                .all()
            )
            by_id = {eg.id: eg for eg in eg_rows}
            out: list[dict] = []
            for gid in ids:
                eg = by_id.get(gid)
                out.append(
                    {
                        "equipment_group_id": gid,
                        "numb": eg.numb if eg is not None else None,
                        "name": (eg.name or eg.name_ext or f"id={gid}")
                        if eg is not None
                        else f"id={gid}",
                    }
                )
            out.sort(
                key=lambda g: (
                    g["numb"] is None,
                    g["numb"] if g["numb"] is not None else 0,
                    g["name"] or "",
                )
            )
            return out

        empty = {
            "year_number": cyear,
            "filter_group_count": len(group_ids),
            "calc_fuel_group_count": 0,
            "missing_fuel_count": 0,
            "missing_fuel_groups": [],
            "missing_count": 0,
            "groups": [],
        }
        if not group_ids:
            return empty

        fuel_eg_ids = {
            int(gid)
            for (gid,) in self.session.query(EquipmentGroupFuelParam.equipment_group_id)
            .filter(
                EquipmentGroupFuelParam.equipment_group_id.in_(group_ids),
                EquipmentGroupFuelParam.year_number == cyear,
            )
            .distinct()
            .all()
            if gid is not None
        }
        missing_fuel_ids = sorted(set(int(g) for g in group_ids) - fuel_eg_ids)
        missing_fuel_groups = _groups_payload(missing_fuel_ids)

        if not fuel_eg_ids:
            empty["missing_fuel_count"] = len(missing_fuel_groups)
            empty["missing_fuel_groups"] = missing_fuel_groups
            return empty

        specific_q = self.session.query(
            EquipmentGroupSpecificFuelConsumption.equipment_group_id
        ).filter(
            EquipmentGroupSpecificFuelConsumption.equipment_group_id.in_(fuel_eg_ids),
            EquipmentGroupSpecificFuelConsumption.year_number <= cyear,
        )
        if effective_db_version is not None and hasattr(
            EquipmentGroupSpecificFuelConsumption, "database_version_id"
        ):
            specific_q = specific_q.filter(
                or_(
                    EquipmentGroupSpecificFuelConsumption.database_version_id
                    == effective_db_version,
                    EquipmentGroupSpecificFuelConsumption.database_version_id.is_(None),
                )
            )
        with_specific = {
            int(gid)
            for (gid,) in specific_q.distinct().all()
            if gid is not None
        }
        # Как _latest_specific_row: если с фильтром версии пусто — запасной поиск без версии.
        still_missing = fuel_eg_ids - with_specific
        if still_missing:
            fallback = {
                int(gid)
                for (gid,) in self.session.query(
                    EquipmentGroupSpecificFuelConsumption.equipment_group_id
                )
                .filter(
                    EquipmentGroupSpecificFuelConsumption.equipment_group_id.in_(
                        still_missing
                    ),
                    EquipmentGroupSpecificFuelConsumption.year_number <= cyear,
                )
                .distinct()
                .all()
                if gid is not None
            }
            with_specific |= fallback

        missing_ids = sorted(fuel_eg_ids - with_specific)
        groups_out = _groups_payload(missing_ids)

        return {
            "year_number": cyear,
            "filter_group_count": len(group_ids),
            "calc_fuel_group_count": len(fuel_eg_ids),
            "missing_fuel_count": len(missing_fuel_groups),
            "missing_fuel_groups": missing_fuel_groups,
            "missing_count": len(groups_out),
            "groups": groups_out,
        }

    def run_for_distribution_parameter(
        self,
        distribution_parameter_id: int,
        *,
        commit: bool = True,
    ) -> CoeffStageRunResult:
        row = self.session.get(
            DistributionParameter,
            distribution_parameter_id,
            options=[
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

        effective_db_version = self._resolve_effective_db_version(row)
        group_ids = self._select_group_ids(row, effective_db_version)

        byear = row.base_year.number if row.base_year is not None else None
        cyear = row.year.number
        e_target = d0(row.e)

        by_key = self._fuel_param_by_group_year(
            group_ids, byear, cyear, effective_db_version
        )

        bsumnust = Decimal("0")
        bsume = Decimal("0")
        bsumetp = Decimal("0")
        bsumq = Decimal("0")
        bsumqotr = Decimal("0")

        csumnust = Decimal("0")
        csumnustn = Decimal("0")
        csumnustngt = Decimal("0")
        csumnustnpg = Decimal("0")
        csumetp = Decimal("0")
        csumq = Decimal("0")
        csumqotr = Decimal("0")
        sum_e_cyear = Decimal("0")

        updated_fuel_rows = 0

        for equipment_group_id in group_ids:
            base_row = by_key.get((equipment_group_id, byear)) if byear is not None else None
            cur_row = by_key.get((equipment_group_id, cyear))

            # Базовый год в Access: суммы по всем строкам w с year=byear под фильтром (не только
            # если есть строка расчётного года).
            if base_row is not None:
                bsumnust += d0(base_row.nust)
                bsume += d0(base_row.e)
                bsumetp += d0(base_row.ewtp)
                bsumq += d0(base_row.q)
                bsumqotr += d0(base_row.qotr)

            if cur_row is None:
                continue

            base_nust = d0(base_row.nust) if base_row is not None else Decimal("0")

            # Access: If U.NoMatch Then GoTo Skip — без EWTP и без сумм расчётного года.
            spec = self._latest_specific_row(equipment_group_id, cyear, effective_db_version)
            if spec is None:
                continue

            cur_row.ewtp = d0(cur_row.qotr) * d0(spec.y) / Decimal("1000")
            updated_fuel_rows += 1

            csumnust += d0(cur_row.nust)
            if base_nust == 0:
                n_cur = d0(cur_row.nust)
                csumnustn += n_cur
                oc = _obor_int(cur_row.obor)
                if oc in (20, 90):
                    csumnustngt += n_cur
                if oc in (21, 91):
                    csumnustnpg += n_cur

            csumetp += d0(cur_row.ewtp)
            sum_e_cyear += d0(cur_row.e)
            csumq += d0(cur_row.q)
            csumqotr += d0(cur_row.qotr)

        bnust = bsumnust
        be = bsume
        betp = bsumetp
        bq = bsumq
        bqotr = bsumqotr

        cnust = csumnust
        cnustn = csumnustn
        cnustngt = csumnustngt
        cnustnpg = csumnustnpg
        cnustnps = cnustn - cnustngt - cnustnpg
        cetp = csumetp
        cq = csumq
        cqotr = csumqotr

        bptp = betp / be * Decimal("100") if be > 0 else Decimal("0")
        # Access Кнопка5_Click: cptp = csumetp / E * 100 — E это Ераспред на форме (поле e параметра).
        # Если E не задан (=0), в качестве знаменателя используем ΣE по строкам расчётного года.
        denom_cptp = e_target if e_target > 0 else sum_e_cyear
        cptp = cetp / denom_cptp * Decimal("100") if denom_cptp > 0 else Decimal("0")
        bh = be / bnust * Decimal("1000") if bnust > 0 else Decimal("0")
        ch = e_target / cnust * Decimal("1000") if cnust > 0 else Decimal("0")
        ph1 = ch / bh if bh > 0 else Decimal("0")
        pe = e_target / be if be > 0 else Decimal("0")

        knps, kngt, knpg = _access_k_coefficients_from_h(row, ch)

        hd = Decimal("0")
        if (cnust - cnustn) > 0:
            hd = (
                e_target
                - (cnustnps * knps + cnustngt * kngt + cnustnpg * knpg) * ch / Decimal("1000")
            ) / (cnust - cnustn) * Decimal("1000")

        kn = Decimal("0")
        if cnustn > 0:
            kn = (cnustnps * knps + cnustngt * kngt + cnustnpg * knpg) / cnustn

        ph = hd / bh if bh > 0 else Decimal("0")
        pq = cq / bq if bq > 0 else Decimal("0")
        potr = cqotr / bqotr if bqotr > 0 else Decimal("0")

        summary = (
            self.session.query(DistributionCoefficientSummary)
            .filter_by(
                distribution_parameter_id=row.id,
                year_number=cyear,
                database_version_id=effective_db_version,
            )
            .first()
        )
        if summary is None:
            summary = DistributionCoefficientSummary(
                distribution_parameter_id=row.id,
                year_number=cyear,
                base_year=byear,
                database_version_id=effective_db_version,
            )
            self.session.add(summary)

        summary.bnust = bnust
        summary.be = be
        summary.betp = betp
        summary.bq = bq
        summary.bqotr = bqotr

        summary.cnust = cnust
        summary.cnustn = cnustn
        summary.cnustngt = cnustngt
        summary.cnustnpg = cnustnpg
        summary.cnustnps = cnustnps
        summary.cetp = cetp
        summary.cq = cq
        summary.cqotr = cqotr

        summary.bptp = bptp
        summary.cptp = cptp
        summary.bh = bh
        summary.ch = ch
        summary.ph1 = ph1
        summary.pe = pe
        summary.hd = hd
        summary.kn = kn
        summary.ph = ph
        summary.pq = pq
        summary.potr = potr

        summary.e_target = e_target
        summary.k = d0(row.k)
        summary.kplus = d0(row.kplus)
        summary.kmin = d0(row.kmin)
        summary.knps = knps
        summary.kngt = kngt
        summary.knpg = knpg
        summary.hnps = d0(row.hnps)
        summary.hngt = d0(row.hngt)
        summary.hnpg = d0(row.hnpg)
        summary.doptim = d0(row.doptim)
        summary.lim = d0(row.lim)

        if commit:
            self.session.commit()
        else:
            self.session.flush()

        return CoeffStageRunResult(
            distribution_parameter_id=row.id,
            total_groups=len(group_ids),
            updated_fuel_rows=updated_fuel_rows,
            summary_id=summary.id,
        )

    def compute_base_year_preview_for_distribution_parameter(
        self,
        distribution_parameter_id: int,
    ) -> dict[str, Decimal] | None:
        """
        Агрегаты по базовому году для первой строки таблицы «Коэфф» при загрузке страницы.

        Те же отбор групп и условие «есть строка расчётного года», что в
        ``run_for_distribution_parameter`` (логика Access Кнопка5_Click).
        """
        row = self.session.get(
            DistributionParameter,
            distribution_parameter_id,
            options=[
                joinedload(DistributionParameter.year),
                joinedload(DistributionParameter.base_year),
            ],
        )
        if row is None or row.year is None or row.base_year is None:
            return None

        byear = row.base_year.number
        cyear = row.year.number
        effective_db_version = self._resolve_effective_db_version(row)
        group_ids = self._select_group_ids(row, effective_db_version)
        if not group_ids:
            return None

        by_key = self._fuel_param_by_group_year(
            group_ids, byear, cyear, effective_db_version
        )

        bsumnust = Decimal("0")
        bsume = Decimal("0")
        bsumetp = Decimal("0")
        bsumq = Decimal("0")
        bsumqotr = Decimal("0")
        had_base = False

        for equipment_group_id in group_ids:
            base_row = by_key.get((equipment_group_id, byear))
            if base_row is None:
                continue
            had_base = True
            bsumnust += d0(base_row.nust)
            bsume += d0(base_row.e)
            bsumetp += d0(base_row.ewtp)
            bsumq += d0(base_row.q)
            bsumqotr += d0(base_row.qotr)

        if not had_base:
            return None

        bh = bsume / bsumnust * Decimal("1000") if bsumnust > 0 else Decimal("0")
        bptp = bsumetp / bsume * Decimal("100") if bsume > 0 else Decimal("0")
        return {
            "bnust": bsumnust,
            "be": bsume,
            "betp": bsumetp,
            "bq": bsumq,
            "bqotr": bsumqotr,
            "bh": bh,
            "bptp": bptp,
        }

    def compute_calc_year_preview_for_distribution_parameter(
        self,
        distribution_parameter_id: int,
    ) -> dict[str, Decimal] | None:
        """
        Агрегаты по расчётному году для строки «Расчётный год» и второй таблицы «Коэфф»
        до сохранённой сводки DistributionCoefficientSummary.

        Та же логика сумм и пересчёта теплофикационной выработки ЭЭ (ewtp) по удельному расходу, что в ``run_for_distribution_parameter``,
        без записи в БД.
        """
        row = self.session.get(
            DistributionParameter,
            distribution_parameter_id,
            options=[
                joinedload(DistributionParameter.year),
                joinedload(DistributionParameter.base_year),
            ],
        )
        if row is None or row.year is None:
            return None

        effective_db_version = self._resolve_effective_db_version(row)
        group_ids = self._select_group_ids(row, effective_db_version)
        if not group_ids:
            return None

        byear = row.base_year.number if row.base_year is not None else None
        cyear = row.year.number
        e_target = d0(row.e)

        by_key = self._fuel_param_by_group_year(
            group_ids, byear, cyear, effective_db_version
        )

        csumnust = Decimal("0")
        csumnustn = Decimal("0")
        csumnustngt = Decimal("0")
        csumnustnpg = Decimal("0")
        csumetp = Decimal("0")
        csumq = Decimal("0")
        csumqotr = Decimal("0")
        sum_e_cyear = Decimal("0")

        for equipment_group_id in group_ids:
            base_row = by_key.get((equipment_group_id, byear)) if byear is not None else None
            cur_row = by_key.get((equipment_group_id, cyear))

            if cur_row is None:
                continue

            base_nust = d0(base_row.nust) if base_row is not None else Decimal("0")

            # Access Skip без удельных — не копить суммы расчётного года.
            spec = self._latest_specific_row(equipment_group_id, cyear, effective_db_version)
            if spec is None:
                continue
            ewtp = d0(cur_row.qotr) * d0(spec.y) / Decimal("1000")

            csumnust += d0(cur_row.nust)
            if base_nust == 0:
                n_cur = d0(cur_row.nust)
                csumnustn += n_cur
                oc = _obor_int(cur_row.obor)
                if oc in (20, 90):
                    csumnustngt += n_cur
                if oc in (21, 91):
                    csumnustnpg += n_cur

            csumetp += ewtp
            sum_e_cyear += d0(cur_row.e)
            csumq += d0(cur_row.q)
            csumqotr += d0(cur_row.qotr)

        cnustnps = csumnustn - csumnustngt - csumnustnpg
        cetp = csumetp
        denom_cptp = e_target if e_target > 0 else sum_e_cyear
        cptp = cetp / denom_cptp * Decimal("100") if denom_cptp > 0 else Decimal("0")
        ch = e_target / csumnust * Decimal("1000") if csumnust > 0 else Decimal("0")

        cnust = csumnust
        cnustn = csumnustn
        cnustngt = csumnustngt
        cnustnpg = csumnustnpg
        knps, kngt, knpg = _access_k_coefficients_from_h(row, ch)

        hd = Decimal("0")
        if (cnust - cnustn) > 0:
            hd = (
                e_target
                - (cnustnps * knps + cnustngt * kngt + cnustnpg * knpg) * ch / Decimal("1000")
            ) / (cnust - cnustn) * Decimal("1000")

        kn = Decimal("0")
        if cnustn > 0:
            kn = (cnustnps * knps + cnustngt * kngt + cnustnpg * knpg) / cnustn

        base_preview = self.compute_base_year_preview_for_distribution_parameter(
            distribution_parameter_id
        )
        ph = None
        if base_preview is not None:
            bh_prev = d0(base_preview.get("bh"))
            if bh_prev > 0:
                ph = hd / bh_prev

        return {
            "cnust": cnust,
            "cnustn": cnustn,
            "e_target": e_target,
            "sum_e_cyear": sum_e_cyear,
            "hd": hd,
            "kn": kn,
            "ph": ph,
            "cq": csumq,
            "cqotr": csumqotr,
            "cptp": cptp,
            "cetp": cetp,
            "cnustnps": cnustnps,
            "cnustngt": csumnustngt,
            "cnustnpg": csumnustnpg,
            "ch": ch,
            "hnps": d0(row.hnps),
            "hngt": d0(row.hngt),
            "hnpg": d0(row.hnpg),
            "knps": knps,
            "kngt": kngt,
            "knpg": knpg,
        }
