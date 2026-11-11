from pathlib import Path
import re
from types import SimpleNamespace

from flask import Flask, render_template
import pytest


TEMPLATES = Path(__file__).resolve().parents[2] / "app/templates"


@pytest.fixture
def app():
    app = Flask(__name__, template_folder=str(TEMPLATES))
    app.add_url_rule("/station/<int:station_id>", "station_bp.station_details", lambda: "")
    app.add_url_rule("/machine/<int:station_id>/<int:machine_id>", "station_bp.machine_details", lambda: "")
    app.add_url_rule("/group/<int:equipment_group_id>", "fuel_bp.equipment_group_edit", lambda: "")
    app.add_url_rule("/transfer", "fuel_bp.equipment_group_binding_transfer_page", lambda: "")
    return app


@pytest.mark.parametrize("entity_type", ["station", "equipment_group", "machine"])
@pytest.mark.parametrize("version_id", [None, 20])
@pytest.mark.parametrize("code,record_id,status", [
    ("shared-code", 10, "matching"),
    (" shared-code ", 10, "matching"),
    ("different-code", 10, "different"),
    ("", None, "missing"),
    ("", 10, "empty"),
])
def test_cell_distinguishes_matching_different_missing_and_empty(
    app, entity_type, version_id, code, record_id, status,
):
    with app.test_request_context():
        cell = app.jinja_env.get_template("generation/stations/external_code_cell.html").module.external_code_cell
        html = str(cell(entity_type, {"id": version_id, "version_number": "Test"},
                        code, record_id, "shared-code", rowspan=2))
    assert ("table-warning" in html) == (status == "different")
    assert ("external-code-different" in html) == (status == "different")
    assert ("external-code-missing-cell" in html) == (status == "missing")
    assert ("– нет записи" in html) == (status == "missing")
    assert ("Код не задан" in html) == (status == "empty")
    assert ("external-code-input" in html) == (record_id is not None)
    assert 'rowspan="2"' in html
    if status == "different":
        assert "Код отличается от кода записи" in html
    if status == "missing":
        explanation = "Нет записи без версии БД" if version_id is None else "Нет записи в этой версии БД"
        assert explanation in html
    else:
        assert f'data-entity-type="{entity_type}"' in html
        assert 'data-record-id="10"' in html
        assert f'value="{code.strip()}"' in html


@pytest.mark.parametrize("different_code", [None, "other-code"])
def test_all_row_types_leave_matching_cells_unmarked_when_other_versions_are_missing_or_different(app, different_code):
    versions = [{"id": i, "version_number": f"Version {i}"} for i in (20, 37, 39, 40)]
    codes = {20: "shared-code", 37: "shared-code", 39: different_code or "", 40: ""}
    records = {20: 10, 37: 11, 39: 12 if different_code else None, 40: None}
    common = dict(external_code="shared-code", external_codes_by_version=codes,
                  external_code_record_ids_by_version=records, external_code_mismatch=True)
    machine = SimpleNamespace(id=1, machine_group="", machine_number="1", display_name="Турбина",
                              pgu_machines=[], **common)
    group = SimpleNamespace(id=2, name="Общая группа", numb=11, main=False, database_version_id=37,
                            duplicate_code_count=1, machines=[machine], **common)
    station = SimpleNamespace(id=3, name="Станция", regional_district=None, machines=[machine],
                              external_code_equipment_groups=[group], external_code_ungrouped_machines=[], **common)
    with app.test_request_context():
        html = render_template("generation/stations/external_code_station_rows.html",
                               station=station, database_versions=versions)
    for row_class in ("station", "equipment-group", "machine"):
        row = re.search(rf'<tr[^>]*class="[^"]*external-code-{row_class}-row[^"]*"[^>]*>(.*?)</tr>', html, re.S).group(1)
        cells = re.findall(r"<td\b[^>]*>.*?</td>", row, re.S)
        code_cells = [cell for cell in cells if "external-code-cell" in cell]
        assert len(code_cells) == 4
        for cell in code_cells[:2]:
            assert "table-warning" not in cell
            assert "external-code-missing-cell" not in cell
            assert 'value="shared-code"' in cell
        assert ("table-warning" in code_cells[2]) == bool(different_code)
        assert ("external-code-missing-cell" in code_cells[2]) == (not different_code)
        assert "table-warning" not in code_cells[3]
        assert "– нет записи" in code_cells[3]


def test_reference_code_and_input_values_are_escaped(app):
    with app.test_request_context():
        cell = app.jinja_env.get_template("generation/stations/external_code_cell.html").module.external_code_cell
        html = str(cell("station", {"id": 20, "version_number": "Test"}, '<script>"', 10, '<img>"'))
    assert "<script>" not in html
    assert "<img>" not in html
    assert "&lt;script&gt;" in html
    assert "&lt;img&gt;" in html
