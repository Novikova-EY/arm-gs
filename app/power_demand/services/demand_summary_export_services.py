"""Выгрузка сводных таблиц нагрузок в Excel."""
from __future__ import annotations

from io import BytesIO
from typing import Any


def build_demand_summary_excel_stream(
    *,
    summary_rows: list[dict[str, Any]],
    years: list[int],
    sheet_title: str,
    year_is_plan: dict[int, bool] | None = None,
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
    ] + [str(y) for y in years]
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
        for i, y in enumerate(years):
            v = yvals[i] if i < len(yvals) else "—"
            if year_is_plan and year_is_plan.get(y) and pk != "max_power":
                line.append("")
            else:
                line.append(v if v is not None and v != "" else "—")
        ws.append(line)

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio
