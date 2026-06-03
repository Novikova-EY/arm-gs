from collections import defaultdict
from decimal import Decimal

import pytest

from app.energy_consumption.services import energy_consumption_summary_import_services as service


@pytest.mark.parametrize(
    ("raw_label", "expected"),
    [
        ("ЕЭС России сНТ сзарядом ГАЭС", "ЕЭС России с НТ с зарядом ГАЭС"),
        ("ЕЭС России безНТ с зарядом ГАЭС", "ЕЭС России без НТ с зарядом ГАЭС"),
        ("ОЭС Юга безНТ сГАЭС", "ОЭС Юга без НТ с ГАЭС"),
    ],
)
def test_normalize_import_label_typos_expands_compact_variant_suffixes(
    raw_label,
    expected,
):
    assert service._normalize_import_label_typos(raw_label) == expected


def test_normalize_russia_federation_import_variant_maps_bare_russia_to_without_nt():
    assert (
        service._normalize_russia_federation_import_perimeter_variant("Россия", "with_nt")
        == service.CODE_WITHOUT_NT
    )
    assert (
        service._normalize_russia_federation_import_perimeter_variant("Россия", None)
        == service.CODE_WITHOUT_NT
    )
    assert (
        service._normalize_russia_federation_import_perimeter_variant("Россия с НТ", "with_nt")
        == service.CODE_WITH_NT
    )


def test_aggregate_sheet_labels_russia_with_nt_column_writes_without_nt_variant(
    monkeypatch,
):
    """Шаблон «Для работы в АРМе»: «Россия» + with_nt в колонке → without_nt в аккумуляторе."""
    monkeypatch.setattr(service, "_aggregate_model_requires_perimeter_variant", lambda _model: True)
    matrix = [
        ("perimeter-variants", "Наименование", 2026, 2027),
        ("with_nt", "Россия", 1078.411, 1089.105),
        ("", "Россия", 1078.411, 1089.105),
    ]
    acc, variant_column_mode = service._aggregate_sheet_labels(
        matrix, sheet_title="млн. кВт.ч"
    )
    assert variant_column_mode is True
    assert acc[("Россия", 2026, service.CODE_WITHOUT_NT)] == Decimal("1078.411")
    assert acc[("Россия", 2027, service.CODE_WITHOUT_NT)] == Decimal("1089.105")
    assert ("Россия", 2026, "with_nt") not in acc


@pytest.mark.parametrize(
    ("label", "variant_code"),
    [
        ("ЕЭС России сНТ с зарядом ГАЭС", service.CODE_WITH_NT_WITH_GAES),
        ("ЕЭС России безНТ с зарядом ГАЭС", service.CODE_WITHOUT_NT_WITH_GAES),
    ],
)
def test_resolve_aggregate_binding_accepts_compact_ees_russia_labels(
    monkeypatch,
    label,
    variant_code,
):
    monkeypatch.setattr(service, "_aggregate_model_requires_perimeter_variant", lambda _model: True)

    bind = service._resolve_aggregate_energy_consumption_binding(
        label,
        perimeter_variant_code=variant_code,
        variant_column_mode=True,
    )

    assert bind is not None
    assert bind.demand_model is service.EesRussiaEnergyConsumptionParameter
    assert bind.perimeter_variant_code == variant_code


def test_aggregate_sheet_labels_skips_kaliningrad_sync_zone_in_variant_column_mode():
    """СЗ Калининграда — расчётная строка; без кода варианта не должна попадать в импорт."""
    matrix = [
        ("perimeter-variants", "Наименование", 2024, 2025),
        ("", "Синхронная зона Калининградской области", 100, 5141),
    ]
    acc, variant_column_mode = service._aggregate_sheet_labels(matrix, sheet_title="СиПР")
    assert variant_column_mode is True
    assert len(acc) == 0


def test_aggregate_sheet_labels_skips_duplicate_row_without_variant_when_explicit_exists():
    """Две строки с одним наименованием: без варианта и с o1 — берётся только явный вариант."""
    matrix = [
        ("perimeter-variants", "Наименование", 2024, 2025),
        ("", "ЭС Камчатского края", 100, 110),
        ("o1", "ЭС Камчатского края", 200, 210),
    ]
    acc, variant_column_mode = service._aggregate_sheet_labels(matrix, sheet_title="СиПР")
    assert variant_column_mode is True
    assert acc[("ЭС Камчатского края", 2024, "o1")] == Decimal("200")
    assert ("ЭС Камчатского края", 2024, None) not in acc


