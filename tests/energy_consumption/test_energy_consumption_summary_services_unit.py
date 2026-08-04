from decimal import Decimal
from dataclasses import replace

from app.energy_consumption.services import energy_consumption_summary_services as service


def _ues_base_row() -> dict:
    return {
        "entity_label": "ОЭС Центра",
        "entity_rowspan": 1,
        "entity_depth": 0,
        "entity_kind": "group",
        "show_entity_cell": True,
        "show_entity_note_cell": True,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "parameter_label": "Потребление электрической энергии, млн кВтч",
        "demand_model_name": "UnionEnergySystemEnergyConsumptionParameter",
        "parent_fk_column": "id_union_energy_system",
        "parent_id": 117,
        "hist_row_id": None,
        "year_row_ids": [101],
        "hist_value": "—",
        "hist_numeric_tooltip": "",
        "perimeter_variant_code": None,
        "perimeter_variant_label": "",
        "perimeter_variant_options": [],
        "show_perimeter_variant_select": False,
        "year_values": ["100.0"],
        "year_numeric_tooltips": ["100.0"],
        "entity_note_row_id": 201,
        "entity_note_text": "",
    }


def _ues_gaes_row() -> dict:
    return {
        "entity_label": "ОЭС Центра (заряд ГАЭС)",
        "entity_rowspan": 1,
        "entity_depth": 0,
        "entity_kind": "group",
        "show_entity_cell": True,
        "show_entity_note_cell": True,
        "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
        "parameter_label": service.GAES_CHARGE_PARAMETER_LABEL,
        "demand_model_name": "UnionEnergySystemEnergyConsumptionParameter",
        "parent_fk_column": "id_union_energy_system",
        "parent_id": 117,
        "hist_row_id": None,
        "year_row_ids": [None],
        "hist_value": "—",
        "hist_numeric_tooltip": "",
        "perimeter_variant_code": None,
        "perimeter_variant_label": "",
        "perimeter_variant_options": [],
        "show_perimeter_variant_select": False,
        "year_values": ["20.0"],
        "year_numeric_tooltips": ["20.0"],
        "entity_note_row_id": None,
        "entity_note_text": "",
        "gaes_charge_row_station_name": "всего",
        "pd_ec_gaes_injected_row": True,
    }


def _south_variant_row(code: str, value: str) -> dict:
    return {
        "entity_label": "ОЭС Юга",
        "entity_rowspan": 1,
        "entity_depth": 0,
        "entity_kind": "perimeter_variant",
        "show_entity_cell": True,
        "show_entity_note_cell": True,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "parameter_label": "Потребление электрической энергии, млн кВтч",
        "demand_model_name": "UnionEnergySystemEnergyConsumptionParameter",
        "parent_fk_column": "id_union_energy_system",
        "parent_id": 118,
        "hist_row_id": None,
        "year_row_ids": [None],
        "hist_value": "—",
        "hist_numeric_tooltip": "",
        "perimeter_variant_code": code,
        "perimeter_variant_label": "",
        "perimeter_variant_options": [],
        "show_perimeter_variant_select": False,
        "year_values": [value],
        "year_numeric_tooltips": [value],
        "entity_note_row_id": None,
        "entity_note_text": "",
    }


def _south_gaes_charge_row(value: str) -> dict:
    return {
        "entity_label": "ОЭС Юга",
        "entity_rowspan": 1,
        "entity_depth": 0,
        "entity_kind": "group",
        "show_entity_cell": True,
        "show_entity_note_cell": True,
        "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
        "parameter_label": service.GAES_CHARGE_PARAMETER_LABEL,
        "demand_model_name": "UnionEnergySystemEnergyConsumptionParameter",
        "parent_fk_column": "id_union_energy_system",
        "parent_id": 118,
        "hist_row_id": None,
        "year_row_ids": [None],
        "hist_value": "—",
        "hist_numeric_tooltip": "",
        "perimeter_variant_code": None,
        "perimeter_variant_label": "",
        "perimeter_variant_options": [],
        "show_perimeter_variant_select": False,
        "year_values": [value],
        "year_numeric_tooltips": [value],
        "entity_note_row_id": None,
        "entity_note_text": "",
        "gaes_charge_row_station_name": "Зеленчукская ГАЭС",
    }


def _south_gaes_charge_row_for_nt_group(value: str, *, nt_group: str) -> dict:
    row = _south_gaes_charge_row(value)
    if nt_group == "with_nt":
        row["pd_ec_nt_extra_row"] = True
        row["pd_ec_nt_without_row"] = False
    else:
        row["pd_ec_nt_extra_row"] = False
        row["pd_ec_nt_without_row"] = True
    return row


def test_inject_union_energy_system_without_gaes_rows_for_base_ues(monkeypatch):
    summary_rows = [_ues_base_row(), _ues_gaes_row()]
    years = [2024]

    monkeypatch.setattr(
        service,
        "_summary_row_entity_has_gaes_charge",
        lambda row: row.get("parent_id") == 117,
    )

    service.inject_union_energy_system_without_gaes_summary_rows(
        summary_rows,
        years,
        rounding_digits=1,
    )

    assert len(summary_rows) == 3
    injected = summary_rows[2]

    assert injected["entity_label"] == "ОЭС Центра без заряда ГАЭС"
    assert injected["pd_ec_ues_without_gaes_injected_row"] is True
    assert injected["pd_ec_gaes_extra_row"] is True
    assert injected["pd_ec_gaes_without_row"] is True
    assert injected["pd_ec_formula_derived_row"] is True
    assert injected["gaes_without_charge_formula_kind"] == "oes"
    assert injected["perimeter_variant_code"] is None
    assert injected["year_row_ids"] == [None]
    assert service._raw_year_values_from_summary_row(injected, years) == {
        2024: Decimal("80.0")
    }


def test_apply_union_energy_system_gaes_entity_labels_sets_toggle_labels(monkeypatch):
    summary_rows = [_ues_base_row(), _ues_gaes_row()]
    years = [2024]

    monkeypatch.setattr(
        service,
        "_summary_row_entity_has_gaes_charge",
        lambda row: row.get("parent_id") == 117,
    )

    service.inject_union_energy_system_without_gaes_summary_rows(
        summary_rows,
        years,
        rounding_digits=1,
    )
    service.apply_union_energy_system_gaes_entity_labels(summary_rows)

    main_row, charge_row, without_gaes_row = summary_rows

    assert main_row["entity_label"] == "ОЭС Центра с зарядом ГАЭС"
    assert main_row["pd_ec_entity_label_compact"] == "ОЭС Центра"
    assert main_row["pd_ec_entity_label_compact_nt"] == "ОЭС Центра с зарядом ГАЭС"
    assert main_row["pd_ec_entity_label_compact_nt_gaes"] == "ОЭС Центра"

    assert charge_row["entity_label"] == "ОЭС Центра (заряд ГАЭС)"
    assert charge_row["pd_ec_entity_label_compact_nt_gaes"] == "ОЭС Центра"

    assert without_gaes_row["entity_label"] == "ОЭС Центра без заряда ГАЭС"
    assert without_gaes_row["pd_ec_entity_label_compact_nt_gaes"] == "ОЭС Центра"


def test_apply_union_energy_system_gaes_entity_labels_keeps_south_variant_nt_labels():
    rows = [
        _south_variant_row(service.CODE_WITH_NT_WITHOUT_GAES, "130.0"),
        _south_variant_row(service.CODE_WITHOUT_NT_WITHOUT_GAES, "88.0"),
    ]
    for row in rows:
        row["gaes_without_charge_formula_kind"] = "oes"

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)
    service.apply_union_energy_system_gaes_entity_labels(rows)

    assert rows[0]["entity_label"] == "ОЭС Юга с НТ без заряда ГАЭС"
    assert rows[1]["entity_label"] == "ОЭС Юга без НТ без заряда ГАЭС"
    assert rows[0]["pd_ec_entity_label_compact"] == "ОЭС Юга с НТ"
    assert rows[1]["pd_ec_entity_label_compact"] == "ОЭС Юга без НТ"


def test_nt_on_gaes_off_variant_row_rules_and_export_labels():
    ees_type_with_nt_without_gaes = {
        "entity_label": "ЭЭС России",
        "demand_model_name": "EnergySystemTypeEnergyConsumptionParameter",
        "parent_fk_column": "id_energy_system_type",
        "parent_id": 1,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "perimeter_variant_code": service.CODE_WITH_NT_WITHOUT_GAES,
    }
    ees_type_with_nt_plain = {
        **ees_type_with_nt_without_gaes,
        "perimeter_variant_code": service.CODE_WITH_NT,
    }
    ees_russia_without_nt_without_gaes = _ees_russia_variant_row(
        code=service.CODE_WITHOUT_NT_WITHOUT_GAES,
    )
    ees_russia_without_nt_with_gaes = _ees_russia_variant_row(
        code=service.CODE_WITHOUT_NT_WITH_GAES,
    )
    sync_without_nt_without_gaes = {
        "entity_label": "Первая синхронная зона",
        "demand_model_name": "SynchronousAreaEnergyConsumptionParameter",
        "parent_fk_column": "id_synchronous_area",
        "parent_id": 39,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "perimeter_variant_code": "without_nt_without_gaes_with_kaliningrad_es",
    }
    south_with_nt_with_gaes = _south_variant_row(service.CODE_WITH_NT_WITH_GAES, "130.0")
    south_with_nt_without_gaes = _south_variant_row(service.CODE_WITH_NT_WITHOUT_GAES, "120.0")
    ees_type_with_nt_with_gaes = {
        **ees_type_with_nt_without_gaes,
        "perimeter_variant_code": service.CODE_WITH_NT_WITH_GAES,
    }
    rows = [
        ees_type_with_nt_with_gaes,
        ees_type_with_nt_plain,
        ees_type_with_nt_without_gaes,
        ees_russia_without_nt_with_gaes,
        ees_russia_without_nt_without_gaes,
        sync_without_nt_without_gaes,
        south_with_nt_with_gaes,
        south_with_nt_without_gaes,
    ]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)
    service._mark_summary_table_nt_on_gaes_off_variant_row_rules(rows)

    assert ees_type_with_nt_with_gaes["pd_ec_nt_on_gaes_off_visible_row"] is True
    assert ees_type_with_nt_plain["pd_ec_nt_on_gaes_off_redundant_row"] is True
    assert ees_type_with_nt_without_gaes["pd_ec_nt_on_gaes_off_redundant_row"] is True
    assert ees_russia_without_nt_with_gaes["pd_ec_nt_on_gaes_off_visible_row"] is True
    assert ees_russia_without_nt_without_gaes["pd_ec_nt_on_gaes_off_redundant_row"] is True
    # Нет варианта «с зарядом» — оставляем «без заряда» как fallback.
    assert sync_without_nt_without_gaes["pd_ec_nt_on_gaes_off_visible_row"] is True
    assert south_with_nt_with_gaes["pd_ec_nt_on_gaes_off_visible_row"] is True
    assert south_with_nt_without_gaes["pd_ec_nt_on_gaes_off_redundant_row"] is True

    ui_opts = service.EnergyConsumptionExportUiOptions(
        nt_detail_on=True,
        gaes_detail_on=False,
        verification_on=False,
        territory_compact_on=True,
    )
    assert (
        service.export_entity_label_for_summary_row(ees_type_with_nt_with_gaes, ui_opts)
        == "ЭЭС России с НТ"
    )
    assert (
        service.export_entity_label_for_summary_row(ees_russia_without_nt_with_gaes, ui_opts)
        == "ЕЭС России без НТ"
    )
    assert (
        service.export_entity_label_for_summary_row(sync_without_nt_without_gaes, ui_opts)
        == "Первая синхронная зона без НТ"
    )
    assert (
        service.export_entity_label_for_summary_row(south_with_nt_with_gaes, ui_opts)
        == "ОЭС Юга с НТ"
    )

    def parameter_visible(_pk: str) -> bool:
        return True

    assert service._summary_row_visible_for_export_ui(
        ees_russia_without_nt_with_gaes, opts=ui_opts, parameter_visible=parameter_visible
    )
    assert not service._summary_row_visible_for_export_ui(
        ees_russia_without_nt_without_gaes, opts=ui_opts, parameter_visible=parameter_visible
    )
    assert service._summary_row_visible_for_export_ui(
        ees_type_with_nt_with_gaes, opts=ui_opts, parameter_visible=parameter_visible
    )
    assert not service._summary_row_visible_for_export_ui(
        ees_type_with_nt_without_gaes, opts=ui_opts, parameter_visible=parameter_visible
    )
    assert service._summary_row_visible_for_export_ui(
        south_with_nt_with_gaes, opts=ui_opts, parameter_visible=parameter_visible
    )
    assert not service._summary_row_visible_for_export_ui(
        south_with_nt_without_gaes, opts=ui_opts, parameter_visible=parameter_visible
    )


def test_collapsed_nt_gaes_visible_rows_skip_empty_hide_marks_south_ues_without_nt():
    south_without_nt = _south_variant_row(service.CODE_WITHOUT_NT, "70.0")
    rows = [south_without_nt]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)

    assert south_without_nt.get("pd_ec_collapsed_nt_gaes_visible_row") is True
    assert south_without_nt.get("pd_ec_skip_empty_hide_row") is True


def test_collapsed_nt_gaes_variant_row_rules_mark_primary_rows():
    ees_russia_with = {
        "entity_label": "ЕЭС России",
        "demand_model_name": "EesRussiaEnergyConsumptionParameter",
        "parent_fk_column": None,
        "parent_id": None,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "perimeter_variant_code": service.CODE_WITHOUT_NT_WITH_GAES,
    }
    ees_russia_without = {
        **ees_russia_with,
        "perimeter_variant_code": service.CODE_WITHOUT_NT_WITHOUT_GAES,
    }
    south_rows = [
        _south_variant_row(service.CODE_WITHOUT_NT_WITH_GAES, "100.0"),
        _south_variant_row(service.CODE_WITHOUT_NT_WITHOUT_GAES, "88.0"),
        _south_variant_row(service.CODE_WITHOUT_NT, "70.0"),
    ]
    sync_row = {
        "entity_label": "Первая синхронная зона",
        "demand_model_name": "SynchronousAreaEnergyConsumptionParameter",
        "parent_fk_column": "id_synchronous_area",
        "parent_id": 39,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "perimeter_variant_code": "without_nt_without_gaes_with_kaliningrad_es",
    }
    rows = [ees_russia_with, ees_russia_without, *south_rows, sync_row]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)

    assert ees_russia_with["pd_ec_collapsed_nt_gaes_visible_row"] is True
    assert ees_russia_with["pd_ec_entity_label_compact_nt_gaes"] == "ЕЭС России"
    assert ees_russia_without["pd_ec_collapsed_nt_gaes_redundant_row"] is True
    assert south_rows[0]["pd_ec_collapsed_nt_gaes_visible_row"] is True
    assert south_rows[0]["pd_ec_entity_label_compact_nt_gaes"] == "ОЭС Юга"
    assert south_rows[1]["pd_ec_collapsed_nt_gaes_redundant_row"] is True
    assert south_rows[2]["pd_ec_collapsed_nt_gaes_redundant_row"] is True
    # Только «без заряда» — fallback primary.
    assert sync_row["pd_ec_collapsed_nt_gaes_visible_row"] is True
    assert sync_row["pd_ec_entity_label_compact_nt_gaes"] == "Первая синхронная зона"


def test_collapsed_nt_gaes_hides_fo_without_gaes_when_base_row_exists():
    """ФО: базовая строка без кода + инжект «без заряда» не должны оба быть primary."""
    fd_mn = "FederalDistrictEnergyConsumptionParameter"
    fo_base = {
        "entity_label": "Центральный ФО",
        "demand_model_name": fd_mn,
        "parent_fk_column": "id_federal_district",
        "parent_id": 1,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "perimeter_variant_code": None,
        "show_entity_cell": True,
        "entity_kind": "group",
    }
    fo_without = {
        **fo_base,
        "entity_label": "Центральный ФО без заряда ГАЭС",
        "perimeter_variant_code": service.CODE_WITHOUT_NT_WITHOUT_GAES,
        "pd_ec_gaes_extra_row": True,
        "pd_ec_gaes_without_row": True,
        "pd_ec_fo_without_gaes_injected_row": True,
        "gaes_without_charge_formula_kind": "fo",
    }
    rows = [fo_base, fo_without]

    service._mark_summary_table_collapsed_nt_gaes_variant_row_rules(rows)
    service._mark_summary_table_nt_on_gaes_off_variant_row_rules(rows)

    assert fo_without.get("pd_ec_collapsed_nt_gaes_visible_row") is not True
    assert fo_without.get("pd_ec_collapsed_nt_gaes_redundant_row") is True
    assert fo_without.get("pd_ec_nt_on_gaes_off_visible_row") is not True
    assert fo_without.get("pd_ec_nt_on_gaes_off_redundant_row") is True
    assert service._summary_row_visible_for_export_ui(
        fo_without,
        opts=service.EnergyConsumptionExportUiOptions(
            sipr_on=False,
            verification_on=False,
            gaes_detail_on=False,
            nt_detail_on=False,
            isolated_energy_units_on=False,
            territory_compact_on=True,
        ),
        parameter_visible=lambda _pk: True,
    ) is False
    assert service._summary_row_visible_for_export_ui(
        fo_without,
        opts=service.EnergyConsumptionExportUiOptions(
            sipr_on=False,
            verification_on=False,
            gaes_detail_on=True,
            nt_detail_on=False,
            isolated_energy_units_on=False,
            territory_compact_on=True,
        ),
        parameter_visible=lambda _pk: True,
    ) is True


def test_collapse_gaes_split_removes_south_fd_duplicates_without_stations(monkeypatch):
    """Южный ФО без станций ГАЭС: не оставлять одинаковые строки с/без заряда."""
    fd_mn = "FederalDistrictEnergyConsumptionParameter"
    rows = [
        {
            "entity_label": "Южный ФО без НТ с зарядом ГАЭС",
            "demand_model_name": fd_mn,
            "parent_fk_column": "id_federal_district",
            "parent_id": 20,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "perimeter_variant_code": service.CODE_WITHOUT_NT_WITH_GAES,
            "pd_ec_gaes_extra_row": True,
            "year_values": ["100.0"],
            "show_entity_cell": True,
        },
        {
            "entity_label": "Южный ФО (заряд ГАЭС)",
            "demand_model_name": fd_mn,
            "parent_fk_column": "id_federal_district",
            "parent_id": 20,
            "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
            "perimeter_variant_code": None,
            "pd_ec_gaes_injected_row": True,
            "year_values": ["—"],
            "show_entity_cell": True,
        },
        {
            "entity_label": "Южный ФО без НТ без заряда ГАЭС",
            "demand_model_name": fd_mn,
            "parent_fk_column": "id_federal_district",
            "parent_id": 20,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "perimeter_variant_code": service.CODE_WITHOUT_NT_WITHOUT_GAES,
            "pd_ec_gaes_without_row": True,
            "year_values": ["100.0"],
            "show_entity_cell": True,
        },
        {
            "entity_label": "Центральный ФО с зарядом ГАЭС",
            "demand_model_name": fd_mn,
            "parent_fk_column": "id_federal_district",
            "parent_id": 1,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "perimeter_variant_code": service.CODE_WITHOUT_NT_WITH_GAES,
            "pd_ec_gaes_extra_row": True,
            "year_values": ["200.0"],
            "show_entity_cell": True,
        },
        {
            "entity_label": "Центральный ФО без заряда ГАЭС",
            "demand_model_name": fd_mn,
            "parent_fk_column": "id_federal_district",
            "parent_id": 1,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "perimeter_variant_code": service.CODE_WITHOUT_NT_WITHOUT_GAES,
            "pd_ec_gaes_without_row": True,
            "year_values": ["190.0"],
            "show_entity_cell": True,
        },
    ]

    def _has_gaes(row):
        return int(row.get("parent_id") or 0) == 1

    monkeypatch.setattr(service, "_summary_row_entity_has_gaes_charge", _has_gaes)

    service.collapse_gaes_variant_split_for_entities_without_stations(rows)

    south = [r for r in rows if r.get("parent_id") == 20]
    central = [r for r in rows if r.get("parent_id") == 1]
    assert len(south) == 1
    assert south[0]["perimeter_variant_code"] == service.CODE_WITHOUT_NT_WITH_GAES
    assert south[0].get("pd_ec_gaes_extra_row") is False
    assert "с зарядом" not in (south[0].get("entity_label") or "")
    assert len(central) == 2
    assert any("without_gaes" in str(r.get("perimeter_variant_code") or "") for r in central)


def test_collapse_gaes_keeps_ees_russia_with_and_without_gaes_variants(monkeypatch):
    """ЭЭС России: полный набор с/без НТ × с/без ГАЭС, даже без parent_id/станций."""
    rows = [
        _ees_russia_variant_row(code=service.CODE_WITH_NT_WITH_GAES, value="100.0"),
        _ees_russia_variant_row(code=service.CODE_WITH_NT_WITHOUT_GAES, value="90.0"),
        _ees_russia_variant_row(code=service.CODE_WITHOUT_NT_WITH_GAES, value="80.0"),
        _ees_russia_variant_row(code=service.CODE_WITHOUT_NT_WITHOUT_GAES, value="70.0"),
    ]
    for row in rows:
        row["entity_label"] = "ЭЭС России"
        row["entity_kind"] = "ees_russia"

    monkeypatch.setattr(service, "_summary_row_entity_has_gaes_charge", lambda _row: False)

    service.collapse_gaes_variant_split_for_entities_without_stations(rows)
    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)

    codes = [r["perimeter_variant_code"] for r in rows]
    assert codes == [
        service.CODE_WITH_NT_WITH_GAES,
        service.CODE_WITH_NT_WITHOUT_GAES,
        service.CODE_WITHOUT_NT_WITH_GAES,
        service.CODE_WITHOUT_NT_WITHOUT_GAES,
    ]
    assert rows[0]["entity_label"] == "ЭЭС России с НТ с зарядом ГАЭС"
    assert rows[1]["entity_label"] == "ЭЭС России с НТ без заряда ГАЭС"
    assert rows[2]["entity_label"] == "ЭЭС России без НТ с зарядом ГАЭС"
    assert rows[3]["entity_label"] == "ЭЭС России без НТ без заряда ГАЭС"
    assert all(r.get("pd_ec_gaes_extra_row") or r.get("pd_ec_gaes_without_row") for r in rows)


def test_collapse_gaes_keeps_kaliningrad_sync_area_without_gaes_variant(monkeypatch):
    """СЗ Калининграда с кодом without_gaes не удаляется (нет станций ГАЭС)."""
    rows = [_kaliningrad_sync_area_variant_row(value="10.0")]
    rows[0]["perimeter_variant_code"] = "without_nt_without_gaes_kaliningrad"
    monkeypatch.setattr(service, "_summary_row_entity_has_gaes_charge", lambda _row: False)

    service.collapse_gaes_variant_split_for_entities_without_stations(rows)

    assert len(rows) == 1
    assert rows[0]["perimeter_variant_code"] == "without_nt_without_gaes_kaliningrad"
    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)
    assert rows[0].get("pd_ec_collapsed_nt_gaes_redundant_row") is not True
    assert rows[0].get("pd_ec_nt_without_row") is False
    assert rows[0].get("pd_ec_gaes_without_row") is False


def test_expanded_nt_gaes_variant_row_rules_mark_plain_with_nt_redundant():
    plain_with_nt = {
        "entity_label": "ЕЭС России",
        "demand_model_name": "EesRussiaEnergyConsumptionParameter",
        "parent_fk_column": None,
        "parent_id": None,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "perimeter_variant_code": service.CODE_WITH_NT,
    }
    with_nt_with_gaes = {
        **plain_with_nt,
        "perimeter_variant_code": service.CODE_WITH_NT_WITH_GAES,
        "entity_label": "ЕЭС России с НТ с зарядом ГАЭС",
    }
    with_nt_without_gaes = {
        **plain_with_nt,
        "perimeter_variant_code": service.CODE_WITH_NT_WITHOUT_GAES,
        "entity_label": "ЕЭС России с НТ без заряда ГАЭС",
    }
    rows = [with_nt_with_gaes, plain_with_nt, with_nt_without_gaes]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)

    assert plain_with_nt.get("pd_ec_expanded_nt_gaes_redundant_row") is True
    assert with_nt_with_gaes.get("pd_ec_expanded_nt_gaes_redundant_row") is None
    assert with_nt_without_gaes.get("pd_ec_expanded_nt_gaes_redundant_row") is None


def test_expanded_nt_gaes_variant_row_rules_mark_plain_without_nt_redundant():
    plain_without_nt = {
        "entity_label": "ЕЭС России",
        "demand_model_name": "EesRussiaEnergyConsumptionParameter",
        "parent_fk_column": None,
        "parent_id": None,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "perimeter_variant_code": service.CODE_WITHOUT_NT,
    }
    without_nt_with_gaes = {
        **plain_without_nt,
        "perimeter_variant_code": service.CODE_WITHOUT_NT_WITH_GAES,
        "entity_label": "ЕЭС России без НТ с зарядом ГАЭС",
    }
    without_nt_without_gaes = {
        **plain_without_nt,
        "perimeter_variant_code": service.CODE_WITHOUT_NT_WITHOUT_GAES,
        "entity_label": "ЕЭС России без НТ без заряда ГАЭС",
    }
    rows = [without_nt_with_gaes, plain_without_nt, without_nt_without_gaes]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)

    assert plain_without_nt.get("pd_ec_expanded_nt_gaes_redundant_row") is True
    assert without_nt_with_gaes.get("pd_ec_expanded_nt_gaes_redundant_row") is None
    assert without_nt_without_gaes.get("pd_ec_expanded_nt_gaes_redundant_row") is None


def test_order_variants_with_gaes_charge_rows_inserts_charge_between_gaes_variants():
    def _variant(code: str) -> service.SummaryEntity:
        return service.SummaryEntity(
            label=service.EES_RUSSIA_AGGREGATE_NAME,
            depth=0,
            parameters=service.PARAMETERS_ENERGY_CONSUMPTION,
            demand_rows=[],
            perimeter_variant_code=code,
        )

    variants = [
        _variant(service.CODE_WITH_NT_WITH_GAES),
        _variant(service.CODE_WITH_NT),
        _variant(service.CODE_WITH_NT_WITHOUT_GAES),
        _variant(service.CODE_WITHOUT_NT_WITH_GAES),
        _variant(service.CODE_WITHOUT_NT),
        _variant(service.CODE_WITHOUT_NT_WITHOUT_GAES),
    ]
    charge_marker = service._gaes_charge_marker_entity(variants[0])

    ordered = service._order_variants_with_gaes_charge_rows(variants, charge_marker)
    codes = [str(entity.perimeter_variant_code or "") for entity in ordered]

    assert codes == [
        service.CODE_WITH_NT_WITH_GAES,
        "",
        service.CODE_WITH_NT_WITHOUT_GAES,
        service.CODE_WITH_NT,
        service.CODE_WITHOUT_NT_WITH_GAES,
        "",
        service.CODE_WITHOUT_NT_WITHOUT_GAES,
        service.CODE_WITHOUT_NT,
    ]


def _res_base_row() -> dict:
    row = _ues_base_row()
    row.update(
        {
            "entity_label": "Московская область",
            "entity_depth": 2,
            "demand_model_name": "RegionalEnergySystemEnergyConsumptionParameter",
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 501,
        }
    )
    return row


def _res_gaes_row() -> dict:
    row = _ues_gaes_row()
    row.update(
        {
            "entity_label": "Московская область (заряд ГАЭС)",
            "entity_depth": 2,
            "demand_model_name": "RegionalEnergySystemEnergyConsumptionParameter",
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 501,
        }
    )
    return row


def _rd_base_row() -> dict:
    row = _res_base_row()
    row.update(
        {
            "entity_label": "Московская область",
            "entity_depth": 3,
            "demand_model_name": "RegionalDistrictEnergyConsumptionParameter",
            "parent_fk_column": "id_regional_district",
            "parent_id": 601,
        }
    )
    return row


def _rd_gaes_row() -> dict:
    row = _res_gaes_row()
    row.update(
        {
            "entity_depth": 3,
            "demand_model_name": "RegionalDistrictEnergyConsumptionParameter",
            "parent_fk_column": "id_regional_district",
            "parent_id": 601,
        }
    )
    return row


def test_inject_oes_territory_detail_without_gaes_rows_for_res_and_rd(monkeypatch):
    summary_rows = [_res_base_row(), _res_gaes_row(), _rd_base_row(), _rd_gaes_row()]
    years = [2024]

    def _has_gaes(row):
        if row.get("demand_model_name") == "RegionalEnergySystemEnergyConsumptionParameter":
            return row.get("parent_id") == 501
        if row.get("demand_model_name") == "RegionalDistrictEnergyConsumptionParameter":
            return row.get("parent_id") == 601
        return False

    monkeypatch.setattr(service, "_summary_row_entity_has_gaes_charge", _has_gaes)

    service.inject_oes_territory_detail_without_gaes_summary_rows(
        summary_rows,
        years,
        rounding_digits=1,
    )

    assert len(summary_rows) == 6
    res_without = summary_rows[2]
    rd_without = summary_rows[5]

    assert res_without["entity_label"] == "Московская область без заряда ГАЭС"
    assert res_without["pd_ec_res_without_gaes_injected_row"] is True
    assert res_without["gaes_without_charge_formula_kind"] == "oes"
    assert service._raw_year_values_from_summary_row(res_without, years) == {
        2024: Decimal("80.0")
    }

    assert rd_without["entity_label"] == "Московская область без заряда ГАЭС"
    assert rd_without["pd_ec_rd_without_gaes_injected_row"] is True
    assert rd_without["gaes_without_charge_formula_kind"] == "oes"
    assert service._raw_year_values_from_summary_row(rd_without, years) == {
        2024: Decimal("80.0")
    }


def test_apply_oes_territory_detail_gaes_entity_labels_sets_toggle_labels(monkeypatch):
    summary_rows = [_res_base_row(), _res_gaes_row()]
    years = [2024]

    monkeypatch.setattr(
        service,
        "_summary_row_entity_has_gaes_charge",
        lambda row: row.get("parent_id") == 501,
    )

    service.inject_oes_territory_detail_without_gaes_summary_rows(
        summary_rows,
        years,
        rounding_digits=1,
    )
    service.apply_oes_territory_detail_gaes_entity_labels(summary_rows)

    main_row, charge_row, without_gaes_row = summary_rows

    assert main_row["entity_label"] == "Московская область с зарядом ГАЭС"
    assert main_row["perimeter_variant_label"] == "с зарядом ГАЭС"
    assert main_row["pd_ec_entity_label_compact"] == "Московская область"
    assert main_row["pd_ec_entity_label_compact_nt"] == "Московская область с зарядом ГАЭС"
    assert main_row["pd_ec_entity_label_compact_nt_gaes"] == "Московская область"

    assert charge_row["entity_label"] == "Московская область (заряд ГАЭС)"
    assert charge_row["pd_ec_entity_label_compact_nt_gaes"] == "Московская область"

    assert without_gaes_row["entity_label"] == "Московская область без заряда ГАЭС"
    assert without_gaes_row["perimeter_variant_label"] == "без заряда ГАЭС"
    assert without_gaes_row["pd_ec_entity_label_compact_nt_gaes"] == "Московская область"


def _ees_russia_variant_row(*, code: str, value: str = "100.0") -> dict:
    return {
        "entity_label": "ЕЭС России",
        "entity_rowspan": 1,
        "entity_depth": 0,
        "entity_kind": "perimeter_variant",
        "show_entity_cell": True,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "demand_model_name": "EesRussiaEnergyConsumptionParameter",
        "parent_fk_column": None,
        "parent_id": None,
        "perimeter_variant_code": code,
        "year_values": [value],
        "year_numeric_tooltips": [value],
        "year_row_ids": [None],
    }


def _ees_russia_gaes_charge_row(value: str = "12.0") -> dict:
    return {
        "entity_label": "ЕЭС России (заряд ГАЭС)",
        "entity_rowspan": 1,
        "entity_depth": 0,
        "entity_kind": "energy_system_type",
        "show_entity_cell": True,
        "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
        "demand_model_name": "EnergySystemTypeEnergyConsumptionParameter",
        "parent_fk_column": "id_energy_system_type",
        "parent_id": 1,
        "perimeter_variant_code": None,
        "year_values": [value],
        "year_numeric_tooltips": [value],
        "year_row_ids": [None],
        "pd_ec_gaes_injected_row": True,
    }


def test_apply_variant_toggle_tags_ees_russia_gaes_charge_rows_by_nt_group():
    rows = [
        _ees_russia_variant_row(code=service.CODE_WITH_NT_WITH_GAES),
        _ees_russia_gaes_charge_row("20.0"),
        _ees_russia_variant_row(code=service.CODE_WITH_NT_WITHOUT_GAES),
        _ees_russia_variant_row(code=service.CODE_WITHOUT_NT_WITH_GAES),
        _ees_russia_gaes_charge_row("12.0"),
        _ees_russia_variant_row(code=service.CODE_WITHOUT_NT_WITHOUT_GAES),
    ]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)

    with_nt_charge = rows[1]
    without_nt_charge = rows[4]

    assert with_nt_charge["pd_ec_gaes_extra_row"] is True
    assert with_nt_charge["pd_ec_nt_extra_row"] is True
    assert with_nt_charge["pd_ec_nt_without_row"] is False

    assert without_nt_charge["pd_ec_gaes_extra_row"] is True
    assert without_nt_charge["pd_ec_nt_extra_row"] is False
    assert without_nt_charge["pd_ec_nt_without_row"] is True


def test_expand_ees_unified_energy_system_type_uses_ees_russia_binding(monkeypatch):
    from app.common.perimeter_variant.constants import (
        CODE_WITHOUT_NT_WITHOUT_GAES,
        CODE_WITHOUT_NT_WITH_GAES,
        CODE_WITH_NT_WITHOUT_GAES,
        CODE_WITH_NT_WITH_GAES,
        EES_RUSSIA_AGGREGATE_NAME,
        EES_UNIFIED_REF_NAME,
        ENTITY_KIND_EES_RUSSIA,
        ENTITY_KIND_ENERGY_SYSTEM_TYPE,
    )
    from app.common.perimeter_variant.registry_types import (
        EntityPerimeterBinding,
        PerimeterVariantDefinition,
    )

    gaes_variants = (
        PerimeterVariantDefinition(CODE_WITH_NT_WITH_GAES, "с НТ с зарядом ГАЭС"),
        PerimeterVariantDefinition(CODE_WITH_NT_WITHOUT_GAES, "с НТ без заряда ГАЭС"),
        PerimeterVariantDefinition(CODE_WITHOUT_NT_WITH_GAES, "без НТ с зарядом ГАЭС"),
        PerimeterVariantDefinition(CODE_WITHOUT_NT_WITHOUT_GAES, "без НТ без заряда ГАЭС"),
    )
    ees_binding = EntityPerimeterBinding(
        entity_kind=ENTITY_KIND_EES_RUSSIA,
        entity_name_cf=EES_RUSSIA_AGGREGATE_NAME.casefold(),
        entity_name=EES_RUSSIA_AGGREGATE_NAME,
        label_prefix=EES_RUSSIA_AGGREGATE_NAME,
        variants=gaes_variants,
    )

    def _fake_resolve(kind, name):
        if kind == ENTITY_KIND_ENERGY_SYSTEM_TYPE and name == EES_UNIFIED_REF_NAME:
            return None
        if kind == ENTITY_KIND_EES_RUSSIA and name == EES_RUSSIA_AGGREGATE_NAME:
            return ees_binding
        return None

    monkeypatch.setattr(service, "resolve_entity_perimeter_binding", _fake_resolve)
    monkeypatch.setattr(service.dps, "get_demand_rows", lambda *args, **kwargs: [])

    entity = service.SummaryEntity(
        label=EES_UNIFIED_REF_NAME,
        depth=0,
        parameters=service.PARAMETERS_ENERGY_CONSUMPTION,
        demand_rows=[],
        entity_kind="group-root",
        children=[],
        demand_model_name="EnergySystemTypeEnergyConsumptionParameter",
        parent_fk_column="id_energy_system_type",
        parent_id=7,
    )

    expanded = service._expand_summary_entity_perimeter_variants(
        entity,
        binding_entity_kind=ENTITY_KIND_ENERGY_SYSTEM_TYPE,
        binding_entity_name=EES_UNIFIED_REF_NAME,
        expand=True,
        tree_years=[2024],
    )

    variant_codes = {
        str(e.perimeter_variant_code)
        for e in expanded
        if e.perimeter_variant_code
    }
    assert variant_codes == {
        CODE_WITH_NT_WITH_GAES,
        CODE_WITH_NT_WITHOUT_GAES,
        CODE_WITHOUT_NT_WITH_GAES,
        CODE_WITHOUT_NT_WITHOUT_GAES,
    }
    gaes_variant_rows = [
        e
        for e in expanded
        if e.perimeter_variant_code
        and "gaes" in str(e.perimeter_variant_code)
    ]
    assert gaes_variant_rows
    assert all(e.label == EES_UNIFIED_REF_NAME for e in gaes_variant_rows)
    assert all(
        e.demand_model_name == "EnergySystemTypeEnergyConsumptionParameter"
        for e in gaes_variant_rows
    )


