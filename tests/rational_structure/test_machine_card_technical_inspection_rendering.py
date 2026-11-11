from pathlib import Path

import pytest
from jinja2 import Environment

from test_technical_characteristics import database
from test_technical_characteristic_machine_links import machine_factory
from app.extensions import db
from app.generation.models.machine.machine_model import Machine
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine
from app.rational_structure.models import EquipmentTechnicalCharacteristic, TechnicalInspectionCode


@pytest.mark.parametrize("pgu", [False, True])
@pytest.mark.parametrize("editable", [False, True])
@pytest.mark.parametrize("state", ["new", "empty", "matched", "saved_only"])
def test_technical_inspection_block_renders_for_machine_cards(
    database, machine_factory, pgu, editable, state,
):
    machine_id, _ = machine_factory()
    model = Machine
    entity_id = machine_id
    if pgu:
        model = PGUMachine
        entity_id = db.session.execute(PGUMachine.__table__.insert().values(
            id_parent_machine=machine_id, database_version_id=1,
            machine_number="ГТ-1", machine_name="ГТ-60",
        )).inserted_primary_key[0]

    if state != "new":
        link = {"pgu_machine_id" if pgu else "machine_id": entity_id}
        db.session.add(EquipmentTechnicalCharacteristic(
            database_version_id=1, equipment_type="steam", report_year=2023,
            equipment_code="partial-code", match_status="partial", **link,
        ))
        if state == "saved_only":
            db.session.add(TechnicalInspectionCode(
                database_version_id=1, machine_id=machine_id,
                pgu_machine_id=entity_id if pgu else None, equipment_code="stored-001",
            ))
        if state == "matched":
            db.session.add(EquipmentTechnicalCharacteristic(
                database_version_id=1, equipment_type="steam", report_year=2023,
                equipment_code="001000465562", match_status="matched", **link,
            ))
    db.session.commit()
    entity = None if state == "new" else db.session.get(model, entity_id)

    template_name = "pgu_machine_details.html" if pgu else "machine_details.html"
    path = Path(__file__).resolve().parents[2] / "app/templates/generation/stations" / template_name
    source = path.read_text(encoding="utf-8")
    # Render the actual inspection field without unrelated page forms/navigation.
    start = source.index("{% set ti_codes =")
    block = source[start:source.index("</div>", start)]
    environment = Environment(autoescape=True)
    html = environment.from_string(block).render(
        machine=entity, pgu_machine=entity,
        can_edit_generation_fields=editable, can_edit=editable,
        url_for=lambda endpoint: "/save-inspection-code",
    )

    assert "partial-code" not in html
    if editable:
        assert 'name="technical_inspection_code"' in html
        assert 'data-save-url="/save-inspection-code"' in html
        if state == "saved_only":
            assert 'value="stored-001"' in html
        elif state == "matched":
            assert 'value="001000465562"' in html
    elif state == "saved_only":
        assert "stored-001" in html
    elif state == "matched":
        assert "001000465562" in html
        assert "Паровые турбины" in html
        assert "2023 г." in html
    else:
        assert "не заполнены" in html
