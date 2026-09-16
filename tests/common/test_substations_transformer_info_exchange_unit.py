# -*- coding: utf-8 -*-
"""Юнит-тесты заглушки substations_transformer_info."""
from app.api.services import substations_transformer_info_exchange_services as svc


def test_stub_row_has_contract_keys_and_zeros():
    row = svc.build_substations_transformer_info_stub_row()
    assert list(row.keys()) == [
        "Название подстанции",
        "Субъект подстанции",
        "Год",
        "Класс напряжения ПС, кВ",
        "Название трансформатора",
        "Тип трансформатора",
        "Год ввода трансформатора в эксплуатацию",
        "ИТС",
        "Мощность трансформатора, МВт",
        "Фактическая нагрузка, день зимнего контрольного замера, МВА",
        "Фактическая нагрузка, день летнего контрольного замера, МВА",
        (
            "Объем перевода нагрузки по сети 6–35 кВ в течение 20 минут "
            "после нормативных возмущений, МВА"
        ),
        "external_code",
    ]
    assert row["Название подстанции"] == ""
    assert row["Субъект подстанции"] == ""
    assert row["Год"] == 0
    assert row["Класс напряжения ПС, кВ"] == ""
    assert row["Название трансформатора"] == ""
    assert row["Тип трансформатора"] == ""
    assert row["Год ввода трансформатора в эксплуатацию"] == 0
    assert row["ИТС"] == 0
    assert row["Мощность трансформатора, МВт"] == 0
    assert row["Фактическая нагрузка, день зимнего контрольного замера, МВА"] == 0
    assert row["Фактическая нагрузка, день летнего контрольного замера, МВА"] == 0
    assert row[svc.KEY_LOAD_TRANSFER] == 0
    assert row["external_code"] == ""


def test_load_substations_transformer_info_stub_envelope(monkeypatch):
    monkeypatch.setattr(
        "app.api.services.exchange_common_services.resolve_database_version",
        lambda version_id: (46, "ГС-2026"),
    )
    payload = svc.load_substations_transformer_info_dataset(version_id=46, year=2025)
    assert payload["dataset"] == "substations_transformer_info"
    assert payload["database_version"] == 46
    assert payload["version"] == 46
    assert "нет в АРМ" in payload["comment"]
    assert "заполняются вручную" in payload["comment"]
    assert payload["rows"] == [svc.build_substations_transformer_info_stub_row()]
