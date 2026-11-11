from pathlib import Path
from types import SimpleNamespace
import re

import pytest
from jinja2 import Environment, FileSystemLoader
from werkzeug.datastructures import MultiDict
from wtforms import Form, SelectField


TEMPLATES = Path(__file__).resolve().parents[2] / 'app/templates'


class GroupForm(Form):
    id_equipment_group = SelectField(coerce=int, choices=[(0, 'не указано'), (317, 'Тип из карточки')])


@pytest.mark.parametrize('station_type', ['ВЭС', 'СЭС', 'СНЭЭ', 'ГЭС', 'ГАЭС', 'ТЭС', 'АЭС', ' гэс '])
@pytest.mark.parametrize('editable', [False, True])
@pytest.mark.parametrize('group_id', [None, 317])
def test_equipment_group_visibility_and_preservation(station_type, editable, group_id):
    form = GroupForm(prefix='main_', data={'id_equipment_group': group_id or 0})
    environment = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=True)
    html = environment.get_template('generation/stations/_machine_equipment_group_type.html').render(
        station=SimpleNamespace(station_type=SimpleNamespace(name=station_type)),
        equipment_group_machine=SimpleNamespace(equipment_group=SimpleNamespace(name='Тип из карточки') if group_id else None),
        equipment_group_form=form, equipment_group_editable=editable)
    visible = station_type.strip().upper() in ('ТЭС', 'АЭС')
    assert ('Тип группы оборудования:' in html) == visible
    assert ('<select' in html) == (visible and editable)
    if not visible and editable:
        field = re.search(r'<input type="hidden" name="([^"]+)"\s+value="([^"]+)"', html)
        assert field is not None
        posted = GroupForm(MultiDict({field[1]: field[2]}), prefix='main_')
        assert posted.validate()
        assert posted.id_equipment_group.data == (group_id or 0)
    elif not visible:
        assert '<input' not in html and 'Тип из карточки' not in html


def test_parent_and_pgu_cards_use_the_same_group_visibility_block():
    for name in ('machine_details.html', 'pgu_machine_details.html'):
        source = (TEMPLATES / 'generation/stations' / name).read_text(encoding='utf-8')
        assert "include 'generation/stations/_machine_equipment_group_type.html'" in source
