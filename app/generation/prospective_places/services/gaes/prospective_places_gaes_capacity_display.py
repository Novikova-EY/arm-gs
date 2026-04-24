# -*- coding: utf-8 -*-
"""
Колонка «Планируемая установленная генерирующая мощность ГАЭС, МВт» в списке /gaes/:
текст строится по данным ТЭП (как на карточке площадки), а не по полю planned_capacity_mw.
"""

from __future__ import annotations

import html


def _is_empty(val) -> bool:
    if val is None:
        return True
    if isinstance(val, str) and not val.strip():
        return True
    return False


def _fmt_display(val) -> str:
    s = str(val).strip().replace(".", ",")
    return html.escape(s)


def _format_one_queue(gen, pump, line_break: str) -> str | None:
    """Одна «очередь»: генераторный и/или насосный столбец."""
    if _is_empty(gen) and _is_empty(pump):
        return None
    if not _is_empty(gen) and _is_empty(pump):
        return f"{_fmt_display(gen)} МВт генераторный режим"
    if not _is_empty(gen) and not _is_empty(pump):
        return (
            f"{_fmt_display(gen)} МВт генераторный режим /"
            f"{line_break}"
            f"{_fmt_display(pump)} МВт насосный режим"
        )
    return f"{_fmt_display(pump)} МВт насосный режим"


def format_gaes_tep_row_planned_capacity_display(tep, line_break: str) -> str | None:
    """
    Одна запись ProspectivePlaceGaesTepSource:
    сначала столбцы «всего» (генераторный / насосный); если оба пусты — 1 и 2 очередь.
    """
    g = tep.installed_capacity_mw_generator_mode
    pump = tep.installed_capacity_mw_pump_mode
    s1g = tep.stage_1_capacity_mw_generator_mode
    s1p = tep.stage_1_capacity_mw_pump_mode
    s2g = tep.stage_2_capacity_mw_generator_mode
    s2p = tep.stage_2_capacity_mw_pump_mode

    both_totals_empty = _is_empty(g) and _is_empty(pump)

    if not both_totals_empty:
        return _format_one_queue(g, pump, line_break)

    parts = []
    q1 = _format_one_queue(s1g, s1p, line_break)
    q2 = _format_one_queue(s2g, s2p, line_break)
    if q1:
        parts.append(f"1 очередь{line_break}{q1}")
    if q2:
        parts.append(f"{line_break}2 очередь{line_break}{q2}")
    if parts:
        return line_break.join(parts)
    return None


def format_gaes_planned_capacity_display(station, *, line_break: str = "<br>") -> str | None:
    """
    Берется первая по id запись ТЭП, для которой получается непустая строка
    (после сортировки, как в sort_machines_by_station_block_number).
    """
    rows = list(station.gaes_tep_source_indicators or [])
    rows.sort(key=lambda r: (r.id or 0,))
    for tep in rows:
        text = format_gaes_tep_row_planned_capacity_display(tep, line_break)
        if text:
            return text
    return None


def inject_gaes_planned_capacity_display_html(gaes_place_type_groups) -> None:
    """Проставляет station.gaes_planned_capacity_display_html для шаблона списка."""
    for group in gaes_place_type_groups:
        for station in group["stations"]:
            station.gaes_planned_capacity_display_html = format_gaes_planned_capacity_display(
                station, line_break="<br>"
            )
