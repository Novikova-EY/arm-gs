from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.energy_balance.services import ee_balance_ves_ses_page_services as aes_page_services
from app.energy_balance.services.ee_balance_hydro_own_needs_services import (
    save_hydro_own_needs_coefficient,
)
from app.energy_balance.services.ee_balance_ves_ses_page_services import (
    _aes_delivery_energy,
    _aes_metric_maps,
    _aes_own_needs_percent,
    _accumulate_station,
    _blank_total,
    _finalize_total,
    _hydro_metric_maps,
)


def test_aes_own_needs_percent_uses_entered_own_needs_divided_by_generation():
    own_needs = Decimal("1000")
    generation = Decimal("8000")
    own_needs_percent = Decimal("12.5")

    assert _aes_own_needs_percent(own_needs, generation) == own_needs_percent
    assert _aes_delivery_energy(own_needs, generation) == Decimal("7000")


def test_focus_page_type_ids_are_separated_by_technology(monkeypatch):
    monkeypatch.setattr(
        aes_page_services,
        "get_station_type_list_full",
        lambda: [
            SimpleNamespace(id=1, name="АЭС"),
            SimpleNamespace(id=2, name="АЭС плавучая"),
            SimpleNamespace(id=3, name="ТЭС"),
            SimpleNamespace(id=4, name="ГЭС"),
            SimpleNamespace(id=5, name="ГАЭС"),
        ],
    )

    assert aes_page_services.aes_station_type_ids() == [1, 2]
    assert aes_page_services.ges_station_type_ids() == [4]
    assert aes_page_services.gaes_station_type_ids() == [5]


def test_hydro_coefficient_save_rejects_unknown_type_and_negative_values():
    with pytest.raises(ValueError, match="только для ГЭС и ГАЭС"):
        save_hydro_own_needs_coefficient(1, "aes", "0.1")
    with pytest.raises(ValueError, match="неотрицательным"):
        save_hydro_own_needs_coefficient(1, "ges", "-0.1")


def test_hydro_metrics_use_station_coefficient_for_each_year():

    maps = _hydro_metric_maps(
        Decimal("0.025"),
        {2024: Decimal("800"), 2025: Decimal("1000")},
        [2024, 2025],
        digits=1,
    )

    assert maps["own_needs"][2024] == Decimal("20.000")
    assert maps["own_needs_display"] == {2024: "20,0", 2025: "25,0"}
    assert maps["delivery_display"] == {2024: "780,0", 2025: "975,0"}
    assert maps["own_needs_coefficient_display"] == "0,025"


def test_hydro_totals_sum_station_coefficient_results():
    years = [2025]
    total = _blank_total(years)
    for coefficient, generation in (
        (Decimal("0.01"), Decimal("1000")),
        (Decimal("0.02"), Decimal("2000")),
    ):
        metrics = _hydro_metric_maps(coefficient, {2025: generation}, years, digits=1)
        _accumulate_station(
            total,
            {
                "capacity": {2025: None},
                "energy": {2025: generation},
                "owner": {},
                "min_value": None,
                **metrics,
            },
        )

    row = _finalize_total(total, years, 1, "ОЭС – всего", "ues_total")

    assert row["own_needs_display"] == {2025: "50,0"}
    assert row["delivery_display"] == {2025: "2 950,0"}


def test_gaes_charge_values_are_summed_for_totals():
    years = [2025]
    total = _blank_total(years)
    for charge in (Decimal("12.5"), Decimal("7.25")):
        _accumulate_station(
            total,
            {
                "capacity": {2025: None},
                "energy": {2025: None},
                "owner": {},
                "gaes_charge": {2025: charge},
                "gaes_charge_enabled": True,
                "min_value": None,
            },
        )

    row = _finalize_total(total, years, 2, "ГАЭС России", "russia_total")

    assert row["gaes_charge_enabled"] is True
    assert row["gaes_charge_display"] == {2025: "19,75"}


def test_hydro_metrics_are_blank_without_a_coefficient():
    maps = _hydro_metric_maps(None, {2025: Decimal("1000")}, [2025], digits=1)

    assert maps["own_needs_display"] == {2025: ""}
    assert maps["delivery_display"] == {2025: ""}
    assert maps["own_needs_coefficient_display"] == ""


@pytest.mark.parametrize(
    "own_needs, generation",
    [(None, Decimal("10")), (Decimal("5"), Decimal("0")), (Decimal("5"), None)],
)
def test_aes_percent_is_empty_for_missing_inputs_or_zero_denominator(own_needs, generation):
    assert _aes_own_needs_percent(own_needs, generation) is None
    maps = _aes_metric_maps({2025: own_needs}, {2025: generation}, [2025], digits=1)
    assert maps["own_needs_display"] == {2025: ""}
    assert maps["own_needs_raw"] == {2025: ""}


