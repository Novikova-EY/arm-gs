# -*- coding: utf-8 -*-
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace

import pandas as pd
import pytest

from app.fuel.services.fuel_imports.fuel_excel_file_guard_services import (
    filename_looks_like_access_stations_or_extra_fuel,
    filename_looks_like_imena_stanciy,
    headers_look_like_access_stations_or_extra_fuel,
    headers_look_like_imena_stanciy,
    reject_access_stations_or_extra_fuel_excel,
    reject_imena_stanciy_on_fuel_db_import,
)
from app.fuel.services.fuel_imports.import_equipment_group_fuel_params_services import (
    _scale_sn_from_file,
    detect_fuel_params_excel_import_kind,
    extract_year_from_fuel_params_import_filename,
    fuel_params_import_year_mismatch_message,
    require_fuel_params_excel_import_kind,
    resolve_fuel_params_import_year,
)
from app.fuel.services.fuel_imports.import_equipment_group_specific_fuel_cost_services import (
    filename_looks_like_specific_fuel_cost,
    require_specific_fuel_cost_excel_filename,
)
from app.fuel.services.fuel_imports.soft_import_composite_flags_services import (
    soft_import_composite_flags_from_imena_excel,
)


def _xlsx_bytes(df: pd.DataFrame, sheet_name: str = "Sheet1") -> BytesIO:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
    buf.seek(0)
    return buf


def test_filename_detects_stations_and_extra():
    assert filename_looks_like_access_stations_or_extra_fuel("Станции2024.xlsx")
    assert filename_looks_like_access_stations_or_extra_fuel("stancii2024.xlsx")
    assert filename_looks_like_access_stations_or_extra_fuel("Доп_угли2024.xlsx")
    assert filename_looks_like_access_stations_or_extra_fuel("Dop_ugli2024.xlsx")
    assert not filename_looks_like_access_stations_or_extra_fuel("Имена_станций.xlsx")
    assert not filename_looks_like_access_stations_or_extra_fuel("export_groups.xlsx")
    assert filename_looks_like_imena_stanciy("Имена_станций.xlsx")
    assert filename_looks_like_imena_stanciy("imena_stanciy.xlsx")
    assert not filename_looks_like_imena_stanciy("export_groups.xlsx")


def test_headers_detect_stations_markers():
    buf = _xlsx_bytes(
        pd.DataFrame(columns=["NUMB", "NAME", "NUST", "EOTP", "QOTR", "COMP", "MAIN"])
    )
    assert headers_look_like_access_stations_or_extra_fuel(buf) is True
    buf2 = _xlsx_bytes(pd.DataFrame(columns=["NUMB", "NAME", "COMP", "MAIN", "NIV"]))
    assert headers_look_like_access_stations_or_extra_fuel(buf2) is False
    assert headers_look_like_imena_stanciy(buf2) is True
    buf3 = _xlsx_bytes(pd.DataFrame(columns=["id_station", "equipment_group", "id_machine"]))
    assert headers_look_like_imena_stanciy(buf3) is False


def test_reject_by_filename():
    with pytest.raises(ValueError, match="Сведения о работе ТЭС"):
        reject_access_stations_or_extra_fuel_excel(
            "Станции2024.xlsx", file=None, context="fuel_db"
        )


def test_reject_by_headers_even_without_stations_filename():
    buf = _xlsx_bytes(
        pd.DataFrame([{"NUMB": 1, "NAME": "X", "NUST": 100, "EOTP": 1, "COMP": 1}])
    )
    with pytest.raises(ValueError, match="Имена_станций"):
        reject_access_stations_or_extra_fuel_excel(
            "unknown.xlsx", file=buf, context="soft_import"
        )


def test_reject_imena_on_fuel_db_import():
    with pytest.raises(ValueError, match="Проверить / загрузить флаги"):
        reject_imena_stanciy_on_fuel_db_import("Имена_станций.xlsx", file=None)
    buf = _xlsx_bytes(
        pd.DataFrame([{"NUMB": 1502, "NAME": "Ижора", "COMP": None, "MAIN": 81, "NIV": 1}])
    )
    with pytest.raises(ValueError, match="Имена_станций"):
        reject_imena_stanciy_on_fuel_db_import("unknown.xlsx", file=buf)


def test_soft_import_rejects_stations_filename(monkeypatch):
    df = pd.DataFrame(
        [
            {"NUMB": 1, "COMP": 1, "MAIN": None, "NIV": None, "NAME": "Parent"},
        ]
    )
    buf = _xlsx_bytes(df)
    # имитация FileStorage с «опасным» именем
    wrapped = SimpleNamespace(filename="Станции2024.xlsx", read=buf.read, seek=buf.seek, tell=buf.tell)

    def _read(_f):
        buf.seek(0)
        return buf.read()

    wrapped.read = _read

    with pytest.raises(ValueError, match="Станции"):
        soft_import_composite_flags_from_imena_excel(
            wrapped, "tester", dry_run=True, session=SimpleNamespace()
        )


