# -*- coding: utf-8 -*-
"""Общие хелперы страницы «Расчёт» (параметры распределения / этапы Коэфф–Распред–Топливо)."""
from urllib.parse import urlparse

from flask import redirect, request, url_for

# После успешного POST этапа «Распред» — сырой JSON-сериализуемый словарь для таблицы на GET /fuel/calculation.
FUEL_DISTRIBUTION_LAST_RUN_SESSION_KEY = "fuel_distribution_last_run"


def redirect_back_after_post():
    """После POST сохраняем query string страницы расчёта (фильтры), если referrer локальный."""
    ref = (request.referrer or "").strip()
    if ref:
        try:
            path = urlparse(ref).path.rstrip("/")
            if path.endswith("/fuel/calculation"):
                return redirect(ref)
        except Exception:
            pass
    return redirect(url_for("fuel_bp.fuel_calculation_form"))
