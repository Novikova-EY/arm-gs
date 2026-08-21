"""Общие вспомогательные функции для страниц сводки."""

from __future__ import annotations

from typing import Any

from app.common.services.database_version_services import get_current_version
from app.energy_consumption.services.ec_summary_formula_template_vars import (
    inject_ec_formula_template_variables,
)
from app.energy_consumption.services.formula_text.energy_consumption_summary_formula_text_services import (
    apply_row_formula_text_overrides,
    build_ec_formula_texts_map,
)
from app.energy_consumption.services.energy_consumption_summary_logging import (
    load_formatted_ec_gaes_charge_logs,
    load_formatted_ec_summary_logs,
)


def finalize_ec_summary_page_context(context: dict[str, Any]) -> dict[str, Any]:
    """Подставить редактируемые тексты формул в контекст и строки сводки."""
    context = dict(context)
    from app.energy_consumption.services.energy_consumption_summary_services import (
        ensure_first_sa_variant_formula_tooltips,
    )

    # Иконки «i» у Первой СЗ — до подстановки переопределений текстов формул.
    ensure_first_sa_variant_formula_tooltips(context.get("summary_rows"))
    formula_texts = build_ec_formula_texts_map()
    context["ec_formula_texts"] = formula_texts
    inject_ec_formula_template_variables(context, formula_texts)
    apply_row_formula_text_overrides(context.get("summary_rows"))
    return context


def attach_ec_summary_logs(context: dict) -> None:
    scope = context.get("active_summary")
    if scope not in ("oes", "fo", "ez"):
        return
    vid = get_current_version()
    context["ec_summary_logs_formatted"] = load_formatted_ec_summary_logs(
        str(scope), vid, limit=50
    )


def attach_ec_gaes_charge_logs(context: dict) -> None:
    """Журнал на страницах «ГАЭС на заряд»: сводка + карточки электростанций."""
    scope = context.get("active_summary")
    if scope not in ("oes", "fo", "ez"):
        return
    vid = get_current_version()
    context["ec_summary_logs_formatted"] = load_formatted_ec_gaes_charge_logs(
        str(scope), vid, limit=50
    )
    context["ec_summary_logs_gaes_charge_merged"] = True
