from decimal import Decimal

import pytest

from app.rational_structure.services.technical_characteristic_matching import MachineMatcher


@pytest.fixture(autouse=True)
def _patch_infrastructure():
    # Matcher не использует БД; отключаем общую инфраструктурную fixture tests/conftest.py.
    yield


def candidate(**changes):
    return {
        "machine_id": 7, "station_id": 3,
        "subject_name": 'ПАО "Энергия"', "station_name": "Березовская ТЭЦ-1",
        "station_number": "1", "equipment_brand": "ПТ-60",
        "installed_electric_power": Decimal("60"), **changes,
    }


def assert_status(result, status):
    assert set(result) == {"machine_id", "pgu_machine_id", "match_status", "match_details"}
    assert result["match_status"] == status
    if status != "matched":
        assert result["machine_id"] is None
    details = result["match_details"]
    assert set(details) == {"reason", "differing_fields", "candidates"}
    assert details["reason"]
    assert len(details["candidates"]) <= 3
    for item in details["candidates"]:
        assert set(item) == {
            "machine_id", "pgu_machine_id", "station_id", "station_name", "station_number",
            "equipment_brand", "installed_electric_power", "score", "differences",
        }
        assert type(item["score"]) is int and 0 <= item["score"] <= 100
        for difference in item["differences"]:
            assert set(difference) == {"field", "label", "source", "target"}
            assert all(isinstance(value, str) for value in difference.values())


@pytest.mark.parametrize("number", ["№ 01", "ст. №1", "1.0", "１", "1,00", '«№ 01»'])
def test_safe_normalization_and_repeated_matching(number):
    matcher = MachineMatcher([candidate()])
    record = candidate(subject_name="АО «ЭНЕРГИЯ»", station_name="березовская тэц 1",
                       station_number=number, equipment_brand="ПT–60")
    first = matcher.match(record)
    assert_status(first, "matched")
    assert first["machine_id"] == 7
    assert first["match_details"]["differing_fields"] == []
    assert first["match_details"]["candidates"][0]["differences"] == []
    assert matcher.match(record) == first


@pytest.mark.parametrize("field,source,target", [
    ("equipment_brand", "ПТ-60", "PT-60"),
    ("installed_electric_power", Decimal("60"), Decimal("61")),
])
def test_different_required_fields_never_auto_assign(field, source, target):
    """Различия в обязательных полях (марка, мощность) дают partial."""
    result = MachineMatcher([candidate(**{field: target})]).match(candidate(**{field: source}))
    assert_status(result, "partial")
    assert field in result["match_details"]["differing_fields"]


@pytest.mark.parametrize("source,target", [
    ("ПТ-60-12", "ПТ-6012"),
    ("ПТ-60/12", "ПТ-6012"),
])
def test_brand_separator_variations_match(source, target):
    result = MachineMatcher([candidate(equipment_brand=target)]).match(candidate(equipment_brand=source))
    assert_status(result, "matched")
    assert result["machine_id"] == 7


@pytest.mark.parametrize("excel,db", [
    ("Т-100/120-130", "Т-100-130"),
    ("ПТ-60-90/13/1,2", "ПТ-60-90/13"),
    ("АПТ-12-29", "АПТ-12-1"),
    ("Т-100/120-130-2", "Т-100/120-130-3"),
])
def test_brand_tail_difference_matches(excel, db):
    result = MachineMatcher([candidate(equipment_brand=db)]).match(candidate(equipment_brand=excel))
    assert_status(result, "matched")
    assert result["machine_id"] == 7


def test_brand_tail_difference_keeps_ambiguity_with_several_candidates():
    matcher = MachineMatcher([
        candidate(machine_id=1, equipment_brand="Т-100-130"),
        candidate(machine_id=2, equipment_brand="Т-100-131"),
    ])
    result = matcher.match(candidate(equipment_brand="Т-100-130"))
    assert_status(result, "ambiguous")


def test_different_station_name_is_unmatched():
    """Полностью разное название станции дает unmatched (similarity < 0.85)."""
    result = MachineMatcher([candidate(station_name="Березовская ТЭЦ-2")]).match(
        candidate(station_name="Березовская ТЭЦ-1"))
    assert_status(result, "unmatched")


@pytest.mark.parametrize("db_station,excel_station", [
    ("Автовская ТЭЦ (ТЭЦ-15)", "Автовская ТЭЦ"),
    ("Автовская ТЭЦ", "Автовская ТЭЦ (ТЭЦ-15)"),
])
def test_station_parenthesis_suffix_matches(db_station, excel_station):
    result = MachineMatcher([candidate(station_name=db_station)]).match(
        candidate(station_name=excel_station))
    assert_status(result, "matched")
    assert result["machine_id"] == 7


@pytest.mark.parametrize("delta,status", [
    ("0", "matched"), ("0.000001", "matched"), ("-0.000001", "matched"),
    ("0.0000011", "matched"), ("0.2", "matched"),
    ("0.4", "partial"), ("0.5", "partial"), ("-0.5", "partial"),
])
def test_power_tolerance(delta, status):
    result = MachineMatcher([candidate()]).match(
        candidate(installed_electric_power=Decimal("60") + Decimal(delta)))
    assert_status(result, status)
    if status == "partial":
        assert result["match_details"]["differing_fields"] == ["installed_electric_power"]


