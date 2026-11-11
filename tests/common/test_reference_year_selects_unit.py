"""Все фильтры периода должны показывать годы справочника, а не локальные окна."""

from html.parser import HTMLParser
from pathlib import Path
import re
from types import SimpleNamespace

from flask import Flask
from jinja2 import Environment
import pytest

from app.common.services.get_services.years.years_get_services import get_reference_years
from app.refdata.services.years import year_services


TEMPLATES = Path(__file__).resolve().parents[2] / "app" / "templates"
SELECT_RE = re.compile(
    r'<select\b[^>]*\b(?:name=["\'](?:start_year|end_year)|id=["\']batchFilter(?:Start|End)Year)["\'][^>]*>.*?</select>',
    re.S,
)
YEAR_SELECTS = [
    pytest.param(match[0], id=f"{path.relative_to(TEMPLATES)}:{index}")
    for path in sorted(TEMPLATES.rglob("*.html"))
    for index, match in enumerate(SELECT_RE.finditer(path.read_text(encoding="utf-8-sig")))
]


class YearOptions(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.years = []
        self.selected = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "option" and attrs.get("value"):
            year = int(attrs["value"])
            self.years.append(year)
            if "selected" in attrs:
                self.selected.append(year)


@pytest.mark.parametrize("select", YEAR_SELECTS)
@pytest.mark.parametrize("years", [[2015, 2024, 2048], []])
def test_period_select_matches_reference_even_with_conflicting_local_years(select, years):
    env = Environment(autoescape=True)
    env.globals["get_reference_years"] = lambda: years
    rendered = env.from_string(select).render(
        filter_year_list=[2021, 2022, 2023], start_year=2024, end_year=2048,
        default_batch_filter_start_year=2024, default_batch_filter_end_year=2048,
    )
    options = YearOptions(rendered)
    assert options.years == years
    if years:
        selected = 2024 if 'name="start_year"' in select or 'id="batchFilterStartYear"' in select else 2048
        assert options.selected == [selected]


def test_reference_years_sorted_unique_and_cached_only_for_request(monkeypatch):
    rows = [2048, 2015, 2024, 2015]
    calls = []

    def year_query():
        calls.append(True)
        return SimpleNamespace(all=lambda: [SimpleNamespace(number=y) for y in rows])

    monkeypatch.setattr(year_services, "year_query", year_query)
    app = Flask(__name__)
    with app.test_request_context():
        assert get_reference_years() == [2015, 2024, 2048]
        assert get_reference_years() == [2015, 2024, 2048]
        assert len(calls) == 1

    # Следующий запрос видит изменения справочника / другую выбранную версию.
    rows[:] = [2031]
    with app.test_request_context():
        assert get_reference_years() == [2031]
    rows.clear()
    with app.test_request_context():
        assert get_reference_years() == []
        assert get_reference_years() == []
    assert len(calls) == 3
