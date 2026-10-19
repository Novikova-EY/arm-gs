# -*- coding: utf-8 -*-
"""Журнал изменений и просмотров страниц раздела энергобалансов."""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from flask import Blueprint, Flask
from flask_login import LoginManager

from app.energy_balance.services import balance_custom_flow_services
from app.energy_balance.services import change_log_services
from app.extensions import db
from app.energy_balance.services.balance_custom_flow_services import CustomFlowConfig
from app.energy_balance.services import balance_sheet_note_services as note_services
from app.energy_balance.services import ee_import_export_value_services as import_export
from app.energy_balance.services import ee_transfers_value_services as transfers
from app.energy_balance.services import ee_balance_manual_generation_services as manual
from app.energy_balance.services import power_balance_demand_cold_services as cold
from app.energy_balance.services import power_balance_export_services as power_export
from app.logs.services import page_view_logging

ENERGY_BALANCE_MODULE_LABEL = "Балансы электрической энергии и мощности"


def _user(username: str = "tester"):
    return SimpleNamespace(username=username, is_authenticated=True)


@pytest.fixture
def logged(monkeypatch):
    """Перехватывает записи журнала раздела."""
    records = []

    def fake_log_to_db(user, action, details=None, entity_type=None, entity_id=None):
        records.append(
            {
                "username": getattr(user, "username", None),
                "action": action,
                "details": details,
                "entity_type": entity_type,
            }
        )

    monkeypatch.setattr(change_log_services, "log_to_db", fake_log_to_db)
    return records


def _assert_change(record, expected_line: str):
    assert expected_line in record["details"]
    assert record["entity_type"] == change_log_services.ENTITY_TYPE


# ---------------------------------------------------------------- форматирование


@pytest.mark.parametrize(
    "value, expected",
    [
        (Decimal("123.400"), "123,4"),
        (Decimal("100"), "100"),
        (0, "0"),
        (None, "не указано"),
        ("", "не указано"),
    ],
)
def test_format_change_number_matches_page_display(value, expected):
    assert change_log_services.format_change_number(value) == expected


def test_value_change_uses_was_and_became():
    assert (
        change_log_services.value_change("2026 г.", Decimal("1"), Decimal("2.5"))
        == "2026 г.: было 1 → стало 2,5"
    )
    assert (
        change_log_services.value_change("Примечание", None, "текст", number=False)
        == "Примечание: было не указано → стало текст"
    )


@pytest.mark.parametrize(
    "left, right, equal",
    [
        (None, "", True),
        (Decimal("1.0"), Decimal("1"), True),
        (Decimal("1"), "1,0", True),
        (Decimal("1"), Decimal("2"), False),
        ("текст", " текст ", True),
        ("текст", None, False),
    ],
)
def test_values_equal_normalizes_empty_numbers_and_text(left, right, equal):
    assert change_log_services.values_equal(left, right) is equal


def test_identical_values_are_not_journaled(logged):
    change_log_services.log_cell_change(_user(), "Заголовок", "2026 г.", Decimal("5"), "5,0")
    assert logged == []


def test_journal_record_contains_context_and_changes(logged):
    change_log_services.log_cell_change(
        _user(),
        "Изменения в балансе ЭЭ, примечание строки",
        "Примечание строки «demand_max»",
        "старое",
        "новое",
        context="Лист: ОЭС Урала",
        number=False,
    )
    assert len(logged) == 1
    assert logged[0]["username"] == "tester"
    assert logged[0]["action"] == "Изменения в балансе ЭЭ, примечание строки"
    assert logged[0]["details"] == (
        "Лист: ОЭС Урала\nПримечание строки «demand_max»: было старое → стало новое"
    )


# ------------------------------------------------------------ просмотр страниц


def test_energy_balance_pages_are_journaled_as_page_views(monkeypatch):
    records = []
    monkeypatch.setattr(
        page_view_logging.logging_service_mod,
        "log_to_db",
        lambda user, action, details=None, entity_type=None, entity_id=None: records.append(
            (action, details, entity_type)
        ),
    )
    monkeypatch.setattr(
        page_view_logging, "current_user", _user("reader")
    )
    app = Flask(__name__)
    app.config.update(SECRET_KEY="test", LOGIN_DISABLED=True)
    page_view_logging.init_page_view_logging(app)
    bp = Blueprint("energy_balance_bp", __name__)

    @bp.route("/ee_balance/<slug>/")
    def ee_balance_table(slug):
        return (
            "<html><head><title>Баланс ЭЭ — ОЭС Урала</title></head>"
            "<body>данные</body></html>"
        )

    app.register_blueprint(bp, url_prefix="/energy_balance")

    response = app.test_client().get("/energy_balance/ee_balance/ural/")

    assert response.status_code == 200
    assert len(records) == 1
    action, details, entity_type = records[0]
    assert action == "Открыта страница: Баланс ЭЭ — ОЭС Урала"
    assert f"module={ENERGY_BALANCE_MODULE_LABEL}" in details
    assert "endpoint=energy_balance_bp.ee_balance_table" in details
    assert entity_type == "page"