def test_aes_zero_own_needs_has_zero_percent_and_zero_generation_is_undefined():
    assert _aes_own_needs_percent(Decimal("0"), Decimal("10")) == 0
    assert _aes_own_needs_percent(Decimal("5"), Decimal("0")) is None
    assert _aes_delivery_energy(Decimal("5"), Decimal("0")) is None


def test_aes_totals_sum_entered_own_needs_and_recalculate_percent():
    years = [2026]
    total = _blank_total(years)
    for generation, own_needs in (("100", "5"), ("300", "10")):
        energy = {2026: Decimal(generation)}
        metrics = _aes_metric_maps({2026: Decimal(own_needs)}, energy, years, digits=1)
        _accumulate_station(total, {"energy": energy, **metrics})

    row = _finalize_total(total, years, 1, "АЭС России", "russia_total")

    assert row["own_needs_energy_display"] == {2026: "15,0"}
    assert row["own_needs_display"] == {2026: "3,8"}
    assert row["own_needs_energy_raw"] == {2026: "15"}
    assert row["delivery_display"] == {2026: "385,0"}


def test_aes_percent_uses_unrounded_values():
    maps = _aes_metric_maps(
        {2026: Decimal("0.1578")}, {2026: Decimal("0.6")}, [2026], digits=1
    )
    assert maps["own_needs_energy_display"] == {2026: "0,2"}
    assert maps["own_needs_display"] == {2026: "26,3"}


def test_manual_percent_is_used_only_when_own_needs_energy_is_missing():
    maps = _aes_metric_maps(
        {2026: None, 2027: Decimal("10"), 2028: Decimal("0")},
        {2026: Decimal("100"), 2027: Decimal("100"), 2028: Decimal("100")},
        [2026, 2027, 2028], digits=1,
        percent_map={2026: Decimal("7.25"), 2027: Decimal("8"), 2028: Decimal("9")},
    )
    assert maps["own_needs_display"] == {2026: "7,3", 2027: "10,0", 2028: "0,0"}
    assert maps["own_needs_percent_calculated"] == {2026: False, 2027: True, 2028: True}
    assert maps["own_needs_raw"][2026] == "7,25"
    assert maps["own_needs_energy_display"][2028] == "0,0"
    assert maps["delivery_display"][2026] == "92,8"


@pytest.mark.parametrize("own_needs, editable", [(None, True), (Decimal("0"), False), (Decimal("5"), False)])
def test_rendered_percent_editor_is_locked_only_when_own_needs_are_filled(own_needs, editable):
    import re
    from pathlib import Path
    from jinja2 import Environment

    source = Path("app/templates/energy_balance/ee_balance/ee_balance_ves_ses.html").read_text(encoding="utf-8")
    macros = source[source.index("    {% macro ves_raw_attrs"):source.index("    <style>")]
    template = Environment(autoescape=True).from_string(macros + "{{ focus_extra_rows(row) }}")
    row = {"kind": "station", "id": 1, **_aes_metric_maps(
        {2026: own_needs}, {2026: Decimal("100")}, [2026], 1,
        percent_map={2026: Decimal("7.25")},
    )}
    context = dict(row=row, years=[2026], owner_years=[], is_aes_focus=True,
                   is_station_focus=True, is_snee_focus=False, is_coefficient_focus=False)
    html = template.render(can_edit=True, **context)
    tag = re.search(r'<span[^>]*data-kind="own_needs_percent"[^>]*>', html).group()
    assert ('data-readonly="1"' not in tag) is editable
    assert ('tabindex="0"' in tag) is editable
    assert 'data-kind="own_needs_percent"' not in template.render(can_edit=False, **context)


@pytest.mark.parametrize("generation, percent, expected", [
    (Decimal("200"), Decimal("7.5"), Decimal("185")),
    (Decimal("200"), Decimal("0"), Decimal("200")),
    (Decimal("200"), Decimal("100"), Decimal("0")),
    (Decimal("0"), Decimal("7.5"), Decimal("0")),
    (None, Decimal("7.5"), None),
    (Decimal("200"), None, None),
])
def test_aes_delivery_uses_manual_percent_when_own_needs_are_empty(generation, percent, expected):
    assert _aes_delivery_energy(None, generation, percent) == expected


def test_aes_delivery_display_uses_unrounded_percent():
    maps = _aes_metric_maps({}, {2026: Decimal("200")}, [2026], digits=1,
                            percent_map={2026: Decimal("7.25")})
    assert maps["own_needs_display"] == {2026: "7,3"}
    assert maps["delivery_display"] == {2026: "185,5"}
