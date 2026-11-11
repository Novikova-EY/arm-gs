from sqlalchemy import inspect, select

from test_technical_characteristics import database
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.rational_structure.models import (
    EquipmentTechnicalCharacteristic,
    TechnicalInspectionCode,
    TurbineTechnicalCharacteristic,
)


def test_generation_relationships_resolve_generalized_model(database):
    for model in (Machine, PGUMachine):
        relationship = inspect(model).relationships["turbine_technical_characteristics"]
        assert relationship.mapper.class_ is EquipmentTechnicalCharacteristic
    assert TechnicalInspectionCode.__table__.key in db.metadata.tables


def test_legacy_turbine_api_reads_and_writes_equipment_type(database):
    row = TurbineTechnicalCharacteristic(
        database_version_id=1, turbine_type="steam", equipment_code="legacy", report_year=2023,
    )
    db.session.add(row)
    db.session.commit()
    db.session.expire_all()

    stored = db.session.scalar(select(EquipmentTechnicalCharacteristic).where(
        TurbineTechnicalCharacteristic.turbine_type == "steam",
    ))
    assert stored.equipment_code == "legacy"
    assert stored.equipment_type == stored.turbine_type == "steam"

    stored.turbine_type = "gas"
    db.session.commit()
    db.session.expire_all()
    assert db.session.scalar(select(EquipmentTechnicalCharacteristic.equipment_type)) == "gas"
