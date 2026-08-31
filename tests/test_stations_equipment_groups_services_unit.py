from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.services.stations.stations_equipment_groups_services import (
    _eg_station_regional_district_consistent,
    _group_block_display_sort_key,
    _hierarchy_key_from_equipment_group,
    _merge_adjacent_group_blocks_for_display,
    _merge_adjacent_station_entries_for_display,
    _parent_groups_from_blocks,
    _reapply_display_merges_for_page_blocks,
    _split_group_block_by_station_hierarchy,
    _territorial_filter_or_fk_or_obl,
    filter_legacy_duplicate_equipment_group_ids,
    prepare_equipment_group_blocks_for_display,
)


def _station(station_id, name):
    return SimpleNamespace(id=station_id, name=name)


def _equipment_group(group_id, name, *, main=None, comp=None, numb=None):
    return SimpleNamespace(
        id=group_id, name=name, name_ext=None, main=main, comp=comp, numb=numb
    )


def test_merge_adjacent_station_entries_does_not_merge_homonym_stations():
    """Две ТЭС-2 с разными id (Сегежский / Кондопожский ЦБК) остаются отдельными строками."""
    blocks = [
        {
            "station_entries": [
                {
                    "station": _station(28434, "ТЭС-2"),
                    "station_rowspan": 2,
                    "links": [],
                }
            ]
        },
        {
            "station_entries": [
                {
                    "station": _station(29702, "ТЭС-2"),
                    "station_rowspan": 3,
                    "links": [],
                }
            ]
        },
    ]

    _merge_adjacent_station_entries_for_display(blocks)

    first_entry = blocks[0]["station_entries"][0]
    second_entry = blocks[1]["station_entries"][0]

    assert first_entry["show_merged_station_cells"] is True
    assert first_entry["merged_station_rowspan"] == 2
    assert second_entry["show_merged_station_cells"] is True
    assert second_entry["merged_station_rowspan"] == 3


def test_merge_adjacent_station_entries_for_same_station_id():
    station = _station(1, "Архангельская ТЭЦ")
    blocks = [
        {
            "station_entries": [
                {
                    "station": station,
                    "station_rowspan": 2,
                    "links": [],
                }
            ]
        },
        {
            "station_entries": [
                {
                    "station": _station(1, "Архангельская ТЭЦ"),
                    "station_rowspan": 3,
                    "links": [],
                }
            ]
        },
    ]

    _merge_adjacent_station_entries_for_display(blocks)

    first_entry = blocks[0]["station_entries"][0]
    second_entry = blocks[1]["station_entries"][0]

    assert first_entry["show_merged_station_cells"] is True
    assert first_entry["merged_station_rowspan"] == 5
    assert second_entry["show_merged_station_cells"] is False


def test_merge_adjacent_station_entries_does_not_merge_none_stations():
    """Standalone-группы без станции не склеиваются в один rowspan по ключу «—»."""
    blocks = [
        {
            "station_entries": [
                {"station": None, "station_rowspan": 1, "links": []},
            ]
        },
        {
            "station_entries": [
                {"station": None, "station_rowspan": 1, "links": []},
            ]
        },
        {
            "station_entries": [
                {"station": None, "station_rowspan": 1, "links": []},
            ]
        },
    ]

    _merge_adjacent_station_entries_for_display(blocks)

    for block in blocks:
        entry = block["station_entries"][0]
        assert entry["show_merged_station_cells"] is True
        assert entry["merged_station_rowspan"] == 1


def test_reapply_display_merges_after_page_slice_restores_station_cells():
    """
    После merge по полной ветке хвост страницы имел show=False.
    Пересчёт на срезе страницы снова показывает ячейку станции.
    """
    station = _station(1, "Новомосковская ГРЭС")
    blocks = [
        {
            "equipment_group": _equipment_group(1, "Группа A"),
            "rowspan": 1,
            "station_entries": [
                {"station": station, "station_rowspan": 1, "links": []},
            ],
        },
        {
            "equipment_group": _equipment_group(2, "Группа B"),
            "rowspan": 1,
            "station_entries": [
                {"station": station, "station_rowspan": 1, "links": []},
            ],
        },
        {
            "equipment_group": _equipment_group(3, "Группа C"),
            "rowspan": 1,
            "station_entries": [
                {"station": station, "station_rowspan": 1, "links": []},
            ],
        },
    ]

    _merge_adjacent_station_entries_for_display(blocks)
    assert blocks[0]["station_entries"][0]["show_merged_station_cells"] is True
    assert blocks[1]["station_entries"][0]["show_merged_station_cells"] is False
    assert blocks[2]["station_entries"][0]["show_merged_station_cells"] is False

    page_tail = blocks[1:]
    _reapply_display_merges_for_page_blocks(page_tail)

    assert page_tail[0]["station_entries"][0]["show_merged_station_cells"] is True
    assert page_tail[0]["station_entries"][0]["merged_station_rowspan"] == 2
    assert page_tail[1]["station_entries"][0]["show_merged_station_cells"] is False


