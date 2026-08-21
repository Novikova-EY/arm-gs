# -*- coding: utf-8 -*-
from io import BytesIO
from types import SimpleNamespace

import pandas as pd

from app.fuel.services.equipment_groups.composite_main_vs_station_reconciliation_services import (
    ParentShellsResult,
    create_missing_numbs_from_excel,
    create_missing_parent_shells_from_children,
    create_phase_b_comp1_parents_from_excel,
)
from app.fuel.services.fuel_imports.soft_import_composite_flags_services import (
    SoftCompositeFlagsResult,
    _dict_updates_from_meta,
    _numb_key,
    _read_imena_dataframe,
    _safe_int,
    soft_import_composite_flags_from_imena_excel,
)


def test_safe_int_and_numb_key():
    assert _safe_int(1.0) == 1
    assert _safe_int("2") == 2
    assert _safe_int("") is None
    assert _safe_int(None) is None
    assert _numb_key(10.0) == "10"
    assert _numb_key(None) is None


def test_read_imena_dataframe_aliases():
    df = pd.DataFrame(
        [
            {"NUMB": 1, "COMP": 1, "MAIN": None, "NIV": None, "NAME": "Parent"},
            {"NUMB": 2, "COMP": None, "MAIN": 1, "NIV": 1, "NAME": "Child"},
        ]
    )
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Имена_станций")
    buf.seek(0)
    parsed = _read_imena_dataframe(buf)
    assert "numb" in parsed.columns
    assert "comp" in parsed.columns
    assert "main" in parsed.columns
    assert "niv" in parsed.columns


def test_soft_import_dry_run_phase_b_without_children(monkeypatch):
    """Пустой индекс EG → phase A=0, phase B создаёт COMP=1 «в пустоту»."""
    df = pd.DataFrame(
        [
            {"NUMB": 999001, "COMP": 1, "MAIN": None, "NIV": None, "NAME": "Alone"},
            {"NUMB": 999002, "COMP": None, "MAIN": 999001, "NIV": 1},
        ]
    )
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buf.seek(0)

    class _Q:
        def filter(self, *a, **k):
            return self

        def distinct(self):
            return self

        def all(self):
            return []

    class _Sess:
        def query(self, *a, **k):
            return _Q()

        def commit(self):
            raise AssertionError("commit must not be called in dry_run")

        def add(self, obj):
            raise AssertionError("add must not be called in dry_run")

    monkeypatch.setattr(
        "app.fuel.services.equipment_groups.composite_main_vs_station_reconciliation_services._find_station_id_by_name",
        lambda sess, name, ver: None,
    )
    monkeypatch.setattr(
        "app.fuel.services.equipment_groups.composite_main_vs_station_reconciliation_services._distinct_eg_version_ids",
        lambda sess: [None],
    )

    result = soft_import_composite_flags_from_imena_excel(
        buf, "tester", dry_run=True, session=_Sess()
    )
    assert isinstance(result, SoftCompositeFlagsResult)
    assert result.dry_run is True
    assert result.excel_unique_numb == 2
    assert result.matched_numb == 0
    assert result.eg_rows_updated == 0
    assert result.parent_shells_would_create == 0
    assert result.phase_b_enabled is False
    assert result.phase_b_unique_numbs == 1
    assert result.phase_b_would_create >= 1
    assert result.phase_b_created == 0
    assert result.missing_numbs_enabled is False
    assert result.missing_numbs_created == 0
    assert result.missing_numbs_would_create >= 1
    assert any("phase B выкл" in line or "отложена" in line for line in result.to_flash_lines())
    assert any("отсутствующие NUMB выкл" in line or "отложены" in line for line in result.to_flash_lines())


def test_create_parents_skips_when_require_station(monkeypatch):
    """require_station=True: без Station родителя не создаём."""
    child = SimpleNamespace(
        id=101,
        numb=20,
        main=10,
        comp=None,
        niv=1,
        name="Child",
        name_ext="Child",
        obl=1,
        dep=1,
        oes=1,
        er=1,
        fo=1,
        vedomstvo=1,
        regional_district_id=None,
        regional_energy_system_id=None,
        database_version_id=7,
        d=None,
        r=None,
        forem=None,
        tm=None,
        addr=None,
        note=None,
        codegor=None,
        be=None,
        gk=None,
        gkf=None,
    )

    class _Q:
        def filter(self, *a, **k):
            return self

        def all(self):
            return [child]

    class _Sess:
        def query(self, *a, **k):
            return _Q()

        def add(self, obj):
            raise AssertionError("must not create parent without station")

        def flush(self):
            pass

    monkeypatch.setattr(
        "app.fuel.services.equipment_groups.composite_main_vs_station_reconciliation_services._resolve_station_for_parent",
        lambda kids, siblings, ver: (None, kids[0], "no_station"),
    )

    result = create_missing_parent_shells_from_children(
        _Sess(),
        dry_run=False,
        excel_parents={"10": {"name": "Parent", "comp": 1}},
        require_station=True,
    )
    assert isinstance(result, ParentShellsResult)
    assert result.created_or_planned == 0
    assert len(result.skipped_no_station) == 1


