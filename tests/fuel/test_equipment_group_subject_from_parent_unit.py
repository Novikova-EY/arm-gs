# -*- coding: utf-8 -*-
from types import SimpleNamespace
from unittest.mock import patch

from app.fuel.models.fue_equipment_group_model import EquipmentGroup


def test_apply_regional_ids_from_parent_copies_subject_and_res():
    child = SimpleNamespace(
        main=81,
        database_version_id=20,
        regional_district_id=None,
        regional_energy_system_id=None,
        obl=None,
    )
    parent = SimpleNamespace(
        regional_district_id=111,
        regional_energy_system_id=222,
        obl=78,
    )
    with patch(
        "app.fuel.models.fue_equipment_group_model.coerce_regional_district_id_for_db_version",
        side_effect=lambda pk, vid: pk,
    ), patch(
        "app.fuel.models.fue_equipment_group_model.coerce_regional_energy_system_id_for_db_version",
        side_effect=lambda pk, vid: pk,
    ):
        assert EquipmentGroup._apply_regional_ids_from_parent(child, parent=parent) is True
    assert child.regional_district_id == 111
    assert child.regional_energy_system_id == 222
    assert child.obl == 78


def test_apply_regional_ids_from_parent_without_parent_is_false():
    child = SimpleNamespace(main=81, database_version_id=20)
    child._find_composite_parent = lambda: None
    assert EquipmentGroup._apply_regional_ids_from_parent(child) is False


def test_populate_regional_ids_prefers_parent_over_station():
    child = SimpleNamespace(
        id=30052,
        main=81,
        database_version_id=20,
        regional_district_id="stale",
        regional_energy_system_id="stale",
        obl=None,
        equipment_group_links_v2=["should-not-be-used"],
    )

    def _from_parent(parent=None):
        child.regional_district_id = 111
        child.regional_energy_system_id = 222
        return True

    child._apply_regional_ids_from_parent = _from_parent
    EquipmentGroup._populate_regional_ids(child)
    assert child.regional_district_id == 111
    assert child.regional_energy_system_id == 222
