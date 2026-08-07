# -*- coding: utf-8 -*-
"""Экспорт параметров распределения в Excel (шапка совместима с импортом)."""

from __future__ import annotations

import io
from decimal import Decimal

from openpyxl import Workbook

from app.fuel.models.fue_distribution_parameter_model import DistributionParameter

# Тот же набор и порядок, что ожидает импорт (первая строка файла).
_EXPORT_HEADERS: tuple[str, ...] = (
    "name",
    "year",
    "filter",
    "e",
    "kplus",
    "kmin",
    "k",
    "bkl",
    "wname",
    "uname",
    "toplname",
    "dopname",
    "byear",
    "kn",
    "knps",
    "kngt",
    "knpg",
    "hnps",
    "hngt",
    "hnpg",
    "numb",
    "doptim",
    "lim",
)


def _cell(v):
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return v


def export_distribution_parameters_to_excel(
    rows: list[DistributionParameter],
) -> io.BytesIO:
    wb = Workbook()
    ws = wb.active
    if ws is None:
        raise RuntimeError("openpyxl: active sheet is None")
    ws.title = "Параметры"
    ws.append(list(_EXPORT_HEADERS))

    for dp in rows:
        ws.append(
            [
                dp.union_energy_system.name if dp.union_energy_system else None,
                dp.year.number if dp.year else None,
                dp.filter_text,
                _cell(dp.e),
                _cell(dp.kplus),
                _cell(dp.kmin),
                _cell(dp.k),
                _cell(dp.bkl),
                dp.wname,
                dp.uname,
                dp.toplname,
                dp.dopname,
                dp.base_year.number if dp.base_year else None,
                _cell(dp.kn),
                _cell(dp.knps),
                _cell(dp.kngt),
                _cell(dp.knpg),
                _cell(dp.hnps),
                _cell(dp.hngt),
                _cell(dp.hnpg),
                _cell(dp.numb),
                _cell(dp.doptim),
                dp.lim,
            ]
        )

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
