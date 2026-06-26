from decimal import Decimal

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
        "parameter_label": "Потребление электрической энергии, млн кВт·ч",
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
        "parameter_label": "Потребление электрической энергии, млн кВт·ч",
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
        ees_russia_without_nt_without_gaes,
        sync_without_nt_without_gaes,
        south_with_nt_with_gaes,
        south_with_nt_without_gaes,
    ]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)
    service._mark_summary_table_nt_on_gaes_off_variant_row_rules(rows)

    assert ees_type_with_nt_without_gaes["pd_ec_nt_on_gaes_off_visible_row"] is True
    assert ees_type_with_nt_plain["pd_ec_nt_on_gaes_off_redundant_row"] is True
    assert ees_type_with_nt_with_gaes["pd_ec_nt_on_gaes_off_redundant_row"] is True
    assert ees_russia_without_nt_without_gaes["pd_ec_nt_on_gaes_off_visible_row"] is True
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
        service.export_entity_label_for_summary_row(ees_type_with_nt_without_gaes, ui_opts)
        == "ЭЭС России с НТ"
    )
    assert (
        service.export_entity_label_for_summary_row(ees_russia_without_nt_without_gaes, ui_opts)
        == "ЕЭС России без НТ"
    )
    assert (
        service.export_entity_label_for_summary_row(sync_without_nt_without_gaes, ui_opts)
        == "Первая синхронная зона без НТ (с ЭС Калининградской области)"
    )
    assert (
        service.export_entity_label_for_summary_row(south_with_nt_with_gaes, ui_opts)
        == "ОЭС Юга с НТ"
    )

    def parameter_visible(_pk: str) -> bool:
        return True

    assert service._summary_row_visible_for_export_ui(
        ees_russia_without_nt_without_gaes, opts=ui_opts, parameter_visible=parameter_visible
    )
    assert service._summary_row_visible_for_export_ui(
        ees_type_with_nt_without_gaes, opts=ui_opts, parameter_visible=parameter_visible
    )
    assert service._summary_row_visible_for_export_ui(
        south_with_nt_with_gaes, opts=ui_opts, parameter_visible=parameter_visible
    )
    assert not service._summary_row_visible_for_export_ui(
        south_with_nt_without_gaes, opts=ui_opts, parameter_visible=parameter_visible
    )
    assert not service._summary_row_visible_for_export_ui(
        ees_type_with_nt_with_gaes, opts=ui_opts, parameter_visible=parameter_visible
    )


def test_collapsed_nt_gaes_visible_rows_skip_empty_hide_marks_south_ues_without_nt():
    south_without_nt = _south_variant_row(service.CODE_WITHOUT_NT, "70.0")
    rows = [south_without_nt]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)

    assert south_without_nt.get("pd_ec_collapsed_nt_gaes_visible_row") is True
    assert south_without_nt.get("pd_ec_skip_empty_hide_row") is True


def test_collapsed_nt_gaes_variant_row_rules_mark_primary_rows():
    ees_russia_row = {
        "entity_label": "ЕЭС России",
        "demand_model_name": "EesRussiaEnergyConsumptionParameter",
        "parent_fk_column": None,
        "parent_id": None,
        "parameter_key": "energy_consumption_mln_kvt_ch",
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
    rows = [ees_russia_row, *south_rows, sync_row]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)

    assert ees_russia_row["pd_ec_collapsed_nt_gaes_visible_row"] is True
    assert ees_russia_row["pd_ec_entity_label_compact_nt_gaes"] == "ЕЭС России"
    assert south_rows[0]["pd_ec_collapsed_nt_gaes_visible_row"] is True
    assert south_rows[0]["pd_ec_entity_label_compact_nt_gaes"] == "ОЭС Юга"
    assert south_rows[1]["pd_ec_collapsed_nt_gaes_redundant_row"] is True
    assert south_rows[2]["pd_ec_collapsed_nt_gaes_redundant_row"] is True
    assert sync_row["pd_ec_collapsed_nt_gaes_visible_row"] is True
    assert sync_row["pd_ec_entity_label_compact_nt_gaes"] == (
        "Первая синхронная зона (с ЭС Калининградской области)"
    )


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


