from decimal import Decimal
from functools import lru_cache
from types import SimpleNamespace

import pytest
from flask import Flask, g

from app.energy_consumption.services import energy_consumption_summary_import_services as importer
from app.energy_consumption.services import energy_consumption_summary_services as summary


VARIANTS = {
    importer.CODE_WITHOUT_NT_WITHOUT_GAES: Decimal("100"),
    importer.CODE_WITHOUT_NT_WITH_GAES: Decimal("112"),
    importer.CODE_WITH_NT_WITHOUT_GAES: Decimal("120"),
    importer.CODE_WITH_NT_WITH_GAES: Decimal("132"),
}
YEARS = list(range(2021, 2026))
FIELDS = ("energy_consumption_mln_kvt_ch", "energy_consumption_sipr_mln_kvt_ch")
MODEL = importer.EnergySystemTypeEnergyConsumptionParameter
FK = "id_energy_system_type"


def _mock_components(monkeypatch, charges=True, nt=True):
    @lru_cache(maxsize=8)
    def station_values(version, model, fk, parent, years):
        assert version == g.current_db_version == 7
        assert (model, fk, parent) == (MODEL.__name__, FK, 72)
        return (
            (1, "GAES A", tuple((year, Decimal("8")) for year in years)),
            (2, "GAES B", tuple((year, Decimal("4")) for year in years)),
        ) if charges else ()

    def nt_values(years, field):
        assert g.current_db_version == 7
        assert field in FIELDS
        return {year: Decimal("20") for year in years} if nt else {}

    monkeypatch.setattr(summary, "_gaes_charge_raw_station_values_for_entity", station_values)
    monkeypatch.setattr(summary, "_new_territories_parameter_year_values", nt_values)


@pytest.mark.parametrize("source", VARIANTS)
@pytest.mark.parametrize("field", FIELDS)
def test_each_explicit_perimeter_completes_other_three_without_repeated_charge(
    monkeypatch, source, field
):
    _mock_components(monkeypatch)
    explicit = {(MODEL, FK, 72, year, source): VARIANTS[source] for year in YEARS}
    with Flask(__name__).app_context():
        g.current_db_version = 99
        related = importer._ees_unified_adjacent_import_values(
            explicit, parent_id=72, database_version_id=7, field_name=field
        )
        assert g.current_db_version == 99
        assert not (related.keys() & explicit.keys())
        combined = {**explicit, **related}
        assert combined == {
            (MODEL, FK, 72, year, code): value
            for year in YEARS for code, value in VARIANTS.items()
        }
        # A repeated import must use the source again, not add charge to a stored result.
        assert importer._ees_unified_adjacent_import_values(
            explicit, parent_id=72, database_version_id=7, field_name=field
        ) == related


def test_explicit_values_win_even_when_both_charge_perimeters_are_in_file(monkeypatch):
    _mock_components(monkeypatch)
    explicit = {
        (MODEL, FK, 72, 2024, importer.CODE_WITHOUT_NT_WITH_GAES): Decimal("112"),
        (MODEL, FK, 72, 2024, importer.CODE_WITHOUT_NT_WITHOUT_GAES): Decimal("99"),
        (importer.EesRussiaEnergyConsumptionParameter, importer._FK_AGGREGATE_NO_PARENT,
         0, 2024, importer.CODE_WITHOUT_NT_WITH_GAES): Decimal("500"),
    }
    with Flask(__name__).app_context():
        related = importer._ees_unified_adjacent_import_values(
            explicit, parent_id=72, database_version_id=7, field_name=FIELDS[0]
        )
        assert not hasattr(g, "current_db_version")
    assert not (related.keys() & explicit.keys())
    assert all(key[0] is MODEL for key in related)
    assert related[(MODEL, FK, 72, 2024, importer.CODE_WITH_NT_WITH_GAES)] == Decimal("132")
    assert related[(MODEL, FK, 72, 2024, importer.CODE_WITH_NT_WITHOUT_GAES)] == Decimal("119")