def test_expand_south_ues_uses_gaes_variants_when_expand_true(monkeypatch):
    from app.common.perimeter_variant.constants import (
        CODE_WITHOUT_NT_WITHOUT_GAES,
        CODE_WITHOUT_NT_WITH_GAES,
        CODE_WITH_NT_WITHOUT_GAES,
        CODE_WITH_NT_WITH_GAES,
    )
    from app.common.perimeter_variant.registry_types import (
        EntityPerimeterBinding,
        PerimeterVariantDefinition,
    )

    south_binding = EntityPerimeterBinding(
        entity_kind="union_energy_system",
        entity_name_cf="оэс юга",
        entity_name="ОЭС Юга",
        label_prefix="ОЭС Юга",
        variants=(
            PerimeterVariantDefinition(service.CODE_WITH_NT, "с НТ", effective_from_year=2024),
            PerimeterVariantDefinition(service.CODE_WITHOUT_NT, "без НТ"),
        ),
    )

    def _fake_resolve(kind, name):
        if kind == "union_energy_system" and name == "ОЭС Юга":
            return south_binding
        return None

    monkeypatch.setattr(service, "resolve_entity_perimeter_binding", _fake_resolve)
    monkeypatch.setattr(service.dps, "get_demand_rows", lambda *args, **kwargs: [])

    entity = service.SummaryEntity(
        label="ОЭС Юга",
        depth=1,
        parameters=service.PARAMETERS_ENERGY_CONSUMPTION,
        demand_rows=[],
        entity_kind="group",
        children=[],
        demand_model_name="UnionEnergySystemEnergyConsumptionParameter",
        parent_fk_column="id_union_energy_system",
        parent_id=118,
    )

    expanded = service._expand_summary_entity_perimeter_variants(
        entity,
        binding_entity_kind="union_energy_system",
        binding_entity_name="ОЭС Юга",
        expand=True,
        tree_years=[2024],
    )

    variant_codes = [
        str(e.perimeter_variant_code or "")
        for e in expanded
        if e.perimeter_variant_code
    ]
    charge_count = sum(1 for e in expanded if not e.perimeter_variant_code)

    assert variant_codes == [
        CODE_WITH_NT_WITH_GAES,
        CODE_WITH_NT_WITHOUT_GAES,
        CODE_WITHOUT_NT_WITH_GAES,
        CODE_WITHOUT_NT_WITHOUT_GAES,
    ]
    assert charge_count == 2


def test_expand_ees_unified_prefers_ees_russia_gaes_when_flag_set(monkeypatch):
    from app.common.perimeter_variant.constants import (
        CODE_WITHOUT_NT,
        CODE_WITHOUT_NT_WITHOUT_GAES,
        CODE_WITHOUT_NT_WITH_GAES,
        CODE_WITH_NT,
        CODE_WITH_NT_WITHOUT_GAES,
        CODE_WITH_NT_WITH_GAES,
        EES_RUSSIA_AGGREGATE_NAME,
        EES_UNIFIED_REF_NAME,
        ENTITY_KIND_EES_RUSSIA,
        ENTITY_KIND_ENERGY_SYSTEM_TYPE,
    )
    from app.common.perimeter_variant.registry_types import (
        EntityPerimeterBinding,
        PerimeterVariantDefinition,
    )

    est_binding = EntityPerimeterBinding(
        entity_kind=ENTITY_KIND_ENERGY_SYSTEM_TYPE,
        entity_name_cf=EES_UNIFIED_REF_NAME.casefold(),
        entity_name=EES_UNIFIED_REF_NAME,
        label_prefix=EES_UNIFIED_REF_NAME,
        variants=(
            PerimeterVariantDefinition(CODE_WITH_NT, "с НТ", effective_from_year=2024),
            PerimeterVariantDefinition(CODE_WITHOUT_NT, "без НТ"),
        ),
    )
    gaes_variants = (
        PerimeterVariantDefinition(CODE_WITH_NT_WITH_GAES, "с НТ с зарядом ГАЭС"),
        PerimeterVariantDefinition(CODE_WITH_NT_WITHOUT_GAES, "с НТ без заряда ГАЭС"),
        PerimeterVariantDefinition(CODE_WITHOUT_NT_WITH_GAES, "без НТ с зарядом ГАЭС"),
        PerimeterVariantDefinition(CODE_WITHOUT_NT_WITHOUT_GAES, "без НТ без заряда ГАЭС"),
    )
    ees_binding = EntityPerimeterBinding(
        entity_kind=ENTITY_KIND_EES_RUSSIA,
        entity_name_cf=EES_RUSSIA_AGGREGATE_NAME.casefold(),
        entity_name=EES_RUSSIA_AGGREGATE_NAME,
        label_prefix=EES_RUSSIA_AGGREGATE_NAME,
        variants=gaes_variants,
    )

    def _fake_resolve(kind, name):
        if kind == ENTITY_KIND_ENERGY_SYSTEM_TYPE and name == EES_UNIFIED_REF_NAME:
            return est_binding
        if kind == ENTITY_KIND_EES_RUSSIA and name == EES_RUSSIA_AGGREGATE_NAME:
            return ees_binding
        return None

    monkeypatch.setattr(service, "resolve_entity_perimeter_binding", _fake_resolve)
    monkeypatch.setattr(service.dps, "get_demand_rows", lambda *args, **kwargs: [])

    entity = service.SummaryEntity(
        label=EES_UNIFIED_REF_NAME,
        depth=0,
        parameters=service.PARAMETERS_ENERGY_CONSUMPTION,
        demand_rows=[],
        entity_kind="group-root",
        children=[],
        demand_model_name="EnergySystemTypeEnergyConsumptionParameter",
        parent_fk_column="id_energy_system_type",
        parent_id=7,
    )

    without_flag = service._expand_summary_entity_perimeter_variants(
        entity,
        binding_entity_kind=ENTITY_KIND_ENERGY_SYSTEM_TYPE,
        binding_entity_name=EES_UNIFIED_REF_NAME,
        expand=True,
        tree_years=[2024],
        use_ees_russia_gaes_variants=False,
    )
    with_flag = service._expand_summary_entity_perimeter_variants(
        entity,
        binding_entity_kind=ENTITY_KIND_ENERGY_SYSTEM_TYPE,
        binding_entity_name=EES_UNIFIED_REF_NAME,
        expand=True,
        tree_years=[2024],
        use_ees_russia_gaes_variants=True,
    )

    plain_codes = {
        str(e.perimeter_variant_code)
        for e in without_flag
        if e.perimeter_variant_code
    }
    assert plain_codes == {CODE_WITH_NT, CODE_WITHOUT_NT}

    gaes_codes = {
        str(e.perimeter_variant_code)
        for e in with_flag
        if e.perimeter_variant_code
    }
    assert gaes_codes == {
        CODE_WITH_NT_WITH_GAES,
        CODE_WITH_NT_WITHOUT_GAES,
        CODE_WITHOUT_NT_WITH_GAES,
        CODE_WITHOUT_NT_WITHOUT_GAES,
    }
    assert all(e.label == EES_UNIFIED_REF_NAME for e in with_flag if e.perimeter_variant_code)


def test_apply_gaes_without_charge_formula_south_without_nt_without_gaes_is_formula_derived(
    monkeypatch,
):
    """ОЭС Юга без НТ без заряда ГАЭС = с зарядом − заряд; всегда расчётная, на все годы."""
    years = [2024, 2025, 2026]
    monkeypatch.setattr(
        service,
        "perimeter_variant_year_bounds_for_code",
        lambda code: (2024, 2025)
        if code
        in (
            service.CODE_WITHOUT_NT_WITH_GAES,
            service.CODE_WITHOUT_NT_WITHOUT_GAES,
        )
        else (None, None),
    )
    source_row = {
        **_south_variant_row(service.CODE_WITHOUT_NT_WITH_GAES, "100.0"),
        "year_values": ["100.0", "110.0", "120.0"],
        "year_numeric_tooltips": ["100.0", "110.0", "120.0"],
    }
    charge_row = {
        **_south_gaes_charge_row_for_nt_group("12.0", nt_group="without_nt"),
        "year_values": ["12.0", "10.0", "8.0"],
        "year_numeric_tooltips": ["12.0", "10.0", "8.0"],
    }
    target_row = {
        **_south_variant_row(service.CODE_WITHOUT_NT_WITHOUT_GAES, "77.5"),
        "year_values": ["77.5", "—", "—"],
        "year_numeric_tooltips": ["77.5", "", ""],
    }
    rows = [source_row, charge_row, target_row]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)
    service.apply_gaes_without_charge_formula_to_summary_rows(
        rows,
        years,
        rounding_digits=1,
    )

    assert service._raw_year_values_from_summary_row(
        target_row, years, ignore_perimeter_variant_year_bounds=True
    ) == {
        2024: Decimal("88.0"),
        2025: Decimal("100.0"),
        2026: Decimal("112.0"),
    }
    assert target_row.get("year_values") == ["88", "100", "112"]
    assert target_row.get("pd_ec_formula_derived_row") is True
    assert target_row.get("pd_ec_skip_perimeter_variant_year_bounds") is True
    assert (
        target_row.get("gaes_without_charge_formula_kind")
        == "south_ues_without_nt_without_gaes"
    )


def test_apply_gaes_without_charge_formula_fills_empty_south_without_nt_without_gaes():
    years = [2024]
    source_row = _south_variant_row(service.CODE_WITHOUT_NT_WITH_GAES, "100.0")
    charge_row = _south_gaes_charge_row_for_nt_group("12.0", nt_group="without_nt")
    target_row = _south_variant_row(service.CODE_WITHOUT_NT_WITHOUT_GAES, "—")
    rows = [source_row, charge_row, target_row]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)
    service.apply_gaes_without_charge_formula_to_summary_rows(
        rows,
        years,
        rounding_digits=1,
    )

    assert service._raw_year_values_from_summary_row(target_row, years) == {
        2024: Decimal("88.0")
    }
    assert target_row.get("pd_ec_formula_derived_row") is True
    assert (
        target_row.get("gaes_without_charge_formula_kind")
        == "south_ues_without_nt_without_gaes"
    )


def test_apply_gaes_without_charge_formula_replaces_polluted_south_without_nt_without_gaes():
    """Ранний проход мог скопировать «с зарядом» — повторный вызов должен вычесть ГАЭС."""
    years = [2024]
    source_row = _south_variant_row(service.CODE_WITHOUT_NT_WITH_GAES, "100.0")
    charge_row = _south_gaes_charge_row_for_nt_group("12.0", nt_group="without_nt")
    target_row = _south_variant_row(service.CODE_WITHOUT_NT_WITHOUT_GAES, "100.0")
    rows = [source_row, charge_row, target_row]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)
    service.apply_gaes_without_charge_formula_to_summary_rows(
        rows,
        years,
        rounding_digits=1,
    )

    assert service._raw_year_values_from_summary_row(target_row, years) == {
        2024: Decimal("88.0")
    }
    assert target_row.get("pd_ec_formula_derived_row") is True


def test_apply_gaes_without_charge_formula_does_not_sum_south_nt_charge_twice():
    years = [2024]
    with_nt_source = _south_variant_row(service.CODE_WITH_NT_WITH_GAES, "150.0")
    without_nt_source = _south_variant_row(service.CODE_WITHOUT_NT_WITH_GAES, "100.0")
    with_nt_charge = _south_gaes_charge_row_for_nt_group("20.0", nt_group="with_nt")
    without_nt_charge = _south_gaes_charge_row_for_nt_group(
        "12.0", nt_group="without_nt"
    )
    with_nt_target = _south_variant_row(service.CODE_WITH_NT_WITHOUT_GAES, "0.0")
    without_nt_target = _south_variant_row(service.CODE_WITHOUT_NT_WITHOUT_GAES, "0.0")
    rows = [
        with_nt_source,
        with_nt_charge,
        with_nt_target,
        without_nt_source,
        without_nt_charge,
        without_nt_target,
    ]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)
    service.apply_gaes_without_charge_formula_to_summary_rows(
        rows,
        years,
        rounding_digits=1,
    )

    assert service._raw_year_values_from_summary_row(with_nt_target, years) == {
        2024: Decimal("130.0")
    }
    assert service._raw_year_values_from_summary_row(without_nt_target, years) == {
        2024: Decimal("88.0")
    }
    assert without_nt_target.get("pd_ec_formula_derived_row") is True


def test_first_sa_without_kaliningrad_verification_prefers_summary_row_over_db(
    monkeypatch,
):
    years = [2025]
    first_sa_id = 39
    computed = Decimal("1087532.4")
    stale_db = Decimal("1009410.6")
    summary_rows = [
        {
            "demand_model_name": "SynchronousAreaEnergyConsumptionParameter",
            "parent_fk_column": "id_synchronous_area",
            "parent_id": first_sa_id,
            "entity_kind": "perimeter_variant",
            "entity_label": "Первая синхронная зона",
            "perimeter_variant_code": service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_VARIANT,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "year_values": [str(computed)],
            "year_numeric_tooltips": [str(computed)],
        },
        {
            "demand_model_name": "SynchronousAreaEnergyConsumptionParameter",
            "parent_fk_column": "id_synchronous_area",
            "parent_id": first_sa_id,
            "entity_kind": "perimeter_variant",
            "entity_label": "Первая синхронная зона",
            "perimeter_variant_code": service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_VARIANT,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "year_values": [str(computed)],
            "year_numeric_tooltips": [str(computed)],
        },
    ]

    monkeypatch.setattr(
        service,
        "_year_values_from_parent_demand_rows",
        lambda *_args, **_kwargs: {2025: stale_db},
    )
    monkeypatch.setattr(
        service,
        "_year_values_sum_ues_in_first_sa_without_kaliningrad_es",
        lambda *_args, **_kwargs: {2025: computed},
    )

    rows = service._build_first_sa_without_nt_with_gaes_ues_verification_rows(
        summary_rows,
        years=years,
        rounding_digits=1,
        first_sa_id=first_sa_id,
        exclude_ues_ids=frozenset(),
        entity_depth=0,
        entity_label=service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_UES_VERIFICATION_LABEL,
        formula_tooltip=service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_UES_VERIFICATION_TOOLTIP,
        first_sa_perimeter_variant_code=service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_VARIANT,
        default_ues_variant_code=service.CODE_WITHOUT_NT_WITH_GAES,
        year_bounds_variant_code=service.CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES,
        use_without_kaliningrad_es_sum=True,
    )

    ec_row = next(
        row for row in rows if row["parameter_key"] == "energy_consumption_mln_kvt_ch"
    )
    assert ec_row["year_values"] == ["0"]


def test_first_sa_kaliningrad_verification_respects_year_bounds():
    years = [2023, 2024, 2025, 2026]
    base_ec = {y: Decimal("100") for y in years}
    sum_ec = {y: Decimal("100") for y in years}

    with_kaliningrad_rows = service._build_ec_summary_verification_rows(
        entity_label=service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_UES_VERIFICATION_LABEL,
        entity_kind="oes_ees_sync_table_verification",
        entity_depth=0,
        years=years,
        rounding_digits=1,
        base_ec=base_ec,
        sum_ec=sum_ec,
        base_sipr={},
        sum_sipr={},
        year_bounds_variant_code=service.CODE_WITHOUT_NT_WITH_KALININGRAD_ES,
    )
    without_kaliningrad_rows = service._build_ec_summary_verification_rows(
        entity_label=service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_UES_VERIFICATION_LABEL,
        entity_kind="oes_ees_sync_table_verification",
        entity_depth=0,
        years=years,
        rounding_digits=1,
        base_ec=base_ec,
        sum_ec=sum_ec,
        base_sipr={},
        sum_sipr={},
        year_bounds_variant_code=service.CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES,
    )

    with_kal_ec = next(
        row
        for row in with_kaliningrad_rows
        if row["parameter_key"] == "energy_consumption_mln_kvt_ch"
    )
    without_kal_ec = next(
        row
        for row in without_kaliningrad_rows
        if row["parameter_key"] == "energy_consumption_mln_kvt_ch"
    )

    assert with_kal_ec.get("perimeter_variant_to_year") is None
    assert with_kal_ec["year_values"] != ["—", "—", "—", "—"]
    assert with_kal_ec["pd_ec_verification_year_red"] == [False, False, False, False]

    assert without_kal_ec["perimeter_variant_from_year"] == 2025
    assert without_kal_ec["year_values"][:2] == ["—", "—"]
    assert without_kal_ec["year_values"][2:] != ["—", "—"]
    assert without_kal_ec["pd_ec_verification_year_red"] == [False, False, False, False]


def test_apply_first_sa_kaliningrad_es_subtract_from_year_values_like_power_demand(
    monkeypatch,
):
    """Как на /power_demand/: для ``_kaliningrad`` вычитание ЭС Калининграда с «Год с»."""
    years = [2024, 2025]
    year_sums = {2024: Decimal("130"), 2025: Decimal("240")}
    kaliningrad = {2024: Decimal("5"), 2025: Decimal("7")}

    monkeypatch.setattr(
        service,
        "perimeter_variant_year_bounds_for_code",
        lambda _code: (2025, None),
    )
    adjusted = service._apply_first_sa_kaliningrad_es_subtract_from_year_values(
        years,
        year_sums,
        kaliningrad,
        "without_nt_with_gaes_kaliningrad",
    )
    assert adjusted == {2024: Decimal("130"), 2025: Decimal("233")}

    unchanged = service._apply_first_sa_kaliningrad_es_subtract_from_year_values(
        years,
        year_sums,
        kaliningrad,
        "without_nt_with_gaes",
    )
    assert unchanged == year_sums


def test_first_sa_verification_red_flags_nonzero_after_perimeter_tag():
    years = [2024, 2025]
    rows = service._build_ec_summary_verification_rows(
        entity_label=service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_UES_VERIFICATION_LABEL,
        entity_kind="oes_ees_sync_table_verification",
        entity_depth=0,
        years=years,
        rounding_digits=1,
        base_ec={2024: Decimal("100.5"), 2025: Decimal("100")},
        sum_ec={2024: Decimal("100"), 2025: Decimal("100.1")},
        base_sipr={},
        sum_sipr={},
        year_bounds_variant_code=service.CODE_WITHOUT_NT_WITH_KALININGRAD_ES,
    )
    service.tag_energy_consumption_summary_rows_perimeter_variant_labels(rows)
    ec = next(
        row for row in rows if row["parameter_key"] == "energy_consumption_mln_kvt_ch"
    )
    assert ec["year_values"][0] not in ("—", "0", "0,0", "0,000000")
    assert ec["year_values"][1] not in ("—", "0", "0,0", "0,000000")
    assert ec["pd_ec_verification_year_red"] == [True, True]
    assert ec.get("perimeter_variant_to_year") is None


def test_first_sa_without_kal_verification_red_flags_nonzero_after_perimeter_tag():
    years = [2024, 2025]
    rows = service._build_ec_summary_verification_rows(
        entity_label=service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_UES_VERIFICATION_LABEL,
        entity_kind="oes_ees_sync_table_verification",
        entity_depth=0,
        years=years,
        rounding_digits=1,
        base_ec={2024: Decimal("100"), 2025: Decimal("100.25")},
        sum_ec={2024: Decimal("100"), 2025: Decimal("100")},
        base_sipr={},
        sum_sipr={},
        year_bounds_variant_code=service.CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES,
    )
    service.tag_energy_consumption_summary_rows_perimeter_variant_labels(rows)
    ec = next(
        row for row in rows if row["parameter_key"] == "energy_consumption_mln_kvt_ch"
    )
    assert ec["year_values"][0] == "—"
    assert ec["year_values"][1] not in ("—", "0", "0,0", "0,000000")
    assert ec["pd_ec_verification_year_red"] == [False, True]
    assert ec.get("perimeter_variant_from_year") == 2025


def test_verification_red_flags_follow_displayed_nonzero_values():
    years = [2024]
    rows = service._build_ec_summary_verification_rows(
        entity_label=service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_UES_VERIFICATION_LABEL,
        entity_kind="oes_ees_sync_table_verification",
        entity_depth=0,
        years=years,
        rounding_digits=1,
        base_ec={2024: Decimal("10.1234567")},
        sum_ec={2024: Decimal("10.1234500")},
        base_sipr={},
        sum_sipr={},
        year_bounds_variant_code=service.CODE_WITHOUT_NT_WITH_KALININGRAD_ES,
    )
    ec_row = next(
        row for row in rows if row["parameter_key"] == "energy_consumption_mln_kvt_ch"
    )
    assert ec_row["year_values"] == ["0,000007"]
    assert ec_row["pd_ec_verification_year_red"] == [True]


def test_verify_for_rows_use_six_decimal_places_independent_of_rounding_digits():
    years = [2024]
    rows = service._build_ec_summary_verification_rows(
        entity_label="Проверка для ОЭС Центра",
        entity_kind="ues_res_sum_check",
        entity_depth=1,
        years=years,
        rounding_digits=1,
        base_ec={2024: Decimal("10.1234567")},
        sum_ec={2024: Decimal("10.1234500")},
        base_sipr={},
        sum_sipr={},
    )
    ec_row = next(
        row for row in rows if row["parameter_key"] == "energy_consumption_mln_kvt_ch"
    )
    assert ec_row["year_values"] == ["0,000007"]
    assert ec_row["pd_ec_verification_year_red"] == [True]


def test_all_verification_rows_use_six_decimal_places_independent_of_rounding_digits():
    years = [2024]
    rows = service._build_ec_summary_verification_rows(
        entity_label="Проверка ЕЭС России без НТ с зарядом ГАЭС",
        entity_kind="oes_ees_sync_table_verification",
        entity_depth=0,
        years=years,
        rounding_digits=1,
        base_ec={2024: Decimal("0.1234567")},
        sum_ec={2024: Decimal(0)},
        base_sipr={},
        sum_sipr={},
    )
    ec_row = next(
        row for row in rows if row["parameter_key"] == "energy_consumption_mln_kvt_ch"
    )
    assert ec_row["year_values"] == ["0,123457"]


def test_sync_table_verification_rows_get_nt_gaes_toggle_compact_labels():
    """«Проверка ЕЭС/СЗ …»: приписки НТ/ГАЭС только при нажатых кнопках — как у обычных строк."""
    ees_rows = [
        {
            "entity_label": "Проверка ЕЭС России без НТ с зарядом ГАЭС",
            "entity_kind": "oes_ees_sync_table_verification",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        }
    ]
    service._tag_sync_table_verification_rows_for_nt_gaes_toggles(
        ees_rows,
        perimeter_variant_code=service.CODE_WITHOUT_NT_WITH_GAES,
    )
    assert ees_rows[0]["pd_ec_entity_label_compact"] == "Проверка ЕЭС России без НТ"
    assert (
        ees_rows[0]["pd_ec_entity_label_compact_nt"]
        == "Проверка ЕЭС России с зарядом ГАЭС"
    )
    assert ees_rows[0]["pd_ec_entity_label_compact_nt_gaes"] == "Проверка ЕЭС России"
    assert (
        service.export_entity_label_for_summary_row(
            ees_rows[0],
            service.EnergyConsumptionExportUiOptions(
                sipr_on=False,
                verification_on=True,
                gaes_detail_on=False,
                nt_detail_on=False,
                isolated_energy_units_on=False,
                territory_compact_on=True,
            ),
        )
        == "Проверка ЕЭС России"
    )
    assert (
        service.export_entity_label_for_summary_row(
            ees_rows[0],
            service.EnergyConsumptionExportUiOptions(
                sipr_on=False,
                verification_on=True,
                gaes_detail_on=True,
                nt_detail_on=True,
                isolated_energy_units_on=False,
                territory_compact_on=True,
            ),
        )
        == "Проверка ЕЭС России без НТ с зарядом ГАЭС"
    )

    first_sa_rows = [
        {
            "entity_label": (
                "Проверка первой синхронной зоны без НТ с зарядом ГАЭС "
                "(без ЭС Калининградской области)"
            ),
            "entity_kind": "oes_ees_sync_table_verification",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        }
    ]
    service._tag_sync_table_verification_rows_for_nt_gaes_toggles(
        first_sa_rows,
        perimeter_variant_code=service.CODE_WITHOUT_NT_WITH_GAES,
    )
    assert (
        first_sa_rows[0]["pd_ec_entity_label_compact_nt_gaes"]
        == "Проверка первой синхронной зоны"
    )
    assert (
        first_sa_rows[0]["pd_ec_entity_label_compact"]
        == "Проверка первой синхронной зоны без НТ"
    )


def test_consumption_mln_rows_respect_rounding_digits_from_url():
    class _DemandRow:
        def __init__(self, ec: Decimal, sipr: Decimal | None = None):
            self.year_number = 2024
            self.energy_consumption_mln_kvt_ch = ec
            self.energy_consumption_sipr_mln_kvt_ch = sipr

    parameter_maps, tooltips = service._build_parameter_maps(
        [_DemandRow(Decimal("1234.6"), Decimal("789.44"))],
        service.PARAMETERS_ENERGY_CONSUMPTION,
        rounding_digits=2,
    )

    assert parameter_maps["energy_consumption_mln_kvt_ch"][2024] == "1 234,6"
    assert parameter_maps["energy_consumption_sipr_mln_kvt_ch"][2024] == "789,44"
    assert tooltips["energy_consumption_sipr_mln_kvt_ch"][2024] == "789,44"
    assert parameter_maps[service.ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY][2024] == "—"


def test_sipr_consumption_display_falls_back_to_ec_when_sipr_missing():
    class _DemandRow:
        def __init__(self, year: int, ec: Decimal, sipr: Decimal | None = None):
            self.year_number = year
            self.energy_consumption_mln_kvt_ch = ec
            self.energy_consumption_sipr_mln_kvt_ch = sipr

    parameter_maps, tooltips = service._build_parameter_maps(
        [
            _DemandRow(2023, Decimal("1000")),
            _DemandRow(2024, Decimal("1100")),
        ],
        service.PARAMETERS_ENERGY_CONSUMPTION,
        rounding_digits=1,
    )

    assert parameter_maps["energy_consumption_sipr_mln_kvt_ch"][2024] == "1 100"
    assert tooltips["energy_consumption_sipr_mln_kvt_ch"][2024] == "1 100"
    assert parameter_maps[service.ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY][2024] == "100"
    assert parameter_maps[service.ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY][2024] == "10,00"


def test_recompute_sipr_growth_metrics_after_display_fallback():
    years = [2023, 2024]
    russia_base = {
        "demand_model_name": "RussiaFederationEnergyConsumptionParameter",
        "parent_fk_column": None,
        "parent_id": None,
        "entity_kind": service.ENTITY_KIND_RUSSIA_FEDERATION,
        "entity_label": "Россия с НТ",
        "perimeter_variant_code": service.CODE_WITH_NT,
        "pd_ec_skip_perimeter_variant_year_bounds": True,
    }
    summary_rows = [
        {
            **russia_base,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "year_values": ["1000", "1100"],
            "year_numeric_tooltips": ["1000", "1100"],
        },
        {
            **russia_base,
            "parameter_key": service.ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
            "year_values": ["—", "—"],
            "year_numeric_tooltips": ["", ""],
        },
        {
            **russia_base,
            "parameter_key": service.ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
            "year_values": ["—", "—"],
            "year_numeric_tooltips": ["", ""],
        },
    ]
    service.recompute_sipr_growth_metrics_for_summary_rows(summary_rows, years, rounding_digits=1)
    abs_row = summary_rows[1]
    yoy_row = summary_rows[2]
    assert abs_row["year_values"][1] == "100"
    assert yoy_row["year_values"][1] == "10,00"


def test_apply_sipr_consumption_display_fallback_to_summary_rows():
    years = [2024]
    summary_rows = [
        {
            "demand_model_name": "FederalDistrictEnergyConsumptionParameter",
            "parent_fk_column": "id_federal_district",
            "parent_id": 1,
            "entity_kind": "group",
            "entity_label": "Центральный ФО",
            "perimeter_variant_code": None,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "year_values": ["100,5"],
            "year_numeric_tooltips": ["100,5"],
        },
        {
            "demand_model_name": "FederalDistrictEnergyConsumptionParameter",
            "parent_fk_column": "id_federal_district",
            "parent_id": 1,
            "entity_kind": "group",
            "entity_label": "Центральный ФО",
            "perimeter_variant_code": None,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "year_values": ["—"],
            "year_numeric_tooltips": [""],
        },
    ]
    service.apply_sipr_consumption_display_fallback_to_summary_rows(summary_rows, years)
    sipr_row = summary_rows[1]
    assert sipr_row["year_values"] == ["100,5"]
    assert sipr_row["year_numeric_tooltips"] == ["100,5"]


def test_summary_table_russia_with_nt_shows_all_years():
    years = [2022, 2023, 2024, 2025]
    summary_rows = [
        {
            "entity_kind": service.ENTITY_KIND_RUSSIA_FEDERATION,
            "entity_label": "Россия",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "perimeter_variant_code": service.CODE_WITH_NT,
            "year_values": ["10.0", "20.0", "30.0", "40.0"],
            "year_numeric_tooltips": ["10.0", "20.0", "30.0", "40.0"],
            "year_row_ids": [1, 2, 3, 4],
        }
    ]

    service.apply_summary_table_russia_federation_row_rules(summary_rows)
    service.tag_energy_consumption_summary_rows_perimeter_variant_labels(summary_rows)
    service.mask_summary_rows_perimeter_variant_year_display(summary_rows, years)

    row = summary_rows[0]
    assert row["entity_label"] == f"{service.RUSSIA_FEDERATION_AGGREGATE_NAME} с НТ"
    assert row.get("pd_ec_skip_perimeter_variant_year_bounds") is True
    assert "perimeter_variant_from_year" not in row
    assert "perimeter_variant_to_year" not in row
    assert row["year_values"] == ["10.0", "20.0", "30.0", "40.0"]
    assert row["year_row_ids"] == [1, 2, 3, 4]


def test_mask_unrestricted_perimeter_variant_input_keeps_all_years(monkeypatch):
    """На /summary/oes/ строки с вариантом ≠ «не указано» не маскируются по Год с/по."""
    years = [2022, 2023, 2024, 2025]

    def _fake_bounds(code: str):
        if code == "without_nt_with_gaes_kaliningrad":
            return 2025, None
        return None, None

    monkeypatch.setattr(
        service,
        "perimeter_variant_year_bounds_for_code",
        _fake_bounds,
    )
    summary_rows = [
        {
            "entity_kind": "union_energy_system",
            "entity_label": "ОЭС Центра",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "perimeter_variant_code": "without_nt_with_gaes_kaliningrad",
            "year_values": ["10.0", "20.0", "30.0", "40.0"],
            "year_numeric_tooltips": ["10.0", "20.0", "30.0", "40.0"],
            "year_row_ids": [1, 2, 3, 4],
        },
        {
            "entity_kind": "union_energy_system",
            "entity_label": "ОЭС Северо-Запада",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "perimeter_variant_code": None,
            "year_values": ["1.0", "2.0", "3.0", "4.0"],
            "year_numeric_tooltips": ["1.0", "2.0", "3.0", "4.0"],
            "year_row_ids": [5, 6, 7, 8],
        },
    ]

    service.mask_summary_rows_perimeter_variant_year_display(
        summary_rows,
        years,
        unrestricted_perimeter_variant_input=True,
    )

    restricted_code_row = summary_rows[0]
    assert restricted_code_row.get("pd_ec_skip_perimeter_variant_year_bounds") is True
    assert "perimeter_variant_from_year" not in restricted_code_row
    assert restricted_code_row["year_values"] == ["10.0", "20.0", "30.0", "40.0"]
    assert restricted_code_row["year_row_ids"] == [1, 2, 3, 4]

    unset_row = summary_rows[1]
    assert unset_row.get("pd_ec_skip_perimeter_variant_year_bounds") is not True
    assert unset_row["year_values"] == ["1.0", "2.0", "3.0", "4.0"]

    # Без флага — маскируем годы до «Год с».
    masked = [
        {
            "entity_kind": "union_energy_system",
            "entity_label": "ОЭС Центра",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "perimeter_variant_code": "without_nt_with_gaes_kaliningrad",
            "year_values": ["10.0", "20.0", "30.0", "40.0"],
            "year_numeric_tooltips": ["10.0", "20.0", "30.0", "40.0"],
            "year_row_ids": [1, 2, 3, 4],
        }
    ]
    service.mask_summary_rows_perimeter_variant_year_display(masked, years)
    assert masked[0]["year_values"] == ["—", "—", "—", "40.0"]
    assert masked[0]["year_row_ids"] == [None, None, None, 4]


def test_formula_write_respects_perimeter_variant_year_bounds_even_when_input_unrestricted(
    monkeypatch,
):
    """Формулы на oes/fo/ez пишутся только в «Год с»…«Год по»; вне периода — данные из БД."""
    years = [2022, 2023, 2024, 2025]

    def _fake_bounds(code: str):
        if code == "with_nt_with_gaes":
            return 2023, 2024
        return None, None

    monkeypatch.setattr(
        service,
        "perimeter_variant_year_bounds_for_code",
        _fake_bounds,
    )
    row = {
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "perimeter_variant_code": "with_nt_with_gaes",
        "pd_ec_skip_perimeter_variant_year_bounds": True,
        "year_values": ["11.0", "22.0", "33.0", "44.0"],
        "year_numeric_tooltips": ["11.0", "22.0", "33.0", "44.0"],
    }
    service._write_numeric_year_values_to_summary_row(
        row,
        years,
        {
            2022: Decimal("100.0"),
            2023: Decimal("200.0"),
            2024: Decimal("300.0"),
            2025: Decimal("400.0"),
        },
        parameter_key="energy_consumption_mln_kvt_ch",
        rounding_digits=1,
    )
    assert row["year_values"] == ["11.0", "200", "300", "44.0"]
    assert row["year_numeric_tooltips"][0] == "11.0"
    assert row["year_numeric_tooltips"][3] == "44.0"


def test_formula_year_applies_ignores_skip_flag(monkeypatch):
    monkeypatch.setattr(
        service,
        "perimeter_variant_year_bounds_for_code",
        lambda _code: (2023, None),
    )
    row = {
        "perimeter_variant_code": "with_nt",
        "pd_ec_skip_perimeter_variant_year_bounds": True,
    }
    assert service._year_applies_to_summary_row_perimeter_variant(row, 2022) is True
    assert service._formula_year_applies_to_row_perimeter_variant(row, 2022) is False
    assert service._formula_year_applies_to_row_perimeter_variant(row, 2023) is True


def test_energy_unit_ec_perimeter_entity_context_resolves(monkeypatch):
    from app.common.perimeter_variant.registry import perimeter_entity_context_for_model

    class _FakeEU:
        name = "Тестовый энергорайон"

    def _fake_import_module(name):
        mod = type("m", (), {})()
        if name.endswith("energy_unit_model"):
            mod.EnergyUnit = type(
                "EU",
                (),
                {
                    "query": type(
                        "Q",
                        (),
                        {"get": staticmethod(lambda _id: _FakeEU())},
                    )()
                },
            )
        return mod

    monkeypatch.setattr("importlib.import_module", _fake_import_module)
    ctx = perimeter_entity_context_for_model(
        "EnergyUnitEnergyConsumptionParameter",
        parent_fk_column="id_energy_unit",
        parent_id=1,
    )
    assert ctx == ("energy_unit", "Тестовый энергорайон")


def test_tag_ec_summary_o1_energy_unit_gets_perimeter_select_with_options(monkeypatch):
    from app.common.perimeter_variant.registry import resolve_catalog_o1_perimeter_variant_code

    o1_code = resolve_catalog_o1_perimeter_variant_code()
    row = {
        "show_entity_cell": True,
        "entity_label": "Изолированный энергорайон",
        "demand_model_name": "EnergyUnitEnergyConsumptionParameter",
        "parent_fk_column": "id_energy_unit",
        "parent_id": 42,
        "perimeter_variant_code": o1_code,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "pd_ec_perimeter_entity_kind": "energy_unit",
        "pd_ec_perimeter_entity_name": "Изолированный энергорайон",
    }
    monkeypatch.setattr(
        "app.power_demand.services.demand_summary_services._perimeter_variant_options_for_summary",
        lambda kind, name: [],
    )
    service.tag_energy_consumption_summary_rows_perimeter_variant_labels(
        [row],
        use_summary_perimeter_options=True,
    )
    assert row["show_perimeter_variant_select"] is True
    assert any(
        opt.get("code") == o1_code for opt in row.get("perimeter_variant_options") or []
    )


def test_ec_summary_table_oes_perimeter_labels_do_not_strip_gaes(monkeypatch):
    captured_strip_flags: list[bool] = []

    def _fake_label(code, *, binding, entity_kind, entity_name, strip_gaes_suffix=True):
        captured_strip_flags.append(strip_gaes_suffix)
        return "без НТ без заряда ГАЭС"

    def _fake_options(kind, name, *, strip_gaes_suffix=True):
        captured_strip_flags.append(strip_gaes_suffix)
        return [{"code": "without_nt_without_gaes", "label": "без НТ без заряда ГАЭС"}]

    monkeypatch.setattr(
        "app.power_demand.services.demand_summary_services._oes_perimeter_variant_russian_label",
        _fake_label,
    )
    monkeypatch.setattr(
        "app.power_demand.services.demand_summary_services._perimeter_variant_options_for_oes_summary",
        _fake_options,
    )
    row = {
        "show_entity_cell": True,
        "entity_label": "Первая синхронная зона",
        "demand_model_name": "SynchronousAreaEnergyConsumptionParameter",
        "parent_fk_column": "id_synchronous_area",
        "parent_id": 39,
        "perimeter_variant_code": "without_nt_without_gaes",
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "pd_ec_perimeter_entity_kind": "synchronous_area",
        "pd_ec_perimeter_entity_name": "Первая синхронная зона",
    }
    service.tag_energy_consumption_summary_rows_perimeter_variant_labels(
        [row],
        oes_summary=True,
        use_summary_perimeter_options=True,
    )
    assert captured_strip_flags == [False, False]
    assert row["perimeter_variant_label"] == "без НТ без заряда ГАЭС"