def test_fuel_params_detect_by_filename():
    assert detect_fuel_params_excel_import_kind("Станции2024.xlsx") == "stations"
    assert detect_fuel_params_excel_import_kind("Доп_угли2024.xlsx") == "extra"
    assert detect_fuel_params_excel_import_kind("Сводная таблица для ОТЭТ_.xls") == "otet_svodnaya"
    assert detect_fuel_params_excel_import_kind("svodnaya_tablica_dlya_otet.xlsx") == "otet_svodnaya"
    assert detect_fuel_params_excel_import_kind("Имена_станций.xlsx") is None
    assert detect_fuel_params_excel_import_kind("export_groups.xlsx") is None


def test_fuel_params_detect_by_headers_when_name_unknown():
    buf = _xlsx_bytes(
        pd.DataFrame(columns=["NUMB1120", "NAME", "NUST", "EOTP", "QOTR"])
    )
    assert detect_fuel_params_excel_import_kind("unknown.xlsx", file=buf) == "stations"
    buf2 = _xlsx_bytes(
        pd.DataFrame(columns=["NUMB1120", "NAME", "GAZ_PRIR", "NAZAR", "MAZTOP"])
    )
    assert detect_fuel_params_excel_import_kind("unknown.xlsx", file=buf2) == "extra"
    buf3 = _xlsx_bytes(pd.DataFrame(columns=["id_station", "equipment_group", "NAME"]))
    assert detect_fuel_params_excel_import_kind("unknown.xlsx", file=buf3) is None


def test_fuel_params_detect_otet_svodnaya_by_headers():
    # Шапка не в первой строке — как в реальной сводной ОТЭТ.
    rows = [
        [None, None, None, None],
        ["Наименование", "С н.ээ", "С.н. тыс.кВтч", "NUMB1120"],
        ["NAME", None, None, "NUMB1120"],
        ["Пенза ТЭЦ-1", 71287.497, 55671.599, 326],
    ]
    df = pd.DataFrame(rows)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, header=False, sheet_name="2024")
    buf.seek(0)
    assert detect_fuel_params_excel_import_kind("unknown.xlsx", file=buf) == "otet_svodnaya"
    buf.seek(0)
    assert require_fuel_params_excel_import_kind("unknown.xlsx", file=buf) == "otet_svodnaya"


def test_fuel_params_require_rejects_unknown():
    with pytest.raises(ValueError, match="Станции"):
        require_fuel_params_excel_import_kind("Имена_станций.xlsx")
    buf = _xlsx_bytes(pd.DataFrame(columns=["id_station", "equipment_group"]))
    with pytest.raises(ValueError, match="Доп_угли|ОТЭТ"):
        require_fuel_params_excel_import_kind("export.xlsx", file=buf)


def test_extract_year_from_fuel_params_import_filename():
    assert extract_year_from_fuel_params_import_filename("Станции2023.xlsx") == 2023
    assert extract_year_from_fuel_params_import_filename("Доп_угли2024.xlsx") == 2024
    assert extract_year_from_fuel_params_import_filename("stancii2025.xls") == 2025
    assert extract_year_from_fuel_params_import_filename("Станции.xlsx") is None
    assert extract_year_from_fuel_params_import_filename(None) is None


def test_resolve_fuel_params_import_year_from_filename_or_fallback():
    assert resolve_fuel_params_import_year("Станции2023.xlsx", 2024) == 2023
    assert resolve_fuel_params_import_year("Доп_угли2018.xlsx", 2024) == 2018
    assert resolve_fuel_params_import_year("Станции.xlsx", 2024) == 2024
    assert resolve_fuel_params_import_year(None, 2020) == 2020


def test_fuel_params_import_year_mismatch_message():
    msg = fuel_params_import_year_mismatch_message(
        "Станции2023.xlsx", 2024, import_kind="stations"
    )
    assert msg is not None
    assert "2023" in msg
    assert "2024" in msg
    assert "отменена" in msg
    assert fuel_params_import_year_mismatch_message(
        "Станции2024.xlsx", 2024, import_kind="stations"
    ) is None
    assert fuel_params_import_year_mismatch_message(
        "Станции.xlsx", 2024, import_kind="stations"
    ) is None