def test_phase_b_plans_rows_per_version(monkeypatch):
    class _Q:
        def filter(self, *a, **k):
            return self

        def distinct(self):
            return self

        def all(self):
            # existing numbs empty; versions from distinct call on database_version_id
            return []

        def first(self):
            return None

    class _Sess:
        def query(self, *a, **k):
            return _Q()

        def add(self, obj):
            raise AssertionError("dry_run")

        def flush(self):
            pass

    monkeypatch.setattr(
        "app.fuel.services.equipment_groups.composite_main_vs_station_reconciliation_services._distinct_eg_version_ids",
        lambda sess: [None, 7, 20],
    )
    monkeypatch.setattr(
        "app.fuel.services.equipment_groups.composite_main_vs_station_reconciliation_services._find_station_id_by_name",
        lambda sess, name, ver: 100 if ver == 7 else None,
    )

    result = create_phase_b_comp1_parents_from_excel(
        _Sess(),
        dry_run=True,
        excel_parents={
            "40": {"name": "Брянская ГРЭС", "comp": 1},
            "99": {"name": "Not parent", "comp": None},
        },
    )
    assert result.unique_parent_numbs == 1
    assert result.created_or_planned == 3  # None, 7, 20
    assert result.created_without_station == 2  # None and 20


def test_soft_import_dry_run_create_missing_numbs_reports_child(monkeypatch):
    """Пустой индекс EG + create_missing_numbs: в отчёте есть ребёнок 999002."""
    df = pd.DataFrame(
        [
            {"NUMB": 999001, "COMP": 1, "MAIN": None, "NIV": None, "NAME": "Alone"},
            {"NUMB": 999002, "COMP": None, "MAIN": 999001, "NIV": 1, "NAME": "Child"},
        ]
    )
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buf.seek(0)

    class _Q:
        def filter(self, *a, **k):
            return self

        def distinct(self):
            return self

        def all(self):
            return []

    class _Sess:
        def query(self, *a, **k):
            return _Q()

        def commit(self):
            raise AssertionError("commit must not be called in dry_run")

        def add(self, obj):
            raise AssertionError("add must not be called in dry_run")

    monkeypatch.setattr(
        "app.fuel.services.equipment_groups.composite_main_vs_station_reconciliation_services._find_station_id_by_name",
        lambda sess, name, ver: None,
    )
    monkeypatch.setattr(
        "app.fuel.services.equipment_groups.composite_main_vs_station_reconciliation_services._distinct_eg_version_ids",
        lambda sess: [None],
    )

    result = soft_import_composite_flags_from_imena_excel(
        buf,
        "tester",
        dry_run=True,
        session=_Sess(),
        create_missing_numbs=True,
        database_version_id=20,
    )
    assert result.missing_numbs_enabled is True
    assert result.missing_numbs_created == 0
    assert result.missing_numbs_unique >= 1
    sample_numbs = {int(s["numb"]) for s in result.sample_missing_numbs}
    assert 999002 in sample_numbs
    assert any("отсутствующие NUMB" in line for line in result.to_flash_lines())


def test_create_missing_numbs_from_excel_skips_existing_and_headers(monkeypatch):
    class _Q:
        def filter(self, *a, **k):
            return self

        def distinct(self):
            return self

        def all(self):
            return [(81,)]

    added = []

    class _Sess:
        def query(self, *a, **k):
            return _Q()

        def add(self, obj):
            added.append(obj)

        def flush(self):
            pass

    def _fake_build(*, name, numb, ver, meta, donor, comp=None, main=None):
        return SimpleNamespace(
            name=name,
            numb=numb,
            database_version_id=ver,
            main=main,
            comp=comp,
            tm=None,
            addr=None,
            note=None,
        )

    monkeypatch.setattr(
        "app.fuel.services.equipment_groups.composite_main_vs_station_reconciliation_services._build_parent_eg",
        _fake_build,
    )

    result = create_missing_numbs_from_excel(
        _Sess(),
        dry_run=False,
        database_version_id=20,
        excel_rows={
            "81": {"name": "Ижора", "comp": 1, "main": None},
            "0": {"name": "Zero", "comp": None},
            "1502": {"name": "Ижора котельная", "comp": None, "main": 81, "niv": 1},
            "1503": {"name": "Наименование станции", "comp": None, "main": 81},
        },
    )
    assert result.created_or_planned == 1
    assert result.unique_parent_numbs == 1
    assert added and added[0].numb == 1502
    assert added[0].main == 81
    assert added[0].database_version_id == 20
    assert getattr(added[0], "station_id", None) is None