@pytest.mark.parametrize("charges,nt,expected", [
    (False, False, {}),
    (False, True, {importer.CODE_WITH_NT_WITHOUT_GAES: Decimal("120")}),
    (True, False, {importer.CODE_WITHOUT_NT_WITH_GAES: Decimal("112")}),
])
def test_missing_components_do_not_turn_into_zero(monkeypatch, charges, nt, expected):
    _mock_components(monkeypatch, charges=charges, nt=nt)
    with Flask(__name__).app_context():
        related = importer._ees_unified_adjacent_import_values(
            {(MODEL, FK, 72, 2024, importer.CODE_WITHOUT_NT_WITHOUT_GAES): Decimal("100")},
            parent_id=72, database_version_id=7, field_name=FIELDS[0],
        )
    assert related == {(MODEL, FK, 72, 2024, code): value for code, value in expected.items()}


@pytest.mark.parametrize("source", VARIANTS)
def test_xlsx_import_writes_adjacent_perimeters_and_protects_them_from_formula_overwrite(
    monkeypatch, source
):
    from io import BytesIO
    from openpyxl import Workbook

    from app.common.perimeter_variant import registry
    from app.energy_consumption.services import ec_display_cache

    _mock_components(monkeypatch)
    monkeypatch.setattr(ec_display_cache, "invalidate_energy_consumption_display_caches",
                        lambda **kwargs: None)
    monkeypatch.setattr(registry, "_catalog", lambda: SimpleNamespace(variants_by_code=VARIANTS))
    book = Workbook()
    book.remove(book.active)
    for sheet in (importer.SHEET_MLN_KVTCH, importer.SHEET_SIPR):
        ws = book.create_sheet(sheet)
        ws.append(["perimeter-variants", "Наименование", *YEARS])
        # The explicit code wins over a contradictory label suffix.
        ws.append([source, "ЕЭС России с НТ с зарядом ГАЭС", *[VARIANTS[source]] * len(YEARS)])
    stream = BytesIO()
    book.save(stream)
    ctx = {"energy_system_type": [(SimpleNamespace(id=72), "ЕЭС России")]}
    monkeypatch.setattr(importer, "_binding_ctx", lambda vid: ctx)
    monkeypatch.setattr(importer, "_year_numbers_for_version", lambda vid: set(YEARS))
    monkeypatch.setattr(importer, "_aggregate_model_requires_perimeter_variant", lambda model: True)
    monkeypatch.setattr(importer, "_import_perimeter_variant_without_entity_bindings",
                        lambda model, fk, parent, code: code)
    monkeypatch.setattr(importer, "_mirror_res_accumulator_rows_to_single_district_rd",
                        lambda *args, **kwargs: None)
    monkeypatch.setattr(importer.db.session, "is_active", True, raising=False)
    saved = {}

    def write(acc, *, field_name, version_id, **kwargs):
        assert version_id == 7
        saved.setdefault(field_name, {}).update(acc)
        return len(acc)

    monkeypatch.setattr(importer, "_apply_accumulator_for_version", write)
    formula_calls = []

    def persist(*, database_version_id, years, skip_accumulator_keys_by_field, **kwargs):
        assert database_version_id == 7
        for field in FIELDS:
            expected = {(MODEL, FK, 72, year, code): value
                        for year in YEARS for code, value in VARIANTS.items()}
            assert saved[field] == expected
            assert skip_accumulator_keys_by_field[field] == frozenset(expected)
        formula_calls.append(database_version_id)
        return 0

    monkeypatch.setattr(importer, "persist_all_energy_consumption_summary_computed_rows", persist)
    with Flask(__name__).app_context():
        stats = importer._import_energy_consumption_summary_from_xlsx_bytes_impl(
            stream.getvalue(), version_ids=[7], import_user="test", on_version_progress=None
        )
    assert formula_calls == [7]
    assert stats["cells_written_formula"] == 3 * len(YEARS) * len(FIELDS)
    assert stats["unmatched_labels_mln"] == []
    assert stats["unmatched_labels_sipr"] == []


@pytest.mark.parametrize("code", [importer.CODE_WITH_NT, importer.CODE_WITHOUT_NT])
def test_sparse_ees_row_keeps_explicit_perimeter_without_guessing_gaes(monkeypatch, code):
    from app.common.perimeter_variant import registry

    monkeypatch.setattr(registry, "_catalog", lambda: SimpleNamespace(variants_by_code={code: None}))
    monkeypatch.setattr(importer, "_aggregate_model_requires_perimeter_variant", lambda model: True)
    values, variant_mode = importer._aggregate_sheet_labels([
        ("perimeter-variants", "Наименование", 2021, 2024, 2025),
        (code, "ЕЭС России с зарядом ГАЭС", None, 100, 110),
    ])
    assert variant_mode
    assert dict(values) == {
        ("ЕЭС России с зарядом ГАЭС", 2024, code): Decimal("100"),
        ("ЕЭС России с зарядом ГАЭС", 2025, code): Decimal("110"),
    }