def test_ec_ensure_gaes_suffix_in_perimeter_variant_label_from_short_catalog():
    assert service._ensure_gaes_suffix_in_perimeter_variant_label(
        "без НТ",
        "without_nt_without_gaes",
    ) == "без НТ без заряда ГАЭС"
    assert service._ensure_gaes_suffix_in_perimeter_variant_label(
        "без заряда ГАЭС",
        None,
    ) == "без заряда ГАЭС"


def test_ec_retag_preserves_injected_gaes_perimeter_label(monkeypatch):
    row = {
        "show_entity_cell": True,
        "entity_label": "ОЭС Центра без заряда ГАЭС",
        "demand_model_name": "UnionEnergySystemEnergyConsumptionParameter",
        "parent_fk_column": "id_union_energy_system",
        "parent_id": 117,
        "perimeter_variant_code": None,
        "perimeter_variant_label": service._GAES_PERIMETER_VARIANT_LABEL_WITHOUT,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "pd_ec_perimeter_entity_kind": "union_energy_system",
        "pd_ec_perimeter_entity_name": "ОЭС Центра",
        "pd_ec_ues_without_gaes_injected_row": True,
    }
    monkeypatch.setattr(
        "app.power_demand.services.demand_summary_services._perimeter_variant_options_for_oes_summary",
        lambda kind, name, strip_gaes_suffix=False: [],
    )
    service.tag_energy_consumption_summary_rows_perimeter_variant_labels(
        [row],
        oes_summary=True,
        use_summary_perimeter_options=True,
    )
    assert row["perimeter_variant_label"] == service._GAES_PERIMETER_VARIANT_LABEL_WITHOUT


def test_ees_russia_without_nt_gaes_verification_computed_for_all_years():
    years = [2023, 2024, 2025, 2026]
    base_ec = {y: Decimal("100") for y in years}
    sum_ec = {y: Decimal("100") for y in years}

    without_nt_rows = service._build_ec_summary_verification_rows(
        entity_label=service._EES_RUSSIA_WITHOUT_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_LABEL,
        entity_kind="oes_ees_sync_table_verification",
        entity_depth=0,
        years=years,
        rounding_digits=1,
        base_ec=base_ec,
        sum_ec=sum_ec,
        base_sipr={},
        sum_sipr={},
        year_bounds_variant_code=None,
    )

    without_nt_ec = next(
        row
        for row in without_nt_rows
        if row["parameter_key"] == "energy_consumption_mln_kvt_ch"
    )

    assert "perimeter_variant_from_year" not in without_nt_ec
    assert "perimeter_variant_to_year" not in without_nt_ec
    assert without_nt_ec["year_values"] == ["0", "0", "0", "0"]
    assert without_nt_ec["entity_rowspan"] == 2
    assert {row["parameter_key"] for row in without_nt_rows} == {
        "energy_consumption_mln_kvt_ch",
        "energy_consumption_sipr_mln_kvt_ch",
    }
    assert all(row.get("pd_ec_verification_omit_sipr_abs") for row in without_nt_rows)


def test_ees_russia_with_nt_gaes_verification_keeps_sipr_abs_parameter():
    years = [2024]
    with_nt_rows = service._build_ec_summary_verification_rows(
        entity_label=service._EES_RUSSIA_WITH_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_LABEL,
        entity_kind="oes_ees_sync_table_verification",
        entity_depth=0,
        years=years,
        rounding_digits=1,
        base_ec={2024: Decimal("10")},
        sum_ec={2024: Decimal("10")},
        base_sipr={},
        sum_sipr={},
        year_bounds_variant_code=None,
    )
    assert "energy_consumption_sipr_abs_growth_mln" in {
        row["parameter_key"] for row in with_nt_rows
    }
    assert not any(row.get("pd_ec_verification_omit_sipr_abs") for row in with_nt_rows)


def test_first_sa_without_nt_with_gaes_parameter_year_values_prefers_without_kaliningrad():
    years = [2024]
    first_sa_without_kal = Decimal("1087532.4")
    summary_rows = [
        {
            "demand_model_name": "SynchronousAreaEnergyConsumptionParameter",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "entity_label": "Первая синхронная зона",
            "perimeter_variant_code": service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_VARIANT,
            "pd_ec_skip_perimeter_variant_year_bounds": True,
            "year_values": [str(first_sa_without_kal)],
            "year_numeric_tooltips": [str(first_sa_without_kal)],
        },
        {
            "demand_model_name": "SynchronousAreaEnergyConsumptionParameter",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "entity_label": "Первая синхронная зона",
            "perimeter_variant_code": service.CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES,
            "pd_ec_skip_perimeter_variant_year_bounds": True,
            "year_values": ["9999999.0"],
            "year_numeric_tooltips": ["9999999.0"],
        },
    ]

    result = service._first_sa_without_nt_with_gaes_parameter_year_values(
        summary_rows,
        years,
        "energy_consumption_mln_kvt_ch",
    )

    assert result == {2024: first_sa_without_kal}


def test_ees_russia_without_nt_gaes_verification_formula_matches_user_example(monkeypatch):
    years = [2024]
    ees_total = Decimal("1143225.2")
    first_sa = Decimal("1087532.4")
    second_sa = Decimal("50551.3")
    kaliningrad = Decimal("5141.5")

    monkeypatch.setattr(
        service,
        "_ees_russia_without_nt_with_gaes_verification_component_values",
        lambda _rows, _years, _key: (
            {2024: first_sa},
            {2024: second_sa},
            {2024: kaliningrad},
        ),
    )
    monkeypatch.setattr(
        service,
        "_ees_russia_gaes_verification_base_year_values",
        lambda *_args, **_kwargs: {2024: ees_total},
    )

    rows = service._build_ees_russia_without_nt_with_gaes_kaliningrad_split_verification_rows(
        [],
        years=years,
        rounding_digits=1,
        entity_depth=0,
    )
    ec_row = next(row for row in rows if row["parameter_key"] == "energy_consumption_mln_kvt_ch")
    sipr_row = next(
        row for row in rows if row["parameter_key"] == "energy_consumption_sipr_mln_kvt_ch"
    )
    assert ec_row["year_values"] == ["0"]
    assert sipr_row["year_values"] == ["0"]


def test_ees_russia_without_nt_gaes_verification_excludes_tites(monkeypatch):
    """ЕЭС не включает ТИТЭС: вычитание ТИТЭС давало бы ровно −ТИТЭС."""
    years = [2024]
    first_sa = Decimal("100")
    second_sa = Decimal("20")
    kaliningrad = Decimal("5")
    tites = Decimal("22298.7")
    ees_total = first_sa + second_sa + kaliningrad

    monkeypatch.setattr(
        service,
        "_ees_russia_without_nt_with_gaes_verification_component_values",
        lambda _rows, _years, _key: (
            {2024: first_sa},
            {2024: second_sa},
            {2024: kaliningrad},
        ),
    )
    monkeypatch.setattr(
        service,
        "_ees_russia_gaes_verification_base_year_values",
        lambda *_args, **_kwargs: {2024: ees_total},
    )
    # Старая формула (с ТИТЭС) дала бы −tites; новая должна дать 0.
    assert ees_total - (first_sa + second_sa + kaliningrad + tites) == -tites

    rows = service._build_ees_russia_without_nt_with_gaes_kaliningrad_split_verification_rows(
        [],
        years=years,
        rounding_digits=1,
        entity_depth=0,
    )
    ec_row = next(row for row in rows if row["parameter_key"] == "energy_consumption_mln_kvt_ch")
    assert ec_row["year_values"] == ["0"]


def test_ees_russia_without_nt_gaes_verification_uses_ec_aligned_sipr_components(
    monkeypatch,
):
    """СиПР-слагаемые берём из потребления «с ГАЭС», даже если колонка СиПР без ГАЭС."""
    years = [2020]
    first_ec = Decimal("993025.5322992")
    second_ec = Decimal("40694.514342")
    kal_ec = Decimal("0")
    gaes_charge = Decimal("2636.192258")
    # Колонка СиПР 1-й СЗ — как без заряда ГАЭС (типичный рассинхрон данных).
    first_sipr_without_gaes = first_ec - gaes_charge
    ees_ec = first_ec + second_ec + kal_ec
    ees_sipr_rounded = Decimal("1033720")

    def _components(_rows, _years, key):
        if key == "energy_consumption_mln_kvt_ch":
            return {2020: first_ec}, {2020: second_ec}, {2020: kal_ec}
        return {2020: first_sipr_without_gaes}, {2020: second_ec}, {2020: kal_ec}

    def _base(_rows, _years, key, **_kwargs):
        if key == "energy_consumption_mln_kvt_ch":
            return {2020: ees_ec}
        return {2020: ees_sipr_rounded}

    monkeypatch.setattr(
        service,
        "_ees_russia_without_nt_with_gaes_verification_component_values",
        _components,
    )
    monkeypatch.setattr(
        service,
        "_ees_russia_gaes_verification_base_year_values",
        _base,
    )

    # Старая логика (сырой СиПР) давала бы ≈ заряд ГАЭС.
    old_sipr_diff = ees_sipr_rounded - (
        first_sipr_without_gaes + second_ec + kal_ec
    )
    assert abs(old_sipr_diff - gaes_charge) < Decimal("1")

    rows = service._build_ees_russia_without_nt_with_gaes_kaliningrad_split_verification_rows(
        [],
        years=years,
        rounding_digits=1,
        entity_depth=0,
    )
    sipr_row = next(
        row for row in rows if row["parameter_key"] == "energy_consumption_sipr_mln_kvt_ch"
    )
    ec_row = next(row for row in rows if row["parameter_key"] == "energy_consumption_mln_kvt_ch")
    assert ec_row["year_values"] == ["0"]
    assert sipr_row["year_values"] == ["0"]


def test_last_ees_russia_summary_table_row_index_before_first_oes():
    def _ees_row(*, variant: str | None = None, label: str = "ЕЭС России") -> dict:
        row = {
            "entity_label": label,
            "entity_kind": "ees_russia",
            "demand_model_name": "EesRussiaEnergyConsumptionParameter",
        }
        if variant is not None:
            row["perimeter_variant_code"] = variant
        return row

    def _sync_row() -> dict:
        return {
            "entity_label": "Первая синхронная зона",
            "demand_model_name": "SynchronousAreaEnergyConsumptionParameter",
        }

    def _oes_row() -> dict:
        return {
            "entity_label": "ОЭС Северо-Запада",
            "demand_model_name": "UnionEnergySystemEnergyConsumptionParameter",
            "parent_fk_column": "id_union_energy_system",
        }

    top_ees = _ees_row(label="ЭЭС России")
    sync = _sync_row()
    pre_oes_ees = _ees_row(
        variant=service.CODE_WITHOUT_NT_WITHOUT_GAES,
        label="ЕЭС России без НТ без заряда ГАЭС",
    )
    oes = _oes_row()
    summary_rows = [top_ees, sync, pre_oes_ees, oes]

    assert service._last_ees_russia_summary_table_row_index(summary_rows) == 2


def test_filter_summary_table_gaes_charge_aggregate_rows():
    gaes_key = service.GAES_CHARGE_PARAMETER_KEY

    def _gaes_row(**kwargs: object) -> dict:
        base = {
            "parameter_key": gaes_key,
            "pd_ec_gaes_injected_row": True,
        }
        base.update(kwargs)
        return base

    rows = [
        _gaes_row(
            entity_label="ЭЭС России (заряд ГАЭС)",
            demand_model_name="EesRussiaEnergyConsumptionParameter",
        ),
        _gaes_row(
            entity_label="ЕЭС России (заряд ГАЭС)",
            demand_model_name="EnergySystemTypeEnergyConsumptionParameter",
        ),
        _gaes_row(
            entity_label="Первая синхронная зона (заряд ГАЭС)",
            demand_model_name="SynchronousAreaEnergyConsumptionParameter",
        ),
        _gaes_row(
            entity_label="ОЭС Юга (заряд ГАЭС)",
            demand_model_name="UnionEnergySystemEnergyConsumptionParameter",
        ),
        {
            "entity_label": "ЭЭС России",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "EesRussiaEnergyConsumptionParameter",
        },
    ]

    filtered = service.filter_summary_table_gaes_charge_aggregate_rows(rows)

    assert [row.get("entity_label") for row in filtered] == [
        "ОЭС Юга (заряд ГАЭС)",
        "ЭЭС России",
    ]


def test_gaes_charge_marker_without_stations_emits_placeholder_row(monkeypatch):
    """Южный ФО: слот заряда между с/без ГАЭС виден даже без станций ГАЭС в ФО."""
    fd_mn = "FederalDistrictEnergyConsumptionParameter"
    marker = service._gaes_charge_marker_entity(
        service.SummaryEntity(
            label="Южный ФО",
            depth=0,
            parameters=service.PARAMETERS_ENERGY_CONSUMPTION,
            demand_rows=[],
            entity_kind="perimeter_variant",
            demand_model_name=fd_mn,
            parent_fk_column="id_federal_district",
            parent_id=42,
            perimeter_variant_code="without_nt_with_gaes",
        )
    )
    monkeypatch.setattr(service.dps, "get_current_version", lambda: 20)
    monkeypatch.setattr(
        service,
        "_gaes_charge_raw_station_values_for_entity",
        lambda *args, **kwargs: tuple(),
    )

    rows = service._gaes_charge_rows_for_entity(marker, [2024, 2025], rounding_digits=1)

    assert len(rows) == 1
    assert rows[0]["parameter_key"] == service.GAES_CHARGE_PARAMETER_KEY
    assert rows[0]["entity_label"] == "Южный ФО (заряд ГАЭС)"
    assert rows[0]["pd_ec_skip_empty_hide_row"] is True
    assert rows[0]["year_values"] == ["—", "—"]
    assert rows[0]["parent_id"] == 42


def test_fo_rd_gaes_labels_skip_entities_with_structural_gaes_variants():
    fd_mn = "FederalDistrictEnergyConsumptionParameter"
    rows = [
        {
            "entity_label": "Южный ФО без НТ с зарядом ГАЭС",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": fd_mn,
            "parent_fk_column": "id_federal_district",
            "parent_id": 42,
            "perimeter_variant_code": "without_nt_with_gaes",
            "show_entity_cell": True,
        },
        {
            "entity_label": "Южный ФО (заряд ГАЭС)",
            "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
            "demand_model_name": fd_mn,
            "parent_fk_column": "id_federal_district",
            "parent_id": 42,
            "pd_ec_gaes_injected_row": True,
            "show_entity_cell": True,
        },
    ]

    service.apply_fo_rd_gaes_territory_entity_labels(rows)

    assert rows[0]["entity_label"] == "Южный ФО без НТ с зарядом ГАЭС"
    assert rows[1]["entity_label"] == "Южный ФО (заряд ГАЭС)"


def test_tag_territory_compact_marks_res_rd_and_gaes_charge_rows():
    res_mn = "RegionalEnergySystemEnergyConsumptionParameter"
    rd_mn = "RegionalDistrictEnergyConsumptionParameter"
    rows = [
        {
            "demand_model_name": res_mn,
            "entity_depth": 2,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "demand_model_name": res_mn,
            "entity_depth": 2,
            "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
            "entity_label": "ОЭС Юга (заряд ГАЭС)",
        },
        {
            "demand_model_name": rd_mn,
            "entity_depth": 3,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "pd_ec_rd_without_gaes_injected_row": True,
        },
        {
            "entity_kind": service.ENTITY_KIND_RUSSIA_FEDERATION,
            "entity_label": "Заряд ГАЭС",
            "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
            "entity_depth": 0,
        },
        {
            "entity_label": "Первая синхронная зона",
            "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
            "gaes_charge_row_station_name": "всего",
            "entity_depth": 0,
            "show_entity_cell": True,
        },
    ]

    service.tag_energy_consumption_summary_rows_for_territory_compact(rows)

    assert rows[0].get("pd_ec_territory_detail_row") is True
    assert "pd_ec_territory_compact_hide_row" not in rows[0]
    assert rows[1].get("pd_ec_territory_compact_hide_row") is True
    assert rows[2].get("pd_ec_territory_detail_row") is True
    assert "pd_ec_territory_compact_hide_row" not in rows[2]
    assert rows[3].get("pd_ec_territory_compact_hide_row") is True
    assert rows[4].get("pd_ec_territory_compact_hide_row") is True
    for row in rows:
        assert "pd_ec_territory_detail_relaxed_compact_nt_gaes" not in row


def test_keep_centralized_zone_rows_in_territory_compact():
    rows = [
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
        },
        {
            "entity_kind": "union_energy_system",
            "entity_label": "ОЭС Центра",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "UnionEnergySystemEnergyConsumptionParameter",
        },
    ]

    service.tag_energy_consumption_summary_rows_for_territory_compact(rows)
    assert rows[0].get("pd_ec_territory_compact_hide_row") is True
    assert "pd_ec_territory_compact_hide_row" not in rows[1]

    service.keep_centralized_zone_rows_in_territory_compact(rows)
    assert "pd_ec_territory_compact_hide_row" not in rows[0]


def test_tag_territory_compact_hides_res_level_verification_rows():
    """В «Сводной таблице» строки «Проверка для …» по РЭС помечаются скрытыми."""
    rows = [
        {
            "entity_kind": "ues_res_sum_check",
            "entity_label": "Проверка для ОЭС Центра",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "entity_depth": 0,
        },
        {
            "entity_kind": "res_subject_sum_check",
            "entity_label": "Проверка для ЭС Москвы и Московской области",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "entity_depth": 1,
        },
        {
            "entity_kind": "tites_res_energy_unit_sum_check",
            "entity_label": "Проверка для ЭС Якутии",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "entity_depth": 2,
        },
        {
            "entity_kind": "east_ez_o1_res_energy_unit_sum_check",
            "entity_label": "Проверка для ЭС Магаданской области",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "entity_depth": 1,
        },
        {
            "entity_kind": "ez_res_sum_check",
            "entity_label": "Проверка для Энергозона Востока",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "entity_depth": 0,
        },
        {
            "entity_kind": "ues_nt_subject_sum_check",
            "entity_label": "Проверка для Новых территорий",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "entity_depth": 2,
        },
    ]

    service.tag_energy_consumption_summary_rows_for_territory_compact(rows)

    assert "pd_ec_territory_compact_hide_row" not in rows[0]
    assert rows[1].get("pd_ec_territory_compact_hide_row") is True
    assert rows[2].get("pd_ec_territory_compact_hide_row") is True
    assert rows[3].get("pd_ec_territory_compact_hide_row") is True
    assert "pd_ec_territory_compact_hide_row" not in rows[4]
    assert rows[5].get("pd_ec_territory_compact_hide_row") is True


def test_export_hides_res_verification_when_territory_compact_on():
    opts = service.EnergyConsumptionExportUiOptions(
        verification_on=True,
        territory_compact_on=True,
        summary_table_page=False,
    )
    row = {
        "entity_kind": "res_subject_sum_check",
        "entity_label": "Проверка для ЭС Москвы и Московской области",
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "pd_ec_territory_compact_hide_row": True,
    }
    assert (
        service._summary_row_visible_for_export_ui(
            row, opts=opts, parameter_visible=lambda _pk: True
        )
        is False
    )
    opts_off = service.EnergyConsumptionExportUiOptions(
        verification_on=True,
        territory_compact_on=False,
        summary_table_page=False,
    )
    assert (
        service._summary_row_visible_for_export_ui(
            row, opts=opts_off, parameter_visible=lambda _pk: True
        )
        is True
    )


def test_tag_summary_rows_before_oes_blocks_marks_prefix_only():
    rows = [
        {
            "entity_label": "Россия",
            "show_entity_cell": True,
            "entity_depth": 0,
            "demand_model_name": "RussiaFederationEnergyConsumptionParameter",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "ЦЗ России",
            "show_entity_cell": True,
            "entity_depth": 0,
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "ОЭС Центра",
            "show_entity_cell": True,
            "entity_depth": 0,
            "entity_kind": "group",
            "demand_model_name": "UnionEnergySystemEnergyConsumptionParameter",
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 1,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "entity_rowspan": 1,
        },
        {
            "entity_label": "ЭС тест",
            "show_entity_cell": True,
            "entity_depth": 1,
            "demand_model_name": "RegionalEnergySystemEnergyConsumptionParameter",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
    ]
    service.tag_energy_consumption_summary_rows_before_oes_blocks(rows)
    assert rows[0].get("pd_ec_summary_table_only_row") is True
    assert rows[1].get("pd_ec_summary_table_only_row") is True
    assert rows[2].get("pd_ec_summary_table_only_row") is not True
    assert rows[3].get("pd_ec_summary_table_only_row") is not True


def test_territory_compact_tites_block_shows_res_only(monkeypatch):
    """В «Сводной таблице» под «ТИТЭС» — РЭС Востока и энергорайон Таймыр/Норильск."""
    tites_ues_id = 77
    tites_res_id = 701
    norilsk_res_id = 702
    type_mn = "EnergySystemTypeEnergyConsumptionParameter"
    res_mn = "RegionalEnergySystemEnergyConsumptionParameter"
    eu_mn = "EnergyUnitEnergyConsumptionParameter"
    taimyr_label = (
        "Таймырский Долгано-Ненецкий муниципальный район, Туруханский район "
        "и городской округ г. Норильск Красноярского края"
    )

    monkeypatch.setattr(
        service,
        "_tites_union_energy_system_ids",
        lambda: frozenset({tites_ues_id}),
    )

    rows = [
        {
            "entity_label": "ТИТЭС",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_depth": 0,
            "entity_kind": "group-root",
            "demand_model_name": type_mn,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "ЭС г. Норильска Красноярского края",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_depth": 1,
            "demand_model_name": res_mn,
            "id_union_energy_system": tites_ues_id,
            "id_regional_energy_system": norilsk_res_id,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": taimyr_label,
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_depth": 2,
            "demand_model_name": eu_mn,
            "id_union_energy_system": tites_ues_id,
            "id_regional_energy_system": norilsk_res_id,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "ЭС Камчатского края",
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "entity_depth": 1,
            "demand_model_name": res_mn,
            "id_union_energy_system": tites_ues_id,
            "id_regional_energy_system": tites_res_id,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "ЭС Камчатского края",
            "show_entity_cell": False,
            "entity_depth": 1,
            "demand_model_name": res_mn,
            "id_union_energy_system": tites_ues_id,
            "id_regional_energy_system": tites_res_id,
            "parameter_key": "energy_consumption_yoy_pct",
        },
        {
            "entity_label": "Центральный энергорайон Камчатского края",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_depth": 2,
            "demand_model_name": eu_mn,
            "id_union_energy_system": tites_ues_id,
            "id_regional_energy_system": tites_res_id,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "ДЗ энергорайон",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_depth": 1,
            "demand_model_name": eu_mn,
            "pd_ec_decentralized_zone_mark": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
    ]

    service.tag_energy_consumption_summary_rows_for_territory_compact(rows)

    assert rows[1].get("pd_ec_territory_compact_hide_row") is True
    assert rows[2].get("pd_ec_territory_detail_row") is not True
    assert rows[3].get("pd_ec_territory_detail_row") is not True
    assert "pd_ec_territory_compact_hide_row" not in rows[3]
    assert rows[4].get("pd_ec_territory_detail_row") is not True
    assert rows[5].get("pd_ec_territory_detail_row") is True
    assert rows[6].get("pd_ec_territory_compact_hide_row") is True

    filtered = service.filter_summary_rows_for_summary_table_page(rows)
    labels = [r["entity_label"] for r in filtered if r.get("show_entity_cell")]
    assert labels == ["ТИТЭС", taimyr_label, "ЭС Камчатского края"]

def test_exclude_centralized_zone_russia_o1_summary_rows():
    rows = [
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России с НТ",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "perimeter_variant_code": "o1_with_nt",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 2,
        },
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России с НТ",
            "perimeter_variant_code": "o1_with_nt",
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "show_entity_cell": False,
            "entity_rowspan": 2,
        },
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России с НТ",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "perimeter_variant_code": "with_nt",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 1,
        },
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России без НТ",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "perimeter_variant_code": "o1_without_nt",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 1,
        },
    ]

    filtered = service.exclude_centralized_zone_russia_o1_summary_rows(rows)

    assert len(filtered) == 1
    assert filtered[0]["perimeter_variant_code"] == "with_nt"


def test_tag_perimeter_labels_cz_o1_is_o1_form_and_nt_toggle_row():
    """ЦЗ О-1: «Форма О-1»; с НТ дополнительно через pd_ec_nt_extra; подписи с/без НТ."""
    rows = [
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "perimeter_variant_code": "o1_with_nt",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_depth": 0,
        },
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "perimeter_variant_code": "o1_without_nt",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_depth": 0,
        },
        {
            "entity_label": "ЭС пример О-1",
            "demand_model_name": "RegionalEnergySystemEnergyConsumptionParameter",
            "perimeter_variant_code": "o1",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_depth": 1,
        },
    ]
    service.tag_energy_consumption_summary_rows_perimeter_variant_labels(rows)
    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)

    assert rows[0].get("pd_ec_o1_form_row") is True
    assert rows[0].get("pd_ec_nt_extra_row") is True
    assert rows[0]["entity_label"] == "ЦЗ России с НТ"
    assert rows[0].get("pd_ec_entity_label_compact_nt_gaes") == "ЦЗ России"
    assert rows[1].get("pd_ec_o1_form_row") is True
    assert rows[1].get("pd_ec_nt_extra_row") is not True
    assert rows[1].get("pd_ec_nt_without_row") is True
    assert rows[1]["entity_label"] == "ЦЗ России без НТ"
    assert rows[1].get("pd_ec_entity_label_compact_nt_gaes") == "ЦЗ России"
    assert rows[2].get("pd_ec_o1_form_row") is True


def test_exclude_centralized_zone_russia_non_o1_summary_rows():
    rows = [
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России с НТ",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "perimeter_variant_code": "o1_with_nt",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 2,
        },
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России с НТ",
            "perimeter_variant_code": "o1_with_nt",
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "show_entity_cell": False,
            "entity_rowspan": 2,
        },
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России с НТ",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "perimeter_variant_code": "with_nt",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 1,
        },
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России без НТ",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "perimeter_variant_code": "o1_without_nt",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 1,
        },
        {
            "entity_kind": "union_energy_system",
            "entity_label": "ОЭС Центра",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 1,
        },
    ]

    filtered = service.exclude_centralized_zone_russia_non_o1_summary_rows(rows)

    codes = [
        r.get("perimeter_variant_code") for r in filtered if r.get("show_entity_cell")
    ]
    assert codes == ["o1_with_nt", "o1_without_nt", None]
    assert filtered[0]["entity_rowspan"] == 2
    assert filtered[1]["show_entity_cell"] is False


def test_mark_centralized_zone_without_nt_rows_skip_empty_hide_includes_o1_variant():
    rows = [
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России без НТ",
            "perimeter_variant_code": "without_nt",
            "pd_ec_nt_without_row": True,
        },
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России без НТ",
            "perimeter_variant_code": "o1_without_nt",
            "pd_ec_nt_without_row": True,
            "pd_ec_o1_form_row": True,
        },
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России с НТ",
            "perimeter_variant_code": "o1_with_nt",
            "pd_ec_nt_extra_row": True,
            "pd_ec_o1_form_row": True,
        },
    ]

    service._mark_centralized_zone_without_nt_rows_skip_empty_hide(rows)

    assert rows[0].get("pd_ec_skip_empty_hide_row") is True
    assert rows[1].get("pd_ec_skip_empty_hide_row") is True
    assert "pd_ec_skip_empty_hide_row" not in rows[2]


def test_apply_variant_toggle_rows_marks_cz_o1_without_nt_skip_empty_hide():
    rows = [
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "perimeter_variant_code": "o1_without_nt",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
    ]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)

    assert rows[0].get("pd_ec_nt_without_row") is True
    assert rows[0].get("pd_ec_skip_empty_hide_row") is True


def test_apply_variant_toggle_rows_hides_non_o1_when_entity_has_o1_variants():
    rows = [
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "parent_fk_column": None,
            "parent_id": None,
            "perimeter_variant_code": "with_nt",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "parent_fk_column": None,
            "parent_id": None,
            "perimeter_variant_code": "o1_with_nt",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "parent_fk_column": None,
            "parent_id": None,
            "perimeter_variant_code": "o1_without_nt",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
    ]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)

    assert rows[0].get("pd_ec_hide_when_isolated_eu_on") is True
    assert "pd_ec_hide_when_isolated_eu_on" not in rows[1]
    assert "pd_ec_hide_when_isolated_eu_on" not in rows[2]


def test_apply_variant_toggle_rows_keeps_null_base_when_entity_has_o1():
    """Базовая строка без варианта не скрывается кнопкой «Форма О-1» — O-1 добавляется к ней."""
    rows = [
        {
            "entity_label": "ЭС Камчатского края",
            "demand_model_name": "RegionalEnergySystemEnergyConsumptionParameter",
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 601,
            "perimeter_variant_code": None,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "ЭС Камчатского края",
            "demand_model_name": "RegionalEnergySystemEnergyConsumptionParameter",
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 601,
            "perimeter_variant_code": "o1",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "pd_ec_o1_form_row": True,
        },
    ]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)

    assert "pd_ec_hide_when_isolated_eu_on" not in rows[0]
    assert "pd_ec_hide_when_isolated_eu_on" not in rows[1]


def _ues_component_row(
    *,
    label: str,
    values: list[str],
    variant: str = service.CODE_WITH_NT_WITH_GAES,
) -> dict:
    return {
        "entity_label": label,
        "entity_depth": 0,
        "entity_kind": "union_energy_system",
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "demand_model_name": "UnionEnergySystemEnergyConsumptionParameter",
        "perimeter_variant_code": variant,
        "year_values": list(values),
    }


def test_apply_centralized_zone_with_nt_sum_formula():
    years = [2024]
    rows = [
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России с НТ",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "perimeter_variant_code": service.CODE_WITH_NT,
            "pd_ec_nt_extra_row": True,
            "year_values": ["0"],
        },
        _ues_component_row(label="ОЭС Северо-Запада", values=["10"]),
        _ues_component_row(label="ОЭС Центра с зарядом ГАЭС", values=["20"]),
        _ues_component_row(label="ОЭС Средней Волги", values=["30"]),
        _ues_component_row(label="ОЭС Юга с НТ с зарядом ГАЭС", values=["40"]),
        _ues_component_row(label="ОЭС Урала", values=["50"]),
        {
            "entity_label": "Энергозона Сибири",
            "entity_depth": 0,
            "entity_kind": "formula",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "year_values": ["60"],
        },
        {
            "entity_label": "Энергозона Востока",
            "entity_depth": 0,
            "entity_kind": "formula",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "year_values": ["70"],
        },
    ]

    service.apply_centralized_zone_with_nt_sum_formula(rows, years, rounding_digits=1)

    cz_row = rows[0]
    assert cz_row["year_values"] == ["280"]
    assert cz_row.get("pd_ec_formula_derived_row") is True
    assert service._CZ_RUSSIA_WITH_NT_FORMULA_TOOLTIP in str(
        cz_row.get("pd_ec_summary_row_formula_tooltip") or ""
    )


def test_apply_centralized_zone_with_nt_sum_formula_uses_shallowest_ues_depth():
    """На /summary-table/ строки ОЭС имеют entity_depth=1, не 0."""
    years = [2024]
    rows = [
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России с НТ",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "perimeter_variant_code": service.CODE_WITH_NT,
            "pd_ec_nt_extra_row": True,
            "year_values": ["0"],
        },
        _ues_component_row(label="ОЭС Северо-Запада", values=["10"]),
        {
            **_ues_component_row(label="ОЭС Северо-Запада", values=["999"]),
            "entity_depth": 2,
            "entity_kind": "regional_energy_system",
        },
        _ues_component_row(label="ОЭС Центра с зарядом ГАЭС", values=["20"]),
        _ues_component_row(label="ОЭС Средней Волги", values=["30"]),
        _ues_component_row(label="ОЭС Юга с НТ с зарядом ГАЭС", values=["40"]),
        _ues_component_row(label="ОЭС Урала", values=["50"]),
        {
            "entity_label": "Энергозона Сибири",
            "entity_depth": 0,
            "entity_kind": "formula",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "year_values": ["60"],
        },
        {
            "entity_label": "Энергозона Востока",
            "entity_depth": 0,
            "entity_kind": "formula",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "year_values": ["70"],
        },
    ]
    for row in rows[1:8]:
        if row.get("demand_model_name") == "UnionEnergySystemEnergyConsumptionParameter":
            row["entity_depth"] = 1

    service.apply_centralized_zone_with_nt_sum_formula(rows, years, rounding_digits=1)

    assert rows[0]["year_values"] == ["280"]


def test_apply_centralized_zone_with_nt_sum_formula_skips_o1_with_nt_row():
    years = [2024]
    rows = [
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России с НТ",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "perimeter_variant_code": "o1_with_nt",
            "pd_ec_nt_extra_row": True,
            "pd_ec_o1_form_row": True,
            "year_values": ["99"],
        },
        _ues_component_row(label="ОЭС Северо-Запада", values=["10"]),
    ]

    service.apply_centralized_zone_with_nt_sum_formula(rows, years, rounding_digits=1)

    o1_row = rows[0]
    assert o1_row["year_values"] == ["99"]
    assert o1_row.get("pd_ec_cz_o1_manual_row") is True
    assert o1_row.get("pd_ec_cz_o1_with_nt_manual_row") is True
    assert "pd_ec_formula_derived_row" not in o1_row
    assert "pd_ec_summary_row_formula_tooltip" not in o1_row


def test_apply_centralized_zone_without_nt_sum_formula():
    years = [2021, 2022, 2025]
    rows = [
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России без НТ",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "perimeter_variant_code": service.CODE_WITHOUT_NT,
            "pd_ec_nt_without_row": True,
            "year_values": ["100", "200", "0"],
        },
        _ues_component_row(
            label="ОЭС Северо-Запада",
            values=["1", "10", "100"],
            variant=service.CODE_WITHOUT_NT,
        ),
        _ues_component_row(
            label="ОЭС Центра с зарядом ГАЭС",
            values=["2", "20", "200"],
            variant=service.CODE_WITHOUT_NT_WITH_GAES,
        ),
        _ues_component_row(
            label="ОЭС Средней Волги",
            values=["3", "30", "300"],
            variant=service.CODE_WITHOUT_NT,
        ),
        _ues_component_row(
            label="ОЭС Юга без НТ с зарядом ГАЭС",
            values=["4", "40", "400"],
            variant=service.CODE_WITHOUT_NT_WITH_GAES,
        ),
        _ues_component_row(
            label="ОЭС Урала",
            values=["5", "50", "500"],
            variant=service.CODE_WITHOUT_NT,
        ),
        {
            "entity_label": "Энергозона Сибири",
            "entity_depth": 0,
            "entity_kind": "formula",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "year_values": ["6", "60", "600"],
        },
        {
            "entity_label": "Энергозона Востока",
            "entity_depth": 0,
            "entity_kind": "formula",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "year_values": ["7", "70", "700"],
        },
    ]

    service.apply_centralized_zone_without_nt_sum_formula(rows, years, rounding_digits=1)

    cz_row = rows[0]
    # В БД уже есть значения — формула не перезаписывает, строка остаётся редактируемой.
    assert cz_row["year_values"] == ["100", "200", "0"]
    assert cz_row.get("pd_ec_formula_derived_row") is not True
    assert service._CZ_RUSSIA_WITHOUT_NT_FORMULA_TOOLTIP in str(
        cz_row.get("pd_ec_summary_row_formula_tooltip") or ""
    )


def test_apply_centralized_zone_without_nt_sum_formula_fills_empty_row():
    years = [2021, 2022, 2025]
    rows = [
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России без НТ",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "perimeter_variant_code": service.CODE_WITHOUT_NT,
            "pd_ec_nt_without_row": True,
            "year_values": ["—", "—", "—"],
        },
        _ues_component_row(
            label="ОЭС Северо-Запада",
            values=["1", "10", "100"],
            variant=service.CODE_WITHOUT_NT,
        ),
        _ues_component_row(
            label="ОЭС Центра с зарядом ГАЭС",
            values=["2", "20", "200"],
            variant=service.CODE_WITHOUT_NT_WITH_GAES,
        ),
        _ues_component_row(
            label="ОЭС Средней Волги",
            values=["3", "30", "300"],
            variant=service.CODE_WITHOUT_NT,
        ),
        _ues_component_row(
            label="ОЭС Юга без НТ с зарядом ГАЭС",
            values=["4", "40", "400"],
            variant=service.CODE_WITHOUT_NT_WITH_GAES,
        ),
        _ues_component_row(
            label="ОЭС Урала",
            values=["5", "50", "500"],
            variant=service.CODE_WITHOUT_NT,
        ),
        {
            "entity_label": "Энергозона Сибири",
            "entity_depth": 0,
            "entity_kind": "formula",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "year_values": ["6", "60", "600"],
        },
        {
            "entity_label": service._EAST_ENERGY_ZONE_LABEL,
            "entity_depth": 0,
            "entity_kind": "formula",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "year_values": ["7", "70", "700"],
        },
    ]

    service.apply_centralized_zone_without_nt_sum_formula(rows, years, rounding_digits=1)

    cz_row = rows[0]
    assert cz_row["year_values"] == ["—", "280", "2 800"]
    assert cz_row.get("pd_ec_formula_derived_row") is not True
    assert service._CZ_RUSSIA_WITHOUT_NT_FORMULA_TOOLTIP in str(
        cz_row.get("pd_ec_summary_row_formula_tooltip") or ""
    )


