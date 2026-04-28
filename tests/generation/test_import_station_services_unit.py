from types import SimpleNamespace

import pandas as pd

from app.generation.services.station_services import import_station_services as service


class _FakeQuery:
    def __init__(self, obj):
        self.obj = obj

    def filter_by(self, **kwargs):
        return self

    def first(self):
        return self.obj


class _ListQuery:
    def __init__(self, items):
        self.items = list(items)

    def filter_by(self, **kwargs):
        filtered = [
            item
            for item in self.items
            if all(getattr(item, key, None) == value for key, value in kwargs.items())
        ]
        return _ListQuery(filtered)

    def first(self):
        return self.items[0] if self.items else None

    def all(self):
        return list(self.items)


class _DummySession:
    def __init__(self):
        self.added = []

    def add(self, *args, **kwargs):
        if args:
            self.added.append(args[0])
        return None

    def flush(self):
        return None

    def commit(self):
        return None

    def rollback(self):
        return None


class _FakeExcelFile:
    def __init__(self, df):
        self.sheet_names = ["список"]
        self._header = pd.DataFrame(columns=df.columns)
        self._body = df

    def parse(self, sheet_name, header=0, nrows=None, **kwargs):
        if sheet_name != "список":
            raise AssertionError(f"unexpected sheet: {sheet_name}")
        if nrows == 0:
            return self._header.copy()
        return self._body.copy()


def test_apply_station_import_column_aliases_supports_common_excel_headers():
    df = pd.DataFrame(
        columns=["machine_no", "Группа агрегатов", "Год ввода", "Примечание"]
    )

    renamed = service._apply_station_import_column_aliases(df)

    assert "machine_number" in renamed.columns
    assert "machine_group" in renamed.columns
    assert "date_exploitation" in renamed.columns
    assert "note" in renamed.columns


def test_canonicalize_station_import_power_columns_prefers_nonzero_duplicate_value():
    df = pd.DataFrame(
        [[0, "24.9", "16.5"]],
        columns=["p_2024", "2024", "2025"],
    )

    years = service._canonicalize_station_import_power_columns(df)

    assert years == [2024, 2025]
    assert list(df.columns) == ["p_2024", "p_2025"]
    assert df.loc[0, "p_2024"] == "24.9"
    assert df.loc[0, "p_2025"] == "16.5"


def test_import_station_list_from_excel_processes_combined_station_machine_row(monkeypatch):
    df = pd.DataFrame(
        [
            {
                "regional_district": "Республика Карелия",
                "station_name": "Беломорская ГЭС-1",
                "machine_group": "Г-1 Г-2",
                "machine_number": "1",
                "machine_name": "Гидротурбина",
                "gen_company": "ООО «ТГК»",
                "station_type": "ГЭС",
                "p_2024": "24.9",
            }
        ]
    )
    fake_excel = _FakeExcelFile(df)
    fake_station = SimpleNamespace(name="Беломорская ГЭС-1")
    fake_machine = SimpleNamespace(
        machine_number="1",
        machine_name="Гидротурбина",
        machine_station=SimpleNamespace(
            name="Беломорская ГЭС-1",
            regional_district=SimpleNamespace(name="Республика Карелия"),
        ),
    )
    calls = {"station": 0, "machine": 0, "p_ust": 0}

    def fake_handle_station(row, user, **kwargs):
        calls["station"] += 1
        return fake_station

    def fake_handle_machine(row, current_station, user, import_power_years=None):
        calls["machine"] += 1
        assert current_station is fake_station
        assert import_power_years == [2024]
        return fake_machine

    def fake_assign_machine_power_p_ust(machine, row, years, user):
        calls["p_ust"] += 1
        assert machine is fake_machine
        assert years == [2024]
        assert row["p_2024"] == "24.9"

    monkeypatch.setattr(service.pd, "ExcelFile", lambda _: fake_excel)
    monkeypatch.setattr(service, "_overwrite_power_columns_from_excel_raw", lambda *a, **k: None)
    monkeypatch.setattr(service, "_canonicalize_station_import_power_columns", lambda df: [2024])
    monkeypatch.setattr(service, "handle_station", fake_handle_station)
    monkeypatch.setattr(service, "handle_machine", fake_handle_machine)
    monkeypatch.setattr(service, "assign_machine_types", lambda *a, **k: None)
    monkeypatch.setattr(service, "assign_machine_power_p_ust", fake_assign_machine_power_p_ust)
    monkeypatch.setattr(service, "cleanup_machine_fuel_and_tes_type", lambda *a, **k: None)
    monkeypatch.setattr(service, "assign_machine_power_p_rasp", lambda *a, **k: None)
    monkeypatch.setattr(service, "update_machine_commission_status", lambda *a, **k: None)
    monkeypatch.setattr(service, "update_machine_power_ogr", lambda *a, **k: None)
    monkeypatch.setattr(service, "update_station_power", lambda *a, **k: None)
    monkeypatch.setattr(service, "versioned_query", lambda model: _FakeQuery(fake_station))
    monkeypatch.setattr(service.db, "session", _DummySession())

    result = service.import_station_list_from_excel(
        SimpleNamespace(filename="stations.xlsx"),
        user="tester",
    )

    assert result["processed_rows"] == 1
    assert result["errors_count"] == 0
    assert calls == {"station": 1, "machine": 1, "p_ust": 1}


