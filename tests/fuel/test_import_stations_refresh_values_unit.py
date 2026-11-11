from decimal import Decimal
from types import SimpleNamespace

import pandas as pd

from app.fuel.services.fuel_imports import import_equipment_group_fuel_params_services as service


class _Logger:
    def info(self, *args, **kwargs):
        pass

    def exception(self, *args, **kwargs):
        pass


def test_stations_import_refreshes_reported_values_and_sn_ee_from_snk(monkeypatch):
    dataframe = pd.DataFrame(
        [
            {
                "NUMB1120": 123,
                "YEAR": 2024,
                "E": 200,
                "EOTP": 150,
                "EUST": 45,
                "EURT": 300,
                "SNK": 5,
            }
        ]
    )

    class _ExcelFile:
        sheet_names = ["Станции"]

        def parse(self, sheet_name, header=0):
            assert sheet_name == "Станции"
            assert header == 0
            return dataframe.copy()

    param = SimpleNamespace(
        e=None,
        eotp=Decimal("100"),
        eust=Decimal("30"),
        eurt=Decimal("300"),
        sn_ee=Decimal("1"),
        snk=Decimal("1"),
    )
    monkeypatch.setattr(service.pd, "ExcelFile", lambda _file: _ExcelFile())
    monkeypatch.setattr(service, "get_fuel_import_logger", lambda _name: _Logger())
    monkeypatch.setattr(service, "log_to_db", lambda *args: None)
    monkeypatch.setattr(service, "_resolve_equipment_groups_from_row", lambda _row: [(1, 7)])
    monkeypatch.setattr(service, "_get_or_create_equipment_group_fuel_param", lambda *_args: (param, False))
    monkeypatch.setattr(service, "sanitize_equipment_group_fuel_param_foreign_keys", lambda _param: False)
    monkeypatch.setattr(service, "db", SimpleNamespace(session=SimpleNamespace(commit=lambda: None)))

    result = service.import_equipment_group_fuel_params_from_excel(
        SimpleNamespace(filename="Станции_2024.xlsx"), "tester", year=2024
    )

    assert result["updated"] == 1
    assert param.e == Decimal("200")
    assert param.eotp == Decimal("150")
    assert param.eust == Decimal("45")
    assert param.eurt == Decimal("300")
    assert param.snk == Decimal("5")
    assert param.sn_ee == Decimal("10")


def test_stations_import_prefers_explicit_sn_ee_over_derived_value():
    dataframe = pd.DataFrame(
        [{"E": 200, "SNK": 5, "SN_EE": 12.5}]
    )
    dataframe = service._apply_column_aliases(dataframe)
    values = service._stations_schema_row_values(dataframe.iloc[0], dataframe.columns)
    assert values["sn_ee"] == Decimal("12.5")
