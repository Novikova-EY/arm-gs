# -*- coding: utf-8 -*-
"""Сортировка энергоблоков перспективной площадки АЭС по станционному номеру блока."""
import re


def _station_block_sort_key(station_block_number):
    """Ключ сортировки: числа из строки по порядку (естественный порядок: 2 < 10)."""
    s = (station_block_number or "").strip()
    nums = re.findall(r"\d+", s)
    if nums:
        return (0, tuple(int(n) for n in nums))
    return (1, s.lower())


def sort_machines_by_station_block_number(station):
    """
    Сортирует на месте список энергоблоков площадки по станционному номеру
    (например: Блок 1, Блок 2, … Блок 10).
    """
    mps = station.machine_prospective_places
    if not mps:
        return
    mps.sort(
        key=lambda mp: (
            _station_block_sort_key(mp.station_block_number),
            mp.id or 0,
        )
    )