def test_dict_updates_from_meta_maps_name_to_name_ext_and_skips_empty():
    eg = SimpleNamespace(
        name="ТЭС-2 и ТЭС-3 ЭнТЭС",
        name_ext=None,
        d=None,
        r=None,
        vedomstvo=None,
        be=None,
        gk=None,
        gkf=None,
        er=None,
        n1=None,
        n2=None,
        p1=None,
        p2=None,
        addr=None,
        codegor=None,
        note="keep-me",
    )
    changes = _dict_updates_from_meta(
        eg,
        {
            "name": "Access NAME",
            "d": 1,
            "r": 0,
            "vedomstvo": 1,
            "be": 2,
            "gk": 3,
            "gkf": 4,
            "er": 5,
            "n1": "100",
            "n2": "110",
            "p1": "90",
            "p2": "130",
            "addr": "ул. Примерная",
            "codegor": 77,
            "note": None,
            "forem": None,
        },
    )
    assert "name" not in changes
    assert changes["name_ext"] == "Access NAME"
    assert changes["d"] == 1
    assert changes["r"] == 0
    assert changes["vedomstvo"] == 1
    assert changes["be"] == 2
    assert changes["gk"] == 3
    assert changes["gkf"] == 4
    assert changes["er"] == 5
    assert changes["n1"] == "100"
    assert changes["p1"] == "90"
    assert changes["addr"] == "ул. Примерная"
    assert changes["codegor"] == 77
    assert "note" not in changes
    assert "forem" not in changes


def test_read_imena_dataframe_dictionary_columns():
    df = pd.DataFrame(
        [
            {
                "NUMB": 11,
                "D": 1,
                "R": 0,
                "NAME": "ТЭС",
                "VEDOMSTVO": 1,
                "BE": 2,
                "GK": 3,
                "GKF": 4,
                "ER": 5,
                "N1": 100,
                "N2": 110,
                "P1": 90,
                "P2": 130,
                "ADDR": "addr",
                "CODEGOR": 77,
                "NOTE": "note",
            }
        ]
    )
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Имена_станций")
    buf.seek(0)
    parsed = _read_imena_dataframe(buf)
    for col in (
        "numb",
        "d",
        "r",
        "name",
        "vedomstvo",
        "be",
        "gk",
        "gkf",
        "er",
        "n1",
        "n2",
        "p1",
        "p2",
        "addr",
        "codegor",
        "note",
    ):
        assert col in parsed.columns


def _stub_soft_import_side_effects(monkeypatch):
    empty = ParentShellsResult()
    monkeypatch.setattr(
        "app.fuel.services.equipment_groups.composite_main_vs_station_reconciliation_services.create_missing_parent_shells_from_children",
        lambda *a, **k: empty,
    )
    monkeypatch.setattr(
        "app.fuel.services.equipment_groups.composite_main_vs_station_reconciliation_services.create_phase_b_comp1_parents_from_excel",
        lambda *a, **k: empty,
    )
    monkeypatch.setattr(
        "app.fuel.services.equipment_groups.composite_main_vs_station_reconciliation_services.create_missing_numbs_from_excel",
        lambda *a, **k: empty,
    )
    monkeypatch.setattr(
        "app.fuel.services.equipment_groups.composite_main_vs_station_reconciliation_services.report_composite_vs_station_clusters",
        lambda *a, **k: SimpleNamespace(to_flash_lines=lambda: []),
    )
    monkeypatch.setattr(
        "app.fuel.services.equipment_groups.composite_parent_ved_sync_services.sync_composite_parent_ved_zero",
        lambda *a, **k: 0,
    )
    monkeypatch.setattr(
        "app.fuel.services.fuel_imports.soft_import_composite_flags_services.log_to_db",
        lambda *a, **k: None,
    )


