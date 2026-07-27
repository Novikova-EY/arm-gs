# -*- coding: utf-8 -*-
"""Права доступа к модулю «Нагрузки» (power_demand)."""

from __future__ import annotations

# Коды ролей (Role.name), по аналогии с fuel-admin / generation-admin.
POWER_DEMAND_EDIT_ROLE_NAMES = frozenset(
    {
        "admin",
        "load-admin",
        "load-editor",
        "load_admin",
        "load_editor",
        "Нагрузки-админ",
        "Нагрузки-редактор",
    }
)

# Отображаемые имена (Role.name_full), как в UI управления пользователями.
POWER_DEMAND_EDIT_ROLE_FULL_NAMES = frozenset(
    {
        "Нагрузки-админ",
        "Нагрузки-редактор",
    }
)


def can_edit_power_demand(user) -> bool:
    """Редактирование, формулы и «Проверка» — для Нагрузки-админ/редактор и admin."""
    if not getattr(user, "is_authenticated", False):
        return False
    for role in getattr(user, "roles", []) or []:
        name = (getattr(role, "name", None) or "").strip()
        name_full = (getattr(role, "name_full", None) or "").strip()
        if name in POWER_DEMAND_EDIT_ROLE_NAMES or name_full in POWER_DEMAND_EDIT_ROLE_FULL_NAMES:
            return True
    return False
