import importlib
from io import BytesIO
from types import SimpleNamespace

import pandas as pd
import pytest

from app.fuel.services.equipment_groups import composite_main_vs_station_reconciliation_services as parents
from app.fuel.services.fuel_imports import import_fuel_db_equipment_groups_services as fuel_db
from app.fuel.services.fuel_imports import soft_import_composite_flags_services as soft_import


@pytest.fixture
def registered_models(app):
    for module in (
        "app.power_demand.models", "app.economics.models", "app.electrical_intensity.models",
        "app.energy_consumption.models", "app.energy_balance.models", "app.territories.models",
        "app.ecology.models",
    ):
        importlib.import_module(module)


class _Query:
    def __init__(self, rows=()):
        self.rows = list(rows)

    def filter(self, *args):
        return self

    def filter_by(self, **kwargs):
        return self

    def order_by(self, *args):
        return self

    def distinct(self):
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class _Session:
    def __init__(self, groups=()):
        self.groups = groups
        self.added = []
        self.commits = 0

    def query(self, model):
        return _Query(self.groups if model is parents.EquipmentGroup else [])

    def add(self, obj):
        self.added.append(obj)

    def flush(self):
        for index, obj in enumerate(self.added, start=1):
            if obj.id is None:
                obj.id = index

    def commit(self):
        self.commits += 1


@pytest.mark.parametrize("version", [None, 0, -1, 999])
def test_fuel_db_import_rejects_missing_or_unknown_current_version(monkeypatch, version):
    buf = BytesIO()
    pd.DataFrame(columns=["id_station", "equipment_group"]).to_excel(buf, index=False)
    buf.seek(0)
    session = _Session()
    monkeypatch.setattr(fuel_db.db, "session", session)
    monkeypatch.setattr(fuel_db, "get_current_db_version_id", lambda: version)
    monkeypatch.setattr(
        fuel_db, "DatabaseVersion",
        SimpleNamespace(id=fuel_db.DatabaseVersion.id, query=_Query([SimpleNamespace(id=37)])),
    )

    with pytest.raises(ValueError, match="верси"):
        fuel_db.import_fuel_db_equipment_groups_from_excel(buf, "tester")
    assert session.added == []
    assert session.commits == 0


@pytest.mark.parametrize("version", [None, 0, -1, 999])
@pytest.mark.parametrize("kind", ["group", "station_link"])
def test_standalone_creation_requires_valid_version(monkeypatch, version, kind):
    session = _Session()
    monkeypatch.setattr(fuel_db.db, "session", session)
    with pytest.raises(ValueError, match="верси"):
        if kind == "group":
            fuel_db._find_or_create_standalone_equipment_group("Котельная", version, {37})
        else:
            fuel_db._find_or_create_kotelnaya_type_station_link(version, {37})
    assert session.added == []


def test_standalone_group_keeps_explicit_version(monkeypatch, registered_models):
    session = _Session()
    monkeypatch.setattr(fuel_db.db, "session", session)
    monkeypatch.setattr(fuel_db, "_standalone_equipment_group_query", lambda version: _Query())
    monkeypatch.setattr(fuel_db, "get_current_db_version_id", lambda: 20)

    group, created = fuel_db._find_or_create_standalone_equipment_group("Котельная", 37, {20, 37}, numb=1502)

    assert created
    assert session.added == [group]
    assert group.database_version_id == 37
    assert str(group.numb) == "1502"


def test_standalone_station_link_keeps_explicit_version(monkeypatch, registered_models):
    session = _Session()
    monkeypatch.setattr(fuel_db.EquipmentGroupSetStation, "query", _Query())
    monkeypatch.setattr(fuel_db.db, "session", session)
    monkeypatch.setattr(fuel_db, "_find_kotelnaya_equipment_group_type_for_version", lambda version: SimpleNamespace(id=5))
    monkeypatch.setattr(fuel_db, "get_current_db_version_id", lambda: 20)

    link, created = fuel_db._find_or_create_kotelnaya_type_station_link(37, {20, 37})

    assert created
    assert session.added == [link]
    assert link.database_version_id == 37
    assert link.equipment_group_type_id == 5
    assert link.station_id is None


