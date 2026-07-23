# -*- coding: utf-8 -*-
"""Пагинация сводок нагрузок по секциям ОЭС / ФО / энергозон."""

from __future__ import annotations

from app.power_demand.services.pd_summary_entity_pagination import (
    filter_segment_rows_to_pagination_page,
    paginate_oes_summary_rows,
    paginate_summary_rows_for_scope,
    split_oes_summary_rows_for_pagination,
    split_summary_rows_for_pagination,
)


def _block(*rows: dict) -> list[dict]:
    out: list[dict] = []
    for i, row in enumerate(rows):
        rc = dict(row)
        rc["show_entity_cell"] = i == 0
        rc["entity_rowspan"] = len(rows)
        out.append(rc)
    return out


def _sample_oes_rows() -> list[dict]:
    prefix = _block(
        {"entity_label": "Россия", "entity_kind": "default", "parameter_key": "max_power"},
        {"entity_label": "Россия", "parameter_key": "peak_datetime"},
    )
    oes1 = _block(
        {
            "entity_label": "ОЭС Центра",
            "entity_kind": "union_energy_system",
            "parameter_key": "max_power",
        },
        {"entity_label": "ОЭС Центра", "parameter_key": "combined_on_oes"},
    )
    res1 = _block(
        {
            "entity_label": "РЭС-1",
            "entity_kind": "child",
            "parameter_key": "max_power",
        },
    )
    oes2 = _block(
        {
            "entity_label": "ОЭС Юга",
            "entity_kind": "union_energy_system",
            "parameter_key": "max_power",
        },
    )
    suffix = [
        {
            "entity_label": "ТИТЭС и децентрализованная зона",
            "entity_kind": "aggregation_level",
            "pd_pd_aggregation_level_row": True,
            "show_entity_cell": True,
            "entity_rowspan": 1,
        }
    ]
    return prefix + oes1 + res1 + oes2 + suffix


def test_split_oes_summary_rows_for_pagination():
    prefix, sections, suffix = split_oes_summary_rows_for_pagination(_sample_oes_rows())
    assert [r["entity_label"] for r in prefix if r.get("show_entity_cell")] == ["Россия"]
    assert len(sections) == 2
    assert sections[0][0]["entity_label"] == "ОЭС Центра"
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


def test_tag_summary_rows_before_section_blocks_marks_prefix_only():
    from app.power_demand.services.pd_summary_entity_pagination import (
        tag_summary_rows_before_section_blocks,
    )

    rows = _sample_oes_rows()
    tag_summary_rows_before_section_blocks(rows, "oes")
    by_label = {
        r["entity_label"]: r
        for r in rows
        if r.get("show_entity_cell")
    }
    assert by_label["Россия"].get("pd_pd_summary_table_only_row") is True
    assert by_label["ОЭС Центра"].get("pd_pd_summary_table_only_row") is not True
    assert by_label["ОЭС Юга"].get("pd_pd_summary_table_only_row") is not True
    assert by_label["ТИТЭС и децентрализованная зона"].get(
        "pd_pd_summary_table_only_row"
    ) is not True


def test_export_without_compact_hides_summary_table_only_prefix():
    from app.power_demand.services import demand_summary_services as service

    rows = [
        {"entity_label": "ЦЗ России", "pd_pd_summary_table_only_row": True},
        {"entity_label": "ОЭС Центра"},
    ]
    exported_off = service.apply_power_demand_summary_territory_compact_export_ui(
        rows,
        territory_compact_on=False,
    )
    assert [r["entity_label"] for r in exported_off] == ["ОЭС Центра"]

    exported_on = service.apply_power_demand_summary_territory_compact_export_ui(
        rows,
        territory_compact_on=True,
    )
    assert [r["entity_label"] for r in exported_on] == ["ЦЗ России", "ОЭС Центра"]


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


