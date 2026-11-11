from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask.templating import render_template
from openpyxl import load_workbook
from sqlalchemy import select

from test_territory_technologies import database, http_client, territory_database, workbook
from app.extensions import db
from app.rational_structure.models import TerritoryTechnology
from app.rational_structure.services.territory_technology_matching import match_technology_name
from app.rational_structure.services.territory_technology_services import import_territory_inputs
from app.refdata.models.refdata_for_stations.technologies.technology_type_model import TechnologyType
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import EquipmentGroupType


@pytest.fixture
def references(territory_database):
    records = [
        TechnologyType(id=10, name="АЭС", database_version_id=1),
        TechnologyType(id=11, name="ТЭС", database_version_id=1),
        TechnologyType(id=12, name="ГЭС", database_version_id=1),
        TechnologyType(id=13, name="накопитель (ГАЭС)", database_version_id=1),
        TechnologyType(id=20, name="Другой тип", database_version_id=2),
        EquipmentGroupType(id=100, name="ТЭЦ-130 ата", database_version_id=1, id_technology_type=11),
        EquipmentGroupType(id=101, name="Блоки 300К", database_version_id=1, id_technology_type=11),
        EquipmentGroupType(id=102, name="ГТУ-ТЭЦ", database_version_id=1, id_technology_type=11),
        EquipmentGroupType(id=103, name="прочее", database_version_id=1, id_technology_type=10),
        EquipmentGroupType(id=104, name="ТЭЦ<90 ата", database_version_id=1, id_technology_type=11),
        EquipmentGroupType(id=105, name="ТЭЦ-90 ата", database_version_id=1, id_technology_type=11),
        EquipmentGroupType(id=200, name="Чужая группа", database_version_id=2, id_technology_type=20),
    ]
    for model in (TechnologyType, EquipmentGroupType):
        db.session.execute(model.__table__.insert(), [
            {column.name: getattr(record, column.name) for column in model.__table__.columns
             if getattr(record, column.name) is not None}
            for record in records if isinstance(record, model)
        ])
    db.session.commit()
    from app.rational_structure.services.territory_technology_matching import technology_references
    return technology_references(1)


@pytest.mark.parametrize("name, expected", [
    ("ТЭЦ-130 ата_газ", (11, 100, "gas")),
    ("ТЭЦ-90 ата_газ", (11, 105, "gas")),
    ("ТЭЦ<90 ата_газ", (11, 104, "gas")),
    ("Блок 300К_уголь", (11, 101, "coal")),
    ("ГТУ-ТЭЦ", (11, 102, "gas")),
    ("АЭС", (10, None, "other")),
    ("Ивановская ГЭС", (12, None, "other")),
    ("Загорская ГАЭС 1,2", (13, None, "other")),
    ("Неизвестная технология", (None, None, None)),
    ("Неизвестная_прочее", (None, None, "other")),
    ("ТЭЦ-130 ата_газ_уголь", (11, 100, None)),
])
def test_match_name_components(references, name, expected):
    result = match_technology_name(name, references)
    assert tuple(result.values()) == expected


def test_ambiguous_groups_are_not_selected(references):
    references["equipment_group_types"].append(SimpleNamespace(id=999, name="ТЭЦ 130 ата", id_technology_type=11))
    assert match_technology_name("ТЭЦ-130 ата_газ", references)["equipment_group_type_id"] is None
    assert match_technology_name("Блок 3000К_газ", references)["equipment_group_type_id"] is None


def named_workbook(name):
    book = load_workbook(BytesIO(workbook()))
    book["Технологии"]["A4"] = name
    stream = BytesIO()
    book.save(stream)
    book.close()
    return stream.getvalue()


def test_import_matches_existing_rows_and_preserves_unknown_values(references):
    name = "ТЭЦ-130 ата_газ"
    import_territory_inputs(named_workbook(name), 1, "tester", "test.xlsx")
    row = db.session.scalar(select(TerritoryTechnology))
    assert row.name == name
    assert (row.technology_type_id, row.equipment_group_type_id, row.fuel_category) == (11, 100, "gas")
    assert row.energy_zone.number == "1"
    row.technology_type_id = None
    row.equipment_group_type_id = None
    db.session.commit()
    import_territory_inputs(named_workbook(name), 1, "tester", "test.xlsx")
    assert row.technology_type_id == 11
    import_territory_inputs(named_workbook("Новый вид"), 1, "tester", "test.xlsx")
    unknown = db.session.scalar(select(TerritoryTechnology).where(TerritoryTechnology.name == "Новый вид"))
    assert unknown is not None and unknown.technology_type_id is None
    import_territory_inputs(named_workbook(name), 2, "tester", "test.xlsx")
    other = db.session.scalar(select(TerritoryTechnology).where(TerritoryTechnology.database_version_id == 2))
    assert other.technology_type_id is None and other.equipment_group_type_id is None


