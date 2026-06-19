# -*- coding: utf-8 -*-
"""Общие хелперы маршрутов электроёмкости."""

from __future__ import annotations

from flask import redirect, request, session, url_for

from app.energy_consumption.forms.energy_consumption_parameter_forms import EmptyCSRFForm

EI_FO_ENDPOINT = "electrical_intensity_root_bp.electrical_intensity"


def csrf():
    return EmptyCSRFForm()


def csrf_ok() -> bool:
    """Проверка CSRF для AJAX (токен из session, как в fuel batch UI)."""
    expected = session.get("csrf_token") or ""
    if not str(expected).strip():
        return True
    token = (
        request.headers.get("X-CSRF-Token")
        or request.headers.get("X-CSRFToken")
        or (request.get_json(silent=True) or {}).get("csrf_token")
        or request.form.get("csrf_token")
    )
    return bool(token) and token == expected


def redirect_preserving_query(endpoint: str = EI_FO_ENDPOINT, **extra):
    qs = (request.form.get("preserve_qs") or "").strip()
    if qs:
        base = url_for(endpoint, **extra)
        return redirect(f"{base}?{qs}" if "?" not in base else f"{base}&{qs}")
    args = {k: v for k, v in request.args.items(multi=True)}
    flat: dict = {}
    for k, v in args.items():
        flat[k] = v[0] if isinstance(v, list) and len(v) == 1 else v
    flat.update(extra)
    return redirect(url_for(endpoint, **flat))


def parse_rounding_digits() -> int:
    raw = request.args.get("rounding_digits")
    if request.method == "POST" and (raw is None or str(raw).strip() == ""):
        raw = request.form.get("rounding_digits")
    if raw is None or str(raw).strip() == "":
        return 1
    try:
        v = int(raw)
    except (ValueError, TypeError):
        return 1
    if v in (0, 1, 2, 3, -1):
        return v
    return 1


def parse_ei_export_years_list(full_years: list[int]) -> list[int] | None:
    """GET export_years=2015,2016,... — подмножество full_years, порядок как в запросе."""
    raw = request.args.get("export_years")
    if raw is None or str(raw).strip() == "":
        return None
    allowed = set(full_years)
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    if not parts:
        return None
    out: list[int] = []
    for p in parts:
        try:
            y = int(p)
        except (TypeError, ValueError):
            return None
        if y not in allowed:
            return None
        if y not in out:
            out.append(y)
    return out
