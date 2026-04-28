"""Выгрузка сводных таблиц нагрузок в Excel."""
from __future__ import annotations

from io import BytesIO
from typing import Any


def _excel_hide_plan_year_cell(
    y: int,
    pk: str,
    row: dict[str, Any],
    year_is_plan: dict[int, bool] | None,
    coeff_base_year: int | None,
) -> bool:
    """Пустые «план»-столбцы для всех строк, кроме max_power, РЭС «Совмещенный на ОЭС/ЕЭС» (среднесрочный) и расчётных строк УЭС в отчётном/среднесрочном интервале."""
    if not year_is_plan or not year_is_plan.get(y):
        return False
    if pk == "max_power":
        return False
    if (
        coeff_base_year is not None
        and (coeff_base_year + 1) <= y <= (coeff_base_year + 6)
        and pk in ("combined_on_oes", "combined_on_ees")
        and row.get("demand_model_name") == "RegionalEnergySystemDemandParameter"
    ):
        return False
    if coeff_base_year is not None and row.get("demand_model_name") == "UnionEnergySystemDemandParameter":
        rep_med = (coeff_base_year - 9) <= y <= coeff_base_year or (
            (coeff_base_year + 1) <= y <= (coeff_base_year + 6)
        )
        med_only = (coeff_base_year + 1) <= y <= (coeff_base_year + 6)
        if pk in ("calculated_max_power_mw", "calculated_combined_on_ees_mw") and rep_med:
            return False
        if pk == "combined_on_ees" and med_only:
            return False
    return True


def build_demand_summary_excel_stream(
    *,
    summary_rows: list[dict[str, Any]],
    years: list[int],
    sheet_title: str,
    year_is_plan: dict[int, bool] | None = None,
    export_coeff_k_columns: bool = False,
    coeff_base_year: int | None = None,
) -> BytesIO:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    safe_title = (sheet_title or "Сводка").replace("/", "-").replace("\\", "-")[:31]
    ws.title = safe_title or "Сводка"

    header = [
        "Энергосистема",
        "Наименование параметров",
        "Исторический собственный максимум",
    ]
    if export_coeff_k_columns:
        for y in years:
            header.append(f"{y} k")
            header.append(f"{y} МВт")
    else:
        header.extend(str(y) for y in years)
    header.append("Примечание")
    ws.append(header)

    for row in summary_rows:
        entity_cell = ""
        if row.get("show_entity_cell"):
            depth = int(row.get("entity_depth") or 0)
            label = row.get("entity_label") or ""
            entity_cell = ("  " * depth) + str(label)
        line = [
            entity_cell,
            row.get("parameter_label") or "",
            row.get("hist_value") if row.get("hist_value") is not None else "—",
        ]
        yvals = row.get("year_values") or []
        pk = row.get("parameter_key") or ""
        ykvals = row.get("year_k_values") or []
        for i, y in enumerate(years):
            v = yvals[i] if i < len(yvals) else "—"
            hide_plan = _excel_hide_plan_year_cell(
                y, pk, row, year_is_plan, coeff_base_year
            )
            if export_coeff_k_columns:
                kk = ykvals[i] if i < len(ykvals) else "—"
                if hide_plan:
                    line.append("—")
                    line.append("")
                else:
                    line.append(kk if kk is not None and kk != "" else "—")
                    line.append(v if v is not None and v != "" else "—")
            elif hide_plan:
                line.append("")
            else:
                line.append(v if v is not None and v != "" else "—")
        nn = row.get("entity_note_text")
        line.append("" if nn is None else str(nn))
        ws.append(line)

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio
