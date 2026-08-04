# -*- coding: utf-8 -*-
"""
Инвалидация кэшей отображения модуля «Спрос» на всех путях изменения данных.

Сводки Спроса — SSR (без data.json), но после обновлений нужно сбрасывать:
LRU заряда ГАЭС, request-кэш формул, индекс потребления для Нагрузок (+ pd_summary).
"""

from __future__ import annotations

import inspect
from unittest.mock import patch

from app.energy_consumption.services import ec_display_cache
from app.energy_consumption.services import energy_consumption_parameter_services as ec_ps
from app.energy_consumption.services.formula_text import (
    energy_consumption_summary_formula_text_services as formula_svc,
)
from app.energy_consumption.services import energy_consumption_summary_import_services as import_svc


def test_invalidate_energy_consumption_display_caches_calls_all_layers(app):
    with app.app_context():
        with (
            patch(
                "app.energy_consumption.services.energy_consumption_summary_services.clear_gaes_charge_summary_cache"
            ) as clear_gaes,
            patch(
                "app.energy_consumption.services.formula_text.energy_consumption_summary_formula_text_services.clear_formula_text_override_cache"
            ) as clear_formula,
            patch(
                "app.power_demand.services.pd_ec_consumption_index_cache.invalidate_pd_ec_consumption_index_cache"
            ) as inv_pd_ec,
        ):
            ec_display_cache.invalidate_energy_consumption_display_caches(version_id=42)
            clear_gaes.assert_called_once_with()
            clear_formula.assert_called_once_with()
            inv_pd_ec.assert_called_once_with(version_id=42)


def test_ec_detail_save_invalidates_display_caches():
    src = inspect.getsource(ec_ps.save_energy_consumption_rows_from_post)
    assert "invalidate_energy_consumption_display_caches" in src
    assert src.index("db.session.commit()") < src.index(
        "invalidate_energy_consumption_display_caches"
    )


def test_ec_summary_cell_and_note_and_gaes_invalidate():
    cell_src = inspect.getsource(ec_ps.save_demand_summary_cell)
    gaes_src = inspect.getsource(ec_ps._save_gaes_charge_summary_cell)
    assert "invalidate_energy_consumption_display_caches" in cell_src
    assert "invalidate_energy_consumption_display_caches" in gaes_src
    # entity_note ветка тоже сбрасывает кэш (раньше пропускала).
    assert cell_src.count("invalidate_energy_consumption_display_caches") >= 2


def test_ec_perimeter_block_commit_invalidates():
    src = inspect.getsource(ec_ps._commit_summary_perimeter_variant_change)
    assert "invalidate_energy_consumption_display_caches" in src
    assert src.index("db.session.commit()") < src.index(
        "invalidate_energy_consumption_display_caches"
    )


def test_ec_formula_save_reset_invalidate():
    assert "invalidate_energy_consumption_display_caches" in inspect.getsource(
        formula_svc.save_formula_text_override
    )
    assert "invalidate_energy_consumption_display_caches" in inspect.getsource(
        formula_svc.reset_formula_text_override
    )


def test_ec_persist_computed_invalidates():
    src = inspect.getsource(import_svc.persist_all_energy_consumption_summary_computed_rows)
    assert "invalidate_energy_consumption_display_caches" in src


def test_clear_all_caches_energy_consumption_uses_unified_invalidate():
    from app.common.services import clear_all_caches as cac

    src = inspect.getsource(cac.clear_all_application_caches)
    assert "invalidate_energy_consumption_display_caches" in src
