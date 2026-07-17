# -*- coding: utf-8 -*-
"""autofill_tes_and_fuel_chain не должен сбрасывать явно заданные в форме значения."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from app.generation.services.machine_services.machine_services import autofill_tes_and_fuel_chain


class _FakeField:
    def __init__(self, data):
        self.data = data


class _FakeEntry:
    def __init__(self, year, tes_type=None, fuel_type=None, year_name=None, p_ust=None, p_ogr=None, p_rasp=None):
        self.year = _FakeField(year)
        self.tes_type = _FakeField(tes_type)
        self.fuel_type = _FakeField(fuel_type)
        self.year_name = _FakeField(year_name)
        self.p_ust = _FakeField(p_ust)
        self.p_ogr = _FakeField(p_ogr)
        self.p_rasp = _FakeField(p_rasp)


class _FakeFieldList:
    def __init__(self, entries):
        self.entries = entries

    def __len__(self):
        return len(self.entries)

    def __getitem__(self, idx):
        return self.entries[idx]


class _FakeAdvancedForm:
    def __init__(self, entries):
        self.tes_types = _FakeFieldList(entries)
        self.fuels = _FakeFieldList(entries)
        self.machine_names = _FakeFieldList(entries)
        self.powers = _FakeFieldList(entries)


def _station_tes():
    return SimpleNamespace(station_type=SimpleNamespace(name="ТЭС"))


def _patch_choices(monkeypatch):
    from app.generation.services.machine_services import machine_services as ms

    monkeypatch.setattr(
        ms.choices_cache,
        "get_choices",
        lambda model, field: [(0, "не указано"), (57, "ТЭЦ")],
    )
    monkeypatch.setattr(ms.choices_cache, "EMPTY_VALUE_ID", 0)
    monkeypatch.setattr(ms.choices_cache, "is_empty_value", lambda val: val in (None, 0, "", "0"))


@patch("flask.flash")
def test_autofill_keeps_user_set_tes_and_fuel_when_power_zero(mock_flash, monkeypatch):
    _patch_choices(monkeypatch)

    mt = SimpleNamespace(id_tes_type=57)
    mf = SimpleNamespace(id_fuel=1221)
    mp = SimpleNamespace(p_ust=Decimal(0), p_ogr=Decimal(0), p_rasp=Decimal(0))
    mn = SimpleNamespace(name="АГР-1")

    changes = []
    advanced_form = _FakeAdvancedForm(
        [_FakeEntry(2024, tes_type=57, fuel_type=1221, year_name="АГР-1")]
    )

    autofill_tes_and_fuel_chain(
        machine=SimpleNamespace(),
        station=_station_tes(),
        advanced_form=advanced_form,
        changes=changes,
        start_year=2024,
        end_year=2024,
        powers_map={2024: mp},
        tes_map={2024: mt},
        fuel_map={2024: mf},
        names_map={2024: mn},
        can_edit_fuel=True,
        can_edit_generation=True,
    )

    assert mt.id_tes_type == 57
    assert mf.id_fuel == 1221
    assert mn.name == "АГР-1"
    assert not any("Тип ТЭС" in change for change in changes)


@patch("flask.flash")
def test_autofill_uses_form_powers_when_db_still_zero(mock_flash, monkeypatch):
    _patch_choices(monkeypatch)

    mt = SimpleNamespace(id_tes_type=57)
    mf = SimpleNamespace(id_fuel=1221)
    mp = SimpleNamespace(p_ust=Decimal(0), p_ogr=Decimal(0), p_rasp=Decimal(0))

    changes = []
    advanced_form = _FakeAdvancedForm(
        [_FakeEntry(2024, tes_type=57, fuel_type=1221, year_name="")]
    )
    advanced_form.powers.entries[0].p_ust = _FakeField(Decimal("90"))
    advanced_form.powers.entries[0].p_ogr = _FakeField(Decimal(0))
    advanced_form.powers.entries[0].p_rasp = _FakeField(Decimal("90"))

    autofill_tes_and_fuel_chain(
        machine=SimpleNamespace(),
        station=_station_tes(),
        advanced_form=advanced_form,
        changes=changes,
        start_year=2024,
        end_year=2024,
        powers_map={2024: mp},
        tes_map={2024: mt},
        fuel_map={2024: mf},
        names_map={},
        can_edit_fuel=True,
        can_edit_generation=True,
    )

    assert mt.id_tes_type == 57
    assert not any("→ не указано" in change for change in changes)


@patch("flask.flash")
def test_autofill_clears_tes_when_power_zero_and_form_empty(mock_flash, monkeypatch):
    _patch_choices(monkeypatch)

    mt = SimpleNamespace(id_tes_type=57)
    mf = SimpleNamespace(id_fuel=1221)
    mp = SimpleNamespace(p_ust=Decimal(0), p_ogr=Decimal(0), p_rasp=Decimal(0))
    mn = SimpleNamespace(name="")

    changes = []
    advanced_form = _FakeAdvancedForm(
        [_FakeEntry(2024, tes_type=0, fuel_type=0, year_name="")]
    )

    autofill_tes_and_fuel_chain(
        machine=SimpleNamespace(),
        station=_station_tes(),
        advanced_form=advanced_form,
        changes=changes,
        start_year=2024,
        end_year=2024,
        powers_map={2024: mp},
        tes_map={2024: mt},
        fuel_map={2024: mf},
        names_map={2024: mn},
        can_edit_fuel=True,
        can_edit_generation=True,
    )

    assert mt.id_tes_type == 0
    assert mf.id_fuel == 0
