from pathlib import Path
import re
from types import SimpleNamespace

import pytest
from flask import g
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader

from app.common.services.get_services.years import years_get_services as years
from app.refdata.routes import refdata_routes as routes
from app.refdata.services import year_management_services as services
from app.refdata.services.years import year_services


@pytest.mark.parametrize(
    ("current_year", "expected"),
    [
        (None, None), (0, None), (2023, None),
        (2024, 2042), (2025, 2042), (2027, 2042), (2029, 2042),
        (2030, 2048), (2033, 2048), (2035, 2048),
        (2036, 2054), (2039, 2054), (2041, 2054), (2042, 2060),
    ],
)
def test_general_scheme_cycle(current_year, expected):
    assert services.get_general_scheme_end_year(current_year) == expected


@pytest.fixture
def render_refdata(monkeypatch):
    templates = Path(__file__).resolve().parents[2] / "app" / "templates"
    env = Environment(
        loader=ChoiceLoader([
            DictLoader({"base.html": "{% block content %}{% endblock %}"}),
            FileSystemLoader(templates),
        ]),
        autoescape=True,
    )

    def render(template, **context):
        return env.get_template(template).render(
            **context,
            current_user=SimpleNamespace(is_authenticated=True, has_admin=False),
            url_for=lambda endpoint: "/" + endpoint,
        )

    monkeypatch.setattr(routes, "render_template", render)


@pytest.mark.parametrize(
    ("version_id", "current_year", "expected"),
    [(1, 2024, "2025&nbsp;–&nbsp;2042"),
     (2, 2027, "2028&nbsp;–&nbsp;2042"),
     (3, 2030, "2031&nbsp;–&nbsp;2048"),
     (4, 2033, "2034&nbsp;–&nbsp;2048"),
     (5, 0, "не установлен"),
     (6, 2023, "не установлен"),
     (None, 0, "не установлен")],
)
def test_refdata_general_scheme(client, monkeypatch, render_refdata,
                                version_id, current_year, expected):
    monkeypatch.setattr(routes, "get_current_version", lambda: version_id)
    monkeypatch.setattr(routes, "get_reference_years", lambda: [])

    def year_info(selected_version):
        assert selected_version == version_id
        assert selected_version is not None
        return {"current_year": current_year, "sipr_start": current_year + 1,
                "sipr_end": current_year + 6}

    monkeypatch.setattr(routes, "get_current_year_info", year_info)
    response = client.get("/refdata/")
    assert response.status_code == 200
    cell = response.get_data(as_text=True).split("Генеральная схема:</span>", 1)[1]
    cell = cell.split('class="form-control', 1)[1].split("</div>", 1)[0]
    assert expected in cell
    assert "None" not in cell


@pytest.fixture
def reference_year_catalog(app, monkeypatch):
    catalog = {
        "version": 1,
        "rows": {1: [2150, 1990, 2030, 1990], 2: [2048, 2024], 3: []},
    }

    @app.before_request
    def select_version():
        g.current_db_version = catalog["version"]

    monkeypatch.setattr(routes, "get_current_version", lambda: g.current_db_version)
    monkeypatch.setattr(
        year_services, "year_query",
        lambda: SimpleNamespace(all=lambda: [
            SimpleNamespace(number=number)
            for number in catalog["rows"][g.current_db_version]
        ]),
    )
    monkeypatch.setattr(
        routes, "get_current_year_info",
        lambda pk: {"current_year": 2030, "sipr_start": 2031, "sipr_end": 2036},
    )
    return catalog


def test_current_year_select_uses_reference_catalog(client, render_refdata,
                                                  reference_year_catalog):
    for version, expected in [
        (1, [0, 1990, 2030, 2150]), (2, [0, 2024, 2048]), (3, [0]), (None, [0]),
    ]:
        reference_year_catalog["version"] = version
        response = client.get("/refdata/")
        assert response.status_code == 200
        select = re.search(
            r'<select[^>]*id="current-year-select"[^>]*>(.*?)</select>',
            response.get_data(as_text=True), re.S,
        ).group(1)
        assert [int(y) for y in re.findall(r'<option value="(\d+)"', select)] == expected
        if version == 1:
            assert re.search(r'<option value="2030"\s+selected', select)

    reference_year_catalog["version"] = 1
    reference_year_catalog["rows"][1] = [2054]
    response = client.get("/refdata/")
    select = re.search(
        r'<select[^>]*id="current-year-select"[^>]*>(.*?)</select>',
        response.get_data(as_text=True), re.S,
    ).group(1)
    assert [int(y) for y in re.findall(r'<option value="(\d+)"', select)] == [0, 2054]