def test_import_station_list_updates_exact_touched_station_not_name_lookup(monkeypatch):
    df = pd.DataFrame(
        [
            {
                "regional_district": "Республика Карелия",
                "station_name": "Белопорожская ГЭС-1",
                "machine_group": "Г-1, Г-2",
                "machine_number": "1, 2",
                "machine_name": "Гидроагрегат",
                "gen_company": "ООО «ТГК»",
                "p_2024": "24.9",
            }
        ]
    )
    fake_excel = _FakeExcelFile(df)
    touched_station = SimpleNamespace(id=101, name="Белопорожская ГЭС-1")
    wrong_station = SimpleNamespace(id=999, name="Белопорожская ГЭС-1")
    fake_machine = SimpleNamespace(
        machine_number="1, 2",
        machine_name="Гидроагрегат",
        machine_station=touched_station,
    )
    updated_station_ids = []

    monkeypatch.setattr(service.pd, "ExcelFile", lambda _: fake_excel)
    monkeypatch.setattr(service, "_overwrite_power_columns_from_excel_raw", lambda *a, **k: None)
    monkeypatch.setattr(service, "_canonicalize_station_import_power_columns", lambda df: [2024])
    monkeypatch.setattr(service, "handle_station", lambda row, user, **kwargs: touched_station)
    monkeypatch.setattr(
        service,
        "handle_machine",
        lambda row, current_station, user, import_power_years=None: fake_machine,
    )
    monkeypatch.setattr(service, "assign_machine_types", lambda *a, **k: None)
    monkeypatch.setattr(service, "assign_machine_power_p_ust", lambda *a, **k: None)
    monkeypatch.setattr(service, "cleanup_machine_fuel_and_tes_type", lambda *a, **k: None)
    monkeypatch.setattr(service, "assign_machine_power_p_rasp", lambda *a, **k: None)
    monkeypatch.setattr(service, "update_machine_commission_status", lambda *a, **k: None)
    monkeypatch.setattr(service, "update_machine_power_ogr", lambda *a, **k: None)
    monkeypatch.setattr(
        service,
        "update_station_power",
        lambda station, years, user: updated_station_ids.append(station.id),
    )
    monkeypatch.setattr(service, "versioned_query", lambda model: _FakeQuery(wrong_station))
    monkeypatch.setattr(service.db, "session", _DummySession())

    result = service.import_station_list_from_excel(
        SimpleNamespace(filename="stations.xlsx"),
        user="tester",
    )

    assert result["errors_count"] == 0
    assert updated_station_ids == [101]


def test_import_station_list_marks_non_adjacent_duplicate_station_block_as_unused_slot(monkeypatch):
    df = pd.DataFrame(
        [
            {
                "regional_district": "Республика Карелия",
                "station_name": "ТЭС-2",
            },
            {
                "regional_district": "Республика Карелия",
                "station_name": "ТЭС-1",
            },
            {
                "regional_district": "Республика Карелия",
                "station_name": "ТЭС-2",
            },
        ]
    )
    fake_excel = _FakeExcelFile(df)
    station_calls = []

    def fake_handle_station(row, user, **kwargs):
        station_calls.append(
            {
                "station_name": row.get("station_name"),
                "prefer_unused_slot": kwargs.get("prefer_unused_slot"),
            }
        )
        return SimpleNamespace(id=len(station_calls), name=row.get("station_name"))

    monkeypatch.setattr(service.pd, "ExcelFile", lambda _: fake_excel)
    monkeypatch.setattr(service, "_overwrite_power_columns_from_excel_raw", lambda *a, **k: None)
    monkeypatch.setattr(service, "_canonicalize_station_import_power_columns", lambda df: [2024])
    monkeypatch.setattr(service, "handle_station", fake_handle_station)
    monkeypatch.setattr(service, "update_station_power", lambda *a, **k: None)
    monkeypatch.setattr(service.db, "session", _DummySession())

    result = service.import_station_list_from_excel(
        SimpleNamespace(filename="stations.xlsx"),
        user="tester",
    )

    assert result["errors_count"] == 0
    assert station_calls == [
        {"station_name": "ТЭС-2", "prefer_unused_slot": False},
        {"station_name": "ТЭС-1", "prefer_unused_slot": False},
        {"station_name": "ТЭС-2", "prefer_unused_slot": True},
    ]


