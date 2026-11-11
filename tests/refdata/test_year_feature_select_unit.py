from html.parser import HTMLParser
from pathlib import Path
import re
from types import SimpleNamespace

from jinja2 import Environment
import pytest


TEMPLATE = Path(__file__).resolve().parents[2] / "app/templates/refdata/years/year/year.html"


class FeatureOptions(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.options = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == "option":
            self.options.append(dict(attrs))

    def handle_data(self, data):
        if self.options and data.strip():
            self.options[-1]["text"] = data.strip()


@pytest.mark.parametrize("feature_id, expected_value, expected_text", [
    (None, "", "Не указан"),
    (81, "81", "план"),
    (80, "80", "текущий (оценка)"),
    (79, "79", "факт"),
])
def test_year_feature_select_shows_saved_value_or_explicit_empty_option(
    feature_id, expected_value, expected_text,
):
    select = re.search(
        r'<select\b[^>]*name="year_features\[\]"[^>]*>.*?</select>',
        TEMPLATE.read_text(encoding="utf-8-sig"), re.S,
    ).group()
    html = Environment(autoescape=True).from_string(select).render(
        y=SimpleNamespace(id_year_feature=feature_id),
        year_features=[(81, "план"), (80, "текущий (оценка)"), (79, "факт")],
        version_id=37,
    )
    options = FeatureOptions(html).options
    selected = [option for option in options if "selected" in option]
    assert len(selected) == 1
    assert selected[0]["value"] == expected_value
    assert selected[0]["text"] == expected_text
    assert options[0]["value"] == ""
