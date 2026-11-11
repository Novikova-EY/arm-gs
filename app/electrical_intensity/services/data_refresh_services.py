"""Отслеживание изменений исходных данных для электроемкости."""

from flask import g, has_request_context
from redis.exceptions import RedisError

from app.common.services.cache_counters import get_shared_counter
from app.common.services.data_change_events import DataChangeTracker
from app.generation.services.station_services.aggregation_cache import get_redis_client

_REDIS_DATA_REVISION_KEY = "electrical_intensity:economics_data_revision"
_data_revision = 0


def get_electrical_intensity_data_revision() -> int:
    return get_shared_counter(get_redis_client(), _REDIS_DATA_REVISION_KEY, _data_revision)


def publish_electrical_intensity_data_change() -> None:
    global _data_revision

    _data_revision += 1
    revision = _data_revision
    redis_client = get_redis_client()
    if redis_client:
        try:
            revision = int(redis_client.incr(_REDIS_DATA_REVISION_KEY))
        except RedisError:
            pass
    if has_request_context() and "electrical_intensity_saved_revisions" in g:
        g.electrical_intensity_saved_revisions.append(revision)


_tracker = DataChangeTracker(
    ("app.economics.models.",),
    publish_electrical_intensity_data_change,
    "_electrical_intensity_economics_changed_transactions",
)


def init_electrical_intensity_change_events() -> None:
    _tracker.register()
