# -*- coding: utf-8 -*-
"""Разметка tbody «Агрегаты электростанции»: строки Рогр/Ррасп ПГУ не съезжают."""
import os
import re
from html.parser import HTMLParser
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader


TEMPLATES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "app", "templates")
)


class _RowCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self._tr_class = None
        self._cells = None
        self._cell_tag = None
        self._cell_class = None
        self._cell_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "tr":
            self._tr_class = attrs.get("class", "")
            self._cells = []
        elif tag in ("td", "th") and self._cells is not None:
            self._cell_tag = tag
            self._cell_class = attrs.get("class", "")
            self._cell_text = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cells is not None:
            self._cells.append(
                (self._cell_tag, self._cell_class, "".join(self._cell_text).strip())
            )
            self._cell_tag = None
        elif tag == "tr" and self._cells is not None:
            self.rows.append((self._tr_class, self._cells))
            self._cells = None

    def handle_data(self, data):
        if self._cell_tag:
            self._cell_text.append(data)


def _render_tbody(station, start_year=2024, end_year=2031):
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    env.globals["url_for"] = lambda *a, **k: "/x"
    env.globals["request"] = SimpleNamespace(args={})
    env.globals["current_user"] = SimpleNamespace(is_admin=False)

    def _format_decimal(v, d=None):
        return "" if v in (None, 0) else str(v)

    env.globals["format_decimal"] = _format_decimal
    env.filters["format_decimal"] = _format_decimal
    tmpl = env.get_template("generation/stations/_machines_tbody.html")
    return tmpl.render(
        station=station,
        start_year=start_year,
        end_year=end_year,
        can_edit=False,
        gen_company_choices=[],
    )


def _pgu_station():
    pgu_parts = [
        SimpleNamespace(
            id=11,
            machine_number="1",
            machine_name="1",
            commission_display="2026",
            exploitation_display="2026",
            date_commission_year=2026,
            date_exploitation=2026,
            decompressing_display="2032",
            modernization_display=None,
            tes_machine_type=None,
            pgu_tes_machine_type=None,
            powers_by_year={},
            note=None,
        ),
        SimpleNamespace(
            id=12,
            machine_number="ГТ-1",
            machine_name="ГТ-1",
            commission_display="2026",
            exploitation_display="2026",
            date_commission_year=2026,
            date_exploitation=2026,
            decompressing_display="2032",
            modernization_display=None,
            tes_machine_type=None,
            pgu_tes_machine_type=None,
            powers_by_year={},
            note=None,
        ),
    ]
    machine = SimpleNamespace(
        id=1,
        machine_group=1,
        machine_number=None,
        display_name="ПГУ",
        machine_name="ПГУ",
        gen_company=SimpleNamespace(id=5, name="ПАО «ТГК-1»"),
        date_commission_year=2026,
        date_exploitation=2026,
        decompressing_display="2032",
        modernization_display=None,
        tes_types="ТЭС",
        tes_machine_type=SimpleNamespace(id=1, name="ПГУ"),
        equipment_group=SimpleNamespace(name="ПГУ"),
        fuel_so="Газ",
        machine_fuels=[],
        pgu_machines=pgu_parts,
        powers_by_year={},
        base_rows=3,
        is_archived=False,
        note=None,
    )
    return SimpleNamespace(
        id=6453,
        name="Первомайская ТЭЦ (ТЭЦ-14)",
        machines=[machine],
        powers_by_year={},
    )


def test_pgu_power_extra_rows_have_cells_for_unspanned_columns():
    html = _render_tbody(_pgu_station())
    parser = _RowCollector()
    parser.feed(f"<table>{html}</table>")

    rasp_rows = [cells for cls, cells in parser.rows if "p-rasp-row" in cls]
    ogr_rows = [cells for cls, cells in parser.rows if "p-ogr-row" in cls]
    assert rasp_rows, html
    assert ogr_rows, html

    # Первая строка Ррасп — агрегат ПГУ, последняя — итог по станции.
    pgu_rasp = rasp_rows[0]
    texts = [text for _tag, _cls, text in pgu_rasp]
    assert texts[7] == "Ррасп", texts
    assert any("col-note" in cls for _tag, cls, _text in pgu_rasp)
    # 7 пустых слева + Ррасп + 8 лет мощности + примечание
    assert len(pgu_rasp) == 17, [(cls, text) for _tag, cls, text in pgu_rasp]

    pgu_ogr = ogr_rows[0]
    ogr_texts = [text for _tag, _cls, text in pgu_ogr]
    assert ogr_texts[7] == "Рогр", ogr_texts
    assert len(pgu_ogr) == 17, [(cls, text) for _tag, cls, text in pgu_ogr]

    # HTML-rowspan покрывает родителя, 2 части, Рогр и Ррасп (JS потом вычтет скрытые).
    machine_rowspans = re.findall(
        r'data-machine-base-rowspan="[^"]*"[^>]*rowspan="(\d+)"|rowspan="(\d+)"[^>]*data-machine-base-rowspan',
        html,
    )
    values = [int(a or b) for a, b in machine_rowspans]
    assert values, html
    assert all(r == 5 for r in values), values
