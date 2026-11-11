# -*- coding: utf-8 -*-
"""Привязка *_calc к своей группе (NUMB), году и версии БД."""
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, inspect, select, update
from sqlalchemy.orm import scoped_session, sessionmaker

import app.electrical_intensity.models  # noqa: F401 – связи модели Year
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
    EquipmentGroupSpecificFuelConsumption as Consumption,
)
from app.fuel.services.equipment_groups import (
    equipment_group_specific_fuel_consumption_recalc_services as recalc,
    equipment_group_specific_fuel_consumption_services as service,
)
from app.fuel.services.calculation.fuel_calculation_specific_consumption_edit_data_services import (
    _MissingYearSpecificFuelParam,
)


CALC_ATTRS = ("y_calc", "btp_calc", "sntp_calc", "bk_calc", "snk_calc")


@pytest.fixture
def fuel_session(monkeypatch):
    engine = create_engine("sqlite://", execution_options={
        "schema_translate_map": {EquipmentGroup.__table__.schema: None},
    })
    for model in (EquipmentGroup, EquipmentGroupFuelParam, Consumption):
        model.__table__.create(engine)
    sessions = scoped_session(sessionmaker(bind=engine))
    with sessions() as session:
        monkeypatch.setattr(db, "session", sessions)
        monkeypatch.setattr(recalc, "get_current_db_version_id", lambda: 20)
        monkeypatch.setattr(service, "get_current_db_version_id", lambda: 20)
        yield session
    sessions.remove()
    engine.dispose()


def add_group(session, gid, numb, version=20):
    session.execute(EquipmentGroup.__table__.insert().values(
        id=gid, numb=numb, external_code=f"eg-{gid}", database_version_id=version,
        name="Череповецкая ГРЭС (котельная)",
    ))
    return session.get(EquipmentGroup, gid)


def add_param(session, gid, numb, year=2024, version=20, **values):
    session.execute(EquipmentGroupFuelParam.__table__.insert().values(
        equipment_group_id=gid, numb1120=numb, year_number=year,
        database_version_id=version, **values,
    ))


def add_consumption(session, gid, numb, year=2024, version=20, k=None):
    session.execute(Consumption.__table__.insert().values(
        equipment_group_id=gid, numb1120=numb, year_number=year,
        database_version_id=version, k=k, **dict.fromkeys(CALC_ATTRS, 999),
    ))
    return session.query(Consumption).filter_by(
        equipment_group_id=gid, year_number=year,
    ).one()


def calc_values(consumption):
    return tuple(getattr(consumption, attr) for attr in CALC_ATTRS)


def test_display_uses_own_numb_year_version_and_does_not_hide_ved_zero(fuel_session):
    s = fuel_session
    rows = []
    # Сервер gs01: NUMB=110 – итог станции, NUMB=111 – котельная, а не та же строка.
    for gid, numb, version, ved, eurt, snk in [
        (1, 110, 20, 0, "227.5435", "4.417067"),
        (2, 111, 20, 2, None, None),
        (3, 1217, 20, 1, "225", "5"),
        (4, 110, 22, 0, "350", "8"),
    ]:
        eg = add_group(s, gid, numb, version)
        add_param(s, gid, numb, version=version, ved=ved, eurt=eurt, snk=snk)
        rows.append((eg, add_consumption(s, gid, numb, version=version)))
    add_param(s, 1, 110, year=2023, ved=0, eurt=400, snk=9)
    old_year = add_consumption(s, 1, 110, year=2023)
    rows.append((rows[0][0], old_year))
    s.commit()

    service.overlay_specific_fuel_consumption_calc_from_fuel_params(rows)

    expected = [
        (0, 0, 0, Decimal("227.543500"), Decimal("4.417067")),
        (0, 0, 0, 0, None),
        (0, 0, 0, 225, 5),
        (0, 0, 0, 350, 8),
        (0, 0, 0, 400, 9),
    ]
    assert [calc_values(cons) for _, cons in rows] == expected
    for _, cons in rows:
        assert all(not inspect(cons).attrs[attr].history.has_changes() for attr in CALC_ATTRS)
        assert cons.bk is None  # Загруженные удельники не подменяются расчетными.
    assert not s.dirty
    stored = s.execute(select(Consumption.__table__.c.bk_calc)).scalars().all()
    assert stored == [Decimal(999)] * len(rows)