def test_filter_segment_rows_page1_includes_prefix_calc_not_other_sections():
    """Ленивый calc_max префикса (1-я СЗ) — на 1-й странице, как core prefix."""
    rows = _sample_oes_rows()
    # Добавим id секций, как в реальных строках ОЭС.
    for r in rows:
        if r.get("entity_label") == "ОЭС Центра":
            r["id_union_energy_system"] = 1
            r["demand_model_name"] = "UnionEnergySystemDemandParameter"
        if r.get("entity_label") == "ОЭС Юга":
            r["id_union_energy_system"] = 2
            r["demand_model_name"] = "UnionEnergySystemDemandParameter"

    first_sa_calc = _block(
        {
            "entity_label": "Первая синхронная зона без НТ",
            "entity_kind": "synchronous_area",
            "demand_model_name": "SynchronousAreaDemandParameter",
            "parent_fk_column": "id_synchronous_area",
            "parent_id": 39,
            "id_synchronous_area": 39,
            "perimeter_variant_code": "without_nt",
            "pd_pd_summary_table_only_row": True,
            "parameter_key": "calculated_max_power_mw",
        },
        {"parameter_key": "calculated_max_sa_mw"},
    )
    first_sa_with_nt_calc = _block(
        {
            "entity_label": "Первая синхронная зона с НТ",
            "entity_kind": "synchronous_area",
            "demand_model_name": "SynchronousAreaDemandParameter",
            "parent_fk_column": "id_synchronous_area",
            "parent_id": 39,
            "id_synchronous_area": 39,
            "perimeter_variant_code": "with_nt",
            "pd_pd_nt_extra_row": True,
            "pd_pd_summary_table_only_row": True,
            "parameter_key": "calculated_max_power_mw",
        },
        {"parameter_key": "calculated_max_sa_mw"},
    )
    oes_center_calc = _block(
        {
            "entity_label": "ОЭС Центра",
            "entity_kind": "group",
            "demand_model_name": "UnionEnergySystemDemandParameter",
            "id_union_energy_system": 1,
            "parameter_key": "calculated_max_power_mw",
        },
    )
    oes_south_calc = _block(
        {
            "entity_label": "ОЭС Юга",
            "entity_kind": "group",
            "demand_model_name": "UnionEnergySystemDemandParameter",
            "id_union_energy_system": 2,
            "parameter_key": "calculated_max_power_mw",
        },
    )
    calc_rows = first_sa_with_nt_calc + first_sa_calc + oes_center_calc + oes_south_calc

    page1 = filter_segment_rows_to_pagination_page(
        calc_rows, rows, "oes", page=1, page_size=1
    )
    labels1 = [r["entity_label"] for r in page1 if r.get("show_entity_cell")]
    assert "Первая синхронная зона без НТ" in labels1
    assert "Первая синхронная зона с НТ" in labels1
    assert "ОЭС Центра" in labels1
    assert "ОЭС Юга" not in labels1

    page2 = filter_segment_rows_to_pagination_page(
        calc_rows, rows, "oes", page=2, page_size=1
    )
    labels2 = [r["entity_label"] for r in page2 if r.get("show_entity_cell")]
    assert "Первая синхронная зона без НТ" not in labels2
    assert "Первая синхронная зона с НТ" not in labels2
    assert "ОЭС Юга" in labels2
    assert "ОЭС Центра" not in labels2


def test_filter_segment_rows_last_page_includes_suffix_calc():
    """Суффикс ленивого сегмента (ТИТЭС) — на последней странице, как у core."""
    rows = _sample_oes_rows()
    for r in rows:
        if r.get("entity_label") == "ОЭС Центра":
            r["id_union_energy_system"] = 1
            r["demand_model_name"] = "UnionEnergySystemDemandParameter"
        if r.get("entity_label") == "ОЭС Юга":
            r["id_union_energy_system"] = 2
            r["demand_model_name"] = "UnionEnergySystemDemandParameter"

    tites_calc = _block(
        {
            "entity_label": "ТИТЭС и децентрализованная зона",
            "entity_kind": "aggregation_level",
            "pd_pd_aggregation_level_row": True,
            "parameter_key": "calculated_max_power_mw",
        },
    )
    # Суффикс определяется по блоку с «ТИТЭС» в подписи.
    tites_calc[0]["parameter_key"] = ""
    tites_entity = _block(
        {
            "entity_label": "ТИТЭС объект",
            "entity_kind": "child",
            "demand_model_name": "RegionalDistrictDemandParameter",
            "parameter_key": "calculated_max_power_mw",
        },
    )
    # Нужен заголовок ТИТЭС как suffix_block, затем строки внутри суффикса.
    suffix_header = [
        {
            "entity_label": "ТИТЭС и децентрализованная зона",
            "entity_kind": "aggregation_level",
            "pd_pd_aggregation_level_row": True,
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "parameter_key": "",
        }
    ]
    calc_rows = (
        _block(
            {
                "entity_label": "ОЭС Юга",
                "entity_kind": "group",
                "demand_model_name": "UnionEnergySystemDemandParameter",
                "id_union_energy_system": 2,
                "parameter_key": "calculated_max_power_mw",
            },
        )
        + suffix_header
        + tites_entity
    )

    page2 = filter_segment_rows_to_pagination_page(
        calc_rows, rows, "oes", page=2, page_size=1
    )
    labels = [r["entity_label"] for r in page2 if r.get("show_entity_cell")]
    assert "ОЭС Юга" in labels
    assert any("ТИТЭС" in (lbl or "") for lbl in labels)

    page1 = filter_segment_rows_to_pagination_page(
        calc_rows, rows, "oes", page=1, page_size=1
    )
    labels1 = [r["entity_label"] for r in page1 if r.get("show_entity_cell")]
    assert not any("ТИТЭС" in (lbl or "") for lbl in labels1)


