# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.fuel.services.equipment_groups.equipment_group_machines_services import (
    resolve_equipment_group_ids_for_machines,
)
from app.fuel.services.equipment_groups.equipment_group_rebind_services import (
    _ensure_machine_fuel_param,
    _get_machine_fuel_param,
    apply_inferred_equipment_group_type_to_machine,
    composite_cluster_lookup_keys,
    format_equipment_group_choice_label,
    infer_equipment_group_type_id_for_station_group,
    rebind_machine_to_equipment_group,
    rebind_source_group_machines,
)


def test_format_choice_label_includes_numb_and_composite_marker():
    parent = SimpleNamespace(
        id=13130, numb=81, name="ТЭЦ ПГУ ГСР Энерго (ПГУ-ТЭЦ)", name_ext=None, main=None, comp=1
    )
    child = SimpleNamespace(
        id=30052, numb=1502, name="ТЭЦ Ижорского з-да(тепл)", name_ext=None, main=81, comp=None
    )
    assert format_equipment_group_choice_label(parent) == (
        "81 — ТЭЦ ПГУ ГСР Энерго (ПГУ-ТЭЦ) (составная)"
    )
    assert format_equipment_group_choice_label(child) == "1502 — ТЭЦ Ижорского з-да(тепл)"


def test_composite_cluster_lookup_keys_from_parent_and_child():
    parent = SimpleNamespace(id=1, numb=81, main=None, comp=1)
    child = SimpleNamespace(id=2, numb=1502, main=81, comp=None)
    parent_numbs, child_mains = composite_cluster_lookup_keys([parent, child])
    assert parent_numbs == {81}
    assert child_mains == {81}


def test_resolve_equipment_group_ids_keeps_parent_and_children():
    parent = SimpleNamespace(id=13130, comp=1)
    members = [
        {"equipment_group": SimpleNamespace(id=30052)},
        {"equipment_group": SimpleNamespace(id=30053)},
    ]
    assert resolve_equipment_group_ids_for_machines(parent, members) == [13130, 30052, 30053]
    assert resolve_equipment_group_ids_for_machines(parent, []) == [13130]
    assert resolve_equipment_group_ids_for_machines(None, members) == []


def test_rebind_machine_sets_group_and_numb1120():
    machine = SimpleNamespace(id=22656, id_station=6479, id_equipment_group=355)
    target = SimpleNamespace(id=30052, numb=1502, name="child", name_ext=None, main=81, comp=None)
    mfp = SimpleNamespace(equipment_group_id=13130, numb1120=81)

    with patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.EquipmentGroup"
    ) as eg_cls, patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.ensure_equipment_group_linked_to_station"
    ) as ensure_link, patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services._ensure_machine_fuel_param",
        return_value=mfp,
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.db"
    ) as db_mock:
        eg_cls.query.get.return_value = target
        result = rebind_machine_to_equipment_group(
            machine=machine,
            target_group_id=30052,
            version_id=20,
        )

    ensure_link.assert_called_once_with(
        equipment_group_id=30052,
        station_id=6479,
        version_id=20,
        equipment_group_type_id=355,
    )
    assert mfp.equipment_group_id == 30052
    assert mfp.numb1120 == 1502
    db_mock.session.add.assert_called_once_with(mfp)
    assert result["changed"] is True
    assert result["old_group_id"] == 13130
    assert result["new_group_id"] == 30052


def test_infer_type_returns_unique_station_group_type():
    query = MagicMock()
    query.join.return_value = query
    query.filter.return_value = query
    query.distinct.return_value = query
    query.all.return_value = [(1060,)]

    with patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.db"
    ) as db_mock:
        db_mock.session.query.return_value = query
        assert infer_equipment_group_type_id_for_station_group(
            station_id=28547,
            equipment_group_id=17380,
            version_id=37,
        ) == 1060