def test_small_power_rounding_difference_is_matched():
    matcher = MachineMatcher([candidate(installed_electric_power=Decimal("44.422"))])
    result = matcher.match(candidate(installed_electric_power=Decimal("44.4")))
    assert_status(result, "matched")
    assert result["machine_id"] == 7


def test_power_difference_display_preserves_fraction():
    result = MachineMatcher([candidate()]).match(candidate(installed_electric_power=Decimal("60.400002")))
    difference = result["match_details"]["candidates"][0]["differences"][0]
    assert difference["source"] == "60,400002"
    assert difference["target"] == "60"


@pytest.mark.parametrize("field", ["equipment_brand", "installed_electric_power"])
@pytest.mark.parametrize("missing_side", ["source", "target", "both"])
def test_missing_required_fields_are_not_exact(field, missing_side):
    source, target = candidate(), candidate()
    if missing_side in ("source", "both"):
        source[field] = None
    if missing_side in ("target", "both"):
        target[field] = None
    result = MachineMatcher([target]).match(source)
    assert_status(result, "partial")
    assert field in result["match_details"]["differing_fields"]


@pytest.mark.parametrize("missing_side", ["source", "target", "both"])
def test_missing_station_number_is_ignored_for_matched(missing_side):
    """Станционный номер игнорируется при определении полного совпадения."""
    source, target = candidate(), candidate()
    if missing_side in ("source", "both"):
        source["station_number"] = None
    if missing_side in ("target", "both"):
        target["station_number"] = None
    result = MachineMatcher([target]).match(source)
    assert_status(result, "matched")
    assert "station_number" not in result["match_details"]["differing_fields"]


@pytest.mark.parametrize("missing_side", ["source", "target", "both"])
def test_missing_subject_name_is_ignored_for_matched(missing_side):
    """Субъект ЭЭ игнорируется при определении полного совпадения."""
    source, target = candidate(), candidate()
    if missing_side in ("source", "both"):
        source["subject_name"] = None
    if missing_side in ("target", "both"):
        target["subject_name"] = None
    result = MachineMatcher([target]).match(source)
    assert_status(result, "matched")
    assert "subject_name" not in result["match_details"]["differing_fields"]


def test_zero_power_is_present_but_not_missing():
    matcher = MachineMatcher([candidate(installed_electric_power=Decimal("0"))])
    assert_status(matcher.match(candidate(installed_electric_power=Decimal("0"))), "matched")
    assert_status(matcher.match(candidate(installed_electric_power=None)), "partial")


def test_multiple_exact_candidates_and_limit():
    result = MachineMatcher([candidate(machine_id=value) for value in range(5)]).match(candidate())
    assert_status(result, "ambiguous")
    assert [item["machine_id"] for item in result["match_details"]["candidates"]] == [0, 1, 2]
    assert result["match_details"]["differing_fields"] == []


def test_station_number_breaks_ambiguity_when_unique():
    candidates = [
        candidate(machine_id=1, station_number="9"),
        candidate(machine_id=2, station_number="10"),
        candidate(machine_id=3, station_number="11"),
    ]
    result = MachineMatcher(candidates).match(candidate(station_number="9"))
    assert_status(result, "matched")
    assert result["machine_id"] == 1


def test_station_number_keeps_ambiguity_when_not_unique():
    candidates = [
        candidate(machine_id=1, station_number="9"),
        candidate(machine_id=2, station_number="9"),
        candidate(machine_id=3, station_number="11"),
    ]
    result = MachineMatcher(candidates).match(candidate(station_number="9"))
    assert_status(result, "ambiguous")


def test_close_scores_are_ambiguous_but_unique_exact_wins():
    matcher = MachineMatcher([candidate(), candidate(machine_id=8, installed_electric_power=Decimal("61"))])
    assert_status(matcher.match(candidate(installed_electric_power=Decimal("60.5"))), "ambiguous")
    assert_status(matcher.match(candidate()), "matched")


@pytest.mark.parametrize("record", [
    candidate(station_name="Дальняя ГЭС"),
    candidate(station_name="Березовская ТЭЦ-11"),
    candidate(station_name=None),
    candidate(station_name=""),
    candidate(station_number="11", equipment_brand="ГТ-120"),
    candidate(station_number=None, equipment_brand=None),
    {},
])
def test_no_reasonable_candidates(record):
    result = MachineMatcher([candidate()]).match(record)
    assert_status(result, "unmatched")
    assert result["match_details"]["candidates"] == []


def test_empty_candidate_list():
    assert_status(MachineMatcher([]).match(candidate()), "unmatched")


def test_fuzzy_station_requires_machine_evidence():
    matcher = MachineMatcher([candidate()])
    assert_status(matcher.match(candidate(station_name="Березовкая ТЭЦ-1")), "partial")
    assert_status(matcher.match(candidate(station_name="Березовкая ТЭЦ-1", station_number="2",
                                          equipment_brand="ГТ-120")), "unmatched")


def test_exact_station_is_preferred_to_fuzzy_station():
    matcher = MachineMatcher([
        candidate(station_number="2", equipment_brand="ГТ-120"),
        candidate(machine_id=8, station_id=4, station_name="Березовкая ТЭЦ-1"),
    ])
    # Теперь для unmatched ищем похожие станции, поэтому может быть partial
    assert_status(matcher.match(candidate()), "partial")


def test_blank_and_punctuation_only_text_is_not_exact():
    result = MachineMatcher([candidate(equipment_brand=' « » ')]).match(candidate(equipment_brand=""))
    assert_status(result, "partial")
