# -*- coding: utf-8 -*-
"""Импорт сводных показателей потребления из Excel (листы «млн. кВт.ч» и/или «СиПР»)."""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional, Type

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select

from flask import session

from app.common.models.database_version_model import DatabaseVersion
from app.common.services.database_version_filter import filter_by_explicit_db_version
from app.common.services.database_version_services import get_current_version
from app.extensions import db
from app.energy_consumption.services import energy_consumption_parameter_services as ecps
from app.refdata.models.energy_systems.regional_district_regional_energy_system_model import (
    regional_district_regional_energy_system,
)
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.years.year_model import Year

from app.energy_consumption.models.energy_systems.regional_energy_system_energy_consumption_parameter_model import (
    RegionalEnergySystemEnergyConsumptionParameter,
)
from app.energy_consumption.models.energy_systems.union_energy_system_energy_consumption_parameter_model import (
    UnionEnergySystemEnergyConsumptionParameter,
)
from app.energy_consumption.models.territories.federal_district_energy_consumption_parameter_model import (
    FederalDistrictEnergyConsumptionParameter,
)
from app.energy_consumption.models.territories.regional_district_energy_consumption_parameter_model import (
    RegionalDistrictEnergyConsumptionParameter,
)


SHEET_MLN_KVTCH = "млн. кВт.ч"
SHEET_SIPR = "СиПР"

# Год в шапке: «2025», «2025 г.», «2025г», лат. «2025 g.»; «2025.0» из строкового представления числа Excel.
_YEAR_HEADER_RE = re.compile(
    r"^\s*(\d{4})(?:\s*(?:г|[gG])\.?)?\s*$",
    re.IGNORECASE,
)
_YEAR_HEADER_NUMSTR_RE = re.compile(r"^\s*(\d{4})(?:\.0+)?\s*$")

# Для поиска строки с годами в файле — без совпадения со справочником Years (его может ещё не быть).
_YEAR_HEADER_PLAUSIBLE = range(1990, 2051)


@dataclass(frozen=True)
class _ImportBind:
    demand_model: Type[Any]
    fk_column: str
    parent_id: int


_MODEL_FK: dict[Type[Any], str] = {
    UnionEnergySystemEnergyConsumptionParameter: "id_union_energy_system",
    RegionalEnergySystemEnergyConsumptionParameter: "id_regional_energy_system",
    RegionalDistrictEnergyConsumptionParameter: "id_regional_district",
    FederalDistrictEnergyConsumptionParameter: "id_federal_district",
}


def _norm_space(s: str) -> str:
    return " ".join(str(s).replace("\xa0", " ").split()).strip()


def _cell_as_text(val: Any) -> str:
    if val is None:
        return ""
    from datetime import date, datetime

    if isinstance(val, datetime):
        return str(val.year)
    if isinstance(val, date):
        return str(val.year)
    return str(val)


def _coerce_cell_to_year_number(val: Any) -> Optional[int]:
    """Распознать календарный год в ячейке по формату (число, «2025 г.», …), без справочника Years."""
    if val is None:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, (int, float)):
        try:
            i = int(val)
        except (TypeError, ValueError):
            return None
        return i if i in _YEAR_HEADER_PLAUSIBLE else None
    s = _norm_space(_cell_as_text(val))
    if not s:
        return None
    m = _YEAR_HEADER_RE.match(s) or _YEAR_HEADER_NUMSTR_RE.match(s)
    if not m:
        return None
    y = int(m.group(1))
    return y if y in _YEAR_HEADER_PLAUSIBLE else None


def _parse_numeric_cell(val: Any) -> Optional[Decimal]:
    if val is None:
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, Decimal):
        return val
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    return ecps.parse_decimal(val)


def _year_numbers_for_version(version_id: int) -> set[int]:
    rows = Year.query.filter(Year.database_version_id == version_id).all()
    return {int(y.number) for y in rows if y.number is not None}


def _database_version_ids_ordered() -> list[int]:
    rows = (
        DatabaseVersion.query.filter(DatabaseVersion.id > 0)
        .order_by(DatabaseVersion.id.asc())
        .all()
    )
    out = [int(r.id) for r in rows]
    if out:
        return out
    cv = get_current_version()
    if cv is not None:
        return [int(cv)]
    return []


def _find_sheet_title(wb, wanted: str):
    wstrip = wanted.strip()
    for title in wb.sheetnames:
        if title.strip() == wstrip:
            return wb[title]
    low = wstrip.casefold()
    for title in wb.sheetnames:
        if title.strip().casefold() == low:
            return wb[title]
    raise ValueError(f'В книге нет листа «{wanted}».')


