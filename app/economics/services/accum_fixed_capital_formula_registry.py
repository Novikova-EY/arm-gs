# -*- coding: utf-8 -*-
"""Реестр формул для страницы накопленных инвестиций в основной капитал."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class AccumFixedCapitalFormulaDef:
    key: str
    page: str
    row_label: str
    default_text: str


VED_CONSUMPTION_FORMULA_REGISTRY: tuple[AccumFixedCapitalFormulaDef, ...] = (
    AccumFixedCapitalFormulaDef(
        key="afci_total_row",
        page="Накопленные Накопленные инвестиции в основной капитал",
        row_label="Всего накопленные Накопленные инвестиции",
        default_text=(
            "Всего накопленные Накопленные инвестиции = Промышленное производство, в том числе: + Строительство + "
            "Транспорт + Прочие ВЭД + Сельскохозяйственное производство."
        ),
    ),
    AccumFixedCapitalFormulaDef(
        key="afci_industrial_group",
        page="Накопленные Накопленные инвестиции в основной капитал",
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


def iter_formula_defs() -> Iterator[AccumFixedCapitalFormulaDef]:
    yield from VED_CONSUMPTION_FORMULA_REGISTRY


def get_formula_def(key: str) -> AccumFixedCapitalFormulaDef | None:
    for item in VED_CONSUMPTION_FORMULA_REGISTRY:
        if item.key == key:
            return item
    return None
