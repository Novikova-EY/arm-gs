from pathlib import Path
from threading import Thread

import pytest
from flask import current_app
from flask_login import current_user
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
from werkzeug.serving import make_server

from test_user_settings_reset import TestUser, settings_app
from app.auth.forms.users_forms import UsersBulkForm
from app.auth.services import user_settings_services as settings
from app.common.models.pagination import Pagination

pytest.importorskip("selenium")
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


@pytest.fixture
def settings_server(settings_app):
    root = Path(__file__).resolve().parents[2]
    settings_app.static_folder = str(root / "app/static")
    settings_app.jinja_loader = ChoiceLoader([
        DictLoader({"base.html": '''<!doctype html><html><head>
        {% if user_settings_reset %}
        <script id="user-settings-reset-config" type="application/json">{{ user_settings_reset|tojson }}</script>
        <script src="/static/js/common/user_settings_reset.js"></script>
        {% endif %}</head><body>{% block content %}{% endblock %}</body></html>'''}),
        FileSystemLoader(str(root / "app/templates")),
    ])

    @settings_app.get("/test-users")
    def test_users():
        target = TestUser(2)
        target.email = "target@example.com"
        context = dict(
            current_user=current_user, users=[target], roles=[], form=UsersBulkForm(),
            pagination=Pagination(page=1, per_page=50, total=1), q="", sort_by="id", sort_dir="asc", per_page=50,
        )
        current_app.update_template_context(context)
        return current_app.jinja_env.get_template("auth/users/users.html").render(context)

    settings_app.view_functions["users_bp.list_users"] = lambda: "Users after reset"
    server = make_server("127.0.0.1", 0, settings_app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield settings_app, f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()


def test_confirmation_separate_submission_and_browser_reset(settings_server):
    app, url = settings_server
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    browser = webdriver.Chrome(options=options)
    try:
        browser.get(url + "/login/1")
        browser.get(url + "/test-users")
        button = browser.find_element(By.CSS_SELECTOR, '[form="reset-settings-2"]')
        browser.execute_script("document.querySelector('[name=\"emails[]\"]').value = ''")
        button.click()
        WebDriverWait(browser, 5).until(lambda driver: driver.switch_to.alert)
        browser.switch_to.alert.dismiss()
        assert browser.current_url.endswith("/test-users")
        with app.app_context():
            assert settings.get_settings_reset_token(2) == ""
        button.click()
        browser.switch_to.alert.accept()
        WebDriverWait(browser, 5).until(lambda driver: driver.current_url.endswith("/users?q=&sort_by=id&sort_dir=asc&page=1&per_page=50"))
        with app.app_context():
            assert settings.get_settings_reset_token(2)
            assert settings.get_settings_reset_token(1) == ""
        browser.execute_script("localStorage.setItem('rounding_digits', '5'); sessionStorage.setItem('pdEcSummaryNtDetail_oes', '1'); sessionStorage.setItem('fuel-db-import:2', 'keep-job');")
        browser.get(url + "/test-users")
        assert browser.execute_script("return localStorage.getItem('rounding_digits')") == "5"
        browser.get(url + "/login/2")
        browser.get(url + "/test-users")
        assert browser.execute_script("return localStorage.getItem('rounding_digits')") is None
        assert browser.execute_script("return sessionStorage.getItem('pdEcSummaryNtDetail_oes')") is None
        assert browser.execute_script("return sessionStorage.getItem('fuel-db-import:2')") == "keep-job"
        browser.execute_script("localStorage.setItem('rounding_digits', '3')")
        browser.refresh()
        assert browser.execute_script("return localStorage.getItem('rounding_digits')") == "3"
    finally:
        browser.quit()
