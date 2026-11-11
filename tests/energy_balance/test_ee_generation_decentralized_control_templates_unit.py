from decimal import Decimal
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader


@pytest.fixture
def template_environment():
    templates = Path(__file__).resolve().parents[2] / "app" / "templates"
    return Environment(loader=FileSystemLoader(str(templates)), autoescape=True)


def test_decentralized_zone_control_row_uses_est_control_key(template_environment):
    html = template_environment.get_template(
        "energy_balance/ee_generation/ee_generation_control_row.html"
    ).render(
        res_id=164,
        control_key="est-164",
        control_level="est",
        control_entity_id=164,
        label="Децентрализованная зона, всего",
        period_columns=[(2024, "2024")],
        period_totals={2024: Decimal("17.5")},
        format_generation_input_value=lambda value, digits: str(value),
        rounding_digits=1,
        can_edit_energy_balance=True,
    )

    assert 'class="form-control form-control-sm text-center ee-control-value"' in html
    assert 'data-control-key="est-164"' in html
    assert 'data-control-level="est"' in html
    assert 'data-control-entity-id="164"' in html
    assert 'value="17.5"' in html


def test_decentralized_zone_verification_row_uses_station_sum_and_est_key(
    template_environment,
):
    html = template_environment.get_template(
        "energy_balance/ee_generation/ee_generation_verification_row.html"
    ).render(
        res_id=164,
        control_key="est-164",
        label="Проверка для Децентрализованная зона",
        period_columns=[(2024, "2024")],
        period_totals={2024: Decimal("2.5")},
        left_totals={2024: Decimal("20")},
        format_verification_cell=lambda value: str(value),
        is_verification_nonzero=lambda value: value != 0,
    )

    assert 'class="ee-verification-cell"' in html
    assert 'data-control-key="est-164"' in html
    assert 'data-left-sum="20"' in html
    assert "2.5" in html
