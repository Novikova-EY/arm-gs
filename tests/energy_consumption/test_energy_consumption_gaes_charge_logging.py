# -*- coding: utf-8 -*-
"""Журнал изменений ГАЭС на заряд: сводка потребления ↔ карточка станции."""
from types import SimpleNamespace
from unittest.mock import patch

from app.energy_consumption.services import energy_consumption_summary_logging as logging_mod


def _log(**kwargs):
    return SimpleNamespace(**kwargs)


@patch.object(logging_mod, "log_to_db")
@patch.object(logging_mod, "log_ec_summary_cell_change")
def test_log_gaes_charge_from_summary_table_writes_all_summary_scopes(
    mock_ec_log, mock_station_log
):
    logging_mod.log_gaes_charge_from_summary_table(
        "tester",
        summary_log_scope="oes",
        station_id=6620,
        station_name="Зеленчукская ГАЭС",
        rd_name="Карачаево-Черкесская Республика",
        year=2020,
        old_val=None,
        new_val=12.5,
        database_version_id=3,
    )
    assert mock_ec_log.call_count == 3
    assert {c[0][1] for c in mock_ec_log.call_args_list} == {"oes", "fo", "ez"}
    mock_station_log.assert_called_once()
    assert mock_station_log.call_args.kwargs["entity_type"] == "station"
    assert mock_station_log.call_args.kwargs["entity_id"] == 6620
    assert "со сводной таблицы" in mock_station_log.call_args[0][1]


@patch.object(logging_mod, "log_ec_summary_cell_change")
def test_log_gaes_charge_from_station_details_writes_all_summary_scopes(mock_ec_log):
    logging_mod.log_gaes_charge_from_station_details(
        "tester",
        station_id=6620,
        station_name="Зеленчукская ГАЭС",
        change_lines=["2020 г.: 10 → 12"],
        database_version_id=3,
    )
    assert mock_ec_log.call_count == 3
    assert {c[0][1] for c in mock_ec_log.call_args_list} == {"oes", "fo", "ez"}
    chunks = mock_ec_log.call_args.kwargs["detail_chunks"]
    assert any("карточка электростанции" in c for c in chunks)


@patch.object(logging_mod, "log_ec_summary_cell_change")
def test_log_gaes_charge_from_station_details_skips_empty(mock_ec_log):
    logging_mod.log_gaes_charge_from_station_details(
        "tester",
        station_id=1,
        station_name="X",
        change_lines=[],
        database_version_id=None,
    )
    mock_ec_log.assert_not_called()


def test_is_gaes_charge_station_log_matches_station_card_action():
    log = _log(
        entity_type="station",
        action=(
            "Изменения в электростанции Загорская ГАЭС, "
            "потребление электроэнергии ГАЭС на заряд (млн кВт·ч)"
        ),
    )
    assert logging_mod._is_gaes_charge_station_log(log) is True


def test_is_gaes_charge_summary_log_matches_table_marker():
    log = _log(
        entity_type=logging_mod.ENTITY_TYPE_BY_SCOPE["oes"],
        details=(
            f"таблица={logging_mod.GAES_CHARGE_TABLE_LABEL}; "
            "электростанция=Загорская (id=6620); 2020 г.: 1 → 2"
        ),
    )
    assert logging_mod._is_gaes_charge_summary_log(log) is True


def test_dedupe_gaes_charge_log_pairs_drops_station_when_summary_exists():
    from datetime import datetime, timezone

    ts = datetime(2026, 5, 12, 8, 5, 23, tzinfo=timezone.utc)
    summary = _log(
        id=1,
        entity_type=logging_mod.ENTITY_TYPE_BY_SCOPE["oes"],
        timestamp=ts,
        username="user",
        details=(
            f"таблица={logging_mod.GAES_CHARGE_TABLE_LABEL}; "
            "источник=карточка электростанции; 2020 г.: 1 → 2"
        ),
    )
    station = _log(
        id=2,
        entity_type="station",
        timestamp=ts,
        username="user",
        action="потребление электроэнергии ГАЭС на заряд",
        details="2020 г.: 1 → 2",
    )
    merged = logging_mod._merge_logs_by_timestamp([[summary, station]])
    assert len(merged) == 1
    assert merged[0].id == 1