def test_module_label_is_registered_for_energy_balance_pages():
    assert (
        page_view_logging.module_label_for_endpoint("energy_balance_bp.ee_balance_table")
        == ENERGY_BALANCE_MODULE_LABEL
    )


# ------------------------------------------------------------------- перетоки ЭЭ


class _Query:
    def __init__(self, rows):
        self.rows = rows

    def filter_by(self, **conditions):
        return _Query(
            [
                row
                for row in self.rows
                if all(getattr(row, key, None) == value for key, value in conditions.items())
            ]
        )

    def filter(self, *conditions):
        return self

    def all(self):
        return self.rows

    def one_or_none(self):
        return self.rows[0] if self.rows else None

    def first(self):
        return self.rows[0] if self.rows else None


def _patch_transfer_module(monkeypatch, record, ues_id=7):
    class _Transfer:
        query = _Query([record])

        def __init__(self, **fields):
            self.__dict__.update(fields)

    monkeypatch.setattr(transfers, "RegionalEnergySystemTransfer", _Transfer)
    monkeypatch.setattr(
        transfers,
        "UnionEnergySystem",
        SimpleNamespace(query=_Query([SimpleNamespace(id=ues_id)])),
    )
    monkeypatch.setattr(transfers, "get_current_db_version_id", lambda: 4)
    monkeypatch.setattr(transfers, "filter_by_db_version", lambda query, model: query)
    monkeypatch.setattr(
        transfers, "filter_by_explicit_db_version", lambda query, model, version: query
    )
    monkeypatch.setattr(transfers, "_commit_with_retry", lambda: None)
    monkeypatch.setattr(transfers, "clear_energy_balance_cache", lambda: None)
    monkeypatch.setattr(
        transfers, "_get_res_territory_maps", lambda: {"res_ues_map": {}, "rd_res_map": {}}
    )
    monkeypatch.setattr(
        transfers, "get_union_energy_systems_map", lambda: {ues_id: "ОЭС Сибири"}
    )
    monkeypatch.setattr(transfers, "get_union_energy_system_display_order_map", lambda: {ues_id: 1})
    monkeypatch.setattr(transfers.db.session, "add", lambda row: None, raising=False)


def test_transfer_value_change_is_journaled(monkeypatch, logged):
    record = SimpleNamespace(
        id_from_regional_energy_system=10,
        id_from_regional_district=None,
        id_to_regional_energy_system=20,
        id_to_foreign_border_country=None,
        id_to_regional_district=None,
        id_to_energy_unit=None,
        id_union_energy_system=7,
        year_number=2026,
        month_number=4,
        source_oes_name="ОЭС Сибири",
        transfer_value=Decimal("1"),
        from_display_name="РЭС Томская",
        to_display_name="РЭС Новосибирская",
    )
    _patch_transfer_module(monkeypatch, record)

    transfers.update_ee_transfer_value(
        ues_id=7,
        source_res_id=10,
        source_rd_id="",
        target_res_id=20,
        target_country_id="",
        target_rd_id="",
        target_energy_unit_id="",
        year=2026,
        month=4,
        raw_value="2,5",
        user=_user(),
    )

    assert len(logged) == 1
    assert logged[0]["action"] == "Изменения в балансе ЭЭ, переток электроэнергии"
    assert "2026 г., месяц 4: было 1 → стало 2,5" in logged[0]["details"]
    assert "получатель: РЭС Новосибирская" in logged[0]["details"]


# --------------------------------------------------------- импорт/экспорт по ОЭС


class _ValuesModel:
    """Заглушка ORM-модели: столбцы нужны для выражений, запросы не выполняются."""

    query = None
    id = object()
    level = object()
    entity_id = object()
    month_number = object()
    year_number = object()
    sheet_slug = object()
    row_key = object()
    balance_kind = object()
    direction = object()
    parent_key = object()
    sort_order = object()
    id_station = object()
    station_type_key = object()

    def __init__(self, **fields):
        self.__dict__.update(fields)


