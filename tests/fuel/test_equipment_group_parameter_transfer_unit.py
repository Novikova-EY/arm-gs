from importlib import import_module

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

import app.rational_structure.models  # noqa: F401 – relationships on Machine
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_extra_fuel_param_model import EquipmentGroupExtraFuelParam
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import EquipmentGroupSpecificFuelConsumption
from app.fuel.models.fue_equipment_group_specific_fuel_cost_model import EquipmentGroupSpecificFuelCost
from app.fuel.models.fue_equipment_group_specific_fuel_price_model import EquipmentGroupSpecificFuelPrice
from app.fuel.models.fue_equipment_group_natural_fuel_model import EquipmentGroupNaturalFuel
from app.fuel.models.fue_equipment_group_fuel_formula_model import EquipmentGroupFuelFormula
from app.fuel.models.fue_equipment_group_electricity_production_cost_model import EquipmentGroupElectricityProductionCost
from app.fuel.models.fue_equipment_group_heat_and_tariffs_model import EquipmentGroupHeatAndTariffs
from app.fuel.models.coefficient.equipment_group_coefficient_result_model import EquipmentGroupCoefficientResult
from app.generation.models.machine.machine_model import Machine
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroupType
from app.fuel.services.equipment_groups import equipment_group_rebind_services as service
from app.fuel.services.equipment_groups import equipment_group_set_services as sets


DETAILS = [
    (EquipmentGroupFuelParam, "nust", {}),
    (EquipmentGroupExtraFuelParam, "gaz_prir", {}),
    (EquipmentGroupSpecificFuelConsumption, "y", {}),
    (EquipmentGroupSpecificFuelCost, "gaz", {}),
    (EquipmentGroupSpecificFuelPrice, "gaz_c", {}),
    (EquipmentGroupNaturalFuel, "gaz", {}),
    (EquipmentGroupFuelFormula, "formtxt", {"variant_number": 1}),
    (EquipmentGroupElectricityProductionCost, "zatr_e", {"cost_code": 1}),
    (EquipmentGroupHeatAndTariffs, "tarif", {"kod_goroda": 1, "name_eto": "ETO", "var_razv": 1}),
    (EquipmentGroupCoefficientResult, "k", {"distribution_parameter_id": 1}),
]


@pytest.fixture
def transfer_db(app, monkeypatch):
    for module in ("electrical_intensity", "energy_consumption", "power_demand", "economics", "territories", "ecology", "energy_balance"):
        import_module(f"app.{module}.models")
    engine = create_engine("sqlite://")
    models = [EquipmentGroup, EquipmentGroupSet, EquipmentGroupSetStation, Machine,
              MachineFuelParam, EquipmentGroupType] + [model for model, _, _ in DETAILS]
    with engine.begin() as conn:
        for schema in {model.__table__.schema for model in models}:
            conn.exec_driver_sql(f'ATTACH DATABASE ":memory:" AS "{schema}"')
        for model in models:
            model.__table__.create(conn)
    session = scoped_session(sessionmaker(bind=engine))
    monkeypatch.setattr(db, "session", session)
    monkeypatch.setattr(EquipmentGroup, "_populate_regional_ids", lambda self: None)
    monkeypatch.setattr(sets, "_quick_fix_equipment_group_seqs", lambda: None)
    monkeypatch.setattr(sets, "resolve_station_and_type_for_version", lambda station, kind, version: (station, kind))
    monkeypatch.setattr(
        "app.common.services.get_services.years.years_get_services.get_reference_years",
        lambda: [2024, 2025, 2030],
    )
    source = EquipmentGroup(id=1, name="head", numb=100, comp=1, niv=1,
                            database_version_id=1, tm="turbine", n1="100", p1="130", note="note")
    target = EquipmentGroup(id=2, name="child", numb=101, main=100, niv=1, database_version_id=1)
    session.execute(EquipmentGroupType.__table__.insert(), {
        "id": 10, "name": "type", "database_version_id": 1,
    })
    shared = EquipmentGroupSetStation(id=1, station_id=50, equipment_group_type_id=10, database_version_id=1)
    source_set = EquipmentGroupSet(id=1, equipment_group_id=1, equipment_group_set_station=shared)
    target_set = EquipmentGroupSet(id=2, equipment_group_id=2, equipment_group_set_station=shared)
    session.execute(Machine.__table__.insert(), {
        "id": 1, "id_station": 50, "id_equipment_group": 10, "machine_number": "1",
        "database_version_id": 1, "external_code": "machine", "machine_name": "Machine",
    })
    machine = session.get(Machine, 1)
    mfp = MachineFuelParam(machine_id=1, equipment_group_id=1, numb1120=100, database_version_id=1)
    session.add_all([source, target, shared, source_set, target_set, mfp])
    session.flush()
    monkeypatch.setattr(service, "ensure_equipment_group_linked_to_station", lambda **kw: target_set)
    with app.test_request_context('/'):
        yield session, source, target, machine, mfp
    session.remove()
    engine.dispose()


