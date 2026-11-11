import pytest
from werkzeug.datastructures import MultiDict

from test_technical_characteristics import database, http_client
from app.extensions import db
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
from app.generation.models.machine.machine_model import Machine
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.generation.models.station.station_model import Station
from app.rational_structure.models import TechnicalInspectionCode, TurbineTechnicalCharacteristic as Turbine
from app.rational_structure.services.technical_characteristic_group_links import station_head_group_ids
from app.rational_structure.services.technical_characteristic_page_services import build_technical_characteristic_context


@pytest.fixture(autouse=True)
def group_tables(database):
    for model in (EquipmentGroup, MachineFuelParam):
        model.__table__.create(db.engine, checkfirst=True)


def group(*, numb=100, main=0, version=1):
    return db.session.execute(EquipmentGroup.__table__.insert().values(
        external_code=f"group-{version}-{numb}-{main}", numb=numb, main=main,
        database_version_id=version,
    )).inserted_primary_key[0]


def binding(group_id, *, code="turbine-code", version=1, saved=False, pgu=False):
    station_id = db.session.execute(Station.__table__.insert().values(
        external_code=f"station-{code}", name="Station", database_version_id=version,
    )).inserted_primary_key[0]
    machine_id = db.session.execute(Machine.__table__.insert().values(
        external_code=f"machine-{code}", machine_number="1", machine_name="Turbine",
        id_station=station_id, database_version_id=version,
    )).inserted_primary_key[0]
    db.session.execute(MachineFuelParam.__table__.insert().values(
        machine_id=machine_id, equipment_group_id=group_id, database_version_id=version,
    ))
    pgu_id = None
    if pgu:
        pgu_id = db.session.execute(PGUMachine.__table__.insert().values(
            id_parent_machine=machine_id, machine_name="Component", database_version_id=version,
        )).inserted_primary_key[0]
    turbine = Turbine(database_version_id=1, equipment_type="steam", equipment_code=code,
                      station_name="Station", report_year=2023, match_status="matched",
                      machine_id=machine_id, pgu_machine_id=pgu_id)
    db.session.add(turbine)
    if saved:
        db.session.add(TechnicalInspectionCode(database_version_id=1, equipment_code=code,
                                               machine_id=machine_id))
        turbine.machine_id = None
        turbine.match_status = "not_checked"
    db.session.commit()
    return turbine


@pytest.mark.parametrize("page_key,kind,path", [
    ("turbines", "gas", ""),
    ("hydro", "hydro", "/hydro"),
    ("boiler_energy", "boiler_energy", "/boilers/energy"),
    ("boiler_water", "boiler_water", "/boilers/water"),
])
@pytest.mark.parametrize("child", [False, True])
def test_all_tabs_link_object_to_turbine_head_group(http_client, page_key, kind, path, child):
    head = group()
    target = group(numb=101, main=100) if child else head
    binding(target)
    # Объект на другой вкладке может иметь другой год и код оборудования.
    row = Turbine(database_version_id=1, equipment_type=kind, equipment_code="other-code",
                  station_name=" Station ", report_year=2024)
    db.session.add(row)
    db.session.commit()
    context = build_technical_characteristic_context(MultiDict({"year": "2024"}), 1, page_key=page_key)
    assert context["station_head_group_ids"] == {"Station": head}
    client, _ = http_client
    response = client.get(f"/rational_structure/technical_characteristics{path}?year=2024")
    assert response.status_code == 200
    assert f'href="/fuel/equipment_group/{head}?year=2024"' in response.text
    assert "> Station </a>" in response.text


@pytest.mark.parametrize("saved,pgu", [(True, False), (False, True)])
def test_codes_from_cards_and_pgu_use_parent_machine_group(database, saved, pgu):
    head = group()
    row = binding(head, saved=saved, pgu=pgu)
    assert station_head_group_ids([row], 1) == {"Station": head}


def test_different_children_of_same_head_are_not_ambiguous(database):
    head = group()
    row = binding(group(numb=101, main=100))
    binding(group(numb=102, main=100), code="second")
    assert station_head_group_ids([row], 1) == {"Station": head}
    binding(group(numb=200), code="conflict")
    assert station_head_group_ids([row], 1) == {}


@pytest.mark.parametrize("case", ["missing-parent", "foreign-parent", "foreign-machine", "unmatched", "no-binding"])
def test_unresolved_objects_are_plain_text(http_client, case):
    if case == "foreign-parent":
        group(version=2)
    target = group(numb=101, main=100) if case in ("missing-parent", "foreign-parent") else group()
    row = binding(target, version=2 if case == "foreign-machine" else 1)
    if case == "unmatched":
        row.match_status = "partial"
    if case == "no-binding":
        db.session.query(MachineFuelParam).delete()
    db.session.commit()
    assert station_head_group_ids([row], 1) == {}
    client, _ = http_client
    response = client.get("/rational_structure/technical_characteristics?year=2023")
    assert response.status_code == 200
    assert "/fuel/equipment_group/" not in response.text


def test_current_version_parent_wins_over_shared_and_foreign(database):
    group(version=None)
    group(version=2)
    head = group()
    row = binding(group(numb=101, main=100))
    assert station_head_group_ids([row], 1) == {"Station": head}
    assert station_head_group_ids([row], None) == {}


def test_saved_card_code_overrides_stale_import_machine(database):
    old = binding(group())
    head = group(numb=200)
    current = binding(head, code="current")
    db.session.add(TechnicalInspectionCode(database_version_id=1, equipment_code=old.equipment_code,
                                           machine_id=current.machine_id))
    db.session.commit()
    assert station_head_group_ids([old], 1) == {"Station": head}
