import gzip
from graphlib import CycleError
import hashlib
import sys

import pytest

from scripts import cleanup_unversioned_generation_data as cleanup


STATIONS = ("gs_gen", "gs_gen_stations")
MACHINES = ("gs_gen", "gs_gen_machines")
GROUPS = ("gs_fue", "gs_fue_equipment_groups")
PARAMS = ("gs_fue", "gs_fue_params")


def fk(child, parent):
    return cleanup.ForeignKey(child, parent, ("parent_id",), ("id",))


def test_named_child_protects_parent_station_and_other_parameters_but_not_unrelated_rows():
    station, machine, named_param, power = (STATIONS, 1), (MACHINES, 2), (PARAMS, 3), (PARAMS, 4)
    unrelated = (STATIONS, 99)
    protected = cleanup.protect_dependencies(
        {named_param: "version 20"},
        {machine: {station}, named_param: {machine}, power: {machine}, unrelated: set()},
    )
    assert set(protected) == {station, machine, named_param, power}
    assert unrelated not in protected
    assert protected[named_param] == "version 20"


def test_shared_link_protects_both_parents_and_handles_cycles():
    group, station, link = (GROUPS, 1), (STATIONS, 2), (PARAMS, 3)
    protected = cleanup.protect_dependencies({group: "named data"}, {link: {group, station}, group: {link}})
    assert set(protected) == {group, station, link}


def test_all_unversioned_component_is_deletable_without_named_seeds():
    assert cleanup.protect_dependencies({}, {(MACHINES, 2): {(STATIONS, 1)}}) == {}


def test_deletion_order_places_all_children_before_both_parents():
    keys = {STATIONS, MACHINES, GROUPS, PARAMS}
    relations = [fk(MACHINES, STATIONS), fk(PARAMS, MACHINES), fk(PARAMS, GROUPS)]
    order = cleanup.deletion_order(keys, relations)
    for relation in relations:
        assert order.index(relation.child) < order.index(relation.parent)
    assert cleanup.reachable_tables({STATIONS, GROUPS}, relations) == keys


def test_reachability_excludes_unrelated_reference_tables():
    unrelated = ("gs_sys", "gs_sys_years")
    assert unrelated not in cleanup.reachable_tables({STATIONS}, [fk(MACHINES, STATIONS), fk(PARAMS, unrelated)])


def test_cyclic_delete_dependencies_are_rejected():
    with pytest.raises(CycleError):
        cleanup.deletion_order({STATIONS, MACHINES}, [fk(STATIONS, MACHINES), fk(MACHINES, STATIONS)])


class CopyCursor:
    def __init__(self, content):
        self.content = content

    def mogrify(self, query, values):
        assert values == ([1, 2],)
        return b"COPY test TO STDOUT WITH CSV HEADER"

    def copy_expert(self, query, stream):
        stream.write(self.content)


def test_backup_preserves_csv_multiline_values_and_verifies_row_count(tmp_path):
    table = cleanup.Table("gs_gen", "example", ("id", "note"), ("id",))
    content = b'id,note\n1,"a,b"\n2,"line one\nline two"\n'
    result = cleanup.backup_rows(CopyCursor(content), table, [1, 2], tmp_path)
    path = tmp_path / result["file"]
    assert gzip.decompress(path.read_bytes()) == content
    assert result["rows"] == 2
    assert result["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert result["columns"] == ["id", "note"]


@pytest.mark.parametrize("content", [b"id,note\n1,only one\n", b"note,id\na,1\nb,2\n"])
def test_incomplete_or_wrong_column_backup_aborts_before_delete(tmp_path, content):
    table = cleanup.Table("gs_gen", "example", ("id", "note"), ("id",))
    with pytest.raises(ValueError, match="Проверка резервной копии"):
        cleanup.backup_rows(CopyCursor(content), table, [1, 2], tmp_path)


def test_apply_without_confirmed_plan_is_rejected_before_connection(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", ["cleanup", "--apply", "--output", str(tmp_path / "must-not-exist")])
    with pytest.raises(SystemExit) as exc:
        cleanup.main()
    assert exc.value.code == 2
    assert not (tmp_path / "must-not-exist").exists()