def test_manual_replacement_validation_and_reimport(references, http_client, monkeypatch, territory_database):
    from app.rational_structure.routes import territory_technology_routes as routes
    monkeypatch.setattr(routes, "log_to_db", lambda *args, **kwargs: None)
    monkeypatch.setattr(routes, "render_template", render_template)
    client, user = http_client
    raw = named_workbook("Неизвестная технология")
    import_territory_inputs(raw, 1, "tester", "test.xlsx")
    row = db.session.scalar(select(TerritoryTechnology))
    endpoint = f"/rational_structure/territory_technologies/{row.id}/references"
    payload = dict(database_version_id="1", technology_type_id="11", equipment_group_type_id="100", fuel_category="coal")
    # CSRF remains required even for a valid replacement.
    assert client.post(endpoint, data=payload).status_code == 302
    assert row.technology_type_id is None
    territory_database.config["WTF_CSRF_ENABLED"] = False
    for invalid in (dict(payload, database_version_id="2"), dict(payload, technology_type_id="20"),
                    dict(payload, equipment_group_type_id="200"), dict(payload, technology_type_id="10"),
                    dict(payload, fuel_category="invalid")):
        assert client.post(endpoint, data=invalid).status_code == 302
        assert row.technology_type_id is None
    assert client.post(endpoint, data=payload).status_code == 302
    assert (row.technology_type_id, row.equipment_group_type_id, row.fuel_category) == (11, 100, "coal")
    assert row.references_manual and row.name == "Неизвестная технология"
    import_territory_inputs(raw, 1, "tester", "again.xlsx")
    assert row.fuel_category == "coal" and row.technology_type_id == 11
    html = client.get("/rational_structure/territory_technologies").get_data(as_text=True)
    assert '<th scope="col" rowspan="2" class="d-none">Энергозона</th>' in html
    assert '<th scope="col" rowspan="2" class="d-none">Справочники</th>' in html
    assert f'<td class="d-none">{row.energy_zone.name}</td>' in html
    assert '<td class="d-none">\n                    <div>Тип:' in html
    assert '<th scope="col" rowspan="2">ЭЗ</th>' in html
    assert 'name="technology_type_id"' in html and 'name="equipment_group_type_id"' in html
    assert 'value="100" selected' in html and 'value="200"' not in html
    assert client.post(endpoint, data=dict(payload, technology_type_id="", equipment_group_type_id="", fuel_category="")).status_code == 302
    import_territory_inputs(raw, 1, "tester", "again.xlsx")
    assert row.technology_type_id is None and row.fuel_category is None
    user.has_admin = False
    assert client.post(endpoint, data=payload).status_code == 403


def test_group_can_supply_technology_and_foreign_row_is_not_editable(references, http_client, monkeypatch, territory_database):
    from app.rational_structure.routes import territory_technology_routes as routes
    monkeypatch.setattr(routes, "log_to_db", lambda *args, **kwargs: None)
    client, _ = http_client
    territory_database.config["WTF_CSRF_ENABLED"] = False
    raw = workbook()
    import_territory_inputs(raw, 1, "tester", "test.xlsx")
    row = db.session.scalar(select(TerritoryTechnology))
    assert client.post(f"/rational_structure/territory_technologies/{row.id}/references", data={
        "database_version_id": "1", "technology_type_id": "", "equipment_group_type_id": "100", "fuel_category": "gas",
    }).status_code == 302
    assert row.technology_type_id == 11
    import_territory_inputs(raw, 2, "tester", "test.xlsx")
    other = db.session.scalar(select(TerritoryTechnology).where(TerritoryTechnology.database_version_id == 2))
    assert client.post(f"/rational_structure/territory_technologies/{other.id}/references", data={
        "database_version_id": "1",
    }).status_code == 404


REAL_WORKBOOK = Path("z:/НИО-10/АРМ ГС/05. Шаблоны для АРМ ГС/12. Рациональная структура/Расчетные файлы/Ввод данных_1.xlsx")


@pytest.mark.skipif(not REAL_WORKBOOK.exists(), reason="User workbook is unavailable")
def test_user_workbook_imports_without_recalculation(references):
    counts = import_territory_inputs(REAL_WORKBOOK.read_bytes(), 1, "tester", REAL_WORKBOOK.name)
    rows = list(db.session.scalars(select(TerritoryTechnology)))
    assert counts["technologies"] == len(rows) and len(rows) > 100
    assert counts["sections"] == 13
    assert all(row.energy_zone.number in {str(number) for number in range(1, 14)} for row in rows)
    assert any(row.name == "ТЭЦ-130 ата_газ" and row.equipment_group_type_id == 100 for row in rows)
