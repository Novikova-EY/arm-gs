# -*- coding: utf-8 -*-
"""Журнал модуля «Экология»: «было → стало» для изменяемых полей."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.ecology.services import analysis_param_services
from app.ecology.services import ecology_logging_services as logging_services
from app.ecology.services import new_tes_page_services
from app.ecology.services import operating_tes_page_services as operating_services


@pytest.fixture
def logged(monkeypatch):
    """Перехват записей журнала вместо записи в БД."""
    records: list[dict] = []

    def _log_to_db(user, action, details=None, entity_type=None, entity_id=None):
        records.append(
            {
                "user": user,
                "action": action,
                "details": details,
                "entity_type": entity_type,
            }
        )

    monkeypatch.setattr(logging_services, "log_to_db", _log_to_db)
    return records


class _FakeQuery:
    def __init__(self, row):
        self._row = row

    def filter_by(self, **_kwargs):
        return self

    def filter(self, *_args):
        return self

    def first(self):
        return self._row


def _patch_fake_session(monkeypatch, module):
    session = SimpleNamespace(add=lambda obj: None, commit=lambda: None)
    monkeypatch.setattr(module, "db", SimpleNamespace(session=session))


def test_value_change_formats_numbers_like_pages():
    assert (
        logging_services.value_change("Ap, %", None, "1.20")
        == "Ap, %: было не указано → стало 1,2"
    )
    assert (
        logging_services.value_change("Текст", "старый", "новый", number=False)
        == "Текст: было старый → стало новый"
    )


def test_change_lines_skips_unchanged_values():
    assert logging_services.change_lines(
        [
            ("Ap, %", Decimal("1.0"), "1"),
            ("K", Decimal("2"), Decimal("3")),
            ("Т", None, None),
        ]
    ) == ["K: было 2 → стало 3"]


def test_log_cell_change_writes_module_action_and_before_after(logged):
    logging_services.log_cell_change(
        "Коэффициенты – Всего",
        "КПД золоулавливания",
        Decimal("0.975"),
        Decimal("0.98"),
        context=["лист=Коэффициенты", "год=2026"],
    )

    assert logged == [
        {
            "user": None,
            "action": "Изменение: Экология – Коэффициенты – Всего",
            "details": (
                "лист=Коэффициенты; год=2026; "
                "КПД золоулавливания: было 0,975 → стало 0,98"
            ),
            "entity_type": "ecology",
        }
    ]


def test_log_cell_change_skips_equal_values(logged):
    logging_services.log_cell_change("Нормативы", "Зола", Decimal("1.50"), "1,5")
    assert logged == []


def test_log_page_visit_marks_page_and_tab(logged):
    logging_services.log_page_visit(
        "Действующие ТЭС",
        tab="Коэффициенты",
        details=["территория=Всего", "год=2026"],
    )

    record = logged[0]
    assert record["action"] == (
        "Открыта страница: Экология – Действующие ТЭС, вкладка «Коэффициенты»"
    )
    assert "раздел=Экология" in record["details"]
    assert "вкладка=Коэффициенты" in record["details"]
    assert "территория=Всего" in record["details"]
    assert record["entity_type"] == "ecology"


def test_log_file_upload_and_download_name_the_file(logged):
    logging_services.log_file_upload(
        "Парниковые газы (ПГ)", "gis_tek.xlsx", size_bytes=2048
    )
    logging_services.log_file_download(
        "Парниковые газы (ПГ)", "gis_tek_parnikovye_gazy.xlsx"
    )

    assert logged[0]["action"] == "Загружен файл: Экология – Парниковые газы (ПГ)"
    assert logged[0]["details"] == "файл=gis_tek.xlsx; размер=2 КБ"
    assert logged[1]["action"] == "Скачан файл: Экология – Парниковые газы (ПГ)"
    assert logged[1]["details"] == "файл=gis_tek_parnikovye_gazy.xlsx"


def test_log_changes_limits_long_change_lists(logged):
    changes = [f"Строка {index}: было 0 → стало {index}" for index in range(150)]

    logging_services.log_changes("Акцепт данных", changes, context=["год=2026"])

    details = logged[0]["details"]
    assert "показаны первые 100 из 150 изменений" in details
    assert "Строка 99:" in details
    assert "Строка 100:" not in details


def test_upsert_coefficient_logs_before_and_after(operating_tes_db, logged):
    operating_services.upsert_coefficient("centr", 2026, "ash_eta", Decimal("0.9"))
    logged.clear()

    operating_services.upsert_coefficient("centr", 2026, "ash_eta", Decimal("0.95"))

    assert logged[0]["action"] == "Изменение: Экология – Коэффициенты – ОЭС Центра"
    assert logged[0]["details"] == (
        "лист=Коэффициенты; территория=ОЭС Центра; "
        "принадлежность=Все принадлежности; год=2026; "
        "КПД золоулавливания: было 0,9 → стало 0,95"
    )


def test_upsert_coefficient_does_not_log_same_value(operating_tes_db, logged):
    operating_services.upsert_coefficient("centr", 2026, "ash_eta", Decimal("0.9"))
    logged.clear()

    operating_services.upsert_coefficient("centr", 2026, "ash_eta", Decimal("0.90"))

    assert logged == []


def test_upsert_characteristic_logs_before_and_after(operating_tes_db, logged):
    operating_services.upsert_characteristic(
        "vsego", "gas_natural", 2026, "tut_per_t", Decimal("1.1")
    )
    logged.clear()

    operating_services.upsert_characteristic(
        "vsego", "gas_natural", 2026, "tut_per_t", Decimal("1.2")
    )

    assert logged[0]["action"] == "Изменение: Экология – Характеристики – Всего"
    assert "топливо=природный газ" in logged[0]["details"]
    assert "было 1,1 → стало 1,2" in logged[0]["details"]


def test_upsert_norm_logs_before_and_after(monkeypatch, logged):
    row = SimpleNamespace(
        fuel_key="gas_natural",
        capacity_class="le100",
        year_number=2026,
        database_version_id=1,
        ash=Decimal("1"),
    )
    monkeypatch.setattr(
        new_tes_page_services,
        "NewTesNorm",
        SimpleNamespace(query=_FakeQuery(row), database_version_id=1),
    )
    monkeypatch.setattr(new_tes_page_services, "get_current_db_version_id", lambda: 1)
    _patch_fake_session(monkeypatch, new_tes_page_services)

    new_tes_page_services.upsert_norm("gas_natural", 2026, "ash_le100", Decimal("1.5"))

    assert logged[0]["action"] == "Изменение: Экология – Нормативы новых ТЭС"
    assert logged[0]["details"] == (
        "лист=Нормативы; топливо=природный газ; год=2026; "
        "твердые частицы (зола) (до 100 МВт): было 1 → стало 1,5"
    )


def test_analysis_cell_edit_logs_before_and_after(monkeypatch, logged):
    row = SimpleNamespace(
        sheet_slug="zv-vse",
        station_numb=708,
        year_number=2017,
        database_version_id=1,
        sulfur_dioxide=Decimal("15"),
    )
    params_model = SimpleNamespace(query=_FakeQuery(row), database_version_id=1)
    reports_model = SimpleNamespace(query=_FakeQuery(None), database_version_id=1)
    monkeypatch.setattr(
        "app.common.services.database_version_filter.get_current_db_version_id",
        lambda: 1,
    )
    monkeypatch.setattr(
        "app.extensions.db",
        SimpleNamespace(session=SimpleNamespace(add=lambda obj: None, commit=lambda: None)),
    )

    analysis_param_services.upsert_param_values(
        params_model,
        reports_model,
        sheet_slug="zv-vse",
        sheet_slugs=frozenset({"zv-vse"}),
        fields=("sulfur_dioxide",),
        label="ЗВ",
        station_numb=708,
        year_number=2017,
        values={"sulfur_dioxide": "12,5"},
    )

    assert logged[0]["action"] == (
        "Изменение: Экология – Анализ ЗВ, Загрязняющие вещества (с котельными)"
    )
    assert logged[0]["details"] == (
        "год=2017; группа оборудования (numb1120)=708; "
        "диоксид серы: было 15 → стало 12,5"
    )