def test_infer_type_returns_none_when_several_types():
    query = MagicMock()
    query.join.return_value = query
    query.filter.return_value = query
    query.distinct.return_value = query
    query.all.return_value = [(1060,), (1061,)]

    with patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.db"
    ) as db_mock:
        db_mock.session.query.return_value = query
        assert infer_equipment_group_type_id_for_station_group(
            station_id=28547,
            equipment_group_id=None,
            version_id=37,
        ) is None


def test_apply_inferred_type_skips_when_already_set():
    machine = SimpleNamespace(id=1, id_station=10, id_equipment_group=355)
    with patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.infer_equipment_group_type_id_for_station_group"
    ) as infer:
        assert apply_inferred_equipment_group_type_to_machine(
            machine, version_id=37, equipment_group_id=17380
        ) is None
    infer.assert_not_called()
    assert machine.id_equipment_group == 355


def test_rebind_machine_fills_missing_equipment_group_type():
    machine = SimpleNamespace(id=62802, id_station=28547, id_equipment_group=None)
    target = SimpleNamespace(id=17380, numb=55, name="TES", name_ext=None, main=None, comp=None)
    mfp = SimpleNamespace(equipment_group_id=17380, numb1120=55)

    def _fill_type(machine_obj, *, version_id, equipment_group_id=None):
        machine_obj.id_equipment_group = 1060
        return 1060

    with patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.EquipmentGroup"
    ) as eg_cls, patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.ensure_equipment_group_linked_to_station"
    ) as ensure_link, patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.apply_inferred_equipment_group_type_to_machine",
        side_effect=_fill_type,
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services._ensure_machine_fuel_param",
        return_value=mfp,
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.db"
    ):
        eg_cls.query.get.return_value = target
        result = rebind_machine_to_equipment_group(
            machine=machine,
            target_group_id=17380,
            version_id=37,
        )

    assert machine.id_equipment_group == 1060
    assert result["changed"] is True
    assert result["inferred_type_id"] == 1060
    assert ensure_link.call_count == 2


def test_rebind_source_group_rejects_target_outside_cluster():
    source = SimpleNamespace(id=13130, numb=81, name="parent", name_ext=None, main=None, comp=1)
    target = SimpleNamespace(id=99, numb=1, name="other", name_ext=None, main=None, comp=None)

    with patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.EquipmentGroup"
    ) as eg_cls, patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.get_rebind_target_choices_for_group",
        return_value=[(30052, "1502 — child")],
    ):
        eg_cls.query.get.side_effect = lambda gid: {13130: source, 99: target}.get(gid)
        result = rebind_source_group_machines(
            source_group_id=13130,
            target_group_id=99,
            version_id=20,
        )

    assert "не входит в составной кластер" in result["error"]


def test_get_machine_fuel_param_falls_back_to_existing_row_other_version():
    existing = SimpleNamespace(id=1, machine_id=22358, database_version_id=None)
    exact_q = MagicMock()
    exact_q.first.return_value = None
    by_machine = MagicMock()
    by_machine.filter.return_value = exact_q
    by_machine.first.return_value = existing
    query = MagicMock()
    query.filter.return_value = by_machine

    with patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.MachineFuelParam"
    ) as mfp_cls:
        mfp_cls.query = query
        row = _get_machine_fuel_param(22358, 20)

    assert row is existing
    by_machine.filter.assert_called_once()
    by_machine.first.assert_called_once()


def test_ensure_machine_fuel_param_reuses_row_and_aligns_version():
    existing = SimpleNamespace(machine_id=22358, database_version_id=None)

    with patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services._get_machine_fuel_param",
        return_value=existing,
    ), patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.db"
    ) as db_mock, patch(
        "app.fuel.services.equipment_groups.equipment_group_rebind_services.MachineFuelParam"
    ) as mfp_cls:
        row = _ensure_machine_fuel_param(22358, 20)

    assert row is existing
    assert existing.database_version_id == 20
    db_mock.session.add.assert_called_once_with(existing)
    mfp_cls.assert_not_called()
