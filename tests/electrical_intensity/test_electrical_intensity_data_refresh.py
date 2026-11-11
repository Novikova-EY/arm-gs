from datetime import datetime
from types import SimpleNamespace

from flask import g, request
from sqlalchemy import Column, Integer, create_engine, event
from sqlalchemy.orm import Session, declarative_base

from app.electrical_intensity.routes.electrical_intensity_root_bp import (
    electrical_intensity_root_bp,
)
from app.electrical_intensity.services import data_refresh_services as refresh

Base = declarative_base()


class EconomicsSource(Base):
    __module__ = "app.economics.models.test_electrical_intensity_refresh"
    __tablename__ = "ei_refresh_economics_source"
    id = Column(Integer, primary_key=True)
    value = Column(Integer)


def test_economics_commits_advance_electrical_intensity_revision(monkeypatch):
    monkeypatch.setattr(refresh, "get_redis_client", lambda: None)
    monkeypatch.setattr(refresh, "_data_revision", 0)
    handlers = (
        ("after_flush", refresh._tracker._after_flush),
        ("do_orm_execute", refresh._tracker._orm_write),
        ("after_commit", refresh._tracker._after_commit),
        ("after_soft_rollback", refresh._tracker._after_soft_rollback),
    )
    registered = {
        name for name, handler in handlers if event.contains(Session, name, handler)
    }
    refresh.init_electrical_intensity_change_events()
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            session.add(EconomicsSource(value=10))
            session.commit()
            assert refresh.get_electrical_intensity_data_revision() == 1

            row = session.get(EconomicsSource, 1)
            row.value = 20
            session.commit()
            assert refresh.get_electrical_intensity_data_revision() == 2

            session.delete(row)
            session.commit()
            assert refresh.get_electrical_intensity_data_revision() == 3
    finally:
        engine.dispose()
        for name, handler in handlers:
            if name not in registered:
                event.remove(Session, name, handler)


def test_electrical_intensity_refresh_routes_clear_sources_and_disable_http_cache(
    app, monkeypatch
):
    from app.electrical_intensity.routes import data_refresh_routes as routes

    app.register_blueprint(electrical_intensity_root_bp, url_prefix="/electrical_intensity")
    monkeypatch.setattr(routes, "get_current_db_version_id", lambda: 7)
    monkeypatch.setattr(refresh, "get_redis_client", lambda: None)
    monkeypatch.setattr(refresh, "_data_revision", 4)
    invalidate = []
    monkeypatch.setattr(
        routes,
        "invalidate_economics_fd_data_cache",
        lambda version_id: invalidate.append(version_id),
    )

    client = app.test_client()
    status = client.get("/electrical_intensity/data-revision/")
    assert status.status_code == 200
    assert status.json == {"ok": True, "revision": "7:data:4"}
    assert "no-store" in status.headers["Cache-Control"]

    refreshed = client.post("/electrical_intensity/refresh-data/")
    assert refreshed.status_code == 200
    assert refreshed.json == {"ok": True, "revision": "7:data:4"}
    assert "no-store" in refreshed.headers["Cache-Control"]
    assert invalidate == [7]


def test_electrical_intensity_refresh_context_includes_page_generation_time(app):
    from app.electrical_intensity.routes import data_refresh_routes as routes

    app.register_blueprint(electrical_intensity_root_bp, url_prefix="/electrical_intensity")
    with app.test_request_context("/"):
        request.url_rule = SimpleNamespace(endpoint=routes._PAGE_ENDPOINT)
        g.electrical_intensity_page_revision = "7:data:4"

        context = routes.inject_data_refresh()["electrical_intensity_refresh"]

    generated_at = datetime.fromisoformat(context["loadedAt"])
    assert generated_at.tzinfo is not None


def test_electrical_intensity_page_includes_refresh_control(app):
    app.jinja_env.get_template("electrical_intensity/electrical_intensity.html")
    template, *_ = app.jinja_loader.get_source(
        app.jinja_env, "electrical_intensity/electrical_intensity.html"
    )
    assert "common/_data_refresh.html" in template
    assert "electrical_intensity_refresh" in template
    assert template.index("common/_data_refresh.html") < template.index(
        'for="rounding_digits"'
    )
