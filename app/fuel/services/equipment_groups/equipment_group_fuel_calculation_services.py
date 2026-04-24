# -*- coding: utf-8 -*-
"""
Расчёт топливной и энергетической части для одной группы оборудования на один год.

Зона ответственности (и только она): выбрать актуальные исходные строки; посчитать
EWTP, EOTP, EUST, EURT, TUST, B; разобрать formtxt; записать значения в
EquipmentGroupFuelParam и EquipmentGroupExtraFuelParam.

Здесь нет UI, территориальных фильтров, запуска по параметру распределения, JSON и шаблонов.
Перенос полей между годами — отдельная управленческая логика, не этот сервис.

Вход: EquipmentGroupFuelParam (базовые e, q, …), EquipmentGroupSpecificFuelConsumption,
EquipmentGroupFuelFormula (formtxt), EquipmentGroupExtraFuelParam.
Выход: обновление EquipmentGroupFuelParam и EquipmentGroupExtraFuelParam.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Dict

from sqlalchemy.orm import Session

from app.extensions import db
from app.common.services.database_version_filter import get_current_db_version_id
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import EquipmentGroupExtraFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_fuel_formula_model import EquipmentGroupFuelFormula
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption,
)

# Основные «газ/мазут/…» — только поля, которые есть в EquipmentGroupFuelParam
TOPLS = frozenset({"gaz", "isk_gaz", "mazut", "torf", "slan", "proch"})

# Углеводородные агрегаты на основной записи (кроме ugol — он считается суммой)
UGLI = frozenset(
    {
        "don",
        "podm",
        "pech",
        "arkt",
        "kuzn",
        "ural",
        "bashk",
        "kazah",
        "kan",
        "tung",
        "irkut",
        "hak",
        "tuv",
        "bur",
        "chit",
        "yakut",
        "amur",
        "urg",
        "ushum",
        "prim",
        "mag",
        "chukot",
        "kamch",
        "sah",
        "ugol",
    }
)

# Детальные поля «Доп_угли» — EquipmentGroupExtraFuelParam (+ sosv, luch, tal при наличии колонок)
UGLI1 = frozenset(
    {
        "nazar",
        "ibor",
        "berez",
        "per",
        "irbei",
        "kansk",
        "gusin",
        "tugn",
        "okino",
        "azey",
        "mug",
        "cher",
        "jer",
        "karab",
        "har",
        "urt",
        "tataur",
        "tarbag",
        "zab_kam",
        "vork",
        "intin",
        "sver",
        "chel",
        "kizel",
        "sosv",
        "neru",
        "zyryan",
        "pyak",
        "rai",
        "erk",
        "ogodj",
        "svo",
        "bikin",
        "razdol",
        "hankai",
        "bering",
        "anad",
        "ekib",
        "maikub",
        "karag",
        "karajyra",
        "teniz",
        "kuznt",
        "kuzngd",
        "kuznss",
        "kuznun",
        "gaz_prir",
        "gazpp",
        "disel",
        "maztop",
        "nft_proch",
        "koks_g",
        "domen_g",
        "prochgaz",
        "szh_gaz",
        "inoe",
        "tvproch",
        "luch",
        "tal",
    }
)

FUEL_PARAM_CARRY_FIELDS = (
    "name",
    "numb1120",
    "numb1",
    "obor",
    "ved",
    "ved_cyrillic",
    "obl",
    "dep",
    "oes",
    "ees",
    "er",
    "gk",
    "be",
    "nust",
    "nr",
    "e",
    "q",
    "qotr",
    "turt",
    "snk",
    "sn_t",
    "nt",
    "nt_sum",
)

EXTRA_FUEL_PARAM_CARRY_FIELDS = (
    "name",
    "numb1120",
    "numb1",
)

GROUPS = {
    "pech": ["intin", "vork"],
    "kuzn": ["kuznt", "kuznss", "kuzngd", "kuznun"],
    "kan": ["nazar", "ibor", "berez", "per", "irbei", "kansk"],
    "ural": ["sver", "chel", "kizel", "sosv"],
    "irkut": ["azey", "mug", "cher"],
    "bur": ["gusin", "tugn", "okino"],
    "chit": ["har", "urt", "tataur", "tarbag", "zab_kam"],
    "yakut": ["neru", "pyak", "zyryan"],
    "amur": ["rai", "erk", "svo", "ogodj"],
    "gaz": ["gaz_prir", "gazpp"],
    "mazut": ["disel", "maztop", "nft_proch"],
    "isk_gaz": ["koks_g", "prochgaz", "domen_g"],
    "proch": ["szh_gaz", "inoe", "tvproch"],
    "tung": ["jer", "karab"],
    "prim": ["bikin", "razdol", "hankai"],
    "chukot": ["bering", "anad"],
    "kazah": ["ekib", "maikub", "karag", "karajyra", "teniz"],
}


def d0(value) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def parse_decimal_text(value: str | None) -> Decimal:
    if value is None:
        return Decimal("0")
    text = str(value).strip().replace(",", ".")
    if not text:
        return Decimal("0")
    return Decimal(text)


@dataclass
class ParsedFuelFormula:
    main_values: Dict[str, Decimal] = field(default_factory=dict)
    extra_values: Dict[str, Decimal] = field(default_factory=dict)
    used_names: set[str] = field(default_factory=set)
    residual_name: str | None = None


def collect_fuel_names_from_formtxt(formtxt: str) -> list[str]:
    """
    Имена типов топлива из formtxt (нижний регистр), порядок первого вхождения в строке.
    Согласовано с _parse_formtxt: токены «имя=доля» и остаточное имя без «=».
    """
    if not formtxt or not str(formtxt).strip():
        return []
    parts = [p.strip() for p in str(formtxt).split(";") if p.strip()]
    names: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if "=" in part:
            raw_name, _ = part.split("=", 1)
            name = raw_name.strip().lower()
            if not name:
                continue
            if name.startswith("/"):
                name = name[1:].strip().lower()
                if not name:
                    continue
        else:
            name = part.strip().lower()
            if not name:
                continue
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


class EquipmentGroupFuelCalculationService:
    def __init__(self, session: Session | None = None):
        self.session = session or db.session

    def _resolve_db_version_for_fuel_rows(
        self,
        equipment_group_id: int,
        explicit_database_version_id: int | None,
    ) -> int | None:
        """
        Единое правило для строк параметров топлива: явная версия; иначе текущая
        версия сессии; иначе версия группы оборудования; иначе NULL.
        """
        if explicit_database_version_id is not None:
            return explicit_database_version_id
        vid = get_current_db_version_id()
        if vid is not None:
            return vid
        eg = (
            self.session.query(EquipmentGroup)
            .filter(EquipmentGroup.id == equipment_group_id)
            .one_or_none()
        )
        if eg is not None and eg.database_version_id is not None:
            return eg.database_version_id
        return None

    @staticmethod
    def _copy_missing_attrs(target, source, attrs: tuple[str, ...]) -> None:
        """.. deprecated:: Вместе с переносом полей между годами; не используется в расчёте."""
        if target is None or source is None:
            return
        for attr in attrs:
            if getattr(target, attr, None) is None:
                value = getattr(source, attr, None)
                if value is not None:
                    setattr(target, attr, value)

    @staticmethod
    def _row_has_any_payload(row, attrs: tuple[str, ...]) -> bool:
        if row is None:
            return False
        return any(getattr(row, attr, None) is not None for attr in attrs)

    def _ensure_fuel_row_db_version(
        self,
        equipment_group_id: int,
        row,
        explicit_database_version_id: int | None = None,
    ) -> None:
        """
        Заполняет database_version_id у строки параметров, если NULL — иначе JOIN
        в get_equipment_groups_with_fuel_params_data не находит запись (прочерки в таблицах).
        Правило версии — см. _resolve_db_version_for_fuel_rows.
        """
        if row is None or getattr(row, "database_version_id", None) is not None:
            return
        vid = self._resolve_db_version_for_fuel_rows(equipment_group_id, explicit_database_version_id)
        if vid is not None:
            row.database_version_id = vid

    def _stamp_fuel_param_rows_version(
        self,
        *,
        equipment_group_id: int,
        fuel_param: EquipmentGroupFuelParam,
        extra_param: EquipmentGroupExtraFuelParam,
        formula_database_version_id: int | None,
    ) -> None:
        """
        После расчёта фиксирует database_version_id у строк параметров
        по единому правилу (_resolve_db_version_for_fuel_rows).
        """
        vid = self._resolve_db_version_for_fuel_rows(equipment_group_id, formula_database_version_id)
        if vid is not None:
            fuel_param.database_version_id = vid
            extra_param.database_version_id = vid

    def calculate_group_year(
        self,
        *,
        equipment_group_id: int,
        year_number: int,
        database_version_id: int | None = None,
        variant_number: int = 0,
        strict_formula_validation: bool = False,
        commit: bool = False,
    ) -> EquipmentGroupFuelParam:
        """
        Рассчитывает топливную и энергетическую часть для одной группы оборудования на один год.

        ВАЖНО:
        - не копирует payload из прошлых лет;
        - использует только текущую строку fuel_param на год расчёта;
        - для удельных и формулы берет последнюю доступную запись
          с year_number <= target_year.
        """
        fuel_param = self._get_or_create_fuel_param(
            equipment_group_id=equipment_group_id,
            year_number=year_number,
        )
        extra_param = self._get_or_create_extra_param(
            equipment_group_id=equipment_group_id,
            year_number=year_number,
        )

        effective_db_version = database_version_id
        if effective_db_version is None:
            effective_db_version = get_current_db_version_id()

        consumption = self._select_actual_consumption_row(
            equipment_group_id=equipment_group_id,
            target_year=year_number,
            database_version_id=effective_db_version,
        )
        formula = self._select_actual_formula_row(
            equipment_group_id=equipment_group_id,
            target_year=year_number,
            variant_number=variant_number,
            database_version_id=effective_db_version,
        )

        # 1. Энергетический блок
        self._calculate_energy_part(
            fuel_param=fuel_param,
            consumption=consumption,
        )

        # 2. Перед разбором formtxt очищаем только расчетные топливные колонки
        self._reset_main_fuel_fields(fuel_param)
        self._reset_extra_fuel_fields(extra_param)

        # 3. Разбор формулы топлива
        if formula and formula.formtxt:
            parsed = self._parse_formtxt(
                formtxt=formula.formtxt,
                total_b=d0(fuel_param.b),
                strict=strict_formula_validation,
            )
            self._apply_parsed_values(
                fuel_param=fuel_param,
                extra_param=extra_param,
                parsed=parsed,
            )
            self._aggregate_main_fuels(
                fuel_param=fuel_param,
                extra_param=extra_param,
            )

        # 4. Фиксируем database_version_id у целевых строк
        self._stamp_fuel_param_rows_version(
            equipment_group_id=equipment_group_id,
            fuel_param=fuel_param,
            extra_param=extra_param,
            formula_database_version_id=effective_db_version,
        )

        if commit:
            self.session.add(fuel_param)
            self.session.add(extra_param)
            self.session.commit()

        return fuel_param

    # LEGACY:
    # автоперенос значений из предыдущих лет временно отключен,
    # так как он смешивает подготовку данных и собственно расчет топлива.
    # При необходимости будет вынесен в отдельный сервис подготовки параметров распределения.

    def _seed_target_rows_from_previous_years(
        self,
        *,
        equipment_group_id: int,
        year_number: int,
        fuel_param: EquipmentGroupFuelParam,
        extra_param: EquipmentGroupExtraFuelParam,
    ) -> None:
        """
        .. deprecated::
            Не вызывается из calculate_group_year. Перенос полей между годами —
            отдельная подготовка данных, не расчёт топлива. Оставлено для возможного
            вынесения в отдельный сервис.
        """
        warnings.warn(
            "_seed_target_rows_from_previous_years is deprecated; do not use from new code",
            DeprecationWarning,
            stacklevel=2,
        )
        source_fuel = self._select_source_fuel_param_row(
            equipment_group_id=equipment_group_id,
            target_year=year_number,
            current_row_id=getattr(fuel_param, "id", None),
        )
        if source_fuel is not None:
            self._copy_missing_attrs(
                fuel_param,
                source_fuel,
                FUEL_PARAM_CARRY_FIELDS,
            )
            self._copy_missing_attrs(
                extra_param,
                source_fuel,
                EXTRA_FUEL_PARAM_CARRY_FIELDS,
            )

        source_extra = self._select_source_extra_param_row(
            equipment_group_id=equipment_group_id,
            target_year=year_number,
            current_row_id=getattr(extra_param, "id", None),
        )
        if source_extra is not None:
            self._copy_missing_attrs(
                extra_param,
                source_extra,
                EXTRA_FUEL_PARAM_CARRY_FIELDS,
            )

    def _get_or_create_fuel_param(
        self,
        *,
        equipment_group_id: int,
        year_number: int,
    ) -> EquipmentGroupFuelParam:
        row = (
            self.session.query(EquipmentGroupFuelParam)
            .filter(
                EquipmentGroupFuelParam.equipment_group_id == equipment_group_id,
                EquipmentGroupFuelParam.year_number == year_number,
            )
            .one_or_none()
        )
        if row:
            self._ensure_fuel_row_db_version(equipment_group_id, row)
            return row

        row = EquipmentGroupFuelParam(
            equipment_group_id=equipment_group_id,
            year_number=year_number,
        )
        self.session.add(row)
        self.session.flush()
        self._ensure_fuel_row_db_version(equipment_group_id, row)
        return row

    def _select_source_fuel_param_row(
        self,
        *,
        equipment_group_id: int,
        target_year: int,
        current_row_id: int | None = None,
    ) -> EquipmentGroupFuelParam | None:
        """.. deprecated:: Только для устаревшего _seed_target_rows_from_previous_years."""
        rows = (
            self.session.query(EquipmentGroupFuelParam)
            .filter(
                EquipmentGroupFuelParam.equipment_group_id == equipment_group_id,
                EquipmentGroupFuelParam.year_number <= target_year,
            )
            .order_by(EquipmentGroupFuelParam.year_number.desc())
            .all()
        )
        for row in rows:
            if current_row_id is not None and getattr(row, "id", None) == current_row_id:
                continue
            if self._row_has_any_payload(row, FUEL_PARAM_CARRY_FIELDS):
                return row
        return None

    def _get_or_create_extra_param(
        self,
        *,
        equipment_group_id: int,
        year_number: int,
    ) -> EquipmentGroupExtraFuelParam:
        row = (
            self.session.query(EquipmentGroupExtraFuelParam)
            .filter(
                EquipmentGroupExtraFuelParam.equipment_group_id == equipment_group_id,
                EquipmentGroupExtraFuelParam.year_number == year_number,
            )
            .one_or_none()
        )
        if row:
            self._ensure_fuel_row_db_version(equipment_group_id, row)
            return row

        row = EquipmentGroupExtraFuelParam(
            equipment_group_id=equipment_group_id,
            year_number=year_number,
        )
        self.session.add(row)
        self.session.flush()
        self._ensure_fuel_row_db_version(equipment_group_id, row)
        return row

    def _select_source_extra_param_row(
        self,
        *,
        equipment_group_id: int,
        target_year: int,
        current_row_id: int | None = None,
    ) -> EquipmentGroupExtraFuelParam | None:
        """.. deprecated:: Только для устаревшего _seed_target_rows_from_previous_years."""
        rows = (
            self.session.query(EquipmentGroupExtraFuelParam)
            .filter(
                EquipmentGroupExtraFuelParam.equipment_group_id == equipment_group_id,
                EquipmentGroupExtraFuelParam.year_number <= target_year,
            )
            .order_by(EquipmentGroupExtraFuelParam.year_number.desc())
            .all()
        )
        for row in rows:
            if current_row_id is not None and getattr(row, "id", None) == current_row_id:
                continue
            if self._row_has_any_payload(row, EXTRA_FUEL_PARAM_CARRY_FIELDS):
                return row
        return None

    def _select_actual_consumption_row(
        self,
        *,
        equipment_group_id: int,
        target_year: int,
        database_version_id: int | None = None,
    ) -> EquipmentGroupSpecificFuelConsumption | None:
        q = self.session.query(EquipmentGroupSpecificFuelConsumption).filter(
            EquipmentGroupSpecificFuelConsumption.equipment_group_id == equipment_group_id,
            EquipmentGroupSpecificFuelConsumption.year_number <= target_year,
        )

        if database_version_id is not None:
            q = q.filter(
                (EquipmentGroupSpecificFuelConsumption.database_version_id == database_version_id)
                | (EquipmentGroupSpecificFuelConsumption.database_version_id.is_(None))
            )
        else:
            current_vid = get_current_db_version_id()
            if current_vid is not None:
                q = q.filter(
                    (EquipmentGroupSpecificFuelConsumption.database_version_id == current_vid)
                    | (EquipmentGroupSpecificFuelConsumption.database_version_id.is_(None))
                )

        return q.order_by(
            EquipmentGroupSpecificFuelConsumption.year_number.desc()
        ).first()

    def _select_actual_formula_row(
        self,
        *,
        equipment_group_id: int,
        target_year: int,
        variant_number: int,
        database_version_id: int | None = None,
    ) -> EquipmentGroupFuelFormula | None:
        q = self.session.query(EquipmentGroupFuelFormula).filter(
            EquipmentGroupFuelFormula.equipment_group_id == equipment_group_id,
            EquipmentGroupFuelFormula.year_number <= target_year,
            EquipmentGroupFuelFormula.variant_number == variant_number,
        )

        if database_version_id is not None:
            q = q.filter(
                (EquipmentGroupFuelFormula.database_version_id == database_version_id)
                | (EquipmentGroupFuelFormula.database_version_id.is_(None))
            )
        else:
            current_vid = get_current_db_version_id()
            if current_vid is not None:
                q = q.filter(
                    (EquipmentGroupFuelFormula.database_version_id == current_vid)
                    | (EquipmentGroupFuelFormula.database_version_id.is_(None))
                )

        return q.order_by(EquipmentGroupFuelFormula.year_number.desc()).first()

    def _calculate_energy_part(
        self,
        *,
        fuel_param: EquipmentGroupFuelParam,
        consumption: EquipmentGroupSpecificFuelConsumption | None,
    ) -> None:
        """
        Энергетический блок расчета.
        Порт логики Access-модуля: расчет EWTP, EOTP, EUST, EURT, TUST и B
        по текущей строке параметров группы и актуальной строке удельных показателей.
        """
        if consumption is None:
            return

        qotr = d0(fuel_param.qotr)
        e = d0(fuel_param.e)
        q = d0(fuel_param.q)
        turt = d0(fuel_param.turt)

        y = d0(consumption.y)
        snk = d0(consumption.snk)
        sntp = d0(consumption.sntp)
        bk = d0(consumption.bk)
        btp = d0(consumption.btp)

        ewtp = qotr * y / Decimal("1000")
        ekotp = (e - ewtp) * (Decimal("1") - snk / Decimal("100"))
        etpotp = ewtp * sntp
        eotp = ekotp + etpotp
        eust = (ekotp * bk + etpotp * btp) / Decimal("1000")
        eurt = eust / eotp * Decimal("1000") if eotp != 0 else Decimal("0")
        tust = q * turt / Decimal("1000")
        b = eust + tust

        fuel_param.ewtp = ewtp
        fuel_param.eotp = eotp
        fuel_param.eust = eust
        fuel_param.eurt = eurt
        fuel_param.tust = tust
        fuel_param.b = b

    def _parse_formtxt(
        self,
        *,
        formtxt: str,
        total_b: Decimal,
        strict: bool = False,
    ) -> ParsedFuelFormula:
        result = ParsedFuelFormula()

        if not formtxt or not str(formtxt).strip():
            return result

        parts = [p.strip() for p in str(formtxt).split(";") if p.strip()]
        remaining = total_b

        for part in parts:
            lev_from_rest = False

            if "=" in part:
                raw_name, raw_value = part.split("=", 1)
                name = raw_name.strip().lower()

                if not name:
                    if strict:
                        raise ValueError(f"Пустое имя топлива в token={part!r}")
                    continue

                if name.startswith("/"):
                    lev_from_rest = True
                    name = name[1:].strip().lower()
                    if not name:
                        if strict:
                            raise ValueError(f"Пустое имя топлива после '/' в token={part!r}")
                        continue

                try:
                    pct = parse_decimal_text(raw_value)
                except Exception as exc:
                    if strict:
                        raise ValueError(f"Не удалось разобрать число в token={part!r}: {exc}") from exc
                    continue

                base = remaining if lev_from_rest else total_b
                value = base * pct / Decimal("100")
                remaining -= value

                if strict and remaining < Decimal("0"):
                    raise ValueError(
                        f"Формула распределяет больше 100% топлива: token={part!r}, "
                        f"remaining={remaining}"
                    )

                result.used_names.add(name)
                if name in UGLI1:
                    result.extra_values[name] = value
                else:
                    result.main_values[name] = value

            else:
                name = part.strip().lower()
                if not name:
                    if strict:
                        raise ValueError(f"Пустой остаточный token={part!r}")
                    continue
                result.residual_name = name

        if result.residual_name:
            result.used_names.add(result.residual_name)
            if result.residual_name in UGLI1:
                result.extra_values[result.residual_name] = remaining
            else:
                result.main_values[result.residual_name] = remaining

        return result

    def _apply_parsed_values(
        self,
        *,
        fuel_param: EquipmentGroupFuelParam,
        extra_param: EquipmentGroupExtraFuelParam,
        parsed: ParsedFuelFormula,
    ) -> None:
        for field_name, value in parsed.main_values.items():
            if hasattr(fuel_param, field_name):
                setattr(fuel_param, field_name, value)

        for field_name, value in parsed.extra_values.items():
            if hasattr(extra_param, field_name):
                setattr(extra_param, field_name, value)

    def _aggregate_main_fuels(
        self,
        *,
        fuel_param: EquipmentGroupFuelParam,
        extra_param: EquipmentGroupExtraFuelParam,
    ) -> None:
        """
        Отдельный этап после formtxt: укрупнённые группы на основной записи из extra_param,
        затем ugol как сумма угольных полей (кроме самого ugol). Энергобаланс не трогает.
        """
        for group_name, children in GROUPS.items():
            total = sum(
                (d0(getattr(extra_param, child, None)) for child in children),
                Decimal("0"),
            )
            if hasattr(fuel_param, group_name):
                setattr(fuel_param, group_name, total)

        sum_ugol = Decimal("0")
        for field_name in UGLI:
            if field_name == "ugol":
                continue
            sum_ugol += d0(getattr(fuel_param, field_name, None))
        fuel_param.ugol = sum_ugol

    def _reset_main_fuel_fields(self, fuel_param: EquipmentGroupFuelParam) -> None:
        for field_name in TOPLS | UGLI:
            if hasattr(fuel_param, field_name):
                setattr(fuel_param, field_name, Decimal("0"))

    def _reset_extra_fuel_fields(self, extra_param: EquipmentGroupExtraFuelParam) -> None:
        for field_name in UGLI1:
            if hasattr(extra_param, field_name):
                setattr(extra_param, field_name, Decimal("0"))
