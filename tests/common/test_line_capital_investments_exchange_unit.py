# -*- coding: utf-8 -*-
"""Юнит-тесты заглушки line_capital_investments."""
from app.api.services import line_capital_investments_exchange_services as svc


def test_stub_row_has_contract_keys_and_zeros():
    row = svc.build_line_capital_investments_stub_row()
    assert list(row.keys()) == [
        "Название линии",
        "Класс напряжения, кВ",
        "Зона",
        (
            "Входит в развитие объектов электросетевого хозяйства, обеспечивающих "
            "выдачу мощности объектов по производству электрической энергии"
        ),
        "external_code",
    ]
    assert row["Название линии"] == ""
    assert row["Класс напряжения, кВ"] == 0
    assert row["Зона"] == ""
    assert (
        row[
            "Входит в развитие объектов электросетевого хозяйства, обеспечивающих "
            "выдачу мощности объектов по производству электрической энергии"
        ]
        is False
    )
    assert row["external_code"] == ""


def test_load_line_capital_investments_stub_envelope(monkeypatch):
    monkeypatch.setattr(
        "app.api.services.exchange_common_services.resolve_database_version",
        lambda version_id: (46, "ГС-2026"),
    )
    payload = svc.load_line_capital_investments_dataset(version_id=46, year=2025)
    assert payload["dataset"] == "line_capital_investments"
    assert payload["database_version"] == 46
    assert payload["version"] == 46
    assert "нет в АРМ" in payload["comment"]
    assert "заполняются вручную" in payload["comment"]
    assert payload["rows"] == [svc.build_line_capital_investments_stub_row()]
