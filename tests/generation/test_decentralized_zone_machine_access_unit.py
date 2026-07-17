# -*- coding: utf-8 -*-
"""Права редактирования карточки агрегата на станции ДЭЗ."""

from types import SimpleNamespace

from app.generation.services.station_services.station_access_services import (
    can_edit_decentralized_zone_machine_details,
    is_decentralized_zone_station,
)


def _user(*role_names: str, name_full: str | None = None):
    roles = []
    for name in role_names:
        roles.append(SimpleNamespace(name=name, name_full=name_full or name))
    return SimpleNamespace(is_authenticated=True, role_names=list(role_names), roles=roles)


def _station(res_name: str = "не указано"):
    res = SimpleNamespace(name=res_name)
    return SimpleNamespace(
        regional_energy_system_obj=res,
        regional_energy_system=res_name,
        id_regional_energy_system=1,
        regional_district=None,
    )


def test_is_decentralized_zone_station_by_unspecified_res():
    assert is_decentralized_zone_station(_station()) is True
    assert is_decentralized_zone_station(_station("Центральная, Москва")) is False


def test_can_edit_dz_machine_for_fuel_and_generation_roles():
    station = _station()
    assert can_edit_decentralized_zone_machine_details(_user("fuel-editor"), station) is True
    assert can_edit_decentralized_zone_machine_details(_user("generation-editor"), station) is True
    assert can_edit_decentralized_zone_machine_details(_user("admin"), station) is True


def test_can_edit_dz_machine_denied_outside_dz_or_without_role():
    station = _station("Центральная, Москва")
    assert can_edit_decentralized_zone_machine_details(_user("fuel-editor"), station) is False
    assert can_edit_decentralized_zone_machine_details(_user("viewer"), station) is False


def test_can_edit_machine_generation_fields_for_fuel_create_new_machine():
    from app.generation.services.machine_services.machine_services import (
        _can_edit_machine_generation_fields,
    )

    assert _can_edit_machine_generation_fields(
        False, False, was_new=True, fuel_can_create_machine=True
    )
    assert not _can_edit_machine_generation_fields(
        False, False, was_new=False, fuel_can_create_machine=True
    )
    assert _can_edit_machine_generation_fields(
        False, True, was_new=False, fuel_can_create_machine=False
    )
