"""Common sorting helpers (stable UI/export ordering)."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple


def fuel_type_object_sort_key(ft: Any) -> Tuple[Any, ...]:
    """
    Sort key for FuelType-like objects.

    Rules:
    - by display_order (NULLs last)
    - then by name (case-insensitive)
    - then by id
    """
    ft_id = getattr(ft, "id", None)
    display_order = getattr(ft, "display_order", None)
    name = getattr(ft, "name", None)

    return (
        display_order is None,
        display_order if display_order is not None else 0,
        (name or "").strip().lower(),
        ft_id if ft_id is not None else 0,
    )


def sort_fuel_type_objects(fuel_types: Iterable[Any]) -> List[Any]:
    """Sort iterable of FuelType-like objects using `fuel_type_object_sort_key`."""
    return sorted(list(fuel_types or []), key=fuel_type_object_sort_key)


def fuel_type_id_sort_key(
    fuel_type_id: Optional[int],
    *,
    id_to_display_order: Optional[Dict[int, Optional[int]]] = None,
    id_to_name: Optional[Dict[int, str]] = None,
) -> Tuple[Any, ...]:
    """
    Sort key for a FuelType ID.
    Useful when aggregated dicts come as {fuel_type_id: data}.
    """
    ft_id = int(fuel_type_id) if fuel_type_id is not None else -1
    display_order = None
    if id_to_display_order and ft_id in id_to_display_order:
        display_order = id_to_display_order.get(ft_id)
    name = ""
    if id_to_name and ft_id in id_to_name:
        name = (id_to_name.get(ft_id) or "").strip().lower()

    return (
        display_order is None,
        display_order if display_order is not None else 0,
        name,
        ft_id,
    )