def test_all_calc_fields_use_same_year_inputs_and_own_coefficient(fuel_session):
    s = fuel_session
    eg = add_group(s, 1, 111)
    rows = []
    for year, k in [(2023, 1), (2024, 2)]:
        add_param(s, 1, 111, year=year, ved=2, e=1000, ewtp=200,
                  eotp=900, eurt=400, eust=300, snk=10, sn_ee=100, qotr=100)
        rows.append((eg, add_consumption(s, 1, 111, year=year, k=k)))
    service.overlay_specific_fuel_consumption_calc_from_fuel_params(rows)
    assert calc_values(rows[0][1]) == (2000, 320, Decimal("0.9"), Decimal("336.666667"), 10)
    assert calc_values(rows[1][1]) == (2000, 240, Decimal("0.9"), Decimal("356.666667"), 10)


@pytest.mark.parametrize("bad_source", ["year", "version", "numb", "absent"])
def test_display_never_uses_another_source_or_stale_saved_calc(fuel_session, bad_source):
    s = fuel_session
    eg = add_group(s, 1, 111)
    cons = add_consumption(s, 1, 111)
    if bad_source != "absent":
        add_param(s, 1, 110 if bad_source == "numb" else 111,
                  year=2023 if bad_source == "year" else 2024,
                  version=22 if bad_source == "version" else 20,
                  ved=2, eurt=400, snk=9)
    # Соседняя группа с тем же названием не является источником.
    add_group(s, 2, 1217)
    add_param(s, 2, 1217, ved=1, eurt=300, snk=7)
    service.overlay_specific_fuel_consumption_calc_from_fuel_params([(eg, cons)])
    assert calc_values(cons) == (None,) * 5


def test_legacy_null_numb_uses_only_own_group_fk(fuel_session):
    s = fuel_session
    eg = add_group(s, 1, 110, version=None)
    add_param(s, 1, None, version=None, ved=0, eurt=250, snk=6)
    cons = add_consumption(s, 1, 110, version=None)
    service.overlay_specific_fuel_consumption_calc_from_fuel_params([(eg, cons)])
    assert calc_values(cons) == (0, 0, 0, 250, 6)


def test_missing_year_placeholder_stays_empty(fuel_session):
    s = fuel_session
    eg = add_group(s, 1, 110)
    add_param(s, 1, 110, year=2027, ved=0, eurt=250, snk=6)
    missing = _MissingYearSpecificFuelParam(2027)
    service.overlay_specific_fuel_consumption_calc_from_fuel_params([(eg, missing)])
    assert calc_values(missing) == (None,) * 5


@pytest.mark.parametrize("all_versions", [False, True])
def test_recalc_preserves_version_scope_and_matches_display(fuel_session, all_versions):
    s = fuel_session
    rows = []
    for gid, version, eurt in [(1, 20, 250), (2, 22, 350), (3, None, 450)]:
        eg = add_group(s, gid, 110, version)
        add_param(s, gid, 110, version=version, ved=0, eurt=eurt, snk=6)
        rows.append((eg, add_consumption(s, gid, 110, version=version)))
    s.commit()
    count = recalc.recalculate_all_specific_fuel_consumption_calc(
        year=2024, all_versions=all_versions, commit=False,
    )
    assert count == (3 if all_versions else 1)
    assert calc_values(rows[0][1]) == (0, 0, 0, 250, 6)
    assert calc_values(rows[1][1]) == ((0, 0, 0, 350, 6) if all_versions else (999,) * 5)
    assert calc_values(rows[2][1]) == ((0, 0, 0, 450, 6) if all_versions else (999,) * 5)
    assert [cons.database_version_id for _, cons in rows] == [20, 22, None]
    s.flush()
    expected = [calc_values(cons) for _, cons in rows]
    service.overlay_specific_fuel_consumption_calc_from_fuel_params(rows)
    if all_versions:
        assert [calc_values(cons) for _, cons in rows] == expected


