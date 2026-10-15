from types import SimpleNamespace

from app.generation.services.machine_services import machine_services
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
    EquipmentGroupType,
)


def _form():
    return SimpleNamespace(
        id_gen_company=SimpleNamespace(choices=[], data=None),
        id_energy_area=SimpleNamespace(choices=[], data=None),
        id_machine_type=SimpleNamespace(choices=[], data=None),
        id_tes_machine_type=SimpleNamespace(choices=[], data=None),
        id_equipment_group=SimpleNamespace(choices=[], data=317),
        id_condition_type=SimpleNamespace(choices=[], data=None),
    )


def _patch_choices(monkeypatch, equipment_group_choices):
    def get_choices_with_default(model, *_args, **_kwargs):
        if model is EquipmentGroupType:
            return [(0, "не указано"), *equipment_group_choices]
        return [(0, "не указано")]

    monkeypatch.setattr(
        machine_services.choices_cache,
        "get_choices_with_default",
        get_choices_with_default,
    )
    monkeypatch.setattr(
        machine_services.choices_cache,
        "get_choices",
        lambda *_args, **_kwargs: [],
    )


def test_machine_details_keeps_linked_type_missing_from_versioned_choices(monkeypatch):
    _patch_choices(monkeypatch, [])
    form = _form()
    machine = SimpleNamespace(
        id_equipment_group=317,
        equipment_group=SimpleNamespace(name="ТЭЦ<90 ата"),
    )

    machine_services._fill_main_form_choices(form, machine)

    assert (317, "ТЭЦ<90 ата") in form.id_equipment_group.choices
    assert form.id_equipment_group.data == 317


def test_machine_details_does_not_duplicate_type_already_in_choices(monkeypatch):
    _patch_choices(monkeypatch, [(317, "ТЭЦ<90 ата")])
    form = _form()
    machine = SimpleNamespace(
        id_equipment_group=317,
        equipment_group=SimpleNamespace(name="ТЭЦ<90 ата"),
    )

    machine_services._fill_main_form_choices(form, machine)

    assert form.id_equipment_group.choices.count((317, "ТЭЦ<90 ата")) == 1
