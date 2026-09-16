# -*- coding: utf-8 -*-
"""Юнит-тесты заглушки substations_customers_info."""
from app.api.services import substations_customers_info_exchange_services as svc


def test_stub_row_has_contract_keys_and_zeros():
    row = svc.build_substations_customers_info_stub_row()
    assert list(row.keys()) == [
        "Название подстанции",
        (
            "Общая информация по заявителю/дате заключения договора/номера договора "
            "(если есть)"
        ),
        "Заявитель",
        "Дата заключения договора ТП ",
        "Номер договора ТП",
        "Планируемый год реализации ТП",
        "Максимальная мощность по ТУ для ТП, МВт",
        "Ранее присоединенная мощность (по документам о ТП), МВт",
        "Uном перспективной нагрузки, кВ",
        "Прирост нагрузки по ТУ для ТП с учетом коэффициента набора, МВт",
        "Наименование ПС",
        "external_code",
    ]
    assert row["Название подстанции"] == ""
    assert row["Заявитель"] == ""
    assert row["Дата заключения договора ТП "] == ""
    assert row["Номер договора ТП"] == ""
    assert row["Планируемый год реализации ТП"] == 0
    assert row["Максимальная мощность по ТУ для ТП, МВт"] == 0
    assert row["Ранее присоединенная мощность (по документам о ТП), МВт"] == 0
    assert row["Uном перспективной нагрузки, кВ"] == 0
    assert row["Прирост нагрузки по ТУ для ТП с учетом коэффициента набора, МВт"] == 0
    assert row["Наименование ПС"] == ""
    assert row["external_code"] == ""


def test_load_substations_customers_info_stub_envelope(monkeypatch):
    monkeypatch.setattr(
        "app.api.services.exchange_common_services.resolve_database_version",
        lambda version_id: (46, "ГС-2026"),
    )
    payload = svc.load_substations_customers_info_dataset(version_id=46, year=2025)
    assert payload["dataset"] == "substations_customers_info"
    assert payload["database_version"] == 46
    assert payload["version"] == 46
    assert "2027" in payload["comment"]
    assert "будет реализовано" in payload["comment"].casefold()
    assert "потребители" in payload["comment"]
    assert payload["rows"] == [svc.build_substations_customers_info_stub_row()]