def test_recalc_does_not_relabel_foreign_version_consumption(fuel_session):
    s = fuel_session
    add_group(s, 1, 110)
    add_param(s, 1, 110, ved=0, eurt=250, snk=6)
    foreign = add_consumption(s, 1, 110, version=22, k=99)
    assert recalc.recalculate_all_specific_fuel_consumption_calc(year=2024, commit=False) == 0
    assert foreign.database_version_id == 22
    assert foreign.k == 99
    assert calc_values(foreign) == (999,) * 5


@pytest.mark.parametrize("all_versions", [False, True])
def test_recalc_rejects_source_with_wrong_numb_or_version(fuel_session, all_versions):
    s = fuel_session
    add_group(s, 1, 110)
    add_param(s, 1, 111, ved=0, eurt=250, snk=6)
    cons1 = add_consumption(s, 1, 110)
    add_group(s, 2, 1217)
    add_param(s, 2, 1217, version=22, ved=1, eurt=350, snk=8)
    cons2 = add_consumption(s, 2, 1217)
    count = recalc.recalculate_all_specific_fuel_consumption_calc(
        year=2024, all_versions=all_versions, commit=False,
    )
    assert count == 0
    assert calc_values(cons1) == calc_values(cons2) == (999,) * 5


def test_recalc_creates_legacy_row_without_assigning_active_version(fuel_session):
    s = fuel_session
    add_group(s, 1, 110, version=None)
    add_param(s, 1, 110, version=None, ved=0, eurt=250, snk=6)
    assert recalc.recalculate_all_specific_fuel_consumption_calc(
        year=2024, all_versions=True, commit=False,
    ) == 1
    created = s.query(Consumption).one()
    assert created.database_version_id is None
    assert created.numb1120 == 110
    assert calc_values(created) == (0, 0, 0, 250, 6)


def add_composite_station(session, *, version=20):
    parent = add_group(session, 1, 34, version)
    session.execute(update(EquipmentGroup).where(EquipmentGroup.id == 1).values(comp=1))
    for gid, numb, ved in [(2, 35, 1), (3, 36, 2)]:
        add_group(session, gid, numb, version)
        session.execute(update(EquipmentGroup).where(EquipmentGroup.id == gid).values(main=34, niv=1))
        add_param(session, gid, numb, version=version, ved=ved, eurt=400, snk=6)
        add_consumption(session, gid, numb, version=version)
    add_param(session, 1, 34, version=version, ved=0, eurt=390, snk=5)
    add_consumption(session, 1, 34, version=version)
    return parent


def test_tep_excludes_parent_before_mismatch_filter_and_counts(fuel_session):
    s = fuel_session
    add_composite_station(s)
    data = service.get_equipment_groups_with_specific_fuel_consumption_data(
        start_year=2024, end_year=2024,
    )
    assert {eg.numb for eg, _ in data["rows"]} == {35, 36}
    assert data["total_count"] == 2
    assert {eg.numb for eg, cons in data["rows"]
            if service.consumption_has_calc_mismatch(cons)} == {35, 36}
    # Отбор отображения не удаляет родителя или его исходные данные.
    assert s.query(Consumption).filter_by(equipment_group_id=1).count() == 1


def test_tep_parent_code_filter_does_not_bypass_exclusion(fuel_session):
    add_composite_station(fuel_session)
    data = service.get_equipment_groups_with_specific_fuel_consumption_data(
        filters={"equipment_group_ids": [1]}, start_year=2024, end_year=2024,
    )
    assert data["rows"] == []
    assert data["total_count"] == 0


@pytest.mark.parametrize("year,version,ved,hidden", [
    (2024, 20, 1, True),
    (2023, 20, 1, False),
    (2024, 22, 1, False),
    (2024, 20, 0, False),
])
def test_parent_exclusion_requires_active_child_in_own_year_and_version(
    fuel_session, year, version, ved, hidden,
):
    s = fuel_session
    parent = add_group(s, 1, 34)
    s.execute(update(EquipmentGroup).where(EquipmentGroup.id == 1).values(comp=1))
    cons = add_consumption(s, 1, 34)
    add_group(s, 2, 35, version)
    s.execute(update(EquipmentGroup).where(EquipmentGroup.id == 2).values(main=34))
    add_param(s, 2, 35, year=year, version=version, ved=ved)
    rows = [(parent, cons)]
    result = service.filter_specific_consumption_composite_parent_rows(rows, 2024, 2024)
    assert result == ([] if hidden else rows)


