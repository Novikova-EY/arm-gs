# -*- coding: utf-8 -*-
"""JSON-набор line_capital_investments: капитальные вложения в ЛЭП.

Заглушка: схема полей как в контракте интеграций, значения нулевые.
Этих параметров в АРМ нет, они заполняются вручную.
"""
from __future__ import annotations

from typing import Any

from app.api.services.exchange_common_services import (
    MANUAL_FILL_EXCHANGE_COMMENT,
    load_stub_exchange_dataset,
)

DATASET_LINE_CAPITAL_INVESTMENTS = "line_capital_investments"

KEY_LINE_NAME = "Название линии"
KEY_VOLTAGE = "Класс напряжения, кВ"
KEY_ZONE = "Зона"
KEY_POWER_OUTPUT_GRID = (
    "Входит в развитие объектов электросетевого хозяйства, обеспечивающих "
    "выдачу мощности объектов по производству электрической энергии"
)
KEY_LINE_CODE = "external_code"

LINE_CAPITAL_INVESTMENTS_COMMENT = MANUAL_FILL_EXCHANGE_COMMENT


def build_line_capital_investments_stub_row() -> dict[str, Any]:
    return {
        KEY_LINE_NAME: "",
        KEY_VOLTAGE: 0,
        KEY_ZONE: "",
        KEY_POWER_OUTPUT_GRID: False,
        KEY_LINE_CODE: "",
    }


def load_line_capital_investments_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    return load_stub_exchange_dataset(
        DATASET_LINE_CAPITAL_INVESTMENTS,
        comment=LINE_CAPITAL_INVESTMENTS_COMMENT,
        row_factory=build_line_capital_investments_stub_row,
        version_id=version_id,
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