def test_apply_centralized_zone_without_nt_sum_formula_skips_o1_without_nt_row():
    years = [2025]
    rows = [
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России без НТ",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "perimeter_variant_code": "o1_without_nt",
            "pd_ec_nt_without_row": True,
            "year_values": ["77"],
        },
        _ues_component_row(label="ОЭС Северо-Запада", values=["10"]),
    ]

    service.apply_centralized_zone_without_nt_sum_formula(rows, years, rounding_digits=1)

    o1_row = rows[0]
    assert o1_row["year_values"] == ["77"]


def test_apply_federal_district_centralized_zone_values_from_summary_table_hub(monkeypatch):
    years = [2024, 2025]

    def _reference_rows(*_args, **_kwargs):
        return [
            {
                "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
                "entity_label": "ЦЗ России с НТ",
                "perimeter_variant_code": "with_nt",
                "parameter_key": "energy_consumption_mln_kvt_ch",
                "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
                "year_values": ["100.0", "110.0"],
                "pd_ec_formula_derived_row": True,
                "pd_ec_summary_row_formula_tooltip": service._CZ_RUSSIA_WITH_NT_FORMULA_TOOLTIP,
            },
            {
                "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
                "entity_label": "ЦЗ России без НТ О-1",
                "perimeter_variant_code": "o1_without_nt",
                "parameter_key": "energy_consumption_mln_kvt_ch",
                "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
                "year_values": ["50.0", "55.0"],
            },
        ]

    monkeypatch.setattr(
        service,
        "build_summary_table_hub_centralized_zone_reference_summary_rows",
        _reference_rows,
    )

    target_rows = [
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России с НТ",
            "perimeter_variant_code": "with_nt",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "year_values": ["1.0", "2.0"],
        },
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России без НТ О-1",
            "perimeter_variant_code": "o1_without_nt",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
            "year_values": ["3.0", "4.0"],
        },
    ]
    service.apply_federal_district_centralized_zone_values_from_summary_table_hub(
        target_rows,
        years=years,
        rounding_digits=1,
        start_year=2024,
        end_year=2025,
        filter_year_list=years,
    )

    assert target_rows[0]["year_values"] == ["100.0", "110.0"]
    assert target_rows[0].get("pd_ec_formula_derived_row") is True
    assert target_rows[1]["year_values"] == ["50.0", "55.0"]


def _cz_russia_nt_pair_rows_for_reference_test(*, years: list[int]) -> list[dict]:
    n = len(years)
    dash = ["—"] * n

    def _cz_block(label: str, *, with_nt: bool, ec_values: list[str], sipr_values: list[str]) -> list[dict]:
        code = service.CODE_WITH_NT if with_nt else service.CODE_WITHOUT_NT
        flags = (
            {"pd_ec_nt_extra_row": True}
            if with_nt
            else {"pd_ec_nt_without_row": True}
        )
        return [
            {
                "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
                "entity_label": label,
                "entity_depth": 0,
                "entity_rowspan": 5,
                "show_entity_cell": True,
                "parameter_key": "energy_consumption_mln_kvt_ch",
                "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
                "perimeter_variant_code": code,
                "year_values": list(ec_values),
                **flags,
            },
            {
                "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
                "entity_label": label,
                "entity_depth": 0,
                "show_entity_cell": False,
                "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
                "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
                "perimeter_variant_code": code,
                "year_values": list(sipr_values),
                **flags,
            },
            {
                "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
                "entity_label": label,
                "entity_depth": 0,
                "show_entity_cell": False,
                "parameter_key": service.ENERGY_CONSUMPTION_YOY_PARAMETER_KEY,
                "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
                "perimeter_variant_code": code,
                "year_values": list(dash),
                **flags,
            },
            {
                "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
                "entity_label": label,
                "entity_depth": 0,
                "show_entity_cell": False,
                "parameter_key": service.ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
                "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
                "perimeter_variant_code": code,
                "year_values": list(dash),
                **flags,
            },
            {
                "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
                "entity_label": label,
                "entity_depth": 0,
                "show_entity_cell": False,
                "parameter_key": service.ENERGY_CONSUMPTION_SIPR_YOY_PARAMETER_KEY,
                "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
                "perimeter_variant_code": code,
                "year_values": list(dash),
                **flags,
            },
        ]

    russia_block = [
        {
            "entity_kind": service.ENTITY_KIND_RUSSIA_FEDERATION,
            "entity_label": "Россия с НТ",
            "entity_depth": 0,
            "entity_rowspan": 1,
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "RussiaFederationEnergyConsumptionParameter",
            "perimeter_variant_code": service.CODE_WITH_NT,
            "year_values": ["0"],
        },
    ]
    return (
        _cz_block(
            "ЦЗ России с НТ",
            with_nt=True,
            ec_values=["300", "320", "340"],
            sipr_values=["30", "32", "34"],
        )
        + _cz_block(
            "ЦЗ России без НТ",
            with_nt=False,
            ec_values=["250", "270", "290"],
            sipr_values=["25", "27", "29"],
        )
        + russia_block
    )


def test_inject_summary_table_cz_new_territories_reference_row_after_cz():
    years = [2023, 2024, 2025]
    rows = _cz_russia_nt_pair_rows_for_reference_test(years=years)

    service.inject_summary_table_cz_new_territories_reference_row(rows, years, rounding_digits=1)

    ref_start = next(
        index
        for index, row in enumerate(rows)
        if row.get("show_entity_cell")
        and row.get("entity_label") == service._SUMMARY_TABLE_CZ_NT_REFERENCE_LABEL
    )
    last_cz_idx = max(
        index
        for index, row in enumerate(rows)
        if service._is_centralized_zone_russia_summary_row(row)
    )
    russia_start = next(
        index
        for index, row in enumerate(rows)
        if row.get("show_entity_cell")
        and row.get("entity_kind") == service.ENTITY_KIND_RUSSIA_FEDERATION
    )
    # CZ … → СПРАВОЧНО → Россия (как на /summary_table/).
    assert last_cz_idx < ref_start < russia_start

    ref_ec = next(
        row
        for row in rows
        if row.get("entity_label") == service._SUMMARY_TABLE_CZ_NT_REFERENCE_LABEL
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    )
    assert ref_ec["year_values"] == ["—", "50", "50"]
    assert service._SUMMARY_TABLE_CZ_NT_REFERENCE_FORMULA_TOOLTIP in str(
        ref_ec.get("pd_ec_summary_row_formula_tooltip") or ""
    )
    assert ref_ec.get("pd_ec_entity_label_compact_nt_gaes") == (
        service._SUMMARY_TABLE_CZ_NT_REFERENCE_LABEL
    )
    assert ref_ec.get("pd_ec_nt_extra_row") is True
    assert ref_ec.get("pd_ec_formula_text_key") == "summary_table_cz_nt_reference"
    assert ref_ec.get("pd_ec_summary_row_formula_tooltip")
    assert ref_ec.get("pd_ec_cz_o1_manual_row") is None
    assert ref_ec.get("pd_ec_cz_o1_with_nt_manual_row") is None
    assert ref_ec.get("show_perimeter_variant_select") is not True
    assert ref_ec.get("perimeter_variant_code") is None

    ref_sipr = next(
        row
        for row in rows
        if row.get("entity_label") == service._SUMMARY_TABLE_CZ_NT_REFERENCE_LABEL
        and row.get("parameter_key") == "energy_consumption_sipr_mln_kvt_ch"
    )
    assert ref_sipr["year_values"] == ["—", "5", "5"]
    assert ref_sipr.get("pd_ec_nt_extra_row") is True


def test_inject_summary_table_cz_new_territories_reference_row_after_cz_when_russia_first():
    """На /summary/oes|fo|ez порядок «Россия → ЦЗ …»: справочная строка всё равно после ЦЗ."""
    years = [2024]
    cz_then_russia = _cz_russia_nt_pair_rows_for_reference_test(years=years)
    russia_rows = [
        row
        for row in cz_then_russia
        if row.get("entity_kind") == service.ENTITY_KIND_RUSSIA_FEDERATION
    ]
    cz_rows = [
        row
        for row in cz_then_russia
        if service._is_centralized_zone_russia_summary_row(row)
    ]
    rows = russia_rows + cz_rows

    service.inject_summary_table_cz_new_territories_reference_row(rows, years, rounding_digits=1)

    kinds = [
        row.get("entity_kind")
        for row in rows
        if row.get("show_entity_cell")
    ]
    assert kinds == [
        service.ENTITY_KIND_RUSSIA_FEDERATION,
        service.ENTITY_KIND_CENTRALIZED_ZONE,
        service.ENTITY_KIND_CENTRALIZED_ZONE,
        "summary_table_cz_nt_reference",
    ]


def test_inject_summary_table_cz_new_territories_reference_row_is_idempotent():
    years = [2024]
    rows = _cz_russia_nt_pair_rows_for_reference_test(years=years)
    service.inject_summary_table_cz_new_territories_reference_row(rows, years, rounding_digits=1)
    count_first = sum(
        1
        for row in rows
        if row.get("entity_label") == service._SUMMARY_TABLE_CZ_NT_REFERENCE_LABEL
        and row.get("show_entity_cell")
    )
    service.inject_summary_table_cz_new_territories_reference_row(rows, years, rounding_digits=1)
    count_second = sum(
        1
        for row in rows
        if row.get("entity_label") == service._SUMMARY_TABLE_CZ_NT_REFERENCE_LABEL
        and row.get("show_entity_cell")
    )
    assert count_first == 1
    assert count_second == 1


def test_inject_summary_table_cz_new_territories_reference_row_from_o1_variants():
    """После exclude non-O1 источником остаются только О-1 с/без НТ."""
    years = [2023, 2024, 2025]
    rows = _cz_russia_nt_pair_rows_for_reference_test(years=years)
    for row in rows:
        if not service._is_centralized_zone_russia_summary_row(row):
            continue
        code = str(row.get("perimeter_variant_code") or "")
        if code == service.CODE_WITH_NT:
            row["perimeter_variant_code"] = service.CODE_O1_WITH_NT
            row["pd_ec_cz_o1_manual_row"] = True
            row["pd_ec_cz_o1_with_nt_manual_row"] = True
        elif code == service.CODE_WITHOUT_NT:
            row["perimeter_variant_code"] = service.CODE_O1_WITHOUT_NT
            row["pd_ec_cz_o1_manual_row"] = True
            row["pd_ec_cz_o1_with_nt_manual_row"] = True

    service.inject_summary_table_cz_new_territories_reference_row(rows, years, rounding_digits=1)

    ref_ec = next(
        row
        for row in rows
        if row.get("entity_label") == service._SUMMARY_TABLE_CZ_NT_REFERENCE_LABEL
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    )
    assert ref_ec["year_values"] == ["—", "50", "50"]
    assert ref_ec.get("pd_ec_nt_extra_row") is True
    assert ref_ec.get("pd_ec_formula_text_key") == "summary_table_cz_nt_reference"
    assert ref_ec.get("pd_ec_summary_row_formula_tooltip")
    assert ref_ec.get("pd_ec_cz_o1_with_nt_manual_row") is None


def _russia_and_ees_rows_for_decentralized_zone_test(*, years: list[int]) -> list[dict]:
    dash = ["—" for _ in years]
    label_with_nt = "Россия с НТ"
    russia_rows: list[dict] = []
    for idx, (parameter_key, _) in enumerate(service.PARAMETERS_ENERGY_CONSUMPTION):
        values = (
            ["1", "2", "3"]
            if parameter_key == "energy_consumption_mln_kvt_ch"
            else (
                ["0.1", "0.2", "0.3"]
                if parameter_key == "energy_consumption_sipr_mln_kvt_ch"
                else list(dash)
            )
        )
        russia_rows.append(
            {
                "entity_kind": service.ENTITY_KIND_RUSSIA_FEDERATION,
                "entity_label": label_with_nt,
                "entity_depth": 0,
                "entity_rowspan": len(service.PARAMETERS_ENERGY_CONSUMPTION),
                "show_entity_cell": idx == 0,
                "parameter_key": parameter_key,
                "demand_model_name": "RussiaFederationEnergyConsumptionParameter",
                "perimeter_variant_code": service.CODE_WITH_NT,
                "pd_ec_skip_perimeter_variant_year_bounds": True,
                "year_values": values,
            }
        )
    russia_rows.append(
        {
            "entity_kind": service.ENTITY_KIND_RUSSIA_FEDERATION,
            "entity_label": service._SUMMARY_TABLE_RUSSIA_GAES_CHARGE_ENTITY_LABEL,
            "entity_depth": 0,
            "entity_rowspan": 1,
            "show_entity_cell": True,
            "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
            "demand_model_name": "RussiaFederationEnergyConsumptionParameter",
            "perimeter_variant_code": service.CODE_WITH_NT,
            "year_values": ["10", "20", "30"],
        }
    )

    def _ees_ec_row(values: list[str]) -> dict:
        return {
            "entity_kind": service.ENTITY_KIND_EES_RUSSIA,
            "entity_label": "ЕЭС России",
            "entity_depth": 0,
            "entity_rowspan": 1,
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "EesRussiaEnergyConsumptionParameter",
            "perimeter_variant_code": service.CODE_WITHOUT_NT_WITH_GAES,
            "year_values": values,
        }

    return russia_rows + [
        _ees_ec_row(["100", "200", "300"]),
        {
            "entity_kind": service.ENTITY_KIND_EES_RUSSIA,
            "entity_label": "ЕЭС России",
            "entity_depth": 0,
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": "EesRussiaEnergyConsumptionParameter",
            "perimeter_variant_code": service.CODE_WITHOUT_NT_WITH_GAES,
            "year_values": ["10", "20", "30"],
        },
    ]


def test_inject_summary_table_decentralized_zone_row_after_russia():
    years = [2020, 2021, 2022]
    rows = _russia_and_ees_rows_for_decentralized_zone_test(years=years)

    service.inject_summary_table_decentralized_zone_row(rows, years, rounding_digits=1)

    gaes_start = next(
        index
        for index, row in enumerate(rows)
        if row.get("entity_label") == service._SUMMARY_TABLE_RUSSIA_GAES_CHARGE_ENTITY_LABEL
        and row.get("show_entity_cell")
    )
    dz_start = next(
        index
        for index, row in enumerate(rows)
        if row.get("show_entity_cell")
        and row.get("entity_label") == service._SUMMARY_TABLE_DECENTRALIZED_ZONE_LABEL
    )
    assert dz_start < gaes_start
    assert rows[dz_start - 1].get("entity_label") == "Россия с НТ"

    dz_ec = next(
        row
        for row in rows
        if row.get("entity_label") == service._SUMMARY_TABLE_DECENTRALIZED_ZONE_LABEL
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    )
    assert dz_ec["year_values"] == ["900", "1 800", "2 700"]
    dz_sipr = next(
        row
        for row in rows
        if row.get("entity_label") == service._SUMMARY_TABLE_DECENTRALIZED_ZONE_LABEL
        and row.get("parameter_key") == "energy_consumption_sipr_mln_kvt_ch"
    )
    assert dz_sipr["year_values"] == ["90", "180", "270"]
    assert dz_ec.get("pd_ec_formula_text_key") == "summary_table_decentralized_zone"
    assert service._SUMMARY_TABLE_DECENTRALIZED_ZONE_FORMULA_TOOLTIP in str(
        dz_ec.get("pd_ec_summary_row_formula_tooltip") or ""
    )
    for compact_key in (
        "pd_ec_entity_label_compact",
        "pd_ec_entity_label_compact_nt",
        "pd_ec_entity_label_compact_nt_gaes",
    ):
        assert dz_ec[compact_key] == service._SUMMARY_TABLE_DECENTRALIZED_ZONE_LABEL
    assert service.export_entity_label_for_summary_row(
        dz_ec,
        service.EnergyConsumptionExportUiOptions(nt_detail_on=False, gaes_detail_on=True),
    ) == service._SUMMARY_TABLE_DECENTRALIZED_ZONE_LABEL


def test_inject_summary_table_decentralized_zone_row_is_idempotent():
    years = [2020]
    rows = _russia_and_ees_rows_for_decentralized_zone_test(years=years)
    service.inject_summary_table_decentralized_zone_row(rows, years, rounding_digits=1)
    count_first = sum(
        1
        for row in rows
        if row.get("entity_label") == service._SUMMARY_TABLE_DECENTRALIZED_ZONE_LABEL
        and row.get("show_entity_cell")
    )
    service.inject_summary_table_decentralized_zone_row(rows, years, rounding_digits=1)
    count_second = sum(
        1
        for row in rows
        if row.get("entity_label") == service._SUMMARY_TABLE_DECENTRALIZED_ZONE_LABEL
        and row.get("show_entity_cell")
    )
    assert count_first == 1
    assert count_second == 1


def test_inject_oes_summary_verification_rows_adds_res_subject_check_for_multi_subject_res():
    ues_model = "UnionEnergySystemEnergyConsumptionParameter"
    res_model = "RegionalEnergySystemEnergyConsumptionParameter"
    rd_model = "RegionalDistrictEnergyConsumptionParameter"
    rows = [
        {
            "entity_label": "ОЭС Центра",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 117,
            "year_values": ["1000.0"],
        },
        {
            "entity_label": "ЭС г. Москвы и Московской области",
            "entity_rowspan": 2,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 580,
            "year_values": ["100.0"],
        },
        {
            "entity_label": "ЭС г. Москвы и Московской области",
            "entity_rowspan": 2,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 580,
            "year_values": ["90.0"],
        },
        {
            "entity_label": "г. Москва",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 667,
            "year_values": ["40.0"],
        },
        {
            "entity_label": "г. Москва",
            "entity_rowspan":  2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 667,
            "year_values": ["35.0"],
        },
        {
            "entity_label": "Московская область",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 668,
            "year_values": ["55.0"],
        },
        {
            "entity_label": "Московская область",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 668,
            "year_values": ["50.0"],
        },
    ]
    source_rows = list(rows)

    service.inject_oes_summary_verification_rows(
        rows,
        source_rows=source_rows,
        years=[2024],
        rounding_digits=1,
    )

    res_checks = [
        row
        for row in rows
        if row.get("entity_kind") == "res_subject_sum_check"
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    ]
    assert len(res_checks) == 1
    assert res_checks[0]["entity_label"] == "Проверка для ЭС г. Москвы и Московской области"
    assert res_checks[0]["year_values"] == ["5"]

    labels = [str(row.get("entity_label") or "") for row in rows if row.get("show_entity_cell")]
    assert labels.index("ЭС г. Москвы и Московской области") < labels.index(
        "Проверка для ЭС г. Москвы и Московской области"
    )
    assert labels.index("Проверка для ЭС г. Москвы и Московской области") < labels.index(
        "г. Москва"
    )


def test_inject_oes_summary_verification_rows_places_each_res_check_after_its_res():
    """Проверки РЭС идут сразу после своего РЭС, а не в конце поддерева ОЭС."""
    ues_model = "UnionEnergySystemEnergyConsumptionParameter"
    res_model = "RegionalEnergySystemEnergyConsumptionParameter"
    rd_model = "RegionalDistrictEnergyConsumptionParameter"
    rows = [
        {
            "entity_label": "ОЭС Северо-Запада",
            "entity_rowspan": 2,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 120,
            "year_values": ["1000.0"],
        },
        {
            "entity_label": "ОЭС Северо-Запада",
            "entity_rowspan": 2,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 120,
            "year_values": ["900.0"],
        },
        {
            "entity_label": "ЭС Архангельской области и Ненецкого АО",
            "entity_rowspan": 2,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 501,
            "id_union_energy_system": 120,
            "year_values": ["100.0"],
        },
        {
            "entity_label": "ЭС Архангельской области и Ненецкого АО",
            "entity_rowspan": 2,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 501,
            "id_union_energy_system": 120,
            "year_values": ["90.0"],
        },
        {
            "entity_label": "Архангельская область",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 701,
            "year_values": ["60.0"],
        },
        {
            "entity_label": "Архангельская область",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 701,
            "year_values": ["55.0"],
        },
        {
            "entity_label": "Ненецкий АО",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 702,
            "year_values": ["40.0"],
        },
        {
            "entity_label": "Ненецкий АО",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 702,
            "year_values": ["35.0"],
        },
        {
            "entity_label": "ЭС Калининградской области",
            "entity_rowspan": 2,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 502,
            "id_union_energy_system": 120,
            "year_values": ["50.0"],
        },
        {
            "entity_label": "ЭС Калининградской области",
            "entity_rowspan": 2,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 502,
            "id_union_energy_system": 120,
            "year_values": ["45.0"],
        },
        {
            "entity_label": "ЭС г. Москвы и Московской области",
            "entity_rowspan": 2,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 580,
            "id_union_energy_system": 120,
            "year_values": ["200.0"],
        },
        {
            "entity_label": "ЭС г. Москвы и Московской области",
            "entity_rowspan": 2,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 580,
            "id_union_energy_system": 120,
            "year_values": ["180.0"],
        },
        {
            "entity_label": "г. Москва",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 667,
            "year_values": ["80.0"],
        },
        {
            "entity_label": "г. Москва",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 667,
            "year_values": ["70.0"],
        },
        {
            "entity_label": "Московская область",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 668,
            "year_values": ["120.0"],
        },
        {
            "entity_label": "Московская область",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 668,
            "year_values": ["110.0"],
        },
    ]
    source_rows = list(rows)

    service.inject_oes_summary_verification_rows(
        rows,
        source_rows=source_rows,
        years=[2024],
        rounding_digits=1,
    )

    labels = [str(row.get("entity_label") or "") for row in rows if row.get("show_entity_cell")]
    arkhangelsk_res = "ЭС Архангельской области и Ненецкого АО"
    arkhangelsk_check = "Проверка для ЭС Архангельской области и Ненецкого АО"
    moscow_res = "ЭС г. Москвы и Московской области"
    moscow_check = "Проверка для ЭС г. Москвы и Московской области"

    assert arkhangelsk_check in labels
    assert moscow_check in labels
    assert labels.index(arkhangelsk_res) < labels.index(arkhangelsk_check)
    assert labels.index(arkhangelsk_check) < labels.index("Архангельская область")
    assert labels.index(arkhangelsk_check) < labels.index("ЭС Калининградской области")
    assert labels.index(moscow_res) < labels.index(moscow_check)
    assert labels.index(moscow_check) < labels.index("г. Москва")
    # Проверки не сгруппированы в конце поддерева ОЭС.
    assert labels.index(arkhangelsk_check) < labels.index(moscow_res)


def test_inject_south_ues_new_territories_places_check_after_nt_aggregate(monkeypatch):
    """«Проверка для Новых территорий» — сразу после «Новые территории», до субъектов."""
    ues_model = "UnionEnergySystemEnergyConsumptionParameter"
    rd_model = "RegionalDistrictEnergyConsumptionParameter"
    south_ues_id = 7
    rows = [
        {
            "entity_label": "ОЭС Юга",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": south_ues_id,
            "id_union_energy_system": south_ues_id,
            "year_values": ["1000.0"],
        },
        {
            "entity_label": "ОЭС Центра",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 117,
            "id_union_energy_system": 117,
            "year_values": ["2000.0"],
        },
        {
            "entity_label": "ОЭС Новые территории",
            "entity_rowspan": 2,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 99,
            "perimeter_variant_code": None,
            "year_values": ["100.0"],
        },
        {
            "entity_label": "ОЭС Новые территории",
            "entity_rowspan": 2,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 99,
            "perimeter_variant_code": None,
            "year_values": ["90.0"],
        },
    ]
    nt_rows = [
        {
            "entity_label": "Новые территории",
            "entity_rowspan": 2,
            "entity_depth": 2,
            "entity_kind": "fo_nt_under_south",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 99,
            "year_values": ["100.0"],
        },
        {
            "entity_label": "Новые территории",
            "entity_rowspan": 2,
            "entity_depth": 2,
            "entity_kind": "fo_nt_under_south",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 99,
            "year_values": ["90.0"],
        },
        {
            "entity_label": "ДНР",
            "entity_rowspan": 1,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 801,
            "pd_ec_nt_under_south_detail_row": True,
            "year_values": ["40.0"],
        },
        {
            "entity_label": "ЛНР",
            "entity_rowspan": 1,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 802,
            "pd_ec_nt_under_south_detail_row": True,
            "year_values": ["60.0"],
        },
    ]

    monkeypatch.setattr(service, "south_ues_base_tree_includes_new_territories", lambda _years: True)
    monkeypatch.setattr(
        service,
        "_resolve_union_energy_system_id_by_name_cf",
        lambda name_cf: south_ues_id if name_cf == service.SOUTH_UES_NAME_CF else None,
    )
    monkeypatch.setattr(
        service,
        "_build_new_territories_subjects_summary_rows",
        lambda **_kwargs: list(nt_rows),
    )
    monkeypatch.setattr(service, "_resolve_new_territories_union_energy_system_id", lambda: 99)

    service.inject_south_ues_new_territories_summary_rows(
        rows,
        years=[2024],
        rounding_digits=1,
    )

    labels = [str(row.get("entity_label") or "") for row in rows if row.get("show_entity_cell")]
    assert "Новые территории" in labels
    assert "Проверка для Новых территорий" in labels
    assert labels.index("Новые территории") < labels.index("Проверка для Новых территорий")
    assert labels.index("Проверка для Новых территорий") < labels.index("ДНР")
    assert labels.index("Проверка для Новых территорий") < labels.index("ЛНР")


def test_inject_oes_summary_verification_rows_places_nt_check_after_new_territories(
    monkeypatch,
):
    """Фоллбек-инжект проверки НТ ставит её сразу после «Новые территории»."""
    ues_model = "UnionEnergySystemEnergyConsumptionParameter"
    rows = [
        {
            "entity_label": "ОЭС Юга",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 7,
            "perimeter_variant_code": service.CODE_WITH_NT_WITH_GAES,
            "year_values": ["110.0"],
        },
        {
            "entity_label": "ОЭС Юга",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 7,
            "perimeter_variant_code": service.CODE_WITH_NT_WITH_GAES,
            "year_values": ["100.0"],
        },
        {
            "entity_label": "ОЭС Юга",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 7,
            "perimeter_variant_code": service.CODE_WITHOUT_NT_WITH_GAES,
            "year_values": ["80.0"],
        },
        {
            "entity_label": "ОЭС Юга",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 7,
            "perimeter_variant_code": service.CODE_WITHOUT_NT_WITH_GAES,
            "year_values": ["70.0"],
        },
        {
            "entity_label": "Новые территории",
            "entity_rowspan": 1,
            "entity_depth": 2,
            "entity_kind": "fo_nt_under_south",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 99,
            "year_values": ["25.0"],
        },
        {
            "entity_label": "ДНР",
            "entity_rowspan": 1,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "year_values": ["10.0"],
        },
        {
            "entity_label": "ОЭС Новые территории",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 99,
            "year_values": ["25.0"],
        },
    ]
    monkeypatch.setattr(
        service,
        "_new_territories_parameter_year_values",
        lambda years, parameter_key: {2024: Decimal("20.0")},
    )
    monkeypatch.setattr(
        service,
        "_year_values_from_parent_demand_rows",
        lambda *_args, **_kwargs: {2024: None},
    )

    service.inject_oes_summary_verification_rows(
        rows,
        source_rows=list(rows),
        years=[2024],
        rounding_digits=1,
    )

    labels = [str(row.get("entity_label") or "") for row in rows if row.get("show_entity_cell")]
    assert "Проверка для Новых территорий" in labels
    assert labels.index("Новые территории") < labels.index("Проверка для Новых территорий")
    assert labels.index("Проверка для Новых территорий") < labels.index("ДНР")


def test_inject_oes_summary_verification_rows_adds_tites_res_energy_unit_check():
    tites_ues_id = 901
    ues_model = "UnionEnergySystemEnergyConsumptionParameter"
    res_model = "RegionalEnergySystemEnergyConsumptionParameter"
    eu_model = "EnergyUnitEnergyConsumptionParameter"
    res_id = 580
    rows = [
        {
            "entity_label": "ТИТЭС Востока",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": tites_ues_id,
            "year_values": ["1000.0"],
        },
        {
            "entity_label": "ЭС примера",
            "entity_rowspan": 2,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": res_id,
            "id_union_energy_system": tites_ues_id,
            "year_values": ["100.0"],
        },
        {
            "entity_label": "ЭС примера",
            "entity_rowspan": 2,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": res_id,
            "id_union_energy_system": tites_ues_id,
            "year_values": ["90.0"],
        },
        {
            "entity_label": "Энергорайон 1",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": eu_model,
            "parent_fk_column": "id_energy_unit",
            "parent_id": 701,
            "id_union_energy_system": tites_ues_id,
            "year_values": ["40.0"],
        },
        {
            "entity_label": "Энергорайон 1",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": eu_model,
            "parent_fk_column": "id_energy_unit",
            "parent_id": 701,
            "id_union_energy_system": tites_ues_id,
            "year_values": ["35.0"],
        },
        {
            "entity_label": "Энергорайон 2",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": eu_model,
            "parent_fk_column": "id_energy_unit",
            "parent_id": 702,
            "id_union_energy_system": tites_ues_id,
            "year_values": ["50.0"],
        },
        {
            "entity_label": "Энергорайон 2",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": eu_model,
            "parent_fk_column": "id_energy_unit",
            "parent_id": 702,
            "id_union_energy_system": tites_ues_id,
            "year_values": ["45.0"],
        },
        {
            "entity_label": "Энергорайон О-1",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": eu_model,
            "parent_fk_column": "id_energy_unit",
            "parent_id": 703,
            "id_union_energy_system": tites_ues_id,
            "perimeter_variant_code": "o1",
            "pd_ec_o1_form_row": True,
            "year_values": ["200.0"],
        },
        {
            "entity_label": "Энергорайон О-1",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": eu_model,
            "parent_fk_column": "id_energy_unit",
            "parent_id": 703,
            "id_union_energy_system": tites_ues_id,
            "perimeter_variant_code": "o1",
            "pd_ec_o1_form_row": True,
            "year_values": ["180.0"],
        },
    ]
    source_rows = list(rows)

    service.inject_oes_summary_verification_rows(
        rows,
        source_rows=source_rows,
        years=[2024],
        rounding_digits=1,
    )

    eu_checks = [
        row
        for row in rows
        if row.get("entity_kind") == "tites_res_energy_unit_sum_check"
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    ]
    assert len(eu_checks) == 1
    assert eu_checks[0]["entity_label"] == "Проверка для ЭС примера"
    assert eu_checks[0]["year_values"] == ["10"]


def test_inject_oes_summary_verification_rows_adds_center_res_check_after_gaes_detail_split(
    monkeypatch,
):
    ues_model = "UnionEnergySystemEnergyConsumptionParameter"
    res_model = "RegionalEnergySystemEnergyConsumptionParameter"
    rd_model = "RegionalDistrictEnergyConsumptionParameter"
    rows = [
        {
            "entity_label": "ОЭС Центра",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 117,
            "year_values": ["1000.0"],
        },
        {
            "entity_label": "ЭС г. Москвы и Московской области",
            "entity_rowspan": 2,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 580,
            "year_values": ["100.0"],
        },
        {
            "entity_label": "ЭС г. Москвы и Московской области",
            "entity_rowspan": 2,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 580,
            "year_values": ["90.0"],
        },
        {
            "entity_label": "ЭС г. Москвы и Московской области (заряд ГАЭС)",
            "entity_rowspan": 1,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 580,
            "pd_ec_gaes_injected_row": True,
            "year_values": ["10.0"],
        },
        {
            "entity_label": "г. Москва",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 667,
            "year_values": ["40.0"],
        },
        {
            "entity_label": "г. Москва",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 667,
            "year_values": ["35.0"],
        },
        {
            "entity_label": "Московская область",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 668,
            "year_values": ["55.0"],
        },
        {
            "entity_label": "Московская область",
            "entity_rowspan": 2,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 668,
            "year_values": ["50.0"],
        },
    ]
    ues_res_sum_source_rows = list(rows)
    monkeypatch.setattr(
        service,
        "_summary_row_entity_has_gaes_charge",
        lambda row: row.get("parent_id") in (580, 668),
    )
    service.inject_oes_territory_detail_without_gaes_summary_rows(
        rows,
        years=[2024],
        rounding_digits=1,
    )

    service.inject_oes_summary_verification_rows(
        rows,
        source_rows=list(rows),
        ues_res_sum_source_rows=ues_res_sum_source_rows,
        years=[2024],
        rounding_digits=1,
    )

    res_checks = [
        row
        for row in rows
        if row.get("entity_kind") == "res_subject_sum_check"
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    ]
    assert len(res_checks) == 1
    assert (
        res_checks[0]["entity_label"]
        == "Проверка для ЭС г. Москвы и Московской области без заряда ГАЭС"
    )
    assert res_checks[0]["year_values"] == ["5"]


def test_inject_oes_summary_verification_rows_skips_gaes_charge_rows():
    ues_model = "UnionEnergySystemEnergyConsumptionParameter"
    res_model = "RegionalEnergySystemEnergyConsumptionParameter"
    rows = [
        {
            "entity_label": "ОЭС Центра",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 117,
            "year_values": ["1000.0"],
        },
        {
            "entity_label": "ОЭС Центра",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 117,
            "year_values": ["900.0"],
        },
        _ues_gaes_row(),
        {
            "entity_label": "ЭС г. Москвы и Московской области",
            "entity_rowspan": 1,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 580,
            "year_values": ["100.0"],
        },
    ]
    source_rows = list(rows)

    service.inject_oes_summary_verification_rows(
        rows,
        source_rows=source_rows,
        years=[2024],
        rounding_digits=1,
    )

    verification_labels = [
        row["entity_label"]
        for row in rows
        if row.get("entity_kind") == "ues_res_sum_check"
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    ]
    assert verification_labels == ["Проверка для ОЭС Центра"]


def test_center_ues_gaes_verification_order_and_compact_labels(monkeypatch):
    """Проверка ОЭС Центра: сразу после с/без ГАЭС; компактные имена при выкл. кнопке."""
    ues_model = "UnionEnergySystemEnergyConsumptionParameter"
    res_model = "RegionalEnergySystemEnergyConsumptionParameter"
    years = [2024]
    rows = [
        {
            "entity_label": "ОЭС Центра",
            "entity_rowspan": 2,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 117,
            "year_values": ["1000.0"],
            "year_numeric_tooltips": ["1000.0"],
            "year_row_ids": [None],
        },
        {
            "entity_label": "ОЭС Центра",
            "entity_rowspan": 2,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 117,
            "year_values": ["900.0"],
            "year_numeric_tooltips": ["900.0"],
            "year_row_ids": [None],
        },
        {
            "entity_label": "ОЭС Центра (заряд ГАЭС)",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": True,
            "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 117,
            "gaes_charge_row_station_name": "всего",
            "pd_ec_gaes_injected_row": True,
            "year_values": ["50.0"],
            "year_numeric_tooltips": ["50.0"],
            "year_row_ids": [None],
        },
        {
            "entity_label": "ЭС г. Москвы и Московской области",
            "entity_rowspan": 1,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 580,
            "id_union_energy_system": 117,
            "year_values": ["800.0"],
            "year_numeric_tooltips": ["800.0"],
            "year_row_ids": [None],
        },
    ]
    monkeypatch.setattr(
        service,
        "_summary_row_entity_has_gaes_charge",
        lambda row: row.get("parent_id") == 117,
    )
    service.inject_union_energy_system_without_gaes_summary_rows(
        rows, years=years, rounding_digits=1
    )
    service.inject_oes_summary_verification_rows(
        rows,
        source_rows=list(rows),
        years=years,
        rounding_digits=1,
    )
    service.apply_union_energy_system_gaes_entity_labels(rows)

    labels = [
        str(row.get("entity_label") or "")
        for row in rows
        if row.get("show_entity_cell")
        and row.get("parameter_key")
        in (
            "energy_consumption_mln_kvt_ch",
            service.GAES_CHARGE_PARAMETER_KEY,
        )
        or (
            row.get("show_entity_cell")
            and row.get("entity_kind") == "ues_res_sum_check"
            and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
        )
    ]
    # С зарядом → проверка → без заряда → проверка (заряд между с зарядом и проверкой).
    assert labels[:5] == [
        "ОЭС Центра с зарядом ГАЭС",
        "ОЭС Центра (заряд ГАЭС)",
        "Проверка для ОЭС Центра с зарядом ГАЭС",
        "ОЭС Центра без заряда ГАЭС",
        "Проверка для ОЭС Центра без заряда ГАЭС",
    ]

    with_verify = next(
        row
        for row in rows
        if row.get("entity_label") == "Проверка для ОЭС Центра с зарядом ГАЭС"
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    )
    without_verify = next(
        row
        for row in rows
        if row.get("entity_label") == "Проверка для ОЭС Центра без заряда ГАЭС"
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    )
    assert with_verify.get("pd_ec_gaes_extra_row") is True
    assert with_verify.get("pd_ec_gaes_without_row") is not True
    assert with_verify.get("pd_ec_entity_label_compact_nt_gaes") == (
        "Проверка для ОЭС Центра"
    )
    assert without_verify.get("pd_ec_gaes_without_row") is True
    assert without_verify.get("pd_ec_collapsed_nt_gaes_visible_row") is True
    assert without_verify.get("pd_ec_entity_label_compact_nt_gaes") == (
        "Проверка для ОЭС Центра"
    )
    without_ues = next(
        row
        for row in rows
        if row.get("pd_ec_ues_without_gaes_injected_row")
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    )
    assert without_ues.get("pd_ec_entity_label_compact_nt_gaes") == "ОЭС Центра"
    assert without_ues.get("pd_ec_collapsed_nt_gaes_visible_row") is True


