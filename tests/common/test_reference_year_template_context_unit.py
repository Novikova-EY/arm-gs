"""Проверки моделей годов и контекста шаблонов в реальной фабрике приложения."""

import re
from types import SimpleNamespace

import pytest
from redis.exceptions import ConnectionError

from app import create_app
from app.refdata.services.years import year_services
from config import Config


@pytest.fixture(autouse=True)
def _patch_infrastructure():
    # Общая фикстура подменяет модели и render_template, здесь нужна реальная фабрика.
    yield


@pytest.fixture
def template_app(monkeypatch):
    def redis_unavailable(*args, **kwargs):
        raise ConnectionError("Redis отключен для проверки шаблонов")

    monkeypatch.setenv("SKIP_CACHE_WARMUP", "true")
    monkeypatch.setattr(Config, "ENABLE_SCHEDULED_BACKUPS", False)
    monkeypatch.setattr("app.redis.from_url", redis_unavailable)
    monkeypatch.setattr("app.Session", lambda app: None)
    return create_app()


def test_factory_registers_electrical_intensity_year_relationships(template_app):
    from sqlalchemy import inspect

    from app.electrical_intensity.models.federal_district_electrical_intensity_year_parameter_model import (
        FederalDistrictElectricalIntensityYearParameter,
    )
    from app.electrical_intensity.models.russia_federation_electrical_intensity_year_parameter_model import (
        RussiaFederationElectricalIntensityYearParameter,
    )
    from app.refdata.models.years.year_model import Year

    year_mapper = inspect(Year)
    for relationship_name, model in (
        ("fd_electrical_intensity_year_parameters", FederalDistrictElectricalIntensityYearParameter),
        ("rf_electrical_intensity_year_parameters", RussiaFederationElectricalIntensityYearParameter),
    ):
        relationship = year_mapper.relationships[relationship_name]
        assert relationship.mapper.class_ is model
        assert inspect(model).relationships["year"].mapper.class_ is Year


@pytest.mark.parametrize("years", [[2015, 2024, 2048], []])
def test_summary_period_filters_render_with_factory_template_globals(template_app, monkeypatch, years):
    calls = []

    def year_query():
        calls.append(True)
        return SimpleNamespace(all=lambda: [SimpleNamespace(number=year) for year in years])

    monkeypatch.setattr(year_services, "year_query", year_query)
    source, _, _ = template_app.jinja_env.loader.get_source(
        template_app.jinja_env, "energy_consumption/pages/summary_oes_body.html",
    )
    selects = re.findall(r'<select\b[^>]*name="(?:start_year|end_year)"[^>]*>.*?</select>', source, re.S)
    assert len(selects) == 2
    template = template_app.jinja_env.from_string("".join(selects))

    with template_app.test_request_context():
        rendered = template.render(start_year=2024, end_year=2048)

    options = [int(value) for value in re.findall(r'<option value="(\d+)"', rendered)]
    assert options == years * 2
    assert len(calls) == 1