def _find_sheet_title_optional(wb, wanted: str):
    """Возвращает лист или None, если в книге нет вкладки с таким именем."""
    wstrip = wanted.strip()
    for title in wb.sheetnames:
        if title.strip() == wstrip:
            return wb[title]
    low = wstrip.casefold()
    for title in wb.sheetnames:
        if title.strip().casefold() == low:
            return wb[title]
    return None


def _sheet_matrix(ws) -> list[tuple[Any, ...]]:
    rows = list(ws.iter_rows(values_only=True))
    return [tuple(r) for r in rows]


def _load_summary_workbook_from_bytes(raw: bytes):
    """Открывает книгу для импорта; ошибки чтения превращает в ValueError с пояснением для пользователя."""
    from io import BytesIO
    from zipfile import BadZipFile

    from openpyxl import load_workbook
    from openpyxl.utils.exceptions import InvalidFileException

    try:
        return load_workbook(BytesIO(raw), read_only=False, data_only=True)
    except (BadZipFile, InvalidFileException) as e:
        raise ValueError(
            "Не удалось открыть файл как книгу Excel. Нужен формат .xlsx или .xlsm "
            "(не старый .xls). Сохраните документ через «Сохранить как» → «Книга Excel (*.xlsx)»."
        ) from e
    except Exception as e:
        raise ValueError(
            "Не удалось прочитать файл Excel — книга повреждена, неполная или в неподдерживаемом формате. "
            "Откройте её в Excel, сохраните заново как .xlsx и повторите импорт."
        ) from e


def _detect_year_row(matrix: list[tuple[Any, ...]]) -> tuple[int, dict[int, int]]:
    best_row = -1
    best_cols: dict[int, int] = {}
    best_score = 0
    for ri, row in enumerate(matrix):
        cols: dict[int, int] = {}
        for ci, val in enumerate(row):
            y = _coerce_cell_to_year_number(val)
            if y is not None:
                cols[ci] = y
        if len(cols) > best_score:
            best_score = len(cols)
            best_row = ri
            best_cols = cols
    if best_row < 0 or best_score < 2:
        raise ValueError(
            "Не удалось найти строку с годами в таблице (целые годы или «2016 г.» и т.п.; "
            f"ожидаемый диапазон {_YEAR_HEADER_PLAUSIBLE.start}–{_YEAR_HEADER_PLAUSIBLE.stop - 1}). "
            "При записи учитываются только годы, заведённые в справочнике Years для данной версии БД."
        )
    return best_row, best_cols


def _detect_name_column(matrix: list[tuple[Any, ...]], year_row_idx: int) -> int:
    needle = "наименование"
    last_hit: Optional[int] = None
    for ri in range(0, year_row_idx + 1):
        row = matrix[ri] if ri < len(matrix) else ()
        for ci, val in enumerate(row):
            s = _norm_space(_cell_as_text(val)).casefold()
            if needle in s:
                last_hit = ci
    if last_hit is None:
        raise ValueError('Не найден столбец с заголовком, содержащим «Наименование».')
    return last_hit


def _entities_with_names(model, version_id: int) -> list[tuple[Any, str]]:
    q = filter_by_explicit_db_version(model.query, model, version_id)
    rows = q.order_by(model.id.asc()).all()
    out: list[tuple[Any, str]] = []
    for r in rows:
        nm = getattr(r, "name", None)
        if nm is None:
            continue
        ns = _norm_space(str(nm))
        if ns:
            out.append((r, ns))
    return out


def _binding_ctx(version_id: int) -> dict[str, list[tuple[Any, str]]]:
    return {
        "ues": _entities_with_names(UnionEnergySystem, version_id),
        "res": _entities_with_names(RegionalEnergySystem, version_id),
        "rd": _entities_with_names(RegionalDistrict, version_id),
        "fd": _entities_with_names(FederalDistrict, version_id),
    }


def _labels_match(excel_label: str, db_name: str) -> bool:
    ex = _norm_space(excel_label).casefold()
    db = _norm_space(db_name).casefold()
    if not ex or not db:
        return False
    if ex == db:
        return True
    if ex in db or db in ex:
        return True
    return False