def _patch_import_export_module(monkeypatch, existing):
    _ValuesModel.query = _Query([existing] if existing is not None else [])
    monkeypatch.setattr(import_export, "EeImportExportOesValue", _ValuesModel)
    monkeypatch.setattr(import_export, "get_current_db_version_id", lambda: 3)
    monkeypatch.setattr(import_export, "filter_by_db_version", lambda query, model: query)
    monkeypatch.setattr(
        import_export, "filter_by_explicit_db_version", lambda query, model, version: query
    )
    monkeypatch.setattr(import_export, "_commit_with_retry", lambda: None)
    monkeypatch.setattr(import_export, "clear_energy_balance_cache", lambda: None)
    monkeypatch.setattr(
        import_export,
        "UnionEnergySystem",
        SimpleNamespace(query=_Query([SimpleNamespace(id=7, name="ОЭС Сибири")])),
    )
    monkeypatch.setattr(
        import_export,
        "ForeignBorderCountry",
        SimpleNamespace(query=_Query([SimpleNamespace(id=11, name="Монголия")])),
    )
    monkeypatch.setattr(import_export.db.session, "add", lambda row: None, raising=False)


def test_import_export_value_change_is_journaled(monkeypatch, logged):
    existing = SimpleNamespace(
        id_union_energy_system=7,
        id_foreign_border_country=11,
        year_number=2026,
        transfer_value=Decimal("4"),
    )
    _patch_import_export_module(monkeypatch, existing)

    import_export.update_ee_import_export_value(
        ues_id=7, country_id=11, year=2026, direction="import", raw_value="20", user=_user()
    )

    assert len(logged) == 1
    _assert_change(logged[0], "2026 г., импорт: было 4 → стало 20")
    assert "страна: Монголия" in logged[0]["details"]


def test_cleared_value_is_journaled_as_not_set(monkeypatch, logged):
    existing = SimpleNamespace(
        id_union_energy_system=7,
        id_foreign_border_country=11,
        year_number=2026,
        transfer_value=Decimal("4"),
    )
    _patch_import_export_module(monkeypatch, existing)

    import_export.update_ee_import_export_value(
        ues_id=7, country_id=11, year=2026, direction="export", raw_value="", user=_user()
    )

    assert len(logged) == 1
    _assert_change(logged[0], "2026 г., экспорт: было 4 → стало не указано")


# ------------------------------------------------------------------ примечания


def _patch_note_module(monkeypatch, existing):
    monkeypatch.setattr(note_services, "_ensure_tables", lambda: None)
    monkeypatch.setattr(note_services, "_version_id", lambda: 2)
    monkeypatch.setattr(note_services, "_commit_with_retry", lambda: None)
    monkeypatch.setattr(
        note_services,
        "_note_query",
        lambda: _Query([existing] if existing is not None else []),
    )
    monkeypatch.setattr(note_services.db.session, "delete", lambda row: None, raising=False)
    monkeypatch.setattr(note_services.db.session, "add", lambda row: None, raising=False)
    monkeypatch.setattr(note_services, "BalanceSheetNote", _ValuesModel)


@pytest.mark.parametrize(
    "kind, sheet_name, old_note, new_note, expected",
    [
        ("power", "ОЭС Урала", "старое", "новое", "было старое → стало новое"),
        ("ee", "ОЭС Сибири", "старое", "", "было старое → стало не указано"),
    ],
)
def test_note_change_is_journaled(monkeypatch, logged, kind, sheet_name, old_note, new_note, expected):
    existing = SimpleNamespace(note_text=old_note)
    _patch_note_module(monkeypatch, existing)

    note_services.update_balance_sheet_note(
        kind, "ural", "demand_max", new_note, user=_user(), sheet_name=sheet_name
    )

    assert len(logged) == 1
    assert f"Лист: {sheet_name}" in logged[0]["details"]
    assert expected in logged[0]["details"]


# --------------------------------------------------------------- строки перетока


def _custom_flow_config():
    return CustomFlowConfig(
        row_model=_ValuesModel,
        value_model=_ValuesModel,
        value_field="value",
        directions=("flow_in", "flow_out"),
        action="Изменения в балансе мощности, строки перетока",
    )


def _custom_flow_row(**overrides):
    row = SimpleNamespace(
        id=5,
        direction="flow_in",
        label="Переток",
        parent_key="flow_in",
        sort_order=0,
        values=[],
    )
    row.__dict__.update(overrides)
    return row


