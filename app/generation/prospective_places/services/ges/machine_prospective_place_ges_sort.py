# -*- coding: utf-8 -*-
"""Сортировка записей перечня ТЭП (ProspectivePlaceGesTepSource) на площадке ГЭС."""


def sort_machines_by_station_block_number(station):
    """Совместимое имя: сортирует записи перечня ТЭП по id."""
    rows = station.ges_tep_source_indicators
    if not rows:
        return
    rows.sort(key=lambda r: (r.id or 0,))