def test_soft_import_applies_dictionary_fields_by_numb_without_touching_name(
    monkeypatch,
):
    """Существующая EG с numb: словарные поля из Excel, ARM name не трогаем."""
    arm_name = "ТЭС-2 и ТЭС-3 ЭнТЭС ПЛ «Энергетика» (ТЭЦ<90 ата (Р))"
    eg = SimpleNamespace(
        id=30400,
        numb=11,
        name=arm_name,
        name_ext=None,
        comp=None,
        main=None,
        niv=None,
        d=None,
        r=None,
        forem=None,
        vedomstvo=None,
        obl=None,
        dep=None,
        oes=None,
        er=None,
        fo=None,
        tm=None,
        addr=None,
        note=None,
        codegor=None,
        be=None,
        gk=None,
        gkf=None,
        ordnumb=None,
        n1=None,
        n2=None,
        p1=None,
        p2=None,
        database_version_id=20,
    )

    class _Q:
        def filter(self, *a, **k):
            return self

        def distinct(self):
            return self

        def join(self, *a, **k):
            return self

        def all(self):
            return [eg]

    added = []

    class _Sess:
        def query(self, *a, **k):
            return _Q()

        def add(self, obj):
            added.append(obj)

        def flush(self):
            pass

        def commit(self):
            pass

    _stub_soft_import_side_effects(monkeypatch)

    df = pd.DataFrame(
        [
            {
                "NUMB": 11,
                "COMP": None,
                "MAIN": None,
                "NIV": None,
                "D": 1,
                "R": 0,
                "NAME": "Access NAME",
                "VEDOMSTVO": 1,
                "BE": 2,
                "GK": 3,
                "GKF": 4,
                "ER": 5,
                "N1": 100,
                "N2": 110,
                "P1": 90,
                "P2": 130,
                "ADDR": "ул. Примерная",
                "CODEGOR": 77,
                "NOTE": "примечание",
            }
        ]
    )
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buf.seek(0)

    result = soft_import_composite_flags_from_imena_excel(
        buf,
        "tester",
        dry_run=False,
        session=_Sess(),
        create_missing_parents=False,
        create_phase_b_parents=False,
        create_missing_numbs=False,
    )
    assert result.eg_rows_updated == 1
    assert added and added[0] is eg
    assert eg.name == arm_name
    assert eg.name_ext == "Access NAME"
    assert eg.d == 1
    assert eg.r == 0
    assert eg.vedomstvo == 1
    assert eg.be == 2
    assert eg.gk == 3
    assert eg.gkf == 4
    assert eg.er == 5
    assert eg.n1 == "100"
    assert eg.n2 == "110"
    assert eg.p1 == "90"
    assert eg.p2 == "130"
    assert eg.addr == "ул. Примерная"
    assert eg.codegor == 77
    assert eg.note == "примечание"
    sample = result.sample_updates[0]
    assert "name_ext" in (sample.get("dict_changes") or {})


def test_read_imena_dataframe_skips_title_row():
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Имена_станций"])
    ws.append(["NUMB", "D", "NAME", "VEDOMSTVO"])
    ws.append([11, 1, "ТЭС", 1])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    parsed = _read_imena_dataframe(buf)
    assert "numb" in parsed.columns
    assert "d" in parsed.columns
    assert int(parsed.iloc[0]["numb"]) == 11
    assert int(parsed.iloc[0]["d"]) == 1


def test_soft_import_matches_by_name_when_numb_empty(monkeypatch):
    eg = SimpleNamespace(
        id=501,
        numb=None,
        name="Архангельская ТЭЦ",
        name_ext=None,
        comp=None,
        main=None,
        niv=None,
        d=None,
        r=None,
        forem=None,
        vedomstvo=None,
        obl=None,
        dep=None,
        oes=None,
        er=None,
        fo=None,
        tm=None,
        addr=None,
        note=None,
        codegor=None,
        be=None,
        gk=None,
        gkf=None,
        ordnumb=None,
        n1=None,
        n2=None,
        p1=None,
        p2=None,
        database_version_id=20,
    )
    query_n = {"n": 0}

    class _Q:
        def __init__(self, rows):
            self._rows = rows

        def filter(self, *a, **k):
            return self

        def distinct(self):
            return self

        def join(self, *a, **k):
            return self

        def all(self):
            return self._rows

    class _Sess:
        def query(self, *a, **k):
            from app.fuel.models.fue_equipment_group_model import EquipmentGroup

            if a and a[0] is EquipmentGroup:
                query_n["n"] += 1
                if query_n["n"] == 1:
                    return _Q([])
                return _Q([eg])
            return _Q([])

        def add(self, obj):
            pass

        def flush(self):
            pass

        def commit(self):
            pass

    _stub_soft_import_side_effects(monkeypatch)

    df = pd.DataFrame(
        [
            {
                "NUMB": 1,
                "COMP": 1,
                "MAIN": None,
                "NIV": None,
                "D": 1,
                "R": 1,
                "NAME": "Архангельская ТЭЦ",
                "VEDOMSTVO": 1,
            }
        ]
    )
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    buf.seek(0)

    result = soft_import_composite_flags_from_imena_excel(
        buf,
        "tester",
        dry_run=False,
        session=_Sess(),
        create_missing_parents=False,
        create_phase_b_parents=False,
        create_missing_numbs=False,
    )
    assert result.matched_by_name == 1
    assert eg.numb == 1
    assert eg.d == 1
    assert eg.vedomstvo == 1
    assert eg.name == "Архангельская ТЭЦ"