def test_custom_flow_value_change_is_journaled(monkeypatch, logged):
    row = _custom_flow_row(label="Переток на Казахстан")
    row.values = [
        SimpleNamespace(value=Decimal("10"), database_version_id=1, year_number=2026)
    ]
    monkeypatch.setattr(balance_custom_flow_services, "_get_row", lambda config, slug, row_id: row)
    monkeypatch.setattr(balance_custom_flow_services, "_commit_with_retry", lambda: None)
    monkeypatch.setattr(balance_custom_flow_services, "version_id", lambda: 1)

    balance_custom_flow_services.update_custom_flow_value(
        _custom_flow_config(), "sibir", 5, 2026, "12,5", user=_user()
    )

    assert len(logged) == 1
    assert logged[0]["action"] == "Изменения в балансе мощности, строки перетока"
    assert "2026 г.: было 10 → стало 12,5" in logged[0]["details"]
    assert "строка: Переток на Казахстан (flow_in)" in logged[0]["details"]


def test_custom_flow_label_change_is_journaled(monkeypatch, logged):
    row = _custom_flow_row(label="Старое имя")
    monkeypatch.setattr(balance_custom_flow_services, "_get_row", lambda config, slug, row_id: row)
    monkeypatch.setattr(balance_custom_flow_services, "_commit_with_retry", lambda: None)

    balance_custom_flow_services.update_custom_flow_label(
        _custom_flow_config(), "sibir", 5, "Новое имя", user=_user()
    )

    assert len(logged) == 1
    assert "Наименование строки: было Старое имя → стало Новое имя" in logged[0]["details"]


def test_custom_flow_add_and_delete_are_journaled(monkeypatch, logged):
    module = balance_custom_flow_services

    class _RowModel(_ValuesModel):
        pass

    config = module.CustomFlowConfig(
        row_model=_RowModel,
        value_model=_ValuesModel,
        value_field="value",
        directions=("flow_in", "flow_out"),
        action="Изменения в балансе ЭЭ, строки перетока",
    )
    monkeypatch.setattr(module, "ensure_custom_flow_tables", lambda *args, **kwargs: None)
    monkeypatch.setattr(module, "version_id", lambda: 1)
    monkeypatch.setattr(module, "_commit_with_retry", lambda: None)
    monkeypatch.setattr(module, "_serialize_row", lambda config, row: {})
    monkeypatch.setattr(module, "filter_by_db_version", lambda query, model: query)
    session = MagicMock()
    session.query.return_value.filter.return_value.scalar.return_value = -1
    monkeypatch.setattr(module.db, "session", session)

    module.add_custom_flow_row(config, "sibir", "flow_in", "Новый переток", user=_user())

    assert "добавлена строка: Новый переток (направление: flow_in)" in logged[0]["details"]

    monkeypatch.setattr(
        module, "_get_row", lambda config, slug, row_id: _custom_flow_row(label="Новый переток")
    )
    monkeypatch.setattr(module, "_descendant_rows", lambda config, slug, key: [])

    assert module.delete_custom_flow_row(config, "sibir", 5, user=_user()) is True
    assert "удалена строка: Новый переток" in logged[1]["details"]


# ----------------------------------------------------------- баланс мощности (МВт)


class _PowerExportModel(_ValuesModel):
    pass


def test_power_export_value_change_is_journaled(monkeypatch, logged):
    from app.energy_balance.services.balance_export_value_services import ExportValueConfig

    existing = SimpleNamespace(sheet_slug="ural", year_number=2026, value_mw=Decimal("100"))
    model = _PowerExportModel
    model.query = _Query([existing])
    monkeypatch.setattr(
        power_export,
        "_CONFIG",
        ExportValueConfig(
            value_model=model,
            value_field="value_mw",
            export_row_key=power_export.EXPORT_ROW_KEY,
            action="Изменения в балансе мощности, экспорт мощности",
            change_label="Экспорт мощности",
        ),
    )
    monkeypatch.setattr(
        "app.energy_balance.services.balance_export_value_services.ensure_table", lambda model: None
    )
    monkeypatch.setattr(
        "app.energy_balance.services.balance_export_value_services.version_id", lambda: 1
    )
    monkeypatch.setattr(
        "app.energy_balance.services.balance_export_value_services.version_filtered_query",
        lambda model: model.query,
    )
    monkeypatch.setattr(
        "app.energy_balance.services.balance_export_value_services._commit_with_retry", lambda: None
    )

    power_export.update_power_balance_export_value(
        "ural", 2026, "150", user=_user(), sheet_name="ОЭС Урала"
    )

    assert len(logged) == 1
    assert logged[0]["action"] == "Изменения в балансе мощности, экспорт мощности"
    assert "Экспорт мощности, 2026 г.: было 100 → стало 150" in logged[0]["details"]
    assert "Лист: ОЭС Урала" in logged[0]["details"]