def test_split_oes_does_not_treat_nt_aggregation_inside_ues_as_suffix():
    """«Новые территории» внутри ОЭС Юга — часть секции, не суффикс (ТИТЭС)."""
    prefix = _block(
        {
            "entity_label": "ЕЭС России",
            "entity_kind": "default",
            "parameter_key": "max_power",
        },
    )
    oes_yug = _block(
        {
            "entity_label": "ОЭС Юга с НТ",
            "entity_kind": "perimeter_variant",
            "entity_depth": 0,
            "demand_model_name": "UnionEnergySystemDemandParameter",
            "id_union_energy_system": 118,
            "parameter_key": "max_power",
        },
    )
    nt_inside_yug = [
        {
            "entity_label": "Новые территории",
            "entity_kind": "aggregation_level",
            "entity_depth": 1,
            "id_union_energy_system": 118,
            "pd_pd_aggregation_level_row": True,
            "show_entity_cell": True,
            "entity_rowspan": 1,
        }
    ]
    oes_ural = _block(
        {
            "entity_label": "ОЭС Урала",
            "entity_kind": "group",
            "entity_depth": 0,
            "demand_model_name": "UnionEnergySystemDemandParameter",
            "id_union_energy_system": 116,
            "parameter_key": "max_power",
        },
    )
    suffix = [
        {
            "entity_label": "ТИТЭС и децентрализованная зона",
            "entity_kind": "aggregation_level",
            "pd_pd_aggregation_level_row": True,
            "show_entity_cell": True,
            "entity_rowspan": 1,
        }
    ]
    rows = prefix + oes_yug + nt_inside_yug + oes_ural + suffix
    _pfx, sections, sfx = split_oes_summary_rows_for_pagination(rows)
    assert len(sections) == 2
    assert any(r["entity_label"] == "Новые территории" for r in sections[0])
    assert sections[1][0]["entity_label"] == "ОЭС Урала"
    assert sfx[0]["entity_label"].startswith("ТИТЭС")


def test_split_groups_perimeter_variant_oes_blocks_by_ues_id():
    prefix = _block(
        {
            "entity_label": "ЕЭС России",
            "entity_kind": "default",
            "parameter_key": "max_power",
        },
    )
    oes1_v1 = _block(
        {
            "entity_label": "ОЭС Центра",
            "entity_kind": "perimeter_variant",
            "entity_depth": 0,
            "demand_model_name": "UnionEnergySystemDemandParameter",
            "id_union_energy_system": 1,
            "parameter_key": "max_power",
        },
    )
    oes1_v2 = _block(
        {
            "entity_label": "ОЭС Центра с НТ",
            "entity_kind": "perimeter_variant",
            "entity_depth": 0,
            "demand_model_name": "UnionEnergySystemDemandParameter",
            "id_union_energy_system": 1,
            "parameter_key": "max_power",
        },
    )
    res1 = _block(
        {
            "entity_label": "РЭС-1",
            "entity_kind": "child",
            "entity_depth": 1,
            "demand_model_name": "RegionalEnergySystemDemandParameter",
            "id_union_energy_system": 1,
            "parameter_key": "max_power",
        },
    )
    oes2 = _block(
        {
            "entity_label": "ОЭС Юга",
            "entity_kind": "perimeter_variant",
            "entity_depth": 0,
            "demand_model_name": "UnionEnergySystemDemandParameter",
            "id_union_energy_system": 2,
            "parameter_key": "max_power",
        },
    )
    rows = prefix + oes1_v1 + oes1_v2 + res1 + oes2
    _, sections, _ = split_oes_summary_rows_for_pagination(rows)
    assert len(sections) == 2
    assert any(r["entity_label"] == "РЭС-1" for r in sections[0])
    assert sections[1][0]["id_union_energy_system"] == 2


