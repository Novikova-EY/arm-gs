"""Сервисы справочника «Виды топлива» (раздел fuel/refdata).
Используют модели из app.refdata.models.fuels.
"""
from app.refdata.services.fuels.fuel_services import (
    fuel_query,
    get_fuel_list,
    update_fuel_service,
    add_fuel_service,
    delete_fuel_service,
    import_fuel_service,
    export_fuel_service,
)

__all__ = [
    "fuel_query",
    "get_fuel_list",
    "update_fuel_service",
    "add_fuel_service",
    "delete_fuel_service",
    "import_fuel_service",
    "export_fuel_service",
]