def add_details(session, group_id, value=12):
    for model, field, extra in DETAILS:
        values = dict(equipment_group_id=group_id, year_number=2024, database_version_id=1, **extra)
        values[field] = "source formula" if field == "formtxt" else value
        if "numb1120" in model.__mapper__.attrs:
            values["numb1120"] = 100 if group_id == 1 else 101
        if model == EquipmentGroupFuelParam:
            values.update(ved=3, ved_cyrillic=4, snk=0)
        session.add(model(**values))
    session.flush()


def test_parent_transfer_moves_all_details_and_leaves_clean_head(transfer_db):
    session, source, target, machine, mfp = transfer_db
    add_details(session, 1)
    result = service.rebind_source_group_machines(source_group_id=1, target_group_id=2, version_id=1)
    session.flush()

    assert result["rebound_machines"] == 1
    assert result["moved_parameter_rows"] == len(DETAILS)
    assert (mfp.equipment_group_id, mfp.numb1120, machine.id_equipment_group) == (2, 101, 10)
    for model, field, _ in DETAILS:
        row = model.query.filter_by(equipment_group_id=2).one()
        assert getattr(row, field) == ("source formula" if field == "formtxt" else 12)
        if "numb1120" in model.__mapper__.attrs:
            assert row.numb1120 == 101
        if model != EquipmentGroupFuelParam:
            assert model.query.filter_by(equipment_group_id=1).count() == 0
    target_param = EquipmentGroupFuelParam.query.filter_by(equipment_group_id=2).one()
    assert (target_param.ved, target_param.ved_cyrillic, target_param.snk) == (3, 4, 0)
    head_rows = EquipmentGroupFuelParam.query.filter_by(equipment_group_id=1).all()
    assert {row.year_number for row in head_rows} == {2024, 2025, 2030}
    for row in head_rows:
        assert row.ved == 0
        assert row.nust is row.ved_cyrillic is row.snk is row.obor is None
    assert (source.comp, source.numb, source.name) == (1, 100, "head")
    assert source.niv is source.tm is source.n1 is source.p1 is source.note is None
    assert (target.tm, target.n1, target.p1, target.note) == ("turbine", "100", "130", "note")
    session.expire_all()
    source_link = EquipmentGroupSet.query.filter_by(equipment_group_id=1).one().equipment_group_set_station
    target_link = EquipmentGroupSet.query.filter_by(equipment_group_id=2).one().equipment_group_set_station
    assert source_link.equipment_group_type_id is None
    assert target_link.equipment_group_type_id == 10
    assert source_link.station_id == target_link.station_id == 50


def test_source_values_replace_collisions_and_keep_other_target_years(transfer_db):
    session, *_ = transfer_db
    add_details(session, 1, value=12)
    add_details(session, 2, value=99)
    session.add(EquipmentGroupFuelParam(equipment_group_id=2, year_number=2035, nust=55, ved=2, database_version_id=1))
    result = service.rebind_source_group_machines(source_group_id=1, target_group_id=2, version_id=1)
    session.flush()
    assert result["moved_parameter_rows"] == len(DETAILS)
    for model, field, _ in DETAILS:
        row = model.query.filter_by(equipment_group_id=2, year_number=2024).one()
        assert getattr(row, field) == ("source formula" if field == "formtxt" else 12)
    assert EquipmentGroupFuelParam.query.filter_by(equipment_group_id=2, year_number=2035).one().nust == 55


