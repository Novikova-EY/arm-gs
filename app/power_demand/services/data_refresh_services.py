"""Версия сохраненных источников Нагрузок, независимая от очистки кеша."""

from flask import g, has_request_context
from redis.exceptions import RedisError

from app.common.services.cache_counters import get_shared_counter
from app.common.services.data_change_events import DataChangeTracker
from app.power_demand.services.pd_summary_page_cache import invalidate_power_demand_display_caches
from app.generation.services.station_services.aggregation_cache import get_redis_client


_REDIS_DATA_REVISION_KEY = "pd:data_revision"
_data_revision = 0


def get_power_demand_data_revision() -> int:
    return get_shared_counter(get_redis_client(), _REDIS_DATA_REVISION_KEY, _data_revision)


def publish_power_demand_data_change() -> None:
    global _data_revision

    # Сначала инвалидируем кеши всех процессов, затем публикуем новую версию.
    invalidate_power_demand_display_caches()
    _data_revision += 1
    revision = _data_revision
    redis_client = get_redis_client()
    if redis_client:
        try:
            revision = int(redis_client.incr(_REDIS_DATA_REVISION_KEY))
        except RedisError:
            pass
    if has_request_context() and "power_demand_saved_revisions" in g:
        g.power_demand_saved_revisions.append(revision)


_tracker = DataChangeTracker(
    (
        "app.power_demand.models.",
        "app.energy_consumption.models.",
    ),
    publish_power_demand_data_change,
    "_power_demand_changed_transactions",
)


def init_power_demand_change_events():
    _tracker.register()