def test_apply_gaes_without_charge_formula_keeps_south_without_nt_without_gaes_db_values():
    years = [2024]
    source_row = _south_variant_row(service.CODE_WITHOUT_NT_WITH_GAES, "100.0")
    charge_row = _south_gaes_charge_row_for_nt_group("12.0", nt_group="without_nt")
    target_row = _south_variant_row(service.CODE_WITHOUT_NT_WITHOUT_GAES, "77.5")
    rows = [source_row, charge_row, target_row]

    service.apply_energy_consumption_summary_table_variant_toggle_rows(rows)
    service.apply_gaes_without_charge_formula_to_summary_rows(
        rows,
        years,
        rounding_digits=1,
    )

    assert service._raw_year_values_from_summary_row(target_row, years) == {
        2024: Decimal("77.5")
    }
    assert target_row.get("pd_ec_formula_derived_row") is not True
    assert target_row.get("gaes_without_charge_formula_kind") is None


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
        2024: Decimal("0.0")
    }
    assert without_nt_target.get("pd_ec_formula_derived_row") is not True


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

    assert with_kal_ec["perimeter_variant_to_year"] == 2024
    assert with_kal_ec["year_values"][:2] != ["—", "—"]
    assert with_kal_ec["year_values"][2:] == ["—", "—"]
    assert with_kal_ec["pd_ec_verification_year_red"] == [False, False, False, False]

    assert without_kal_ec["perimeter_variant_from_year"] == 2025
    assert without_kal_ec["year_values"][:2] == ["—", "—"]
    assert without_kal_ec["year_values"][2:] != ["—", "—"]
    assert without_kal_ec["pd_ec_verification_year_red"] == [False, False, False, False]


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
    assert ec["year_values"][1] == "—"
    assert ec["pd_ec_verification_year_red"] == [True, False]
    assert ec.get("perimeter_variant_to_year") == 2024


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
    first_sa_with_kal = Decimal("1087532.4") + Decimal("5141.5")
    second_sa = Decimal("50551.3")
    tites = Decimal("0")

    monkeypatch.setattr(
        service,
        "_ees_russia_without_nt_with_gaes_formula_component_values",
        lambda _rows, _years, _key: (
            {2024: first_sa_with_kal},
            {2024: second_sa},
            {2024: tites},
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
    assert ec_row["year_values"] == ["0"]


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
        },
        {
            "demand_model_name": rd_mn,
            "entity_depth": 3,
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "pd_ec_rd_without_gaes_injected_row": True,
        },
    ]

    service.tag_energy_consumption_summary_rows_for_territory_compact(rows)

    for row in rows:
        assert row.get("pd_ec_territory_detail_row") is True
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
    assert cz_row["year_values"] == ["100", "280", "2 800"]
    assert cz_row.get("pd_ec_formula_derived_row") is True
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


def test_inject_summary_table_cz_new_territories_reference_row_before_russia():
    years = [2023, 2024, 2025]
    rows = _cz_russia_nt_pair_rows_for_reference_test(years=years)

    service.inject_summary_table_cz_new_territories_reference_row(rows, years, rounding_digits=1)

    ref_start = next(
        index
        for index, row in enumerate(rows)
        if row.get("show_entity_cell")
        and row.get("entity_label") == service._SUMMARY_TABLE_CZ_NT_REFERENCE_LABEL
    )
    russia_start = next(
        index
        for index, row in enumerate(rows)
        if row.get("show_entity_cell")
        and row.get("entity_kind") == service.ENTITY_KIND_RUSSIA_FEDERATION
    )
    assert ref_start < russia_start

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

    ref_sipr = next(
        row
        for row in rows
        if row.get("entity_label") == service._SUMMARY_TABLE_CZ_NT_REFERENCE_LABEL
        and row.get("parameter_key") == "energy_consumption_sipr_mln_kvt_ch"
    )
    assert ref_sipr["year_values"] == ["—", "5", "5"]


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
    assert checks == []


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
    assert checks == []