def test_find_station_candidate_by_machine_signature_picks_correct_duplicate(monkeypatch):
    candidate_a = SimpleNamespace(id=101, id_station_type=None, note=None)
    candidate_b = SimpleNamespace(id=202, id_station_type=None, note=None)
    row = pd.Series(
        {
            "machine_group": "Г-2",
            "machine_number": "5",
            "machine_name": "Турбина",
            "date_exploitation": "1975",
        }
    )
    machines = [
        SimpleNamespace(
            id_station=202,
            machine_group="Г-2",
            machine_number="5",
            machine_name="Турбина",
            date_exploitation=1975,
        )
    ]

    def fake_versioned_query(model):
        if model is service.Machine:
            return _ListQuery(machines)
        raise AssertionError(f"unexpected model: {model}")

    monkeypatch.setattr(service, "versioned_query", fake_versioned_query)

    resolved = service._find_station_candidate_by_machine_signature(
        [candidate_a, candidate_b],
        row,
    )

    assert resolved is candidate_b


def test_extract_import_machine_signature_ignores_nan_machine_fields():
    row = pd.Series(
        {
            "machine_group": float("nan"),
            "machine_number": float("nan"),
            "machine_name": float("nan"),
            "date_exploitation": float("nan"),
        }
    )

    signature = service._extract_import_machine_signature(row)

    assert signature is None


def test_handle_station_creates_new_station_for_duplicate_name_with_other_machine(monkeypatch):
    row = pd.Series(
        {
            "regional_district": "Республика Карелия",
            "station_name": "ТСС-1",
            "machine_group": "Г-2",
            "machine_number": "5",
            "machine_name": "Турбина",
            "date_exploitation": "1975",
            "note": None,
            "station_type": None,
        }
    )
    district = SimpleNamespace(id=7, name="Республика Карелия", regional_energy_systems=[])
    existing_station = SimpleNamespace(id=101, name="ТСС-1", id_station_type=None, note=None)
    condition_type = SimpleNamespace(id=1)
    energy_unit = SimpleNamespace(id=0)
    session = _DummySession()

    def fake_versioned_query(model):
        if model is service.RegionalDistrict:
            return _ListQuery([district])
        if model is service.EnergyUnit:
            return _ListQuery([energy_unit])
        if model is service.ConditionType:
            return _ListQuery([condition_type])
        if model is service.Station:
            return _ListQuery([existing_station])
        if model is service.Machine:
            return _ListQuery([])
        raise AssertionError(f"unexpected model: {model}")

    monkeypatch.setattr(service, "versioned_query", fake_versioned_query)
    monkeypatch.setattr(service, "safe_lookup", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "set_db_version_on_create", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "get_current_db_version_id", lambda: None)
    monkeypatch.setattr(service, "log_to_db", lambda *args, **kwargs: None)
    monkeypatch.setattr(service.db, "session", session)

    created_station = service.handle_station(row, user="tester")

    assert created_station is not existing_station
    assert created_station in session.added
    assert created_station.id_regional_district == 7
    assert created_station.external_code


