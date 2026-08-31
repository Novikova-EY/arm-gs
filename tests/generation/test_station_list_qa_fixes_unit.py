"""Unit tests for Generation station-list / machine-card QA fixes."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from app.common.services.help_services import (
    _clean_name,
    _has_balanced_angle_quotes,
    _replace_quotes_sequentially,
)
from app.generation.models.machine.machine_model import Machine
from app.generation.services.station_changes_services.station_changes_services import (
    resolve_effective_sync_area_id,
    resolve_effective_sync_area_id_from_parts,
)
from app.generation.services.station_services.groupped_services import (
    machine_commission_year_sort_value,
    order_station_machines_for_display,
    parse_machine_commission_year,
)


def _machine_ns(**kwargs):
    """Lightweight stand-in for Machine display properties (no ORM init)."""
    defaults = dict(
        date_commission_year=None,
        date_exploitation=None,
        date_exploitation_expected=None,
        date_commission_fact=None,
        date_joining_fact=None,
        date_detatchment_fact=None,
        date_decompressing_fact=None,
        date_decompressing_expected=None,
        date_modernization_power_change_expected=None,
        date_modernization_no_power_change_expected=None,
        date_relabing_fact=None,
        date_update_fact=None,
        tes_machine_type=None,
        pgu_machines=[],
        pgu_submachines=[],
    )
    defaults.update(kwargs)
    obj = SimpleNamespace(**defaults)
    # Bind helpers used by @property methods
    obj._is_pgu_parent_with_parts = lambda: Machine._is_pgu_parent_with_parts(obj)
    obj._fact_display_years = lambda raw: Machine._fact_display_years(obj, raw)
    obj._has_fact_in_current_year = lambda raw: Machine._has_fact_in_current_year(obj, raw)
    obj._relabing_year_for_display = lambda dt: Machine._relabing_year_for_display(obj, dt)
    return obj


# --- 1) machine_number empty persistence helpers ---


def test_machine_number_empty_string_is_change_from_one():
    old_v, new_v = "1", ""
    to_str = lambda x: (
        str(x).strip() if x is not None and str(x).strip() != "" else "не указано"
    )
    assert to_str(old_v) != to_str(new_v)
    assert to_str(new_v) == "не указано"


# --- 2) display years: fact suppresses expected ---


def test_modernization_display_suppresses_expected_when_relabing_in_current_year():
    m = _machine_ns(
        date_modernization_power_change_expected=2027,
        date_relabing_fact="15.06.2025",
    )
    with patch(
        "app.common.services.get_services.years.years_get_services.get_current_year",
        return_value=2025,
    ):
        assert Machine.modernization_display.fget(m) == "2025"


def test_modernization_display_keeps_expected_when_no_current_fact():
    m = _machine_ns(date_modernization_power_change_expected=2027)
    with patch(
        "app.common.services.get_services.years.years_get_services.get_current_year",
        return_value=2025,
    ):
        assert Machine.modernization_display.fget(m) == "2027"


def test_commission_display_hides_expected_when_joining_fact_current_year():
    m = _machine_ns(
        date_exploitation_expected=2026,
        date_joining_fact="01.03.2025",
    )
    with patch(
        "app.common.services.get_services.years.years_get_services.get_current_year",
        return_value=2025,
    ):
        assert Machine.commission_display.fget(m) is None


def test_decompressing_display_01_01_rule():
    m = _machine_ns(
        date_decompressing_fact="01.01.2025",
        date_decompressing_expected=2030,
    )
    assert Machine.decompressing_display.fget(m) == 2024


def test_pgu_parent_hides_commission_and_modernization():
    m = _machine_ns(
        date_commission_year=2024,
        date_modernization_power_change_expected=2026,
        tes_machine_type=SimpleNamespace(name="ПГУ"),
        pgu_machines=[SimpleNamespace(id=1)],
    )
    assert Machine.commission_display.fget(m) is None
    assert Machine.modernization_display.fget(m) is None


# --- 3) quotes ---


def test_nested_yolochki_not_mangled_by_clean_name():
    src = "АО «Группа «Илим»»"
    assert _has_balanced_angle_quotes(src)
    assert _clean_name(src) == src
    assert _replace_quotes_sequentially(src) == src


def test_ascii_quotes_still_normalized():
    assert _replace_quotes_sequentially('АО "Группа"') == "АО «Группа»"


# --- 6) decommission filter 01.01.XX → XX-1 (pattern contract) ---


def test_decompressing_filter_0101_patterns():
    """Same pattern contract as modernization filter / card display."""
    years_only = [2024]
    pats = []
    for y in years_only:
        pats.append(rf"01\.01\.{y + 1}\b")
        pats.append(rf"(?<!01\.01\.){y}(?!\d)")
    fact_regex = "(" + "|".join(pats) + ")"
    assert r"01\.01\.2025\b" in fact_regex
    assert r"(?<!01\.01\.)2024(?!\d)" in fact_regex
    # 01.01.2025 must match year filter 2024, not 2025
    import re

    assert re.search(fact_regex, "01.01.2025")
    assert not re.search(
        "(" + "|".join([rf"01\.01\.{2025 + 1}\b", rf"(?<!01\.01\.){2025}(?!\d)"]) + ")",
        "01.01.2025",
    )


# --- 7) commission year sort: year ASC, not id / odd-even ---


def _sort_machine(**kwargs):
    defaults = dict(
        id=0,
        machine_number="",
        machine_name="",
        machine_group="",
        fuel_so="",
        is_archived=False,
        date_commission_year=None,
        date_exploitation_expected=None,
        commission_display=None,
        powers_by_year=None,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_parse_machine_commission_year():
    assert parse_machine_commission_year(2031) == 2031
    assert parse_machine_commission_year("01.01.2042") == 2042
    assert parse_machine_commission_year(None) is None


def test_commission_year_sort_ungrouped_voronezh_2042_not_first():
    """Без группы оборудования каждый агрегат — отдельный блок; раньше порядок шёл по id."""
    machines = [
        _sort_machine(id=10, date_commission_year=2042, machine_name="а"),
        _sort_machine(id=11, date_commission_year=2031, machine_name="б"),
        _sort_machine(id=12, date_commission_year=2032, machine_name="в"),
        _sort_machine(id=13, date_commission_year=2033, machine_name="г"),
    ]
    order_station_machines_for_display(machines)
    assert [m.date_commission_year for m in machines] == [2031, 2032, 2033, 2042]


def test_commission_year_sort_odd_then_even_lipetsk():
    machines = [
        _sort_machine(id=1, date_commission_year=2031),
        _sort_machine(id=2, date_commission_year=2033),
        _sort_machine(id=3, date_commission_year=2035),
        _sort_machine(id=4, date_commission_year=2032),
        _sort_machine(id=5, date_commission_year=2034),
    ]
    order_station_machines_for_display(machines)
    assert [m.date_commission_year for m in machines] == [2031, 2032, 2033, 2034, 2035]


def test_commission_year_sort_new_ses_group_even_then_odd():
    """«Новые СЭС»: пустое топливо дробит блоки по id — годы должны идти по возрастанию."""
    machines = [
        _sort_machine(id=20, machine_group="Новые СЭС", date_commission_year=2032),
        _sort_machine(id=21, machine_group="Новые СЭС", date_commission_year=2034),
        _sort_machine(id=22, machine_group="Новые СЭС", date_commission_year=2036),
        _sort_machine(id=23, machine_group="Новые СЭС", date_commission_year=2031),
        _sort_machine(id=24, machine_group="Новые СЭС", date_commission_year=2033),
        _sort_machine(id=25, machine_group="Новые СЭС", date_commission_year=2035),
    ]
    order_station_machines_for_display(machines)
    assert [m.date_commission_year for m in machines] == [2031, 2032, 2033, 2034, 2035, 2036]


def test_commission_year_sort_new_ses_mixed_buryatia():
    machines = [
        _sort_machine(id=8, machine_group="Новые СЭС", date_commission_year=2040),
        _sort_machine(id=3, machine_group="Новые СЭС", date_commission_year=2031),
        _sort_machine(id=5, machine_group="Новые СЭС", date_commission_year=2038),
        _sort_machine(id=1, machine_group="Новые СЭС", date_commission_year=2033),
        _sort_machine(id=9, machine_group="Новые СЭС", date_commission_year=2032),
    ]
    order_station_machines_for_display(machines)
    assert [m.date_commission_year for m in machines] == [2031, 2032, 2033, 2038, 2040]


def test_tes_numbered_units_keep_number_order_not_year():
    """Нумерные ТЭС: ст. № 1, 2, 3 — не год ввода первым."""
    machines = [
        _sort_machine(id=30, machine_number="3", machine_group="ТЭС", date_commission_year=2020),
        _sort_machine(id=31, machine_number="1", machine_group="ТЭС", date_commission_year=2025),
        _sort_machine(id=32, machine_number="2", machine_group="ТЭС", date_commission_year=2022),
    ]
    order_station_machines_for_display(machines)
    assert [m.machine_number for m in machines] == ["1", "2", "3"]


def test_machine_commission_year_from_powers_by_year():
    machine = _sort_machine(
        powers_by_year=[{"event": "commission", "year": 2037}, {"event": "decommission", "year": 2031}],
    )
    assert machine_commission_year_sort_value(machine) == 2037


# --- 9) sync zones ---


def test_kaliningrad_merged_into_first_sz_before_2025():
    first = SimpleNamespace(id=1, name="1-я синхронная зона", number="1")
    kali = SimpleNamespace(id=10, name="Синхронная зона Калининградской области", number="")
    sa_by_id = {1: first, 10: kali}
    station = SimpleNamespace(
        regional_district=SimpleNamespace(
            name="Калининградская область",
            id_synchronous_area=10,
        )
    )
    assert resolve_effective_sync_area_id(station, sa_by_id, current_year=2024) == 1
    assert resolve_effective_sync_area_id(station, sa_by_id, current_year=2025) == 10
    assert resolve_effective_sync_area_id_from_parts(
        "Калининградская область", 10, sa_by_id, year=2024
    ) == 1
    assert resolve_effective_sync_area_id_from_parts(
        "Калининградская область", 0, sa_by_id, year=2025
    ) == 10
    assert resolve_effective_sync_area_id_from_parts(
        "Калининградская область", 0, sa_by_id, year=2024
    ) == 1


def test_taimyr_not_in_first_sz():
    first = SimpleNamespace(id=1, name="1-я синхронная зона", number="1")
    sa_by_id = {1: first}
    station = SimpleNamespace(
        regional_district=SimpleNamespace(
            name="Таймырский Долгано-Ненецкий муниципальный район",
            id_synchronous_area=1,
        )
    )
    assert resolve_effective_sync_area_id(station, sa_by_id, current_year=2025) == 0
    assert resolve_effective_sync_area_id_from_parts(
        "Норильск", 1, sa_by_id, year=2024
    ) == 0
    assert resolve_effective_sync_area_id_from_parts(
        "Красноярский край",
        1,
        sa_by_id,
        year=2024,
        res_name="ЭС г. Норильска Красноярского края",
    ) == 0
    station_kras = SimpleNamespace(
        regional_district=SimpleNamespace(
            name="Красноярский край",
            id_synchronous_area=1,
        ),
        regional_energy_system_obj=SimpleNamespace(
            name="ЭС г. Норильска Красноярского края",
            union_energy_system=SimpleNamespace(name="ТИТЭС Сибири"),
        ),
        energy_unit=SimpleNamespace(
            name="Таймырский Долгано-Ненецкий муниципальный район, Туруханский район и городской округ г. Норильск Красноярского края"
        ),
    )
    assert resolve_effective_sync_area_id(station_kras, sa_by_id, current_year=2024) == 0


def _agg_row(**kwargs):
    defaults = dict(
        energy_unit_id=1,
        regional_district_id=1,
        federal_district_id=1,
        regional_energy_system_id=1,
        union_energy_system_id=1,
        energy_system_type_id=1,
        synchronous_area_id=1,
        regional_district_name="",
        regional_energy_system_name="",
        union_energy_system_name="",
        energy_unit_name="",
        station_type_id=1,
        tes_type_id=1,
        tes_machine_type_id=1,
        fuel_type_id=1,
        year=2024,
        p_ust=Decimal("10"),
        p_ogr=Decimal("0"),
        p_rasp=Decimal("10"),
        database_version_id=1,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


@patch(
    "app.generation.services.station_services.station_access_services.get_decentralized_zone_res_ids",
    return_value=set(),
)
@patch(
    "app.generation.services.station_services.station_access_services.get_decentralized_zone_energy_system_type_id",
    return_value=None,
)
@patch(
    "app.common.services.get_services.energy_systems.synchronous_area_get_services.get_synchronous_area_list_full",
)
def test_aggregate_all_at_once_applies_kaliningrad_and_taimyr_sa_rules(mock_sa_list, _dz_est, _dz_res):
    from app.generation.services.station_services.aggregation_station_services.optimized_aggregation import (
        aggregate_all_at_once,
    )

    first = SimpleNamespace(id=1, name="1-ая СЗ", number="1")
    kali = SimpleNamespace(id=10, name="Калининградская СЗ", number="")
    mock_sa_list.return_value = [first, kali]

    rows = [
        _agg_row(
            year=2024,
            p_ust=Decimal("100"),
            synchronous_area_id=10,
            regional_district_name="Калининградская область",
        ),
        _agg_row(
            year=2025,
            p_ust=Decimal("100"),
            synchronous_area_id=10,
            regional_district_name="Калининградская область",
        ),
        _agg_row(
            year=2024,
            p_ust=Decimal("50"),
            synchronous_area_id=1,
            regional_district_name="Красноярский край",
            regional_energy_system_name="ЭС г. Норильска Красноярского края",
            union_energy_system_name="ТИТЭС Сибири",
        ),
        _agg_row(
            year=2024,
            p_ust=Decimal("20"),
            synchronous_area_id=1,
            regional_district_name="Московская область",
        ),
    ]
    data = aggregate_all_at_once(rows)
    sa_ust = data["aggregate_power_by_synchronous_areas"]["aggregated"]["p_ust"]
    assert sa_ust[1][2024] == Decimal("120")
    assert 2025 not in sa_ust[1]
    assert sa_ust[10][2025] == Decimal("100")
    assert 2024 not in sa_ust.get(10, {})
    assert 0 not in sa_ust


# --- УМ > 100 МВт filter ---


def test_um_gt_100_filter_wired_in_extract_and_template():
    from pathlib import Path

    filt = Path("app/generation/services/station_services/filters_services.py").read_text(encoding="utf-8")
    svc = Path("app/generation/services/station_services/station_services.py").read_text(encoding="utf-8")
    tmpl = Path("app/templates/generation/stations/station_filters_third_row.html").read_text(encoding="utf-8")
    assert '"um_gt_100": args.get("um_gt_100", "0") == "1"' in filt
    assert 'filters.get("um_gt_100")' in svc
    assert "sum(MachinePower.p_ust)" in svc or "func.sum(MachinePower.p_ust)" in svc
    assert 'id="um_gt_100_switch"' in tmpl
    assert "Станции &gt; 100 МВт" in tmpl
    assert "um_gt_100_switch" in Path("app/static/js/generation/stations/station_page_logic.js").read_text(encoding="utf-8")


def test_tes_type_filter_uses_year_range_on_station_list():
    from pathlib import Path

    svc = Path("app/generation/services/station_services/station_services.py").read_text(encoding="utf-8")
    # Основной отбор станций — between по диапазону, не только current_year
    assert "MachineTesType.year_number.between(_sy, _ey)" in svc
    filt = Path("app/generation/services/station_services/filters_services.py").read_text(encoding="utf-8")
    assert "MachineTesType.year_number.between(_sy, _ey)" in filt


def test_update_hidden_fields_preserves_year_filter_intersection():
    from pathlib import Path

    js = Path("app/static/js/generation/stations/station_page_logic.js").read_text(encoding="utf-8")
    assert "updateHiddenFields" in js
    assert "data-year-filter" in Path(
        "app/templates/generation/stations/station_filters_third_row.html"
    ).read_text(encoding="utf-8")
    assert "y < startY || y > endY" in js


def test_des_dga_keep_fuel_breakdown_in_totals_summary():
    from pathlib import Path

    text = Path("app/generation/routes/totals_summary_routes.py").read_text(encoding="utf-8")
    assert "ДЭС" in text
    assert "ДГА" in text
    assert "_tes_type_skips_fuel_breakdown" in text


def test_apply_machine_display_names_plan_and_fact_relabing_logic():
    """Контракт формата «до (после)» для плана и факт-перемаркировки."""
    from pathlib import Path

    from app.generation.services.station_services.station_services import (
        _split_display_name_before_after,
    )

    src = Path("app/generation/services/station_services/station_services.py").read_text(encoding="utf-8")
    assert 'display_name = f"{base_name} ({plan_name})"' in src
    assert "date_relabing_fact" in src
    assert 'display_name = f"{before_name} ({after_name})"' in src
    assert 'display_name_before = base_name' in src
    assert 'display_name_after = plan_name' in src
    assert 'setattr(m, "display_name_before", display_name_before)' in src
    assert 'setattr(m, "display_name_after", display_name_after)' in src
    assert "_split_display_name_before_after" in src

    # Логика формата (без ORM)
    base_name, plan_name = "ТГ-1", "ТГ-1М"
    assert f"{base_name} ({plan_name})" == "ТГ-1 (ТГ-1М)"
    before_name, after_name = "ПТ-10", "ПТ-12"
    assert f"{before_name} ({after_name})" == "ПТ-10 (ПТ-12)"

    # Готовая строка «до (после)» в machine_name / MachineName
    assert _split_display_name_before_after("РО-230/989-В-450 (РО 230-450)") == (
        "РО-230/989-В-450",
        "РО 230-450",
    )
    assert _split_display_name_before_after("К(ПЛ)-510-ВБ-900 (ПЛ20-В-900)") == (
        "К(ПЛ)-510-ВБ-900",
        "ПЛ20-В-900",
    )
    assert _split_display_name_before_after("ТГ-1") == (None, None)

    rows = Path("app/templates/generation/stations/station_rows.html").read_text(encoding="utf-8")
    assert "machine.display_name or machine.machine_name" in rows
    ch_rows = Path("app/templates/generation/station_changes/station_changes_rows.html").read_text(
        encoding="utf-8"
    )
    assert "machine.display_name" in ch_rows
    assert "display_name_before" in ch_rows
    assert "display_name_after" in ch_rows
    assert "_split_tes_name" in ch_rows


def test_station_changes_rows_split_tes_name_on_modernization():
    """До/после модернизации разносится в «Тип агрегата», не в «Тип агрегата ТЭС»."""
    from pathlib import Path

    text = Path("app/templates/generation/station_changes/station_changes_rows.html").read_text(
        encoding="utf-8"
    )
    tes_block = text.split("Тип агрегата ТЭС")[1]
    assert "machine.tes_machine_type.name" in tes_block
    assert "display_name_before" not in tes_block
    assert "machine.display_name" not in tes_block