@pytest.mark.parametrize(
    "old_value, new_value, expected",
    [
        (Decimal("50"), "60", "было 50 → стало 60"),
        (None, "60", "было не указано → стало 60"),
        (Decimal("50"), "", "было 50 → стало не указано"),
    ],
)
def test_cold_demand_value_change_is_journaled(monkeypatch, logged, old_value, new_value, expected):
    existing = None
    if old_value is not None:
        existing = SimpleNamespace(value_mw=old_value)
    monkeypatch.setattr(cold, "_ensure_tables", lambda: None)
    monkeypatch.setattr(cold, "_version_id", lambda: 1)
    monkeypatch.setattr(cold, "_commit_with_retry", lambda: None)
    monkeypatch.setattr(cold, "_value_query", lambda: _Query([existing] if existing else []))
    monkeypatch.setattr(cold.db.session, "delete", lambda row: None, raising=False)
    monkeypatch.setattr(cold.db.session, "add", lambda row: None, raising=False)
    monkeypatch.setattr(cold, "PowerBalanceDemandColdValue", _ValuesModel)

    cold.update_power_balance_demand_cold_value(
        "tites-vostok", 2027, new_value, user=_user(), sheet_name="ТИТЭС Востока"
    )

    assert len(logged) == 1
    assert f"Максимум потребления (холодная пятидневка), 2027 г.: {expected}" in logged[0]["details"]


# ------------------------------------------------------- баланс ЭЭ: значения


def _patch_manual_module(monkeypatch, stored, sheet):
    query = MagicMock()
    query.filter.return_value.one_or_none.side_effect = lambda: stored
    monkeypatch.setattr(manual, "_value_query", lambda: query)
    monkeypatch.setattr(manual, "_ensure_tables", lambda: None)
    monkeypatch.setattr(manual, "_commit_with_retry", lambda: None)
    monkeypatch.setattr(manual, "_version_id", lambda: 1)
    monkeypatch.setattr(
        manual,
        "db",
        SimpleNamespace(session=SimpleNamespace(delete=lambda record: None)),
    )
    monkeypatch.setattr(manual, "classify_ee_balance_generation_years", lambda years: ([], [2026]))
    monkeypatch.setattr(
        manual,
        "get_power_balance_sheet",
        lambda wanted: {"slug": "oes-413", "group": "oes", "sheet_name": "ОЭС Урала"},
    )


def test_manual_generation_change_is_journaled(monkeypatch, logged):
    stored = SimpleNamespace(
        sheet_slug="oes-413",
        row_key="generation_tes",
        year_number=2026,
        value_mln_kvtch=Decimal("55"),
        database_version_id=1,
    )
    _patch_manual_module(monkeypatch, stored, None)

    manual.update_ee_balance_manual_generation_value(
        "oes-413",
        "generation_tes",
        2026,
        "60",
        user=_user(),
        sheet_name="ОЭС Урала",
    )

    assert len(logged) == 1
    assert logged[0]["action"] == "Изменения в балансе ЭЭ, ручной ввод выработки"
    assert "Строка «generation_tes», 2026 г.: было 55 → стало 60" in logged[0]["details"]


def test_tes_forecast_month_change_is_journaled(monkeypatch, logged):
    from app.energy_balance.services import ee_balance_tes_forecast_services as forecast

    sheet = {"slug": "oes-318", "sheet_name": "ТИТЭС Сибири"}
    writes = []

    def write_value(*, row_key, parsed, **kwargs):
        writes.append((row_key, parsed))
        return Decimal("10") if row_key == "consumption_share" else None

    with (
        patch.object(forecast, "classify_ee_balance_generation_years", return_value=([], [2026])),
        patch.object(forecast, "load_tes_forecast_entities", return_value={"tes_stations": []}),
        patch.object(forecast, "_ensure_tables"),
        patch.object(forecast, "_version_id", return_value=1),
        patch.object(forecast, "_write_month_value", side_effect=write_value),
        patch.object(forecast, "_commit_with_retry"),
        patch.object(
            forecast,
            "build_tes_forecast_year_payload",
            return_value={"rows": [], "tes_total": None},
        ),
    ):
        forecast.update_tes_forecast_value(
            sheet, 2026, "consumption_share", 1, "0,2", rounding_digits=1, user=_user()
        )

    assert len(logged) == 1
    assert (
        "Строка «consumption_share», 2026 г., месяц 1: было 10 → стало 0,2"
        in logged[0]["details"]
    )
    assert "Лист: ТИТЭС Сибири" in logged[0]["details"]


