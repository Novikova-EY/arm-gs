from types import SimpleNamespace

from openpyxl import load_workbook

from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.services.fuel_exports import export_stations_equipment_groups_services as export_service


def test_export_uses_station_and_equipment_group_status_labels(monkeypatch):
    cases = [
        (None, None, "новая", "новая станция"),
        (0, 0, "новая", "новая станция"),
        (1, 1, "действующая", "действующая группа оборудования"),
        (1, 2, "действующая", "новая группа оборудования действующей станции"),
        (9, 9, "демонтирована", "демонтирована"),
    ]
    blocks = []
    for group_id, (d, r, _, _) in enumerate(cases, 1):
        fields = dict.fromkeys(EquipmentGroup.__table__.columns.keys())
        fields.update(id=group_id, numb=group_id, name=f"Group {group_id}", d=d, r=r)
        group = SimpleNamespace(**fields, cities_external_mapping=None)
        blocks.append({
            "equipment_group": group,
            "station_entries": [{
                "station": None,
                "links": [{"equipment_group_type": None, "machines": [None]}],
            }],
        })
    hierarchy = [{"ues_list": [{"res_list": [{"equipment_group_blocks": blocks}]}]}]
    monkeypatch.setattr(
        export_service, "build_equipment_group_hierarchy_eg_first",
        lambda **kwargs: (hierarchy, len(blocks), 1, 1),
    )
    for name in ("get_energy_system_type_map", "get_union_energy_systems_map", "get_regional_energy_systems_map"):
        monkeypatch.setattr(export_service, name, lambda: {})

    output = export_service.export_stations_equipment_groups_to_excel({}, 2026, 2042)
    workbook = load_workbook(output, read_only=True)
    rows = [
        [value.replace("\xa0", " ") if isinstance(value, str) else value for value in row]
        for row in workbook.active.values
    ]
    d_index = rows[0].index("Признак действующей станции (d)")
    r_index = rows[0].index("Признак расширяемой станции (r)")
    data_rows = [row for row in rows[1:] if isinstance(row[0], int)]
    assert [(row[d_index], row[r_index]) for row in data_rows] == [
        (d_label, r_label) for _, _, d_label, r_label in cases
    ]
    workbook.close()