def test_handle_station_does_not_merge_duplicate_name_by_station_type_when_machine_differs(monkeypatch):
    row = pd.Series(
        {
            "regional_district": "Республика Карелия",
            "station_name": "ТЭС-2",
            "machine_group": "",
            "machine_number": "4",
            "machine_name": "ПР-6-35/15/5",
            "date_exploitation": "1970",
            "note": None,
            "station_type": "ТЭЦ",
        }
    )
    district = SimpleNamespace(id=7, name="Республика Карелия", regional_energy_systems=[])
    existing_station = SimpleNamespace(
        id=101,
        name="ТЭС-2",
        id_station_type=99,
        note=None,
    )
    condition_type = SimpleNamespace(id=1)
    energy_unit = SimpleNamespace(id=0)
    session = _DummySession()

    def fake_versioned_query(model):
        if model is service.RegionalDistrict:
            return _ListQuery([district])
        if model is service.EnergyUnit:
            return _ListQuery([energy_unit])
        if model is service.ConditionType:
            return _ListQuery([condition_type])
        if model is service.Station:
            return _ListQuery([existing_station])
        if model is service.Machine:
            return _ListQuery(
                [
                    SimpleNamespace(
                        id_station=101,
                        machine_group="",
                        machine_number="1",
                        machine_name="ПТ-30-3,4-1",
                        date_exploitation=2001,
                    )
                ]
            )
        raise AssertionError(f"unexpected model: {model}")

    monkeypatch.setattr(service, "versioned_query", fake_versioned_query)
    monkeypatch.setattr(service, "safe_lookup", lambda model, field, value, cleaner=None: 99 if model is service.StationType else None)
    monkeypatch.setattr(service, "set_db_version_on_create", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "get_current_db_version_id", lambda: None)
    monkeypatch.setattr(service, "log_to_db", lambda *args, **kwargs: None)
    monkeypatch.setattr(service.db, "session", session)

    created_station = service.handle_station(row, user="tester")

    assert created_station is not existing_station
    assert created_station in session.added


def test_handle_station_prefers_unused_slot_for_repeated_station_block(monkeypatch):
    row = pd.Series(
        {
            "regional_district": "Республика Карелия",
            "station_name": "ТЭС-2",
            "machine_group": "",
            "machine_number": "4",
            "machine_name": "ПР-6-35/15/5",
            "date_exploitation": "1970",
            "note": None,
            "station_type": "ТЭЦ",
        }
    )
    district = SimpleNamespace(id=7, name="Республика Карелия", regional_energy_systems=[])
    existing_station = SimpleNamespace(
        id=101,
        name="ТЭС-2",
        id_station_type=99,
        note=None,
    )
    condition_type = SimpleNamespace(id=1)
    energy_unit = SimpleNamespace(id=0)
    session = _DummySession()
    import_scope = {"used_station_ids_by_key": {("ТЭС-2", 7): {101}}}

    def fake_versioned_query(model):
        if model is service.RegionalDistrict:
            return _ListQuery([district])
        if model is service.EnergyUnit:
            return _ListQuery([energy_unit])
        if model is service.ConditionType:
            return _ListQuery([condition_type])
        if model is service.Station:
            return _ListQuery([existing_station])
        if model is service.Machine:
            return _ListQuery(
                [
                    SimpleNamespace(
                        id_station=101,
                        machine_group="",
                        machine_number="4",
                        machine_name="ПР-6-35/15/5",
                        date_exploitation=1970,
                    )
                ]
            )
        raise AssertionError(f"unexpected model: {model}")

    monkeypatch.setattr(service, "versioned_query", fake_versioned_query)
    monkeypatch.setattr(service, "safe_lookup", lambda model, field, value, cleaner=None: 99 if model is service.StationType else None)
    monkeypatch.setattr(service, "set_db_version_on_create", lambda *args, **kwargs: None)
    monkeypatch.setattr(service, "get_current_db_version_id", lambda: None)
    monkeypatch.setattr(service, "log_to_db", lambda *args, **kwargs: None)
    monkeypatch.setattr(service.db, "session", session)

    created_station = service.handle_station(
        row,
        user="tester",
        import_scope=import_scope,
        prefer_unused_slot=True,
    )

    assert created_station is not existing_station
    assert created_station in session.added


def test_move_matching_machine_from_sibling_station_reassigns_unique_match(monkeypatch):
    current_station = SimpleNamespace(id=202, name="ТЭС-2", id_regional_district=7)
    sibling_station = SimpleNamespace(id=101, name="ТЭС-2", id_regional_district=7)
    sibling_machine = SimpleNamespace(
        id=501,
        id_station=101,
        machine_group="",
        machine_number="4",
        machine_name="ПР-6-35/15/5",
        date_exploitation=1970,
    )
    session = _DummySession()

    def fake_versioned_query(model):
        if model is service.Station:
            return _ListQuery([current_station, sibling_station])
        if model is service.Machine:
            return _ListQuery([sibling_machine])
        raise AssertionError(f"unexpected model: {model}")

    monkeypatch.setattr(service, "versioned_query", fake_versioned_query)
    monkeypatch.setattr(service.db, "session", session)

    moved_machine = service._move_matching_machine_from_sibling_station(
        current_station,
        machine_number="4",
        machine_group="",
        machine_name="ПР-6-35/15/5",
        date_exploitation=1970,
    )

    assert moved_machine is sibling_machine
    assert sibling_machine.id_station == 202
    assert sibling_machine in session.added
