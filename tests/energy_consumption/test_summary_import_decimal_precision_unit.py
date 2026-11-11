from datetime import datetime
from decimal import Decimal
from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree
from zipfile import ZipFile

import pytest
from sqlalchemy.dialects import postgresql

from app.common.perimeter_variant import registry
from app.energy_consumption.services import energy_consumption_summary_import_services as importer
from app.energy_consumption.services import energy_consumption_summary_services as summary
from app.extensions import db


NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def _workbook_bytes(raw_number, *, formula=False):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = importer.SHEET_MLN_KVTCH
    ws.append(["perimeter-variants", "Наименование", 2024, 2025])
    ws.append([importer.CODE_WITHOUT_NT_WITH_GAES, "ЕЭС России", "=1+1" if formula else 0, 0])
    ws["C2"].number_format = "0.0"
    ws["C3"] = datetime(2024, 1, 2)
    ws["D3"] = True
    ws["C4"] = "1 234,123456789012345678901"
    ws["D4"] = "=1+1"
    source = BytesIO()
    wb.save(source)
    target = BytesIO()
    with ZipFile(source) as original, ZipFile(target, "w") as output:
        for item in original.infolist():
            data = original.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                root = ElementTree.fromstring(data)
                cell = root.find(f".//{{{NS}}}c[@r='C2']")
                cell.find(f"{{{NS}}}v").text = raw_number
                data = ElementTree.tostring(root)
            output.writestr(item, data)
    return target.getvalue()


@pytest.mark.parametrize("number", [
    "1121724.6373212999",
    "1234567.123456789012345678",
    "0.123456789012345678901",
    "0.123456789012345678901234567890123456789",
    "-1.234567890123456E-25",
    "0",
])
@pytest.mark.parametrize("formula", [False, True])
def test_xlsx_numeric_and_cached_formula_values_keep_all_stored_digits(monkeypatch, number, formula):
    monkeypatch.setattr(registry, "_catalog", lambda: SimpleNamespace(
        variants_by_code={importer.CODE_WITHOUT_NT_WITH_GAES: None}
    ))
    monkeypatch.setattr(importer, "_aggregate_model_requires_perimeter_variant", lambda model: True)
    wb = importer._load_summary_workbook_from_bytes(_workbook_bytes(number, formula=formula))
    try:
        ws = wb[importer.SHEET_MLN_KVTCH]
        assert isinstance(ws["C2"].value, Decimal)
        assert ws["C2"].value == Decimal(number)
        assert ws["C2"].number_format == "0.0"
        assert ws["C3"].value == datetime(2024, 1, 2)
        assert ws["D3"].value is True
        assert ws["C4"].value == "1 234,123456789012345678901"
        assert ws["D4"].value is None
        values, mode = importer._aggregate_sheet_labels(importer._sheet_matrix(ws))
        assert mode
        assert values[("ЕЭС России", 2024, importer.CODE_WITHOUT_NT_WITH_GAES)] == Decimal(number)
    finally:
        wb.close()


def test_decimal_sum_keeps_digits_beyond_the_default_context():
    value = Decimal("1234567.123456789012345678901234567890123456789")
    charge = Decimal("0.000000000000000000000000000000000000001")
    total = importer._add_import_decimal_values(value, charge)
    assert total == Decimal("1234567.123456789012345678901234567890123456790")
    assert importer._add_import_decimal_values(total, charge.copy_negate()) == value


def test_formula_persistence_uses_full_tooltip_not_rounded_display():
    value = Decimal("1234567.123456789012345678")
    row = {
        "demand_model_name": importer.EnergySystemTypeEnergyConsumptionParameter.__name__,
        "parent_fk_column": "id_energy_system_type",
        "parent_id": 72,
        "perimeter_variant_code": importer.CODE_WITHOUT_NT_WITHOUT_GAES,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "pd_ec_formula_derived_row": True,
    }
    summary._write_numeric_year_values_to_summary_row(
        row, [2024], {2024: value}, parameter_key=row["parameter_key"], rounding_digits=1
    )
    assert row["year_values"] != row["year_numeric_tooltips"]
    values = importer._accumulator_from_formula_summary_rows(
        [row], [2024], field_name=row["parameter_key"]
    )
    assert list(values.values()) == [value]


def _migration():
    path = Path(__file__).resolve().parents[2] / "migrations/versions/gs26110201_energy_consumption_decimal_precision.py"
    spec = spec_from_file_location("ec_decimal_precision_migration", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_consumption_models_and_migration_remove_fixed_scale(monkeypatch):
    migration = _migration()
    changed = []
    monkeypatch.setattr(migration.op, "alter_column", lambda table, column, **kwargs: changed.append(
        (table, column, kwargs)
    ))
    migration.upgrade()
    assert len(changed) == 26
    for table, column, kwargs in changed:
        assert kwargs["type_"].compile(dialect=postgresql.dialect()) == "NUMERIC"
        model_table = db.metadata.tables[f"{kwargs['schema']}.{table}"]
        numeric = model_table.columns[column].type
        assert numeric.precision is None
        assert numeric.scale is None


def test_downgrade_refuses_to_round_existing_data(monkeypatch):
    migration = _migration()
    connection = SimpleNamespace(execute=lambda statement: SimpleNamespace(first=lambda: (1,)))
    monkeypatch.setattr(migration.op, "get_bind", lambda: connection)
    monkeypatch.setattr(migration.op, "alter_column", lambda *args, **kwargs: pytest.fail(
        "Downgrade must stop before modifying columns"
    ))
    with pytest.raises(ValueError, match="Нельзя уменьшить точность"):
        migration.downgrade()
