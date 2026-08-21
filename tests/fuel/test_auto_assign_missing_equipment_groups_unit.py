# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import patch

from app.fuel.services.equipment_groups.auto_assign_missing_equipment_groups_services import (
    apply_auto_assign_to_machines,
)


def test_auto_assign_skips_machines_without_type_when_sync_cannot_infer():
    machine = SimpleNamespace(id=1, id_equipment_group=None, database_version_id=46)
    with (
        patch(
            "app.fuel.services.equipment_groups.auto_assign_missing_equipment_groups_services._get_machine_fuel_param",
            return_value=None,
        ),
        patch(
            "app.fuel.services.equipment_groups.auto_assign_missing_equipment_groups_services.sync_machine_fuel_equipment_group",
            return_value=None,
        ) as sync,
        patch(
            "app.fuel.services.equipment_groups.auto_assign_missing_equipment_groups_services.get_current_db_version_id",
            return_value=46,
        ),
    ):
        summary = apply_auto_assign_to_machines([machine])

    assert summary["skipped_no_type"] == 1
    assert summary["assigned"] == 0
    sync.assert_called_once_with(machine, version_id=46)


def test_auto_assign_fills_type_when_sync_infers_it():
    machine = SimpleNamespace(id=62802, id_equipment_group=None, database_version_id=37)
    mfp = SimpleNamespace(equipment_group_id=17380)
    new_group = SimpleNamespace(id=17380, name="ТЭЦ (кот<90 ата)")

    def _sync(machine_obj, version_id=None):
        machine_obj.id_equipment_group = 1060
        return new_group

    with (
        patch(
            "app.fuel.services.equipment_groups.auto_assign_missing_equipment_groups_services._get_machine_fuel_param",
            return_value=mfp,
        ),
        patch(
            "app.fuel.services.equipment_groups.auto_assign_missing_equipment_groups_services.sync_machine_fuel_equipment_group",
            side_effect=_sync,
        ),
        patch(
            "app.fuel.services.equipment_groups.auto_assign_missing_equipment_groups_services.get_current_db_version_id",
            return_value=37,
        ),
    ):
        summary = apply_auto_assign_to_machines([machine])

    assert summary["assigned"] == 1
    assert summary["skipped_no_type"] == 0
    assert machine.id_equipment_group == 1060


def test_auto_assign_calls_same_sync_as_machine_details_save():
    machine = SimpleNamespace(
        id=62384, id_equipment_group=1310, database_version_id=46
    )
    mfp = SimpleNamespace(equipment_group_id=None)
    new_group = SimpleNamespace(id=9001, name="ТЭЦ-3 (турбина)")

    with (
        patch(
            "app.fuel.services.equipment_groups.auto_assign_missing_equipment_groups_services._get_machine_fuel_param",
            return_value=mfp,
        ),
        patch(
            "app.fuel.services.equipment_groups.auto_assign_missing_equipment_groups_services.sync_machine_fuel_equipment_group",
            return_value=new_group,
        ) as sync,
        patch(
            "app.fuel.services.equipment_groups.auto_assign_missing_equipment_groups_services.get_current_db_version_id",
            return_value=46,
        ),
    ):
        summary = apply_auto_assign_to_machines([machine])

    sync.assert_called_once_with(machine, version_id=46)
    assert summary["assigned"] == 1
    assert summary["failed"] == 0
    assert "турбина" in summary["details"][0]