def test_merge_adjacent_group_blocks_for_display_uses_group_name_and_numb():
    blocks = [
        {
            "equipment_group": _equipment_group(
                1, "Архангельская ТЭЦ (ТЭЦ-130 ата)", numb=130
            ),
            "rowspan": 2,
        },
        {
            "equipment_group": _equipment_group(
                77, "Архангельская ТЭЦ (ТЭЦ-130 ата)", numb=130
            ),
            "rowspan": 4,
        },
        {
            "equipment_group": _equipment_group(2, "Вельская ГТ-ТЭЦ", numb=12),
            "rowspan": 1,
        },
    ]

    _merge_adjacent_group_blocks_for_display(blocks)

    assert blocks[0]["show_merged_group_cells"] is True
    assert blocks[0]["merged_group_rowspan"] == 6
    assert blocks[1]["show_merged_group_cells"] is False
    assert blocks[2]["show_merged_group_cells"] is True
    assert blocks[2]["merged_group_rowspan"] == 1


def test_merge_adjacent_group_blocks_does_not_hide_numb_behind_empty_sibling():
    blocks = [
        {
            "equipment_group": _equipment_group(28289, "ТЭЦ-14 Первомайская"),
            "rowspan": 1,
        },
        {
            "equipment_group": _equipment_group(
                28293, "ТЭЦ-14 Первомайская", numb=66
            ),
            "rowspan": 1,
        },
    ]

    _merge_adjacent_group_blocks_for_display(blocks)

    assert blocks[0]["show_merged_group_cells"] is True
    assert blocks[0]["merged_group_rowspan"] == 1
    assert blocks[1]["show_merged_group_cells"] is True
    assert blocks[1]["merged_group_rowspan"] == 1


def test_group_block_display_sort_key_puts_composite_parent_first():
    station = _station(1, "Архангельская ТЭЦ")
    parent = {
        "equipment_group": _equipment_group(
            10, "Архангельская ТЭЦ", main=0, comp=1, numb=100
        ),
        "station_entries": [
            {
                "station": station,
                "links": [{"equipment_group_type": None}],
            }
        ],
    }
    child = {
        "equipment_group": _equipment_group(
            11, "Архангельская ТЭЦ (ТЭЦ-130 ата)", main=100, comp=None, numb=101
        ),
        "station_entries": [
            {
                "station": station,
                "links": [
                    {
                        "equipment_group_type": SimpleNamespace(
                            display_order=1, name="ТЭЦ-130 ата"
                        )
                    }
                ],
            }
        ],
    }
    assert _group_block_display_sort_key(parent) < _group_block_display_sort_key(child)


def test_group_block_display_sort_keeps_composite_clusters_together():
    station = _station(1, "Станция")
    parent_a = {
        "equipment_group": _equipment_group(1, "A", main=0, comp=1, numb=10),
        "station_entries": [{"station": station, "links": [{"equipment_group_type": None}]}],
    }
    child_a = {
        "equipment_group": _equipment_group(2, "A-child", main=10, comp=None, numb=11),
        "station_entries": [
            {
                "station": station,
                "links": [
                    {
                        "equipment_group_type": SimpleNamespace(
                            display_order=1, name="тип"
                        )
                    }
                ],
            }
        ],
    }
    parent_b = {
        "equipment_group": _equipment_group(3, "B", main=0, comp=1, numb=20),
        "station_entries": [{"station": station, "links": [{"equipment_group_type": None}]}],
    }
    child_b = {
        "equipment_group": _equipment_group(4, "B-child", main=20, comp=None, numb=21),
        "station_entries": [
            {
                "station": station,
                "links": [
                    {
                        "equipment_group_type": SimpleNamespace(
                            display_order=1, name="тип"
                        )
                    }
                ],
            }
        ],
    }
    keys = [
        _group_block_display_sort_key(parent_a),
        _group_block_display_sort_key(child_a),
        _group_block_display_sort_key(parent_b),
        _group_block_display_sort_key(child_b),
    ]
    assert keys == sorted(keys)
    assert keys[0] < keys[1] < keys[2] < keys[3]