def test_split_fo_summary_rows_by_federal_district():
    prefix = _block(
        {
            "entity_label": "ЦЗ России",
            "entity_kind": "centralized_zone",
            "entity_depth": 0,
            "demand_model_name": "CentralizedZoneDemandParameter",
            "parameter_key": "max_power",
        },
    )
    fd1 = _block(
        {
            "entity_label": "Центральный ФО",
            "entity_kind": "group",
            "entity_depth": 0,
            "demand_model_name": "FederalDistrictDemandParameter",
            "id_federal_district": 10,
            "parameter_key": "max_power",
        },
    )
    res1 = _block(
        {
            "entity_label": "РЭС Центра",
            "entity_kind": "child",
            "entity_depth": 1,
            "demand_model_name": "RegionalEnergySystemDemandParameter",
            "id_federal_district": 10,
            "parameter_key": "max_power",
        },
    )
    fd2 = _block(
        {
            "entity_label": "Южный ФО",
            "entity_kind": "group",
            "entity_depth": 0,
            "demand_model_name": "FederalDistrictDemandParameter",
            "id_federal_district": 20,
            "parameter_key": "max_power",
        },
    )
    rows = prefix + fd1 + res1 + fd2
    pfx, sections, sfx = split_summary_rows_for_pagination(rows, "fo")
    assert len(sections) == 2
    assert [r["entity_label"] for r in pfx if r.get("show_entity_cell")] == ["ЦЗ России"]
    assert not sfx
    assert any(r["entity_label"] == "РЭС Центра" for r in sections[0])


def test_paginate_fo_first_page():
    prefix = _block(
        {
            "entity_label": "ЦЗ России",
            "entity_kind": "centralized_zone",
            "entity_depth": 0,
            "demand_model_name": "CentralizedZoneDemandParameter",
            "parameter_key": "max_power",
        },
    )
    fd1 = _block(
        {
            "entity_label": "Центральный ФО",
            "entity_kind": "group",
            "entity_depth": 0,
            "demand_model_name": "FederalDistrictDemandParameter",
            "id_federal_district": 10,
            "parameter_key": "max_power",
        },
    )
    fd2 = _block(
        {
            "entity_label": "Южный ФО",
            "entity_kind": "group",
            "entity_depth": 0,
            "demand_model_name": "FederalDistrictDemandParameter",
            "id_federal_district": 20,
            "parameter_key": "max_power",
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
            "demand_model_name": "EnergySystemTypeDemandParameter",
            "parameter_key": "max_power",
        },
    )
    ez1 = _block(
        {
            "entity_label": "1 — Северо-Запад",
            "entity_kind": "group",
            "entity_depth": 0,
            "demand_model_name": "EnergyZoneDemandParameter",
            "id_energy_zone": 1,
            "parameter_key": "max_power",
        },
    )
    ez2 = _block(
        {
            "entity_label": "2 — Центр",
            "entity_kind": "group",
            "entity_depth": 0,
            "demand_model_name": "EnergyZoneDemandParameter",
            "id_energy_zone": 2,
            "parameter_key": "max_power",
        },
    )
    suffix = [
        {
            "entity_label": "Новые территории",
            "entity_kind": "aggregation_level",
            "pd_pd_aggregation_level_row": True,
            "show_entity_cell": True,
            "entity_rowspan": 1,
        }
    ]
    rows = prefix + ez1 + ez2 + suffix
    pfx, sections, sfx = split_summary_rows_for_pagination(rows, "ez")
    assert len(sections) == 2
    assert sections[0][0]["id_energy_zone"] == 1
    assert sfx[0]["entity_label"] == "Новые территории"
    page_rows, meta = paginate_summary_rows_for_scope(rows, "ez", page=2, page_size=1)
    labels = [r["entity_label"] for r in page_rows if r.get("show_entity_cell")]
    assert "ЕЭС России" not in labels
    assert "2 — Центр" in labels
    assert "Новые территории" in labels
    assert meta["all_label"] == "Все энергозоны"


