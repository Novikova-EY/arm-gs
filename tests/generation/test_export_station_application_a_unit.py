# -*- coding: utf-8 -*-
"""Unit tests for Appendix A (Приложение А) export helpers."""

from datetime import date
from types import SimpleNamespace

import pytest

from app.common.services.help_services import NBSP, apply_excel_nbsp_patterns, to_excel_nbsp
from app.generation.services.station_services.export_station_application_a_helpers import (
    build_machine_appendix_a_note,
    display_appendix_a_machine_number,
    fuel_rowspan_key,
    keep_machine_for_appendix_a_as_of,
    machine_queue_sort_key,
    norilsk_taimyr_ees_label,
    norilsk_taimyr_file_label,
    should_show_energy_unit_header,
    station_name_number_sort_key,
    subject_has_dpm_vie_commissions,
    territory_name_genitive,
)


# --- 1. empty station number → dash ---


@pytest.mark.parametrize(
    "raw,expected",
    [
        (None, "–"),
        ("", "–"),
        ("   ", "–"),
        ("12", "12"),
        (" 3А ", "3А"),
    ],
)
def test_display_appendix_a_machine_number(raw, expected):
    assert display_appendix_a_machine_number(raw) == expected


# --- 2. notes: fact current year with exact dates; past years silent ---


