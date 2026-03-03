"""Сервисы справочника «Типы топлива» (раздел fuel/refdata).
Используют модели из app.refdata.models.fuels.
"""
from app.refdata.services.fuels.fuel_type_services import (
    fuel_type_query,
    get_fuel_type_list,
    update_fuel_type_service,
    add_fuel_type_service,
    delete_fuel_type_service,
    import_fuel_type_service,
    export_fuel_type_service,
)

__all__ = [
    "fuel_type_query",
    "get_fuel_type_list",
    "update_fuel_type_service",
    "add_fuel_type_service",
    "delete_fuel_type_service",
    "import_fuel_type_service",
    "export_fuel_type_service",
]
