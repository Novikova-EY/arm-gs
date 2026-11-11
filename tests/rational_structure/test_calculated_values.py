from http.client import IncompleteRead
from io import BytesIO
import json
from urllib.error import HTTPError, URLError

import pytest
from flask.templating import render_template

from test_technical_characteristics import database, http_client
from app.rational_structure.routes import calculated_values_routes as routes
from app.rational_structure.services import calculated_values_services as services


@pytest.fixture
def results_client(http_client, monkeypatch):
    monkeypatch.setattr(routes, "render_template", render_template)
    return http_client[0]


def mock_response(monkeypatch, key, rows, **metadata):
    payload = {
        "dataset": services.RESULT_DATASETS[key]["dataset"],
        "version": "2026-07-01T00:00:00Z",
        "comment": "",
        "rows": rows,
    }
    payload.update(metadata)
    calls = []

    def open_response(request, timeout):
        calls.append((request.full_url, request.get_header("Accept"), timeout))
        return BytesIO(json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    monkeypatch.setattr(services, "urlopen", open_response)
    return calls


@pytest.mark.parametrize("key", ["technologies", "powers"])
def test_hub_links_to_result_pages_without_fetching_remote_data(results_client, monkeypatch, key):
    def unexpected_request(*args, **kwargs):
        pytest.fail("The hub must not fetch remote results")

    monkeypatch.setattr(services, "urlopen", unexpected_request)
    response = results_client.get("/rational_structure/")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Рассчитанные значения" in html
    assert f'href="/rational_structure/calculated_values/{key}"' in html
    assert '<table ' not in html
    assert 'data-load-results' not in html
    assert 'js/rational_structure/calculated_values.js' not in html


@pytest.mark.parametrize("dataset_prefix", ["", "v_"])
@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize("key", ["technologies", "powers"])
def test_results_show_all_calculations_and_original_values(results_client, monkeypatch, key, as_json, dataset_prefix):
    columns = services.RESULT_DATASETS[key]["columns"]
    row = dict.fromkeys(columns, 0.0)
    row.update({
        "Номер расчета": 1, "Номер точки": 100, "Номер кластера": 5,
        "Расчет принят пользователем": "admin", "Расчет принят (дата)": "admin",
        "external_code": "00000000-0000-0000-0008-000000000001",
    })
    if key == "powers":
        row.update({"Код энергозоны (экспорт)": 10,
                    "Установленная (расчетная) мощност": 100, "Тип технологии": "АЭС"})
    rows = [row, dict(row, **{"Номер расчета": 2, "Номер точки": 200, "external_code": "second-result"})]
    if key == "powers":
        rows.append(dict(row, **{"Код энергозоны (экспорт)": 20, "Тип технологии": "ГЭС"}))
    dataset = dataset_prefix + services.RESULT_DATASETS[key]["dataset"]
    calls = mock_response(monkeypatch, key, rows, dataset=dataset)
    response = results_client.get(
        f"/rational_structure/calculated_values/{key}?load=1&calculation=1",
        headers={"Accept": "application/json"} if as_json else {},
    )
    html = response.get_json()["html"] if as_json else response.get_data(as_text=True)
    assert response.status_code == 200
    assert "2026-07-01T00:00:00Z" in html
    assert dataset in html
    assert "second-result" in html
    assert "<td class=\"text-nowrap\">200</td>" in html
    assert html.count("<tr>") == len(rows) + 1
    assert all(column in html for column in columns)
    if key == "technologies":
        assert '>0.0</td>' in html
    else:
        assert "АЭС" in html and "ГЭС" in html
    assert calls == [(
        "http://10.31.224.135:8080/api/v1/external-sync/views/ge_stage/v_" + services.RESULT_DATASETS[key]["dataset"],
        "application/json", 30,
    )]


@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize("power,technology", [(600.0, "ВИЭ  р-на z6"), (0, "АЭС"), (None, None)])
def test_powers_api_field_names_fill_display_columns(results_client, monkeypatch, as_json, power, technology):
    mock_response(monkeypatch, "powers", [{
        "Установленная (расчетная) мощност": power,
        "Тип технологии": technology,
        "Дата создания": "2026-10-28T08:42:24.447+00:00",
    }], dataset="v_rational_struct_export_from_java_powers")
    response = results_client.get(
        "/rational_structure/calculated_values/powers?load=1",
        headers={"Accept": "application/json"} if as_json else {},
    )
    assert response.status_code == 200
    html = response.get_json()["html"] if as_json else response.get_data(as_text=True)
    assert '<th scope="col">Установленная (расчетная) мощность, МВт</th>' not in html
    assert '<th scope="col">Тип технологии:</th>' not in html
    assert (
        '<thead><tr><th scope="col">Установленная (расчетная) мощност</th>'
        '<th scope="col">Тип технологии</th><th scope="col">Дата создания</th></tr></thead>'
    ) in html
    power_text = power if power is not None else "–"
    technology_text = technology if technology is not None else "–"
    assert (
        f'<td class="text-nowrap">{power_text}</td><td class="text-nowrap">{technology_text}</td>'
    ) in html


def test_powers_original_fields_are_not_renamed_or_overwritten(monkeypatch):
    row = {
        "Установленная (расчетная) мощност": 600.0,
        "Установленная (расчетная) мощность, МВт": 0,
        "Тип технологии": "ВИЭ",
        "Тип технологии:": None,
    }
    mock_response(monkeypatch, "powers", [row])
    result = services.fetch_calculated_values("powers")
    assert result["rows"] == [row]
    assert result["columns"] == list(row)


@pytest.mark.parametrize("key", ["technologies", "powers"])
def test_result_columns_follow_api_field_order_and_include_later_fields(monkeypatch, key):
    rows = [{"Тип технологии": "ВИЭ", "Номер расчета": 4}, {"Дата создания": None, "Номер расчета": 5}]
    mock_response(monkeypatch, key, rows)
    result = services.fetch_calculated_values(key)
    assert result["columns"] == ["Тип технологии", "Номер расчета", "Дата создания"]
    assert result["rows"] == rows


@pytest.mark.parametrize("key", ["technologies", "powers"])
@pytest.mark.parametrize("as_json", [False, True])
def test_empty_results_have_explicit_message(results_client, monkeypatch, key, as_json):
    calls = mock_response(monkeypatch, key, [])
    response = results_client.get(
        f"/rational_structure/calculated_values/{key}",
        query_string={} if as_json else {"load": "1"},
        headers={"Accept": "application/json"} if as_json else {},
    )
    assert response.status_code == 200
    html = response.get_json()["html"] if as_json else response.get_data(as_text=True)
    assert "API не вернул принятых результатов" in html
    assert f'id="rs-result-table-{key}"' in html
    assert len(calls) == 1


@pytest.mark.parametrize("as_json", [False, True])
def test_results_escape_external_text_and_preserve_null_and_extra_columns(results_client, monkeypatch, as_json):
    mock_response(monkeypatch, "powers", [{
        "Тип технологии:": "<script>alert(1)</script>", "external_code": None,
        "Дополнительный показатель": 0,
    }], comment="<img src=x onerror=alert(1)>")
    response = results_client.get(
        "/rational_structure/calculated_values/powers?load=1",
        headers={"Accept": "application/json"} if as_json else {},
    )
    html = response.get_json()["html"] if as_json else response.get_data(as_text=True)
    assert response.status_code == 200
    assert "<script>" not in html and "<img" not in html
    assert "&lt;script&gt;" in html and "&lt;img" in html
    assert "Дополнительный показатель" in html
    assert '>0</td>' in html and '>–</td>' in html


@pytest.mark.parametrize("payload", [
    [], {"dataset": "wrong", "rows": []},
    {"dataset": "v_rational_struct_export_from_java_technologies", "rows": []},
    {"dataset": "vv_rational_struct_export_from_java_powers", "rows": []},
    {"dataset": "rational_struct_export_from_java_powers_v", "rows": []},
    {"dataset": ["rational_struct_export_from_java_powers"], "rows": []},
    {"dataset": "rational_struct_export_from_java_powers", "rows": {}},
    {"dataset": "rational_struct_export_from_java_powers", "rows": [None]},
    {"dataset": "rational_struct_export_from_java_powers", "rows": [{"x": []}]},
])
def test_invalid_contract_is_reported(results_client, monkeypatch, payload):
    monkeypatch.setattr(services, "urlopen", lambda *a, **k: BytesIO(json.dumps(payload).encode()))
    response = results_client.get("/rational_structure/calculated_values/powers?load=1")
    assert response.status_code == 502
    assert "API вернул некорректные данные" in response.get_data(as_text=True)


@pytest.mark.parametrize("raw", [b"<html>not JSON</html>", b"\xff"])
def test_invalid_json_is_reported(results_client, monkeypatch, raw):
    monkeypatch.setattr(services, "urlopen", lambda *a, **k: BytesIO(raw))
    response = results_client.get("/rational_structure/calculated_values/powers?load=1")
    assert response.status_code == 502
    assert "API вернул некорректные данные" in response.get_data(as_text=True)


@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize("exception,status,message", [
    (TimeoutError(), 504, "Превышено время ожидания"),
    (HTTPError("http://api", 503, "Unavailable", {}, None), 502, "HTTP 503"),
    (URLError("offline"), 502, "Не удалось подключиться"),
    (IncompleteRead(b"partial"), 502, "Не удалось подключиться"),
])
def test_remote_errors_allow_retry(results_client, monkeypatch, exception, status, message, as_json):
    def fail(*args, **kwargs):
        raise exception

    monkeypatch.setattr(services, "urlopen", fail)
    headers = {"Accept": "application/json"} if as_json else {}
    response = results_client.get("/rational_structure/calculated_values/powers?load=1", headers=headers)
    assert response.status_code == status
    if as_json:
        assert message in response.get_json()["error"]
        assert "html" not in response.get_json()
    else:
        html = response.get_data(as_text=True)
        assert message in html and "Получить данные из API" in html
        assert 'id="rs-result-table-powers"' in html
    mock_response(monkeypatch, "powers", [])
    retry = results_client.get("/rational_structure/calculated_values/powers?load=1", headers=headers)
    assert retry.status_code == 200
    if as_json:
        assert "API не вернул принятых результатов" in retry.get_json()["html"]


@pytest.mark.parametrize("key", ["technologies", "powers"])
@pytest.mark.parametrize("as_json", [False, True])
def test_empty_view_404_is_shown_as_no_results(results_client, monkeypatch, key, as_json):
    body = json.dumps({
        "message": "Представление пусто или не содержит записей для текущей сессии",
        "status": "error",
    }, ensure_ascii=False).encode("utf-8")
    error = HTTPError("http://api", 404, "Not Found", {}, BytesIO(body))

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(services, "urlopen", fail)
    response = results_client.get(
        f"/rational_structure/calculated_values/{key}?load=1",
        headers={"Accept": "application/json"} if as_json else {},
    )
    assert response.status_code == 200
    html = response.get_json()["html"] if as_json else response.get_data(as_text=True)
    assert "API не вернул принятых результатов" in html
    assert services.RESULT_DATASETS[key]["dataset"] in html
    assert all(column in html for column in services.RESULT_DATASETS[key]["columns"])
    assert error.closed


@pytest.mark.parametrize("body", [
    b"<html>Not Found</html>", b"\xff", b"[]", b"{}",
    b'{"status": "error", "message": "Unknown view"}',
    json.dumps({
        "status": "ok",
        "message": "Представление пусто или не содержит записей для текущей сессии",
    }).encode("utf-8"),
])
@pytest.mark.parametrize("as_json", [False, True])
def test_other_404_responses_remain_errors(results_client, monkeypatch, body, as_json):
    error = HTTPError("http://api", 404, "Not Found", {}, BytesIO(body))

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(services, "urlopen", fail)
    response = results_client.get(
        "/rational_structure/calculated_values/technologies?load=1",
        headers={"Accept": "application/json"} if as_json else {},
    )
    assert response.status_code == 502
    message = response.get_json()["error"] if as_json else response.get_data(as_text=True)
    assert "HTTP 404" in message
    assert error.closed


def test_empty_view_message_with_server_error_remains_an_error(results_client, monkeypatch):
    body = json.dumps({
        "message": "Представление пусто или не содержит записей для текущей сессии",
        "status": "error",
    }).encode("utf-8")

    def fail(*args, **kwargs):
        raise HTTPError("http://api", 503, "Unavailable", {}, BytesIO(body))

    monkeypatch.setattr(services, "urlopen", fail)
    response = results_client.get(
        "/rational_structure/calculated_values/technologies?load=1",
        headers={"Accept": "application/json"},
    )
    assert response.status_code == 502
    assert "HTTP 503" in response.get_json()["error"]


def test_unknown_dataset_is_not_requested(results_client, monkeypatch):
    def unexpected_request(*args, **kwargs):
        pytest.fail("Unknown datasets must not be requested")

    monkeypatch.setattr(services, "urlopen", unexpected_request)
    assert results_client.get("/rational_structure/calculated_values/unknown").status_code == 404


def test_results_require_authentication(results_client, monkeypatch):
    def unexpected_request(*args, **kwargs):
        pytest.fail("Anonymous requests must not reach the external API")

    monkeypatch.setattr(services, "urlopen", unexpected_request)
    with results_client.session_transaction() as session:
        session.clear()
    assert results_client.get("/rational_structure/calculated_values/powers").status_code == 401
    assert results_client.get(
        "/rational_structure/calculated_values/powers", headers={"Accept": "application/json"},
    ).status_code == 401


@pytest.mark.parametrize("key", ["technologies", "powers"])
def test_result_page_opens_with_empty_table_without_calling_api(results_client, monkeypatch, key):
    def unexpected_request(*args, **kwargs):
        pytest.fail("Opening a result page must not fetch the external API")

    monkeypatch.setattr(services, "urlopen", unexpected_request)
    response = results_client.get(f"/rational_structure/calculated_values/{key}")
    html = response.get_data(as_text=True)
    other_key = "powers" if key == "technologies" else "technologies"
    assert response.status_code == 200
    assert html.count('<table ') == 1
    assert f'id="rs-result-table-{key}"' in html
    assert f'id="rs-result-table-{other_key}"' not in html
    assert all(f'<th scope="col">{column}</th>' in html for column in services.RESULT_DATASETS[key]["columns"])
    assert 'Данные еще не загружены.' in html
    assert html.count('data-load-results') == 1
    assert f'data-url="/rational_structure/calculated_values/{key}"' in html
    assert 'Получить данные из API' in html
    assert 'js/rational_structure/calculated_values.js' in html
    assert f'href="/rational_structure/calculated_values/{other_key}"' in html
    assert 'href="/rational_structure/"' in html
    assert 'load=1' in html
    assert 'text-danger' not in html
