"""Инвалидация кеша энергобалансов только после успешного сохранения источников."""

from app.common.services.data_change_events import DataChangeTracker

from app.energy_balance.services.energy_balance_cache import publish_energy_balance_data_change


_SOURCE_MODULES = (
    "app.energy_balance.models.",
    "app.generation.models.",
    "app.energy_consumption.models.",
    "app.power_demand.models.",
)
_tracker = DataChangeTracker(
    _SOURCE_MODULES,
    publish_energy_balance_data_change,
    "_energy_balance_changed_transactions",
)


def init_energy_balance_change_events():
    _tracker.register()
