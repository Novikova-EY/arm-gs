# -*- coding: utf-8 -*-
"""Фильтр журнала сводки нагрузок: entity_id или database_version_id."""

from app.power_demand.services.demand_summary_logging import pd_summary_logs_version_filter


def test_pd_summary_logs_version_filter_matches_entity_or_database_version() -> None:
    compiled = str(
        pd_summary_logs_version_filter(7).compile(compile_kwargs={"literal_binds": True})
    )
    assert "7" in compiled
    assert "entity_id" in compiled
    assert "database_version_id" in compiled
    assert " OR " in compiled.upper()
