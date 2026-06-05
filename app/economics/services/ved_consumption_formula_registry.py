# -*- coding: utf-8 -*-
"""Реестр формул для страницы потребления по ВЭД."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class VedConsumptionFormulaDef:
    key: str
    page: str
    row_label: str
    default_text: str


VED_CONSUMPTION_FORMULA_REGISTRY: tuple[VedConsumptionFormulaDef, ...] = (
    VedConsumptionFormulaDef(
        key="ved_total_row",
        page="Потребление электрической энергии по ВЭД",
        row_label="Всего потребление",
        default_text=(
            "Всего потребление = Промышленное производство, в том числе: + сумма потребления "
            "по остальным видам экономической деятельности, отображаемым в таблице "
            "(без повторного учёта подстрок промышленности)."
        ),
    ),
    VedConsumptionFormulaDef(
        key="ved_industrial_group",
        page="Потребление по ВЭД",
        row_label="Промышленное производство, в том числе",
        default_text=(
            "Промышленное производство, в том числе = "
            "Добыча полезных ископаемых + Обрабатывающие производства + "
            "Обеспечение электрической энергией, газом и паром; Кондиционирование воздуха. "
            "Водоснабжение; Водоотведение, организация сбора и утилизация отходов, "
            "деятельность по ликвидации загрязнений."
        ),
    ),
)


def iter_formula_defs() -> Iterator[VedConsumptionFormulaDef]:
    yield from VED_CONSUMPTION_FORMULA_REGISTRY


def get_formula_def(key: str) -> VedConsumptionFormulaDef | None:
    for item in VED_CONSUMPTION_FORMULA_REGISTRY:
        if item.key == key:
            return item
    return None
