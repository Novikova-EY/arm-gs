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


def test_resolve_row_binding_never_binds_kaliningrad_sync_zone():
    ctx = {"sync_area": [(type("SA", (), {"id": 41})(), "Синхронная зона Калининградской области")]}
    bind = service._resolve_row_binding(
        "Синхронная зона Калининградской области",
        ctx,
        perimeter_variant_code=None,
        variant_column_mode=True,
    )
    assert bind is None