def _pick_match(label: str, pairs: list[tuple[Any, str]]) -> Optional[Any]:
    if not pairs:
        return None
    label_n = _norm_space(label).casefold()
    exact = [e for e, n in pairs if _norm_space(n).casefold() == label_n]
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        exact.sort(key=lambda e: len(getattr(e, "name", "") or ""), reverse=True)
        return exact[0]
    candidates = [e for e, n in pairs if _labels_match(label, n)]
    if not candidates:
        return None
    candidates.sort(key=lambda e: len(getattr(e, "name", "") or ""), reverse=True)
    return candidates[0]


def _resolve_row_binding(label: str, ctx: dict[str, list[tuple[Any, str]]]) -> Optional[_ImportBind]:
    ues = _pick_match(label, ctx["ues"])
    if ues is not None:
        return _ImportBind(
            UnionEnergySystemEnergyConsumptionParameter,
            _MODEL_FK[UnionEnergySystemEnergyConsumptionParameter],
            int(ues.id),
        )
    res = _pick_match(label, ctx["res"])
    if res is not None:
        return _ImportBind(
            RegionalEnergySystemEnergyConsumptionParameter,
            _MODEL_FK[RegionalEnergySystemEnergyConsumptionParameter],
            int(res.id),
        )
    rd = _pick_match(label, ctx["rd"])
    if rd is not None:
        return _ImportBind(
            RegionalDistrictEnergyConsumptionParameter,
            _MODEL_FK[RegionalDistrictEnergyConsumptionParameter],
            int(rd.id),
        )
    fd = _pick_match(label, ctx["fd"])
    if fd is not None:
        return _ImportBind(
            FederalDistrictEnergyConsumptionParameter,
            _MODEL_FK[FederalDistrictEnergyConsumptionParameter],
            int(fd.id),
        )
    return None


# Лист-заглушка «млн. кВт.ч» (несколько строк без сетки годов) — не считаем ошибкой при разборе.
_OPTIONAL_GRID_MAX_ROWS = 6


def _aggregate_sheet_labels(
    matrix: list[tuple[Any, ...]],
    *,
    allow_empty_short_sheet_without_year_grid: bool = False,
) -> defaultdict[tuple[str, int], Decimal]:
    """Ключ: нормализованное наименование из файла, год → сумма по строкам листа.

    Если allow_empty_short_sheet_without_year_grid=True и в коротком листе нет строки с годами
    (типичный пустой лист-заглушка «млн. кВт.ч»), возвращается пустая сводка без ошибки.
    """
    acc: defaultdict[tuple[str, int], Decimal] = defaultdict(lambda: Decimal("0"))
    if not matrix:
        return acc
    try:
        yr_row, year_cols = _detect_year_row(matrix)
        name_ci = _detect_name_column(matrix, yr_row)
    except ValueError:
        if allow_empty_short_sheet_without_year_grid and len(matrix) <= _OPTIONAL_GRID_MAX_ROWS:
            return acc
        raise
    for ri in range(yr_row + 1, len(matrix)):
        row = matrix[ri]
        if name_ci >= len(row):
            continue
        raw_name = row[name_ci]
        label = _norm_space(_cell_as_text(raw_name))
        if not label:
            continue
        for ci, year_n in year_cols.items():
            if ci >= len(row):
                continue
            num = _parse_numeric_cell(row[ci])
            if num is None:
                continue
            acc[(label, year_n)] += num
    return acc


def _single_regional_district_id_for_res(
    regional_energy_system_id: int,
    *,
    database_version_id: int,
) -> Optional[int]:
    """
    Если в связях региональная ЭС привязана ровно к одному субъекту РФ и этот субъект
    есть в указанной версии справочника — вернуть его id, иначе None.
    """
    stmt = select(regional_district_regional_energy_system.c.regional_district_id).where(
        regional_district_regional_energy_system.c.regional_energy_system_id
        == regional_energy_system_id
    )
    rows = db.session.execute(stmt).all()
    rd_ids = {int(r[0]) for r in rows if r[0] is not None}
    if len(rd_ids) != 1:
        return None
    rd_id = next(iter(rd_ids))
    rq = RegionalDistrict.query.filter(RegionalDistrict.id == rd_id)
    rq = filter_by_explicit_db_version(rq, RegionalDistrict, database_version_id)
    return rd_id if rq.first() is not None else None


