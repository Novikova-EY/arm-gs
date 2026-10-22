"""Отправка, отклонение и акцепт не должны смешивать годы и версии."""
from decimal import Decimal

from flask import Flask
import pytest

import app.electrical_intensity.models  # noqa: F401
from app.ecology.models.fuel_exchange_model import EcologyFuelSnapshot, EcologyFuelSubmission
from app.ecology.models.operating_tes_input_model import OperatingTesInputValue
from app.ecology.services import fuel_exchange_services as service
from app.extensions import db


@pytest.fixture
def exchange(monkeypatch):
    app = Flask(__name__)
    models = (EcologyFuelSnapshot, EcologyFuelSubmission, OperatingTesInputValue)
    app.config.update(
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_ENGINE_OPTIONS={"execution_options": {"schema_translate_map": {model.__table__.schema: None for model in models}}},
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    # Некоторые старые unit-модули подменяют глобальную сессию при импорте.
    monkeypatch.setattr(db, "session", db._make_scoped_session({}))
    with app.app_context():
        for model in models:
            model.__table__.create(db.engine)
        monkeypatch.setattr(service, "get_current_db_version_id", lambda: 1)
        monkeypatch.setattr(service, "get_fuel_module_consumption_row_specs", lambda: [{"key": "b", "label": "Расход топлива"}])
        live = {2026: {"vsego": {"b": Decimal("123.456789"), "e": Decimal("2500")}}}
        from app.ecology.services import fuel_summary_services

        monkeypatch.setattr(fuel_summary_services, "load_fuel_summary", lambda years, scope="operating": {year: live.get(year, {}) for year in years})
        db.session.add_all([
            EcologyFuelSnapshot(database_version_id=version, year_number=year, payload={"vsego": {"b": "10", "e": "1000"}})
            for version, year in ((1, 2026), (1, 2027), (2, 2026))
        ])
        db.session.commit()
        yield live
        db.session.remove()


def test_send_freezes_payload_without_changing_accepted_data(exchange):
    sent = service.submit_fuel_year(2026)
    exchange[2026]["vsego"]["b"] = Decimal("999")
    assert service.load_accepted_fuel_inputs([2026])[2026]["vsego"]["b"] == 10
    assert service.decode_inputs(sent.payload)["vsego"]["b"] == Decimal("123.456789")
    assert service.pending_submissions([2026]) == [sent]
    diff = service.submission_differences(sent)
    fuel = next(row for row in diff if row["label"] == "Расход топлива")
    assert fuel["before"] == 10
    assert fuel["after"] == Decimal("123.456789")
    assert fuel["delta"] == Decimal("113.456789")
    electricity = next(row for row in diff if row["label"] == "Выработка электроэнергии")
    assert electricity["before"] == 1
    assert electricity["after"] == Decimal("2.5")


def test_reject_clears_notification_but_keeps_accepted_and_allows_resend(exchange):
    sent = service.submit_fuel_year(2026)
    service.review_fuel_submission(sent.id, accept=False)
    assert service.pending_submissions([2026]) == []
    assert service.load_accepted_fuel_inputs([2026])[2026]["vsego"]["b"] == 10
    assert sent.status == "rejected"
    assert sent.reviewed_at is not None
    newer = service.submit_fuel_year(2026)
    assert service.pending_submissions([2026]) == [newer]
    with pytest.raises(ValueError, match="уже рассмотрен"):
        service.review_fuel_submission(sent.id, accept=True)


def test_accept_replaces_only_selected_year_and_version(exchange):
    db.session.add(OperatingTesInputValue(database_version_id=1, territory_slug="vsego", year_number=2026, row_key="fuel_total", value=999))
    db.session.commit()
    sent = service.submit_fuel_year(2026)
    service.review_fuel_submission(sent.id, accept=True)
    assert service.load_accepted_fuel_inputs([2026, 2027])[2026]["vsego"]["b"] == Decimal("123.456789")
    assert service.load_accepted_fuel_inputs([2027])[2027]["vsego"]["b"] == 10
    assert EcologyFuelSnapshot.query.filter_by(database_version_id=2).one().payload["vsego"]["b"] == "10"
    assert OperatingTesInputValue.query.count() == 0
    assert service.pending_submissions([2026]) == []
    assert sent.status == "accepted"


def test_new_submission_supersedes_old_and_prevents_stale_accept(exchange):
    old = service.submit_fuel_year(2026)
    exchange[2026]["vsego"]["b"] = Decimal("200")
    new = service.submit_fuel_year(2026)
    assert old.status == "superseded"
    assert service.pending_submissions([2026]) == [new]
    with pytest.raises(ValueError, match="заменён"):
        service.review_fuel_submission(old.id, accept=True)
    service.review_fuel_submission(new.id, accept=True)
    assert service.load_accepted_fuel_inputs([2026])[2026]["vsego"]["b"] == 200


def test_empty_payload_clears_old_values_only_after_accept(exchange):
    exchange[2026] = {}
    sent = service.submit_fuel_year(2026)
    assert service.load_accepted_fuel_inputs([2026])[2026]["vsego"]["b"] == 10
    assert any(row["after"] == 0 for row in service.submission_differences(sent))
    service.review_fuel_submission(sent.id, accept=True)
    assert service.load_accepted_fuel_inputs([2026])[2026] == {}


def test_other_version_cannot_review_submission(exchange, monkeypatch):
    sent = service.submit_fuel_year(2026)
    monkeypatch.setattr(service, "get_current_db_version_id", lambda: 2)
    assert service.get_submission(sent.id) is None
    assert service.pending_submissions([2026]) == []
    with pytest.raises(ValueError, match="не найден"):
        service.review_fuel_submission(sent.id, accept=True)


def test_year_without_accepted_data_stays_empty_until_accept(exchange):
    exchange[2031] = {"vsego": {"b": Decimal("40")}}
    assert service.load_accepted_fuel_inputs([2031]) == {2031: {}}
    sent = service.submit_fuel_year(2031)
    assert service.load_accepted_fuel_inputs([2031]) == {2031: {}}
    service.review_fuel_submission(sent.id, accept=True)
    assert service.load_accepted_fuel_inputs([2031])[2031]["vsego"]["b"] == 40


@pytest.mark.parametrize("year", [2026, 2027])
def test_summary_submits_displayed_year_and_keeps_it_after_redirect(exchange, monkeypatch, year):
    from types import SimpleNamespace
    from flask import current_app
    from app.fuel.routes import ecology_summary_routes as routes

    app = current_app._get_current_object()
    app.secret_key = "test-secret"
    app.add_url_rule("/fuel/ecology_summary/", endpoint="fuel_bp.ecology_summary", view_func=lambda: "")
    exchange[2027] = {"vsego": {"b": Decimal("777")}}
    monkeypatch.setattr(routes, "current_user", SimpleNamespace(has_admin=True))
    monkeypatch.setattr(routes, "build_operating_tes_table_context", lambda *args, **kwargs: {
        "view_year": year, "range_years": [2026, 2027],
        "start_year": 2026, "end_year": 2027, "rounding_digits": 1,
    })
    from urllib.parse import parse_qs, urlsplit

    with app.test_request_context(f"/fuel/ecology_summary/?view_year={year}", method="POST", data={"year": "2031"}):
        response = routes.ecology_summary.__wrapped__()
        assert response.status_code == 302
        query = parse_qs(urlsplit(response.location).query)
        assert query == {
            "start_year": ["2026"], "end_year": ["2027"],
            "rounding_digits": ["1"], "view_year": [str(year)],
        }
    pending = service.pending_submissions([2026, 2027, 2031])
    assert [item.year_number for item in pending] == [year]
    assert service.decode_inputs(pending[0].payload)["vsego"]["b"] == exchange[year]["vsego"]["b"]


@pytest.mark.parametrize("scope", ["new_lt100", "new_ge100"])
def test_accept_new_category_keeps_other_categories_and_operating_overrides(exchange, scope):
    db.session.add(OperatingTesInputValue(database_version_id=1, territory_slug="vsego", year_number=2026, row_key="fuel_total", value=999))
    for category, value in (("new_lt100", "20"), ("new_ge100", "30")):
        db.session.add(EcologyFuelSnapshot(database_version_id=1, year_number=2026, scope=category, payload={"vsego": {"b": value}}))
        db.session.add(EcologyFuelSubmission(database_version_id=1, year_number=2026, scope=category, payload={"vsego": {"b": "55"}}, status="pending"))
    db.session.commit()
    sent = service.pending_submissions([2026], scope=scope)[0]
    diff = service.submission_differences(sent)
    fuel = next(row for row in diff if row["label"] == "Расход топлива")
    assert fuel["before"] == (20 if scope == "new_lt100" else 30)
    service.review_fuel_submission(sent.id, accept=True)
    assert service.load_accepted_fuel_inputs([2026], scope=scope)[2026]["vsego"]["b"] == 55
    other = "new_ge100" if scope == "new_lt100" else "new_lt100"
    assert service.load_accepted_fuel_inputs([2026], scope=other)[2026]["vsego"]["b"] == (30 if other == "new_ge100" else 20)
    assert service.load_accepted_fuel_inputs([2026])[2026]["vsego"]["b"] == 10
    assert OperatingTesInputValue.query.one().value == 999
    assert len(service.pending_submissions([2026], scope=other)) == 1
    assert service.pending_submissions([2026]) == []
    combined = service.load_accepted_new_tes_fuel_inputs([2026])[2026]["vsego"]
    assert combined["le100"]["b"] == (55 if scope == "new_lt100" else 20)
    assert combined["gt100"]["b"] == (55 if scope == "new_ge100" else 30)


def test_submission_supersedes_only_same_category_and_keeps_separate_acceptance(exchange):
    operating = service.submit_fuel_year(2026)
    small = service.submit_fuel_year(2026, scope="new_lt100")
    large = service.submit_fuel_year(2026, scope="new_ge100")
    replacement = service.submit_fuel_year(2026, scope="new_lt100")
    assert small.status == "superseded"
    assert operating.status == large.status == replacement.status == "pending"
    service.review_fuel_submission(replacement.id, accept=True)
    assert service.pending_submissions([2026]) == [operating]
    assert service.pending_submissions([2026], scope="new_ge100") == [large]
    assert service.load_accepted_fuel_inputs([2026])[2026]["vsego"]["b"] == 10
    assert service.load_accepted_fuel_inputs([2026], scope="new_ge100")[2026] == {}
    assert service.load_accepted_fuel_inputs([2026], scope="new_lt100")[2026]["vsego"]["b"] == Decimal("123.456789")


def test_new_summary_submission_keeps_category_in_redirect(exchange, monkeypatch):
    from types import SimpleNamespace
    from flask import current_app
    from urllib.parse import parse_qs, urlsplit
    from app.fuel.routes import ecology_summary_routes as routes

    app = current_app._get_current_object()
    app.secret_key = "test-secret"
    app.add_url_rule("/fuel/ecology_summary/", endpoint="fuel_bp.ecology_summary", view_func=lambda: "")
    monkeypatch.setattr(routes, "current_user", SimpleNamespace(has_admin=True))
    monkeypatch.setattr(routes, "build_operating_tes_table_context", lambda *args, **kwargs: {
        "view_year": 2026, "range_years": [2026, 2027],
        "start_year": 2026, "end_year": 2027, "rounding_digits": 1,
    })
    with app.test_request_context("/fuel/ecology_summary/?scope=new_ge100", method="POST"):
        response = routes.ecology_summary.__wrapped__()
    assert parse_qs(urlsplit(response.location).query)["scope"] == ["new_ge100"]
    assert service.pending_submissions([2026]) == []
    assert len(service.pending_submissions([2026], scope="new_ge100")) == 1


def test_ambiguous_summary_cannot_be_sent_even_by_direct_post(exchange, monkeypatch):
    from types import SimpleNamespace
    from flask import current_app
    from app.fuel.routes import ecology_summary_routes as routes
    from app.ecology.services import fuel_summary_services

    monkeypatch.setattr(routes, "current_user", SimpleNamespace(has_admin=True))
    monkeypatch.setattr(routes, "build_operating_tes_table_context", lambda *args, **kwargs: {
        "view_year": 2026, "range_years": [2026],
    })
    def unavailable(*args):
        raise fuel_summary_services.FuelSummaryError("Смешанная группа")
    monkeypatch.setattr(fuel_summary_services, "load_fuel_summary", unavailable)
    with current_app.test_request_context("/fuel/ecology_summary/?scope=new_lt100", method="POST"):
        body, status = routes.ecology_summary.__wrapped__()
    assert status == 409
    assert "Смешанная группа" in body
    assert EcologyFuelSubmission.query.count() == 0
