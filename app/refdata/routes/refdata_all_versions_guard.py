# -*- coding: utf-8 -*-
"""Проверки доступа к операциям «во всех версиях БД» в разделе справочников."""

from flask import flash, request


def all_versions_requested() -> bool:
    return request.values.get("all_versions") == "1"


def block_all_versions_without_admin(current_user) -> bool:
    """
    True — запрос следует заблокировать (нужен redirect и flash).
    """
    if not all_versions_requested():
        return False
    if getattr(current_user, "has_admin", False):
        return False
    flash(
        "Операции во всех версиях базы данных доступны только пользователям с ролью администратора.",
        "danger",
    )
    return True