def _fo_base_row(*, fd_id: int = 10, label: str = "Центральный федеральный округ") -> dict:
    return {
        "entity_label": label,
        "entity_rowspan": 1,
        "entity_depth": 0,
        "entity_kind": "group",
        "show_entity_cell": True,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "demand_model_name": "FederalDistrictEnergyConsumptionParameter",
        "parent_fk_column": "id_federal_district",
        "parent_id": fd_id,
        "perimeter_variant_code": None,
        "year_values": ["1000.0"],
    }


def _fo_sipr_row(*, fd_id: int = 10, label: str = "Центральный федеральный округ") -> dict:
    return {
        "entity_label": label,
        "entity_rowspan": 1,
        "entity_depth": 0,
        "entity_kind": "group",
        "show_entity_cell": False,
        "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
        "demand_model_name": "FederalDistrictEnergyConsumptionParameter",
        "parent_fk_column": "id_federal_district",
        "parent_id": fd_id,
        "perimeter_variant_code": None,
        "year_values": ["900.0"],
    }


def _fo_res_row(
    *,
    res_id: int,
    label: str,
    value: str,
    depth: int = 1,
    perimeter_variant_code=None,
    pd_ec_o1_form_row: bool = False,
) -> dict:
    row = {
        "entity_label": label,
        "entity_rowspan": 1,
        "entity_depth": depth,
        "entity_kind": "child",
        "show_entity_cell": True,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "demand_model_name": "RegionalEnergySystemEnergyConsumptionParameter",
        "parent_fk_column": "id_regional_energy_system",
        "parent_id": res_id,
        "perimeter_variant_code": perimeter_variant_code,
        "year_values": [value],
    }
    if pd_ec_o1_form_row:
        row["pd_ec_o1_form_row"] = True
    return row


def test_inject_fo_summary_verification_rows_builds_fd_minus_res_check(monkeypatch):
    fd_id = 10
    rows = [
        _fo_base_row(fd_id=fd_id),
        _fo_sipr_row(fd_id=fd_id),
        _fo_res_row(res_id=580, label="ЭС г. Москвы и Московской области", value="300.0"),
        _fo_res_row(res_id=581, label="ЭС Тверской области", value="200.0"),
    ]
    rows[0]["entity_rowspan"] = 2

    monkeypatch.setattr(
        service,
        "_resolve_union_energy_system_id_by_name_cf",
        lambda _name: None,
    )

    service.inject_fo_summary_verification_rows(
        rows,
        source_rows=list(rows),
        years=[2024],
        rounding_digits=1,
    )

    checks = [
        row
        for row in rows
        if row.get("entity_kind") == "fo_res_sum_check"
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    ]
    assert len(checks) == 1
    assert checks[0]["entity_label"] == "Проверка для Центральный федеральный округ"
    assert checks[0]["year_values"] == ["500"]
    assert not any(
        row.get("entity_kind") in ("fo_south_ues_verification", "fo_ural_ues_verification")
        for row in rows
    )


def test_inject_fo_summary_verification_rows_excludes_o1_res_from_sum(monkeypatch):
    fd_id = 10
    rows = [
        _fo_base_row(fd_id=fd_id),
        _fo_sipr_row(fd_id=fd_id),
        _fo_res_row(res_id=580, label="ЭС г. Москвы и Московской области", value="300.0"),
        _fo_res_row(
            res_id=999,
            label="Энергорайон О-1",
            value="50.0",
            perimeter_variant_code="o1",
            pd_ec_o1_form_row=True,
        ),
    ]
    rows[0]["entity_rowspan"] = 2

    monkeypatch.setattr(
        service,
        "_resolve_union_energy_system_id_by_name_cf",
        lambda _name: None,
    )

    service.inject_fo_summary_verification_rows(
        rows,
        source_rows=list(rows),
        years=[2024],
        rounding_digits=1,
    )

    checks = [
        row
        for row in rows
        if row.get("entity_kind") == "fo_res_sum_check"
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    ]
    assert len(checks) == 1
    assert checks[0]["year_values"] == ["700"]


def test_inject_fo_summary_verification_rows_does_not_add_oes_cross_checks(
    monkeypatch,
):
    """На сводке ФО не вставляем «Проверка для ОЭС Юга/Урала» — только на /summary/oes/."""
    from decimal import Decimal

    rows = [
        _fo_base_row(fd_id=20, label="Южный ФО"),
        _fo_sipr_row(fd_id=20, label="Южный ФО"),
        _fo_base_row(fd_id=50, label="Северо-Кавказский ФО"),
        _fo_sipr_row(fd_id=50, label="Северо-Кавказский ФО"),
        _fo_base_row(fd_id=87, label="Приволжский ФО"),
        _fo_sipr_row(fd_id=87, label="Приволжский ФО"),
        _fo_base_row(fd_id=91, label="Уральский ФО"),
        _fo_sipr_row(fd_id=91, label="Уральский ФО"),
    ]
    for ix in (0, 2, 4, 6):
        rows[ix]["entity_rowspan"] = 2

    def _resolve_ues(name_cf: str):
        mapping = {
            service.SOUTH_UES_NAME_CF: 118,
            service.URAL_UES_NAME_CF: 116,
            service.MIDDLE_VOLGA_UES_NAME_CF: 115,
        }
        return mapping.get(name_cf)

    def _year_values(model, fk_column, parent_id, years, parameter_key, *, perimeter_variant_code=None):
        if model.__name__ == "UnionEnergySystemEnergyConsumptionParameter":
            return {int(years[0]): Decimal("100")}
        return {int(y): None for y in years}

    monkeypatch.setattr(service, "_resolve_union_energy_system_id_by_name_cf", _resolve_ues)
    monkeypatch.setattr(service, "_year_values_from_parent_demand_rows", _year_values)

    service.inject_fo_summary_verification_rows(
        rows,
        source_rows=list(rows),
        years=[2024],
        rounding_digits=1,
    )

    assert not any(
        row.get("entity_kind") in ("fo_south_ues_verification", "fo_ural_ues_verification")
        for row in rows
    )
    assert not any(
        str(row.get("entity_label") or "").startswith("Проверка для ОЭС ")
        for row in rows
    )

def test_summary_table_verification_uses_res_rows_before_compact_filter():
    """На /summary-table/ РЭС скрыты, но сумма для «Проверка для …» берётся из полного дерева."""
    ues_model = "UnionEnergySystemEnergyConsumptionParameter"
    res_model = "RegionalEnergySystemEnergyConsumptionParameter"
    ues_id = 117
    res_id = 580
    years = [2024]
    full_rows = [
        {
            "entity_label": "ОЭС Центра",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": ues_id,
            "year_values": ["1000.0"],
        },
        {
            "entity_label": "ОЭС Центра",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": ues_id,
            "year_values": ["900.0"],
        },
        {
            "entity_label": "ЭС г. Москвы и Московской области",
            "entity_rowspan": 1,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": res_id,
            "id_union_energy_system": ues_id,
            "year_values": ["800.0"],
        },
        {
            "entity_label": "ЭС г. Москвы и Московской области",
            "entity_rowspan": 1,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": res_id,
            "id_union_energy_system": ues_id,
            "year_values": ["700.0"],
        },
    ]
    source_summary_rows = list(full_rows)
    compact_rows = list(full_rows)
    service.tag_energy_consumption_summary_rows_for_territory_compact(compact_rows)
    table_rows = service.filter_summary_rows_for_summary_table_page(compact_rows)

    service.inject_oes_summary_verification_rows(
        table_rows,
        source_rows=list(table_rows),
        ues_res_sum_source_rows=source_summary_rows,
        years=years,
        rounding_digits=1,
    )

    ues_check = next(
        row
        for row in table_rows
        if row.get("entity_kind") == "ues_res_sum_check"
        and row.get("entity_label") == "Проверка для ОЭС Центра"
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    )
    assert ues_check["year_values"] == ["200"]
    assert ues_check["pd_ec_verification_year_red"] == [True]


def test_summary_table_south_verification_excludes_crimea_sev_res_through_2016():
    """На /summary-table/ до 2017 из суммы РЭС для проверки ОЭС Юга исключается Крым/Севастополь."""
    ues_model = "UnionEnergySystemEnergyConsumptionParameter"
    res_model = "RegionalEnergySystemEnergyConsumptionParameter"
    south_id = 118
    other_res_id = 501
    crimea_res_id = 620
    years = [2016, 2017]
    full_rows = [
        {
            **_south_variant_row(service.CODE_WITHOUT_NT_WITH_GAES, "1000.0"),
            "year_values": ["1000.0", "1000.0"],
        },
        {
            "entity_label": "ОЭС Юга",
            "entity_rowspan": 1,
            "entity_depth": 0,
            "entity_kind": "perimeter_variant",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": south_id,
            "perimeter_variant_code": service.CODE_WITHOUT_NT_WITH_GAES,
            "year_values": ["900.0", "900.0"],
        },
        {
            "entity_label": "ЭС Краснодарского края и Республики Адыгея",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": other_res_id,
            "id_union_energy_system": south_id,
            "year_values": ["200.0", "200.0"],
        },
        {
            "entity_label": "ЭС Республики Крым и г. Севастополя",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": crimea_res_id,
            "id_union_energy_system": south_id,
            "year_values": ["100.0", "100.0"],
        },
    ]
    source_summary_rows = list(full_rows)
    compact_rows = list(full_rows)
    service.tag_energy_consumption_summary_rows_for_territory_compact(compact_rows)
    table_rows = service.filter_summary_rows_for_summary_table_page(compact_rows)
    service.apply_energy_consumption_summary_table_variant_toggle_rows(table_rows)

    service.inject_oes_summary_verification_rows(
        table_rows,
        source_rows=list(table_rows),
        ues_res_sum_source_rows=source_summary_rows,
        years=years,
        rounding_digits=1,
    )

    south_check = next(
        row
        for row in table_rows
        if row.get("entity_kind") == "oes_south_oes_model_verification"
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    )
    assert south_check["entity_label"] == "Проверка для ОЭС Юга без НТ с зарядом ГАЭС"
    assert south_check["year_values"] == ["800", "700"]


def test_inject_oes_summary_verification_rows_adds_south_ues_variant_checks():
    ues_model = "UnionEnergySystemEnergyConsumptionParameter"
    res_model = "RegionalEnergySystemEnergyConsumptionParameter"
    rd_model = "RegionalDistrictEnergyConsumptionParameter"
    south_id = 118
    res_id = 501
    rows = [
        _south_variant_row(service.CODE_WITH_NT_WITH_GAES, "600.0"),
        {
            "entity_label": "ОЭС Юга",
            "entity_rowspan": 1,
            "entity_depth": 0,
            "entity_kind": "perimeter_variant",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": south_id,
            "perimeter_variant_code": service.CODE_WITH_NT_WITH_GAES,
            "year_values": ["550.0"],
        },
        _south_variant_row(service.CODE_WITHOUT_NT_WITH_GAES, "500.0"),
        {
            "entity_label": "ОЭС Юга",
            "entity_rowspan": 1,
            "entity_depth": 0,
            "entity_kind": "perimeter_variant",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": south_id,
            "perimeter_variant_code": service.CODE_WITHOUT_NT_WITH_GAES,
            "year_values": ["450.0"],
        },
        {
            "entity_label": "ЭС Краснодарского края и Республики Адыгея",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": res_id,
            "id_union_energy_system": south_id,
            "year_values": ["200.0"],
        },
        {
            "entity_label": "ЭС Краснодарского края и Республики Адыгея",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "child",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": res_id,
            "id_union_energy_system": south_id,
            "year_values": ["180.0"],
        },
        {
            "entity_label": "Краснодарский край",
            "entity_rowspan": 1,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 701,
            "id_union_energy_system": south_id,
            "year_values": ["120.0"],
        },
        {
            "entity_label": "Республика Адыгея",
            "entity_rowspan": 1,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": rd_model,
            "parent_fk_column": "id_regional_district",
            "parent_id": 702,
            "id_union_energy_system": south_id,
            "year_values": ["70.0"],
        },
    ]
    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)
    source_rows = list(rows)

    service.inject_oes_summary_verification_rows(
        rows,
        source_rows=source_rows,
        years=[2024],
        rounding_digits=1,
    )

    south_checks = [
        row
        for row in rows
        if row.get("entity_kind") == "oes_south_oes_model_verification"
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    ]
    assert len(south_checks) == 1
    assert south_checks[0]["entity_label"] == "Проверка для ОЭС Юга без НТ с зарядом ГАЭС"
    assert south_checks[0]["year_values"] == ["300"]

    res_checks = [
        row
        for row in rows
        if row.get("entity_kind") == "res_subject_sum_check"
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    ]
    assert len(res_checks) == 1
    assert res_checks[0]["entity_label"] == (
        "Проверка для ЭС Краснодарского края и Республики Адыгея"
    )
    assert res_checks[0]["year_values"] == ["10"]


def test_inject_oes_summary_verification_rows_excludes_crimea_sev_res_through_2016():
    ues_model = "UnionEnergySystemEnergyConsumptionParameter"
    res_model = "RegionalEnergySystemEnergyConsumptionParameter"
    south_id = 118
    other_res_id = 501
    crimea_res_id = 620
    years = [2016, 2017]
    rows = [
        {
            **_south_variant_row(service.CODE_WITHOUT_NT_WITH_GAES, "1000.0"),
            "year_values": ["1000.0", "1000.0"],
        },
        {
            "entity_label": "ОЭС Юга",
            "entity_rowspan": 1,
            "entity_depth": 0,
            "entity_kind": "perimeter_variant",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": south_id,
            "perimeter_variant_code": service.CODE_WITHOUT_NT_WITH_GAES,
            "year_values": ["900.0", "900.0"],
        },
        {
            "entity_label": "ЭС Краснодарского края и Республики Адыгея",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": other_res_id,
            "id_union_energy_system": south_id,
            "year_values": ["200.0", "200.0"],
        },
        {
            "entity_label": "ЭС Республики Крым и г. Севастополя",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": crimea_res_id,
            "id_union_energy_system": south_id,
            "year_values": ["100.0", "100.0"],
        },
    ]
    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)
    source_rows = list(rows)

    service.inject_oes_summary_verification_rows(
        rows,
        source_rows=source_rows,
        years=years,
        rounding_digits=1,
    )

    south_check = next(
        row
        for row in rows
        if row.get("entity_kind") == "oes_south_oes_model_verification"
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    )
    assert south_check["year_values"] == ["800", "700"]


def test_inject_oes_summary_verification_rows_skips_tites_east_before_2019():
    tites_east_id = 901
    ues_model = "UnionEnergySystemEnergyConsumptionParameter"
    res_model = "RegionalEnergySystemEnergyConsumptionParameter"
    res_id = 902
    years = [2018, 2019, 2020]
    rows = [
        {
            "entity_label": "ТИТЭС Востока",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": tites_east_id,
            "year_values": ["1000.0", "1000.0", "1000.0"],
        },
        {
            "entity_label": "ТИТЭС Востока",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "entity_kind": "group",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": ues_model,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": tites_east_id,
            "year_values": ["900.0", "900.0", "900.0"],
        },
        {
            "entity_label": "ЭС примера",
            "entity_rowspan": 1,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": res_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": res_id,
            "id_union_energy_system": tites_east_id,
            "year_values": ["800.0", "800.0", "800.0"],
        },
    ]

    service.inject_oes_summary_verification_rows(
        rows,
        source_rows=rows,
        years=years,
        rounding_digits=1,
    )

    tites_check = next(
        row
        for row in rows
        if row.get("entity_kind") == "ues_res_sum_check"
        and row.get("entity_label") == "Проверка для ТИТЭС Востока"
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    )
    assert tites_check["perimeter_variant_from_year"] == service.TITES_EAST_VERIFICATION_FROM_YEAR
    assert tites_check["year_values"] == ["—", "200", "200"]
    assert tites_check["pd_ec_verification_year_red"] == [False, True, True]

    filtered = service.filter_oes_summary_hidden_tites_union_energy_system_rows(rows)
    assert not any(
        row.get("entity_label") == "Проверка для ТИТЭС Востока" for row in filtered
    )
    assert any(row.get("entity_label") == "ЭС примера" for row in filtered)


def test_filter_summary_table_hub_oes_and_tites_verification_rows():
    rows = [
        {
            "entity_label": "Проверка для ОЭС Северо-Запада",
            "entity_kind": "ues_res_sum_check",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "Проверка для ТИТЭС",
            "entity_kind": "oes_tites_aggregate_check",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "Проверка для ЭС примера",
            "entity_kind": "tites_res_energy_unit_sum_check",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "Проверка для РЭС примера",
            "entity_kind": "res_subject_sum_check",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "Проверка ЕЭС России",
            "entity_kind": "oes_ees_model_verification",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "ОЭС Северо-Запада",
            "entity_kind": "group",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
    ]

    filtered = service.filter_summary_table_hub_oes_and_tites_verification_rows(rows)
    labels = {row.get("entity_label") for row in filtered}
    assert labels == {
        "Проверка для РЭС примера",
        "Проверка ЕЭС России",
        "ОЭС Северо-Запада",
    }


def test_filter_oes_summary_hidden_tites_union_energy_system_rows():
    rows = [
        {
            "entity_label": "ТИТЭС Востока",
            "entity_kind": "group",
            "demand_model_name": "UnionEnergySystemEnergyConsumptionParameter",
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 901,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "ТИТЭС Сибири",
            "entity_kind": "group",
            "demand_model_name": "UnionEnergySystemEnergyConsumptionParameter",
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 902,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "ОЭС Северо-Запада",
            "entity_kind": "group",
            "demand_model_name": "UnionEnergySystemEnergyConsumptionParameter",
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 10,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "Проверка для ТИТЭС Востока",
            "entity_kind": "ues_res_sum_check",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "Проверка для ТИТЭС Сибири",
            "entity_kind": "ues_res_sum_check",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "Проверка для ОЭС Северо-Запада",
            "entity_kind": "ues_res_sum_check",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "ЭС примера",
            "entity_kind": "child",
            "id_union_energy_system": 901,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
    ]

    filtered = service.filter_oes_summary_hidden_tites_union_energy_system_rows(rows)

    labels = {row.get("entity_label") for row in filtered}
    assert labels == {
        "ОЭС Северо-Запада",
        "Проверка для ОЭС Северо-Запада",
        "ЭС примера",
    }


def test_filter_oes_max_summary_page_hidden_rows():
    rows = [
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России с НТ",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 2,
        },
        {
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "entity_label": "ЦЗ России с НТ",
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
        },
        {
            "entity_kind": service.ENTITY_KIND_RUSSIA_FEDERATION,
            "entity_label": "Россия с НТ",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 2,
        },
        {
            "entity_kind": service.ENTITY_KIND_RUSSIA_FEDERATION,
            "entity_label": "Заряд ГАЭС",
            "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
            "show_entity_cell": True,
            "entity_rowspan": 1,
        },
        {
            "entity_kind": "union_energy_system",
            "entity_label": "ОЭС Центра",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 1,
        },
        {
            "entity_kind": service.ENTITY_KIND_EES_RUSSIA,
            "entity_label": "ЭЭС России (заряд ГАЭС)",
            "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
            "show_entity_cell": True,
            "entity_rowspan": 1,
        },
    ]

    filtered = service.filter_oes_max_summary_page_hidden_rows(rows)

    assert [row.get("entity_label") for row in filtered] == [
        "ЦЗ России с НТ",
        "ЦЗ России с НТ",
        "Россия с НТ",
        "ОЭС Центра",
        "ЭЭС России (заряд ГАЭС)",
    ]
    assert filtered[0].get("show_entity_cell") is True
    assert filtered[0].get("entity_rowspan") == 2
    assert filtered[2].get("entity_kind") == service.ENTITY_KIND_RUSSIA_FEDERATION
    assert all(row.get("entity_label") != "Заряд ГАЭС" for row in filtered)


def test_filter_oes_max_summary_page_hidden_rows_norilsk_res():
    norilsk_label = "ЭС г. Норильска Красноярского края"
    norilsk_res_id = 7701
    rows = [
        {
            "entity_label": norilsk_label,
            "demand_model_name": "RegionalEnergySystemEnergyConsumptionParameter",
            "id_regional_energy_system": norilsk_res_id,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 2,
        },
        {
            "entity_label": norilsk_label,
            "demand_model_name": "RegionalEnergySystemEnergyConsumptionParameter",
            "id_regional_energy_system": norilsk_res_id,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
        },
        {
            "entity_label": "Таймырский энергорайон",
            "demand_model_name": "EnergyUnitEnergyConsumptionParameter",
            "id_regional_energy_system": norilsk_res_id,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 1,
        },
        {
            "entity_label": f"Проверка для {norilsk_label}",
            "entity_kind": "ues_res_sum_check",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 1,
        },
        {
            "entity_label": "ОЭС Сибири",
            "demand_model_name": "UnionEnergySystemEnergyConsumptionParameter",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 1,
        },
    ]

    filtered = service.filter_oes_max_summary_page_hidden_rows(rows)
    labels = [row.get("entity_label") for row in filtered]

    assert labels == ["Таймырский энергорайон", "ОЭС Сибири"]
    assert all("Норильск" not in str(label) for label in labels)


def test_filter_oes_max_keeps_ees_unified_and_ees_russia_aggregate_rows():
    from app.common.perimeter_variant.constants import (
        CODE_WITH_NT_WITH_GAES,
        EES_RUSSIA_AGGREGATE_NAME,
        EES_UNIFIED_REF_NAME,
    )

    rows = [
        {
            "entity_label": f"{EES_UNIFIED_REF_NAME} с НТ с зарядом ГАЭС",
            "demand_model_name": "EesRussiaEnergyConsumptionParameter",
            "perimeter_variant_code": CODE_WITH_NT_WITH_GAES,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 1,
        },
        {
            "entity_label": EES_RUSSIA_AGGREGATE_NAME,
            "demand_model_name": "EesRussiaEnergyConsumptionParameter",
            "perimeter_variant_code": CODE_WITH_NT_WITH_GAES,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 1,
        },
        {
            "entity_label": EES_UNIFIED_REF_NAME,
            "demand_model_name": "EnergySystemTypeEnergyConsumptionParameter",
            "perimeter_variant_code": CODE_WITH_NT_WITH_GAES,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 1,
        },
    ]

    filtered = service.filter_oes_max_summary_page_hidden_rows(rows)
    filtered_labels = [row.get("entity_label") for row in filtered]

    assert f"{EES_UNIFIED_REF_NAME} с НТ с зарядом ГАЭС" in filtered_labels
    assert EES_RUSSIA_AGGREGATE_NAME in filtered_labels
    assert EES_UNIFIED_REF_NAME in filtered_labels


def test_build_oes_summary_table_raw_entities_matches_pd_top_order(monkeypatch):
    """ЦЗ → ЭЭС → ЕЭС (без ОЭС) → СЗ → ОЭС → ТИТЭС; заряд ГАЭС сохраняется в агрегатах."""
    from unittest.mock import MagicMock

    cz = MagicMock(label="ЦЗ", children=[])
    ees = MagicMock(label="ЭЭС", children=[])
    est = MagicMock(label="ЕЭС", children=[])
    sa = MagicMock(label="СЗ", children=[])
    ues = MagicMock(label="ОЭС", children=[], depth=0)
    tites = service.SummaryEntity(
        label="ТИТЭС",
        depth=0,
        parameters=(),
        demand_rows=[],
        children=[],
    )

    monkeypatch.setattr(
        service,
        "_build_perimeter_aggregate_entities",
        lambda **kwargs: {
            service.ENTITY_KIND_CENTRALIZED_ZONE: [cz],
            service.ENTITY_KIND_EES_RUSSIA: [ees],
            service.ENTITY_KIND_RUSSIA_FEDERATION: [MagicMock(label="Россия")],
        }.get(kwargs["entity_kind"], []),
    )
    monkeypatch.setattr(
        service,
        "_build_energy_system_type_entities",
        lambda name, predicate, **kwargs: (
            [est] if name == service.EES_UNIFIED_REF_NAME else [tites]
        ),
    )
    monkeypatch.setattr(
        service,
        "_build_synchronous_area_entities",
        lambda **kwargs: [sa],
    )
    monkeypatch.setattr(
        service,
        "_build_oes_summary_table_union_energy_system_entities",
        lambda **kwargs: [ues],
    )

    entities = service._build_oes_summary_table_raw_entities(
        include_russia_top_row=False,
        include_ees_russia_rows=True,
        include_synchronous_area_rows=True,
    )

    assert entities == [cz, ees, est, sa, ues, tites]

    # ЕЭС строится без дочерних ОЭС (предикат всегда False).
    calls = []
    def _capture_est(name, predicate, **kwargs):
        calls.append((name, predicate))
        return [est] if name == service.EES_UNIFIED_REF_NAME else [tites]

    monkeypatch.setattr(service, "_build_energy_system_type_entities", _capture_est)
    service._build_oes_summary_table_raw_entities(
        include_russia_top_row=False,
        include_ees_russia_rows=True,
        include_synchronous_area_rows=True,
    )
    ees_call = next(c for c in calls if c[0] == service.EES_UNIFIED_REF_NAME)
    assert ees_call[1](MagicMock()) is False


def test_build_oes_summary_table_raw_entities_russia_federation_first(monkeypatch):
    from unittest.mock import MagicMock

    cz = MagicMock(label="ЦЗ")
    russia = MagicMock(label="Россия")
    ees = MagicMock(label="ЭЭС")

    monkeypatch.setattr(
        service,
        "_build_perimeter_aggregate_entities",
        lambda **kwargs: {
            service.ENTITY_KIND_CENTRALIZED_ZONE: [cz],
            service.ENTITY_KIND_RUSSIA_FEDERATION: [russia],
            service.ENTITY_KIND_EES_RUSSIA: [ees],
        }.get(kwargs["entity_kind"], []),
    )
    monkeypatch.setattr(service, "_build_energy_system_type_entities", lambda *a, **k: [])
    monkeypatch.setattr(service, "_build_synchronous_area_entities", lambda **k: [])
    monkeypatch.setattr(
        service,
        "_build_oes_summary_table_union_energy_system_entities",
        lambda **k: [],
    )

    entities = service._build_oes_summary_table_raw_entities(
        include_russia_top_row=True,
        include_ees_russia_rows=True,
        include_synchronous_area_rows=False,
        russia_federation_first=True,
    )

    assert entities[:3] == [russia, cz, ees]


def test_inject_verification_rows_use_independent_insert_positions(monkeypatch):
    def _row(**kwargs: object) -> dict:
        return dict(kwargs)

    top_ees = _row(
        entity_label="ЭЭС России",
        entity_kind="ees_russia",
        demand_model_name="EesRussiaEnergyConsumptionParameter",
        parameter_key="energy_consumption_mln_kvt_ch",
    )
    ezs_without_nt_with_gaes = _row(
        entity_label="ЭЭС России без НТ с зарядом ГАЭС",
        entity_kind="ees_russia",
        demand_model_name="EesRussiaEnergyConsumptionParameter",
        perimeter_variant_code=service.CODE_WITHOUT_NT_WITH_GAES,
        parameter_key="energy_consumption_mln_kvt_ch",
        entity_depth=0,
    )
    ees_without_nt_with_gaes = _row(
        entity_label="ЕЭС России без НТ с зарядом ГАЭС",
        entity_kind="group-root",
        demand_model_name="EnergySystemTypeEnergyConsumptionParameter",
        perimeter_variant_code=service.CODE_WITHOUT_NT_WITH_GAES,
        parameter_key="energy_consumption_mln_kvt_ch",
        entity_depth=0,
        show_entity_cell=True,
    )
    ees_without_nt_without_gaes = _row(
        entity_label="ЕЭС России без НТ без заряда ГАЭС",
        entity_kind="group-root",
        demand_model_name="EnergySystemTypeEnergyConsumptionParameter",
        perimeter_variant_code=service.CODE_WITHOUT_NT_WITHOUT_GAES,
        parameter_key="energy_consumption_mln_kvt_ch",
        entity_depth=0,
        show_entity_cell=True,
    )
    first_sa_with_nt = _row(
        entity_label="Первая синхронная зона с НТ с зарядом ГАЭС",
        demand_model_name="SynchronousAreaEnergyConsumptionParameter",
        perimeter_variant_code=service._FIRST_SA_WITH_NT_WITH_GAES_WITH_KALININGRAD_VARIANT,
        parameter_key="energy_consumption_mln_kvt_ch",
    )
    first_sa_without_nt_with_gaes = _row(
        entity_label="Первая синхронная зона без НТ с зарядом ГАЭС",
        demand_model_name="SynchronousAreaEnergyConsumptionParameter",
        perimeter_variant_code="without_nt_with_gaes_kaliningrad",
        parameter_key="energy_consumption_mln_kvt_ch",
        entity_depth=0,
    )
    first_sa_without_nt_without_gaes = _row(
        entity_label="Первая синхронная зона без НТ без заряда ГАЭС",
        demand_model_name="SynchronousAreaEnergyConsumptionParameter",
        perimeter_variant_code="without_nt_without_gaes_kaliningrad",
        parameter_key="energy_consumption_mln_kvt_ch",
    )
    first_sa_without_kal = _row(
        entity_label="Первая синхронная зона без НТ с зарядом ГАЭС",
        demand_model_name="SynchronousAreaEnergyConsumptionParameter",
        perimeter_variant_code=service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_VARIANT,
        parameter_key="energy_consumption_mln_kvt_ch",
        entity_depth=0,
    )
    kaliningrad_sa = _row(
        entity_label="Синхронная зона Калининградской области",
        demand_model_name="SynchronousAreaEnergyConsumptionParameter",
        parameter_key="energy_consumption_mln_kvt_ch",
    )
    oes = _row(
        entity_label="ОЭС Северо-Запада",
        demand_model_name="UnionEnergySystemEnergyConsumptionParameter",
        parent_fk_column="id_union_energy_system",
        parameter_key="energy_consumption_mln_kvt_ch",
    )
    summary_rows = [
        top_ees,
        ezs_without_nt_with_gaes,
        ees_without_nt_with_gaes,
        ees_without_nt_without_gaes,
        first_sa_with_nt,
        first_sa_without_nt_with_gaes,
        first_sa_without_nt_without_gaes,
        first_sa_without_kal,
        kaliningrad_sa,
        oes,
    ]

    def _fake_verification_rows(label: str) -> list[dict]:
        return [
            {
                "entity_label": label,
                "entity_kind": "oes_ees_sync_table_verification",
                "parameter_key": "energy_consumption_mln_kvt_ch",
                "show_entity_cell": True,
            }
        ]

    def _build_without_nt(*_args, **_kwargs):
        return _fake_verification_rows("Проверка ЕЭС России без НТ с зарядом ГАЭС")

    def _build_first_sa(*_args, **kwargs):
        return _fake_verification_rows(str(kwargs.get("entity_label", "")))

    monkeypatch.setattr(
        service,
        "_build_ees_russia_without_nt_with_gaes_kaliningrad_split_verification_rows",
        _build_without_nt,
    )
    monkeypatch.setattr(
        service,
        "_build_first_sa_without_nt_with_gaes_ues_verification_rows",
        _build_first_sa,
    )
    monkeypatch.setattr(service, "_resolve_first_synchronous_area_id", lambda: 1)
    monkeypatch.setattr(service, "_resolve_union_energy_system_id_by_name_cf", lambda _name: None)

    service.inject_first_sa_without_nt_with_gaes_with_kaliningrad_ues_verification_after_ees_russia_rows(
        summary_rows,
        years=[2024],
        rounding_digits=1,
    )

    labels = [str(row.get("entity_label") or "") for row in summary_rows]
    assert labels == [
        "ЭЭС России",
        "ЭЭС России без НТ с зарядом ГАЭС",
        "ЕЭС России без НТ с зарядом ГАЭС",
        "Проверка ЕЭС России без НТ с зарядом ГАЭС",
        "ЕЭС России без НТ без заряда ГАЭС",
        "Первая синхронная зона с НТ с зарядом ГАЭС",
        "Первая синхронная зона без НТ с зарядом ГАЭС",
        service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_UES_VERIFICATION_LABEL,
        "Первая синхронная зона без НТ без заряда ГАЭС",
        "Первая синхронная зона без НТ с зарядом ГАЭС",
        service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_UES_VERIFICATION_LABEL,
        "Синхронная зона Калининградской области",
        "ОЭС Северо-Запада",
    ]
    with_kal_rows = [
        row
        for row in summary_rows
        if row.get("entity_label")
        == service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_UES_VERIFICATION_LABEL
    ]
    assert with_kal_rows
    assert all(not row.get("pd_ec_summary_table_only_row") for row in with_kal_rows)
    assert (
        service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_UES_VERIFICATION_LABEL
        == "Проверка первой синхронной зоны без НТ с зарядом ГАЭС"
    )


def test_first_sa_without_nt_with_kaliningrad_sum_subtracts_from_year_from(monkeypatch):
    """Сумма проверки с ``_kaliningrad``: ЭС Калининграда вычитается только с «Год с»."""
    years = [2024, 2025]
    first_sa_id = 39
    monkeypatch.setattr(
        service,
        "_year_values_sum_ues_in_first_sa_without_nt",
        lambda *_a, **_k: {2024: Decimal("130"), 2025: Decimal("240")},
    )
    monkeypatch.setattr(
        service,
        "_kaliningrad_es_parameter_year_values",
        lambda *_a, **_k: {2024: Decimal("5"), 2025: Decimal("7")},
    )
    monkeypatch.setattr(
        service,
        "perimeter_variant_year_bounds_for_code",
        lambda _code: (2025, None),
    )

    result = service._year_values_sum_ues_in_first_sa_without_nt_with_kaliningrad_from_year(
        first_sa_id,
        years,
        "energy_consumption_mln_kvt_ch",
        first_sa_perimeter_variant_code="without_nt_with_gaes_kaliningrad",
    )
    assert result == {2024: Decimal("130"), 2025: Decimal("233")}

    no_bounds = service._year_values_sum_ues_in_first_sa_without_nt_with_kaliningrad_from_year(
        first_sa_id,
        years,
        "energy_consumption_mln_kvt_ch",
        first_sa_perimeter_variant_code="without_nt_with_gaes",
    )
    assert no_bounds == {2024: Decimal("130"), 2025: Decimal("240")}


def test_last_ees_russia_without_nt_with_gaes_summary_row_index():
    rows = [
        {
            "entity_label": "ЭЭС России без НТ с зарядом ГАЭС",
            "demand_model_name": "EesRussiaEnergyConsumptionParameter",
            "entity_kind": "ees_russia",
            "perimeter_variant_code": service.CODE_WITHOUT_NT_WITH_GAES,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
        },
        {
            "entity_label": "ЕЭС России без НТ с зарядом ГАЭС",
            "demand_model_name": "EnergySystemTypeEnergyConsumptionParameter",
            "perimeter_variant_code": service.CODE_WITHOUT_NT_WITH_GAES,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
        },
        {
            "entity_label": "ЕЭС России без НТ с зарядом ГАЭС",
            "demand_model_name": "EnergySystemTypeEnergyConsumptionParameter",
            "perimeter_variant_code": service.CODE_WITHOUT_NT_WITH_GAES,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "show_entity_cell": False,
        },
        {
            "entity_label": "ЕЭС России без НТ без заряда ГАЭС",
            "demand_model_name": "EnergySystemTypeEnergyConsumptionParameter",
            "perimeter_variant_code": service.CODE_WITHOUT_NT_WITHOUT_GAES,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
        },
    ]
    assert service._last_ees_russia_without_nt_with_gaes_summary_row_index(rows) == 2


def test_ees_russia_without_nt_gaes_verification_tooltip_matches_formula_components():
    """Формула проверки ЕЭС = 1-я СЗ + 2-я СЗ + СЗ Калининграда (без ТИТЭС)."""
    assert "ЕЭС России без НТ с зарядом ГАЭС" in (
        service._EES_RUSSIA_WITHOUT_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_TOOLTIP
    )
    assert "Первая синхронная зона без НТ с зарядом ГАЭС" in (
        service._EES_RUSSIA_WITHOUT_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_TOOLTIP
    )
    assert "Вторая синхронная зона" in (
        service._EES_RUSSIA_WITHOUT_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_TOOLTIP
    )
    assert "Синхронная зона Калининградской области" in (
        service._EES_RUSSIA_WITHOUT_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_TOOLTIP
    )
    assert "ТИТЭС" not in (
        service._EES_RUSSIA_WITHOUT_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_TOOLTIP
    )
    # Как у проверки «с НТ»: Калининград отдельным слагаемым, без ТИТЭС.
    assert "Синхронная зона Калининградской области" in (
        service._EES_RUSSIA_WITH_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_TOOLTIP
    )
    assert "ТИТЭС" not in (
        service._EES_RUSSIA_WITH_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_TOOLTIP
    )


def _ees_unified_variant_row(code: str, value: str, *, parent_id: int = 1) -> dict:
    return {
        "entity_label": "ЕЭС России",
        "entity_rowspan": 1,
        "entity_depth": 0,
        "entity_kind": "perimeter_variant",
        "show_entity_cell": True,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "demand_model_name": "EnergySystemTypeEnergyConsumptionParameter",
        "parent_fk_column": "id_energy_system_type",
        "parent_id": parent_id,
        "perimeter_variant_code": code,
        "year_values": [value],
        "year_numeric_tooltips": [value],
        "year_row_ids": [None],
    }


def _ees_unified_gaes_charge_row(value: str, *, nt_group: str, parent_id: int = 1) -> dict:
    row = {
        "entity_label": "ЕЭС России",
        "entity_rowspan": 1,
        "entity_depth": 0,
        "entity_kind": "group",
        "show_entity_cell": True,
        "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
        "parameter_label": service.GAES_CHARGE_PARAMETER_LABEL,
        "demand_model_name": "EnergySystemTypeEnergyConsumptionParameter",
        "parent_fk_column": "id_energy_system_type",
        "parent_id": parent_id,
        "perimeter_variant_code": None,
        "year_values": [value],
        "year_numeric_tooltips": [value],
        "year_row_ids": [None],
        "gaes_charge_row_station_name": "всего",
        "pd_ec_gaes_injected_row": True,
    }
    if nt_group == "with_nt":
        row["pd_ec_nt_extra_row"] = True
        row["pd_ec_nt_without_row"] = False
    else:
        row["pd_ec_nt_extra_row"] = False
        row["pd_ec_nt_without_row"] = True
    return row


def test_ees_unified_without_gaes_rows_are_formula_derived_not_manual():
    """ЕЭС … без заряда ГАЭС = ЕЭС … с зарядом ГАЭС − Заряд ГАЭС; без ручного ввода."""
    years = [2024]
    without_nt_with = _ees_unified_variant_row(
        service.CODE_WITHOUT_NT_WITH_GAES, "100.0"
    )
    without_nt_charge = _ees_unified_gaes_charge_row("12.0", nt_group="without_nt")
    without_nt_without = _ees_unified_variant_row(
        service.CODE_WITHOUT_NT_WITHOUT_GAES, "77.5"
    )
    with_nt_with = _ees_unified_variant_row(service.CODE_WITH_NT_WITH_GAES, "150.0")
    with_nt_charge = _ees_unified_gaes_charge_row("20.0", nt_group="with_nt")
    with_nt_without = _ees_unified_variant_row(
        service.CODE_WITH_NT_WITHOUT_GAES, "0.0"
    )
    rows = [
        without_nt_with,
        without_nt_charge,
        without_nt_without,
        with_nt_with,
        with_nt_charge,
        with_nt_without,
    ]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)
    service.apply_gaes_without_charge_formula_to_summary_rows(
        rows,
        years,
        rounding_digits=1,
    )

    assert service._raw_year_values_from_summary_row(without_nt_without, years) == {
        2024: Decimal("88.0")
    }
    assert service._raw_year_values_from_summary_row(with_nt_without, years) == {
        2024: Decimal("130.0")
    }
    assert without_nt_without.get("pd_ec_formula_derived_row") is True
    assert with_nt_without.get("pd_ec_formula_derived_row") is True
    assert (
        without_nt_without.get("gaes_without_charge_formula_kind")
        == "ees_russia_without_nt_gaes_diff"
    )
    assert (
        with_nt_without.get("gaes_without_charge_formula_kind")
        == "ees_russia_with_nt_gaes_diff"
    )