def _machine(**kwargs):
    defaults = dict(
        date_commission_fact=None,
        date_joining_fact=None,
        date_relabing_fact=None,
        date_decompressing_fact=None,
        date_exploitation=None,
        date_exploitation_expected=None,
        date_commission_year=None,
        date_decompressing_expected=None,
        date_modernization_power_change_expected=None,
        date_modernization_no_power_change_expected=None,
        is_archived=False,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_note_fact_decommission_exact_date():
    m = _machine(date_decompressing_fact="15.06.2025")
    note = build_machine_appendix_a_note(m, fact_year=2025, all_years=range(2024, 2032))
    assert note == "Вывод из эксплуатации 15.06.2025"
    assert "в 2025 г." not in note


def test_note_fact_commission_exact_date():
    m = _machine(date_commission_fact="2025-03-01")
    note = build_machine_appendix_a_note(m, fact_year=2025, all_years=range(2024, 2032))
    assert note == "Ввод в эксплуатацию 01.03.2025"


def test_note_past_year_fact_omitted():
    m = _machine(
        date_commission_fact="10.05.2024",
        date_decompressing_fact="01.08.2024",
        date_relabing_fact="12.12.2024",
        date_joining_fact="02.02.2024",
    )
    note = build_machine_appendix_a_note(m, fact_year=2025, all_years=range(2024, 2032))
    assert note == ""


def test_note_fact_relabing_not_modernization():
    m = _machine(
        date_relabing_fact="20.04.2025",
        date_modernization_power_change_expected=2025,
    )
    note = build_machine_appendix_a_note(m, fact_year=2025, all_years=range(2024, 2032))
    assert note == "Перемаркировка 20.04.2025"
    assert "Модернизация" not in note


def test_note_fact_joining_not_commission():
    m = _machine(
        date_joining_fact="11.11.2025",
        date_commission_fact="11.11.2025",
        date_exploitation=2025,
    )
    note = build_machine_appendix_a_note(m, fact_year=2025, all_years=range(2024, 2032))
    assert note == "Присоединение 11.11.2025"
    assert "Ввод в эксплуатацию" not in note


def test_note_multiple_fact_events_combined():
    m = _machine(
        date_commission_fact="01.02.2025",
        date_relabing_fact="15.03.2025",
        date_decompressing_fact="30.11.2025",
    )
    note = build_machine_appendix_a_note(m, fact_year=2025, all_years=range(2024, 2032))
    assert note == (
        "Ввод в эксплуатацию 01.02.2025. "
        "Перемаркировка 15.03.2025. "
        "Вывод из эксплуатации 30.11.2025"
    )


def test_note_planned_commission_from_card_ves_ses_snee():
    """Ручные ВЭС/СЭС/СНЭЭ: плановый ввод из карточки «в … г.»."""
    m = _machine(date_exploitation_expected=2026)
    note = build_machine_appendix_a_note(m, fact_year=2025, all_years=range(2024, 2032))
    assert note == "Ввод в эксплуатацию в 2026 г."

    m2 = _machine(date_exploitation=2027)
    note2 = build_machine_appendix_a_note(m2, fact_year=2025, all_years=range(2024, 2032))
    assert note2 == "Ввод в эксплуатацию в 2027 г."


# --- 5. DPM VIE detection ---


def _vie_station(name, type_name, years):
    machines = [
        _machine(date_exploitation=y, date_commission_year=y) for y in years
    ]
    return SimpleNamespace(
        name=name,
        station_type=SimpleNamespace(name=type_name),
        machines=machines,
    )


def test_dpm_vie_true_for_rostov_style_ves():
    stations = [_vie_station("Вербная ВЭС", "ВЭС", [2025])]
    assert subject_has_dpm_vie_commissions(stations, fact_year=2025, sipr_end=2031) is True


def test_dpm_vie_false_for_old_ses_and_placeholder():
    stations = [
        _vie_station("С.Энерджи – Севастополь", "СЭС", [2013]),
        _vie_station("Новые СЭС", "СЭС", [2031, 2032]),
        _vie_station("Краснодарская СЭС", "СЭС", [2022]),
    ]
    assert subject_has_dpm_vie_commissions(stations, fact_year=2025, sipr_end=2031) is False


# --- 6. genitive territory / Norilsk labels ---


def test_territory_name_uses_name_rp_not_dp():
    rd = SimpleNamespace(
        name_rp="г. Москвы",
        name_dp="г. Москве",
        name_full="г. Москва",
        name="г. Москва",
    )
    assert territory_name_genitive(rd) == "г. Москвы"


def test_norilsk_labels():
    assert "Норильск" in norilsk_taimyr_file_label()
    assert "Красноярский" not in norilsk_taimyr_file_label()
    label = norilsk_taimyr_ees_label(
        "Таймырский Долгано-Ненецкий муниципальный район, Туруханский район "
        "и городской округ г. Норильск Красноярского края"
    )
    assert label.startswith("Электроэнергетическая система")
    assert "Норильск" in label


def test_hide_energy_unit_for_norilsk_kamchatka_keep_chukotka():
    assert should_show_energy_unit_header(
        district_name="Камчатский край",
        energy_unit_name="Петропавловский энергорайон",
    ) is False
    assert should_show_energy_unit_header(
        district_name="Чукотский автономный округ",
        energy_unit_name="Анадырский энергорайон",
    ) is True
    assert should_show_energy_unit_header(
        district_name="Красноярский край",
        energy_unit_name="Таймырский Долгано-Ненецкий муниципальный район",
        is_norilsk_taimyr=True,
    ) is False


# --- 7. NBSP patterns ---


@pytest.mark.parametrize(
    "src,fragment",
    [
        ("г. Москва", f"г.{NBSP}Москва"),
        ("с. Ивановка", f"с.{NBSP}Ивановка"),
        ("п. Лесной", f"п.{NBSP}Лесной"),
        ("2025 г.", f"2025{NBSP}г."),
        ("№ 12", f"№{NBSP}12"),
        ("110 кВ", f"110{NBSP}кВ"),
        ("4,9 МВт", f"4,9{NBSP}МВт"),
    ],
)
def test_excel_nbsp_patterns(src, fragment):
    assert fragment in apply_excel_nbsp_patterns(src)
    assert fragment in to_excel_nbsp(src, patterns_only=True)


# --- 8. fuel rowspan key merges empty as dash ---


def test_fuel_rowspan_key_empty_is_dash():
    assert fuel_rowspan_key(SimpleNamespace(fuel_so=None)) == "–"
    assert fuel_rowspan_key(SimpleNamespace(fuel_so="")) == "–"
    assert fuel_rowspan_key(SimpleNamespace(fuel_so="не указано")) == "–"
    assert fuel_rowspan_key(SimpleNamespace(fuel_so="Газ")) == "Газ"


# --- 11. keep machines with planned decommission in as_of year ---


def test_keep_machine_planned_decommission_in_as_of_year():
    as_of = date(2025, 1, 1)
    m = _machine(date_decompressing_expected=2025)
    assert keep_machine_for_appendix_a_as_of(m, as_of_date=as_of, sipr_start=2026) is True

    m_old = _machine(date_decompressing_expected=2024)
    assert keep_machine_for_appendix_a_as_of(m_old, as_of_date=as_of, sipr_start=2026) is False

    m_fact_later = _machine(date_decompressing_fact="15.06.2025")
    assert keep_machine_for_appendix_a_as_of(m_fact_later, as_of_date=as_of, sipr_start=2026) is True

    m_fact_as_of = _machine(date_decompressing_fact="01.01.2025")
    assert keep_machine_for_appendix_a_as_of(m_fact_as_of, as_of_date=as_of, sipr_start=2026) is False


# --- 13–14. sorting helpers ---


def test_station_name_number_sort_key_mosenergo_style():
    assert station_name_number_sort_key("ТЭЦ-21") < station_name_number_sort_key("ТЭЦ-22")
    assert station_name_number_sort_key("ТЭЦ-9") < station_name_number_sort_key("ТЭЦ-21")


def test_queue_sort_first_then_second():
    first = SimpleNamespace(machine_group="первая очередь", machine_number="1-3", machine_name="ПГУ", id=1)
    second = SimpleNamespace(machine_group="вторая очередь", machine_number="4-6", machine_name="ПГУ", id=2)
    assert machine_queue_sort_key(first) < machine_queue_sort_key(second)