def test_inject_fo_summary_verification_rows_south_ues_after_north_caucasus_res(
    monkeypatch,
):
    from decimal import Decimal

    rows = [
        _fo_base_row(fd_id=20, label="Южный ФО"),
        _fo_sipr_row(fd_id=20, label="Южный ФО"),
        _fo_base_row(fd_id=50, label="Северо-Кавказский ФО"),
        _fo_sipr_row(fd_id=50, label="Северо-Кавказский ФО"),
        _fo_res_row(res_id=801, label="ЭС Ставропольского края", value="100.0"),
        _fo_res_row(res_id=802, label="ЭС Республики Дагестан", value="200.0"),
        _fo_base_row(fd_id=87, label="Приволжский ФО"),
        _fo_sipr_row(fd_id=87, label="Приволжский ФО"),
    ]
    rows[0]["entity_rowspan"] = 2
    rows[2]["entity_rowspan"] = 2
    rows[6]["entity_rowspan"] = 2
    rows[0]["year_values"] = ["10"]
    rows[2]["year_values"] = ["20"]

    def _resolve_ues(name_cf: str):
        if name_cf == service.SOUTH_UES_NAME_CF:
            return 118
        return None

    def _year_values(
        model,
        fk_column,
        parent_id,
        years,
        parameter_key,
        *,
        perimeter_variant_code=None,
    ):
        if (
            model.__name__ == "UnionEnergySystemEnergyConsumptionParameter"
            and int(parent_id) == 118
            and parameter_key == "energy_consumption_mln_kvt_ch"
        ):
            return {2024: Decimal("500")}
        if (
            model.__name__ == "UnionEnergySystemEnergyConsumptionParameter"
            and int(parent_id) == 118
            and parameter_key == "energy_consumption_sipr_mln_kvt_ch"
        ):
            return {2024: Decimal("450")}
        return {int(y): None for y in years}

    monkeypatch.setattr(service, "_resolve_union_energy_system_id_by_name_cf", _resolve_ues)
    monkeypatch.setattr(service, "_year_values_from_parent_demand_rows", _year_values)

    service.inject_fo_summary_verification_rows(
        rows,
        source_rows=list(rows),
        years=[2024],
        rounding_digits=1,
    )

    south_check = next(
        row
        for row in rows
        if row.get("entity_kind") == "fo_south_ues_verification"
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    )
    assert south_check["entity_label"] == "Проверка для ОЭС Юга"
    assert rows.index(south_check) == 6


def test_inject_fo_summary_verification_rows_adds_ural_ues_check(monkeypatch):
    from decimal import Decimal

    rows = [
        _fo_base_row(fd_id=87, label="Приволжский ФО"),
        _fo_sipr_row(fd_id=87, label="Приволжский ФО"),
        _fo_base_row(fd_id=91, label="Уральский ФО"),
        _fo_sipr_row(fd_id=91, label="Уральский ФО"),
    ]
    rows[0]["entity_rowspan"] = 2
    rows[2]["entity_rowspan"] = 2
    rows[0]["year_values"] = ["189477"]
    rows[2]["year_values"] = ["176175"]

    def _resolve_ues(name_cf: str):
        if name_cf == service.URAL_UES_NAME_CF:
            return 116
        if name_cf == service.MIDDLE_VOLGA_UES_NAME_CF:
            return 115
        return None

    def _year_values(model, fk_column, parent_id, years, parameter_key, *, perimeter_variant_code=None):
        if (
            model.__name__ == "UnionEnergySystemEnergyConsumptionParameter"
            and int(parent_id) == 116
            and parameter_key == "energy_consumption_mln_kvt_ch"
        ):
            return {2016: Decimal("259383")}
        if (
            model.__name__ == "UnionEnergySystemEnergyConsumptionParameter"
            and int(parent_id) == 115
            and parameter_key == "energy_consumption_mln_kvt_ch"
        ):
            return {2016: Decimal("106270")}
        return {int(y): None for y in years}

    monkeypatch.setattr(service, "_resolve_union_energy_system_id_by_name_cf", _resolve_ues)
    monkeypatch.setattr(service, "_year_values_from_parent_demand_rows", _year_values)

    service.inject_fo_summary_verification_rows(
        rows,
        source_rows=list(rows),
        years=[2016],
        rounding_digits=1,
    )

    ural_check = next(
        row
        for row in rows
        if row.get("entity_kind") == "fo_ural_ues_verification"
        and row.get("parameter_key") == "energy_consumption_mln_kvt_ch"
    )
    assert ural_check["entity_label"] == "Проверка для ОЭС Урала"
    assert ural_check["year_values"] == ["-1"]
    assert "Уральский ФО" in ural_check["pd_ec_verification_formula_tooltip"]
    assert rows.index(ural_check) == 4


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
        },
        {
            "entity_kind": "union_energy_system",
            "entity_label": "ОЭС Центра",
            "parameter_key": "energy_consumption_mln_kvt_ch",
            "show_entity_cell": True,
            "entity_rowspan": 1,
        },
    ]

    filtered = service.filter_oes_max_summary_page_hidden_rows(rows)

    assert [row.get("entity_label") for row in filtered] == ["ОЭС Центра"]
    assert filtered[0].get("show_entity_cell") is True
    assert filtered[0].get("entity_rowspan") == 1


def test_filter_oes_max_keeps_ees_unified_gaes_rows_when_no_ees_russia_aggregate():
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
    assert EES_UNIFIED_REF_NAME not in filtered_labels