def test_ees_unified_with_gaes_rows_remain_manual_not_formula_derived(monkeypatch):
    """«ЕЭС России … с зарядом ГАЭС» не пересчитываются и остаются для ручного ввода."""
    years = [2024]

    def _row(**kwargs: object) -> dict:
        base = {
            "year_values": ["100.0"],
            "year_numeric_tooltips": ["100.0"],
            "entity_rowspan": 1,
            "show_entity_cell": True,
            "entity_depth": 0,
        }
        base.update(kwargs)
        return base

    ees_without = _row(
        entity_label="ЕЭС России без НТ с зарядом ГАЭС",
        demand_model_name="EnergySystemTypeEnergyConsumptionParameter",
        perimeter_variant_code=service.CODE_WITHOUT_NT_WITH_GAES,
        parameter_key="energy_consumption_mln_kvt_ch",
        parent_id=1,
        parent_fk_column="id_energy_system_type",
    )
    ees_with = _row(
        entity_label="ЕЭС России с НТ с зарядом ГАЭС",
        demand_model_name="EnergySystemTypeEnergyConsumptionParameter",
        perimeter_variant_code=service.CODE_WITH_NT_WITH_GAES,
        parameter_key="energy_consumption_mln_kvt_ch",
        parent_id=1,
        parent_fk_column="id_energy_system_type",
    )
    ezs = _row(
        entity_label="ЭЭС России без НТ с зарядом ГАЭС",
        entity_kind=service.ENTITY_KIND_EES_RUSSIA,
        demand_model_name="EesRussiaEnergyConsumptionParameter",
        perimeter_variant_code=service.CODE_WITHOUT_NT_WITH_GAES,
        parameter_key="energy_consumption_mln_kvt_ch",
    )
    first_sa = _row(
        entity_label="Первая синхронная зона без НТ с зарядом ГАЭС с ЭС Калининградской области",
        demand_model_name="SynchronousAreaEnergyConsumptionParameter",
        perimeter_variant_code=service.CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES,
        parameter_key="energy_consumption_mln_kvt_ch",
        year_values=["50.0"],
        year_numeric_tooltips=["50.0"],
    )
    second_sa = _row(
        entity_label="Вторая синхронная зона",
        demand_model_name="SynchronousAreaEnergyConsumptionParameter",
        parameter_key="energy_consumption_mln_kvt_ch",
        year_values=["30.0"],
        year_numeric_tooltips=["30.0"],
    )
    rows = [ezs, ees_without, ees_with, first_sa, second_sa]
    monkeypatch.setattr(
        service,
        "_year_values_for_tites_source",
        lambda *_a, **_k: {2024: Decimal("20")},
    )

    service.apply_ees_russia_gaes_aggregate_formulas(rows, years, rounding_digits=1)
    service.apply_oes_ees_unified_consumption_formula_to_summary_rows(
        rows, years, rounding_digits=1
    )

    assert ees_without.get("pd_ec_formula_derived_row") is not True
    assert ees_with.get("pd_ec_formula_derived_row") is not True
    assert ees_without["year_values"] == ["100.0"]
    assert ees_with["year_values"] == ["100.0"]
    assert ezs.get("pd_ec_formula_derived_row") is True


def _kaliningrad_sync_area_variant_row(
    *,
    parameter_key: str = "energy_consumption_mln_kvt_ch",
    value: str = "0.0",
    parent_id: int = 3,
) -> dict:
    return {
        "entity_label": "Синхронная зона Калининградской области",
        "entity_rowspan": 1,
        "entity_depth": 0,
        "entity_kind": "synchronous_area",
        "show_entity_cell": True,
        "parameter_key": parameter_key,
        "demand_model_name": "SynchronousAreaEnergyConsumptionParameter",
        "parent_fk_column": "id_synchronous_area",
        "parent_id": parent_id,
        "perimeter_variant_code": "without_nt_with_gaes_without_kaliningrad_es",
        "year_values": [value],
        "year_numeric_tooltips": [value],
        "year_row_ids": [None],
    }


def test_kaliningrad_sync_area_variant_row_keeps_plain_label():
    rows = [_kaliningrad_sync_area_variant_row(value="10.0")]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)

    assert rows[0]["entity_label"] == "Синхронная зона Калининградской области"
    assert rows[0]["pd_ec_entity_label_compact"] == "Синхронная зона Калининградской области"
    assert rows[0]["pd_ec_entity_label_compact_nt"] == "Синхронная зона Калининградской области"
    assert rows[0]["pd_ec_entity_label_compact_nt_gaes"] == (
        "Синхронная зона Калининградской области"
    )
    assert rows[0].get("pd_ec_nt_without_row") is False
    assert rows[0].get("pd_ec_gaes_without_row") is False
    assert rows[0].get("pd_ec_nt_extra_row") is False
    assert rows[0].get("pd_ec_gaes_extra_row") is False


def test_mask_kaliningrad_sync_area_null_variant_year_bounds_from_2025(monkeypatch):
    years = [2024, 2025, 2026]
    row = {
        "entity_label": "Синхронная зона Калининградской области",
        "demand_model_name": "SynchronousAreaEnergyConsumptionParameter",
        "perimeter_variant_code": None,
        "year_values": ["10", "20", "30"],
        "year_numeric_tooltips": ["10", "20", "30"],
        "year_row_ids": [1, 2, 3],
    }
    monkeypatch.setattr(
        service,
        "kaliningrad_sync_area_year_bounds",
        lambda: (2025, None),
    )
    service.mask_summary_rows_perimeter_variant_year_display([row], years)
    assert row["perimeter_variant_from_year"] == 2025
    assert row["year_values"] == ["—", "20", "30"]
    assert row["year_row_ids"] == [None, 2, 3]


def test_expand_kaliningrad_sync_area_keeps_null_perimeter_variant(monkeypatch):
    from app.common.perimeter_variant.registry_types import (
        EntityPerimeterBinding,
        PerimeterVariantDefinition,
    )

    entity = service.SummaryEntity(
        label="Синхронная зона Калининградской области",
        depth=0,
        parameters=[],
        demand_rows=[],
        entity_kind="synchronous_area",
        demand_model_name="SynchronousAreaEnergyConsumptionParameter",
        parent_fk_column="id_synchronous_area",
        parent_id=41,
    )
    binding = EntityPerimeterBinding(
        entity_kind="synchronous_area",
        entity_name_cf="синхронная зона калининградской области",
        entity_name="Синхронная зона Калининградской области",
        variants=(
            PerimeterVariantDefinition(
                "without_nt_without_gaes_kaliningrad",
                "без НТ без заряда ГАЭС (Калин)",
                effective_from_year=2025,
            ),
        ),
    )
    monkeypatch.setattr(
        service,
        "resolve_entity_perimeter_binding",
        lambda *_a, **_k: binding,
    )
    monkeypatch.setattr(
        service.dps,
        "peek_stored_perimeter_variant_code_for_parent",
        lambda *_a, **_k: None,
    )
    out = service._expand_summary_entity_perimeter_variants(
        entity,
        binding_entity_kind="synchronous_area",
        binding_entity_name="Синхронная зона Калининградской области",
        expand=True,
        tree_years=[2024, 2025],
    )
    assert len(out) == 1
    assert out[0].perimeter_variant_code is None


def test_expand_kaliningrad_sync_area_applies_stored_perimeter_variant(monkeypatch):
    entity = service.SummaryEntity(
        label="Синхронная зона Калининградской области",
        depth=0,
        parameters=[],
        demand_rows=[],
        entity_kind="synchronous_area",
        demand_model_name="SynchronousAreaEnergyConsumptionParameter",
        parent_fk_column="id_synchronous_area",
        parent_id=41,
    )
    monkeypatch.setattr(
        service.dps,
        "peek_stored_perimeter_variant_code_for_parent",
        lambda *_a, **_k: "without_nt_without_gaes_kaliningrad",
    )
    monkeypatch.setattr(
        service.dps,
        "get_demand_rows",
        lambda *_a, **_k: ["row"],
    )
    out = service._expand_summary_entity_perimeter_variants(
        entity,
        binding_entity_kind="synchronous_area",
        binding_entity_name="Синхронная зона Калининградской области",
        expand=True,
        tree_years=[2024, 2025],
    )
    assert len(out) == 1
    assert out[0].perimeter_variant_code == "without_nt_without_gaes_kaliningrad"
    assert out[0].demand_rows == ["row"]


def test_validate_kaliningrad_sync_area_allows_null_perimeter_variant():
    from app.common.perimeter_variant.registry import validate_perimeter_variant_for_entity

    assert (
        validate_perimeter_variant_for_entity(
            "synchronous_area",
            "Синхронная зона Калининградской области",
            None,
        )
        is None
    )



def test_apply_kaliningrad_sa_from_kaliningrad_es_formula_fills_variant_row(monkeypatch):
    years = [2025]
    row = _kaliningrad_sync_area_variant_row(value="0.0")
    rows = [row]

    monkeypatch.setattr(
        service,
        "_resolve_kaliningrad_synchronous_area_id",
        lambda: 3,
    )
    monkeypatch.setattr(
        service,
        "_resolve_regional_energy_system_id_by_name_cf",
        lambda _name: 99,
    )
    monkeypatch.setattr(
        service,
        "_year_values_from_parent_demand_rows",
        lambda *_args, **_kwargs: {2025: Decimal("42.5")},
    )

    service.apply_kaliningrad_sa_from_kaliningrad_es_formula(rows, years, rounding_digits=1)

    assert service._raw_year_values_from_summary_row(row, years) == {2025: Decimal("42.5")}


def test_reorder_centralized_zone_russia_variant_blocks_in_summary_rows():
    def _block(code: str, label: str) -> list[dict]:
        return [
            {
                "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
                "entity_label": label,
                "demand_model_name": "CentralizedZoneEnergyConsumptionParameter",
                "perimeter_variant_code": code,
                "parameter_key": "energy_consumption_mln_kvt_ch",
                "show_entity_cell": True,
                "entity_rowspan": 1,
                "entity_depth": 0,
            }
        ]

    rows = (
        _block("without_nt", "ЦЗ России без НТ")
        + _block("o1_without_nt", "ЦЗ России без НТ")
        + _block("with_nt", "ЦЗ России с НТ")
        + _block("o1_with_nt", "ЦЗ России с НТ")
    )
    service.reorder_centralized_zone_russia_variant_blocks_in_summary_rows(rows)
    codes = [r["perimeter_variant_code"] for r in rows if r.get("show_entity_cell")]
    assert codes == ["with_nt", "o1_with_nt", "without_nt", "o1_without_nt"]


def test_order_variants_with_gaes_charge_rows_pairs_o1_after_base_nt_group():
    """ЦЗ России на сводной таблице: с НТ, с НТ О-1, без НТ, без НТ О-1."""

    def _variant(code: str) -> service.SummaryEntity:
        return service.SummaryEntity(
            label=service.CENTRALIZED_ZONE_AGGREGATE_NAME,
            depth=0,
            parameters=service.PARAMETERS_ENERGY_CONSUMPTION,
            demand_rows=[],
            perimeter_variant_code=code,
        )

    shuffled = [
        _variant("without_nt"),
        _variant("o1_without_nt"),
        _variant("with_nt"),
        _variant("o1_with_nt"),
    ]
    charge_marker = service._gaes_charge_marker_entity(shuffled[0])

    ordered = service._order_variants_with_gaes_charge_rows(shuffled, charge_marker)
    variant_codes = [
        str(entity.perimeter_variant_code)
        for entity in ordered
        if entity.perimeter_variant_code
    ]

    assert variant_codes == ["with_nt", "o1_with_nt", "without_nt", "o1_without_nt"]
    charge_indices = [
        index
        for index, entity in enumerate(ordered)
        if entity.perimeter_variant_code is None
    ]
    assert charge_indices == [2]
    assert ordered[1].perimeter_variant_code == "o1_with_nt"
    assert ordered[3].perimeter_variant_code == "without_nt"


def test_order_first_sa_kaliningrad_variants_for_summary_table():
    def _variant(code: str) -> service.SummaryEntity:
        return service.SummaryEntity(
            label="Первая синхронная зона",
            depth=0,
            parameters=service.PARAMETERS_ENERGY_CONSUMPTION,
            demand_rows=[],
            perimeter_variant_code=code,
        )

    shuffled = [
        _variant(service._FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_VARIANT),
        _variant(service._FIRST_SA_WITH_NT_WITH_GAES_WITH_KALININGRAD_VARIANT),
        _variant(service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_VARIANT),
        _variant(service._FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITH_KALININGRAD_VARIANT),
        _variant(service._FIRST_SA_WITH_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_VARIANT),
        _variant(service.CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES),
    ]
    charge_marker = service._gaes_charge_marker_entity(shuffled[0])

    ordered = service._order_variants_with_gaes_charge_rows(shuffled, charge_marker)
    variant_codes = [
        str(entity.perimeter_variant_code)
        for entity in ordered
        if entity.perimeter_variant_code
    ]

    assert variant_codes == [
        service._FIRST_SA_WITH_NT_WITH_GAES_WITH_KALININGRAD_VARIANT,
        service._FIRST_SA_WITH_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_VARIANT,
        service.CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES,
        service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_VARIANT,
        service._FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITH_KALININGRAD_VARIANT,
        service._FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_VARIANT,
    ]


def test_apply_first_sa_without_nt_without_gaes_with_kaliningrad_diff_formula(monkeypatch):
    years = [2024]
    first_sa_id = 39
    monkeypatch.setattr(service, "_resolve_first_synchronous_area_id", lambda: first_sa_id)
    source_row = {
        "demand_model_name": "SynchronousAreaEnergyConsumptionParameter",
        "parent_fk_column": "id_synchronous_area",
        "parent_id": first_sa_id,
        "entity_kind": "perimeter_variant",
        "entity_label": "Первая синхронная зона",
        "perimeter_variant_code": service.CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES,
        "perimeter_variant_to_year": 2024,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "year_values": ["100.0"],
        "year_numeric_tooltips": ["100.0"],
    }
    target_row = {
        "demand_model_name": "SynchronousAreaEnergyConsumptionParameter",
        "parent_fk_column": "id_synchronous_area",
        "parent_id": first_sa_id,
        "entity_kind": "perimeter_variant",
        "entity_label": "Первая синхронная зона",
        "perimeter_variant_code": service._FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITH_KALININGRAD_VARIANT,
        "perimeter_variant_to_year": 2024,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "year_values": ["0.0"],
        "year_numeric_tooltips": ["0.0"],
    }
    gaes_row = {
        "demand_model_name": "SynchronousAreaEnergyConsumptionParameter",
        "parent_fk_column": "id_synchronous_area",
        "parent_id": first_sa_id,
        "entity_kind": "synchronous_area",
        "entity_label": "Первая синхронная зона без НТ (заряд ГАЭС)",
        "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
        "gaes_charge_row_station_name": "всего",
        "year_values": ["12.0"],
        "year_numeric_tooltips": ["12.0"],
    }
    rows = [source_row, gaes_row, target_row]

    service.apply_first_sa_without_nt_without_gaes_with_kaliningrad_diff_formula(
        rows,
        years,
        rounding_digits=1,
    )

    assert service._raw_year_values_from_summary_row(target_row, years) == {
        2024: Decimal("88.0")
    }
    assert target_row["gaes_without_charge_formula_kind"] == (
        "first_sa_without_nt_with_kaliningrad_gaes_diff"
    )
    assert target_row["pd_ec_formula_derived_row"] is True


def test_apply_first_sa_with_nt_with_gaes_with_kaliningrad_sum_formula(monkeypatch):
    years = [2024]
    first_sa_id = 39
    monkeypatch.setattr(service, "_resolve_first_synchronous_area_id", lambda: first_sa_id)
    target_row = {
        "demand_model_name": "SynchronousAreaEnergyConsumptionParameter",
        "parent_fk_column": "id_synchronous_area",
        "parent_id": first_sa_id,
        "entity_kind": "perimeter_variant",
        "entity_label": "Первая синхронная зона",
        "perimeter_variant_code": service._FIRST_SA_WITH_NT_WITH_GAES_WITH_KALININGRAD_VARIANT,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "year_values": ["0.0"],
        "year_numeric_tooltips": ["0.0"],
    }
    rows = [target_row]

    monkeypatch.setattr(
        service,
        "_year_values_sum_ues_in_first_sa_with_nt_with_gaes_with_kaliningrad_es",
        lambda *_args, **_kwargs: {2024: Decimal("100.0")},
    )
    monkeypatch.setattr(
        service,
        "_new_territories_parameter_year_values",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("NT subjects must not be added separately")
        ),
    )
    monkeypatch.setattr(
        service,
        "_gaes_charge_year_values_for_first_sa_with_nt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("GAES charge must not be added to with_nt with_gaes sum")
        ),
    )

    service.apply_first_sa_with_nt_with_gaes_with_kaliningrad_sum_formula(
        rows,
        years,
        rounding_digits=1,
    )

    assert service._raw_year_values_from_summary_row(target_row, years) == {
        2024: Decimal("100.0")
    }
    assert target_row["pd_ec_formula_derived_row"] is True


def test_first_sa_without_kaliningrad_ues_sum_uses_south_with_gaes_others_without_nt(
    monkeypatch,
):
    """Первая СЗ без НТ с ГАЭС: ОЭС Юга — with_gaes; остальные — как без НТ (без заряда)."""
    south_id = 7
    other_id = 8
    nt_id = 9
    first_sa_id = 39
    years = [2024]
    variants_tried: dict[int, list[str | None]] = {}

    monkeypatch.setattr(
        service,
        "_first_sa_without_nt_ues_exclude_ids",
        lambda: frozenset({nt_id}),
    )
    monkeypatch.setattr(
        service,
        "_resolve_new_territories_union_energy_system_id",
        lambda: nt_id,
    )
    monkeypatch.setattr(
        service,
        "_resolve_union_energy_system_id_by_name_cf",
        lambda name_cf: south_id if name_cf == service.SOUTH_UES_NAME_CF else None,
    )
    monkeypatch.setattr(
        service,
        "_union_energy_system_ids_for_synchronous_area",
        lambda _sa_id: [south_id, other_id, nt_id],
    )

    class _DemandRow:
        def __init__(self, value: Decimal):
            self.year_number = 2024
            self.energy_consumption_mln_kvt_ch = value

    def fake_get_demand_rows(_model, _fk_col, ues_id, perimeter_variant_code=None):
        variants_tried.setdefault(int(ues_id), []).append(perimeter_variant_code)
        if int(ues_id) == south_id:
            if perimeter_variant_code == service.CODE_WITHOUT_NT_WITH_GAES:
                return [_DemandRow(Decimal("12"))]
            if perimeter_variant_code == service.CODE_WITHOUT_NT:
                return [_DemandRow(Decimal("5"))]
            return []
        if int(ues_id) == other_id:
            if perimeter_variant_code == service.CODE_WITHOUT_NT:
                return [_DemandRow(Decimal("20"))]
            if perimeter_variant_code == service.CODE_WITHOUT_NT_WITH_GAES:
                return [_DemandRow(Decimal("99"))]
            return []
        return []

    monkeypatch.setattr(service.dps, "get_demand_rows", fake_get_demand_rows)

    result = service._year_values_sum_ues_in_first_sa_without_kaliningrad_es(
        first_sa_id,
        years,
        "energy_consumption_mln_kvt_ch",
    )

    assert variants_tried[south_id][0] == service.CODE_WITHOUT_NT_WITH_GAES
    assert service.CODE_WITHOUT_NT not in variants_tried[south_id]
    assert variants_tried[other_id][0] == service.CODE_WITHOUT_NT
    assert service.CODE_WITHOUT_NT_WITH_GAES not in variants_tried[other_id]
    assert nt_id not in variants_tried
    assert result == {2024: Decimal("32")}


def test_apply_first_sa_without_nt_with_gaes_without_kaliningrad_sum_formula_uses_ues_sum_only(
    monkeypatch,
):
    years = [2024]
    first_sa_id = 39
    monkeypatch.setattr(service, "_resolve_first_synchronous_area_id", lambda: first_sa_id)
    target_row = {
        "demand_model_name": "SynchronousAreaEnergyConsumptionParameter",
        "parent_fk_column": "id_synchronous_area",
        "parent_id": first_sa_id,
        "entity_kind": "perimeter_variant",
        "entity_label": "Первая синхронная зона",
        "perimeter_variant_code": service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_VARIANT,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "year_values": ["0.0"],
        "year_numeric_tooltips": ["0.0"],
    }
    rows = [target_row]

    monkeypatch.setattr(
        service,
        "_year_values_sum_ues_in_first_sa_without_kaliningrad_es",
        lambda *_args, **_kwargs: {2024: Decimal("1087532.4")},
    )
    monkeypatch.setattr(
        service,
        "_gaes_charge_year_values_for_first_sa_without_nt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("GAES charge must not be added separately")
        ),
    )

    service.apply_first_sa_without_nt_with_gaes_without_kaliningrad_sum_formula(
        rows,
        years,
        rounding_digits=1,
    )

    assert service._raw_year_values_from_summary_row(target_row, years) == {
        2024: Decimal("1087532.4")
    }


def test_first_sa_without_nt_without_gaes_without_kaliningrad_excludes_gaes_charge(
    monkeypatch,
):
    years = [2024]
    first_sa_id = 39
    gaes = Decimal("12")
    ues_with_gaes = Decimal("112")

    monkeypatch.setattr(service, "_resolve_first_synchronous_area_id", lambda: first_sa_id)
    monkeypatch.setattr(
        service,
        "_year_values_sum_ues_in_first_sa_without_kaliningrad_es",
        lambda *_args, **_kwargs: {2024: ues_with_gaes},
    )
    monkeypatch.setattr(
        service,
        "_gaes_charge_year_values_for_first_sa_without_nt",
        lambda *_args, **_kwargs: {2024: gaes},
    )

    with_gaes_row = {
        "demand_model_name": "SynchronousAreaEnergyConsumptionParameter",
        "parent_fk_column": "id_synchronous_area",
        "parent_id": first_sa_id,
        "entity_kind": "perimeter_variant",
        "entity_label": "Первая синхронная зона",
        "perimeter_variant_code": service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_VARIANT,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "year_values": ["0.0"],
        "year_numeric_tooltips": ["0.0"],
    }
    without_gaes_row = {
        "demand_model_name": "SynchronousAreaEnergyConsumptionParameter",
        "parent_fk_column": "id_synchronous_area",
        "parent_id": first_sa_id,
        "entity_kind": "perimeter_variant",
        "entity_label": "Первая синхронная зона",
        "perimeter_variant_code": (
            service._FIRST_SA_WITHOUT_NT_WITHOUT_GAES_WITHOUT_KALININGRAD_VARIANT
        ),
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "year_values": ["0.0"],
        "year_numeric_tooltips": ["0.0"],
    }
    gaes_row = {
        "demand_model_name": "SynchronousAreaEnergyConsumptionParameter",
        "parent_fk_column": "id_synchronous_area",
        "parent_id": first_sa_id,
        "entity_kind": "synchronous_area",
        "entity_label": "Первая синхронная зона без НТ (заряд ГАЭС)",
        "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
        "gaes_charge_row_station_name": "всего",
        "year_values": ["12.0"],
        "year_numeric_tooltips": ["12.0"],
    }
    rows = [with_gaes_row, gaes_row, without_gaes_row]

    service.apply_first_sa_without_nt_with_gaes_without_kaliningrad_sum_formula(
        rows,
        years,
        rounding_digits=1,
    )
    assert service._raw_year_values_from_summary_row(with_gaes_row, years) == {
        2024: ues_with_gaes
    }

    service.apply_first_sa_without_nt_without_gaes_without_kaliningrad_diff_formula(
        rows,
        years,
        rounding_digits=1,
    )
    assert service._raw_year_values_from_summary_row(without_gaes_row, years) == {
        2024: ues_with_gaes - gaes
    }


def test_build_federal_district_res_entity_shows_subjects_when_multiple_in_fd(monkeypatch):
    monkeypatch.setattr(
        service.dps,
        "get_demand_rows",
        lambda *args, **kwargs: [],
    )

    class _EU:
        pass

    class _RD:
        pass

    class _RES:
        pass

    eu1 = _EU()
    eu1.id = 501
    eu1.name = "ЭУ 1"
    eu1.id_regional_energy_system = 1
    rd1 = _RD()
    rd1.id = 101
    rd1.name = "Субъект 1"
    rd1.energy_units = [eu1]
    rd2 = _RD()
    rd2.id = 102
    rd2.name = "Субъект 2"
    rd2.energy_units = []
    res = _RES()
    res.id = 1
    res.name = "РЭС тест"
    res.regional_districts = [rd1, rd2]
    res.energy_units = []

    entity = service._build_federal_district_res_entity(
        res,
        federal_district_id=10,
        fd_rd_ids={101, 102},
    )
    assert len(entity.children) == 2
    assert entity.children[0].demand_model_name == (
        service.RegionalDistrictEnergyConsumptionParameter.__name__
    )
    assert entity.children[1].id_regional_district == 102
    assert len(entity.children[0].children) == 1
    assert entity.children[0].children[0].demand_model_name == (
        service.EnergyUnitEnergyConsumptionParameter.__name__
    )
    assert entity.children[0].children[0].id_energy_unit == 501


def test_build_federal_district_res_entity_shows_energy_units_when_single_subject_in_fd(monkeypatch):
    monkeypatch.setattr(
        service.dps,
        "get_demand_rows",
        lambda *args, **kwargs: [],
    )

    class _EU:
        pass

    class _RD:
        pass

    class _RES:
        pass

    eu1 = _EU()
    eu1.id = 501
    eu1.name = "ЭУ 1"
    eu1.id_regional_energy_system = 1
    rd1 = _RD()
    rd1.id = 101
    rd1.name = "Субъект 1"
    rd1.energy_units = [eu1]
    rd2 = _RD()
    rd2.id = 102
    rd2.name = "Субъект 2"
    rd2.energy_units = []
    res = _RES()
    res.id = 1
    res.name = "РЭС тест"
    res.regional_districts = [rd1, rd2]
    res.energy_units = []

    entity = service._build_federal_district_res_entity(
        res,
        federal_district_id=10,
        fd_rd_ids={101},
    )
    assert len(entity.children) == 1
    assert entity.children[0].demand_model_name == (
        service.EnergyUnitEnergyConsumptionParameter.__name__
    )
    assert entity.children[0].id_energy_unit == 501
    assert entity.id_regional_district == 101


def test_build_federal_district_res_entity_hides_subjects_when_single_in_fd(monkeypatch):
    monkeypatch.setattr(
        service.dps,
        "get_demand_rows",
        lambda *args, **kwargs: [],
    )

    class _RD:
        pass

    class _RES:
        pass

    rd1 = _RD()
    rd1.id = 101
    rd1.name = "Субъект 1"
    rd1.energy_units = []
    rd2 = _RD()
    rd2.id = 102
    rd2.name = "Субъект 2"
    rd2.energy_units = []
    res = _RES()
    res.id = 1
    res.name = "РЭС тест"
    res.regional_districts = [rd1, rd2]
    res.energy_units = []

    entity = service._build_federal_district_res_entity(
        res,
        federal_district_id=10,
        fd_rd_ids={101},
    )
    assert entity.children == []
    assert entity.id_regional_district == 101


def test_prune_summary_entities_fo_filters_by_res_within_fd():
    fd = service.SummaryEntity(
        label="ФО 1",
        depth=0,
        parameters=(),
        demand_rows=[],
        entity_kind="group",
        children=[
            service.SummaryEntity(
                label="РЭС A",
                depth=1,
                parameters=(),
                demand_rows=[],
                entity_kind="child",
                id_federal_district=1,
                id_regional_energy_system=10,
            ),
            service.SummaryEntity(
                label="РЭС B",
                depth=1,
                parameters=(),
                demand_rows=[],
                entity_kind="child",
                id_federal_district=1,
                id_regional_energy_system=11,
            ),
        ],
        id_federal_district=1,
    )
    pruned = service.prune_summary_entities_fo([fd], frozenset({1}), frozenset({10}))
    assert len(pruned) == 1
    assert len(pruned[0].children) == 1
    assert pruned[0].children[0].id_regional_energy_system == 10


def test_prune_summary_entities_fo_res_only_flat_mode():
    fd = service.SummaryEntity(
        label="ФО 1",
        depth=0,
        parameters=(),
        demand_rows=[],
        entity_kind="group",
        children=[
            service.SummaryEntity(
                label="РЭС A",
                depth=1,
                parameters=(),
                demand_rows=[],
                entity_kind="child",
                id_federal_district=1,
                id_regional_energy_system=10,
            ),
        ],
        id_federal_district=1,
    )
    pruned = service.prune_summary_entities_fo([fd], frozenset(), frozenset({10}))
    assert len(pruned) == 1
    assert pruned[0].depth == 0
    assert pruned[0].label == "РЭС A"
    assert pruned[0].id_regional_energy_system == 10


def test_energy_units_for_federal_district_subject_appends_placeholder_res_units():
    class _RES:
        pass

    class _EU:
        pass

    placeholder_res = _RES()
    placeholder_res.name = "не указано"
    valid_res_id = 590

    eu_valid = _EU()
    eu_valid.id = 77
    eu_valid.name = "Центральный энергорайон"
    eu_valid.id_regional_energy_system = valid_res_id

    eu_placeholder_a = _EU()
    eu_placeholder_a.id = 359
    eu_placeholder_a.name = "Озерновский энергорайон"
    eu_placeholder_a.id_regional_energy_system = 569
    eu_placeholder_a.regional_energy_system = placeholder_res

    eu_placeholder_b = _EU()
    eu_placeholder_b.id = 367
    eu_placeholder_b.name = "Южные электрические сети"
    eu_placeholder_b.id_regional_energy_system = 569
    eu_placeholder_b.regional_energy_system = placeholder_res

    result = service._energy_units_for_federal_district_subject(
        [eu_placeholder_a, eu_valid, eu_placeholder_b],
        valid_res_id,
    )
    assert [eu.id for eu in result] == [77, 359, 367]


def test_build_federal_district_res_entity_appends_placeholder_energy_units(monkeypatch):
    monkeypatch.setattr(
        service.dps,
        "get_demand_rows",
        lambda *args, **kwargs: [],
    )

    class _RES:
        pass

    class _EU:
        pass

    class _RD:
        pass

    placeholder_res = _RES()
    placeholder_res.name = "не указано"

    eu_valid = _EU()
    eu_valid.id = 77
    eu_valid.name = "Центральный энергорайон"
    eu_valid.id_regional_energy_system = 1

    eu_placeholder = _EU()
    eu_placeholder.id = 359
    eu_placeholder.name = "Озерновский энергорайон"
    eu_placeholder.id_regional_energy_system = 569
    eu_placeholder.regional_energy_system = placeholder_res

    rd1 = _RD()
    rd1.id = 101
    rd1.name = "Камчатский край"
    rd1.energy_units = [eu_valid, eu_placeholder]

    res = _RES()
    res.id = 1
    res.name = "ЭС Камчатского края"
    res.regional_districts = [rd1]
    res.energy_units = []

    entity = service._build_federal_district_res_entity(
        res,
        federal_district_id=10,
        fd_rd_ids={101},
    )
    assert len(entity.children) == 2
    assert [child.id_energy_unit for child in entity.children] == [77, 359]
    assert entity.children[1].id_regional_energy_system == 1


def test_build_energy_unit_entities_uses_o1_for_placeholder_res(monkeypatch):
    captured: list[str | None] = []

    def _fake_get_demand_rows(model, fk_column, parent_id, *, perimeter_variant_code=None):
        captured.append(perimeter_variant_code)
        return []

    monkeypatch.setattr(service.dps, "get_demand_rows", _fake_get_demand_rows)

    class _RES:
        pass

    class _EU:
        pass

    placeholder_res = _RES()
    placeholder_res.name = "не указано"

    eu = _EU()
    eu.id = 359
    eu.name = "Озерновский энергорайон"
    eu.id_regional_energy_system = 569
    eu.regional_energy_system = placeholder_res

    entities = service._build_energy_unit_entities([eu], depth=3, id_regional_energy_system=590)
    assert len(entities) == 1
    assert entities[0].perimeter_variant_code == "o1"
    assert entities[0].is_decentralized_zone_energy_unit is True
    assert captured == ["o1"]


def test_flatten_entity_marks_decentralized_zone_energy_units(monkeypatch):
    monkeypatch.setattr(
        service,
        "perimeter_entity_context_for_model",
        lambda *_a, **_k: None,
    )
    entity = service.SummaryEntity(
        label="Озерновский энергорайон",
        depth=3,
        parameters=service.PARAMETERS_ENERGY_CONSUMPTION[:2],
        demand_rows=[],
        entity_kind="child",
        demand_model_name=service.EnergyUnitEnergyConsumptionParameter.__name__,
        parent_fk_column="id_energy_unit",
        parent_id=359,
        id_energy_unit=359,
        perimeter_variant_code="o1",
        is_decentralized_zone_energy_unit=True,
    )
    rows = service._flatten_entity(entity, years=[2024], rounding_digits=1)
    assert len(rows) == 2
    assert all(row.get("pd_ec_decentralized_zone_mark") for row in rows)
    assert all(row.get("pd_ec_o1_form_row") is None for row in rows)


def test_build_regional_energy_system_entity_uses_variant_fallback_loader(
    monkeypatch,
):
    monkeypatch.setattr(
        service.dps,
        "get_demand_rows_with_single_variant_fallback",
        lambda *_a, **_k: ["merged"],
    )

    class _RES:
        pass

    res = _RES()
    res.id = 601
    res.name = "ЭС Магаданской области"
    res.regional_districts = []
    res.energy_units = []

    entity = service._build_regional_energy_system_entity(res, ues_id=10)
    assert entity.demand_rows == ["merged"]
    assert entity.perimeter_variant_code is None


