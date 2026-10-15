# -*- coding: utf-8 -*-
"""Проверки территориальных фильтров страницы перетоков ЭЭ."""

from app.energy_balance.services.ee_transfers_page_services import _transfer_matches_filters


def _matches_union_filter(row, ues_id, *, res_ues_map, rd_res_map):
    return _transfer_matches_filters(
        row=row,
        filters={"union_energy_system_filter": [ues_id]},
        res_rd_map={},
        res_fd_map={},
        res_ues_map=res_ues_map,
        res_est_map={},
        rd_res_map=rd_res_map,
        rd_fd_map={},
    )


def test_union_energy_system_filter_matches_source_res_membership():
    row = {"from_res_id": 42}

    assert _matches_union_filter(
        row, 318, res_ues_map={42: 318}, rd_res_map={}
    )
    assert not _matches_union_filter(
        row, 318, res_ues_map={42: 411}, rd_res_map={}
    )


def test_union_energy_system_filter_does_not_include_regional_district_source():
    row = {"ues_id": 318, "from_rd_id": 3090}

    assert not _matches_union_filter(
        row,
        318,
        res_ues_map={42: 318, 43: 411},
        rd_res_map={3090: {42, 43}},
    )


def test_transfer_to_union_filter_matches_destination_oes():
    row = {"to_ues_id": 318}
    filters = {"transfer_to_ues_filter": [318]}

    assert _transfer_matches_filters(
        row,
        filters,
        res_rd_map={},
        res_fd_map={},
        res_ues_map={},
        res_est_map={},
        rd_res_map={},
        rd_fd_map={},
    )
    assert not _transfer_matches_filters(
        row,
        {"transfer_to_ues_filter": [411]},
        res_rd_map={},
        res_fd_map={},
        res_ues_map={},
        res_est_map={},
        rd_res_map={},
        rd_fd_map={},
    )


def test_transfer_to_union_filter_combines_with_destination_entity_filters():
    row = {"to_ues_id": 318, "to_res_id": 42}
    filter_args = {
        "transfer_to_ues_filter": [318],
        "transfer_to_res_filter": [43],
    }

    assert not _transfer_matches_filters(
        row,
        filter_args,
        res_rd_map={},
        res_fd_map={},
        res_ues_map={},
        res_est_map={},
        rd_res_map={},
        rd_fd_map={},
    )
