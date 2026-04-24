# -*- coding: utf-8 -*-
"""Пересчёт ТЭП в цены текущего года и сервисы ``TepPriceConversionCoefficient``.

- Пересчёт столбцов «капзатраты без ПИР» и удельных показателей (тыс. руб./кВт) в строке ТЭП
  (ГЭС, ГАЭС и др.) по коэффициентам по годам.
- Снимок коэффициентов для модального UI, карта «номер года → коэффициент», создание /
  изменение / удаление записей справочника для текущей версии БД.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Iterable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.common.services.database_version_services import get_current_version
from app.common.services.get_services.years.years_get_services import get_year_list_full
from app.generation.prospective_places.models.tep_price_conversion_coefficient_model import (
    TepPriceConversionCoefficient,
)
from app.refdata.models.years.year_model import Year

# Ключ в dict для таблицы/Excel; атрибут суммы на ORM; атрибут relationship Year
TEP_CAPITAL_COST_WO_PIR_FIELD_TRIPLES: tuple[tuple[str, str, str], ...] = (
    (
        "capital_cost_wo_pir_total_million_rub",
        "capital_cost_wo_pir_total_million_rub",
        "year_capital_cost_wo_pir_total",
    ),
    (
        "capital_cost_wo_pir_ges_with_reservoir_million_rub",
        "capital_cost_wo_pir_ges_with_reservoir_million_rub",
        "year_capital_cost_wo_pir_ges_with_reservoir",
    ),
    (
        "capital_cost_wo_pir_svm_million_rub",
        "capital_cost_wo_pir_svm_million_rub",
        "year_capital_cost_wo_pir_svm",
    ),
)


def fmt_numeric_million_rub(val: Any) -> str:
    """Млн руб для таблицы ТЭП: целое число в отображении."""
    if val is None:
        return "—"
    try:
        d = Decimal(str(val))
        return str(int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
    except (InvalidOperation, ValueError, TypeError):
        s = (str(val) or "").strip()
        return s.replace(".", ",") if s else "—"


def multiplier_price_year_to_current_year(
    price_year: int | None,
    target_year: int | None,
    coeff_by_year: dict[int, Decimal],
) -> Decimal | None:
    """
    Произведение коэффициентов за годы (год_цены + 1) … текущий_год включительно.
    Если какого-то коэффициента нет в справочнике — None (показываем исходную сумму).
    """
    if target_year is None or price_year is None:
        return None
    py = int(price_year)
    ty = int(target_year)
    if py >= ty:
        return Decimal(1)
    prod = Decimal(1)
    for y in range(py + 1, ty + 1):
        c = coeff_by_year.get(y)
        if c is None:
            return None
        prod *= c
    return prod


def fmt_thousand_rub_per_kw_scaled(
    raw_val: Any,
    year_obj,
    target_year: int | None,
    coeff_by_year: dict[int, Decimal],
) -> str:
    """
    Пересчёт удельного показателя (тыс. руб./кВт) из года привязки цены в ``target_year``.
    Та же цепочка коэффициентов, что для сумм в млн руб.
    """
    if raw_val is None:
        return "—"
    s0 = str(raw_val).strip()
    if not s0:
        return "—"
    m = multiplier_price_year_to_current_year(
        year_obj.number if year_obj is not None else None,
        target_year,
        coeff_by_year,
    )
    if m is None:
        return s0.replace(".", ",")
    try:
        d = Decimal(s0.replace(",", "."))
    except (InvalidOperation, ValueError, TypeError):
        t = s0.replace(".", ",")
        return t if t else "—"
    try:
        q = (d * m).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ZeroDivisionError):
        return s0.replace(".", ",")
    s = format(q, "f").rstrip("0").rstrip(".")
    return s.replace(".", ",") if s else "—"


def fmt_million_rub_scaled(
    raw_val: Any,
    year_obj,
    target_year: int | None,
    coeff_by_year: dict[int, Decimal],
) -> str:
    """Пересчёт одной суммы (млн руб) из года цены в target_year."""
    m = multiplier_price_year_to_current_year(
        year_obj.number if year_obj is not None else None,
        target_year,
        coeff_by_year,
    )
    if m is None:
        return fmt_numeric_million_rub(raw_val)
    if raw_val is None:
        return "—"
    try:
        d = Decimal(str(raw_val)) * m
        return str(int(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP)))
    except (InvalidOperation, ValueError, TypeError):
        return fmt_numeric_million_rub(raw_val)


def _parse_mw_decimal(installed_capacity_raw: Any) -> Decimal | None:
    """Мощность из строкового поля ТЭП (МВт)."""
    if installed_capacity_raw is None:
        return None
    s = str(installed_capacity_raw).strip()
    if not s:
        return None
    s = s.replace(",", ".")
    try:
        d = Decimal(s)
    except (InvalidOperation, ValueError, TypeError):
        return None
    if d <= 0:
        return None
    return d


def _effective_capital_ges_with_reservoir_million_rub(
    r: Any,
    target_year: int | None,
    coeff_by_year: dict[int, Decimal],
) -> Decimal | None:
    """Млн руб «в т.ч. здания…» с тем же пересчётом в цены года, что и столбец капзатрат."""
    raw = getattr(r, "capital_cost_wo_pir_ges_with_reservoir_million_rub", None)
    if raw is None:
        return None
    try:
        base = Decimal(str(raw))
    except (InvalidOperation, ValueError, TypeError):
        return None
    year_obj = getattr(r, "year_capital_cost_wo_pir_ges_with_reservoir", None)
    if not target_year:
        return base
    m = multiplier_price_year_to_current_year(
        year_obj.number if year_obj is not None else None,
        target_year,
        coeff_by_year,
    )
    if m is None:
        return base
    return base * m


def fmt_specific_capital_investment_thous_rub_per_kw_derived(
    r: Any,
    *,
    installed_capacity_attr: str,
    target_year: int | None = None,
    coeff_by_year: dict[int, Decimal] | None = None,
) -> str:
    """
    Удельные капвложения (тыс. руб./кВт) = капзатраты «в т.ч. здания… ГЭС/ГАЭС», млн руб
    / установленная мощность (МВт). Совпадает с единицами: млн руб / МВт = тыс. руб./кВт.
    """
    coeff = coeff_by_year or {}
    ges_m = _effective_capital_ges_with_reservoir_million_rub(r, target_year, coeff)
    mw = _parse_mw_decimal(getattr(r, installed_capacity_attr, None))
    if ges_m is None or mw is None:
        return "—"
    try:
        q = (ges_m / mw).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ZeroDivisionError):
        return "—"
    s = format(q, "f").rstrip("0").rstrip(".")
    return s.replace(".", ",") if s else "—"


def rows_match_for_scaled_specific_semifixed_operating_costs(
    group: list[Any],
    *,
    target_year: int | None,
    coeff_by_year: dict[int, Decimal] | None,
) -> bool:
    """Совпадение отображаемых удельных эксплуатационных затрат после пересчёта в цены года."""
    if len(group) <= 1:
        return True
    coeff = coeff_by_year or {}
    first = fmt_thousand_rub_per_kw_scaled(
        getattr(group[0], "specific_semifixed_operating_costs_thous_rub_per_kw", None),
        getattr(group[0], "year_specific_semifixed_operating_costs", None),
        target_year,
        coeff,
    )
    for r in group[1:]:
        v = fmt_thousand_rub_per_kw_scaled(
            getattr(r, "specific_semifixed_operating_costs_thous_rub_per_kw", None),
            getattr(r, "year_specific_semifixed_operating_costs", None),
            target_year,
            coeff,
        )
        if v != first:
            return False
    return True


def rows_match_for_derived_specific_capital_investment(
    group: list[Any],
    *,
    target_year: int | None,
    coeff_by_year: dict[int, Decimal] | None,
) -> bool:
    """Совпадение отображаемых удельных капвложений (расчёт по капзатратам и мощности) в группе строк."""
    if len(group) <= 1:
        return True
    first_r = group[0]
    attr0 = installed_capacity_attr_for_tep_row(first_r)
    first_val = fmt_specific_capital_investment_thous_rub_per_kw_derived(
        first_r,
        installed_capacity_attr=attr0,
        target_year=target_year,
        coeff_by_year=coeff_by_year,
    )
    for r in group[1:]:
        attr = installed_capacity_attr_for_tep_row(r)
        v = fmt_specific_capital_investment_thous_rub_per_kw_derived(
            r,
            installed_capacity_attr=attr,
            target_year=target_year,
            coeff_by_year=coeff_by_year,
        )
        if v != first_val:
            return False
    return True


def installed_capacity_attr_for_tep_row(r: Any) -> str:
    """ГЭС: installed_capacity_mw; ГАЭС: установленная мощность в генераторном режиме (всего)."""
    if hasattr(r, "installed_capacity_mw_generator_mode"):
        return "installed_capacity_mw_generator_mode"
    return "installed_capacity_mw"


def resolve_year_id_for_calendar_year_number(year_number: int | None) -> int | None:
    """Идентификатор записи Year в текущей версии БД по календарному году."""
    if year_number is None:
        return None
    from app.common.services.database_version_services import get_current_version
    from app.refdata.models.years.year_model import Year

    vid = get_current_version()
    if not vid:
        return None
    y = (
        Year.query.filter_by(database_version_id=vid, number=int(year_number))
        .limit(1)
        .first()
    )
    return y.id if y else None


def apply_derived_specific_capital_investment_to_ges_tep_source_row(row: Any) -> None:
    """
    Записывает удельные капиталовложения и год привязки для строки ТЭП ГЭС (модель без «генераторного режима»):
    капзатраты «ГЭС (с водохранилищем)» / установленная мощность, пересчёт в цены года ТЭП.
    """
    from app.common.services.get_services.years.years_get_services import (
        get_ges_tep_current_price_year_number,
    )

    coeff = get_tep_price_coefficient_by_year_map()
    ty = get_ges_tep_current_price_year_number()
    s = fmt_specific_capital_investment_thous_rub_per_kw_derived(
        row,
        installed_capacity_attr="installed_capacity_mw",
        target_year=ty,
        coeff_by_year=coeff,
    )
    row.specific_capital_investment_thous_rub_per_kw = None if s == "—" else s
    row.id_year_specific_capital_investment = resolve_year_id_for_calendar_year_number(ty)


def apply_derived_specific_capital_investment_to_gaes_tep_source_row(row: Any) -> None:
    """
    Записывает удельные капиталовложения и год привязки по той же формуле, что и таблица ТЭП
    (капзатраты «здания…» / мощность генераторного режима, пересчёт в цены года ТЭП).
    Год для удельных капвложений совпадает с годом предоставления информации по строке
    «здания, сооружения, оборудование и бассейнами ГАЭС».
    """
    from app.common.services.get_services.years.years_get_services import (
        get_ges_tep_current_price_year_number,
    )

    coeff = get_tep_price_coefficient_by_year_map()
    ty = get_ges_tep_current_price_year_number()
    s = fmt_specific_capital_investment_thous_rub_per_kw_derived(
        row,
        installed_capacity_attr="installed_capacity_mw_generator_mode",
        target_year=ty,
        coeff_by_year=coeff,
    )
    row.specific_capital_investment_thous_rub_per_kw = None if s == "—" else s
    row.id_year_specific_capital_investment = row.id_year_capital_cost_wo_pir_ges_with_reservoir


def apply_derived_specific_capital_investment_to_tep_row_dict(
    row_dict: dict[str, str],
    r: Any,
    *,
    target_year: int | None = None,
    coeff_by_year: dict[int, Decimal] | None = None,
) -> None:
    """Подменяет ``specific_capital_investment_thous_rub_per_kw`` расчётным значением (in-place)."""
    row_dict["specific_capital_investment_thous_rub_per_kw"] = (
        fmt_specific_capital_investment_thous_rub_per_kw_derived(
            r,
            installed_capacity_attr=installed_capacity_attr_for_tep_row(r),
            target_year=target_year,
            coeff_by_year=coeff_by_year,
        )
    )


def merge_tep_row_full_with_capital_costs_current_year_prices(
    base: dict[str, str],
    r: Any,
    target_year: int | None,
    coeff_by_year: dict[int, Decimal],
) -> dict[str, str]:
    """
    Копия base с пересчитанными полями капзатрат без ПИР и удельными показателями в цены target_year.

    ``r`` — строка ТЭП (ГЭС, ГАЭС и т.д.) с атрибутами сумм и связями ``year_*``.
    При ``target_year`` is None возвращается ``base`` без изменений.
    """
    if not target_year:
        return base
    out = dict(base)
    for dict_key, raw_attr, year_rel_attr in TEP_CAPITAL_COST_WO_PIR_FIELD_TRIPLES:
        raw = getattr(r, raw_attr, None)
        year_obj = getattr(r, year_rel_attr, None)
        out[dict_key] = fmt_million_rub_scaled(
            raw,
            year_obj,
            target_year,
            coeff_by_year,
        )
    out["specific_semifixed_operating_costs_thous_rub_per_kw"] = fmt_thousand_rub_per_kw_scaled(
        getattr(r, "specific_semifixed_operating_costs_thous_rub_per_kw", None),
        getattr(r, "year_specific_semifixed_operating_costs", None),
        target_year,
        coeff_by_year,
    )
    apply_derived_specific_capital_investment_to_tep_row_dict(
        out, r, target_year=target_year, coeff_by_year=coeff_by_year
    )
    return out


# --- TepPriceConversionCoefficient: UI и CRUD ---


class _UnsetType:
    pass


_UNSET = _UnsetType()


def _parse_coefficient(raw) -> Decimal | None:
    if raw is None:
        return None
    if isinstance(raw, str) and not raw.strip():
        return None
    if isinstance(raw, (int, float)):
        return Decimal(str(raw))
    s = str(raw).strip().replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation as e:
        raise ValueError("Некорректное значение коэффициента.") from e


def get_price_coefficients_snapshot() -> dict:
    """
    Данные для модального окна: строки коэффициентов и справочник годов текущей версии БД.
    """
    vid = get_current_version()
    if not vid:
        return {"rows": [], "years": []}

    years = [{"id": y.id, "number": y.number} for y in get_year_list_full()]

    rows_orm = (
        TepPriceConversionCoefficient.query.filter(
            TepPriceConversionCoefficient.database_version_id == vid
        )
        .options(joinedload(TepPriceConversionCoefficient.year))
        .join(Year, TepPriceConversionCoefficient.id_year == Year.id)
        .filter(Year.database_version_id == vid)
        .order_by(Year.number.asc())
        .all()
    )

    rows: list[dict] = []
    for r in rows_orm:
        y = r.year
        num = y.number if y is not None else None
        c = r.coefficient
        coeff_s = str(c) if c is not None else None
        rows.append(
            {
                "id": r.id,
                "id_year": r.id_year,
                "year": num,
                "coefficient": coeff_s,
            }
        )

    return {"rows": rows, "years": years}


def get_tep_price_coefficient_by_year_map() -> dict[int, Decimal]:
    """
    Номер календарного года → коэффициент пересчёта (текущая версия БД).
    Для цепочки пересчёта цены из года P в текущий год Y используются коэффициенты
    за годы P+1 … Y включительно.
    """
    out: dict[int, Decimal] = {}
    for row in get_price_coefficients_snapshot()["rows"]:
        yn = row.get("year")
        cs = row.get("coefficient")
        if yn is None or cs is None:
            continue
        try:
            out[int(yn)] = Decimal(str(cs))
        except (InvalidOperation, ValueError, TypeError):
            continue
    return out


def get_tep_main_radio_price_year_number(
    tep_source_rows: Iterable[Any] | None,
    *,
    current_target_year: int | None = None,
) -> int | None:
    """
    Календарный год для подписи радиокнопки «в ценах N года» на ТЭП основных площадок.

    Если максимальный год в полях «год» блока «Стоимость (капзатраты без ПИР)» по
    отображаемым строкам меньше целевого «текущего» года пересчёта — в подписи
    используется максимальный год среди строк таблицы коэффициентов (где задан
    коэффициент). Иначе — максимальный год из тех же полей исходных данных.
    """
    from app.common.services.get_services.years.years_get_services import (
        get_ges_tep_current_price_year_number,
    )

    if current_target_year is None:
        current_target_year = get_ges_tep_current_price_year_number()

    nums: list[int] = []
    for r in tep_source_rows or ():
        for _dk, _ra, year_attr in TEP_CAPITAL_COST_WO_PIR_FIELD_TRIPLES:
            y = getattr(r, year_attr, None)
            if y is None:
                continue
            num = getattr(y, "number", None)
            if num is None:
                continue
            try:
                nums.append(int(num))
            except (TypeError, ValueError):
                pass
    max_source = max(nums) if nums else None

    coeff_map = get_tep_price_coefficient_by_year_map()
    max_coeff_year = max(coeff_map.keys()) if coeff_map else None

    if (
        max_source is not None
        and current_target_year is not None
        and max_source < current_target_year
    ):
        return max_coeff_year if max_coeff_year is not None else current_target_year
    return max_source if max_source is not None else current_target_year


def tep_main_rows_have_mixed_source_price_years(tep_source_rows: Iterable[Any] | None) -> bool:
    """
    True, если по разным строкам ТЭП в блоках «Капитальные затраты» и/или
    «Удельные условно-постоянные эксплуатационные затраты» заданы разные
    календарные года (по каждому из полей года — более одного ненулевого значения
    среди строк). Тогда пересчёт в единые «цены года» для всей таблицы недоступен.
    """
    rows = list(tep_source_rows or ())
    if len(rows) <= 1:
        return False

    def _year_num(r: Any, attr: str) -> int | None:
        y = getattr(r, attr, None)
        if y is None:
            return None
        n = getattr(y, "number", None)
        if n is None:
            return None
        try:
            return int(n)
        except (TypeError, ValueError):
            return None

    for _dk, _ra, year_attr in TEP_CAPITAL_COST_WO_PIR_FIELD_TRIPLES:
        distinct: set[int] = set()
        for r in rows:
            num = _year_num(r, year_attr)
            if num is not None:
                distinct.add(num)
        if len(distinct) > 1:
            return True

    distinct_sf: set[int] = set()
    for r in rows:
        num = _year_num(r, "year_specific_semifixed_operating_costs")
        if num is not None:
            distinct_sf.add(num)
    return len(distinct_sf) > 1


# Год цен по связям Year на энергоблоке АЭС (пересчёт удельных показателей, тыс. руб./кВт и аналоги)
AES_MACHINE_TEP_YEAR_RELATIONSHIP_ATTRS: tuple[str, ...] = (
    "year_specific_fuel_cost",
    "year_specific_fixed_operating_costs",
    "year_specific_capital_investment",
    "year_specific_decommissioning",
)


def get_aes_tep_main_radio_price_year_number(
    machines: Iterable[Any] | None,
    *,
    current_target_year: int | None = None,
) -> int | None:
    """Год для подписи «в ценах N года» на страницах ТЭП АЭС (логика как у перечня ТЭП ГЭС)."""
    from app.common.services.get_services.years.years_get_services import (
        get_ges_tep_current_price_year_number,
    )

    if current_target_year is None:
        current_target_year = get_ges_tep_current_price_year_number()

    nums: list[int] = []
    for r in machines or ():
        for attr in AES_MACHINE_TEP_YEAR_RELATIONSHIP_ATTRS:
            y = getattr(r, attr, None)
            if y is None:
                continue
            num = getattr(y, "number", None)
            if num is None:
                continue
            try:
                nums.append(int(num))
            except (TypeError, ValueError):
                pass
    max_source = max(nums) if nums else None

    coeff_map = get_tep_price_coefficient_by_year_map()
    max_coeff_year = max(coeff_map.keys()) if coeff_map else None

    if (
        max_source is not None
        and current_target_year is not None
        and max_source < current_target_year
    ):
        return max_coeff_year if max_coeff_year is not None else current_target_year
    return max_source if max_source is not None else current_target_year


def aes_tep_rows_have_mixed_source_price_years(machines: Iterable[Any] | None) -> bool:
    """
    True, если среди отображаемых энергоблоков по любому из полей «год данных»
    встречается более одного календарного года — единый пересчёт в «цены года» недоступен.
    """
    rows = list(machines or ())
    if len(rows) <= 1:
        return False

    def _year_num(r: Any, rel_attr: str) -> int | None:
        y = getattr(r, rel_attr, None)
        if y is None:
            return None
        n = getattr(y, "number", None)
        if n is None:
            return None
        try:
            return int(n)
        except (TypeError, ValueError):
            return None

    for rel_attr in AES_MACHINE_TEP_YEAR_RELATIONSHIP_ATTRS:
        distinct: set[int] = set()
        for r in rows:
            num = _year_num(r, rel_attr)
            if num is not None:
                distinct.add(num)
        if len(distinct) > 1:
            return True
    return False


def rows_match_for_scaled_thousand_rub_pair(
    group: list[Any],
    raw_attr: str,
    year_rel_attr: str,
    *,
    target_year: int | None,
    coeff_by_year: dict[int, Decimal] | None,
) -> bool:
    """Совпадение отображаемых удельных значений после пересчёта (тыс. руб./кВт и т.п.)."""
    if len(group) <= 1:
        return True
    coeff = coeff_by_year or {}
    y0 = getattr(group[0], year_rel_attr, None)
    first = fmt_thousand_rub_per_kw_scaled(
        getattr(group[0], raw_attr, None),
        y0,
        target_year,
        coeff,
    )
    for r in group[1:]:
        v = fmt_thousand_rub_per_kw_scaled(
            getattr(r, raw_attr, None),
            getattr(r, year_rel_attr, None),
            target_year,
            coeff,
        )
        if v != first:
            return False
    return True


def _require_version() -> int:
    vid = get_current_version()
    if not vid:
        raise ValueError("Не выбрана текущая версия БД.")
    return vid


def _year_in_version(id_year: int, vid: int) -> Year | None:
    return Year.query.filter_by(id=id_year, database_version_id=vid).first()


def create_price_conversion_coefficient(id_year: int, coefficient_raw) -> TepPriceConversionCoefficient:
    vid = _require_version()
    y = _year_in_version(id_year, vid)
    if not y:
        raise ValueError("Указанный год не найден в текущей версии БД.")

    coeff = _parse_coefficient(coefficient_raw)

    row = TepPriceConversionCoefficient(
        id_year=id_year,
        coefficient=coeff,
        database_version_id=vid,
    )
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError("Для этого года уже задан коэффициент.") from None
    db.session.refresh(row)
    return row


def update_price_conversion_coefficient(
    row_id: int,
    *,
    id_year: int | None = None,
    update_year: bool = False,
    coefficient_raw=_UNSET,
) -> TepPriceConversionCoefficient:
    vid = _require_version()
    row = TepPriceConversionCoefficient.query.filter_by(
        id=row_id, database_version_id=vid
    ).first()
    if not row:
        raise LookupError("Запись не найдена.")

    if update_year:
        if id_year is None:
            raise ValueError("Не указан год.")
        y = _year_in_version(id_year, vid)
        if not y:
            raise ValueError("Указанный год не найден в текущей версии БД.")
        row.id_year = id_year

    if coefficient_raw is not _UNSET:
        row.coefficient = _parse_coefficient(coefficient_raw)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError("Для этого года уже задан другой коэффициент.") from None
    db.session.refresh(row)
    return row


def update_price_conversion_coefficient_from_request(
    row_id: int, data: dict
) -> TepPriceConversionCoefficient:
    """Разбор тела PUT: поля id_year и coefficient задаются только если переданы в JSON."""
    if not isinstance(data, dict):
        data = {}
    update_year = "id_year" in data
    id_year_val = None
    if update_year:
        raw_y = data.get("id_year")
        try:
            id_year_val = int(raw_y)
        except (TypeError, ValueError) as e:
            raise ValueError("Укажите корректный идентификатор года.") from e

    coeff_raw = _UNSET
    if "coefficient" in data:
        coeff_raw = data["coefficient"]

    return update_price_conversion_coefficient(
        row_id,
        update_year=update_year,
        id_year=id_year_val,
        coefficient_raw=coeff_raw,
    )


def delete_price_conversion_coefficient(row_id: int) -> None:
    vid = _require_version()
    row = TepPriceConversionCoefficient.query.filter_by(
        id=row_id, database_version_id=vid
    ).first()
    if not row:
        raise LookupError("Запись не найдена.")
    db.session.delete(row)
    db.session.commit()