def test_expand_o1_subject_perimeter_variants_puts_o1_before_base(monkeypatch):
    captured: list[str | None] = []

    def _fake_get_demand_rows(model, fk_column, parent_id, *, perimeter_variant_code=None):
        captured.append(perimeter_variant_code)
        return [{"pvc": perimeter_variant_code}]

    class _Binding:
        variants = (type("V", (), {"code": "o1"})(),)

    monkeypatch.setattr(service.dps, "get_demand_rows", _fake_get_demand_rows)
    monkeypatch.setattr(
        service,
        "perimeter_entity_context_for_model",
        lambda *_a, **_k: ("regional_energy_system", "ЭС Камчатского края"),
    )
    monkeypatch.setattr(
        service,
        "resolve_entity_perimeter_binding",
        lambda *_a, **_k: _Binding(),
    )

    child = service.SummaryEntity(
        label="Центральный энергорайон",
        depth=3,
        parameters=service.PARAMETERS_ENERGY_CONSUMPTION[:1],
        demand_rows=[],
        entity_kind="child",
        demand_model_name=service.EnergyUnitEnergyConsumptionParameter.__name__,
        parent_fk_column="id_energy_unit",
        parent_id=10,
    )
    base = service.SummaryEntity(
        label="ЭС Камчатского края",
        depth=2,
        parameters=service.PARAMETERS_ENERGY_CONSUMPTION[:1],
        demand_rows=[{"pvc": None}],
        entity_kind="child",
        children=[child],
        demand_model_name=service.RegionalEnergySystemEnergyConsumptionParameter.__name__,
        parent_fk_column="id_regional_energy_system",
        parent_id=601,
    )

    expanded = service._expand_summary_entities_o1_subject_perimeter_variants([base])
    assert len(expanded) == 2
    assert expanded[0].perimeter_variant_code == "o1"
    assert expanded[0].children == []
    assert expanded[0].demand_rows == [{"pvc": "o1"}]
    assert expanded[1].perimeter_variant_code is None
    assert len(expanded[1].children) == 1
    assert captured == ["o1"]


def test_expand_o1_subject_perimeter_variants_skips_without_o1_binding(monkeypatch):
    monkeypatch.setattr(
        service,
        "perimeter_entity_context_for_model",
        lambda *_a, **_k: ("regional_energy_system", "ЭС Амурской области"),
    )
    monkeypatch.setattr(
        service,
        "resolve_entity_perimeter_binding",
        lambda *_a, **_k: None,
    )

    base = service.SummaryEntity(
        label="ЭС Амурской области",
        depth=2,
        parameters=service.PARAMETERS_ENERGY_CONSUMPTION[:1],
        demand_rows=[],
        entity_kind="child",
        demand_model_name=service.RegionalEnergySystemEnergyConsumptionParameter.__name__,
        parent_fk_column="id_regional_energy_system",
        parent_id=100,
    )
    expanded = service._expand_summary_entities_o1_subject_perimeter_variants([base])
    assert expanded == [base]


def test_build_regional_energy_system_entity_shows_energy_units_when_single_subject(
    monkeypatch,
):
    monkeypatch.setattr(
        service.dps,
        "get_demand_rows",
        lambda *args, **kwargs: [],
    )

    class _EU:
        pass

    class _RD:
        pass

    class _RES:
        pass

    eu1 = _EU()
    eu1.id = 501
    eu1.name = "ЭУ 1"
    eu1.id_regional_energy_system = 1
    rd1 = _RD()
    rd1.id = 101
    rd1.name = "Субъект 1"
    rd1.energy_units = [eu1]
    res = _RES()
    res.id = 1
    res.name = "РЭС тест"
    res.regional_districts = [rd1]
    res.energy_units = []

    entity = service._build_regional_energy_system_entity(res, ues_id=10)
    assert len(entity.children) == 1
    assert entity.children[0].demand_model_name == (
        service.EnergyUnitEnergyConsumptionParameter.__name__
    )
    assert entity.children[0].id_energy_unit == 501
    assert entity.id_regional_district == 101


def test_build_regional_energy_system_entity_appends_placeholder_energy_units(
    monkeypatch,
):
    monkeypatch.setattr(
        service.dps,
        "get_demand_rows",
        lambda *args, **kwargs: [],
    )

    class _RES:
        pass

    class _EU:
        pass

    class _RD:
        pass

    placeholder_res = _RES()
    placeholder_res.name = "не указано"

    eu_valid = _EU()
    eu_valid.id = 77
    eu_valid.name = "Центральный энергорайон"
    eu_valid.id_regional_energy_system = 1

    eu_placeholder = _EU()
    eu_placeholder.id = 359
    eu_placeholder.name = "Озерновский энергорайон"
    eu_placeholder.id_regional_energy_system = 569
    eu_placeholder.regional_energy_system = placeholder_res

    rd1 = _RD()
    rd1.id = 101
    rd1.name = "Камчатский край"
    rd1.energy_units = [eu_valid, eu_placeholder]

    res = _RES()
    res.id = 1
    res.name = "ЭС Камчатского края"
    res.regional_districts = [rd1]
    res.energy_units = []

    entity = service._build_regional_energy_system_entity(res, ues_id=10)
    assert len(entity.children) == 2
    assert [child.id_energy_unit for child in entity.children] == [77, 359]
    assert entity.children[1].id_regional_energy_system == 1


def test_build_ez_raw_entities_includes_summary_table_top_aggregates_when_expanded(
    monkeypatch,
):
    top_item = object()
    ez_item = object()
    monkeypatch.setattr(
        service,
        "_build_summary_table_top_aggregate_entities",
        lambda **kwargs: [top_item],
    )
    monkeypatch.setattr(service, "_build_energy_zone_entities", lambda: [ez_item])

    entities = service._build_ez_raw_entities(expand_entity_perimeter_variants=True)

    assert entities == [top_item, ez_item]


def test_build_summary_table_top_aggregate_entities_russia_first(monkeypatch):
    from unittest.mock import MagicMock

    russia = MagicMock(label="Россия")
    cz = MagicMock(label="ЦЗ")
    ees = MagicMock(label="ЭЭС")
    est = MagicMock(label="ЕЭС")
    sa = MagicMock(label="СЗ")

    monkeypatch.setattr(
        service,
        "_build_perimeter_aggregate_entities",
        lambda **kwargs: {
            service.ENTITY_KIND_RUSSIA_FEDERATION: [russia],
            service.ENTITY_KIND_CENTRALIZED_ZONE: [cz],
            service.ENTITY_KIND_EES_RUSSIA: [ees],
        }.get(kwargs["entity_kind"], []),
    )
    monkeypatch.setattr(
        service,
        "_build_energy_system_type_entities",
        lambda name, predicate, **kwargs: [est] if name == service.EES_UNIFIED_REF_NAME else [],
    )
    monkeypatch.setattr(service, "_build_synchronous_area_entities", lambda **k: [sa])

    entities = service._build_summary_table_top_aggregate_entities(
        include_russia_top_row=True,
        include_ees_russia_rows=True,
        include_synchronous_area_rows=True,
        russia_federation_first=True,
    )

    assert entities == [russia, cz, ees, est, sa]


