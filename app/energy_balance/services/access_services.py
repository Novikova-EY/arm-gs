# -*- coding: utf-8 -*-
"""Права на изменение данных раздела балансов ЭЭ и мощности."""

_EDIT_ROLES = frozenset(
    {
        "admin",
        "generation-admin",
        "generation-editor",
        "generation_admin",
        "generation_editor",
        "Админ",
        "Генерация-админ",
        "Генерация-редактор",
    }
)


def can_edit_energy_balance(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if set(getattr(user, "role_names", None) or []) & _EDIT_ROLES:
        return True
    return any(
        (getattr(role, field, None) or "").strip() in _EDIT_ROLES
        for role in (getattr(user, "roles", None) or [])
        for field in ("name", "name_full")
    )
