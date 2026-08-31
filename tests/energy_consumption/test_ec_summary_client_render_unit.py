# -*- coding: utf-8 -*-
"""Shell + JSON клиентский рендер сводок потребления."""

from __future__ import annotations

from unittest.mock import patch

from app.energy_consumption.services.ec_summary_client_render_services import (
    build_client_render_config,
    filter_ec_summary_rows_for_client_flags,
    prepare_summary_rows_for_client,
)
from app.energy_consumption.services.energy_consumption_summary_services import (
    _build_summary_shell_context,
)


def test_oes_shell_context_has_no_summary_rows():
    with patch(
        "app.energy_consumption.services.energy_consumption_summary_services.get_year_feature_dict",
        return_value={},
    ):
        context = _build_summary_shell_context(
            page_title="Потребление электрической энергии по энергосистемам",
            active_summary="oes",
            rounding_digits=1,
            start_year=2020,
            end_year=2024,
            filter_year_list=list(range(2020, 2025)),
            data_start_year=2020,
            data_end_year=2024,
        )
    assert context["summary_rows"] == []
    assert context["active_summary"] == "oes"
    assert context["years"] == [2020, 2021, 2022, 2023, 2024]


def test_prepare_summary_rows_for_client_copies_formula_tooltip():
    rows = [
        {
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "pd_ec_summary_row_formula_tooltip": "A + B",
            "year_values": ["1"],
            "unused_blob": {"heavy": True},
            "pd_ec_nt_extra_row": False,
        }
    ]
    out = prepare_summary_rows_for_client(rows)
    assert out[0]["pd_parameter_formula_tooltip"] == "A + B"
    assert out[0]["year_values"] == ["1"]
    assert "unused_blob" not in out[0]
    assert "pd_ec_nt_extra_row" not in out[0]


def test_filter_omits_sipr_and_verification_by_default():
    rows = [
        {
            "show_entity_cell": True,
            "entity_rowspan": 4,
            "entity_label": "ОЭС Центра",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "year_values": ["10"],
            "show_entity_note_cell": True,
            "entity_note_text": "note",
        },
        {
            "show_entity_cell": False,
            "entity_rowspan": 4,
            "entity_label": "ОЭС Центра",
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "year_values": ["11"],
        },
        {
            "show_entity_cell": False,
            "entity_rowspan": 4,
            "entity_label": "ОЭС Центра",
            "parameter_key": "energy_consumption_yoy_growth_pct",
            "year_values": ["1"],
        },
        {
            "show_entity_cell": False,
            "entity_rowspan": 4,
            "entity_label": "ОЭС Центра",
            "parameter_key": "energy_consumption_sipr_yoy_growth_pct",
            "year_values": ["2"],
        },
        {
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_label": "Проверка ОЭС Центра",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "year_values": ["0"],
        },
        {
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_label": "ОЭС Юга с НТ",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "pd_ec_nt_extra_row": True,
            "year_values": ["3"],
        },
        {
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_label": "ОЭС Юга с ГАЭС",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "pd_ec_gaes_extra_row": True,
            "year_values": ["4"],
        },
    ]
    off = {
        "sipr": False,
        "gaes": False,
        "nt": False,
        "verify": False,
        "o1": False,
        "compact": False,
    }
    out = filter_ec_summary_rows_for_client_flags(rows, off)
    keys = [r["parameter_key"] for r in out]
    labels = [r["entity_label"] for r in out]
    assert keys == [
        "energy_consumption_mln_kvt_ch",
        "energy_consumption_yoy_growth_pct",
    ]
    assert labels == ["ОЭС Центра", "ОЭС Центра"]
    assert out[0]["entity_rowspan"] == 2
    assert out[0]["show_entity_cell"] is True
    assert out[0]["entity_note_text"] == "note"
    assert out[1]["show_entity_cell"] is False

    sipr_on = dict(off, sipr=True)
    sipr_out = filter_ec_summary_rows_for_client_flags(rows, sipr_on)
    assert [r["parameter_key"] for r in sipr_out] == [
        "energy_consumption_sipr_mln_kvt_ch",
        "energy_consumption_sipr_yoy_growth_pct",
    ]

    verify_on = dict(off, verify=True)
    verify_out = filter_ec_summary_rows_for_client_flags(rows, verify_on)
    assert any(r["entity_label"] == "Проверка ОЭС Центра" for r in verify_out)


