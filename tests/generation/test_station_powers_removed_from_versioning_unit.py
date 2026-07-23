# -*- coding: utf-8 -*-
"""Доп. тесты: версионирование больше не ссылается на gs_gen_station_powers."""

from pathlib import Path

import app.common.services.database_version_services as dvs
import app.common.services.version_comparison_service as vcs


def test_database_version_services_has_no_station_powers_table_refs():
    source = Path(dvs.__file__).read_text(encoding="utf-8")
    assert "gs_gen_station_powers" not in source
    assert "station_powers" not in source


def test_version_comparison_service_has_no_station_powers_table_refs():
    source = Path(vcs.__file__).read_text(encoding="utf-8")
    assert "station_powers" not in source


def test_get_max_generation_data_year_sql_uses_machine_powers_only():
    # Функция содержит SQL-строку; проверяем, что station_powers там нет.
    import inspect

    src = inspect.getsource(dvs._get_max_generation_data_year)
    assert "gs_gen_machine_powers" in src
    assert "gs_gen_station_powers" not in src
