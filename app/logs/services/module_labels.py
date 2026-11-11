"""Названия модулей для общего журнала действий."""
from typing import Optional

from flask import has_request_context, request

SYSTEM_MODULE = "Система"

MODULE_LABELS = {
    "start": "Главная",
    "auth": "Авторизация",
    "users_bp": "Пользователи",
    "refdata_bp": "Справочники",
    "generation_bp": "Генерация",
    "station_bp": "Генерация",
    "station_changes_bp": "Генерация",
    "prospective_places_bp": "Генерация",
    "rational_structure_bp": "Рациональная структура",
    "rational_structure_module_bp": "Рациональная структура",
    "fuel_bp": "Топливо",
    "power_demand_bp": "Нагрузки",
    "energy_consumption_bp": "Спрос",
    "long_term_consumption_bp": "Долгосрочный прогноз потребления",
    "electrical_intensity_root_bp": "Долгосрочный прогноз потребления",
    "energy_balance_bp": "Балансы электрической энергии и мощности",
    "ecology_bp": "Экология",
    "economics_bp": "Экономика",
    "territories_bp": "Характеристики территорий",
    "logs": "Журнал",
    "history_bp": "История",
    "perimeter_variant_bp": "Варианты сценариев",
    "year_management": "Справочники",
    "exchange_api_bp": "Обмен данными",
    "database_versions_api_bp": "Справочники",
}


def module_label_for_endpoint(endpoint: Optional[str]) -> str:
    if not endpoint or "." not in endpoint:
        blueprint = (endpoint or "").strip()
    else:
        blueprint = endpoint.rsplit(".", 1)[0]
    return MODULE_LABELS.get(blueprint, "")


ENTITY_MODULES = {
    "Рациональная структура": ("rational_structure", "rational_structure_code"),
    "Генерация": ("station", "machine", "pgu_machine", "document", "import_fuel",
                  "gaes_tep_source", "ges_tep_source", "prospective_place_aes",
                  "prospective_place_gaes", "prospective_place_ges"),
    "Топливо": ("fuel", "distribution_parameter", "cities", "gen_company_branch",
                "import_fuel_db_equipment_groups", "soft_import_composite_flags", "territories_energy",
                "import_equipment_group_fuel_params", "import_equipment_groups"),
    "Экология": ("ecology",),
    "Экономика": ("long_term_accum_fixed_capital", "long_term_accum_monetary_income",
                  "long_term_population", "long_term_product_output", "long_term_ved_consumption"),
    "Долгосрочный прогноз потребления": ("long_term_electrical_intensity",),
    "Балансы электрической энергии и мощности": ("energy_balance", "ee_generation_import", "ee_transfers_import"),
    "Характеристики территорий": ("energy_unit_power_transfer",),
    "Нагрузки": ("pd_summ_oes_max", "power_demand_summary_ez", "power_demand_summary_fo", "power_demand_summary_oes"),
    "Спрос": ("energy_consumption_summary_ez", "energy_consumption_summary_fo", "energy_consumption_summary_oes"),
    "Пользователи": ("user",),
    "Справочники": ("business_unit", "condition_type", "database_version", "department",
                    "economic_activity_type", "economic_region", "electricity_production_cost_type",
                    "energy_area", "energy_system_type", "energy_unit", "energy_zone",
                    "energy_zone_external_mapping", "equipment_group", "federal_district",
                    "foreign_border_country", "fuel_type", "gen_company", "machine_type",
                    "pgu_tes_machine_type", "refdata_history", "regional_district",
                    "regional_energy_system", "regional_energy_system_external_mapping", "station_type",
                    "synchronous_area", "technology", "technology_availability", "technology_type", "tes_machine_type",
                    "tes_type", "union_energy_system", "year"),
}


def resolve_log_module(module: Optional[str] = None, entity_type: Optional[str] = None) -> str:
    if module and module.strip():
        return module.strip()
    if has_request_context():
        label = module_label_for_endpoint(request.endpoint)
        if label:
            return label
    for label, entities in ENTITY_MODULES.items():
        if entity_type in entities:
            return label
    return SYSTEM_MODULE
