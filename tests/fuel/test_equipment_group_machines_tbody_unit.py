# -*- coding: utf-8 -*-
"""Разметка tbody «Агрегаты группы оборудования»: rowspan ПГУ включает строку Ррасп."""
import os
import re
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader


TEMPLATES_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "app", "templates")
)


def _render_tbody(stations_with_machines, start_year=2024, end_year=2031):
    env = Environment(loader=FileSystemLoader(TEMPLATES_DIR), autoescape=True)
    env.globals["url_for"] = lambda *a, **k: "/x"
    env.globals["request"] = SimpleNamespace(args={})
    def _format_decimal(v, d=None):
        return "" if v in (None, 0) else str(v)

    env.globals["format_decimal"] = _format_decimal
    env.filters["format_decimal"] = _format_decimal
    tmpl = env.get_template("fuel/equipment_groups/_equipment_group_machines_tbody.html")
    return tmpl.render(
        stations_with_machines=stations_with_machines,
        start_year=start_year,
        end_year=end_year,
        equipment_group=SimpleNamespace(name="ТЭЦ-14 Первомайская", name_ext=""),
        show_equipment_group_total=False,
    )


def _pgu_station_bundle():
    pgu_parts = [
        SimpleNamespace(
            id=11,
            machine_name="1",
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
            machine_name="ГТ-1",
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
        gen_company=SimpleNamespace(name="ПАО «ТГК-1»"),
        date_commission_year=2026,
        date_exploitation=2026,
        decompressing_display="2032",
        modernization_display=None,
        tes_types="ТЭС",
        tes_machine_type=SimpleNamespace(id=1, name="ПГУ"),
        equipment_group=SimpleNamespace(name="ПГУ"),
        fuel_so="Газ",
        machine_fuel_param=SimpleNamespace(nt=135),
        machine_powers=[],
        machine_fuels=[],
        pgu_machines=pgu_parts,
        base_rows=3,
        note=None,
    )
    station = SimpleNamespace(
        id=100,
        name="Первомайская ТЭЦ (ТЭЦ-14)",
        machines_nt_sum=135,
        powers_by_year={},
    )
    return [(station, [machine])]


def test_pgu_rowspan_includes_rasp_row():
    html = _render_tbody(_pgu_station_bundle())
    # 2 части ПГУ + строка Руст родителя + строка Ррасп = 4
    machine_rowspans = re.findall(
        r'data-machine-base-rowspan="[^"]*"[^>]*rowspan="(\d+)"|rowspan="(\d+)"[^>]*data-machine-base-rowspan',
        html,
    )
    values = [int(a or b) for a, b in machine_rowspans]
    assert values, html
    assert all(r == 4 for r in values), values
    assert html.count("Ррасп") >= 2  # строка агрегата + итог по станции
    assert "Руст" in html