def test_tag_summary_rows_before_federal_district_blocks():
    rows = [
        {
            "entity_label": "Россия",
            "show_entity_cell": True,
            "entity_depth": 0,
            "entity_kind": service.ENTITY_KIND_RUSSIA_FEDERATION,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "ЦЗ России",
            "show_entity_cell": True,
            "entity_depth": 0,
            "entity_kind": service.ENTITY_KIND_CENTRALIZED_ZONE,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "ЦФО",
            "show_entity_cell": True,
            "entity_depth": 0,
            "entity_kind": "group",
            "demand_model_name": "FederalDistrictEnergyConsumptionParameter",
            "parent_fk_column": "id_federal_district",
            "parent_id": 1,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "ЭС тест",
            "show_entity_cell": True,
            "entity_depth": 1,
            "demand_model_name": "RegionalEnergySystemEnergyConsumptionParameter",
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
    ]
    service.tag_energy_consumption_summary_rows_before_federal_district_blocks(rows)
    assert rows[0].get("pd_ec_summary_table_only_row") is True
    assert rows[1].get("pd_ec_summary_table_only_row") is True
    assert rows[2].get("pd_ec_summary_table_only_row") is not True
    assert rows[3].get("pd_ec_summary_table_only_row") is not True


def test_promote_taimyr_norilsk_first_among_tites_children():
    res_mn = "RegionalEnergySystemEnergyConsumptionParameter"
    eu_mn = "EnergyUnitEnergyConsumptionParameter"
    taimyr_label = (
        "Таймырский Долгано-Ненецкий муниципальный район, Туруханский район "
        "и городской округ г. Норильск Красноярского края"
    )
    kamchatka = service.SummaryEntity(
        label="ЭС Камчатского края",
        depth=1,
        parameters=(),
        demand_rows=[],
        demand_model_name=res_mn,
    )
    norilsk = service.SummaryEntity(
        label="ЭС г. Норильска Красноярского края",
        depth=1,
        parameters=(),
        demand_rows=[],
        demand_model_name=res_mn,
        children=[
            service.SummaryEntity(
                label=taimyr_label,
                depth=2,
                parameters=(),
                demand_rows=[],
                demand_model_name=eu_mn,
            )
        ],
    )
    ordered = service._promote_taimyr_norilsk_first_among_tites_children(
        [kamchatka, norilsk]
    )
    assert [e.label for e in ordered] == [
        "ЭС г. Норильска Красноярского края",
        "ЭС Камчатского края",
    ]


def test_tag_summary_rows_before_energy_zone_blocks():
    rows = [
        {
            "entity_label": "ЭЭС России",
            "show_entity_cell": True,
            "entity_depth": 0,
            "entity_kind": service.ENTITY_KIND_EES_RUSSIA,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
        {
            "entity_label": "Энергозона Сибири",
            "show_entity_cell": True,
            "entity_depth": 0,
            "entity_kind": "group",
            "demand_model_name": "EnergyZoneEnergyConsumptionParameter",
            "parent_fk_column": "id_energy_zone",
            "parent_id": 2,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
    ]
    service.tag_energy_consumption_summary_rows_before_energy_zone_blocks(rows)
    assert rows[0].get("pd_ec_summary_table_only_row") is True
    assert rows[1].get("pd_ec_summary_table_only_row") is not True


def test_remove_gaes_charge_preserves_summary_table_top_aggregate_rows():
    """На /summary/energy_zones/ заряд ГАЭС остаётся в общем верху до блоков ЭЗ."""
    from app.energy_consumption.services.energy_consumption_gaes_charge_summary_services import (
        remove_gaes_charge_rows_from_summary_context,
    )

    rows = [
        {
            "entity_label": "ЭЭС России с НТ (заряд ГАЭС)",
            "show_entity_cell": True,
            "entity_depth": 0,
            "entity_kind": service.ENTITY_KIND_EES_RUSSIA,
            "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
            "entity_rowspan": 1,
        },
        {
            "entity_label": "Энергозона Сибири",
            "show_entity_cell": True,
            "entity_depth": 0,
            "entity_kind": "group",
            "demand_model_name": "EnergyZoneEnergyConsumptionParameter",
            "parent_fk_column": "id_energy_zone",
            "parent_id": 2,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "entity_rowspan": 2,
        },
        {
            "entity_label": "Энергозона Сибири",
            "show_entity_cell": False,
            "entity_depth": 0,
            "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
            "entity_rowspan": 2,
        },
    ]
    out = remove_gaes_charge_rows_from_summary_context({"summary_rows": rows})
    labels = [
        (r.get("entity_label"), r.get("parameter_key"), r.get("show_entity_cell"))
        for r in out["summary_rows"]
    ]
    assert labels[0] == (
        "ЭЭС России с НТ (заряд ГАЭС)",
        service.GAES_CHARGE_PARAMETER_KEY,
        True,
    )
    assert labels[1] == (
        "Энергозона Сибири",
        "energy_consumption_mln_kvt_ch",
        True,
    )
    assert all(
        r.get("parameter_key") != service.GAES_CHARGE_PARAMETER_KEY
        for r in out["summary_rows"][1:]
    )


def test_tag_summary_table_energy_zone_footer_rows_hides_siberia_east_and_east_children():
    rows = [
        {
            "entity_label": "Энергозона Центра",
            "show_entity_cell": True,
            "entity_depth": 0,
        },
        {
            "entity_label": "Энергозона Сибири",
            "show_entity_cell": True,
            "entity_depth": 0,
        },
        {
            "entity_label": "Энергозона Сибири",
            "show_entity_cell": False,
            "entity_depth": 0,
        },
        {
            "entity_label": "Энергозона Востока",
            "show_entity_cell": True,
            "entity_depth": 0,
        },
        {
            "entity_label": "ЭС Амурской области",
            "show_entity_cell": True,
            "entity_depth": 1,
        },
        {
            "entity_label": "Другая зона",
            "show_entity_cell": True,
            "entity_depth": 0,
        },
    ]
    service.tag_summary_table_energy_zone_footer_rows(rows)
    assert rows[0].get("pd_ec_summary_table_only_row") is not True
    assert rows[1].get("pd_ec_summary_table_only_row") is True
    assert rows[1].get("pd_ec_o1_form_row") is True
    assert rows[1].get("pd_ec_show_o1_badge") is True
    assert rows[2].get("pd_ec_summary_table_only_row") is True
    assert rows[2].get("pd_ec_o1_form_row") is True
    assert not rows[2].get("pd_ec_show_o1_badge")
    assert rows[3].get("pd_ec_summary_table_only_row") is True
    assert rows[3].get("pd_ec_o1_form_row") is True
    assert rows[3].get("pd_ec_show_o1_badge") is True
    assert rows[4].get("pd_ec_summary_table_only_row") is True
    assert rows[4].get("pd_ec_o1_form_row") is not True
    assert rows[5].get("pd_ec_summary_table_only_row") is not True


def test_prune_one_ez_hides_ees_russia_when_filters_active():
    e = service.SummaryEntity(
        label=service.EES_RUSSIA_AGGREGATE_NAME,
        depth=0,
        parameters=tuple(),
        demand_rows=[],
        entity_kind=service.ENTITY_KIND_EES_RUSSIA,
    )
    assert service._prune_one_ez(e, frozenset({1}), frozenset()) is None
    assert service._prune_one_ez(e, frozenset(), frozenset()) is e


def test_apply_oes_tites_root_formula_sums_energy_units_excluding_o1(monkeypatch):
    tites_ues_id = 77
    monkeypatch.setattr(
        service,
        "_tites_union_energy_system_ids",
        lambda: frozenset({tites_ues_id}),
    )
    monkeypatch.setattr(
        service,
        "_tites_sakha_yakutia_extra_energy_unit_ids",
        lambda: frozenset(),
    )

    def _eu_row(*, label: str, value: str, pvc: str | None = None) -> dict:
        return {
            "entity_label": label,
            "entity_rowspan": 1,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "EnergyUnitEnergyConsumptionParameter",
            "id_union_energy_system": tites_ues_id,
            "perimeter_variant_code": pvc,
            "year_values": [value],
            "year_numeric_tooltips": [value],
        }

    eu_rows = [
        _eu_row(label="ЭР-1", value="10.0"),
        _eu_row(label="ЭР-2", value="5.0"),
        _eu_row(label="ЭР О-1", value="100.0", pvc="o1"),
    ]
    summary_rows = [
        {
            "entity_label": "ТИТЭС",
            "entity_rowspan": 2,
            "entity_depth": 0,
            "entity_kind": "group-root",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "parameter_label": "Потребление электрической энергии, млн кВтч",
            "demand_model_name": "EnergySystemTypeEnergyConsumptionParameter",
            "perimeter_variant_code": None,
            "year_values": ["0.0"],
            "year_numeric_tooltips": ["0.0"],
        },
        {
            "entity_label": "ТИТЭС",
            "entity_rowspan": 1,
            "entity_depth": 0,
            "entity_kind": "group-root",
            "show_entity_cell": False,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "demand_model_name": "EnergySystemTypeEnergyConsumptionParameter",
            "perimeter_variant_code": None,
            "year_values": ["0.0"],
            "year_numeric_tooltips": ["0.0"],
        },
        *eu_rows,
    ]

    service.apply_oes_tites_root_formula_to_summary_rows(
        summary_rows,
        years=[2024],
        rounding_digits=1,
        eu_source_rows=eu_rows,
    )

    mln_row = summary_rows[0]
    assert mln_row["year_values"] == ["15"]
    assert mln_row.get("pd_ec_formula_derived_row") is True
    assert mln_row.get("pd_ec_tites_oes_root") is True
    assert service._TITES_OES_FORMULA_TOOLTIP in str(
        mln_row.get("pd_ec_summary_row_formula_tooltip") or ""
    )


def test_apply_oes_tites_root_formula_includes_sakha_yakutia_extra_energy_units(monkeypatch):
    tites_ues_id = 77
    sakha_west_id = 78
    sakha_central_id = 80
    monkeypatch.setattr(
        service,
        "_tites_union_energy_system_ids",
        lambda: frozenset({tites_ues_id}),
    )
    monkeypatch.setattr(
        service,
        "_tites_sakha_yakutia_extra_energy_unit_ids",
        lambda: frozenset({sakha_west_id, sakha_central_id}),
    )

    def _eu_row(
        *,
        eu_id: int,
        ues_id: int,
        value: str,
        pvc: str | None = None,
    ) -> dict:
        return {
            "entity_label": "ЭР",
            "entity_rowspan": 1,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "EnergyUnitEnergyConsumptionParameter",
            "parent_fk_column": "id_energy_unit",
            "parent_id": eu_id,
            "id_union_energy_system": ues_id,
            "perimeter_variant_code": pvc,
            "year_values": [value],
            "year_numeric_tooltips": [value],
        }

    eu_rows = [
        _eu_row(eu_id=1, ues_id=tites_ues_id, value="10.0"),
        _eu_row(eu_id=sakha_west_id, ues_id=999, value="2966.0"),
        _eu_row(eu_id=sakha_central_id, ues_id=999, value="1660.0"),
        _eu_row(eu_id=79, ues_id=999, value="999.0"),
    ]
    summary_rows = [
        {
            "entity_label": "ТИТЭС",
            "entity_rowspan": 1,
            "entity_depth": 0,
            "entity_kind": "group-root",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "EnergySystemTypeEnergyConsumptionParameter",
            "perimeter_variant_code": None,
            "year_values": ["0.0"],
            "year_numeric_tooltips": ["0.0"],
        },
        *eu_rows,
    ]

    service.apply_oes_tites_root_formula_to_summary_rows(
        summary_rows,
        years=[2016],
        rounding_digits=1,
        eu_source_rows=eu_rows,
    )

    assert summary_rows[0]["year_values"] == ["4 636"]


def test_apply_oes_tites_root_formula_excludes_sakha_yakutia_extra_after_2018(
    monkeypatch,
):
    tites_ues_id = 77
    sakha_west_id = 78
    sakha_central_id = 80
    monkeypatch.setattr(
        service,
        "_tites_union_energy_system_ids",
        lambda: frozenset({tites_ues_id}),
    )
    monkeypatch.setattr(
        service,
        "_tites_sakha_yakutia_extra_energy_unit_ids",
        lambda: frozenset({sakha_west_id, sakha_central_id}),
    )

    def _eu_row(
        *,
        eu_id: int,
        ues_id: int,
        values: list[str],
    ) -> dict:
        return {
            "entity_label": "ЭР",
            "entity_rowspan": 1,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "EnergyUnitEnergyConsumptionParameter",
            "parent_fk_column": "id_energy_unit",
            "parent_id": eu_id,
            "id_union_energy_system": ues_id,
            "year_values": values,
            "year_numeric_tooltips": values,
        }

    eu_rows = [
        _eu_row(eu_id=1, ues_id=tites_ues_id, values=["10.0", "10.0"]),
        _eu_row(eu_id=sakha_west_id, ues_id=999, values=["100.0", "200.0"]),
        _eu_row(eu_id=sakha_central_id, ues_id=999, values=["50.0", "60.0"]),
    ]
    summary_rows = [
        {
            "entity_label": "ТИТЭС",
            "entity_rowspan": 1,
            "entity_depth": 0,
            "entity_kind": "group-root",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "EnergySystemTypeEnergyConsumptionParameter",
            "perimeter_variant_code": None,
            "year_values": ["0.0", "0.0"],
            "year_numeric_tooltips": ["0.0", "0.0"],
        },
        *eu_rows,
    ]

    service.apply_oes_tites_root_formula_to_summary_rows(
        summary_rows,
        years=[2018, 2019],
        rounding_digits=1,
        eu_source_rows=eu_rows,
    )

    assert summary_rows[0]["year_values"] == ["160", "10"]


def test_mask_sakha_yakutia_splits_years_between_tites_and_oes_east(monkeypatch):
    monkeypatch.setattr(
        service,
        "_tites_sakha_yakutia_extra_energy_unit_ids",
        lambda: frozenset({101}),
    )
    years = [2018, 2019]
    tites_row = {
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "id_energy_unit": 101,
        "parent_fk_column": "id_energy_unit",
        "parent_id": 101,
        "entity_kind": service._SAKHA_TITES_THROUGH_YEAR_ENTITY_KIND,
        "pd_ec_sakha_tites_through_year_row": True,
        "year_values": ["10", "20"],
        "year_numeric_tooltips": ["10", "20"],
        "year_row_ids": [1, 2],
    }
    oes_row = {
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "id_energy_unit": 101,
        "parent_fk_column": "id_energy_unit",
        "parent_id": 101,
        "entity_kind": "child",
        "year_values": ["10", "20"],
        "year_numeric_tooltips": ["10", "20"],
        "year_row_ids": [1, 2],
    }
    service.mask_sakha_yakutia_tites_oes_east_year_membership([tites_row, oes_row], years)
    assert tites_row["year_values"] == ["10", "—"]
    assert oes_row["year_values"] == ["—", "20"]
    assert oes_row.get("pd_ec_sakha_oes_east_from_year_row") is True


def test_build_tites_summary_entities_appends_sakha_extra_without_res(monkeypatch):
    res_child = service.SummaryEntity(
        label="ЭС ТИТЭС",
        depth=1,
        parameters=service.PARAMETERS_ENERGY_CONSUMPTION,
        demand_rows=[],
        entity_kind="child",
        demand_model_name="RegionalEnergySystemEnergyConsumptionParameter",
        parent_fk_column="id_regional_energy_system",
        parent_id=1,
        id_regional_energy_system=1,
    )
    tites_root = service.SummaryEntity(
        label="ТИТЭС",
        depth=0,
        parameters=service.PARAMETERS_ENERGY_CONSUMPTION,
        demand_rows=[],
        entity_kind="group-root",
        children=[res_child],
        demand_model_name="EnergySystemTypeEnergyConsumptionParameter",
        parent_fk_column="id_energy_system_type",
        parent_id=5,
    )
    sakha_west = service.SummaryEntity(
        label="Западный энергорайон",
        depth=1,
        parameters=service.PARAMETERS_ENERGY_CONSUMPTION,
        demand_rows=[],
        entity_kind=service._SAKHA_TITES_THROUGH_YEAR_ENTITY_KIND,
        demand_model_name="EnergyUnitEnergyConsumptionParameter",
        parent_fk_column="id_energy_unit",
        parent_id=101,
        id_energy_unit=101,
        sakha_yakutia_tites_through_year_row=True,
    )
    monkeypatch.setattr(
        service,
        "_build_energy_system_type_entities",
        lambda *a, **k: [tites_root],
    )
    monkeypatch.setattr(service, "_unwrap_hidden_tites_ues_entities", lambda xs: list(xs))
    monkeypatch.setattr(
        service,
        "_build_tites_sakha_yakutia_extra_energy_unit_entities",
        lambda *, depth: [replace(sakha_west, depth=depth)],
    )
    entities = service._build_tites_summary_entities_for_summary_table()
    assert len(entities) == 1
    children = entities[0].children
    assert len(children) == 2
    assert children[1].label == "Западный энергорайон"
    assert children[1].sakha_yakutia_tites_through_year_row is True
    assert children[1].id_regional_energy_system is None


def test_inject_oes_tites_aggregate_verification_row_at_table_bottom(monkeypatch):
    tites_ues_id = 77
    sakha_west_id = 78
    sakha_central_id = 80
    monkeypatch.setattr(
        service,
        "_tites_union_energy_system_ids",
        lambda: frozenset({tites_ues_id}),
    )
    monkeypatch.setattr(
        service,
        "_tites_sakha_yakutia_extra_energy_unit_ids",
        lambda: frozenset({sakha_west_id, sakha_central_id}),
    )

    def _eu_row(*, eu_id: int, ues_id: int, value: str) -> dict:
        return {
            "entity_label": "ЭР",
            "entity_rowspan": 1,
            "entity_depth": 3,
            "entity_kind": "child",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "EnergyUnitEnergyConsumptionParameter",
            "parent_fk_column": "id_energy_unit",
            "parent_id": eu_id,
            "id_union_energy_system": ues_id,
            "year_values": [value],
            "year_numeric_tooltips": [value],
        }

    eu_rows = [
        _eu_row(eu_id=1, ues_id=tites_ues_id, value="10.0"),
        _eu_row(eu_id=sakha_west_id, ues_id=999, value="2966.0"),
        _eu_row(eu_id=sakha_central_id, ues_id=999, value="1660.0"),
    ]
    summary_rows = [
        {
            "entity_label": "ТИТЭС",
            "entity_rowspan": 1,
            "entity_depth": 0,
            "entity_kind": "group-root",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "EnergySystemTypeEnergyConsumptionParameter",
            "perimeter_variant_code": None,
            "year_values": ["0.0"],
            "year_numeric_tooltips": ["0.0"],
        },
        *eu_rows,
    ]
    service.apply_oes_tites_root_formula_to_summary_rows(
        summary_rows,
        years=[2016],
        rounding_digits=1,
        eu_source_rows=eu_rows,
    )
    before_len = len(summary_rows)

    service.inject_oes_tites_aggregate_verification_row(
        summary_rows,
        source_rows=eu_rows,
        years=[2016],
        rounding_digits=1,
    )

    checks = [
        row
        for row in summary_rows
        if row.get("entity_kind") == "oes_tites_aggregate_check"
    ]
    assert checks
    assert summary_rows.index(checks[0]) == before_len
    check = next(
        row
        for row in checks
        if row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    )
    assert check["entity_kind"] == "oes_tites_aggregate_check"
    assert check["entity_label"] == "Проверка для ТИТЭС"
    assert check["parameter_key"] == "energy_consumption_mln_kvt_ch"
    assert check["year_values"] == ["0"]
    assert service._TITES_OES_AGGREGATE_VERIFICATION_TOOLTIP in str(
        check.get("pd_ec_verification_formula_tooltip") or ""
    )


def test_finalize_oes_max_summary_tites_skips_verification_on_summary_table(monkeypatch):
    from app.energy_consumption.pages._summary_page_transforms import (
        finalize_oes_max_summary_tites_formula,
    )

    monkeypatch.setattr(service, "_tites_union_energy_system_ids", lambda: frozenset())
    monkeypatch.setattr(
        service, "_tites_sakha_yakutia_extra_energy_unit_ids", lambda: frozenset()
    )

    summary_rows = [
        {
            "entity_label": "ТИТЭС",
            "entity_rowspan": 1,
            "entity_depth": 0,
            "entity_kind": "group-root",
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "demand_model_name": "EnergySystemTypeEnergyConsumptionParameter",
            "perimeter_variant_code": None,
            "year_values": ["0.0"],
            "year_numeric_tooltips": ["0.0"],
        },
    ]
    ctx = finalize_oes_max_summary_tites_formula(
        {
            "active_summary": "oes",
            "summary_table_standalone": True,
            "years": [2024],
            "rounding_digits": 1,
            "summary_rows": summary_rows,
            "_eu_source_rows_for_tites": list(summary_rows),
        }
    )
    assert not any(
        row.get("entity_kind") == "oes_tites_aggregate_check"
        for row in ctx.get("summary_rows") or []
    )


def test_is_sakha_yakutia_regional_energy_system_name():
    assert service._is_sakha_yakutia_regional_energy_system_name("ЭС Республики Саха (Якутия)")
    assert not service._is_sakha_yakutia_regional_energy_system_name("ЭС Республики Саха")
    assert not service._is_sakha_yakutia_regional_energy_system_name("ОЭС Востока")


def _fake_flatten_entity_for_energy_zone_inject_tests(
    entity: service.SummaryEntity,
    years: list[int],
    rounding_digits: int,
    **kwargs,
) -> list[dict]:
    del rounding_digits, kwargs
    rows: list[dict] = []
    parameter_count = len(service.PARAMETERS_ENERGY_CONSUMPTION)
    component_ec_values = {
        "ЭС Амурской области": ["3"],
        "ЭС Приморского края": ["7"],
    }
    for index, (parameter_key, parameter_label) in enumerate(service.PARAMETERS_ENERGY_CONSUMPTION):
        year_values = ["—" for _ in years]
        if parameter_key == "energy_consumption_mln_kvt_ch":
            year_values = component_ec_values.get(entity.label, year_values)
        rows.append(
            {
                "entity_label": entity.label,
                "entity_rowspan": parameter_count,
                "entity_depth": entity.depth,
                "entity_kind": entity.entity_kind,
                "show_entity_cell": index == 0,
                "parameter_key": parameter_key,
                "parameter_label": parameter_label,
                "demand_model_name": entity.demand_model_name,
                "year_values": year_values,
            }
        )
    for child in entity.children:
        rows.extend(
            _fake_flatten_entity_for_energy_zone_inject_tests(
                child,
                years,
                1,
            )
        )
    return rows


def _siberia_energy_zone_summary_block() -> list[dict]:
    block: list[dict] = []
    for index, parameter_key in enumerate(
        ("energy_consumption_mln_kvt_ch", "energy_consumption_sipr_mln_kvt_ch")
    ):
        block.append(
            {
                "entity_label": "Энергозона Сибири",
                "entity_rowspan": 2,
                "entity_depth": 0,
                "entity_kind": "formula",
                "show_entity_cell": index == 0,
                "parameter_key": parameter_key,
                "year_values": ["1"],
            }
        )
    return block


def test_is_tites_east_union_energy_system_matches_only_tites_east():
    assert service._is_tites_east_union_energy_system(
        type("Ues", (), {"name": "ТИТЭС Востока"})()
    )
    assert not service._is_tites_east_union_energy_system(
        type("Ues", (), {"name": "ТИТЭС Сибири"})()
    )


def test_is_tites_regional_energy_system_by_union_energy_system_id(monkeypatch):
    monkeypatch.setattr(
        service,
        "_tites_union_energy_system_ids",
        lambda: frozenset({77}),
    )

    class _Res:
        pass

    tites_res = _Res()
    tites_res.id_union_energy_system = 77
    ees_res = _Res()
    ees_res.id_union_energy_system = 10
    unassigned_res = _Res()
    unassigned_res.id_union_energy_system = None

    assert service._is_tites_regional_energy_system(tites_res)
    assert not service._is_tites_regional_energy_system(ees_res)
    assert not service._is_tites_regional_energy_system(unassigned_res)


def test_extend_east_energy_zone_block_children_with_extra_energy_units(monkeypatch):
    res_child = service.SummaryEntity(
        label="ЭС ТИТЭС Востока",
        depth=1,
        parameters=service.PARAMETERS_ENERGY_CONSUMPTION,
        demand_rows=[],
        entity_kind="child",
        children=[
            service.SummaryEntity(
                label="Энергорайон 1",
                depth=2,
                parameters=service.PARAMETERS_ENERGY_CONSUMPTION,
                demand_rows=[],
                entity_kind="child",
                demand_model_name="EnergyUnitEnergyConsumptionParameter",
                parent_fk_column="id_energy_unit",
                parent_id=501,
                id_energy_unit=501,
            ),
        ],
        demand_model_name="RegionalEnergySystemEnergyConsumptionParameter",
        parent_fk_column="id_regional_energy_system",
        parent_id=301,
    )
    extra_sakha = service.SummaryEntity(
        label="Изолированый энергорайон Республики Саха (Якутия)",
        depth=1,
        parameters=service.PARAMETERS_ENERGY_CONSUMPTION,
        demand_rows=[],
        entity_kind="child",
        demand_model_name="EnergyUnitEnergyConsumptionParameter",
        parent_fk_column="id_energy_unit",
        parent_id=399,
        id_energy_unit=399,
        perimeter_variant_code="o1",
    )
    extra_khabarovsk = service.SummaryEntity(
        label="Николаевский энергорайон Хабаровского края",
        depth=1,
        parameters=service.PARAMETERS_ENERGY_CONSUMPTION,
        demand_rows=[],
        entity_kind="child",
        demand_model_name="EnergyUnitEnergyConsumptionParameter",
        parent_fk_column="id_energy_unit",
        parent_id=407,
        id_energy_unit=407,
        perimeter_variant_code="o1",
    )
    monkeypatch.setattr(
        service,
        "_build_east_energy_zone_extra_energy_unit_entities",
        lambda: [extra_sakha, extra_khabarovsk],
    )

    children = [res_child]
    service._extend_east_energy_zone_block_children_with_extra_energy_units(children)
    assert [child.label for child in children] == [
        "ЭС ТИТЭС Востока",
        extra_sakha.label,
        extra_khabarovsk.label,
    ]
    assert [child.id_energy_unit for child in children[1:]] == [399, 407]


def test_inject_east_energy_zone_summary_rows_after_siberia_with_tites_res(monkeypatch):
    tites_res_children = [
        service.SummaryEntity(
            label=label,
            depth=1,
            parameters=service.PARAMETERS_ENERGY_CONSUMPTION,
            demand_rows=[],
            entity_kind="child",
            demand_model_name="RegionalEnergySystemEnergyConsumptionParameter",
            parent_fk_column="id_regional_energy_system",
            parent_id=300 + index,
            id_regional_energy_system=300 + index,
        )
        for index, label in enumerate(
            ("ЭС Амурской области", "ЭС Приморского края"),
            start=1,
        )
    ]
    monkeypatch.setattr(
        service,
        "_build_tites_regional_energy_system_entities_for_east_energy_zone",
        lambda: tites_res_children,
    )
    monkeypatch.setattr(
        service,
        "_flatten_entity",
        _fake_flatten_entity_for_energy_zone_inject_tests,
    )
    monkeypatch.setattr(service, "tag_energy_consumption_summary_rows_perimeter_variant_labels", lambda rows: None)
    monkeypatch.setattr(service, "_filter_east_energy_zone_summary_rows_to_o1", lambda rows: None)

    summary_rows = _siberia_energy_zone_summary_block() + [
        {"entity_label": "Хвост", "show_entity_cell": True, "entity_rowspan": 1}
    ]
    service.inject_east_energy_zone_summary_rows(summary_rows, [2024], 1)

    east_start = next(
        index
        for index, row in enumerate(summary_rows)
        if row.get("show_entity_cell")
        and row.get("entity_label") == service._EAST_ENERGY_ZONE_LABEL
    )
    siberia_start = next(
        index
        for index, row in enumerate(summary_rows)
        if row.get("show_entity_cell") and row.get("entity_label") == "Энергозона Сибири"
    )
    tail_start = next(
        index
        for index, row in enumerate(summary_rows)
        if row.get("entity_label") == "Хвост"
    )
    assert siberia_start < east_start < tail_start
    assert any(
        row.get("entity_label") == "ЭС Амурской области" for row in summary_rows[east_start:]
    )
    assert any(
        row.get("entity_label") == "ЭС Приморского края" for row in summary_rows[east_start:]
    )

    east_ec = next(
        row
        for row in summary_rows
        if row.get("entity_label") == service._EAST_ENERGY_ZONE_LABEL
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    )
    assert east_ec["year_values"] == ["10"]
    assert service._EAST_ENERGY_ZONE_FORMULA_TOOLTIP in str(
        east_ec.get("pd_ec_summary_row_formula_tooltip") or ""
    )
    assert not east_ec.get("pd_ec_sipr_integer_display_row")
    east_sipr = next(
        row
        for row in summary_rows
        if row.get("entity_label") == service._EAST_ENERGY_ZONE_LABEL
        and row.get("parameter_key") == "energy_consumption_sipr_mln_kvt_ch"
    )
    assert service._EAST_ENERGY_ZONE_FORMULA_TOOLTIP in str(
        east_sipr.get("pd_ec_summary_row_formula_tooltip") or ""
    )
    assert east_sipr.get("pd_ec_sipr_integer_display_row") is True


def test_inject_east_energy_zone_summary_rows_is_idempotent(monkeypatch):
    monkeypatch.setattr(
        service,
        "_build_tites_regional_energy_system_entities_for_east_energy_zone",
        lambda: [
            service.SummaryEntity(
                label="ЭС Амурской области",
                depth=1,
                parameters=service.PARAMETERS_ENERGY_CONSUMPTION,
                demand_rows=[],
                entity_kind="child",
                demand_model_name="RegionalEnergySystemEnergyConsumptionParameter",
                parent_fk_column="id_regional_energy_system",
                parent_id=1,
            ),
        ],
    )
    monkeypatch.setattr(
        service,
        "_flatten_entity",
        _fake_flatten_entity_for_energy_zone_inject_tests,
    )
    monkeypatch.setattr(service, "tag_energy_consumption_summary_rows_perimeter_variant_labels", lambda rows: None)
    monkeypatch.setattr(service, "_filter_east_energy_zone_summary_rows_to_o1", lambda rows: None)

    summary_rows = _siberia_energy_zone_summary_block()
    service.inject_east_energy_zone_summary_rows(summary_rows, [2024], 1)
    count_after_first = sum(
        1
        for row in summary_rows
        if row.get("entity_label") == service._EAST_ENERGY_ZONE_LABEL
        and row.get("show_entity_cell")
    )
    service.inject_east_energy_zone_summary_rows(summary_rows, [2024], 1)
    count_after_second = sum(
        1
        for row in summary_rows
        if row.get("entity_label") == service._EAST_ENERGY_ZONE_LABEL
        and row.get("show_entity_cell")
    )
    assert count_after_first == 1
    assert count_after_second == 1


def test_is_ees_russia_nt_gaes_variant_summary_row():
    base = {
        "demand_model_name": "EesRussiaEnergyConsumptionParameter",
        "entity_kind": service.ENTITY_KIND_EES_RUSSIA,
        "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
    }
    assert service._is_ees_russia_nt_gaes_variant_summary_row(
        {**base, "perimeter_variant_code": service.CODE_WITH_NT_WITH_GAES}
    )
    assert service._is_ees_russia_nt_gaes_variant_summary_row(
        {**base, "perimeter_variant_code": service.CODE_WITHOUT_NT_WITHOUT_GAES}
    )
    assert service._is_ees_russia_nt_gaes_variant_summary_row(
        {**base, "perimeter_variant_code": service.CODE_WITH_NT}
    )
    assert not service._is_ees_russia_nt_gaes_variant_summary_row(
        {**base, "perimeter_variant_code": "o1"}
    )
    assert not service._is_ees_russia_nt_gaes_variant_summary_row(
        {
            **base,
            "entity_kind": "union_energy_system",
            "perimeter_variant_code": service.CODE_WITH_NT_WITH_GAES,
        }
    )


def test_tag_ees_russia_sipr_integer_display_rows():
    rows = [
        {
            "demand_model_name": "EesRussiaEnergyConsumptionParameter",
            "entity_kind": service.ENTITY_KIND_EES_RUSSIA,
            "perimeter_variant_code": service.CODE_WITHOUT_NT_WITHOUT_GAES,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
        },
        {
            "parameter_key": service.ENERGY_CONSUMPTION_SIPR_ABS_PARAMETER_KEY,
        },
        {
            "parameter_key": service.GAES_CHARGE_PARAMETER_KEY,
        },
        {
            "demand_model_name": "EesRussiaEnergyConsumptionParameter",
            "entity_kind": service.ENTITY_KIND_EES_RUSSIA,
            "perimeter_variant_code": service.CODE_WITH_NT_WITH_GAES,
            "parameter_key": "energy_consumption_mln_kvt_ch",
        },
    ]
    service.tag_ees_russia_sipr_integer_display_rows(rows)
    assert rows[0].get("pd_ec_sipr_integer_display_row") is True
    assert rows[1].get("pd_ec_sipr_integer_display_row") is True
    assert rows[2].get("pd_ec_sipr_integer_display_row") is True
    assert not rows[3].get("pd_ec_sipr_integer_display_row")


def test_pick_east_energy_zone_formula_component_row_matches_sakha_energy_unit_aliases():
    summary_rows = [
        {
            "entity_label": "Западный энергорайон",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "perimeter_variant_code": None,
            "year_values": ["2965.8"],
        },
        {
            "entity_label": "Центральный энергорайон",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "perimeter_variant_code": None,
            "year_values": ["1659.6"],
        },
    ]
    west = service._pick_east_energy_zone_formula_component_row(
        summary_rows,
        "Западный энергорайон ЭС Республики Саха (Якутия)",
        "energy_consumption_mln_kvt_ch",
    )
    central = service._pick_east_energy_zone_formula_component_row(
        summary_rows,
        "Центральный энергорайон ЭС Республики Саха (Якутия)",
        "energy_consumption_mln_kvt_ch",
    )
    assert west is not None
    assert central is not None


def test_east_energy_zone_formula_sakha_districts_only_through_2018():
    row = {
        "entity_label": "Западный энергорайон",
        "year_values": ["100", "200"],
    }
    values = service._east_energy_zone_formula_component_year_values(
        row,
        [2018, 2019],
        "Западный энергорайон ЭС Республики Саха (Якутия)",
    )
    assert values[2018] == Decimal("100")
    assert values[2019] is None

    other = service._east_energy_zone_formula_component_year_values(
        {"entity_label": "ЭС Амурской области", "year_values": ["50", "60"]},
        [2018, 2019],
        "ЭС Амурской области",
    )
    assert other[2018] == Decimal("50")
    assert other[2019] == Decimal("60")


def test_sum_east_energy_zone_formula_includes_sakha_res_and_kamchatka_o1(monkeypatch):
    monkeypatch.setattr(
        service,
        "_east_energy_zone_o1_perimeter_variant_code",
        lambda: "o1",
    )
    component_values = {
        "ЭС Амурской области": Decimal("8370.5"),
        "ЭС Приморского края": Decimal("13108.6"),
        "ЭС Хабаровского края и Еврейской АО": Decimal("9784.9"),
        "ЭС Республики Саха (Якутия)": Decimal("1913.4"),
        "Западный энергорайон ЭС Республики Саха (Якутия)": Decimal("2965.8"),
        "Центральный энергорайон ЭС Республики Саха (Якутия)": Decimal("1659.6"),
        "ЭС Камчатского края": Decimal("1617.3"),
        "ЭС Чукотского АО": Decimal("450.5"),
        "ЭС Сахалинской области": Decimal("2635.7"),
        "ЭС Магаданской области": Decimal("2165.1"),
        "Изолированый энергорайон Республики Саха (Якутия)": Decimal("278"),
        "Николаевский энергорайон Хабаровского края": Decimal("296.9"),
    }
    block_rows: list[dict] = [
        {
            "entity_label": service._EAST_ENERGY_ZONE_LABEL,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "year_values": ["—"],
        }
    ]
    for label, value in component_values.items():
        block_rows.append(
            {
                "entity_label": label,
                "parameter_key": "energy_consumption_mln_kvt_ch",
                "perimeter_variant_code": "o1"
                if label.casefold()
                in service._EAST_ENERGY_ZONE_FORMULA_O1_SOURCE_BASE_LABELS_CF
                else None,
                "year_values": [str(value)],
            }
        )

    summed_2018 = service._sum_east_energy_zone_formula_from_summary_rows(
        block_rows,
        [2018],
        "energy_consumption_mln_kvt_ch",
    )
    assert summed_2018[2018] == Decimal("45246.3")

    summed_2024 = service._sum_east_energy_zone_formula_from_summary_rows(
        block_rows,
        [2024],
        "energy_consumption_mln_kvt_ch",
    )
    assert summed_2024[2024] == Decimal("40620.9")


def test_inject_east_energy_zone_o1_parent_verification_row_at_block_end():
    years = [2024]
    summary_rows = [
        {
            "entity_label": service._EAST_ENERGY_ZONE_LABEL,
            "show_entity_cell": True,
            "entity_depth": 0,
            "entity_kind": "formula",
            "entity_rowspan": 2,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "year_values": ["100.0"],
        },
        {
            "entity_label": service._EAST_ENERGY_ZONE_LABEL,
            "show_entity_cell": False,
            "entity_depth": 0,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "year_values": ["200"],
        },
        {
            "entity_label": "ЭС Амурской области",
            "show_entity_cell": True,
            "entity_depth": 1,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "year_values": ["60.0"],
        },
        {
            "entity_label": "ЭС Камчатского края",
            "show_entity_cell": True,
            "entity_depth": 1,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "perimeter_variant_code": "o1",
            "year_values": ["40.0"],
        },
        {
            "entity_label": "Хвост",
            "show_entity_cell": True,
            "entity_depth": 0,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "year_values": ["0"],
        },
    ]
    service.inject_east_energy_zone_o1_parent_verification_row(
        summary_rows,
        source_rows=list(summary_rows),
        years=years,
        rounding_digits=1,
    )
    check = next(
        row
        for row in summary_rows
        if row.get("entity_kind") == "east_ez_o1_parent_sum_check"
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    )
    tail_index = next(
        index for index, row in enumerate(summary_rows) if row.get("entity_label") == "Хвост"
    )
    verify_block = [
        row
        for row in summary_rows
        if row.get("entity_kind") == "east_ez_o1_parent_sum_check"
    ]
    assert summary_rows.index(verify_block[-1]) + 1 == tail_index
    assert check["entity_label"] == service._EAST_ENERGY_ZONE_O1_PARENT_VERIFICATION_LABEL
    assert check.get("pd_ec_verification_require_isolated_eu") is True
    assert service._EAST_ENERGY_ZONE_O1_PARENT_VERIFICATION_TOOLTIP in str(
        check.get("pd_ec_verification_formula_tooltip") or ""
    )
    assert check["year_values"] == ["0"]


def test_filter_east_energy_zone_summary_rows_to_o1_keeps_only_o1_and_marks_parent(
    monkeypatch,
):
    monkeypatch.setattr(
        service,
        "_east_energy_zone_o1_perimeter_variant_code",
        lambda: "o1",
    )
    monkeypatch.setattr(
        service,
        "tag_energy_consumption_summary_rows_perimeter_variant_labels",
        lambda rows: None,
    )
    summary_rows = _siberia_energy_zone_summary_block() + [
        {
            "entity_label": service._EAST_ENERGY_ZONE_LABEL,
            "show_entity_cell": True,
            "entity_depth": 0,
            "entity_kind": "formula",
            "entity_rowspan": 4,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "perimeter_variant_code": None,
        },
        {
            "entity_label": service._EAST_ENERGY_ZONE_LABEL,
            "show_entity_cell": False,
            "entity_depth": 0,
            "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
            "perimeter_variant_code": None,
        },
        {
            "entity_label": "ЭС ТИТЭС Востока",
            "show_entity_cell": True,
            "entity_depth": 1,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "perimeter_variant_code": "o1",
        },
        {
            "entity_label": "ЭС ТИТЭС Востока",
            "show_entity_cell": True,
            "entity_depth": 1,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "perimeter_variant_code": "with_nt",
        },
        {
            "entity_label": "Следующая энергозона",
            "show_entity_cell": True,
            "entity_depth": 0,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "perimeter_variant_code": "with_nt",
        },
    ]
    service._filter_east_energy_zone_summary_rows_to_o1(summary_rows)

    east_res_rows = [
        row
        for row in summary_rows
        if row.get("entity_label") == "ЭС ТИТЭС Востока"
    ]
    assert len(east_res_rows) == 1
    assert service.is_o1_perimeter_variant_code(east_res_rows[0].get("perimeter_variant_code"))
    parent = next(
        row
        for row in summary_rows
        if row.get("show_entity_cell")
        and row.get("entity_label") == service._EAST_ENERGY_ZONE_LABEL
    )
    assert parent.get("pd_ec_o1_form_row") is True
    assert parent.get("pd_ec_show_o1_badge") is True
    assert parent.get("pd_ec_skip_empty_hide_row") is True
    assert parent.get("perimeter_variant_code") in (None, "")
    assert service._EAST_ENERGY_ZONE_FORMULA_TOOLTIP in str(
        parent.get("pd_ec_summary_row_formula_tooltip") or ""
    )
    assert any(
        row.get("entity_label") == "Следующая энергозона"
        and row.get("perimeter_variant_code") == "with_nt"
        for row in summary_rows
    )


def _chukotka_energy_zone_summary_block() -> list[dict]:
    """Минимальный фрагмент сводки по энергозонам: ЭС Чукотского АО и два энергорайона (О-1)."""
    rowspan = len(service.PARAMETERS_ENERGY_CONSUMPTION)

    def _row(
        *,
        label: str,
        depth: int,
        param_key: str,
        param_label: str,
        demand_model: str,
        value: str,
        show_entity: bool,
    ) -> dict:
        return {
            "entity_label": label,
            "entity_rowspan": rowspan,
            "entity_depth": depth,
            "entity_kind": "child",
            "show_entity_cell": show_entity,
            "show_entity_note_cell": show_entity,
            "parameter_key": param_key,
            "parameter_label": param_label,
            "demand_model_name": demand_model,
            "parent_fk_column": "id_regional_energy_system",
            "parent_id": 648,
            "hist_row_id": None,
            "year_row_ids": [None],
            "hist_value": "—",
            "hist_numeric_tooltip": "",
            "perimeter_variant_code": "o1",
            "perimeter_variant_label": "О-1",
            "pd_ec_o1_form_row": True,
            "year_values": [value],
            "year_numeric_tooltips": [value],
        }

    entity_specs = (
        (
            service._CHUKOTKA_RES_LABEL,
            1,
            "RegionalEnergySystemEnergyConsumptionParameter",
            {
                "energy_consumption_mln_kvt_ch": "603.7",
                "energy_consumption_sipr_mln_kvt_ch": "600.0",
            },
        ),
        (
            "Анадырский энергорайон",
            2,
            "EnergyUnitEnergyConsumptionParameter",
            {
                "energy_consumption_mln_kvt_ch": "134.9",
                "energy_consumption_sipr_mln_kvt_ch": "130.0",
            },
        ),
        (
            service._CHAUN_BILIBINO_EU_LABEL,
            2,
            "EnergyUnitEnergyConsumptionParameter",
            {
                "energy_consumption_mln_kvt_ch": "419.2",
                "energy_consumption_sipr_mln_kvt_ch": "410.0",
            },
        ),
    )
    rows: list[dict] = []
    for label, depth, demand_model, values_by_key in entity_specs:
        for idx, (param_key, param_label) in enumerate(service.PARAMETERS_ENERGY_CONSUMPTION):
            rows.append(
                _row(
                    label=label,
                    depth=depth,
                    param_key=param_key,
                    param_label=param_label,
                    demand_model=demand_model,
                    value=values_by_key.get(param_key, "—"),
                    show_entity=idx == 0,
                )
            )
    rows.append(
        {
            "entity_label": "Следующая РЭС",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "parameter_label": "Потребление электрической энергии, млн кВтч",
            "year_values": ["1"],
        }
    )
    return rows


def _chukotka_oes_split_summary_block() -> list[dict]:
    """Как на /summary/oes/: О-1 строка РЭС без детей + базовая РЭС с ЭУ без метки О-1."""
    rowspan = len(service.PARAMETERS_ENERGY_CONSUMPTION)

    def _res_row(*, o1: bool, value_ec: str, value_sipr: str, show_entity: bool, param_key: str, param_label: str) -> dict:
        value = (
            value_ec
            if param_key == "energy_consumption_mln_kvt_ch"
            else (
                value_sipr
                if param_key == "energy_consumption_sipr_mln_kvt_ch"
                else "—"
            )
        )
        row = {
            "entity_label": service._CHUKOTKA_RES_LABEL,
            "entity_rowspan": rowspan,
            "entity_depth": 1,
            "entity_kind": "child",
            "show_entity_cell": show_entity,
            "show_entity_note_cell": show_entity,
            "parameter_key": param_key,
            "parameter_label": param_label,
            "demand_model_name": "RegionalEnergySystemEnergyConsumptionParameter",
            "year_values": [value],
            "year_numeric_tooltips": [value],
            "hist_value": "—",
            "hist_numeric_tooltip": "",
            "year_row_ids": [None],
            "hist_row_id": None,
        }
        if o1:
            row["perimeter_variant_code"] = "o1"
            row["pd_ec_o1_form_row"] = True
        else:
            row["perimeter_variant_code"] = None
        return row

    def _eu_row(*, label: str, value_ec: str, value_sipr: str, show_entity: bool, param_key: str, param_label: str) -> dict:
        value = (
            value_ec
            if param_key == "energy_consumption_mln_kvt_ch"
            else (
                value_sipr
                if param_key == "energy_consumption_sipr_mln_kvt_ch"
                else "—"
            )
        )
        return {
            "entity_label": label,
            "entity_rowspan": rowspan,
            "entity_depth": 2,
            "entity_kind": "child",
            "show_entity_cell": show_entity,
            "show_entity_note_cell": show_entity,
            "parameter_key": param_key,
            "parameter_label": param_label,
            "demand_model_name": "EnergyUnitEnergyConsumptionParameter",
            "perimeter_variant_code": None,
            "year_values": [value],
            "year_numeric_tooltips": [value],
            "hist_value": "—",
            "hist_numeric_tooltip": "",
            "year_row_ids": [None],
            "hist_row_id": None,
        }

    rows: list[dict] = []
    for idx, (param_key, param_label) in enumerate(service.PARAMETERS_ENERGY_CONSUMPTION):
        rows.append(
            _res_row(
                o1=True,
                value_ec="603.7",
                value_sipr="600.0",
                show_entity=idx == 0,
                param_key=param_key,
                param_label=param_label,
            )
        )
    for idx, (param_key, param_label) in enumerate(service.PARAMETERS_ENERGY_CONSUMPTION):
        rows.append(
            _res_row(
                o1=False,
                value_ec="603.7",
                value_sipr="600.0",
                show_entity=idx == 0,
                param_key=param_key,
                param_label=param_label,
            )
        )
    for idx, (param_key, param_label) in enumerate(service.PARAMETERS_ENERGY_CONSUMPTION):
        rows.append(
            _eu_row(
                label="Анадырский энергорайон",
                value_ec="134.9",
                value_sipr="130.0",
                show_entity=idx == 0,
                param_key=param_key,
                param_label=param_label,
            )
        )
    for idx, (param_key, param_label) in enumerate(service.PARAMETERS_ENERGY_CONSUMPTION):
        rows.append(
            _eu_row(
                label=service._CHAUN_BILIBINO_EU_LABEL,
                value_ec="419.2",
                value_sipr="410.0",
                show_entity=idx == 0,
                param_key=param_key,
                param_label=param_label,
            )
        )
    rows.append(
        {
            "entity_label": "Следующая РЭС",
            "entity_rowspan": 1,
            "entity_depth": 1,
            "show_entity_cell": True,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "parameter_label": "Потребление электрической энергии, млн кВтч",
            "year_values": ["1"],
        }
    )
    return rows


def test_apply_chaun_bilibino_chersky_transfer_note():
    summary_rows = _chukotka_energy_zone_summary_block()
    service.apply_chaun_bilibino_chersky_transfer_note(summary_rows)
    chaun_first = next(
        row
        for row in summary_rows
        if row.get("show_entity_cell")
        and row.get("entity_label") == service._CHAUN_BILIBINO_EU_LABEL
    )
    assert chaun_first.get("pd_ec_chersky_transfer_note") == (
        service._CHAUN_BILIBINO_CHERSKY_TRANSFER_NOTE
    )
    assert all(
        row.get("pd_ec_chukotka_reference_align")
        for row in summary_rows
        if row.get("entity_label") == service._CHAUN_BILIBINO_EU_LABEL
    )


def test_inject_chukotka_chersky_reference_transfer_row_after_chaun_bilibino(monkeypatch):
    monkeypatch.setattr(
        service,
        "tag_energy_consumption_summary_rows_perimeter_variant_labels",
        lambda rows: None,
    )
    monkeypatch.setattr(
        service,
        "resolve_catalog_o1_perimeter_variant_code",
        lambda: "o1",
    )

    summary_rows = _chukotka_energy_zone_summary_block()
    service.inject_chukotka_chersky_reference_transfer_row(summary_rows, [2024], 1)

    ref_start = next(
        index
        for index, row in enumerate(summary_rows)
        if row.get("show_entity_cell")
        and row.get("entity_label") == service._CHERSKY_REFERENCE_TRANSFER_LABEL
    )
    chaun_start = next(
        index
        for index, row in enumerate(summary_rows)
        if row.get("show_entity_cell")
        and row.get("entity_label") == service._CHAUN_BILIBINO_EU_LABEL
    )
    next_res_start = next(
        index
        for index, row in enumerate(summary_rows)
        if row.get("entity_label") == "Следующая РЭС"
    )
    assert chaun_start < ref_start < next_res_start

    ref_ec = next(
        row
        for row in summary_rows
        if row.get("entity_label") == service._CHERSKY_REFERENCE_TRANSFER_LABEL
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    )
    assert ref_ec["year_values"] == ["49,6"]
    assert service._CHERSKY_REFERENCE_TRANSFER_FORMULA_TOOLTIP in str(
        ref_ec.get("pd_ec_summary_row_formula_tooltip") or ""
    )
    assert ref_ec.get("pd_ec_formula_derived_row") is True
    assert ref_ec.get("entity_depth") == service._CHUKOTKA_REFERENCE_ROW_ENTITY_DEPTH
    assert ref_ec.get("pd_ec_chukotka_reference_align") is True
    assert ref_ec.get("pd_ec_o1_form_row") is True
    assert ref_ec.get("pd_ec_show_o1_badge") is True
    assert ref_ec.get("pd_ec_perimeter_entity_kind") is None

    ref_sipr = next(
        row
        for row in summary_rows
        if row.get("entity_label") == service._CHERSKY_REFERENCE_TRANSFER_LABEL
        and row.get("parameter_key") == "energy_consumption_sipr_mln_kvt_ch"
    )
    assert service._decimal_or_none(ref_sipr["year_values"][0].replace(",", ".")) == Decimal(
        "60"
    )
    assert service._CHERSKY_REFERENCE_TRANSFER_FORMULA_TOOLTIP in str(
        ref_sipr.get("pd_ec_summary_row_formula_tooltip") or ""
    )


def test_inject_chukotka_chersky_reference_transfer_row_oes_split_res_blocks(monkeypatch):
    """OES/FO: О-1 РЭС без детей, ЭУ под базовой РЭС без метки О-1."""
    monkeypatch.setattr(
        service,
        "tag_energy_consumption_summary_rows_perimeter_variant_labels",
        lambda rows: None,
    )
    monkeypatch.setattr(
        service,
        "resolve_catalog_o1_perimeter_variant_code",
        lambda: "o1",
    )

    summary_rows = _chukotka_oes_split_summary_block()
    service.apply_chukotka_chersky_reference_summary_rows(summary_rows, [2024], 1)

    ref_ec = next(
        row
        for row in summary_rows
        if row.get("entity_label") == service._CHERSKY_REFERENCE_TRANSFER_LABEL
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    )
    assert ref_ec["year_values"] == ["49,6"]
    assert any(
        row.get("show_entity_cell")
        and row.get("entity_label")
        == service._CHAUN_BILIBINO_WITHOUT_CHERSKY_TRANSFER_LABEL
        for row in summary_rows
    )


def test_inject_chukotka_chersky_reference_transfer_row_is_idempotent():
    summary_rows = _chukotka_energy_zone_summary_block()
    service.inject_chukotka_chersky_reference_transfer_row(summary_rows, [2024], 1)
    count_after_first = sum(
        1
        for row in summary_rows
        if row.get("entity_label") == service._CHERSKY_REFERENCE_TRANSFER_LABEL
        and row.get("show_entity_cell")
    )
    service.inject_chukotka_chersky_reference_transfer_row(summary_rows, [2024], 1)
    count_after_second = sum(
        1
        for row in summary_rows
        if row.get("entity_label") == service._CHERSKY_REFERENCE_TRANSFER_LABEL
        and row.get("show_entity_cell")
    )
    assert count_after_first == 1
    assert count_after_second == 1


def test_inject_chaun_bilibino_without_chersky_transfer_row_after_chersky_reference(
    monkeypatch,
):
    monkeypatch.setattr(
        service,
        "tag_energy_consumption_summary_rows_perimeter_variant_labels",
        lambda rows: None,
    )
    monkeypatch.setattr(
        service,
        "resolve_catalog_o1_perimeter_variant_code",
        lambda: "o1",
    )

    summary_rows = _chukotka_energy_zone_summary_block()
    service.inject_chukotka_chersky_reference_transfer_row(summary_rows, [2024], 1)
    service.inject_chaun_bilibino_without_chersky_transfer_row(summary_rows, [2024], 1)

    ref_start = next(
        index
        for index, row in enumerate(summary_rows)
        if row.get("show_entity_cell")
        and row.get("entity_label") == service._CHERSKY_REFERENCE_TRANSFER_LABEL
    )
    without_start = next(
        index
        for index, row in enumerate(summary_rows)
        if row.get("show_entity_cell")
        and row.get("entity_label") == service._CHAUN_BILIBINO_WITHOUT_CHERSKY_TRANSFER_LABEL
    )
    next_res_start = next(
        index
        for index, row in enumerate(summary_rows)
        if row.get("entity_label") == "Следующая РЭС"
    )
    assert ref_start < without_start < next_res_start

    without_ec = next(
        row
        for row in summary_rows
        if row.get("entity_label") == service._CHAUN_BILIBINO_WITHOUT_CHERSKY_TRANSFER_LABEL
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    )
    assert without_ec["year_values"] == ["468,8"]
    assert without_ec.get("entity_depth") == service._CHUKOTKA_REFERENCE_ROW_ENTITY_DEPTH
    assert without_ec.get("pd_ec_chukotka_reference_align") is True
    assert service._CHAUN_BILIBINO_WITHOUT_CHERSKY_TRANSFER_FORMULA_TOOLTIP in str(
        without_ec.get("pd_ec_summary_row_formula_tooltip") or ""
    )

    without_sipr = next(
        row
        for row in summary_rows
        if row.get("entity_label") == service._CHAUN_BILIBINO_WITHOUT_CHERSKY_TRANSFER_LABEL
        and row.get("parameter_key") == "energy_consumption_sipr_mln_kvt_ch"
    )
    assert service._decimal_or_none(without_sipr["year_values"][0].replace(",", ".")) == Decimal(
        "470"
    )
    assert service._CHAUN_BILIBINO_WITHOUT_CHERSKY_TRANSFER_FORMULA_TOOLTIP in str(
        without_sipr.get("pd_ec_summary_row_formula_tooltip") or ""
    )


def test_inject_chaun_bilibino_without_chersky_transfer_row_is_idempotent(monkeypatch):
    monkeypatch.setattr(
        service,
        "tag_energy_consumption_summary_rows_perimeter_variant_labels",
        lambda rows: None,
    )
    monkeypatch.setattr(
        service,
        "resolve_catalog_o1_perimeter_variant_code",
        lambda: "o1",
    )

    summary_rows = _chukotka_energy_zone_summary_block()
    service.inject_chukotka_chersky_reference_transfer_row(summary_rows, [2024], 1)
    service.inject_chaun_bilibino_without_chersky_transfer_row(summary_rows, [2024], 1)
    count_after_first = sum(
        1
        for row in summary_rows
        if row.get("entity_label") == service._CHAUN_BILIBINO_WITHOUT_CHERSKY_TRANSFER_LABEL
        and row.get("show_entity_cell")
    )
    service.inject_chaun_bilibino_without_chersky_transfer_row(summary_rows, [2024], 1)
    count_after_second = sum(
        1
        for row in summary_rows
        if row.get("entity_label") == service._CHAUN_BILIBINO_WITHOUT_CHERSKY_TRANSFER_LABEL
        and row.get("show_entity_cell")
    )
    assert count_after_first == 1
    assert count_after_second == 1


def test_apply_chukotka_chersky_reference_summary_rows_inserts_both(monkeypatch):
    monkeypatch.setattr(
        service,
        "tag_energy_consumption_summary_rows_perimeter_variant_labels",
        lambda rows: None,
    )
    monkeypatch.setattr(
        service,
        "resolve_catalog_o1_perimeter_variant_code",
        lambda: "o1",
    )

    summary_rows = _chukotka_energy_zone_summary_block()
    # На ОЭС/ФО глубина Чаун-Билибинского может отличаться от энергозон.
    for row in summary_rows:
        if row.get("entity_label") == service._CHAUN_BILIBINO_EU_LABEL:
            row["entity_depth"] = 4

    service.apply_chukotka_chersky_reference_summary_rows(summary_rows, [2024], 1)

    labels = [
        row.get("entity_label")
        for row in summary_rows
        if row.get("show_entity_cell")
    ]
    assert service._CHERSKY_REFERENCE_TRANSFER_LABEL in labels
    assert service._CHAUN_BILIBINO_WITHOUT_CHERSKY_TRANSFER_LABEL in labels

    chaun_first = next(
        row
        for row in summary_rows
        if row.get("show_entity_cell")
        and row.get("entity_label") == service._CHAUN_BILIBINO_EU_LABEL
    )
    assert chaun_first.get("pd_ec_chersky_transfer_note") == (
        service._CHAUN_BILIBINO_CHERSKY_TRANSFER_NOTE
    )

    ref_depth = next(
        row.get("entity_depth")
        for row in summary_rows
        if row.get("show_entity_cell")
        and row.get("entity_label") == service._CHERSKY_REFERENCE_TRANSFER_LABEL
    )
    assert ref_depth == 4

    for label in (
        service._CHERSKY_REFERENCE_TRANSFER_LABEL,
        service._CHAUN_BILIBINO_WITHOUT_CHERSKY_TRANSFER_LABEL,
    ):
        ref_rows = [row for row in summary_rows if row.get("entity_label") == label]
        assert ref_rows
        assert all(row.get("pd_ec_o1_form_row") is True for row in ref_rows)
        assert all(
            row.get("pd_ec_hide_when_summary_table_and_o1") is True for row in ref_rows
        )


def test_chukotka_reference_rows_hidden_when_summary_table_and_o1():
    row = {
        "entity_label": service._CHERSKY_REFERENCE_TRANSFER_LABEL,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "pd_ec_o1_form_row": True,
        "pd_ec_hide_when_summary_table_and_o1": True,
    }

    def parameter_visible(_pk: str) -> bool:
        return True

    assert service._summary_row_visible_for_export_ui(
        row,
        opts=service.EnergyConsumptionExportUiOptions(
            isolated_energy_units_on=True,
            territory_compact_on=False,
        ),
        parameter_visible=parameter_visible,
    )
    assert not service._summary_row_visible_for_export_ui(
        row,
        opts=service.EnergyConsumptionExportUiOptions(
            isolated_energy_units_on=True,
            territory_compact_on=True,
        ),
        parameter_visible=parameter_visible,
    )
    assert not service._summary_row_visible_for_export_ui(
        row,
        opts=service.EnergyConsumptionExportUiOptions(
            isolated_energy_units_on=False,
            territory_compact_on=True,
        ),
        parameter_visible=parameter_visible,
    )


def test_build_oes_summary_context_applies_chukotka_chersky_rows(monkeypatch):
    captured: list[list] = []

    def _fake_apply(rows, years, rounding_digits):
        captured.append(list(rows))

    monkeypatch.setattr(
        service,
        "apply_chukotka_chersky_reference_summary_rows",
        _fake_apply,
    )
    monkeypatch.setattr(
        service,
        "_build_oes_raw_entities",
        lambda **_kwargs: [],
    )
    monkeypatch.setattr(
        service,
        "_expand_summary_entities_o1_subject_perimeter_variants",
        lambda entities: entities,
    )
    monkeypatch.setattr(
        service,
        "_build_summary_context",
        lambda **_kwargs: {
            "summary_rows": [{"entity_label": "stub"}],
            "years": [2024],
        },
    )

    ctx = service.build_oes_summary_context(
        1,
        start_year=2024,
        end_year=2024,
        filter_year_list=[2024],
        data_start_year=2024,
        data_end_year=2024,
    )
    assert captured
    assert ctx["summary_rows"] == [{"entity_label": "stub"}]


def test_build_federal_district_summary_context_applies_chukotka_chersky_rows(
    monkeypatch,
):
    captured: list[list] = []

    def _fake_apply(rows, years, rounding_digits):
        captured.append(list(rows))

    monkeypatch.setattr(
        service,
        "apply_chukotka_chersky_reference_summary_rows",
        _fake_apply,
    )
    monkeypatch.setattr(
        service,
        "_build_summary_table_top_aggregate_entities",
        lambda **_kwargs: [],
    )
    monkeypatch.setattr(
        service,
        "_build_federal_district_entities",
        lambda **_kwargs: [],
    )
    monkeypatch.setattr(
        service,
        "_expand_summary_entities_o1_subject_perimeter_variants",
        lambda entities: entities,
    )
    monkeypatch.setattr(
        service,
        "_build_summary_context",
        lambda **_kwargs: {
            "summary_rows": [{"entity_label": "fo-stub"}],
            "years": [2024],
        },
    )

    ctx = service.build_federal_district_summary_context(
        1,
        start_year=2024,
        end_year=2024,
        filter_year_list=[2024],
        data_start_year=2024,
        data_end_year=2024,
        expand_entity_perimeter_variants=True,
    )
    assert captured
    assert ctx["summary_rows"] == [{"entity_label": "fo-stub"}]


def test_clear_gaes_charge_summary_cache_clears_lru_helpers(monkeypatch):
    service._entity_has_gaes_charge_stations.cache_clear()
    service._gaes_charge_raw_station_values_for_entity.cache_clear()

    monkeypatch.setattr(
        service,
        "_gaes_stations_for_entity_query",
        lambda *_args, **_kwargs: None,
    )
    service._entity_has_gaes_charge_stations(1, "UnionEnergySystemEnergyConsumptionParameter", 117)
    service._gaes_charge_raw_station_values_for_entity(
        1,
        "UnionEnergySystemEnergyConsumptionParameter",
        "id_union_energy_system",
        117,
        (2024,),
    )
    assert service._entity_has_gaes_charge_stations.cache_info().currsize == 1
    assert service._gaes_charge_raw_station_values_for_entity.cache_info().currsize == 1

    service.clear_gaes_charge_summary_cache()

    assert service._entity_has_gaes_charge_stations.cache_info().currsize == 0
    assert service._gaes_charge_raw_station_values_for_entity.cache_info().currsize == 0


def test_apply_energy_zone_formula_to_summary_rows_overwrites_from_res_aggregates(monkeypatch):
    """Обычная энергозона на сводке: mln/sipr = сумма РЭС (как live-формула ФО)."""
    years = [2024, 2025]
    ez_id = 42
    monkeypatch.setattr(
        service.dps,
        "compute_energy_zone_res_aggregates",
        lambda **_kwargs: {
            (ez_id, None): {
                2024: (Decimal("10.5"), Decimal("11.0")),
                2025: (Decimal("20.0"), Decimal("21.5")),
            }
        },
    )

    mln_row = {
        "entity_label": "1 — Тестовая ЭЗ",
        "entity_rowspan": 2,
        "entity_depth": 0,
        "entity_kind": "group",
        "show_entity_cell": True,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "demand_model_name": "EnergyZoneEnergyConsumptionParameter",
        "parent_fk_column": "id_energy_zone",
        "parent_id": ez_id,
        "perimeter_variant_code": None,
        "year_values": ["1.0", "2.0"],
        "year_numeric_tooltips": ["1.0", "2.0"],
        "year_row_ids": [None, None],
        "hist_value": "—",
        "hist_numeric_tooltip": "",
    }
    sipr_row = {
        **mln_row,
        "show_entity_cell": False,
        "entity_rowspan": 1,
        "parameter_key": "energy_consumption_sipr_mln_kvt_ch",
        "year_values": ["3.0", "4.0"],
        "year_numeric_tooltips": ["3.0", "4.0"],
    }
    formula_row = {
        "entity_label": "Энергозона Сибири",
        "entity_rowspan": 1,
        "entity_depth": 0,
        "entity_kind": "formula",
        "show_entity_cell": True,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "demand_model_name": None,
        "parent_fk_column": None,
        "parent_id": None,
        "perimeter_variant_code": None,
        "year_values": ["99.0"],
        "year_numeric_tooltips": ["99.0"],
        "year_row_ids": [None],
        "hist_value": "—",
        "hist_numeric_tooltip": "",
    }
    rows = [mln_row, sipr_row, formula_row]

    service.apply_energy_zone_formula_to_summary_rows(rows, years, rounding_digits=1)

    assert mln_row["year_values"] == ["10,5", "20"]
    assert sipr_row["year_values"] == ["11", "21,5"]
    assert mln_row.get("pd_ec_formula_derived_row") is True
    assert sipr_row.get("pd_ec_formula_derived_row") is True
    assert mln_row.get("pd_ec_summary_row_formula_tooltip") == service._EZ_FORMULA_TOOLTIP
    # Формульные Сибирь/Восток не трогаем.
    assert formula_row["year_values"] == ["99.0"]
    assert formula_row.get("pd_ec_formula_derived_row") is not True


def test_apply_energy_zone_formula_falls_back_to_null_pvc_aggregates(monkeypatch):
    """Если у ЭЗ with_nt, а у РЭС pvc пустой — берём агрегат (ez_id, None)."""
    years = [2024]
    ez_id = 7
    monkeypatch.setattr(
        service.dps,
        "compute_energy_zone_res_aggregates",
        lambda **_kwargs: {
            (ez_id, None): {2024: (Decimal("15"), Decimal("16"))},
        },
    )
    mln_row = {
        "entity_label": "2 — ЭЗ",
        "entity_rowspan": 1,
        "entity_depth": 0,
        "entity_kind": "perimeter_variant",
        "show_entity_cell": True,
        "parameter_key": "energy_consumption_mln_kvt_ch",
        "demand_model_name": "EnergyZoneEnergyConsumptionParameter",
        "parent_fk_column": "id_energy_zone",
        "parent_id": ez_id,
        "perimeter_variant_code": service.CODE_WITH_NT,
        "year_values": ["—"],
        "year_numeric_tooltips": [""],
        "year_row_ids": [None],
        "hist_value": "—",
        "hist_numeric_tooltip": "",
    }

    service.apply_energy_zone_formula_to_summary_rows([mln_row], years, rounding_digits=1)

    assert mln_row["year_values"] == ["15"]
    assert mln_row.get("pd_ec_formula_derived_row") is True

