# -*- coding: utf-8 -*-
"""Unit tests for energy_consumption role access helper."""

from types import SimpleNamespace

from app.energy_consumption.services.access_services import can_edit_energy_consumption


def _user(*roles):
    role_objs = []
    for item in roles:
        if isinstance(item, tuple):
            name, name_full = item
        else:
            name, name_full = item, item
        role_objs.append(SimpleNamespace(name=name, name_full=name_full))
    return SimpleNamespace(is_authenticated=True, roles=role_objs)


def test_guest_cannot_edit():
    user = _user(("Пользователь-гость", "Пользователь-гость"))
    assert can_edit_energy_consumption(user) is False


def test_load_admin_by_full_name_can_edit():
    user = _user(("load-admin", "Нагрузки-админ"))
    assert can_edit_energy_consumption(user) is True


def test_load_editor_by_full_name_can_edit():
    user = _user(("load-editor", "Нагрузки-редактор"))
    assert can_edit_energy_consumption(user) is True


def test_russian_name_only_can_edit():
    user = _user("Нагрузки-админ")
    assert can_edit_energy_consumption(user) is True


def test_system_admin_can_edit():
    user = _user(("admin", "Администратор"))
    assert can_edit_energy_consumption(user) is True


def test_demand_module_roles_cannot_edit_by_themselves():
    user = _user(("demand-admin", "Спрос-админ"))
    assert can_edit_energy_consumption(user) is False
    user = _user(("demand-editor", "Спрос-редактор"))
    assert can_edit_energy_consumption(user) is False


def test_load_reader_cannot_edit():
    user = _user(("load-reader", "Нагрузки-чтение"))
    assert can_edit_energy_consumption(user) is False


def test_other_module_admin_cannot_edit():
    user = _user(("generation-admin", "Генерация-админ"))
    assert can_edit_energy_consumption(user) is False


def test_anonymous_cannot_edit():
    user = SimpleNamespace(is_authenticated=False, roles=[])
    assert can_edit_energy_consumption(user) is False
