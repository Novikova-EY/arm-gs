# -*- coding: utf-8 -*-
"""Unit tests: колонка «Группа оборудования» в полном Excel-экспорте — тип группы."""

from types import SimpleNamespace

from app.generation.services.station_services.export_station_services import (
    equipment_group_type_display_name,
    resolve_machine_equipment_group_label,
)


def test_type_display_name():
    assert equipment_group_type_display_name(SimpleNamespace(name="ТЭЦ-130 МВт")) == "ТЭЦ-130 МВт"
    assert equipment_group_type_display_name(SimpleNamespace(name="  ТЭЦ-КЭС  ")) == "ТЭЦ-КЭС"


def test_type_display_name_skips_unset():
    assert equipment_group_type_display_name(None) == "—"
    assert equipment_group_type_display_name(SimpleNamespace(name="")) == "—"
    assert equipment_group_type_display_name(SimpleNamespace(name="не указано")) == "—"


def test_resolve_uses_equipment_group_type_not_fuel_name():
    machine = SimpleNamespace(
        id=10,
        machine_group="",
        id_equipment_group=1055,
        equipment_group=SimpleNamespace(name="ТЭЦ-130 МВт"),
        machine_fuel_param=SimpleNamespace(
            equipment_group=SimpleNamespace(name="Кировская ТЭЦ-2", name_ext=None)
        ),
    )
    assert resolve_machine_equipment_group_label(machine) == "ТЭЦ-130 МВт"


def test_resolve_prefers_type_name_map():
    machine = SimpleNamespace(
        id=10,
        id_equipment_group=1289,
        equipment_group=None,
        machine_fuel_param=None,
    )
    assert resolve_machine_equipment_group_label(
        machine,
        type_names_by_id={1289: "ТЭЦ-КЭС"},
    ) == "ТЭЦ-КЭС"


def test_resolve_empty_without_type():
    machine = SimpleNamespace(
        id=10,
        machine_group="не тип",
        id_equipment_group=None,
        equipment_group=None,
        machine_fuel_param=SimpleNamespace(
            equipment_group=SimpleNamespace(name="Название группы")
        ),
    )
    assert resolve_machine_equipment_group_label(machine) == "—"
