from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, render_template


TEMPLATES = Path(__file__).resolve().parents[2] / "app" / "templates"


@pytest.mark.parametrize("per_page", [25, None])
@pytest.mark.parametrize("is_admin, show_button, expected", [
    (True, True, True),
    (False, True, False),
    (True, False, False),
])
def test_transfer_button_is_on_left_of_top_pagination(per_page, is_admin, show_button, expected):
    app = Flask(__name__, template_folder=str(TEMPLATES))
    app.add_url_rule("/fuel/stations_equipment_groups", "fuel_bp.stations_equipment_groups", lambda: "")
    app.add_url_rule("/transfer/page", "fuel_bp.equipment_group_binding_transfer_page", lambda: "")
    with app.test_request_context("/fuel/stations_equipment_groups?composite_only=1"):
        html = render_template(
            "fuel/_shared/station_filters_third_row.html",
            current_user=SimpleNamespace(is_admin=is_admin),
            show_binding_transfer_button=show_button,
            center_top_pagination=True,
            hide_year_range=True,
            hide_filters_third_row_reset=True,
            per_page=per_page,
            current_page=1,
            total_pages=2,
        )

    target = 'href="/transfer/page"'
    assert (target in html) is expected
    if expected:
        left = html.index("station-filters-third-left")
        button = html.index(target)
        assert left < button < html.index('id="yearForm"')
        assert '<a class="btn btn-outline-primary"' in html[left:button]
        assert 'target="_blank" rel="noopener"' in html[button:]
        assert 'data-bs-toggle="modal"' not in html
        if per_page is not None:
            assert button < html.index("station-filters-third-pagination")
    if per_page is not None:
        assert "composite_only=1" in html


def test_equipment_group_page_template_compiles():
    app = Flask(__name__, template_folder=str(TEMPLATES))
    app.jinja_env.get_template("fuel/equipment_groups/stations_equipment_groups.html")
    app.jinja_env.get_template("fuel/equipment_groups/binding_transfer.html")


def test_catalog_does_not_embed_transfer_interface_or_script():
    html = (TEMPLATES / "fuel/equipment_groups/stations_equipment_groups.html").read_text(encoding="utf-8")
    assert "_binding_transfer.html" not in html
    assert "equipment_group_binding_transfer.js" not in html
    assert "_binding_transfer_button.html" in html
