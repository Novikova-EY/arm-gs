# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import patch

from app.fuel.services.equipment_groups.equipment_group_set_services import (
    compose_equipment_group_name,
    resolve_auto_equipment_group_name,
    apply_auto_equipment_group_name,
)


def test_compose_equipment_group_name_basic_and_new_suffix():
    station = SimpleNamespace(name="Архангельская ТЭЦ")
    group_type = SimpleNamespace(name="ТЭЦ-130 ата")
    assert compose_equipment_group_name(station, group_type) == (
        "Архангельская ТЭЦ (ТЭЦ-130 ата)"
    )
    assert compose_equipment_group_name(
        station, group_type, is_new_group=True
    ) == "Архангельская ТЭЦ (ТЭЦ-130 ата) (нов)"
    assert compose_equipment_group_name(None, group_type) is None
    assert compose_equipment_group_name(station, None) is None


def test_resolve_keeps_manual_name():
    suggested = "Станция А (Тип 1)"
    assert (
        resolve_auto_equipment_group_name(
            suggested=suggested,
            old_name="Моё ручное имя",
            submitted_name="Моё ручное имя",
            old_suggested=suggested,
        )
        is None
    )


def test_resolve_updates_when_name_was_auto_and_unchanged():
    old_suggested = "Станция А (Тип 1)"
    new_suggested = "Станция А (Тип 2)"
    assert (
        resolve_auto_equipment_group_name(
            suggested=new_suggested,
            old_name=old_suggested,
            submitted_name=old_suggested,
            old_suggested=old_suggested,
        )
        == new_suggested
    )


def test_resolve_fills_empty_and_force():
    suggested = "Станция А (Тип 1)"
    assert (
        resolve_auto_equipment_group_name(
            suggested=suggested,
            old_name="",
            submitted_name="",
        )
        == suggested
    )
    assert (
        resolve_auto_equipment_group_name(
            suggested=suggested,
            old_name="Что угодно",
            submitted_name="Что угодно",
            force=True,
        )
        == suggested
    )


def test_apply_auto_equipment_group_name_sets_group():
    group = SimpleNamespace(id=17280, name="старое")
    with patch(
        "app.fuel.services.equipment_groups.equipment_group_set_services."
        "suggested_equipment_group_name",
        return_value="Архангельская ТЭЦ (ТЭЦ-130 ата)",
    ):
        applied = apply_auto_equipment_group_name(
            group,
            force=True,
            old_name="старое",
        )
    assert applied == "Архангельская ТЭЦ (ТЭЦ-130 ата)"
    assert group.name == "Архангельская ТЭЦ (ТЭЦ-130 ата)"