def test_all_years_variants_and_distribution_keys_are_preserved(transfer_db):
    session, *_ = transfer_db
    add_details(session, 1)
    session.add_all([
        EquipmentGroupFuelParam(equipment_group_id=1, year_number=1999, ved=2, nust=25, database_version_id=1),
        EquipmentGroupFuelFormula(equipment_group_id=1, year_number=2024, variant_number=2, formtxt="variant 2", database_version_id=1),
        EquipmentGroupCoefficientResult(equipment_group_id=1, year_number=2024, distribution_parameter_id=2, k=0.8, database_version_id=1),
    ])
    service.rebind_source_group_machines(source_group_id=1, target_group_id=2, version_id=1)
    session.flush()
    assert EquipmentGroupFuelParam.query.filter_by(equipment_group_id=2, year_number=1999).one().ved == 2
    assert EquipmentGroupFuelParam.query.filter_by(equipment_group_id=1, year_number=1999).one().ved == 0
    assert {row.variant_number for row in EquipmentGroupFuelFormula.query.filter_by(equipment_group_id=2)} == {1, 2}
    assert {row.distribution_parameter_id for row in EquipmentGroupCoefficientResult.query.filter_by(equipment_group_id=2)} == {1, 2}


@pytest.mark.parametrize("reverse", [False, True])
def test_failure_can_roll_back_machines_parameters_and_types(transfer_db, monkeypatch, reverse):
    session, source, target, machine, mfp = transfer_db
    add_details(session, 1)
    if reverse:
        service.rebind_source_group_machines(source_group_id=source.id, target_group_id=target.id, version_id=1)
        source, target = target, source
    session.commit()
    session.expire_all()
    from app.fuel.services.equipment_groups import equipment_group_edit_services as edit
    original = edit._apply_equipment_group_type_change_from_form

    def fail_clearing_head(group_id, type_id, version):
        if group_id == source.id:
            return "cannot clear source"
        return original(group_id, type_id, version)

    monkeypatch.setattr(edit, "_apply_equipment_group_type_change_from_form", fail_clearing_head)
    with pytest.raises(ValueError, match="cannot clear source"):
        service.rebind_source_group_machines(source_group_id=source.id, target_group_id=target.id, version_id=1)
    session.rollback()
    assert mfp.equipment_group_id == source.id
    assert source.tm == "turbine"
    assert EquipmentGroupFuelParam.query.filter_by(equipment_group_id=source.id).one().ved == 3
    if reverse:
        assert EquipmentGroupFuelParam.query.filter_by(equipment_group_id=target.id, year_number=2024).one().ved == 0
    else:
        assert EquipmentGroupFuelParam.query.filter_by(equipment_group_id=target.id).count() == 0
    assert EquipmentGroupSet.query.filter_by(equipment_group_id=source.id).one().equipment_group_set_station.equipment_group_type_id == 10


def test_repeated_transfer_does_not_overwrite_child_with_empty_head(transfer_db):
    session, *_ = transfer_db
    add_details(session, 1)
    service.rebind_source_group_machines(source_group_id=1, target_group_id=2, version_id=1)
    session.flush()
    session.expire_all()
    result = service.rebind_source_group_machines(source_group_id=1, target_group_id=2, version_id=1)
    session.flush()
    assert result["moved_parameter_rows"] is None
    assert EquipmentGroupFuelParam.query.filter_by(equipment_group_id=2, year_number=2024).one().nust == 12
    assert EquipmentGroupFuelParam.query.filter_by(equipment_group_id=1).count() == 3