def test_prepare_marks_composite_parent_and_orders_parent_first():
    station = _station(1, "Архангельская ТЭЦ")
    child_block = {
        "equipment_group": _equipment_group(
            11, "Архангельская ТЭЦ (ТЭЦ-130 ата)", main=100, comp=None, numb=101
        ),
        "rowspan": 1,
        "station_entries": [
            {
                "station": station,
                "station_rowspan": 1,
                "links": [
                    {
                        "equipment_group_type": SimpleNamespace(
                            display_order=1, name="ТЭЦ-130 ата"
                        ),
                        "machines": [None],
                        "rowspan": 1,
                    }
                ],
            }
        ],
    }
    parent_block = {
        "equipment_group": _equipment_group(
            10, "Архангельская ТЭЦ", main=None, comp=1, numb=100
        ),
        "rowspan": 1,
        "station_entries": [
            {
                "station": station,
                "station_rowspan": 1,
                "links": [
                    {
                        "equipment_group_type": None,
                        "machines": [None],
                        "rowspan": 1,
                    }
                ],
            }
        ],
    }

    prepared = prepare_equipment_group_blocks_for_display([child_block, parent_block])

    assert prepared[0]["is_composite_parent"] is True
    assert prepared[0]["equipment_group"].id == 10
    assert prepared[0]["show_composite_cluster"] is True
    assert prepared[1]["is_composite_child"] is True
    assert prepared[1]["equipment_group"].id == 11
    assert prepared[1]["show_composite_cluster"] is True


def test_prepare_inherits_station_for_composite_child_boiler():
    """Котельная с main→родитель и station=None берёт станцию родителя в колонке «Станция»."""
    station = _station(6622, "Шатурская ГРЭС")
    parent_block = {
        "equipment_group": _equipment_group(
            10, "ГРЭС-5 Шатурская", main=None, comp=1, numb=159
        ),
        "rowspan": 1,
        "station_entries": [
            {
                "station": station,
                "station_rowspan": 1,
                "links": [
                    {
                        "equipment_group_type": None,
                        "machines": [None],
                        "rowspan": 1,
                    }
                ],
            }
        ],
    }
    child_block = {
        "equipment_group": _equipment_group(
            11, "ГРЭС-5 Шатурская(ВК)", main=159, comp=None, numb=1882
        ),
        "rowspan": 1,
        "station_entries": [
            {
                "station": None,
                "station_rowspan": 1,
                "links": [
                    {
                        "equipment_group_type": SimpleNamespace(
                            display_order=5, name="котельная"
                        ),
                        "machines": [None],
                        "rowspan": 1,
                    }
                ],
            }
        ],
    }

    prepared = prepare_equipment_group_blocks_for_display([child_block, parent_block])

    assert prepared[0]["equipment_group"].id == 10
    assert prepared[1]["equipment_group"].id == 11
    assert prepared[1]["station_entries"][0]["station"] is station
    assert prepared[1]["station_entries"][0]["station"].name == "Шатурская ГРЭС"
    # rowspan «Станция» объединяет родителя и ребёнка
    assert prepared[0]["station_entries"][0]["merged_station_rowspan"] == 2
    assert prepared[1]["station_entries"][0]["show_merged_station_cells"] is False


def test_prepare_inherits_station_from_db_when_parent_block_absent(monkeypatch):
    """Если родителя нет в текущем куске РЭС — станция подтягивается по main→numb."""
    station = _station(6599, "ТЭЦ-16 Мосэнерго")
    child_block = {
        "equipment_group": _equipment_group(
            11, "ТЭЦ-16 Мосэнерго(90 ата)", main=177, comp=None, numb=178
        ),
        "rowspan": 1,
        "station_entries": [
            {
                "station": None,
                "station_rowspan": 1,
                "links": [
                    {
                        "equipment_group_type": SimpleNamespace(
                            display_order=5, name="котельная"
                        ),
                        "machines": [None],
                        "rowspan": 1,
                    }
                ],
            }
        ],
    }

    import app.fuel.services.stations.stations_equipment_groups_services as svc

    monkeypatch.setattr(
        svc,
        "_load_composite_parent_stations_by_numb",
        lambda numbs, version_id=None: {177: station},
    )

    prepared = prepare_equipment_group_blocks_for_display([child_block])

    assert len(prepared) == 1
    assert prepared[0]["station_entries"][0]["station"] is station
    assert prepared[0]["show_composite_cluster"] is False


