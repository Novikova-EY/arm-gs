# -*- coding: utf-8 -*-
"""Единая очистка кэшей всех модулей (кнопка на странице версий БД)."""

from __future__ import annotations

import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)


def _safe_cache_clear(fn: Any) -> None:
    clear = getattr(fn, "cache_clear", None)
    if callable(clear):
        clear()


def _run_clear(name: str, fn: Callable[[], None], cleared: list[str], errors: list[str]) -> None:
    try:
        fn()
        cleared.append(name)
    except Exception as exc:
        logger.warning("Не удалось очистить кэш «%s»: %s", name, exc)
        errors.append(f"{name}: {exc}")


def clear_all_application_caches() -> dict[str, Any]:
    """Сбрасывает кэши станций, справочников, сводок и смежных модулей.

    Каждый шаг изолирован: сбой одного кэша не отменяет остальные.
    """
    cleared: list[str] = []
    errors: list[str] = []

    def _stations() -> None:
        from app.generation.services.station_services.aggregation_cache import (
            clear_aggregation_cache,
        )
        from app.generation.routes.stations.station_details_routes import (
            _render_machines_tbody_cached,
        )
        from app.generation.services.machine_services.machine_services import (
            clear_machine_choices_cache,
        )

        clear_aggregation_cache()
        _safe_cache_clear(_render_machines_tbody_cached)
        clear_machine_choices_cache()

    def _refdata() -> None:
        from app.common.services.cache_services import CacheService
        from app.common.services.choices_cache_service import ChoicesCacheService
        from app.common.services.choices_cache_service import choices_cache
        from app.common.perimeter_variant.db_loader import invalidate_perimeter_catalog_cache
        from app.common.services.get_services.territories.regional_district_get_services import (
            invalidate_regional_district_lookups_cache,
        )
        from app.common.services.get_services.territories.federal_district_get_services import (
            get_federal_district_list,
            get_federal_districts_map,
            get_regional_district_to_fd_id_map,
            get_fd_to_res_ids_map,
            get_fd_to_ues_ids_map,
            get_fd_to_est_ids_map,
            get_fd_to_rd_ids_map,
        )
        from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
            get_ues_to_est_id_map,
            get_ues_to_rd_ids_map,
            get_ues_to_fd_ids_map,
            get_union_energy_system_list_full,
            get_union_energy_system_list,
            get_union_energy_systems_map,
            get_ues_to_res_ids_map,
            get_res_to_ues_id_map,
        )
        from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
            get_res_to_rd_ids_map,
            get_res_to_fd_ids_map,
            get_res_to_synchronous_area_ids_map,
            get_regional_energy_systems_map,
        )
        from app.common.services.get_services.years.years_get_services import (
            clear_planning_period_year_caches,
        )
        from app.extensions import cache as flask_cache

        CacheService.clear_cache()
        ChoicesCacheService.clear_cache()
        choices_cache.clear_cache()
        invalidate_perimeter_catalog_cache()
        invalidate_regional_district_lookups_cache()
        for fn in (
            get_federal_district_list,
            get_federal_districts_map,
            get_regional_district_to_fd_id_map,
            get_fd_to_res_ids_map,
            get_fd_to_ues_ids_map,
            get_fd_to_est_ids_map,
            get_fd_to_rd_ids_map,
            get_ues_to_est_id_map,
            get_ues_to_rd_ids_map,
            get_ues_to_fd_ids_map,
            get_union_energy_system_list_full,
            get_union_energy_system_list,
            get_union_energy_systems_map,
            get_ues_to_res_ids_map,
            get_res_to_ues_id_map,
            get_res_to_rd_ids_map,
            get_res_to_fd_ids_map,
            get_res_to_synchronous_area_ids_map,
            get_regional_energy_systems_map,
        ):
            _safe_cache_clear(fn)
        clear_planning_period_year_caches()
        try:
            flask_cache.clear()
        except Exception:
            pass

    def _power_demand() -> None:
        from app.power_demand.services.pd_summary_page_cache import clear_pd_summary_page_cache
        from app.power_demand.services.pd_demand_rows_bulk_cache import (
            clear_power_demand_rows_bulk_cache,
        )
        from app.power_demand.services.formula_text.power_demand_summary_formula_text_services import (
            clear_formula_text_override_cache as clear_pd_formula_text_cache,
        )

        clear_pd_summary_page_cache()
        clear_power_demand_rows_bulk_cache()
        clear_pd_formula_text_cache()

    def _energy_consumption() -> None:
        from app.energy_consumption.services.energy_consumption_summary_services import (
            clear_gaes_charge_summary_cache,
        )
        from app.power_demand.services.pd_ec_consumption_index_cache import (
            invalidate_pd_ec_consumption_index_cache,
        )
        from app.energy_consumption.services.formula_text.energy_consumption_summary_formula_text_services import (
            clear_formula_text_override_cache as clear_ec_formula_text_cache,
        )

        clear_gaes_charge_summary_cache()
        invalidate_pd_ec_consumption_index_cache()
        clear_ec_formula_text_cache()

    def _energy_balance() -> None:
        from app.energy_balance.services.energy_balance_cache import clear_energy_balance_cache
        from app.energy_balance.services.ee_transfers_resolve_services import (
            clear_transfer_import_resolver_cache,
        )

        clear_energy_balance_cache()
        clear_transfer_import_resolver_cache()

    def _economics() -> None:
        from app.common.services.database_version_filter import get_current_db_version_id
        from app.common.services.economics_fd_data_cache import (
            invalidate_all_economics_fd_data_cache,
        )
        from app.economics.services.formula_text import (
            accum_fixed_capital_formula_text_services as afc_ft,
            product_output_formula_text_services as po_ft,
            ved_consumption_formula_text_services as ved_ft,
        )

        version_id = get_current_db_version_id()
        invalidate_all_economics_fd_data_cache(version_id)
        if version_id is not None:
            invalidate_all_economics_fd_data_cache(None)
        afc_ft.clear_formula_text_override_cache()
        po_ft.clear_formula_text_override_cache()
        ved_ft.clear_formula_text_override_cache()

    _run_clear("станции / агрегации", _stations, cleared, errors)
    _run_clear("справочники / территории / энергосистемы", _refdata, cleared, errors)
    _run_clear("сводки нагрузок (power demand)", _power_demand, cleared, errors)
    _run_clear("сводки потребления (energy consumption)", _energy_consumption, cleared, errors)
    _run_clear("энергобаланс", _energy_balance, cleared, errors)
    _run_clear("экономика", _economics, cleared, errors)

    return {
        "cleared": cleared,
        "errors": errors,
        "success": len(errors) == 0,
    }