def _mirror_res_accumulator_rows_to_single_district_rd(
    acc: defaultdict[tuple[Type[Any], str, int, int], Decimal],
    *,
    database_version_id: int,
    explicit_rd_subject_year_pairs: frozenset[tuple[int, int]],
) -> None:
    """Дублирует суммы импорта по РЭС в параметры единственного субъекта этой РЭС (если он один).

    Если в файле по этому субъекту за тот же год уже есть строка, сопоставленная именно как
    субъект РФ, зеркало не добавляют — без этого значения суммировались бы дважды.
    """
    res_model = RegionalEnergySystemEnergyConsumptionParameter
    fk_res = _MODEL_FK[res_model]
    fk_rd = _MODEL_FK[RegionalDistrictEnergyConsumptionParameter]
    rd_model = RegionalDistrictEnergyConsumptionParameter
    for (model_cls, fk_column, parent_id, year_n), total in list(acc.items()):
        if model_cls is not res_model or fk_column != fk_res:
            continue
        rd_id = _single_regional_district_id_for_res(
            int(parent_id),
            database_version_id=database_version_id,
        )
        if rd_id is None:
            continue
        if (rd_id, year_n) in explicit_rd_subject_year_pairs:
            continue
        key_rd = (rd_model, fk_rd, rd_id, year_n)
        acc[key_rd] += total


def _collapse_labels_to_bind_keys(
    acc_labels: defaultdict[tuple[str, int], Decimal],
    *,
    ctx: dict[str, list[tuple[Any, str]]],
    years_ok: set[int],
) -> tuple[
    defaultdict[tuple[Type[Any], str, int, int], Decimal],
    frozenset[tuple[int, int]],
]:
    """Отбор годов, входящих в справочник Years данной версии; привязка к объектам версии.

    Второй элемент — множество (id_subj_rf, год), для которых в файле уже есть сумма как по
    субъекту РФ (без дубля зеркалом с РЭС).
    """
    acc: defaultdict[tuple[Type[Any], str, int, int], Decimal] = defaultdict(
        lambda: Decimal("0")
    )
    explicit_rd_subject_years: set[tuple[int, int]] = set()
    rd_model = RegionalDistrictEnergyConsumptionParameter
    for (label, year_n), total in acc_labels.items():
        if year_n not in years_ok:
            continue
        bind = _resolve_row_binding(label, ctx)
        if bind is None:
            continue
        key = (bind.demand_model, bind.fk_column, bind.parent_id, year_n)
        acc[key] += total
        if bind.demand_model is rd_model:
            explicit_rd_subject_years.add((int(bind.parent_id), int(year_n)))
    return acc, frozenset(explicit_rd_subject_years)


def _find_existing_parameter_row(
    model: Type[Any],
    fk_column: str,
    parent_id: int,
    year_n: int,
    version_id: int,
):
    q = model.query.filter(
        getattr(model, fk_column) == parent_id,
        model.year_number == year_n,
    )
    q = filter_by_explicit_db_version(q, model, version_id)
    return q.first()


def _apply_accumulator_for_version(
    acc: defaultdict[tuple[Type[Any], str, int, int], Decimal],
    *,
    field_name: str,
    version_id: int,
) -> int:
    touched = 0
    user = session.get("username", "Неизвестный пользователь")
    for (model, fk_column, parent_id, year_n), total in acc.items():
        row = _find_existing_parameter_row(model, fk_column, parent_id, year_n, version_id)
        if row is None:
            row = model()
            setattr(row, fk_column, parent_id)
            row.database_version_id = version_id
            row.year_number = year_n
            row.created_by = user
            db.session.add(row)
        setattr(row, field_name, total)
        row.modified_by = user
        touched += 1
    return touched


def _labels_matched_in_any_version(labels: set[str], version_ids: list[int]) -> set[str]:
    matched: set[str] = set()
    for vid in version_ids:
        ctx = _binding_ctx(vid)
        for lbl in labels:
            if lbl in matched:
                continue
            if _resolve_row_binding(lbl, ctx) is not None:
                matched.add(lbl)
    return matched