def test_inject_verification_rows_use_independent_insert_positions(monkeypatch):
    def _row(**kwargs: object) -> dict:
        return dict(kwargs)

    top_ees = _row(
        entity_label="ЭЭС России",
        entity_kind="ees_russia",
        demand_model_name="EesRussiaEnergyConsumptionParameter",
        parameter_key="energy_consumption_mln_kvt_ch",
    )
    sync = _row(
        entity_label="Синхронная зона Калининградской области",
        demand_model_name="SynchronousAreaEnergyConsumptionParameter",
        parameter_key="energy_consumption_mln_kvt_ch",
    )
    pre_oes_ees = _row(
        entity_label="ЕЭС России без НТ без заряда ГАЭС",
        entity_kind="ees_russia",
        demand_model_name="EesRussiaEnergyConsumptionParameter",
        parameter_key="energy_consumption_mln_kvt_ch",
    )
    oes = _row(
        entity_label="ОЭС Северо-Запада",
        demand_model_name="UnionEnergySystemEnergyConsumptionParameter",
        parent_fk_column="id_union_energy_system",
        parameter_key="energy_consumption_mln_kvt_ch",
    )
    summary_rows = [top_ees, sync, pre_oes_ees, oes]

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
        "Синхронная зона Калининградской области",
        service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_UES_VERIFICATION_LABEL,
        service._FIRST_SA_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_UES_VERIFICATION_LABEL,
        "ЕЭС России без НТ без заряда ГАЭС",
        "Проверка ЕЭС России без НТ с зарядом ГАЭС",
        "ОЭС Северо-Запада",
    ]


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


def test_first_sa_without_kaliningrad_ues_sum_prefers_with_gaes_variant(monkeypatch):
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
        "_union_energy_system_ids_for_synchronous_area",
        lambda _sa_id: [south_id, other_id, nt_id],
    )
    monkeypatch.setattr(
        service,
        "_kaliningrad_es_parameter_year_values",
        lambda *_args, **_kwargs: {},
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
            if perimeter_variant_code == service.CODE_WITHOUT_NT_WITHOUT_GAES:
                return [_DemandRow(Decimal("5"))]
            return []
        if perimeter_variant_code in (
            service.CODE_WITHOUT_NT_WITH_GAES_WITH_KALININGRAD_ES,
            None,
        ):
            return [_DemandRow(Decimal("20"))]
        return []

    monkeypatch.setattr(service.dps, "get_demand_rows", fake_get_demand_rows)

    result = service._year_values_sum_ues_in_first_sa_without_kaliningrad_es(
        first_sa_id,
        years,
        "energy_consumption_mln_kvt_ch",
    )

    assert variants_tried[south_id][0] == service.CODE_WITHOUT_NT_WITH_GAES
    assert service.CODE_WITHOUT_NT_WITHOUT_GAES not in variants_tried[south_id]
    assert variants_tried[other_id][0] == service.CODE_WITHOUT_NT_WITH_GAES
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
    assert captured == ["o1"]


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


def test_build_ez_raw_entities_includes_ees_russia_variants_when_expanded(monkeypatch):
    captured: list[dict] = []

    def _fake_build_perimeter_aggregate_entities(**kwargs):
        captured.append(kwargs)
        return []

    monkeypatch.setattr(
        service,
        "_build_perimeter_aggregate_entities",
        _fake_build_perimeter_aggregate_entities,
    )
    monkeypatch.setattr(service, "_build_energy_zone_entities", lambda: [])

    entities = service._build_ez_raw_entities(expand_entity_perimeter_variants=True)

    assert entities == []
    assert len(captured) == 2
    assert captured[0]["entity_kind"] == service.ENTITY_KIND_CENTRALIZED_ZONE
    assert captured[1]["entity_kind"] == service.ENTITY_KIND_EES_RUSSIA
    assert captured[1]["all_bound_variants"] is True
    assert captured[1]["display_label"] == "ЕЭС России"


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
            "parameter_label": "Потребление электрической энергии, млн кВт·ч",
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


def test_apply_oes_tites_root_formula_excludes_sakha_yakutia_extra_after_2019(
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
        years=[2019, 2020],
        rounding_digits=1,
        eu_source_rows=eu_rows,
    )

    assert summary_rows[0]["year_values"] == ["160", "10"]


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
    assert parent.get("pd_ec_o1_form_row") is not True
    assert not parent.get("pd_ec_show_o1_badge")
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
            "parameter_label": "Потребление электрической энергии, млн кВт·ч",
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

