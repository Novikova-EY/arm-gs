from pathlib import Path
import re

import pytest
from flask import render_template_string


TEMPLATES = Path(__file__).resolve().parents[2] / "app/templates/energy_consumption"
BODIES = [TEMPLATES / "energy_consumption_summary_body.html", *sorted((TEMPLATES / "pages").glob("*_body.html"))]


@pytest.mark.parametrize("template", BODIES, ids=lambda path: path.stem)
def test_formula_info_is_only_in_parameter_column_on_every_server_rendered_page(app, template):
    source = template.read_text(encoding="utf-8-sig")
    entity_class = source.index('class="summary-entity-cell ')
    entity_start = source.rfind("<td ", 0, entity_class)
    entity_end = source.index("</td>", entity_class) + len("</td>")
    entity = source[entity_start:entity_end]
    parameter = re.search(r'<td class="summary-parameter-cell">.*?</td>', source, re.S)
    assert entity_start >= 0 and parameter
    row = dict(entity_label="Энергосистема <тест>", entity_depth=0, entity_rowspan=1,
               parameter_label="Потребление электрической энергии", pd_parameter_formula_tooltip="Сумма = A + B",
               pd_ec_chersky_transfer_note="Примечание о передаче", pd_ec_show_o1_badge=True)
    with app.test_request_context():
        entity_html = render_template_string(entity, row=row, _initial_entity_rowspan=1)
        parameter_html = render_template_string(parameter[0], row=row)
    assert "ec-formula-info" not in entity_html
    assert "bi-info-circle" not in entity_html
    assert "Энергосистема &lt;тест&gt;" in entity_html
    assert "Примечание о передаче" in entity_html
    assert "О-1" in entity_html
    assert parameter_html.count("ec-formula-info") == 1
    assert 'title="Сумма = A + B"' in parameter_html
    assert row["parameter_label"] in parameter_html