def import_energy_consumption_summary_from_xlsx_bytes(raw: bytes) -> dict[str, Any]:
    """
    Читает листы «млн. кВт.ч» и/или «СиПР» (какие есть в книге), сопоставляет наименования
    (ОЭС → РЭС → субъект РФ → ФО) и записывает числа в параметры для каждой версии базы данных.

    Должен присутствовать хотя бы один из двух листов. Отсутствующий лист пропускается.

    Строка, сопоставленная с РЭС, дублируется в параметры субъекта РФ, если в
    gs_sys_regional_district_regional_energy_system у этой РЭС ровно один субъект
    (и он есть в той же версии справочника): лист «млн. кВт.ч» → поле по субъекту,
    лист «СиПР» → поле СиПР по субъекту. Если для того же субъекта и года в файле уже
    есть строка, сопоставленная как субъект РФ (а не как РЭС), копирование с РЭС не
    выполняется — иначе сумма на субъекте удваивается.

    Если лист «млн. кВт.ч» есть, но это короткая заглушка без таблицы, показатели «млн. кВт·ч»
    из файла не обновляются (как при отсутствии данных на листе).
    """
    version_ids = _database_version_ids_ordered()
    if not version_ids:
        raise ValueError("Не найдено ни одной версии базы данных для записи импорта.")

    wb = _load_summary_workbook_from_bytes(raw)
    try:
        ws_m = _find_sheet_title_optional(wb, SHEET_MLN_KVTCH)
        ws_s = _find_sheet_title_optional(wb, SHEET_SIPR)
        if ws_m is None and ws_s is None:
            raise ValueError(
                f'В книге нет ни листа «{SHEET_MLN_KVTCH}», ни листа «{SHEET_SIPR}».'
            )
        matrix_m = _sheet_matrix(ws_m) if ws_m is not None else []
        matrix_s = _sheet_matrix(ws_s) if ws_s is not None else []
    finally:
        wb.close()

    acc_mln_labels = _aggregate_sheet_labels(
        matrix_m, allow_empty_short_sheet_without_year_grid=(ws_m is not None)
    )
    acc_sipr_labels = _aggregate_sheet_labels(matrix_s)

    mln_skipped = (
        ws_m is not None
        and len(matrix_m) > 0
        and len(matrix_m) <= _OPTIONAL_GRID_MAX_ROWS
        and len(acc_mln_labels) == 0
    )
    labels_mln = {lbl for lbl, _ in acc_mln_labels.keys()}
    labels_sipr = {lbl for lbl, _ in acc_sipr_labels.keys()}
    matched_any = _labels_matched_in_any_version(labels_mln | labels_sipr, version_ids)

    try:
        n_mln = 0
        n_sipr = 0
        for vid in version_ids:
            ctx = _binding_ctx(vid)
            years_ok = _year_numbers_for_version(vid)
            if not years_ok:
                continue
            acc_m, explicit_rd_mln = _collapse_labels_to_bind_keys(
                acc_mln_labels, ctx=ctx, years_ok=years_ok
            )
            _mirror_res_accumulator_rows_to_single_district_rd(
                acc_m,
                database_version_id=vid,
                explicit_rd_subject_year_pairs=explicit_rd_mln,
            )
            acc_s, explicit_rd_sipr = _collapse_labels_to_bind_keys(
                acc_sipr_labels, ctx=ctx, years_ok=years_ok
            )
            _mirror_res_accumulator_rows_to_single_district_rd(
                acc_s,
                database_version_id=vid,
                explicit_rd_subject_year_pairs=explicit_rd_sipr,
            )
            n_mln += _apply_accumulator_for_version(
                acc_m, field_name="energy_consumption_mln_kvt_ch", version_id=vid
            )
            db.session.flush()
            n_sipr += _apply_accumulator_for_version(
                acc_s, field_name="energy_consumption_sipr_mln_kvt_ch", version_id=vid
            )
            db.session.flush()
            ecps.sync_energy_zone_consumption_aggregates(database_version_id=vid)
            db.session.flush()
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise ValueError("Не удалось сохранить импорт (конфликт целостности данных).") from None

    def _uniq_sorted(xs: set[str], limit: int) -> list[str]:
        out = sorted(xs, key=lambda s: s.casefold())[:limit]
        return out

    stats_out: dict[str, Any] = {
        "cells_written_mln_kvt_ch": n_mln,
        "cells_written_sipr": n_sipr,
        "database_versions_processed": len(version_ids),
        "unmatched_labels_mln": _uniq_sorted(labels_mln - matched_any, 80),
        "unmatched_labels_sipr": _uniq_sorted(labels_sipr - matched_any, 80),
        "mln_sheet_skipped_no_data_grid": mln_skipped,
        "mln_sheet_absent": ws_m is None,
        "sipr_sheet_absent": ws_s is None,
    }
    try:
        from app.energy_consumption.services.energy_consumption_summary_logging import (
            log_ec_summary_excel_import,
        )

        log_ec_summary_excel_import(
            session.get("username", "Неизвестный пользователь"),
            stats_out,
            database_version_id=get_current_version(),
        )
    except Exception:
        pass
    return stats_out