@pytest.mark.parametrize(
    ("version", "submitted", "accepted"),
    [(1, "1990", True), (1, "2150", True), (1, "2030", True),
     (1, "2024", False), (1, "2026", False), (1, "0", False),
     (1, "invalid", False), (2, "2024", True), (3, "2030", False),
     (None, "2030", False)],
)
def test_current_year_save_requires_catalog_membership(
    client, monkeypatch, reference_year_catalog, version, submitted, accepted,
):
    from app.auth.routes import decorators

    admin = SimpleNamespace(is_authenticated=True, roles=[SimpleNamespace(name="admin")])
    monkeypatch.setattr(decorators, "current_user", admin)
    monkeypatch.setattr(routes, "current_user", admin)
    updates = []

    def update(version_id, year, user):
        updates.append((version_id, year))
        return True, "Текущий год успешно обновлен"

    monkeypatch.setattr(routes, "update_current_year", update)
    reference_year_catalog["version"] = version
    response = client.post("/refdata/update_current_year", data={"current_year": submitted})
    assert response.status_code == 302
    assert updates == ([(version, int(submitted))] if accepted else [])


def test_general_scheme_filters_are_version_scoped(monkeypatch):
    version_years = {1: 2027, 2: 2030, 3: 2033, 4: 2036, 5: 0, 6: 2023}
    monkeypatch.setattr(
        years.db, "session",
        SimpleNamespace(get=lambda model, pk: SimpleNamespace(
            version_number="ГС 2024-2042", description=None)),
    )
    monkeypatch.setattr(years, "_year_service_sipr_bounds", lambda pk: (2028, 2033))
    monkeypatch.setattr(
        services, "get_current_year_info",
        lambda pk: {"current_year": version_years[pk]},
    )
    years.clear_planning_period_year_caches()
    try:
        for version_id, expected_end in [
            (1, 2042), (2, 2048), (3, 2048), (4, 2054),
            (5, years.Config.END_YEAR), (6, years.Config.END_YEAR), (1, 2042),
        ]:
            assert years._get_planning_period_years_for_version(version_id) == (
                2026, expected_end)
    finally:
        years.clear_planning_period_year_caches()


def test_changing_current_year_clears_cached_general_scheme_end(monkeypatch):
    year_service = SimpleNamespace(year_sipr_start=2030, year_sipr_end=2035)
    year = SimpleNamespace(number=2030, id_year_feature=1)
    features = {"факт": 1, "текущий (оценка)": 2, "план": 3}

    class Query:
        def __init__(self, model):
            self.model = model
            self.filters = {}

        def filter_by(self, **filters):
            self.filters = filters
            return self

        def filter(self, *args):
            return self

        def first(self):
            if self.model is services.YearFeature:
                return SimpleNamespace(id=features[self.filters["name"]])
            if self.model is services.YearService:
                return year_service
            return year

        def all(self):
            return [year]

    monkeypatch.setattr(
        services, "DatabaseVersion",
        SimpleNamespace(query=SimpleNamespace(get=lambda pk: SimpleNamespace(id=pk))),
    )
    monkeypatch.setattr(
        services.db, "session",
        SimpleNamespace(query=Query, commit=lambda: None),
    )
    monkeypatch.setattr(services, "log_to_db", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        years, "_get_planning_period_years_for_version",
        lambda pk: (2028, services.get_general_scheme_end_year(year_service.year_sipr_start - 1)),
    )
    years.clear_planning_period_year_caches()
    try:
        assert years._get_filter_end_year_for_version(1) == 2042
        success, message = services.update_current_year(1, 2030, SimpleNamespace(id=1))
        assert success, message
        assert years._get_filter_end_year_for_version(1) == 2048
    finally:
        years.clear_planning_period_year_caches()


def test_sipr_filters_keep_service_bounds(monkeypatch):
    monkeypatch.setattr(
        years.db, "session",
        SimpleNamespace(get=lambda model, pk: SimpleNamespace(
            version_number="СиПР 2031-2036", description=None)),
    )
    monkeypatch.setattr(years, "_year_service_sipr_bounds", lambda pk: (2031, 2036))
    assert years._get_planning_period_years_for_version.__wrapped__(7) == (2029, 2036)