@pytest.mark.parametrize("version", [None, 0, -1])
def test_parent_builder_rejects_unversioned_group(version):
    with pytest.raises(ValueError, match="верси"):
        parents._build_parent_eg(name="Parent", numb=10, ver=version, meta={}, donor=None)


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("legacy_version", [None, 0, -1])
def test_phase_a_skips_legacy_children_but_keeps_versioned_family(monkeypatch, registered_models, dry_run, legacy_version):
    legacy = SimpleNamespace(id=1, numb=11, main=10, comp=None, database_version_id=legacy_version)
    versioned = SimpleNamespace(id=2, numb=12, main=10, comp=None, database_version_id=37)
    session = _Session([legacy, versioned])
    monkeypatch.setattr(parents, "_resolve_station_for_parent", lambda kids, siblings, ver: (None, kids[0], "no_station"))
    monkeypatch.setattr(parents, "_parent_display_name", lambda donor, meta, sess: "Parent")

    result = parents.create_missing_parent_shells_from_children(
        session, dry_run=dry_run, excel_parents={"10": {"name": "Parent", "comp": 1}},
    )

    assert result.created_or_planned == 1
    assert [sample["database_version_id"] for sample in result.samples] == [37]
    assert any("верси" in warning for warning in result.warnings)
    assert [group.database_version_id for group in session.added] == ([] if dry_run else [37])
    assert legacy.database_version_id == legacy_version


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("versions", [[None, 0, -1, 20, 37], [None], []])
@pytest.mark.parametrize("explicit_versions", [True, False])
def test_phase_b_never_creates_or_plans_null_version(monkeypatch, registered_models, dry_run, versions, explicit_versions):
    session = _Session()
    monkeypatch.setattr(parents, "_distinct_eg_version_ids", lambda sess: versions)
    monkeypatch.setattr(parents, "_find_station_id_by_name", lambda sess, name, ver: None)

    result = parents.create_phase_b_comp1_parents_from_excel(
        session, dry_run=dry_run, excel_parents={"10": {"name": "Parent", "comp": 1}},
        version_ids=versions if explicit_versions else None,
    )

    expected = [ver for ver in versions if ver is not None and ver > 0]
    assert result.created_or_planned == len(expected)
    assert result.unique_parent_numbs == (1 if expected else 0)
    assert [sample["database_version_id"] for sample in result.samples] == expected[:1]
    assert [group.database_version_id for group in session.added] == ([] if dry_run else expected)
    if not expected:
        assert result.warnings
        assert result.planned_numbs == set()


@pytest.mark.parametrize("version", [None, 0, -1, 37])
def test_parent_station_link_requires_version(registered_models, version):
    session = _Session()
    parent = parents.EquipmentGroup(id=100, name="Parent", database_version_id=37)
    if version != 37:
        with pytest.raises(ValueError, match="верси"):
            parents._ensure_parent_set_on_station(session, parent, station_id=10, type_id=5, version_id=version)
        assert session.added == []
    else:
        parents._ensure_parent_set_on_station(session, parent, station_id=10, type_id=5, version_id=version)
        link, group_set = session.added
        assert link.database_version_id == parent.database_version_id == 37
        assert group_set.equipment_group_id == parent.id
        assert group_set.equipment_group_set_station_id == link.id


@pytest.mark.parametrize("dry_run", [True, False])
@pytest.mark.parametrize("phase_b", [True, False])
@pytest.mark.parametrize("target_version", [None, 0, -1, 37])
def test_soft_import_creates_only_versioned_groups(monkeypatch, registered_models, dry_run, phase_b, target_version):
    buf = BytesIO()
    pd.DataFrame([{"NUMB": 10, "NAME": "Parent", "COMP": 1}]).to_excel(buf, index=False)
    buf.seek(0)
    session = _Session()
    monkeypatch.setattr(parents, "_distinct_eg_version_ids", lambda sess: [None, 37])
    monkeypatch.setattr(parents, "_find_station_id_by_name", lambda sess, name, ver: None)
    monkeypatch.setattr("app.common.services.database_version_filter.get_current_db_version_id", lambda: target_version)
    monkeypatch.setattr(soft_import, "log_to_db", lambda *a, **kw: None)

    result = soft_import.soft_import_composite_flags_from_imena_excel(
        buf, "tester", session=session, dry_run=dry_run,
        create_phase_b_parents=phase_b, create_missing_numbs=True,
        database_version_id=target_version,
    )

    expected_count = int(not dry_run and (phase_b or target_version == 37))
    assert len(session.added) == expected_count
    assert all(group.database_version_id == 37 for group in session.added)
    assert result.phase_b_created == int(not dry_run and phase_b)
    assert result.missing_numbs_created == int(not dry_run and not phase_b and target_version == 37)
    if not dry_run and target_version != 37:
        assert any("Не определена текущая версия БД" in warning for warning in result.warnings)
    assert session.commits == int(not dry_run)


@pytest.mark.parametrize("version", [None, 0, -1])
def test_missing_numb_write_requires_version(version):
    session = _Session()
    with pytest.raises(ValueError, match="верси"):
        parents.create_missing_numbs_from_excel(
            session, dry_run=False, database_version_id=version,
            excel_rows={"10": {"name": "Station", "comp": 1}},
        )
    assert session.added == []
