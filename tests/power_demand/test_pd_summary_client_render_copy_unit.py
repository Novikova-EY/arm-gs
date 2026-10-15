# -*- coding: utf-8 -*-
"""Проверка, что сериализация страницы не мутирует закэшированные строки."""

from app.power_demand.services import demand_summary_client_render_services as client_render


def _section(label: str, section_id: int) -> dict:
    return {
        "entity_label": label,
        "entity_kind": "union_energy_system",
        "entity_depth": 0,
        "demand_model_name": "UnionEnergySystemDemandParameter",
        "id_union_energy_system": section_id,
        "parameter_key": "max_power",
        "parameter_label": "Максимум",
        "entity_rowspan": 1,
        "show_entity_cell": True,
        "year_values": ["1"],
    }


def test_pre_paginated_rows_keep_builder_pagination_metadata(app):
    row = _section("ОЭС Юга", 2)
    pagination_meta = {
        "enabled": True,
        "scope": "oes",
        "page": 2,
        "page_size": 1,
        "total_pages": 2,
        "total_sections": 2,
        "has_prev": True,
        "has_next": False,
        "section_titles": ["ОЭС Юга"],
        "all_label": "Все ОЭС",
    }

    with app.app_context():
        response = client_render.build_summary_data_json_response(
            {
                "summary_rows": [row],
                "years": [2025],
                "active_summary": "oes",
                "summary_route_variant": "max",
                "pd_summary_rows_pre_paginated": True,
                "pd_entity_pagination": pagination_meta,
            },
            entity_pagination=(2, 1),
        )

    payload = response.get_json()
    assert [item["entity_label"] for item in payload["summary_rows"]] == ["ОЭС Юга"]
    assert payload["entity_pagination"] == pagination_meta


def test_paginated_response_does_not_mutate_cached_source_rows(app, monkeypatch):

    rows = [_section("ОЭС 1", 1), _section("ОЭС 2", 2)]

    def mutate_rows(rows):
        for row in rows:
            row["override_applied"] = True

    monkeypatch.setattr(client_render, "apply_row_formula_text_overrides", mutate_rows)

    with app.app_context():
        response = client_render.build_summary_data_json_response(
            {
                "summary_rows": rows,
                "years": [2025],
                "active_summary": "oes",
                "summary_route_variant": "max",
            },
            entity_pagination=(1, 1),
        )

    payload = response.get_json()
    assert [row["entity_label"] for row in payload["summary_rows"]] == ["ОЭС 1"]
    assert payload["summary_rows"][0]["override_applied"] is True
    assert all("override_applied" not in row for row in rows)
