from pathlib import Path
from types import SimpleNamespace
from html.parser import HTMLParser

import pytest
from jinja2 import ChoiceLoader, DictLoader, Environment, FileSystemLoader


class TileParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tiles = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "home-outline__tile" in attrs.get("class", "").split():
            self.tiles.append(attrs)


@pytest.mark.parametrize("dataset", ["daymonth_info", "hour_info", "month_info", "power_energy_export_import_country", "rational_struct_functionals", "rational_struct_k0", "rational_struct_load_graf_import_to_java", "rational_struct_zones", "rational_struct_base", "line_capital_investments"])
@pytest.mark.parametrize("version_id", [37, None])
def test_dataset_tile_status_and_style(dataset, version_id):
    templates = Path(__file__).resolve().parents[2] / "app" / "templates"
    env = Environment(
        loader=ChoiceLoader([
            DictLoader({"hub_base.html": "{% block extra_head %}{% endblock %}{% block content %}{% endblock %}"}),
            FileSystemLoader(templates),
        ]),
        autoescape=True,
    )
    html = env.get_template("output_documents_transfer.html").render(
        current_user=SimpleNamespace(is_authenticated=True, is_admin=False),
        versions=[],
        selected_version_id=version_id,
        json_groups=[{
            "column": 1,
            "title": "common",
            "files": [{"dataset": dataset, "filename": dataset + ".json", "kind": "dataset", "enabled": True}],
        }],
        url_for=lambda endpoint, **kwargs: "/" + endpoint,
    )
    parser = TileParser()
    parser.feed(html)
    tile = parser.tiles[-1]

    if dataset in ("power_energy_export_import_country", "rational_struct_functionals", "rational_struct_k0", "rational_struct_load_graf_import_to_java", "rational_struct_zones", "rational_struct_base"):
        assert "output-doc-future" not in tile["class"].split()
        assert "output-doc-2027" not in tile["class"].split()
        assert "Скоро" in html
        assert "bi-clock" in html
        assert "Скоро будет разработано" in html
        assert ">2027</span>" not in html
        assert "Перспектива" not in html
    else:
        assert "output-doc-future" in tile["class"].split()
        if dataset == "line_capital_investments":
            assert "output-doc-2027" not in tile["class"].split()
            assert "Перспектива" in html
            assert ">2027</span>" not in html
        else:
            assert "output-doc-2027" in tile["class"].split()
            assert "background: #e8e5d3;" in html
            assert "background: #dcd6b9;" in html
            assert ">2027</span>" in html
            assert "Разработка запланирована на 2027 год" in html
            assert "Перспектива" not in html
        assert "Скоро" not in html
        assert "background: #e8eaed;" in html
    if version_id:
        assert tile["data-dataset"] == dataset
        assert tile["href"] == "/exchange_api_bp.get_dataset_by_version"
    else:
        assert tile["aria-disabled"] == "true"


@pytest.mark.parametrize("dataset", [
    "rational_struct_functionals",
    "rational_struct_k0",
    "rational_struct_load_graf_import_to_java",
    "rational_struct_zones",
])
@pytest.mark.parametrize("version_id", [37, None])
def test_mock_tiles_use_default_blue_style(dataset, version_id):
    from app.api.services.output_documents_catalog import build_output_document_groups

    templates = Path(__file__).resolve().parents[2] / "app" / "templates"
    env = Environment(
        loader=ChoiceLoader([
            DictLoader({"hub_base.html": "{% block content %}{% endblock %}"}),
            FileSystemLoader(templates),
        ]),
        autoescape=True,
    )
    groups = build_output_document_groups(public_datasets=[])
    item = next(item for group in groups for item in group["files"] if item["dataset"] == dataset)
    assert item["kind"] == "mock"
    html = env.get_template("output_documents_transfer.html").render(
        current_user=SimpleNamespace(is_authenticated=True, is_admin=False),
        versions=[],
        selected_version_id=version_id,
        json_groups=[{"column": 3, "title": "rational_struct_calc", "files": [item]}],
        url_for=lambda endpoint, **kwargs: (
            "/static/" + kwargs["filename"] if endpoint == "static" else "/" + endpoint
        ),
    )
    parser = TileParser()
    parser.feed(html)
    tile = parser.tiles[-1]
    assert tile["class"].split() == ["home-outline__tile"]
    assert tile["href"] == f"/static/mocks/{dataset}.json"
    assert tile["target"] == "_blank"
    assert tile["rel"] == "noopener noreferrer"
    assert "Скоро</span>" in html
    assert "bi-clock" in html


@pytest.mark.parametrize("key", ["powers", "technologies"])
@pytest.mark.parametrize("version_id", [37, None])
def test_result_tiles_link_to_external_api_and_interface(key, version_id):
    from app.api.services.output_documents_catalog import build_output_document_groups

    templates = Path(__file__).resolve().parents[2] / "app" / "templates"
    env = Environment(
        loader=ChoiceLoader([
            DictLoader({"hub_base.html": "{% block content %}{% endblock %}"}),
            FileSystemLoader(templates),
        ]),
        autoescape=True,
    )
    groups = build_output_document_groups(public_datasets=[])
    dataset = "rational_struct_export_from_java_" + key
    item = next(item for group in groups for item in group["files"] if item["dataset"] == dataset)
    assert item["kind"] == "external"
    assert item["enabled"] is True
    html = env.get_template("output_documents_transfer.html").render(
        current_user=SimpleNamespace(is_authenticated=True, is_admin=True),
        versions=[],
        selected_version_id=version_id,
        json_groups=groups,
        url_for=lambda endpoint, **kwargs: (
            "/rational_structure/calculated_values/" + kwargs["dataset_key"]
            if endpoint == "rational_structure_module_bp.calculated_values" else "/" + endpoint
        ),
    )
    parser = TileParser()
    parser.feed(html)
    api_url = "http://10.31.224.135:8080/api/v1/external-sync/views/ge_stage/v_" + dataset
    tile = next(tile for tile in parser.tiles if tile.get("href") == api_url)
    assert "output-doc-result" in tile["class"].split()
    assert "output-doc-mock" not in tile["class"].split()
    assert tile["target"] == "_blank"
    assert tile["rel"] == "noopener noreferrer"
    assert f'href="/rational_structure/calculated_values/{key}"' in html
    assert f"/static/mocks/{dataset}.json" not in html
