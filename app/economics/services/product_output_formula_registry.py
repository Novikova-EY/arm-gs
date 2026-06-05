# -*- coding: utf-8 -*-
"""Реестр формул для страницы выпуска продукции."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class ProductOutputFormulaDef:
    key: str
    page: str
    row_label: str
    default_text: str


PRODUCT_OUTPUT_FORMULA_REGISTRY: tuple[ProductOutputFormulaDef, ...] = (
    ProductOutputFormulaDef(
        key="po_total_row",
        page="Выпуск продукции",
        row_label="Всего выпуск продукции",
        default_text=(
            "Всего выпуск продукции = Промышленное производство, в том числе: + сумма выпуска "
            "продукции по остальным видам экономической деятельности, отображаемым в таблице "
            "(без повторного учёта подстрок промышленности), млн руб."
        ),
    ),
    ProductOutputFormulaDef(
        key="po_industrial_group",
        page="Выпуск продукции",
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


def iter_formula_defs() -> Iterator[ProductOutputFormulaDef]:
    yield from PRODUCT_OUTPUT_FORMULA_REGISTRY


def get_formula_def(key: str) -> ProductOutputFormulaDef | None:
    for item in PRODUCT_OUTPUT_FORMULA_REGISTRY:
        if item.key == key:
            return item
    return None
