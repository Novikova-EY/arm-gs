# -*- coding: utf-8 -*-
"""Пагинация сводок потребления по секциям ОЭС / ФО / энергозон."""

from __future__ import annotations

from app.energy_consumption.services.ec_summary_entity_pagination import (
    paginate_oes_summary_rows,
    paginate_summary_rows_for_scope,
    split_oes_summary_rows_for_pagination,
    split_summary_rows_for_pagination,
)

UES = "UnionEnergySystemEnergyConsumptionParameter"
FD = "FederalDistrictEnergyConsumptionParameter"
EZ = "EnergyZoneEnergyConsumptionParameter"


def _block(*rows: dict) -> list[dict]:
    out: list[dict] = []
    for i, row in enumerate(rows):
        rc = dict(row)
        rc["show_entity_cell"] = i == 0
        rc["entity_rowspan"] = len(rows)
        out.append(rc)
    return out


def _oes_head(label: str, ues_id: int, **extra) -> dict:
    row = {
        "entity_label": label,
        "entity_kind": "group",
        "demand_model_name": UES,
        "parent_fk_column": "id_union_energy_system",
        "parent_id": ues_id,
        "parameter_key": "energy_consumption_mln_kvt_ch",
    }
    row.update(extra)
    return row


def _sample_oes_rows() -> list[dict]:
    prefix = _block(
        {
            "entity_label": "Россия",
            "entity_kind": "default",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {"entity_label": "Россия", "parameter_key": "energy_consumption_yoy_growth_pct"},
    )
    oes1 = _block(_oes_head("ОЭС Центра", 1))
    variant1 = _block(
        _oes_head("ОЭС Центра", 1, entity_kind="perimeter_variant"),
        {
            "entity_label": "ОЭС Центра",
            "parameter_key": "energy_consumption_yoy_growth_pct",
        },
    )
    res1 = _block(
        {
            "entity_label": "РЭС-1",
            "entity_kind": "child",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
    )
    oes2 = _block(_oes_head("ОЭС Юга", 2))
    suffix = [
        {
            "entity_label": "ТИТЭС и децентрализованная зона",
            "entity_kind": "aggregation_level",
            "pd_ec_aggregation_level_row": True,
            "show_entity_cell": True,
            "entity_rowspan": 1,
        }
    ]
    return prefix + oes1 + variant1 + res1 + oes2 + suffix


def test_split_oes_summary_rows_for_pagination():
    prefix, sections, suffix = split_oes_summary_rows_for_pagination(_sample_oes_rows())
    assert [r["entity_label"] for r in prefix if r.get("show_entity_cell")] == ["Россия"]
    assert len(sections) == 2
    assert sections[0][0]["entity_label"] == "ОЭС Центра"
    assert any(r["entity_kind"] == "perimeter_variant" for r in sections[0])
    assert any(r["entity_label"] == "РЭС-1" for r in sections[0])
    assert sections[1][0]["entity_label"] == "ОЭС Юга"
    assert suffix[0]["entity_label"].startswith("ТИТЭС")


def test_paginate_oes_first_page_includes_prefix_not_suffix():
    page_rows, meta = paginate_oes_summary_rows(
        _sample_oes_rows(),
        page=1,
        page_size=1,
    )
    labels = [r["entity_label"] for r in page_rows if r.get("show_entity_cell")]
    assert "Россия" in labels
    assert "ОЭС Центра" in labels
    assert "ОЭС Юга" not in labels
    assert not any("ТИТЭС" in (lbl or "") for lbl in labels)
    assert meta["enabled"] is True
    assert meta["total_pages"] == 2
    assert meta["has_next"] is True
    assert meta["has_prev"] is False
    assert meta["all_label"] == "Все ОЭС"


def test_paginate_oes_last_page_includes_suffix():
    page_rows, meta = paginate_oes_summary_rows(
        _sample_oes_rows(),
        page=2,
        page_size=1,
    )
    labels = [r["entity_label"] for r in page_rows if r.get("show_entity_cell")]
    assert "Россия" not in labels
    assert "ОЭС Юга" in labels
    assert any("ТИТЭС" in (lbl or "") for lbl in labels)
    assert meta["has_prev"] is True
    assert meta["has_next"] is False


def test_paginate_oes_page_size_zero_returns_all():
    rows = _sample_oes_rows()
    page_rows, meta = paginate_oes_summary_rows(rows, page=1, page_size=0)
    assert len(page_rows) == len(rows)
    assert meta["enabled"] is False
    assert meta["page_size"] == 0
    assert meta["total_sections"] == 2


def test_gaes_charge_row_does_not_start_oes_section():
    rows = (
        _block(_oes_head("ОЭС Центра", 1))
        + _block(
            {
                "entity_label": "ОЭС Центра (заряд ГАЭС)",
                "entity_kind": "group",
                "demand_model_name": UES,
                "parent_fk_column": "id_union_energy_system",
                "parent_id": 1,
                "parameter_key": "gaes_charge_consumption_mln_kvt_ch",
            }
        )
        + _block(_oes_head("ОЭС Юга", 2))
    )
    _, sections, _ = split_oes_summary_rows_for_pagination(rows)
    assert len(sections) == 2
    assert sections[0][0]["entity_label"] == "ОЭС Центра"
    assert any(
        r.get("parameter_key") == "gaes_charge_consumption_mln_kvt_ch"
        for r in sections[0]
    )


def test_paginate_fo_first_page():
    prefix = _block(
        {
            "entity_label": "ЦЗ России",
            "entity_kind": "centralized_zone",
            "entity_depth": 0,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
    )
    fd1 = _block(
        {
            "entity_label": "Центральный ФО",
            "entity_kind": "group",
            "entity_depth": 0,
            "demand_model_name": FD,
            "parent_fk_column": "id_federal_district",
            "id_federal_district": 10,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
    )
    fd2 = _block(
        {
            "entity_label": "Южный ФО",
            "entity_kind": "group",
            "entity_depth": 0,
            "demand_model_name": FD,
            "parent_fk_column": "id_federal_district",
            "id_federal_district": 20,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
    )
    rows = prefix + fd1 + fd2
    page_rows, meta = paginate_summary_rows_for_scope(rows, "fo", page=1, page_size=1)
    labels = [r["entity_label"] for r in page_rows if r.get("show_entity_cell")]
    assert "ЦЗ России" in labels
    assert "Центральный ФО" in labels
    assert "Южный ФО" not in labels
    assert meta["enabled"] is True
    assert meta["all_label"] == "Все ФО"


def test_split_ez_summary_rows_by_energy_zone():
    prefix = _block(
        {
            "entity_label": "ЕЭС России",
            "entity_kind": "ees_russia",
            "entity_depth": 0,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
    )
    ez1 = _block(
        {
            "entity_label": "1 — Северо-Запад",
            "entity_kind": "group",
            "entity_depth": 0,
            "demand_model_name": EZ,
            "parent_fk_column": "id_energy_zone",
            "id_energy_zone": 1,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
    )
    ez2 = _block(
        {
            "entity_label": "2 — Центр",
            "entity_kind": "group",
            "entity_depth": 0,
            "demand_model_name": EZ,
            "parent_fk_column": "id_energy_zone",
            "id_energy_zone": 2,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
    )
    suffix = [
        {
            "entity_label": "Новые территории",
            "entity_kind": "aggregation_level",
            "pd_ec_aggregation_level_row": True,
            "show_entity_cell": True,
            "entity_rowspan": 1,
        }
    ]
    rows = prefix + ez1 + ez2 + suffix
    pfx, sections, sfx = split_summary_rows_for_pagination(rows, "ez")
    assert [r["entity_label"] for r in pfx if r.get("show_entity_cell")] == ["ЕЭС России"]
    assert len(sections) == 2
    assert sections[0][0]["id_energy_zone"] == 1
    assert sfx[0]["entity_label"] == "Новые территории"
    page_rows, meta = paginate_summary_rows_for_scope(rows, "ez", page=2, page_size=1)
    labels = [r["entity_label"] for r in page_rows if r.get("show_entity_cell")]
    assert "ЕЭС России" not in labels
    assert "2 — Центр" in labels
    assert "Новые территории" in labels
    assert meta["all_label"] == "Все энергозоны"
