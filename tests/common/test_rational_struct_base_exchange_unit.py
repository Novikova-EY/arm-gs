# -*- coding: utf-8 -*-
"""Юнит-тесты заглушки rational_struct_base."""
from app.api.services import rational_struct_base_exchange_services as svc


def test_stub_row_has_contract_keys_and_zeros():
    row = svc.build_rational_struct_base_stub_row()
    assert list(row.keys()) == [
        "Тип станций",
        "Год",
        "Базовые удельные капитальные затраты, тыс. руб./кВт",
        "Условно-постоянные затраты, тыс. руб./кВт/год",
        "Удельный расход условного топлива, ",
        "в конденсационном режиме, г у.т./кВт•ч",
        "в теплофикационном режиме, г у.т./кВт•ч",
        "Топливные затраты, руб./кВт•ч",
        "Расход электрической энергии на собственные нужды, %",
        "Срок строительства, лет",
        "Число часов использования установленной мощности, ч/год",
        "Затраты на вывод из эксплуатации, тыс. руб./кВт",
        "ОЭС",
        "Цена топлива на год, тыс. руб./т у.т.",
        "Региональный коэффициент удорожания, ",
        "LCOE (базовые), руб./кВт•ч в ценах расчетного года",
        "LCOE (пиковые), руб./кВт•ч в ценах расчетного года",
        "LCOE (негарантированные), руб./кВт•ч в ценах расчетного года",
        "external_code",
    ]
    assert row["Тип станций"] == ""
    assert row["Год"] == 0
    assert row["ОЭС"] == ""
    assert row["Цена топлива на год, тыс. руб./т у.т."] == 0.0
    assert row["LCOE (базовые), руб./кВт•ч в ценах расчетного года"] == 0.0
    assert row["external_code"] == ""


def test_load_rational_struct_base_stub_envelope(monkeypatch):
    monkeypatch.setattr(
        "app.api.services.exchange_common_services.resolve_database_version",
        lambda version_id: (46, "ГС-2026"),
    )
    payload = svc.load_rational_struct_base_dataset(version_id=46, year=2025)
    assert payload["dataset"] == "rational_struct_base"
    assert payload["database_version"] == 46
    assert payload["version"] == 46
    assert "будет разработано в 2027 году" in payload["comment"]
    assert "таблице 22" in payload["comment"]
    assert "таблице 23" in payload["comment"]
    assert "таблице 24" in payload["comment"]
    assert payload["rows"] == [svc.build_rational_struct_base_stub_row()]