@pytest.mark.parametrize("with_machines", [True, False])
@pytest.mark.parametrize("with_conflicts", [True, False])
def test_round_trip_restores_parameters_and_type_to_head(transfer_db, with_machines, with_conflicts):
    session, head, child, machine, mfp = transfer_db
    if not with_machines:
        session.delete(mfp)
    add_details(session, head.id)
    session.add(EquipmentGroupFuelParam(
        equipment_group_id=head.id, year_number=1999, ved=2, nust=25, database_version_id=1,
    ))
    service.rebind_source_group_machines(source_group_id=head.id, target_group_id=child.id, version_id=1)
    session.flush()
    session.expire_all()
    if with_conflicts:
        EquipmentGroupFuelParam.query.filter_by(equipment_group_id=head.id, year_number=2024).one().nust = 99
        for model, field, extra in DETAILS:
            if model == EquipmentGroupFuelParam:
                continue
            values = dict(equipment_group_id=head.id, year_number=2024, database_version_id=1, **extra)
            values[field] = "old formula" if field == "formtxt" else 99
            if "numb1120" in model.__mapper__.attrs:
                values["numb1120"] = head.numb
            session.add(model(**values))
        session.flush()

    result = service.rebind_source_group_machines(source_group_id=child.id, target_group_id=head.id, version_id=1)
    session.flush()
    session.expire_all()

    assert result["rebound_machines"] == int(with_machines)
    assert result["moved_parameter_rows"] == len(DETAILS) + 1
    assert (head.comp, head.main, head.niv, child.main, child.niv) == (1, None, 1, 100, 1)
    assert (head.tm, head.n1, head.p1, head.note) == ("turbine", "100", "130", "note")
    assert child.tm is child.n1 is child.p1 is child.note is None
    for model, field, _ in DETAILS:
        row = model.query.filter_by(equipment_group_id=head.id, year_number=2024).one()
        assert getattr(row, field) == ("source formula" if field == "formtxt" else 12)
        if "numb1120" in model.__mapper__.attrs:
            assert row.numb1120 == head.numb
        if model != EquipmentGroupFuelParam:
            assert model.query.filter_by(equipment_group_id=child.id).count() == 0
    assert EquipmentGroupFuelParam.query.filter_by(equipment_group_id=head.id, year_number=2024).one().ved == 3
    assert EquipmentGroupFuelParam.query.filter_by(equipment_group_id=head.id, year_number=1999).one().ved == 2
    assert all(row.ved == 0 and row.nust is None for row in EquipmentGroupFuelParam.query.filter_by(equipment_group_id=child.id))
    head_link = EquipmentGroupSet.query.filter_by(equipment_group_id=head.id).one().equipment_group_set_station
    child_link = EquipmentGroupSet.query.filter_by(equipment_group_id=child.id).one().equipment_group_set_station
    assert head_link.equipment_group_type_id == 10
    assert child_link.equipment_group_type_id is None
    assert head_link.station_id == child_link.station_id == 50
    if with_machines:
        assert (mfp.equipment_group_id, mfp.numb1120, machine.id_equipment_group) == (head.id, head.numb, 10)

    repeated = service.rebind_source_group_machines(source_group_id=child.id, target_group_id=head.id, version_id=1)
    assert repeated["moved_parameter_rows"] is None
    assert EquipmentGroupFuelParam.query.filter_by(equipment_group_id=head.id, year_number=2024).one().ved == 3


def test_ordinary_group_rebind_keeps_its_parameters(transfer_db):
    session, source, *_ = transfer_db
    source.comp = None
    add_details(session, 1)
    result = service.rebind_source_group_machines(source_group_id=1, target_group_id=2, version_id=1)
    session.flush()
    assert result["moved_parameter_rows"] is None
    assert EquipmentGroupFuelParam.query.filter_by(equipment_group_id=1).one().ved == 3
    assert source.tm == "turbine"


def test_rejects_cross_version_before_changing_anything(transfer_db):
    session, source, target, machine, mfp = transfer_db
    target.database_version_id = 2
    add_details(session, 1)
    result = service.rebind_source_group_machines(source_group_id=1, target_group_id=2, version_id=1)
    assert "error" in result
    assert mfp.equipment_group_id == 1
    assert source.tm == "turbine"


def test_parameters_can_move_even_without_bound_machines(transfer_db):
    session, source, target, machine, mfp = transfer_db
    session.delete(mfp)
    add_details(session, 1)
    result = service.rebind_source_group_machines(source_group_id=1, target_group_id=2, version_id=1)
    session.flush()
    assert result["rebound_machines"] == 0
    assert result["moved_parameter_rows"] == len(DETAILS)
    assert EquipmentGroupFuelParam.query.filter_by(equipment_group_id=2).one().ved == 3