def test_res_control_value_change_is_journaled(monkeypatch, logged):
    from app.energy_balance.services import station_ee_generation_page_services as page_services

    existing = SimpleNamespace(electricity_generation=Decimal("120"))
    page_services.RegionalEnergySystemEnergyGeneration.query = _Query([existing])
    monkeypatch.setattr(db.session, "add", lambda row: None, raising=False)
    monkeypatch.setattr(
        "app.common.services.database_version_filter.filter_by_db_version",
        lambda query, model: query,
    )
    monkeypatch.setattr(
        "app.common.services.database_version_filter.set_db_version_on_create", lambda record: None
    )
    monkeypatch.setattr(
        "app.common.services.tranzaction_services._commit_with_retry", lambda: None
    )
    monkeypatch.setattr(
        "app.energy_balance.services.energy_balance_cache.clear_energy_balance_cache",
        lambda: None,
    )

    page_services.update_res_control_generation_value(
        12, 2026, "130", period_mode="years", user=_user()
    )

    assert len(logged) == 1
    assert logged[0]["action"] == "Изменения в балансе ЭЭ, контрольная выработка по РЭС"
    assert "2026 г.: было 120 → стало 130" in logged[0]["details"]


def test_hierarchy_control_value_change_is_journaled(monkeypatch, logged):
    from app.energy_balance.services import ee_generation_hierarchy_control_services as hierarchy

    existing = SimpleNamespace(electricity_generation=Decimal("300"))
    monkeypatch.setattr(
        hierarchy, "EnergySystemEnergyGenerationControl", _ValuesModel
    )
    hierarchy.EnergySystemEnergyGenerationControl.query = _Query([existing])
    monkeypatch.setattr(hierarchy, "filter_by_db_version", lambda query, model: query)
    monkeypatch.setattr(hierarchy, "set_db_version_on_create", lambda record: None)
    monkeypatch.setattr(hierarchy, "_commit_with_retry", lambda: None)
    monkeypatch.setattr(hierarchy, "clear_energy_balance_cache", lambda: None)
    monkeypatch.setattr(hierarchy, "_ensure_tables", lambda: None)
    monkeypatch.setattr(hierarchy.db.session, "add", lambda row: None, raising=False)
    monkeypatch.setattr(hierarchy, "_hierarchy_entity_name", lambda level, entity_id: "ОЭС Сибири")

    hierarchy.update_hierarchy_control_generation_value(
        "ues", 7, 2026, "400", period_mode="years", user=_user()
    )

    assert len(logged) == 1
    assert logged[0]["action"] == "Изменения в балансе ЭЭ, контрольная выработка по иерархии"
    assert "2026 г.: было 300 → стало 400" in logged[0]["details"]
    assert "ОЭС: ОЭС Сибири" in logged[0]["details"]


def test_hydro_own_needs_coefficient_change_is_journaled(monkeypatch, logged):
    from app.energy_balance.services import ee_balance_hydro_own_needs_services as hydro

    existing = SimpleNamespace(coefficient=Decimal("0.05"))
    monkeypatch.setattr(hydro, "filter_by_db_version", lambda query, model: query)
    monkeypatch.setattr(hydro, "_commit_with_retry", lambda: None)
    monkeypatch.setattr(hydro, "EeBalanceStationOwnNeedsCoefficient", _ValuesModel)
    hydro.EeBalanceStationOwnNeedsCoefficient.query = _Query([existing])
    monkeypatch.setattr(hydro.db.session, "add", lambda row: None, raising=False)

    hydro.save_hydro_own_needs_coefficient(
        40, "ges", "0,07", user=_user(), station_name="Воткинская ГЭС"
    )

    assert len(logged) == 1
    assert "Коэффициент собственных нужд: было 0,05 → стало 0,07" in logged[0]["details"]
    assert "Станция: Воткинская ГЭС (GES)" in logged[0]["details"]
