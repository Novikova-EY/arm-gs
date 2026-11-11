from pathlib import Path
import re
from types import SimpleNamespace
from urllib.parse import urlsplit

from flask import Flask
import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("authenticated", [False, True])
def test_generation_page_styles_and_scripts_are_local(authenticated):
    app = Flask(__name__, template_folder=str(ROOT / "app/templates"),
                static_folder=str(ROOT / "app/static"))
    with app.test_request_context("/generation"):
        markup = app.jinja_env.get_template("generation/generation_start.html").render(
            current_user=SimpleNamespace(is_authenticated=authenticated, has_admin=True, username="Test"),
            url_for=lambda endpoint, **values: (
                "/static/" + values["filename"] if endpoint == "static" else "/" + endpoint
            ),
        )
    resources = re.findall(r'<(?:link|script)\b[^>]*(?:href|src)="([^"]+)"', markup)
    assert "/static/vendor/bootstrap-icons/bootstrap-icons.min.css" in resources
    with app.test_client() as client:
        for resource in resources:
            assert resource.startswith("/static/"), resource
            assert client.get(resource).status_code == 200, resource


def test_bootstrap_icon_fonts_are_packaged_with_stylesheet():
    vendor = ROOT / "app/static/vendor/bootstrap-icons"
    stylesheet = (vendor / "bootstrap-icons.min.css").read_text(encoding="utf-8")
    fonts = re.findall(r'url\("([^"]+)"\)', stylesheet)
    assert len(fonts) == 2
    for resource in fonts:
        font = vendor / urlsplit(resource).path
        expected_header = b"wOF2" if font.suffix == ".woff2" else b"wOFF"
        assert font.read_bytes().startswith(expected_header)
    assert "MIT License" in (vendor / "LICENSE").read_text(encoding="utf-8")
