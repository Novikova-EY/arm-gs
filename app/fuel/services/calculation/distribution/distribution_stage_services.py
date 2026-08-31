# -*- coding: utf-8 -*-
"""
Этап «Распред» для страницы /fuel/calculation.

Порт основной логики Access из обработчика Кнопка27_Click:
- берет агрегаты этапа «Коэфф» по параметру распределения;
- пересчитывает выработку `e` по строкам топлива расчётного года;
- бинарным поиском подбирает коэффициент `k` (или `kn`, если база пустая),
  чтобы сумма `e` приблизилась к целевому Ераспред.

Опционально (флаг apply_restrictions — аналог открытого окна «Анализ_по_областям»):
- берёт kobl из таблицы (как Access при открытой форме; 0/overflow → 1);
- умножает часы на kobl по субъекту (obl) из gs_fue_restrictions;
- после сходимости K пересчитывает kobl по emin/emax (Ограничения_Click)
  и повторяет BDis, пока субъекты вне emin/emax, максимум 14 раз (Access irestr<15).

Access MsgBox «нет NR → HFIX»: в вебе — двухшаговый сценарий на /fuel/calculation
(список кандидатов → фиксация H=0/hfix=1 по выбранным → продолжение Распред).

Как Кнопка27: «Коэфф» не вызывается. Берётся уже сохранённая сводка и EWTP
на станциях (после ручной правки). Нет сводки — ошибка: сначала «Коэфф».
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
from app.fuel.services.calculation.access_bdis_cursor import (
    AccessBdisCursorState,
    fuel_param_access_n1,
    sort_access_filter_rows,
    walk_access_bdis_cursor,
)
from app.fuel.services.calculation.equipment_group_selection import (
    access_ved_filter_year_row_participates,
    select_equipment_group_ids_for_calculation,
)
from app.fuel.services.calculation.specific_consumption_lookup import (
    query_specific_consumption_access_seek,
)
from app.fuel.services.equipment_groups.composite_station_semantics import (
    fuel_param_row_participates,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    hours_from_energy_and_capacity,
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
# Живая Кнопка27 СиПР: новые ГТ — obor 20|90|24|89 → ch·kngt (не knps).
# gs_fue_restrictions.kobl — numeric(36, 16). Access ~0.3–3; больше 100 — срыв цикла.
KOBL_ABS_MAX = Decimal("100")


def clamp_restriction_kobl(kobl: Decimal) -> Decimal:
    """Не даём kobl взорвать numeric(36,16) на повторных проходах BDis."""
    if kobl > KOBL_ABS_MAX:
        return KOBL_ABS_MAX
    if kobl < -KOBL_ABS_MAX:
        return -KOBL_ABS_MAX
    return kobl


def oes_ved_restriction_filter_text(oes_code: int) -> str:
    """Access ecur: вся ОЭС, ved>0, без filter1 параметра."""
    return f"(oes={int(oes_code)}) and (ved>0)"


def restriction_subject_targets_unmet(
    rows: list,
    oes_code: int,
    *,
    tolerance: Decimal = D03,
) -> bool:
    """True, если именованный субъект ещё вне emin/emax (не строка «прочие»)."""
    residual = 100 + int(oes_code)
    for r in rows:
        if r.obl is None or int(r.obl) == residual:
            continue
        emin = d0(getattr(r, "emin", None))
        emax = d0(getattr(r, "emax", None))
        ecur = d0(getattr(r, "ecur", None))
        if emin > 0 and ecur + tolerance < emin:
            return True
        if emax > 0 and ecur > emax + tolerance:
            return True
    return False


def d0(value) -> Decimal:
    if value is None:
        return D0
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def sum_e_of_distribution_processed_rows(
    group_ids: list[int],
    *,
    cyear: int,
    by_key: dict[tuple[int, int], object],
    group_ids_with_specific: set[int],
) -> tuple[Decimal, int]:
    """
    ΣE по тем же строкам, что пишет «Распред»: ved>0 на расчётном годе и есть удельник.

    Превью «Коэфф» иначе включает группы без ТЭП, если EWTP уже задан (импорт/копия года),
    и их старое E ломает допуск «Топливо» после успешного Распред.
    """
    total = D0
    counted = 0
    year_key = int(cyear)
    for gid in group_ids:
        cur_row = by_key.get((int(gid), year_key))
        if not access_ved_filter_year_row_participates(cur_row):
            continue
        if int(gid) not in group_ids_with_specific:
            continue
        counted += 1
        total += d0(getattr(cur_row, "e", None))
    return total, counted


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


def _access_allows_capacity_growth(row: EquipmentGroupFuelParam | None) -> bool:
    """Access: ``z(w!HFIX <> 1)``. Null → z(Null)=0 → прирост мощности выкл."""
    if row is None or getattr(row, "hfix", None) is None:
        return False
    try:
        return int(row.hfix) != 1
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


@dataclass
class NrHfixCandidate:
    """Станция расчётного года: NUST>0, NR=0, HFIX≠1 (Access MsgBox перед calce)."""

    equipment_group_id: int
    name: str
    year_number: int
    nust: Decimal
    nr: Decimal
    h: Decimal | None
    hfix: int | None


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
        years: list[int] = []
        if row.year is not None and getattr(row.year, "number", None) is not None:
            years.append(int(row.year.number))
        if row.base_year is not None and getattr(row.base_year, "number", None) is not None:
            years.append(int(row.base_year.number))
        year_numbers = sorted(set(years)) or None
        return select_equipment_group_ids_for_calculation(
            self.session,
            filter_text=row.filter_text,
            effective_db_version=effective_db_version,
            year_numbers=year_numbers,
        )

    def sum_processed_calc_year_e(
        self,
        *,
        group_ids: list[int],
        cyear: int,
        effective_db_version: int | None,
        byear: int | None = None,
    ) -> tuple[Decimal, int]:
        """ΣE и число строк расчётного года, которые «Распред» реально пишет."""
        by_key = self._fuel_param_by_group_year(
            group_ids=group_ids,
            byear=None,
            cyear=int(cyear),
            effective_db_version=effective_db_version,
        )
        with_specific: set[int] = set()
        for gid in group_ids:
            spec = self._latest_specific_row(
                equipment_group_id=int(gid),
                target_year=int(cyear),
                effective_db_version=effective_db_version,
                byear=byear,
            )
            if spec is not None:
                with_specific.add(int(gid))
        return sum_e_of_distribution_processed_rows(
            group_ids,
            cyear=int(cyear),
            by_key=by_key,
            group_ids_with_specific=with_specific,
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

    def find_nr_hfix_candidates(
        self,
        *,
        distribution_parameter_id: int,
        database_version_id: int | None = None,
    ) -> list[NrHfixCandidate]:
        """
        Access: NUST>0 And NR=0 And HFIX<>1 на расчётном годе (после успешного Seek удельника).
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
            return []

        effective_db_version = self._resolve_effective_db_version(row, database_version_id)
        group_ids = self._select_equipment_group_ids(
            row=row,
            effective_db_version=effective_db_version,
        )
        cyear = int(row.year.number)
        byear = row.base_year.number if row.base_year is not None else None
        by_key = self._fuel_param_by_group_year(
            group_ids=group_ids,
            byear=byear,
            cyear=cyear,
            effective_db_version=effective_db_version,
        )

        pending: list[tuple[int, EquipmentGroupFuelParam]] = []
        for equipment_group_id in group_ids:
            cur_row = by_key.get((equipment_group_id, cyear))
            if not access_ved_filter_year_row_participates(cur_row):
                continue
            if self._latest_specific_row(
                equipment_group_id=equipment_group_id,
                target_year=cyear,
                effective_db_version=effective_db_version,
                byear=byear,
            ) is None:
                continue
            if d0(cur_row.nust) <= 0:
                continue
            # Числовой шум импорта (напр. 8E-16) считаем NR=0, как Access z(NR)=0.
            if abs(d0(cur_row.nr)) > Decimal("1e-9"):
                continue
            if _is_hfix(cur_row):
                continue
            pending.append((equipment_group_id, cur_row))

        # Подпись в блоке «Ррасп = 0» — поле «Название» из «Общая информация»,
        # а не FuelParam.name (там часто старое имя из БД Топливо).
        name_by_id: dict[int, str] = {}
        pending_ids = [gid for gid, _ in pending]
        if pending_ids:
            for gid, name, name_ext in (
                self.session.query(
                    EquipmentGroup.id,
                    EquipmentGroup.name,
                    EquipmentGroup.name_ext,
                )
                .filter(EquipmentGroup.id.in_(pending_ids))
                .all()
            ):
                display = (name or "").strip() or (name_ext or "").strip() or f"id={gid}"
                name_by_id[int(gid)] = display

        candidates: list[NrHfixCandidate] = []
        for equipment_group_id, cur_row in pending:
            candidates.append(
                NrHfixCandidate(
                    equipment_group_id=equipment_group_id,
                    name=name_by_id.get(equipment_group_id) or f"id={equipment_group_id}",
                    year_number=cyear,
                    nust=d0(cur_row.nust),
                    nr=d0(cur_row.nr),
                    h=cur_row.h,
                    hfix=cur_row.hfix,
                )
            )
        return candidates

    def apply_nr_hfix_zero(
        self,
        *,
        distribution_parameter_id: int,
        equipment_group_ids: list[int],
        database_version_id: int | None = None,
        commit: bool = True,
    ) -> int:
        """
        Access MsgBox Yes: w!H = 0, w!HFIX = 1 на расчётном годе.
        Возвращает число обновлённых строк FuelParam.
        """
        if not equipment_group_ids:
            return 0

        row = self.session.get(
            DistributionParameter,
            distribution_parameter_id,
            options=[joinedload(DistributionParameter.year)],
        )
        if row is None or row.year is None:
            raise ValueError(f"Не найдена строка DistributionParameter id={distribution_parameter_id}")

        effective_db_version = self._resolve_effective_db_version(row, database_version_id)
        cyear = int(row.year.number)
        by_key = self._fuel_param_by_group_year(
            group_ids=list(dict.fromkeys(equipment_group_ids)),
            byear=None,
            cyear=cyear,
            effective_db_version=effective_db_version,
        )

        updated = 0
        for eg_id in equipment_group_ids:
            cur_row = by_key.get((eg_id, cyear))
            if cur_row is None:
                continue
            cur_row.h = D0
            cur_row.hfix = 1
            self.session.add(cur_row)
            updated += 1

        if commit:
            self.session.commit()
        else:
            self.session.flush()
        return updated

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
        all_years: bool = False,
    ) -> dict[tuple[int, int], EquipmentGroupFuelParam]:
        if not group_ids:
            return {}

        filters = [EquipmentGroupFuelParam.equipment_group_id.in_(group_ids)]
        if not all_years:
            if byear is not None:
                filters.append(EquipmentGroupFuelParam.year_number.in_([byear, cyear]))
            else:
                filters.append(EquipmentGroupFuelParam.year_number == cyear)

        rows = (
            self.session.query(EquipmentGroupFuelParam)
            .filter(*filters)
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
        byear: int | None = None,
    ) -> EquipmentGroupSpecificFuelConsumption | None:
        return self._bdis_specific_row(
            equipment_group_id=equipment_group_id,
            byear=byear,
            cyear=target_year,
            effective_db_version=effective_db_version,
        )

    def _bdis_specific_row(
        self,
        *,
        equipment_group_id: int,
        byear: int | None,
        cyear: int,
        effective_db_version: int | None,
    ) -> EquipmentGroupSpecificFuelConsumption | None:
        return query_specific_consumption_access_seek(
            self.session,
            equipment_group_id=equipment_group_id,
            byear=byear,
            cyear=cyear,
            database_version_id=effective_db_version,
        )

    @staticmethod
    def _hours_from_fuel_row(
        row: EquipmentGroupFuelParam | None,
        *,
        synthesize_from_e_nust: bool = False,
    ) -> Decimal:
        """
        Часы из строки FuelParam для Распред (база hb и HFIX).

        Access: ``hb = z(w("h"))`` / ``z(w("h"))`` при hfix — NULL→0.
        В АРМ после импорта ``h`` часто пуст при заполненных e/nust; без
        восстановления действующие уходят в ветку «новая» (H=ch·kn*), подбор k
        не на чем крутить, ΣE зависает (типично EWTP·1.04 или ch·kn*).
        Если ``synthesize_from_e_nust`` и h пуст — H = E/NUST·1000
        (как после calce в Access). Для HFIX синтез не используем.
        """
        if row is None:
            return D0
        h = d0(row.h)
        if h > 0:
            return h
        if synthesize_from_e_nust:
            computed = hours_from_energy_and_capacity(row.e, row.nust)
            if computed is not None and computed > 0:
                return computed
        return D0

    @staticmethod
    def _seed_bisection_k(k: Decimal) -> Decimal:
        """
        Access берёт k с формы и ищет в [k−0.1, k+0.1]. После несошедших
        прогонов k уезжает к краю окна (например 0.58) — следующее окно уже
        не покрывает рабочую область ~1. Тогда стартуем с 1.
        """
        if k <= 0 or k < Decimal("0.8") or k > Decimal("1.2"):
            return D1
        return k

    @staticmethod
    def _seed_restriction_kobl(kobl) -> Decimal:
        """Access при открытой форме берёт kobl из таблицы. 0 / overflow → 1."""
        k = d0(kobl)
        if k <= 0 or abs(k) > Decimal("10"):
            return D1
        return k

    @staticmethod
    def _reset_closed_form_restriction_kobl(rows: list) -> None:
        """Access без формы: UPDATE Ограничения SET kobl=1."""
        for restr in rows:
            restr.kobl = D1

    @staticmethod
    def _distribution_bounds_from_ph(ph: Decimal, doptim: Decimal) -> tuple[Decimal, Decimal]:
        if ph > D1 - doptim and ph < D1:
            return ph * 2 - D1, D1
        if ph > D1 and ph < D1 + doptim:
            return D1, ph * 2 - D1
        return ph - doptim, ph + doptim

    @staticmethod
    def _koptim_from_bk(*, bk: Decimal | None, kmin: Decimal, kplus: Decimal) -> Decimal:
        # Access: If U!Bk < 350 / > 550. Null не True и не False → Else, z(Bk)=0.
        if bk is None:
            return kmin + (kplus - kmin) * D275
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
        # Access Кнопка27 (СиПР): 20|90|24|89 → kngt; 21|91 → knpg; иначе knps.
        oc = _obor_int(obor)
        if oc in (20, 90, 24, 89):
            return ch * kngt
        if oc in (21, 91):
            return ch * knpg
        return ch * knps

    @staticmethod
    def _clamp_hours(*, hours: Decimal, hb: Decimal, hd: Decimal) -> Decimal:
        # Access Кнопка27 (СиПР): If hb>7000 And H>hb Then H=hb
        # затем If hb>6500 And hb<7000 And hd<6000 And H>hb*1.05 Then …
        # Else: If H>7000 Then H=7000
        if hb > D7000 and hours > hb:
            hours = hb
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
        hfix: bool = False,
    ) -> Decimal:
        oc = _obor_int(cur_row.obor)
        ewtp = d0(cur_row.ewtp)
        if oc is not None and 8 <= oc <= 10:
            return ewtp

        nust = d0(cur_row.nust)
        # Access: z(w!HFIX <> 1) — Null HFIX не включает формулу прироста
        if _access_allows_capacity_growth(cur_row) and nust > nustb and h_current > ch and nustb > 0:
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
        effective_db_version: int | None = None,
    ) -> None:
        """
        Порт Ограничения_Click: пересчёт ecur/ecurdis/H/Hdis/etp/kobl по emin/emax.

        ecur — ΣE субъекта по ОЭС/ved>0/году текущей версии БД (Access: одна
        рабочая таблица). Без версии сюда попадали копии станций всех версий,
        ecur раздувался в ~8 раз, kobl за 14 проходов BDis переполнял numeric.
        """
        all_oes_ids = select_equipment_group_ids_for_calculation(
            self.session,
            filter_text=oes_ved_restriction_filter_text(int(oes_code)),
            effective_db_version=effective_db_version,
            year_numbers=[int(cyear)],
        )
        all_oes_groups = []
        if all_oes_ids:
            all_oes_groups = (
                self.session.query(EquipmentGroup)
                .filter(EquipmentGroup.id.in_(all_oes_ids))
                .all()
            )
        all_by_key = self._fuel_param_by_group_year(
            group_ids=all_oes_ids,
            byear=None,
            cyear=cyear,
            effective_db_version=effective_db_version,
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
                row = source_map.get((gid, cyear))
                if row is None:
                    continue
                # Access: (ved>0) на рабочей строке года, не vedomstvo справочника.
                if not fuel_param_row_participates(row):
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
            restr.kobl = clamp_restriction_kobl(kobl)
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
                row = all_by_key.get((gid, cyear))
                if row is None:
                    continue
                if not fuel_param_row_participates(row):
                    continue
                sum_e += d0(row.e)
                sum_n += d0(row.nust)
            for gid in filter_group_ids:
                g = groups_by_id.get(gid)
                if g is None or g.obl is None or int(g.obl) in fltr_set:
                    continue
                # Access sumprochdis: (ved>0) and filter1 — FuelParam.ved за год
                row = by_key.get((gid, cyear))
                if row is None:
                    continue
                if not fuel_param_row_participates(row):
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
            residual.kobl = clamp_restriction_kobl(kobl)
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

        # Access Кнопка27 не вызывает Кнопка5: сводка и EWTP уже на форме/в строках.
        coeff_summary = self._load_coeff_summary(
            distribution_parameter_id=row.id,
            cyear=cyear,
            effective_db_version=effective_db_version,
        )
        if coeff_summary is None:
            raise ValueError(
                "Нет сводки этапа «Коэфф» для этого параметра. "
                "Сначала нажмите «Коэфф» (как в Access: Кнопка5, затем Кнопка27). "
                "После Коэфф можно править EWTP на станциях — Распред их не пересчитает."
            )

        by_key = self._fuel_param_by_group_year(
            group_ids=group_ids,
            byear=byear,
            cyear=cyear,
            effective_db_version=effective_db_version,
        )
        cursor_by_key = self._fuel_param_by_group_year(
            group_ids=group_ids,
            byear=byear,
            cyear=cyear,
            effective_db_version=effective_db_version,
            all_years=True,
        )

        groups_by_id: dict[int, EquipmentGroup] = {}
        if group_ids:
            for g in self.session.query(EquipmentGroup).filter(EquipmentGroup.id.in_(group_ids)).all():
                groups_by_id[g.id] = g

        cursor_rows = sort_access_filter_rows(
            [
                fp
                for fp in cursor_by_key.values()
                if access_ved_filter_year_row_participates(fp)
            ],
            n1_of=lambda fp: fuel_param_access_n1(fp, groups_by_id),
        )

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
            # Галочка = форма открыта: kobl из таблицы, как Access RecordsetClone.
            # Не сбрасываем в 1 — иначе 14 проходов с (k эталона, kobl=1)
            # сходятся в другую точку, чем Access. Overflow/0 → 1.
            for restr in restriction_rows:
                restr.kobl = self._seed_restriction_kobl(restr.kobl)
                self.session.add(restr)
            kobl_by_obl = self._kobl_map_from_rows(restriction_rows)
        elif oes_code is not None:
            # Access: форма закрыта → один раз UPDATE kobl=1 WHERE oes=…
            # Срез АРМ: ОЭС + год параметра + версия БД (как при открытой форме).
            closed_rows = self._load_restriction_rows(
                oes_code=oes_code,
                cyear=cyear,
                effective_db_version=effective_db_version,
            )
            self._reset_closed_form_restriction_kobl(closed_rows)
            for restr in closed_rows:
                self.session.add(restr)

        e_target = d0(row.e)
        doptim = d0(row.doptim)
        bnust = d0(coeff_summary.bnust)
        ch = d0(coeff_summary.ch)
        ph = d0(coeff_summary.ph)
        hd = d0(coeff_summary.hd)

        k_value = self._seed_bisection_k(d0(row.k))
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
        # VBA: Dim hb на уровне Кнопка27_Click — живёт через again: и GoTo BDis.
        cursor_state = AccessBdisCursorState()

        for outer in range(1, outer_max + 1):
            restriction_outer_iterations = outer
            k_value = self._seed_bisection_k(k_value)
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

                for kind, cur_row, cursor in walk_access_bdis_cursor(
                    cursor_rows,
                    byear=byear,
                    cyear=cyear,
                    state=cursor_state,
                ):
                    if kind != "cyear":
                        continue
                    equipment_group_id = cur_row.equipment_group_id

                    spec = self._bdis_specific_row(
                        equipment_group_id=equipment_group_id,
                        byear=byear,
                        cyear=cyear,
                        effective_db_version=effective_db_version,
                    )
                    if spec is None:
                        skipped_group_ids.append(equipment_group_id)
                        continue

                    # Access: hb/nustb с курсора filter1 (не Seek по numb этой станции).
                    hb = cursor.hb
                    nustb = cursor.nustb

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
                            bk=spec.bk,
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

            inner_ok = abs(e_target - total_distributed_e) < D03
            if not inner_ok:
                # Не пересчитывать kobl по несходящейся раздаче: emin/ecur →
                # kobl→∞, k→0 за оставшиеся внешние проходы.
                k_value = D1
                continue

            # Access enddis + Ограничения_Click + повтор BDis (irestr<15).
            # Если emin/emax уже выполнены — стоп: лишние проходы с ecur
            # чуть ниже emin домножают kobl и уводят k от эталона Access.
            row.lim = 1
            self._recalculate_restriction_kobl(
                restriction_rows=restriction_rows,
                oes_code=oes_code,  # type: ignore[arg-type]
                cyear=cyear,
                filter_group_ids=set(group_ids),
                lim_reset=False,
                by_key=by_key,
                groups_by_id=groups_by_id,
                effective_db_version=effective_db_version,
            )
            kobl_by_obl = self._kobl_map_from_rows(restriction_rows)
            if not restriction_subject_targets_unmet(restriction_rows, int(oes_code)):
                break

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
        )
