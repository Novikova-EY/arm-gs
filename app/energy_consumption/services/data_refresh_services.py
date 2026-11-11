"""Версия сохраненных источников Спроса, независимая от очистки кеша."""

from flask import g, has_request_context
from redis.exceptions import RedisError

from app.common.services.cache_counters import get_shared_counter
from app.common.services.data_change_events import DataChangeTracker
from app.energy_consumption.services.ec_summary_page_cache import clear_ec_summary_page_cache
from app.generation.services.station_services.aggregation_cache import get_redis_client


_REDIS_DATA_REVISION_KEY = "ec:data_revision"
_data_revision = 0


def get_energy_consumption_data_revision() -> int:
    return get_shared_counter(get_redis_client(), _REDIS_DATA_REVISION_KEY, _data_revision)


def publish_energy_consumption_data_change() -> None:
    global _data_revision

    # Сначала инвалидируем кеши всех процессов, затем публикуем новую версию.
    clear_ec_summary_page_cache()
    _data_revision += 1
    revision = _data_revision
    redis_client = get_redis_client()
    if redis_client:
        try:
            revision = int(redis_client.incr(_REDIS_DATA_REVISION_KEY))
        except RedisError:
            pass
    if has_request_context() and "energy_consumption_saved_revisions" in g:
        g.energy_consumption_saved_revisions.append(revision)


_tracker = DataChangeTracker(
    ("app.energy_consumption.models.",),
    publish_energy_consumption_data_change,
    "_energy_consumption_changed_transactions",
)


def init_energy_consumption_change_events():
    _tracker.register()
