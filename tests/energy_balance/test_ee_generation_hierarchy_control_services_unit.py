from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.energy_balance.services import ee_generation_hierarchy_control_services as controls


class _Column:
    def __eq__(self, other):
        return self

    def __ge__(self, other):
        return self

    def __le__(self, other):
        return self

    def between(self, lower, upper):
        return self


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *conditions):
        return self

    def all(self):
        return self.rows


class _ControlModel:
    year_number = _Column()
    month_number = _Column()


@pytest.fixture

def fake_control_query(monkeypatch):
    monkeypatch.setattr(controls, "_ensure_tables", lambda: None)
    monkeypatch.setattr(controls, "filter_by_db_version", lambda query, model: query)

    def load_rows(rows):
        monkeypatch.setattr(controls, "EnergySystemEnergyGenerationControl", _ControlModel)
        monkeypatch.setattr(_ControlModel, "query", _Query(rows), raising=False)

    return load_rows


def test_load_hierarchy_controls_uses_year_as_period_key(fake_control_query):
    fake_control_query(
        [
            SimpleNamespace(
                level="est",
                entity_id=164,
                year_number=2024,
                month_number=0,
                electricity_generation=Decimal("17.5"),
            )
        ]
    )

    result = controls.load_hierarchy_control_generation(2020, 2025)

    assert result["est"][164] == {2024: Decimal("17.5")}


def test_load_hierarchy_controls_uses_month_as_period_key(fake_control_query):
    fake_control_query(
        [
            SimpleNamespace(
                level="est",
                entity_id=164,
                year_number=2025,
                month_number=1,
                electricity_generation=Decimal("1.25"),
            ),
            SimpleNamespace(
                level="est",
                entity_id=164,
                year_number=2025,
                month_number=12,
                electricity_generation=Decimal("2.75"),
            ),
        ]
    )

    result = controls.load_hierarchy_control_generation(
        2025, 2025, period_mode="months", selected_year=2025
    )

    assert result["est"][164] == {1: Decimal("1.25"), 12: Decimal("2.75")}
