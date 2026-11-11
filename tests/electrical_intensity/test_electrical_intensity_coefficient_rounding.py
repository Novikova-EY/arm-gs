from decimal import Decimal
from pathlib import Path

from app.electrical_intensity.routes.electrical_intensity_route_helpers import (
    parse_coefficient_rounding_digits,
)
from app.electrical_intensity.services.electrical_intensity_services import (
    _apply_coefficient_rounding,
)


def test_coefficient_rounding_parameter_accepts_precision_and_defaults(app):
    for value, expected in (("0", 0), ("7", 7), ("10", 10), ("-1", -1)):
        with app.test_request_context(
            f"/electrical_intensity/electrical_intensity_fo/?coefficient_rounding_digits={value}"
        ):
            assert parse_coefficient_rounding_digits() == expected

    with app.test_request_context(
        "/electrical_intensity/electrical_intensity_fo/?coefficient_rounding_digits=11"
    ):
        assert parse_coefficient_rounding_digits() == 2

    with app.test_request_context("/electrical_intensity/electrical_intensity_fo/"):
        assert parse_coefficient_rounding_digits() == 2


def test_coefficient_rounding_only_changes_display_fields():
    block = {
        "coefficient_a": Decimal("12.345678"),
        "coefficient_a_manual": Decimal("12.345678"),
        "coefficient_a_computed": Decimal("2.345678"),
        "coefficient_x": Decimal("0.123456"),
        "ved_sections": [
            {
                "coefficient_a_manual": Decimal("3.456789"),
                "coefficient_a_computed": Decimal("1.234567"),
                "coefficient_x": Decimal("0.876543"),
            }
        ],
        "fd_summary": {
            "reference_rows": [
                {"has_coefficient_k": True, "coefficient_k": Decimal("1.234567")}
            ]
        },
    }

    _apply_coefficient_rounding([block], 3)

    assert block["coefficient_a_manual_display"] == "12,346"
    assert block["coefficient_a_computed_display"] == "2,346"
    assert block["coefficient_x_display"] == "0,123"
    section = block["ved_sections"][0]
    assert section["coefficient_a_manual_display"] == "3,457"
    assert section["coefficient_a_computed_display"] == "1,235"
    assert section["coefficient_x_display"] == "0,877"
    k_row = block["fd_summary"]["reference_rows"][0]
    assert k_row["coefficient_k_display"] == "1,235"
    assert block["coefficient_a_manual"] == Decimal("12.345678")
    assert section["coefficient_x"] == Decimal("0.876543")


def test_coefficient_editor_loads_after_shared_live_save_and_has_blur_save(app):
    page, *_ = app.jinja_loader.get_source(
        app.jinja_env, "electrical_intensity/electrical_intensity.html"
    )
    live_save = (
        Path(__file__).resolve().parents[2]
        / "app/static/js/electrical_intensity/live_save.js"
    ).read_text(encoding="utf-8")
    assert page.index("consumption_live_save.js") < page.index(
        "electrical_intensity/live_save.js"
    )
    assert "filename='js/electrical_intensity/live_save.js'" in page
    assert 'table.addEventListener("focusout"' in live_save


def test_page_template_provides_independent_coefficient_precision_control(app):
    page, *_ = app.jinja_loader.get_source(
        app.jinja_env, "electrical_intensity/electrical_intensity.html"
    )
    assert 'id="coefficient_rounding_digits"' in page
    assert 'name="coefficient_rounding_digits"' in page
    assert "Округл. (X):" in page
