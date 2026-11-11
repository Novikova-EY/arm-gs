"""Стартовая страница и ссылки на все виды оборудования должны открываться."""

from io import BytesIO
from urllib.parse import urlsplit

from openpyxl import load_workbook
import pytest

from test_technical_characteristics import database, http_client
from app.extensions import db
from app.rational_structure.models import EquipmentTechnicalCharacteristic


PAGES = [
    ("/technical_characteristics", "steam", "характеристики турбин"),
    ("/technical_characteristics/hydro", "hydro", "характеристики гидротурбин"),
    ("/technical_characteristics/boilers/energy", "boiler_energy", "характеристики энергетических котлов"),
    ("/technical_characteristics/boilers/water", "boiler_water", "характеристики водогрейных котлов"),
]


def test_hub_renders_links_to_every_equipment_page(http_client):
    client, _ = http_client
    response = client.get("/rational_structure/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for path, _, _ in PAGES:
        assert f'href="/rational_structure{path}"' in html


@pytest.fixture
def populated_client(http_client):
    client, _ = http_client
    for version in (1, 2):
        for kind in ("steam", "gas", "hydro", "boiler_energy", "boiler_water"):
            db.session.add(EquipmentTechnicalCharacteristic(
                database_version_id=version, equipment_type=kind, report_year=2024,
                equipment_code=f"equipment-{version}-{kind}",
            ))
    db.session.commit()
    return client


@pytest.mark.parametrize("path,equipment_type,title", PAGES)
def test_equipment_pages_render_and_isolate_rows(populated_client, path, equipment_type, title):
    response = populated_client.get("/rational_structure" + path, query_string={"year": 2024})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert title in html
    assert f"equipment-1-{equipment_type}" in html
    assert "equipment-2-" not in html
    for _, kind, _ in PAGES:
        if kind != equipment_type:
            assert f"equipment-1-{kind}" not in html
    if equipment_type == "steam":
        assert "equipment-1-gas" in html
    else:
        assert "equipment-1-gas" not in html
    assert ('id="rs-match-status"' in html) == (equipment_type == "hydro")
    assert ('id="rsFiltersCollapse"' in html) == (equipment_type != "steam")


@pytest.mark.parametrize("section,expected_types", [
    ("turbines", ["steam", "gas"]), ("hydro", ["hydro"]),
    ("boiler_energy", ["boiler_energy"]), ("boiler_water", ["boiler_water"]),
])
def test_export_preserves_selected_equipment_scope(populated_client, section, expected_types):
    response = populated_client.get("/rational_structure/technical_characteristics/export",
                                    query_string={"section": section, "year": 2024})
    assert response.status_code == 200
    book = load_workbook(BytesIO(response.data), read_only=True)
    try:
        codes = {row[0] for row in book.active.iter_rows(min_row=2, values_only=True)}
        assert codes == {f"equipment-1-{kind}" for kind in expected_types}
    finally:
        book.close()


@pytest.mark.parametrize("path,section", [
    ("/technical_characteristics", "turbines"),
    ("/technical_characteristics/hydro", "hydro"),
    ("/technical_characteristics/boilers/energy", "boiler_energy"),
    ("/technical_characteristics/boilers/water", "boiler_water"),
])
def test_rejected_upload_returns_to_selected_equipment_page(http_client, path, section):
    client, _ = http_client
    response = client.post("/rational_structure/technical_characteristics/import",
                           data={"section": section, "year": "2024"})
    assert response.status_code == 302
    assert urlsplit(response.headers["Location"]).path == "/rational_structure" + path
