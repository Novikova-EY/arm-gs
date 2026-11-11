from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from jinja2 import Environment

from app.fuel.services.stations.stations_equipment_groups_services import (
    _split_group_block_by_station_hierarchy,
    _paginate_equipment_group_hierarchy,
    build_equipment_group_blocks_hierarchy,
)


def _group_block(group_id):
    return {
        "equipment_group": SimpleNamespace(
            id=group_id,
            name=f"Группа {group_id}",
            name_ext=None,
            numb=group_id,
            comp=None,
            main=None,
        ),
        "rowspan": 1,
        "station_entries": [
            {
                "station": None,
                "station_rowspan": 1,
                "links": [
                    {
                        "equipment_group_type": None,
                        "machines": [],
                        "rowspan": 1,
                    }
                ],
            }
        ],
    }


def test_decentralized_zone_is_a_top_level_hierarchy_section(monkeypatch):
    monkeypatch.setattr(
        "app.common.services.get_services.energy_systems.union_energy_system_get_services.get_union_energy_system_display_order_map",
        lambda: {},
    )
    hierarchy = build_equipment_group_blocks_hierarchy(
        {
            (164, -1, -1, 715, 715): [_group_block(1)],
            (72, 5, 10, 715, 715): [_group_block(2)],
        },
        energy_system_type_names={
            72: "ЕЭС России",
            164: "Децентрализованная зона",
        },
        union_energy_system_names={5: "ОЭС"},
        regional_energy_system_names={10: "РЭС"},
        union_energy_system_display_orders={},
    )

    assert [block["est_name"] for block in hierarchy] == [
        "ЕЭС России",
        "Децентрализованная зона",
    ]
    dz_block = hierarchy[1]
    assert dz_block["is_decentralized_zone"] is True
    assert dz_block["ues_list"][0]["ues_id"] == -1


def test_decentralized_zone_marker_survives_pagination():
    hierarchy = [
        {
            "est_id": 164,
            "est_name": "Децентрализованная зона",
            "is_decentralized_zone": True,
            "ues_list": [
                {
                    "ues_id": -1,
                    "ues_name": "Не указано",
                    "res_list": [
                        {
                            "res_id": -1,
                            "res_name": "Не указано",
                            "equipment_group_blocks": [_group_block(1)],
                        }
                    ],
                }
            ],
        }
    ]

    paged, total, pages, current_page = _paginate_equipment_group_hierarchy(
        hierarchy, page=1, per_page=1
    )

    assert (total, pages, current_page) == (1, 1, 1)
    assert paged[0]["is_decentralized_zone"] is True
    assert paged[0]["ues_list"][0]["res_list"][0]["equipment_group_blocks"]


def test_decentralized_zone_linked_group_uses_station_card_hierarchy():
    district = SimpleNamespace(id=715, regional_energy_systems=[])

    def _group(group_id, res_id, *, numb, main=None, comp=None):
        res = SimpleNamespace(
            id=res_id,
            union_energy_system=SimpleNamespace(
                id=20,
                energy_system_type=SimpleNamespace(id=72),
            ),
        )
        return SimpleNamespace(
            id=group_id,
            name=f"Группа {group_id}",
            name_ext=None,
            numb=numb,
            main=main,
            comp=comp,
            regional_district_id=715,
            regional_district=district,
            regional_energy_system_id=res_id,
            regional_energy_system=res,
            equipment_group_links_v2=[],
        )

    equipment_group = _group(1, 100, numb=301, main=300)
    parent_group = _group(2, 200, numb=300, comp=1)
    station = SimpleNamespace(
        id=99,
        name="Станция ДЭЗ",
        id_regional_district=715,
        database_version_id=20,
        regional_district=SimpleNamespace(id=715),
    )
    block = {
        "equipment_group": equipment_group,
        "rowspan": 1,
        "station_entries": [
            {
                "station": station,
                "station_rowspan": 1,
                "links": [
                    {
                        "equipment_group_type": None,
                        "machines": [],
                        "rowspan": 1,
                    }
                ],
            }
        ],
    }

    with (
        patch(
            "app.generation.services.station_services.station_access_services.is_decentralized_zone_station",
            return_value=True,
        ),
        patch(
            "app.generation.services.station_services.station_access_services.get_decentralized_zone_energy_system_type_id",
            return_value=74,
        ),
    ):
        split_blocks = _split_group_block_by_station_hierarchy(
            block, parent_by_numb={300: parent_group}
        )

    assert [key for key, _ in split_blocks] == [(74, -1, -1, 715, 715)]


def test_decentralized_zone_template_renders_one_section_header_without_fake_levels():
    source = Path(
        "app/templates/fuel/equipment_groups/stations_equipment_groups.html"
    ).read_text(encoding="utf-8")
    hierarchy_start = source.index("{% if equipment_group_blocks_hierarchy %}")
    hierarchy_end = source.index("{% elif equipment_group_flat_station_blocks %}")
    hierarchy_template = source[hierarchy_start:hierarchy_end] + "{% endif %}"
    template = Environment(autoescape=True).from_string(
        """
        {% macro render_equipment_group_rows(blocks, duplicate_ids) %}
            GROUP_ROWS
        {% endmacro %}
        {% set column_count = 4 %}
        """
        + hierarchy_template
    )
    hierarchy = [
        SimpleNamespace(
            est_id=164,
            est_name="Децентрализованная зона",
            is_decentralized_zone=True,
            ues_list=[
                SimpleNamespace(
                    ues_id=-1,
                    ues_name="Не указано",
                    res_list=[
                        SimpleNamespace(
                            res_id=-1,
                            res_name="Не указано",
                            equipment_group_blocks=[_group_block(1)],
                        )
                    ],
                )
            ],
        )
    ]

    html = template.render(
        equipment_group_blocks_hierarchy=hierarchy,
        equipment_group_flat_station_blocks=[],
        duplicate_numb_ids=set(),
    )

    assert "Децентрализованная зона" in html
    assert "GROUP_ROWS" in html
    assert "Не указано" not in html
