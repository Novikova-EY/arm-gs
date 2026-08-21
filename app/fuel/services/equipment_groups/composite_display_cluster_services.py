# -*- coding: utf-8 -*-
"""
Кластеры отображения составных станций: ключ = parent numb (comp/main).

Station через SetStation остаётся для машин/типов и подписи блока,
но не является источником истины составности.

allow_station_composite_fallback:
  True  — несколько EG на одном Station без comp/main ведут себя как раньше
          (legacy до полной дозагрузки Access-флагов);
  False — такие EG только сосуществуют в бакете Station, без «составной» семантики.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Callable, Iterable, Literal, Sequence

from app.fuel.services.equipment_groups.composite_station_semantics import (
    _as_int,
    is_composite_child_group,
    is_composite_parent_group,
    is_main_empty,
)

ClusterKind = Literal["composite", "station", "standalone"]


def _eg_label(eg: Any) -> str:
    if eg is None:
        return "—"
    for attr in ("name_ext", "name"):
        val = getattr(eg, attr, None)
        if val and str(val).strip():
            return str(val).strip()
    numb = getattr(eg, "numb", None)
    if numb is not None:
        return f"numb={numb}"
    return "—"


def _primary_station(
    eg_id: int | None,
    eg_to_stations: dict[int, list[tuple[Any, Any]]],
) -> tuple[Any, str] | None:
    if eg_id is None:
        return None
    stations = eg_to_stations.get(eg_id) or []
    if not stations:
        return None
    st_id, st_name = stations[0][0], stations[0][1]
    return (st_id, (st_name or "—"))


def _sort_group_blocks(group_blocks: list[dict]) -> list[dict]:
    def key(gb: dict):
        eg = gb.get("equipment_group")
        # Родитель (итог «…, всего») сверху, дети ниже.
        parent_first = 0 if is_composite_parent_group(eg) else 1
        child = 0 if is_composite_child_group(eg) else 1
        return (
            parent_first,
            child,
            (_eg_label(eg) or "").lower(),
            getattr(eg, "id", 0) or 0,
        )

    return sorted(group_blocks, key=key)


def assign_display_cluster_key(
    eg: Any,
    *,
    numb_to_egs: dict[int, list[Any]],
    eg_to_stations: dict[int, list[tuple[Any, Any]]],
    allow_station_composite_fallback: bool,
    child_mains: set[int] | None = None,
) -> tuple[str, ClusterKind]:
    """
    Возвращает (cluster_key, kind).
    cluster_key стабилен внутри одной РЭС-выборки.

    Родитель comp=1 без детей в текущей выборке — обычный station/standalone бакет
    (не composite:{numb}), иначе соседние EG той же Station оказываются в другом
    кластере с тем же station_id/name и дублируются при пагинации.
    """
    if eg is None:
        return ("standalone:none", "standalone")

    eg_id = getattr(eg, "id", None)
    if is_composite_child_group(eg):
        main = _as_int(getattr(eg, "main", None))
        return (f"composite:{main}", "composite")

    if is_composite_parent_group(eg):
        numb = _as_int(getattr(eg, "numb", None))
        if numb is not None and child_mains is not None and numb in child_mains:
            return (f"composite:{numb}", "composite")
        if numb is not None and child_mains is None:
            # Обратная совместимость вызовов без child_mains: ищем детей в numb_to_egs.
            has_kids = any(
                is_composite_child_group(other)
                and _as_int(getattr(other, "main", None)) == numb
                for others in (numb_to_egs or {}).values()
                for other in others
            )
            if has_kids:
                return (f"composite:{numb}", "composite")
        # Одиночный comp=1 — fall through к station/standalone.

    # Ребёнок с main, но родитель ещё не в выборке — всё равно кластер по main.
    if not is_main_empty(getattr(eg, "main", None)):
        main = _as_int(getattr(eg, "main", None))
        return (f"composite:{main}", "composite")

    st = _primary_station(eg_id, eg_to_stations)
    if st is not None:
        st_id, _ = st
        # Station-бакет для отображения; «составной» fallback — только флагом.
        kind: ClusterKind = "station"
        if allow_station_composite_fallback:
            kind = "station"
        return (f"station:{st_id}", kind)

    return (f"eg:{eg_id}", "standalone")


def build_display_clusters(
    group_blocks: Sequence[dict],
    eg_to_stations: dict[int, list[tuple[Any, Any]]] | None = None,
    *,
    allow_station_composite_fallback: bool = False,
    parent_by_numb: dict[int, Any] | None = None,
) -> list[dict]:
    """
    Группирует group_blocks в кластеры для station_blocks.

    parent_by_numb — EG-родители из БД (comp=1), которых может не быть в rows
    (нет FuelParam) — нужны для имени жёлтой «всего» и composite_parent_eg_id.
    """
    eg_to_stations = eg_to_stations or {}
    parent_by_numb = parent_by_numb or {}
    numb_to_egs: dict[int, list[Any]] = defaultdict(list)
    child_mains: set[int] = set()
    for gb in group_blocks:
        eg = gb.get("equipment_group")
        numb = _as_int(getattr(eg, "numb", None)) if eg is not None else None
        if numb is not None:
            numb_to_egs[numb].append(eg)
        if eg is not None and is_composite_child_group(eg):
            main = _as_int(getattr(eg, "main", None))
            if main is not None:
                child_mains.add(main)
    for numb, peg in parent_by_numb.items():
        if peg is not None and numb not in numb_to_egs:
            numb_to_egs[numb].append(peg)

    buckets: dict[str, list[dict]] = defaultdict(list)
    kinds: dict[str, ClusterKind] = {}
    for gb in group_blocks:
        eg = gb.get("equipment_group")
        key, kind = assign_display_cluster_key(
            eg,
            numb_to_egs=numb_to_egs,
            eg_to_stations=eg_to_stations,
            allow_station_composite_fallback=allow_station_composite_fallback,
            child_mains=child_mains,
        )
        buckets[key].append(gb)
        kinds[key] = kind

    clusters: list[dict] = []
    for key, gbs in buckets.items():
        gbs = _sort_group_blocks(list(gbs))
        egs = [gb.get("equipment_group") for gb in gbs if gb.get("equipment_group")]
        parent_eg = next((eg for eg in egs if is_composite_parent_group(eg)), None)
        if parent_eg is None:
            for eg in egs:
                if is_composite_child_group(eg):
                    main = _as_int(getattr(eg, "main", None))
                    if main is None:
                        continue
                    cand = parent_by_numb.get(main)
                    if cand is not None:
                        parent_eg = cand
                        break
                    for c in numb_to_egs.get(main) or []:
                        if is_composite_parent_group(c) or (
                            is_main_empty(getattr(c, "main", None))
                            and _as_int(getattr(c, "comp", None)) == 1
                        ):
                            parent_eg = c
                            break
                    if parent_eg is not None:
                        break

        kind = kinds.get(key, "standalone")
        # Составная витрина только при наличии детей (main>0).
        # Одиночный comp=1 без детей — обычная станция.
        has_children = any(is_composite_child_group(eg) for eg in egs)
        treat_as_composite = has_children or (
            allow_station_composite_fallback
            and kind == "station"
            and len(gbs) > 1
        )

        station_id = None
        station_name = "—"
        if parent_eg is not None:
            station_name = _eg_label(parent_eg)
            st = _primary_station(getattr(parent_eg, "id", None), eg_to_stations)
            if st:
                station_id = st[0]
        if station_id is None:
            for eg in egs:
                st = _primary_station(getattr(eg, "id", None), eg_to_stations)
                if st:
                    station_id, st_name = st
                    if parent_eg is None:
                        station_name = st_name
                    break
        if parent_eg is None and (not station_name or station_name == "—") and egs:
            station_name = _eg_label(egs[0])

        clusters.append(
            {
                "cluster_key": key,
                "cluster_kind": kind,
                "group_blocks": gbs,
                "station_id": station_id,
                "station_name": station_name,
                "composite_parent_eg_id": getattr(parent_eg, "id", None)
                if parent_eg is not None
                else None,
                "treat_as_composite": treat_as_composite,
            }
        )

    def sort_key(c: dict):
        return (
            1 if c.get("station_id") is None and c.get("cluster_kind") == "standalone" else 0,
            (c.get("station_name") or "").lower(),
            c.get("station_id") or 0,
            c.get("cluster_key") or "",
        )

    return sorted(clusters, key=sort_key)


def build_station_blocks_from_group_items(
    eg_items: Iterable[tuple[Any, list]],
    eg_to_stations: dict[int, list[tuple[Any, Any]]],
    *,
    allow_station_composite_fallback: bool = False,
    use_equipment_group_hierarchy_only: bool = False,
    standalone_eg_ids: set | None = None,
    should_suppress_summary: Callable[..., bool] | None = None,
    parent_by_numb: dict[int, Any] | None = None,
) -> list[dict]:
    """
    eg_items: iterable of (eg_id, eg_rows) where eg_rows = [(eg, param), ...].
    Возвращает заготовки station_blocks (без station_summary / enrich).
    """
    standalone_eg_ids = standalone_eg_ids or set()
    if use_equipment_group_hierarchy_only:
        group_blocks = []
        for _eg_id, eg_rows in eg_items:
            eg = eg_rows[0][0] if eg_rows else None
            group_blocks.append({"equipment_group": eg, "rows": eg_rows})
        return [
            {
                "station_id": None,
                "station_name": "—",
                "group_blocks": group_blocks,
                "station_summary": {},
                "is_virtual": True,
                "suppress_station_summary": True,
                "cluster_key": "virtual",
                "cluster_kind": "standalone",
                "composite_parent_eg_id": None,
                "treat_as_composite": False,
            }
        ]

    group_blocks = []
    for eg_id, eg_rows in eg_items:
        eg = eg_rows[0][0] if eg_rows else None
        group_blocks.append({"equipment_group": eg, "rows": eg_rows})

    clusters = build_display_clusters(
        group_blocks,
        eg_to_stations,
        allow_station_composite_fallback=allow_station_composite_fallback,
        parent_by_numb=parent_by_numb,
    )

    station_blocks = []
    for c in clusters:
        st_id = c["station_id"]
        st_name = c["station_name"]
        gbs = c["group_blocks"]
        suppress = False
        if should_suppress_summary is not None:
            suppress = bool(
                should_suppress_summary(st_id, st_name, gbs, standalone_eg_ids)
            )
        station_blocks.append(
            {
                "station_id": st_id,
                "station_name": st_name,
                "group_blocks": gbs,
                "station_summary": {},
                "is_virtual": False,
                "suppress_station_summary": suppress,
                "cluster_key": c["cluster_key"],
                "cluster_kind": c["cluster_kind"],
                "composite_parent_eg_id": c["composite_parent_eg_id"],
                "treat_as_composite": c["treat_as_composite"],
            }
        )
    return station_blocks


def apply_simple_station_summaries(
    station_blocks: list[dict],
    compute_summary: Callable[[list], dict],
    *,
    parent_by_numb: dict[int, Any] | None = None,
    allow_station_composite_fallback: bool = False,
) -> list[dict]:
    """
    Итог составной станции — на строке родителя («…, всего»), как на fuel_params.
    Отдельную жёлтую «станция, всего» для composites подавляет.
    """
    from app.fuel.services.equipment_groups.composite_hierarchy_enrich_services import (
        enrich_station_blocks_composite_display,
    )

    return enrich_station_blocks_composite_display(
        station_blocks,
        compute_summary,
        parent_by_numb=parent_by_numb,
        allow_station_composite_fallback=allow_station_composite_fallback,
        fuel_params_detail_mode=False,
    )