def test_parent_without_consumption_is_not_shown_beside_active_children(fuel_session):
    s = fuel_session
    parent = add_composite_station(s)
    assert service.filter_specific_consumption_composite_parent_rows(
        [(parent, None)], 2024, 2024,
    ) == []


def test_parent_keeps_historical_station_only_year(fuel_session):
    s = fuel_session
    parent = add_composite_station(s)
    historical = add_consumption(s, 1, 34, year=2010)
    current = s.query(Consumption).filter_by(equipment_group_id=1, year_number=2024).one()
    assert service.filter_specific_consumption_composite_parent_rows(
        [(parent, historical), (parent, current)], 2010, 2024,
    ) == [(parent, historical)]


def test_tep_keeps_nonparent_ved_zero_and_unsplit_station(fuel_session):
    s = fuel_session
    eg = add_group(s, 1, 110)
    add_param(s, 1, 110, ved=0, eurt=250, snk=6)
    add_consumption(s, 1, 110)
    add_group(s, 2, 200)
    s.execute(update(EquipmentGroup).where(EquipmentGroup.id == 2).values(comp=1))
    add_param(s, 2, 200, ved=1, eurt=350, snk=7)
    add_consumption(s, 2, 200)
    data = service.get_equipment_groups_with_specific_fuel_consumption_data(
        start_year=2024, end_year=2024,
    )
    assert {group.id for group, _ in data["rows"]} == {eg.id, 2}
    assert next(cons.bk_calc for group, cons in data["rows"] if group.id == eg.id) == 250


@pytest.mark.parametrize("show_calc_mismatch", [False, True])
def test_tep_hierarchy_and_export_do_not_recreate_parent_total(
    fuel_session, monkeypatch, show_calc_mismatch,
):
    from openpyxl import load_workbook
    from app.fuel.services.fuel_exports.export_stations_equipment_group_specific_fuel_consumption_services import (
        export_stations_equipment_group_specific_fuel_consumption_to_excel,
    )
    s = fuel_session
    parent = add_composite_station(s)
    monkeypatch.setattr(service, "resolve_composite_parents_by_numb", lambda *a, **k: {34: parent})
    monkeypatch.setattr(service, "territorial_ids_for_equipment_group", lambda *a, **k: (1, 2, 3))
    monkeypatch.setattr(
        "app.fuel.services.equipment_groups.equipment_group_fuel_params_services."
        "_get_equipment_group_station_mapping_with_display_order", lambda *a, **k: {},
    )
    for module, func, result in [
        ("energy_system_type", "get_energy_system_type_map", {1: "ЕЭС"}),
        ("regional_energy_system", "get_regional_energy_systems_name_map", {3: "РЭС"}),
        ("union_energy_system", "get_union_energy_systems_map", {2: "ОЭС"}),
        ("union_energy_system", "get_union_energy_system_display_order_map", {}),
    ]:
        monkeypatch.setattr(
            f"app.common.services.get_services.energy_systems.{module}_get_services.{func}",
            lambda result=result: result,
        )
    data = service.get_equipment_groups_with_specific_fuel_consumption_data(
        start_year=2024, end_year=2024,
    )
    hierarchy = service.build_equipment_group_specific_fuel_consumption_hierarchy(data["rows"])
    blocks = hierarchy[0]["ues_list"][0]["res_list"][0]["group_blocks"]
    assert {gb["equipment_group"].id for gb in blocks} == {2, 3}
    excel = export_stations_equipment_group_specific_fuel_consumption_to_excel(
        {}, 2024, 2024, show_calc_mismatch=show_calc_mismatch,
    )
    wb = load_workbook(excel)
    ids = {row[0] for row in wb.active.iter_rows(min_row=2, values_only=True)
           if str(row[0]).isdigit()}
    assert ids == {"2", "3"}