def test_specific_fuel_cost_filename_must_contain_stoimost():
    assert filename_looks_like_specific_fuel_cost("Стоимость2024.xlsx")
    assert filename_looks_like_specific_fuel_cost("стоимость_2018.xls")
    assert not filename_looks_like_specific_fuel_cost("Станции2024.xlsx")
    assert not filename_looks_like_specific_fuel_cost("export.xlsx")
    require_specific_fuel_cost_excel_filename("Стоимость2019.xlsx")
    with pytest.raises(ValueError, match="Стоимость"):
        require_specific_fuel_cost_excel_filename("Станции2019.xlsx")


def test_get_or_create_fuel_param_finds_existing_row_ignoring_version(monkeypatch):
    """uq — (группа, год); строка с другой database_version_id должна обновляться, не INSERT."""
    from app.fuel.services.fuel_imports.import_equipment_group_fuel_params_services import (
        _get_or_create_equipment_group_fuel_param,
    )

    existing = SimpleNamespace(
        equipment_group_id=17162,
        year_number=2023,
        database_version_id=20,
    )
    seen_filter = {}

    class _Query:
        def filter_by(self, **kwargs):
            seen_filter.update(kwargs)
            return self

        def first(self):
            return existing

    monkeypatch.setattr(
        "app.fuel.services.fuel_imports.import_equipment_group_fuel_params_services.EquipmentGroupFuelParam",
        SimpleNamespace(query=_Query()),
    )
    param, created = _get_or_create_equipment_group_fuel_param(17162, 2023, None)
    assert created is False
    assert param is existing
    assert seen_filter == {"equipment_group_id": 17162, "year_number": 2023}


def test_scale_sn_from_file_divides_by_1000():
    assert _scale_sn_from_file(1234567) == Decimal("1234.567")
    assert _scale_sn_from_file("2500,5") == Decimal("2.5005")
    assert _scale_sn_from_file(None) is None
    assert _scale_sn_from_file("") is None


def test_stations_schema_aliases_year_and_qotr():
    from app.fuel.services.fuel_imports.import_equipment_group_fuel_params_services import (
        _apply_column_aliases,
        _qotr_from_stations_row,
        _year_number_from_stations_row,
    )

    df = pd.DataFrame(
        [
            {
                "NUMB1120": 66,
                "NAME": "Первомайская ТЭЦ",
                "DEP": 5,
                "Q": 1699.11,
                "QOTR": 900,
                "Year": 2025,
            }
        ]
    )
    df = _apply_column_aliases(df)
    assert "qotr" in df.columns
    assert "year_number" in df.columns
    row = df.iloc[0]
    assert _qotr_from_stations_row(row) == Decimal("900")
    assert _year_number_from_stations_row(row, 2024) == 2025


def test_stations_schema_empty_qotr_is_skipped_and_year_falls_back():
    from app.fuel.services.fuel_imports.import_equipment_group_fuel_params_services import (
        _apply_column_aliases,
        _qotr_from_stations_row,
        _year_number_from_stations_row,
    )

    df = pd.DataFrame([{"NUMB1120": 66, "DEP": 5, "QOTR": None}])
    df = _apply_column_aliases(df)
    row = df.iloc[0]
    assert _qotr_from_stations_row(row) is None
    assert _year_number_from_stations_row(row, 2026) == 2026


def test_stations_schema_calc_fields_ignore_dep_and_clear_empty_qotr():
    from app.fuel.services.fuel_imports.import_equipment_group_fuel_params_services import (
        _apply_column_aliases,
        _stations_schema_row_values,
    )

    df = pd.DataFrame(
        [
            {
                "NUMB1120": 66,
                "NAME": "ТЭЦ-14",
                "DEP": 5,
                "OES": 1,
                "VED": 2,
                "NUST": 360,
                "NR": 360,
                "HFIX": 1,
                "Q": 1749.1,
                "QOTR": None,
                "TURT": 151.35,
                "E": 2004.0,
                "Year": 2026,
            }
        ]
    )
    df = _apply_column_aliases(df)
    vals = _stations_schema_row_values(df.iloc[0], df.columns)
    assert "dep" not in vals
    assert vals["ved"] == 2
    assert vals["oes"] == "1"
    assert vals["nust"] == Decimal("360")
    assert vals["q"] == Decimal("1749.1")
    assert vals["qotr"] is None
    assert vals["turt"] == Decimal("151.35")
    assert vals["e"] == Decimal("2004")
    assert vals["hfix"] == 1


def test_stations_schema_filename_without_year():
    assert extract_year_from_fuel_params_import_filename("Станции(Схема).xlsx") is None
    assert detect_fuel_params_excel_import_kind("Станции(Схема).xlsx") == "stations"
