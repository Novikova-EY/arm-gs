import json

import pytest

pytest.importorskip("selenium")

from test_consumption_cell_styles_browser import browser, ROOT
from test_russia_with_nt_year_display import WITH_NT_MODELS, make_row
from app.common.perimeter_variant.constants import CODE_WITH_NT_WITH_GAES, CODE_WITH_NT_WITHOUT_GAES
from app.energy_consumption.services.energy_consumption_summary_services import mask_with_nt_summary_year_display
from app.energy_consumption.services.ec_summary_client_render_services import prepare_summary_rows_for_client


@pytest.mark.parametrize("scope", ["oes", "fo", "ez"])
@pytest.mark.parametrize("summary_table", [False, True])
def test_client_renderer_keeps_with_nt_variants_empty_before_2023(browser, tmp_path, scope, summary_table):
    rows = []
    for model, label in WITH_NT_MODELS:
        for code in (CODE_WITH_NT_WITH_GAES, CODE_WITH_NT_WITHOUT_GAES):
            suffix = " с НТ без заряда ГАЭС" if code == CODE_WITH_NT_WITHOUT_GAES else " с НТ с зарядом ГАЭС"
            row = make_row(model, label + suffix, code)
            row["show_entity_cell"] = True
            row["entity_rowspan"] = 1
            row["pd_ec_formula_derived_row"] = code == CODE_WITH_NT_WITHOUT_GAES
            rows.append(row)
    context = {"years": [2021, 2022, 2023, 2024], "summary_rows": rows}
    mask_with_nt_summary_year_display(context)
    payload = {"years": context["years"], "summary_rows": prepare_summary_rows_for_client(rows),
               "config": {"can_edit_summary_cells": True, "summary_table_page": summary_table,
                          "start_year": 2021, "rounding_digits": 0}}
    script = (ROOT / "app/static/js/energy_consumption/demand_summary_client_render.js").read_text(encoding="utf-8")
    page = tmp_path / "russia-with-nt.html"
    page.write_text('''<!doctype html><meta charset="utf-8">
<table id="powerDemandSummaryTable" data-summary-view="''' + scope + '''"><tbody id="powerDemandSummaryTbody"></tbody></table>
<script id="ec-summary-client-render-config" type="application/json">{"data_path":"/data","scope":"''' + scope + '''","can_edit_summary_cells":true}</script>
<script>window.fetch=async()=>({ok:true,json:async()=>(''' + json.dumps(payload, ensure_ascii=False) + ''')});</script>
<script>''' + script + '''</script>''', encoding="utf-8")
    browser.get(page.as_uri())
    result = browser.execute_async_script('''
        const done = arguments[0];
        window.__ecSummaryRowsReady.then(() => done([...document.querySelectorAll('tbody tr')].map(row =>
            [...row.querySelectorAll('.summary-year-cell')].map(cell => ({
                text: cell.querySelector('input')?.value || cell.textContent,
                input: !!cell.querySelector('input'),
                masked: cell.classList.contains('pd-ec-variant-year-out'),
                tooltip: cell.title
            }))
        ))).catch(error => done({error:String(error)}));
    ''')
    assert len(result) == len(rows), result
    for index, cells in enumerate(result):
        assert len(cells) == 4
        assert cells[:2] == [{"text": "", "input": False, "masked": True, "tooltip": ""}] * 2
        assert [cell["text"] for cell in cells[2:]] == ["23,3", "24,4"]
        assert [cell["input"] for cell in cells[2:]] == [index % 2 == 0] * 2
