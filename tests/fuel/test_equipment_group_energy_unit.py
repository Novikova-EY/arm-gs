from pathlib import Path

import pytest
from flask import Flask, g
from jinja2 import Environment
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

import app.electrical_intensity.models  # noqa: F401 – связи Year
import app.energy_consumption.models  # noqa: F401 – связи Year
import app.power_demand.models  # noqa: F401 – связи Year
import app.economics.models  # noqa: F401 – связи Year
import app.territories.models  # noqa: F401 – связи Year
import app.ecology.models  # noqa: F401 – связи Year
import app.energy_balance.models  # noqa: F401 – связи Year
from app.extensions import db
from app.common.models.database_version_model import DatabaseVersion
from app.fuel.services.equipment_groups.equipment_group_merge_services import (
    update_equipment_group_all_versions,
)
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.services.equipment_groups.equipment_group_edit_services import (
    update_equipment_group_from_form,
)
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.regional_district_regional_energy_system_model import (
    regional_district_regional_energy_system,
)
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from config import SCHEMA_FUEL, SCHEMA_REFDATA


@pytest.fixture
def energy_unit_session(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        for schema in {SCHEMA_FUEL, SCHEMA_REFDATA}:
            conn.exec_driver_sql(f'ATTACH DATABASE ":memory:" AS "{schema}"')
        for model in (EnergyUnit, RegionalDistrict, RegionalEnergySystem, EquipmentGroup, DatabaseVersion):
            model.__table__.create(conn)
        regional_district_regional_energy_system.create(conn)
        conn.execute(DatabaseVersion.__table__.insert(), [
            {"id": 1, "version_number": 1}, {"id": 2, "version_number": 2},
        ])
        conn.execute(RegionalDistrict.__table__.insert(), {
            "id": 10, "name": "District", "name_full": "District",
            "name_rp": "District", "name_dp": "District", "database_version_id": 1,
        })
        for system_id, name in ((5, "не указано"), (6, "District system"), (7, "Other system")):
            conn.execute(RegionalEnergySystem.__table__.insert(), {
                "id": system_id, "name": name, "name_full": name, "name_rp": name,
                "database_version_id": 1,
            })
        conn.execute(regional_district_regional_energy_system.insert(), {
            "regional_district_id": 10, "regional_energy_system_id": 6,
        })
        conn.execute(EquipmentGroup.__table__.insert(), {
            "id": 1, "external_code": "group", "name": "Group",
            "database_version_id": 1, "regional_district_id": 10,
        })
        for unit_id, district_id, version, ref_uuid in (
            (101, 10, 1, "unit-a"), (102, 10, 1, "unit-b"),
            (103, 20, 1, "other-district"), (201, 30, 2, "unit-a"),
        ):
            conn.execute(EnergyUnit.__table__.insert(), {
                "id": unit_id, "name": f"Unit {unit_id}", "name_rp": "Unit",
                "name_dp": "Unit", "id_regional_district": district_id,
                "id_regional_energy_system": 5, "database_version_id": version,
                "ref_uuid": ref_uuid,
            })
    session = scoped_session(sessionmaker(bind=engine))
    monkeypatch.setattr(db, "session", session)
    from app.fuel.services.equipment_groups import equipment_group_set_services
    monkeypatch.setattr(equipment_group_set_services, "suggested_equipment_group_name", lambda *a, **k: None)
    monkeypatch.setattr(equipment_group_set_services, "apply_auto_equipment_group_name", lambda *a, **k: None)
    with Flask(__name__).test_request_context('/'):
        g.current_db_version = 1
        yield session
    session.remove()
    engine.dispose()


def test_energy_unit_selection_can_be_saved_changed_and_cleared(energy_unit_session):
    for value, expected in (("101", 101), ("102", 102), ("", None)):
        success, message, changes, target_id = update_equipment_group_from_form(
            1, {"energy_unit_id": value}
        )
        assert success, message
        energy_unit_session.expire_all()
        assert energy_unit_session.get(EquipmentGroup, target_id).energy_unit_id == expected
        assert any(label == "Энергорайон" for label, _, _ in changes)


@pytest.mark.parametrize("value", ["invalid", "9999", "103"])
def test_invalid_energy_unit_does_not_overwrite_saved_choice(energy_unit_session, value):
    assert update_equipment_group_from_form(1, {"energy_unit_id": "101"})[0]
    success, _, _, _ = update_equipment_group_from_form(1, {"energy_unit_id": value})
    assert not success
    energy_unit_session.expire_all()
    assert energy_unit_session.get(EquipmentGroup, 1).energy_unit_id == 101


def test_energy_unit_from_another_version_is_resolved_by_ref_uuid(energy_unit_session):
    success, message, _, _ = update_equipment_group_from_form(1, {"energy_unit_id": "201"})
    assert success, message
    assert energy_unit_session.get(EquipmentGroup, 1).energy_unit_id == 101


def test_all_versions_save_resolves_energy_unit_and_supports_clear(energy_unit_session):
    energy_unit_session.execute(EquipmentGroup.__table__.insert(), {
        "id": 2, "external_code": "group", "name": "Group",
        "database_version_id": 2, "regional_district_id": 30,
    })
    energy_unit_session.commit()
    result = update_equipment_group_all_versions(
        equipment_group_id=1, form_data={"energy_unit_id": "101"}
    )
    assert "error" not in result
    energy_unit_session.commit()
    energy_unit_session.expire_all()
    assert energy_unit_session.get(EquipmentGroup, 1).energy_unit_id == 101
    assert energy_unit_session.get(EquipmentGroup, 2).energy_unit_id == 201
    result = update_equipment_group_all_versions(
        equipment_group_id=1, form_data={"energy_unit_id": ""}
    )
    assert "error" not in result
    energy_unit_session.commit()
    energy_unit_session.expire_all()
    assert energy_unit_session.get(EquipmentGroup, 1).energy_unit_id is None
    assert energy_unit_session.get(EquipmentGroup, 2).energy_unit_id is None


def test_clearing_subject_also_clears_energy_unit(energy_unit_session):
    assert update_equipment_group_from_form(1, {"energy_unit_id": "101"})[0]
    assert update_equipment_group_from_form(1, {"regional_district_id": ""})[0]
    energy_unit_session.expire_all()
    assert energy_unit_session.get(EquipmentGroup, 1).energy_unit_id is None


def test_all_versions_rejects_energy_unit_of_another_subject(energy_unit_session):
    result = update_equipment_group_all_versions(
        equipment_group_id=1, form_data={"energy_unit_id": "103"}
    )
    assert result.get("error")
    assert energy_unit_session.get(EquipmentGroup, 1).energy_unit_id is None


@pytest.mark.parametrize("all_versions", [False, True])
@pytest.mark.parametrize("system_id", [None, 5, 7])
@pytest.mark.parametrize("include_system_in_form", [False, True])
def test_energy_unit_changes_preserve_energy_system(
    energy_unit_session, all_versions, system_id, include_system_in_form
):
    energy_unit_session.execute(
        EquipmentGroup.__table__.update().where(EquipmentGroup.id == 1)
        .values(regional_energy_system_id=system_id)
    )
    energy_unit_session.commit()
    for unit_value, expected_unit in (("101", 101), ("102", 102), ("", None)):
        form_data = {"regional_district_id": "10", "energy_unit_id": unit_value}
        if include_system_in_form:
            form_data["regional_energy_system_id"] = str(system_id) if system_id else ""
        if all_versions:
            result = update_equipment_group_all_versions(
                equipment_group_id=1, form_data=form_data
            )
            assert "error" not in result
            energy_unit_session.commit()
        else:
            success, message, _, _ = update_equipment_group_from_form(1, form_data)
            assert success, message
        energy_unit_session.expire_all()
        group = energy_unit_session.get(EquipmentGroup, 1)
        assert group.energy_unit_id == expected_unit
        assert group.regional_energy_system_id == system_id


@pytest.mark.parametrize("all_versions", [False, True])
def test_energy_system_changes_preserve_energy_unit(energy_unit_session, all_versions):
    assert update_equipment_group_from_form(1, {"energy_unit_id": "101"})[0]
    for system_value, expected_system in (("5", 5), ("6", 6), ("7", 7), ("", None)):
        form_data = {"regional_energy_system_id": system_value}
        if all_versions:
            result = update_equipment_group_all_versions(
                equipment_group_id=1, form_data=form_data
            )
            assert "error" not in result
            energy_unit_session.commit()
        else:
            success, message, _, _ = update_equipment_group_from_form(1, form_data)
            assert success, message
        energy_unit_session.expire_all()
        group = energy_unit_session.get(EquipmentGroup, 1)
        assert group.regional_energy_system_id == expected_system
        assert group.energy_unit_id == 101


def test_unrelated_save_preserves_energy_unit(energy_unit_session):
    assert update_equipment_group_from_form(1, {"energy_unit_id": "101"})[0]
    assert update_equipment_group_from_form(1, {"note": "Updated"})[0]
    assert energy_unit_session.get(EquipmentGroup, 1).energy_unit_id == 101


@pytest.mark.parametrize("can_edit", [True, False])
def test_energy_unit_field_displays_saved_choice(energy_unit_session, can_edit):
    source = Path("app/templates/fuel/equipment_groups/equipment_group_edit.html").read_text(encoding="utf-8")
    start = source.index("{% set energy_units =")
    end = source.index("</div>", start) + len("</div>")
    template = Environment(autoescape=True).from_string(source[start:end])
    group = energy_unit_session.get(EquipmentGroup, 1)
    group.energy_unit_id = 102
    html = template.render(
        equipment_group=group, can_edit=can_edit,
        energy_units_by_regional_district={"10": [{"id": 101, "name": "Unit 101"}, {"id": 102, "name": "Unit 102"}]},
    )
    assert 'hidden' not in html
    if can_edit:
        assert '<select' in html
        assert 'value="102" selected' in html
        assert 'value="101"' in html
    else:
        assert '<select' not in html
        assert 'Unit 102' in html
    html = template.render(equipment_group=group, can_edit=can_edit, energy_units_by_regional_district={})
    assert 'hidden' in html