def test_paginate_oes_page_size_zero_returns_all():
    page_rows, meta = paginate_oes_summary_rows(
        _sample_oes_rows(),
        page=1,
        page_size=0,
    )
    assert len(page_rows) == len(_sample_oes_rows())
    assert meta["enabled"] is False


def test_filter_nt_extra_rows_to_ez_pagination_page():
    """nt_extra не должен попадать на страницы без соответствующей энергозоны."""
    prefix = _block(
        {
            "entity_label": "ЕЭС России",
            "entity_kind": "ees_russia",
            "entity_depth": 0,
            "demand_model_name": "EnergySystemTypeDemandParameter",
            "parameter_key": "max_power",
        },
    )
    ez1 = _block(
        {
            "entity_label": "1 — Северо-Запад",
            "entity_kind": "group",
            "entity_depth": 0,
            "demand_model_name": "EnergyZoneDemandParameter",
            "id_energy_zone": 1,
            "parameter_key": "max_power",
        },
    )
    ez2 = _block(
        {
            "entity_label": "2 — Центр",
            "entity_kind": "group",
            "entity_depth": 0,
            "demand_model_name": "EnergyZoneDemandParameter",
            "id_energy_zone": 2,
            "parameter_key": "max_power",
        },
    )
    core_rows = prefix + ez1 + ez2
    nt_subject_zone1 = _block(
        {
            "entity_label": "Донецкая Народная Республика",
            "entity_kind": "child",
            "entity_depth": 2,
            "demand_model_name": "RegionalDistrictDemandParameter",
            "id_energy_zone": 1,
            "pd_pd_nt_extra_row": True,
            "parameter_key": "max_power",
        },
    )
    nt_subject_zone2 = _block(
        {
            "entity_label": "Луганская Народная Республика",
            "entity_kind": "child",
            "entity_depth": 2,
            "demand_model_name": "RegionalDistrictDemandParameter",
            "id_energy_zone": 2,
            "pd_pd_nt_extra_row": True,
            "parameter_key": "max_power",
        },
    )
    nt_rows = nt_subject_zone1 + nt_subject_zone2

    page1_nt = filter_segment_rows_to_pagination_page(
        nt_rows, core_rows, "ez", page=1, page_size=1
    )
    page2_nt = filter_segment_rows_to_pagination_page(
        nt_rows, core_rows, "ez", page=2, page_size=1
    )
    labels1 = [r["entity_label"] for r in page1_nt if r.get("show_entity_cell")]
    labels2 = [r["entity_label"] for r in page2_nt if r.get("show_entity_cell")]
    assert labels1 == ["Донецкая Народная Республика"]
    assert labels2 == ["Луганская Народная Республика"]


def test_filter_fo_combined_chi_rows_by_federal_district_on_pagination_page():
    fd1 = 10
    fd2 = 20
    core_rows = (
        _block(
            {
                "entity_label": "ЦФО",
                "entity_kind": "group",
                "demand_model_name": "FederalDistrictDemandParameter",
                "id_federal_district": fd1,
                "parameter_key": "max_power",
            },
            {"parameter_key": "combined_on_cz"},
        )
        + _block(
            {
                "entity_label": "РЭС ЦФО",
                "entity_kind": "child",
                "demand_model_name": "RegionalEnergySystemDemandParameter",
                "id_federal_district": fd1,
                "id_regional_energy_system": 101,
                "parameter_key": "max_power",
            },
            {"parameter_key": "combined_on_fo"},
        )
        + _block(
            {
                "entity_label": "СЗФО",
                "entity_kind": "group",
                "demand_model_name": "FederalDistrictDemandParameter",
                "id_federal_district": fd2,
                "parameter_key": "max_power",
            },
            {"parameter_key": "combined_on_cz"},
        )
    )
    chi_rows = [
        {
            "parameter_key": "peak_combined_on_fo_usage_hours",
            "pd_pd_chi_row": True,
            "id_federal_district": fd1,
            "entity_label": "РЭС ЦФО",
        },
        {
            "parameter_key": "peak_combined_on_fo_usage_hours",
            "pd_pd_chi_row": True,
            "id_federal_district": fd2,
            "entity_label": "РЭС СЗФО",
        },
    ]
    page1 = filter_segment_rows_to_pagination_page(
        chi_rows, core_rows, "fo", page=1, page_size=1
    )
    assert len(page1) == 1
    assert page1[0]["id_federal_district"] == fd1
