from html import unescape
from pathlib import Path
import re

from flask import Flask, render_template
import pytest

from app.rational_structure.services.equipment_runtime_columns import runtime_columns


DEPENDENCIES = {
    'AN': (), 'AO': (), 'AP': ('AO', 'AN'), 'AQ': ('AN',),
    'AR': ('AQ', 'AU'), 'AS': ('AR', 'AU'),
    'planned_modernization_year': (), 'AT': (), 'AU': (), 'AV': (),
    'AW': ('AM', 'AT'), 'AX': ('AM', 'AT', 'AP'),
    'AY': ('AT', 'AW', 'AX'), 'AZ': ('AY', 'AU'),
    'BA': ('AZ', 'AT'), 'BC': ('AS', 'BA', 'AY'),
    'BD': ('AM',), 'BF': ('AM',),
}


@pytest.mark.parametrize('end', [2042, 2048])
@pytest.mark.parametrize('key,dependencies', DEPENDENCIES.items())
def test_tooltips_only_show_named_calculation_rules(key, dependencies, end):
    app = Flask(__name__, template_folder=str(Path('app/templates').resolve()))
    columns = runtime_columns(end)
    by_key = {column['key']: column for column in columns}
    with app.test_request_context():
        html = render_template(
            'rational_structure/_equipment_runtime_formula_info.html',
            column=by_key[key], table={'columns': columns}, selected_year=2025,
            general_scheme_end_year=end, sipr_end_year=2038,
        )
    attribute = re.search(r'\btitle="([^"]*)"', html).group(1)
    content = unescape(attribute)
    plain_text = unescape(re.sub(r'<[^>]+>', ' ', content))
    assert '<p><strong>' + by_key[key]['label'] + '</strong></p>' in content
    assert not re.search(r'\b[A-Z]{1,2}\b', plain_text), plain_text
    for dependency in dependencies:
        assert '«' + by_key[dependency]['label'] + '»' in plain_text
    for auxiliary in (
        'источник', 'карточк', 'технических характеристик', 'справочник',
        'выбранной версии', 'округления', 'округляется', 'половина',
        'отображения', '«–»', 'Excel', 'исходной книги',
    ):
        assert auxiliary.lower() not in plain_text.lower()
    assert 'data-bs-html="true"' in html
    assert 'data-bs-custom-class="rs-runtime-formula-tooltip"' in html