def test_filter_keeps_collapsed_gaes_visible_exception():
    rows = [
        {
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_label": "с ГАЭС",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "pd_ec_gaes_extra_row": True,
            "pd_ec_collapsed_nt_gaes_visible_row": True,
            "year_values": ["1"],
        }
    ]
    off = {
        "sipr": False,
        "gaes": False,
        "nt": False,
        "verify": False,
        "o1": False,
        "compact": False,
    }
    out = filter_ec_summary_rows_for_client_flags(rows, off)
    assert len(out) == 1


def test_build_client_render_config_has_data_path(app):
    with app.app_context():
        with app.test_request_context("/energy_consumption/summary/oes/"):
            cfg = build_client_render_config(
                scope="oes",
                data_path="/energy_consumption/summary/oes/data.json",
            )
            assert cfg["scope"] == "oes"
            assert cfg["data_path"].endswith("data.json")
            assert "energy_consumption_yoy_growth_pct" in cfg["pd_readonly_parameter_keys"]
            assert cfg["entity_pagination"]["default_page_size"] == 2
            assert cfg["entity_pagination"]["all_page_size"] == 0
            assert cfg["entity_pagination"]["all_label"] == "Все ОЭС"
            assert cfg["summary_variant_toggle_default_off"] is True


def test_copy_summary_page_context_does_not_alias_cached_rows():
    from app.energy_consumption.routes.energy_consumption_summary_routes import (
        _copy_summary_page_context,
    )

    cached_row = {
        "entity_label": "ОЭС Центра",
        "entity_kind": "group",
        "demand_model_name": "UnionEnergySystemEnergyConsumptionParameter",
        "parent_fk_column": "id_union_energy_system",
        "parent_id": 1,
        "show_entity_cell": True,
        "entity_rowspan": 1,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "year_values": ["1"],
    }
    full = {"active_summary": "oes", "summary_rows": [cached_row], "years": [2024]}
    page_context, meta = _copy_summary_page_context(
        full, scope="oes", entity_pagination=(1, 2)
    )
    assert page_context["summary_rows"][0] is not cached_row
    page_context["summary_rows"][0]["entity_label"] = "changed"
    assert cached_row["entity_label"] == "ОЭС Центра"
    assert meta is not None
    assert meta["page"] == 1


def test_data_json_omits_cascade_and_hidden_sipr_rows(app):
    from app.energy_consumption.services.ec_summary_client_render_services import (
        build_summary_data_json_response,
    )

    context = {
        "active_summary": "oes",
        "years": [2024],
        "year_is_plan": {2024: False},
        "pd_oes_filters_cascade": {"should": "not_appear"},
        "summary_rows": [
            {
                "show_entity_cell": True,
                "entity_rowspan": 2,
                "entity_label": "ОЭС Центра",
                "parameter_key": "energy_consumption_mln_kvt_ch",
                "year_values": ["1"],
                "unused_blob": {"x": 1},
            },
            {
                "show_entity_cell": False,
                "entity_rowspan": 2,
                "entity_label": "ОЭС Центра",
                "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
                "year_values": ["2"],
            },
        ],
    }
    with app.app_context():
        with app.test_request_context(
            "/energy_consumption/summary/oes/data.json?pd_page=1&pd_page_size=2"
        ):
            payload = build_summary_data_json_response(
                context, pagination_meta={"page": 1, "page_size": 2, "enabled": True}
            ).get_json()
    assert "pd_oes_filters_cascade" not in payload
    assert [r["parameter_key"] for r in payload["summary_rows"]] == [
        "energy_consumption_mln_kvt_ch"
    ]
    assert "unused_blob" not in payload["summary_rows"][0]