def test_territorial_filter_with_res_fk_requires_regional_energy_system_id():
    """Котельные с заполненным РЭС: фильтр должен учитывать regional_energy_system_id."""
    clause = _territorial_filter_or_fk_or_obl(
        EquipmentGroup,
        {
            "federal_district_filter": [92],
            "regional_energy_system_filter": [491],
        },
        version_id=1,
    )
    assert clause is not None
    sql = str(
        clause.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "regional_energy_system_id" in sql


def _territory_chain(*, est_id=1, ues_id=10, res_id=581, rd_id=701):
    est = SimpleNamespace(id=est_id)
    ues = SimpleNamespace(id=ues_id, energy_system_type=est)
    res = SimpleNamespace(id=res_id, union_energy_system=ues)
    rd = SimpleNamespace(id=rd_id, regional_energy_systems=[res])
    return rd, res


def _standalone_child_block(group):
    return {
        "equipment_group": group,
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


def test_split_standalone_composite_child_inherits_parent_res():
    """1502 без станции и РЭС должна попасть в ту же РЭС, что и родитель 81."""
    rd, res = _territory_chain()
    child = _equipment_group(30052, "ТЭЦ Ижорского з-да(тепл)", main=81, numb=1502)
    child.regional_district = None
    child.regional_energy_system = None
    child.regional_district_id = None
    child.regional_energy_system_id = None

    parent = _equipment_group(13130, "ТЭЦ ПГУ ГСР Энерго", comp=1, numb=81)
    parent.regional_district = rd
    parent.regional_energy_system = res
    parent.regional_district_id = rd.id
    parent.regional_energy_system_id = res.id
    parent.equipment_group_links_v2 = []

    result = _split_group_block_by_station_hierarchy(
        _standalone_child_block(child),
        parent_by_numb={81: parent},
    )
    assert len(result) == 1
    key, _split_block = result[0]
    assert key[2] == 581
    assert key[3] == 701


def test_split_standalone_composite_child_inherits_parent_station_res():
    """Если у родителя нет полей РЭС, берём иерархию со станции родителя."""
    rd, res = _territory_chain()
    child = _equipment_group(30052, "ТЭЦ Ижорского з-да(тепл)", main=81, numb=1502)
    child.regional_district = None
    child.regional_energy_system = None
    child.regional_district_id = None
    child.regional_energy_system_id = None

    station = SimpleNamespace(
        id=6479,
        name="ТЭЦ ПГУ ГСР Энерго",
        id_regional_district=rd.id,
        regional_district=rd,
        regional_energy_system_obj=res,
        database_version_id=None,
    )
    parent = _equipment_group(13130, "ТЭЦ ПГУ ГСР Энерго", comp=1, numb=81)
    parent.regional_district = None
    parent.regional_energy_system = None
    parent.regional_district_id = None
    parent.regional_energy_system_id = None
    parent.equipment_group_links_v2 = [
        SimpleNamespace(
            equipment_group_set_station=SimpleNamespace(station=station)
        )
    ]

    result = _split_group_block_by_station_hierarchy(
        _standalone_child_block(child),
        parent_by_numb={81: parent},
    )
    assert len(result) == 1
    key, _split_block = result[0]
    assert key[2] == 581
    assert key[3] == 701


def test_hierarchy_key_uses_obl_mapping_when_fk_empty():
    """Калининградская ГРЭС-2 без FK субъекта/РЭС идёт в ветку по obl, не в «Не указано»."""
    rd, res = _territory_chain(est_id=207, ues_id=410, res_id=2775, rd_id=3082)
    group = _equipment_group(29071, "Калининградская ГРЭС-2", main=None, comp=1, numb=88)
    group.regional_district = None
    group.regional_energy_system = None
    group.regional_district_id = None
    group.regional_energy_system_id = None
    group.territories_energy_external_mapping = SimpleNamespace(
        regional_district=rd,
        regional_energy_system=res,
        regional_district_ref_uuid="rd-uuid",
        regional_energy_system_ref_uuid="res-uuid",
    )

    key = _hierarchy_key_from_equipment_group(group)
    assert key[0] == 207
    assert key[1] == 410
    assert key[2] == 2775
    assert key[3] == 3082


def test_split_standalone_uses_obl_mapping_res():
    """Standalone-группа с obl-маппингом не должна быть отдельным блоком «Не указано»."""
    rd, res = _territory_chain(est_id=207, ues_id=410, res_id=2775, rd_id=3082)
    group = _equipment_group(29080, "Калининградская ТЭЦ-1", main=None, comp=1, numb=89)
    group.regional_district = None
    group.regional_energy_system = None
    group.regional_district_id = None
    group.regional_energy_system_id = None
    group.territories_energy_external_mapping = SimpleNamespace(
        regional_district=rd,
        regional_energy_system=res,
        regional_district_ref_uuid="rd-uuid",
        regional_energy_system_ref_uuid="res-uuid",
    )

    result = _split_group_block_by_station_hierarchy(_standalone_child_block(group))
    assert len(result) == 1
    assert result[0][0][2] == 2775
    assert result[0][0][3] == 3082


def test_hierarchy_key_fk_wins_over_obl_mapping():
    """Заполненные FK субъекта/РЭС не подменяются obl-маппингом."""
    rd, res = _territory_chain(res_id=581, rd_id=701)
    mapped_rd, mapped_res = _territory_chain(
        est_id=207, ues_id=410, res_id=2775, rd_id=3082
    )
    group = _equipment_group(1, "Группа с FK")
    group.regional_district = rd
    group.regional_energy_system = res
    group.regional_district_id = rd.id
    group.regional_energy_system_id = res.id
    group.territories_energy_external_mapping = SimpleNamespace(
        regional_district=mapped_rd,
        regional_energy_system=mapped_res,
    )

    key = _hierarchy_key_from_equipment_group(group)
    assert key[2] == 581
    assert key[3] == 701


def test_split_uses_station_res_when_group_key_unspecified():
    """Если у группы нет РЭС, а у станции есть — строка идёт в РЭС станции."""
    est = SimpleNamespace(id=207)
    ues = SimpleNamespace(id=410, energy_system_type=est)
    res = SimpleNamespace(id=2775, union_energy_system=ues)
    rd = SimpleNamespace(id=3082, regional_energy_systems=[])
    station = SimpleNamespace(
        id=6231,
        name="Калининградская ТЭЦ-2",
        id_regional_district=rd.id,
        regional_district=rd,
        regional_energy_system_obj=res,
        database_version_id=None,
    )
    group = _equipment_group(1, "Калининградская ТЭЦ-2 (ПГУ-ТЭЦ)")
    group.regional_district = rd
    group.regional_energy_system = None
    group.regional_district_id = rd.id
    group.regional_energy_system_id = None

    result = _split_group_block_by_station_hierarchy(
        {
            "equipment_group": group,
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
    )
    assert result[0][0][2] == 2775
    assert result[0][0][3] == 3082

    result = _split_group_block_by_station_hierarchy(
        {
            "equipment_group": group,
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
    )
    assert result[0][0][2] == 2775
    assert result[0][0][3] == 3082


def test_split_does_not_override_child_own_res():
    """Своя РЭС ребёнка (другой регион) не подменяется родительской."""
    parent_rd, parent_res = _territory_chain(res_id=581, rd_id=701)
    child_rd, child_res = _territory_chain(
        est_id=2, ues_id=20, res_id=100, rd_id=200
    )
    child = _equipment_group(30052, "Котельная", main=81, numb=1502)
    child.regional_district = child_rd
    child.regional_energy_system = child_res
    child.regional_district_id = child_rd.id
    child.regional_energy_system_id = child_res.id

    parent = _equipment_group(13130, "Родитель", comp=1, numb=81)
    parent.regional_district = parent_rd
    parent.regional_energy_system = parent_res
    parent.regional_district_id = parent_rd.id
    parent.regional_energy_system_id = parent_res.id
    parent.equipment_group_links_v2 = []

    result = _split_group_block_by_station_hierarchy(
        _standalone_child_block(child),
        parent_by_numb={81: parent},
    )
    assert result[0][0][2] == 100
    assert result[0][0][3] == 200


def test_parent_groups_from_blocks_indexes_composite_parent_by_numb():
    parent = _equipment_group(13130, "Родитель", comp=1, numb=81)
    child = _equipment_group(30052, "Ребёнок", main=81, numb=1502)
    found = _parent_groups_from_blocks(
        [
            {"equipment_group": child},
            {"equipment_group": parent},
        ]
    )
    assert found[81] is parent


def test_eg_station_rd_consistent_when_same_id():
    station = SimpleNamespace(id_regional_district=2283, database_version_id=37)
    group = SimpleNamespace(regional_district_id=2283, regional_district=None)
    assert _eg_station_regional_district_consistent(station, group) is True


def test_eg_station_rd_consistent_when_ids_are_version_copies(monkeypatch):
    station = SimpleNamespace(id_regional_district=2283, database_version_id=37)
    group = SimpleNamespace(regional_district_id=663, regional_district=None)

    def _coerce(rd_id, vid):
        if rd_id == 663 and vid == 37:
            return 2283
        return rd_id

    monkeypatch.setattr(
        "app.common.services.refdata_fk_resolve.coerce_regional_district_id_for_db_version",
        _coerce,
    )
    assert _eg_station_regional_district_consistent(station, group) is True


def test_eg_station_rd_inconsistent_for_different_regions(monkeypatch):
    station = SimpleNamespace(id_regional_district=2283, database_version_id=37)
    group = SimpleNamespace(regional_district_id=100, regional_district=None)
    monkeypatch.setattr(
        "app.common.services.refdata_fk_resolve.coerce_regional_district_id_for_db_version",
        lambda rd_id, vid: 999,
    )
    assert _eg_station_regional_district_consistent(station, group) is False


def test_equipment_group_missing_numb_treats_empty_and_zero_as_missing():
    from app.fuel.services.stations.stations_equipment_groups_services import (
        equipment_group_missing_numb,
        filter_equipment_group_ids_missing_numb,
    )

    assert equipment_group_missing_numb(None) is True
    assert equipment_group_missing_numb(0) is True
    assert equipment_group_missing_numb("0") is True
    assert equipment_group_missing_numb("") is True
    assert equipment_group_missing_numb("  ") is True
    assert equipment_group_missing_numb(1120) is False
    assert equipment_group_missing_numb("1120") is False

    kept = filter_equipment_group_ids_missing_numb(
        {1, 2, 3, 4},
        [(1, None), (2, 0), (3, 1120), (4, "")],
    )
    assert kept == {1, 2, 4}


def test_duplicate_numb_equipment_group_ids_ignores_missing_and_uniques():
    from app.fuel.services.stations.stations_equipment_groups_services import (
        duplicate_numb_equipment_group_ids,
        filter_equipment_group_ids_missing_or_duplicate_numb,
        equipment_group_numb_dedupe_key,
    )

    assert equipment_group_numb_dedupe_key(None) is None
    assert equipment_group_numb_dedupe_key(0) is None
    assert equipment_group_numb_dedupe_key(1120) == 1120
    assert equipment_group_numb_dedupe_key("1120") == 1120

    numb_rows = [
        (1, None),
        (2, 0),
        (3, 1120),
        (4, "1120"),
        (5, 5555),
        (6, 7777),
        (7, ""),
    ]
    assert duplicate_numb_equipment_group_ids(numb_rows) == {3, 4}
    assert duplicate_numb_equipment_group_ids(numb_rows, {3, 5, 6}) == set()
    assert duplicate_numb_equipment_group_ids(numb_rows, {3, 4, 5}) == {3, 4}

    kept = filter_equipment_group_ids_missing_or_duplicate_numb(
        {1, 2, 3, 4, 5, 6, 7},
        numb_rows,
    )
    assert kept == {1, 2, 3, 4, 7}


def test_filter_legacy_duplicate_equipment_group_ids_keeps_current_version():
    rows = [
        (28289, "4aaf789b-b89f-5d63-93cb-4b0c674b16ab", None),
        (28293, "4aaf789b-b89f-5d63-93cb-4b0c674b16ab", 37),
        (17121, "a8107f76-df19-563f-b7e6-42e99f48fbf4", None),
        (17333, "a8107f76-df19-563f-b7e6-42e99f48fbf4", 37),
        (30805, "unique-legacy-only", None),
    ]
    kept = filter_legacy_duplicate_equipment_group_ids(rows, 37)
    assert kept == {28293, 17333, 30805}
