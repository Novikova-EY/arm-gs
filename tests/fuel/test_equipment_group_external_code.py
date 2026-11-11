from pathlib import Path
from types import SimpleNamespace

import pytest
from jinja2 import Environment

import app.rational_structure.models  # noqa: F401
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.services.equipment_groups.equipment_group_edit_services import (
    update_equipment_group_from_form,
)
from app.fuel.services.equipment_groups.equipment_group_merge_services import (
    update_equipment_group_all_versions,
)
from test_equipment_group_energy_unit import energy_unit_session  # noqa: F401


@pytest.fixture
def code_session(energy_unit_session, monkeypatch):
    monkeypatch.setattr(
        "flask_login.utils._get_user",
        lambda: SimpleNamespace(is_authenticated=True, is_admin=True),
    )
    energy_unit_session.execute(EquipmentGroup.__table__.insert(), [
        {"id": 2, "external_code": "group", "name": "Group", "database_version_id": 2},
        {"id": 3, "external_code": "legacy", "name": "Legacy", "database_version_id": None},
    ])
    energy_unit_session.commit()
    return energy_unit_session


def save_code(all_versions, code, group_id=1):
    form = {"external_code": code}
    if all_versions:
        result = update_equipment_group_all_versions(
            equipment_group_id=group_id, form_data=form
        )
        return not result.get("error"), result.get("error", ""), result.get("change_details", [])
    success, message, changes, _ = update_equipment_group_from_form(group_id, form)
    return success, message, changes


@pytest.mark.parametrize("all_versions", [False, True])
def test_external_code_save_uses_old_family_and_logs_change(code_session, all_versions):
    success, message, changes = save_code(all_versions, "  new-code  ")
    assert success, message
    code_session.commit()
    code_session.expire_all()
    assert code_session.get(EquipmentGroup, 1).external_code == "new-code"
    assert code_session.get(EquipmentGroup, 2).external_code == ("new-code" if all_versions else "group")
    assert ("external_code", "group", "new-code") in changes


@pytest.mark.parametrize("all_versions", [False, True])
@pytest.mark.parametrize("code", ["", "   ", "x" * 37])
def test_invalid_external_code_preserves_saved_data(code_session, all_versions, code):
    success, message, _ = save_code(all_versions, code)
    assert not success
    assert "external_code" in message
    code_session.commit()
    code_session.expire_all()
    assert code_session.get(EquipmentGroup, 1).external_code == "group"
    assert code_session.get(EquipmentGroup, 2).external_code == "group"


@pytest.mark.parametrize("all_versions", [False, True])
def test_external_code_is_admin_only(code_session, monkeypatch, all_versions):
    monkeypatch.setattr(
        "flask_login.utils._get_user",
        lambda: SimpleNamespace(is_authenticated=True, is_admin=False, has_admin=True),
    )
    success, message, _ = save_code(all_versions, "new-code")
    assert not success
    assert "администратору" in message
    assert code_session.get(EquipmentGroup, 1).external_code == "group"


@pytest.mark.parametrize("all_versions, conflict_version", [(False, 1), (True, 1), (True, 2)])
def test_conflicting_external_code_rejects_entire_save(code_session, all_versions, conflict_version):
    code_session.execute(EquipmentGroup.__table__.insert(), {
        "id": 4, "external_code": "taken", "name": "Other", "database_version_id": conflict_version,
    })
    code_session.commit()
    success, message, _ = save_code(all_versions, "taken")
    assert not success
    assert "id=4" in message
    code_session.commit()
    code_session.expire_all()
    assert code_session.get(EquipmentGroup, 1).external_code == "group"
    assert code_session.get(EquipmentGroup, 2).external_code == "group"


@pytest.mark.parametrize("all_versions", [False, True])
def test_unrelated_save_preserves_external_code(code_session, all_versions):
    if all_versions:
        result = update_equipment_group_all_versions(equipment_group_id=1, form_data={"note": "Updated"})
        assert not result.get("error")
    else:
        assert update_equipment_group_from_form(1, {"note": "Updated"})[0]
    code_session.commit()
    code_session.expire_all()
    assert code_session.get(EquipmentGroup, 1).external_code == "group"


def test_unchanged_code_does_not_replace_merge_target_code(code_session, monkeypatch):
    code_session.execute(EquipmentGroup.__table__.insert(), {
        "id": 4, "external_code": "target", "name": "Target", "database_version_id": 1,
    })
    code_session.commit()
    monkeypatch.setattr(
        "app.fuel.services.equipment_groups.equipment_group_edit_services._get_station_id_for_equipment_group",
        lambda *a: None,
    )
    monkeypatch.setattr(
        "app.fuel.services.equipment_groups.equipment_group_merge_services.rename_or_merge_equipment_group_for_station",
        lambda **k: {"merged": True, "primary_id": 4},
    )
    success, message, changes, target_id = update_equipment_group_from_form(
        1, {"name": "Target", "external_code": "group"}
    )
    assert success, message
    assert target_id == 4
    assert code_session.get(EquipmentGroup, 4).external_code == "target"
    assert not any(label == "external_code" for label, _, _ in changes)


@pytest.mark.parametrize("all_versions", [False, True])
def test_legacy_group_code_can_be_changed(code_session, all_versions):
    success, message, _ = save_code(all_versions, "x" * 36, group_id=3)
    assert success, message
    code_session.commit()
    code_session.expire_all()
    assert code_session.get(EquipmentGroup, 3).external_code == "x" * 36


def test_code_used_only_in_other_version_is_allowed(code_session):
    assert save_code(False, "legacy")[0]
    assert code_session.get(EquipmentGroup, 1).external_code == "legacy"


def test_legacy_version_conflict_is_rejected(code_session):
    code_session.execute(EquipmentGroup.__table__.insert(), {
        "id": 4, "external_code": "taken", "name": "Other", "database_version_id": None,
    })
    code_session.commit()
    success, message, _ = save_code(False, "taken", group_id=3)
    assert not success
    assert "id=4" in message
    assert code_session.get(EquipmentGroup, 3).external_code == "legacy"


@pytest.mark.parametrize("all_versions", [False, True])
def test_unchanged_code_is_allowed(code_session, all_versions):
    success, message, changes = save_code(all_versions, "group")
    assert success, message
    assert not any(label == "external_code" for label, _, _ in changes)


@pytest.mark.parametrize("role, visible, editable", [
    ("admin", True, True),
    ("fuel-admin", True, False),
    ("fuel-editor", True, False),
    ("generation-editor", True, False),
    ("fuel-reader", False, False),
    ("guest", False, False),
])
def test_external_code_field_permissions(role, visible, editable):
    source = Path("app/templates/fuel/equipment_groups/equipment_group_edit.html").read_text(encoding="utf-8")
    permissions = source[source.index("{% set can_edit_external_code"):source.index("{% set grouping_station_bindings")]
    start = source.index("{% if can_view_internal_ids %}")
    end = source.index("{% endif %}", source.index("</div>", start)) + len("{% endif %}")
    template = Environment(autoescape=True).from_string(permissions + source[start:end])
    html = template.render(
        current_user=SimpleNamespace(
            is_admin=role == "admin", has_admin=role in {"admin", "fuel-admin"}, role_names=[role],
        ),
        equipment_group=SimpleNamespace(external_code='code"<value>'),
    )
    assert ("external_code:" in html) == visible
    assert ('name="external_code"' in html) == editable
    if visible:
        assert "code&#34;&lt;value&gt;" in html
    if editable:
        assert 'maxlength="36"' in html
