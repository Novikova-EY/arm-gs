# -*- coding: utf-8 -*-
"""Списки «Год начала» / «Год конца» на карточке агрегата – как на station_details.

Источник значений – справочник Year текущей версии БД (см. `get_filter_year_list`),
поэтому карточка агрегата и карточка станции показывают одинаковые годы.
"""
from __future__ import annotations

import ast
import os
from types import SimpleNamespace

import pytest

from app.generation.services.station_services import generation_year_filter_services


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEMPLATES_DIR = os.path.join(PROJECT_ROOT, "app", "templates", "generation", "stations")

MACHINE_TEMPLATE = "machine_details.html"
PGU_MACHINE_TEMPLATE = "pgu_machine_details.html"
STATION_TEMPLATE = "station_details.html"


def _template_text(template_name: str) -> str:
    path = os.path.join(TEMPLATES_DIR, template_name)
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _source_text(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _years_select_block(template_name: str, select_id: str) -> str:
    text = _template_text(template_name)
    start = text.index(f'id="{select_id}"')
    end = text.index("</select>", start)
    return text[start:end]


@pytest.mark.parametrize("select_id", ["start_year", "end_year"])
@pytest.mark.parametrize("template_name", [MACHINE_TEMPLATE, PGU_MACHINE_TEMPLATE])
def test_year_selects_use_filter_year_list(template_name, select_id):
    block = _years_select_block(template_name, select_id)

    assert "{% for year in filter_year_list %}" in block
    # захардкоженных диапазонов быть не должно – иначе список лет расходится со station_details
    assert "range(" not in block


@pytest.mark.parametrize("select_id", ["start_year", "end_year"])
def test_station_details_uses_same_source(select_id):
    block = _years_select_block(STATION_TEMPLATE, select_id)

    assert "filter_year_list" in block


def test_get_filter_year_list_uses_year_reference(monkeypatch):
    monkeypatch.setattr(
        generation_year_filter_services,
        "get_year_list_full",
        lambda: [SimpleNamespace(number=2019), SimpleNamespace(number=2032)],
    )
    assert generation_year_filter_services.get_filter_year_list() == [2019, 2032]


def test_get_filter_year_list_falls_back_to_planning_period(monkeypatch):
    monkeypatch.setattr(generation_year_filter_services, "get_year_list_full", lambda: [])
    monkeypatch.setattr(
        generation_year_filter_services, "get_filter_start_year", lambda: 2024
    )
    monkeypatch.setattr(
        generation_year_filter_services, "get_filter_end_year", lambda: 2026
    )
    assert generation_year_filter_services.get_filter_year_list() == [2024, 2025, 2026]


def test_render_helper_passes_filter_year_list(monkeypatch):
    from app.generation.services.machine_services import machine_services

    captured = {}
    monkeypatch.setattr(
        machine_services,
        "get_current_version_year_range_from_name",
        lambda: (2024, 2032),
    )
    monkeypatch.setattr(
        machine_services,
        "get_filter_year_list",
        lambda: [2019, 2020],
    )

    def _fake_render(template_name, **kwargs):
        captured["template_name"] = template_name
        captured["kwargs"] = kwargs
        return ""

    monkeypatch.setattr(machine_services, "render_template", _fake_render)

    machine_services._render_machine_details_form_response(
        main_form=None,
        advanced_form=None,
        pgu_machines_form=None,
        station=None,
        machine=None,
        start_year=2019,
        end_year=2032,
        rounding_digits=1,
        year_features={},
        all_documents=[],
        fuel_can_create_machine=False,
    )

    assert captured["template_name"] == "generation/stations/machine_details.html"
    assert captured["kwargs"]["filter_year_list"] == [2019, 2020]


def _render_template_calls_without_year_list(path: str) -> list[int]:
    tree = ast.parse(_source_text(path))
    missing = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Name) and func.id == "render_template"):
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant):
            continue
        template_name = node.args[0].value
        if template_name not in (
            "generation/stations/machine_details.html",
            "generation/stations/pgu_machine_details.html",
        ):
            continue
        if "filter_year_list" not in {kw.arg for kw in node.keywords}:
            missing.append(node.lineno)
    return missing


def test_all_machine_details_renders_pass_filter_year_list():
    files = [
        os.path.join(
            PROJECT_ROOT, "app", "generation", "routes", "stations", "machine_routes.py"
        ),
        os.path.join(
            PROJECT_ROOT,
            "app",
            "generation",
            "services",
            "machine_services",
            "machine_services.py",
        ),
    ]
    for path in files:
        assert _render_template_calls_without_year_list(path) == [], path