def test_aggregate_sheet_labels_imports_none_variant_row_when_o1_row_is_zero_placeholder():
    """Шаблон «млн. кВт.ч»: данные в строке без варианта, o1 — нулевая заглушка."""
    matrix = [
        ("perimeter-variants", "Наименование", 2026, 2027),
        ("", "ЭС Камчатского края", 1822, 1925),
        ("o1", "ЭС Камчатского края", 0, 0),
    ]
    acc, variant_column_mode = service._aggregate_sheet_labels(
        matrix, sheet_title="млн. кВт.ч"
    )
    assert variant_column_mode is True
    assert acc[("ЭС Камчатского края", 2026, None)] == Decimal("1822")
    assert acc[("ЭС Камчатского края", 2027, None)] == Decimal("1925")
    assert ("ЭС Камчатского края", 2026, "o1") not in acc


def test_aggregate_sheet_labels_merges_none_and_o1_rows_per_year():
    """По годам: ненулевой o1 приоритетнее; при нулевом o1 берётся строка без варианта."""
    matrix = [
        ("perimeter-variants", "Наименование", 2025, 2026),
        ("", "ЭС Камчатского края", 1727, 1822),
        ("o1", "ЭС Камчатского края", 1899, 0),
    ]
    acc, variant_column_mode = service._aggregate_sheet_labels(
        matrix, sheet_title="млн. кВт.ч"
    )
    assert variant_column_mode is True
    assert acc[("ЭС Камчатского края", 2025, "o1")] == Decimal("1899")
    assert ("ЭС Камчатского края", 2025, None) not in acc
    assert acc[("ЭС Камчатского края", 2026, None)] == Decimal("1822")


def test_aggregate_from_screen_export_matrix_reads_mln_and_sipr_rows():
    matrix = [
        ("Энергосистема", "Наименование параметров", 2024, 2025),
        ("Россия", "Потребление электрической энергии, млн кВт·ч", 10, 20),
        ("", "Потребление электрической энергии (СиПР), млн кВт·ч", 1, 2),
        ("", "Годовой темп прироста, %", 5, 6),
    ]
    acc_mln, acc_sipr = service._aggregate_from_screen_export_matrix(matrix)
    assert acc_mln[("Россия", 2024, None)] == Decimal("10")
    assert acc_mln[("Россия", 2025, None)] == Decimal("20")
    assert acc_sipr[("Россия", 2024, None)] == Decimal("1")
    assert acc_sipr[("Россия", 2025, None)] == Decimal("2")
    assert not any(k[0] == "Годовой темп прироста, %" for k in acc_mln)


def test_collapse_labels_preserves_none_variant_when_variant_column_mode(monkeypatch):
    """Строка Excel без варианта не подменяется на единственный О-1 при свёртке."""
    monkeypatch.setattr(
        service,
        "_resolve_row_binding",
        lambda label, ctx, **kwargs: service._ImportBind(
            service.RegionalEnergySystemEnergyConsumptionParameter,
            service._MODEL_FK[service.RegionalEnergySystemEnergyConsumptionParameter],
            601,
            kwargs.get("perimeter_variant_code"),
        )
        if label == "ЭС Магаданской области"
        else None,
    )
    acc_labels: defaultdict[tuple[str, int, str | None], Decimal] = defaultdict(
        lambda: Decimal("0"),
        {("ЭС Магаданской области", 2026, None): Decimal("3302")},
    )
    acc, _ = service._collapse_labels_to_bind_keys(
        acc_labels,
        ctx={},
        years_ok={2026},
        variant_column_mode=True,
    )
    key = (
        service.RegionalEnergySystemEnergyConsumptionParameter,
        service._MODEL_FK[service.RegionalEnergySystemEnergyConsumptionParameter],
        601,
        2026,
        None,
    )
    assert acc[key] == Decimal("3302")


def test_resolve_row_binding_never_binds_kaliningrad_sync_zone():
    ctx = {"sync_area": [(type("SA", (), {"id": 41})(), "Синхронная зона Калининградской области")]}
    bind = service._resolve_row_binding(
        "Синхронная зона Калининградской области",
        ctx,
        perimeter_variant_code=None,
        variant_column_mode=True,
    )
    assert bind is None
