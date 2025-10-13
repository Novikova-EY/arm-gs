from typing import Any, Dict, Optional, Tuple
import time

# Very lightweight in-memory cache. Suitable for per-process usage.
_CACHE: Dict[Tuple[str, str], Tuple[float, Dict[str, Any]]] = {}

# TTL in seconds
_TTL_SECONDS = 600  # 10 minutes


def _purge_expired(now: float) -> None:
    expired_keys = [k for k, (ts, _) in _CACHE.items() if now - ts > _TTL_SECONDS]
    for k in expired_keys:
        _CACHE.pop(k, None)


def build_export_key(
    filters: Dict[str, Any],
    rounding_digits: Optional[int],
    start_year: int,
    end_year: int,
    show_p_ogr: bool,
    show_p_rasp: bool,
) -> str:
    # Stable representation of filters and parameters
    items = tuple(sorted((k, tuple(v) if isinstance(v, list) else v) for k, v in (filters or {}).items()))
    return str((items, rounding_digits, start_year, end_year, show_p_ogr, show_p_rasp))


def set_export_payload(user_id: str, key: str, payload: Dict[str, Any]) -> None:
    now = time.time()
    _purge_expired(now)
    _CACHE[(user_id or "anonymous", key)] = (now, payload)


def get_export_payload(user_id: str, key: str) -> Optional[Dict[str, Any]]:
    now = time.time()
    _purge_expired(now)
    entry = _CACHE.get((user_id or "anonymous", key))
    if not entry:
        return None
    ts, payload = entry
    if now - ts > _TTL_SECONDS:
        _CACHE.pop((user_id or "anonymous", key), None)
        return None
    return payload