def test_zero_charge_is_a_known_value_not_missing(monkeypatch):
    _mock_components(monkeypatch, nt=False)
    monkeypatch.setattr(summary, "_gaes_charge_raw_station_values_for_entity",
                        lambda *args: ((1, "GAES", ((2024, Decimal(0)),)),))
    with Flask(__name__).app_context():
        related = importer._ees_unified_adjacent_import_values(
            {(MODEL, FK, 72, 2024, importer.CODE_WITHOUT_NT_WITHOUT_GAES): Decimal("100")},
            parent_id=72, database_version_id=7, field_name=FIELDS[0],
        )
    assert related == {(MODEL, FK, 72, 2024, importer.CODE_WITHOUT_NT_WITH_GAES): Decimal("100")}


def test_version_context_restored_when_component_lookup_fails(monkeypatch):
    def fail(*args):
        raise RuntimeError("component query failed")

    monkeypatch.setattr(summary, "_gaes_charge_raw_station_values_for_entity", fail)
    with Flask(__name__).app_context():
        g.current_db_version = 99
        with pytest.raises(RuntimeError, match="component query failed"):
            importer._ees_unified_adjacent_import_values(
                {(MODEL, FK, 72, 2024, importer.CODE_WITHOUT_NT_WITH_GAES): Decimal("112")},
                parent_id=72, database_version_id=7, field_name=FIELDS[0],
            )
        assert g.current_db_version == 99


@pytest.mark.parametrize("source", VARIANTS)
def test_completed_import_stays_correct_on_screen_and_formula_persistence(monkeypatch, source):
    _mock_components(monkeypatch)
    explicit = {(MODEL, FK, 72, year, source): VARIANTS[source] for year in YEARS}
    with Flask(__name__).app_context():
        values = {**explicit, **importer._ees_unified_adjacent_import_values(
            explicit, parent_id=72, database_version_id=7, field_name=FIELDS[0]
        )}
    base = {
        "entity_label": "ЕЭС России",
        "entity_rowspan": 1,
        "show_entity_cell": True,
        "entity_kind": "perimeter_variant",
        "pd_ec_skip_perimeter_variant_year_bounds": True,
        "demand_model_name": MODEL.__name__,
        "parent_fk_column": FK,
        "parent_id": 72,
        "parameter_key": FIELDS[0],
    }
    rows = []
    for nt_group in ("without_nt", "with_nt"):
        for code in (nt_group + "_with_gaes", nt_group + "_without_gaes"):
            numeric = [str(values[(MODEL, FK, 72, year, code)]) for year in YEARS]
            rows.append({**base, "perimeter_variant_code": code,
                         "year_values": numeric, "year_numeric_tooltips": list(numeric)})
        rows.append({
            **base,
            "entity_kind": "group",
            "parameter_key": summary.GAES_CHARGE_PARAMETER_KEY,
            "perimeter_variant_code": None,
            "gaes_charge_row_station_name": "всего",
            "pd_ec_nt_extra_row": nt_group == "with_nt",
            "pd_ec_nt_without_row": nt_group == "without_nt",
            "year_values": ["12"] * len(YEARS),
            "year_numeric_tooltips": ["12"] * len(YEARS),
        })
    for _ in range(2):
        summary.apply_gaes_without_charge_formula_to_summary_rows(rows, YEARS, 1)
        for row in rows:
            code = row["perimeter_variant_code"]
            if code in VARIANTS:
                assert summary._raw_year_values_from_summary_row(row, YEARS) == {
                    year: VARIANTS[code] for year in YEARS
                }
    persisted = importer._accumulator_from_formula_summary_rows(rows, YEARS, field_name=FIELDS[0])
    assert persisted == {
        (MODEL, FK, 72, year, code): value
        for code, value in VARIANTS.items() if "without_gaes" in code
        for year in YEARS
    }
