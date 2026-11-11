def test_powers_mock_is_served_as_json(app):
    response = app.test_client().get(
        "/static/mocks/rational_struct_export_from_java_powers.json"
    )

    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert "attachment" not in response.headers.get("Content-Disposition", "")
    assert response.get_json() == {
        "dataset": "rational_struct_export_from_java_powers",
        "version": "2026-07-01T00:00:00Z",
        "comment": "",
        "rows": [
            {
                "Номер расчета": 1,
                "Номер точки": 100,
                "Номер кластера": 5,
                "Код энергозоны (экспорт)": 10,
                "Установленная (расчетная) мощность, МВт": 100,
                "Тип технологии:": "АЭС",
                "Расчет принят пользователем": "admin",
                "Расчет принят (дата)": "admin",
                "external_code": "00000000-0000-0000-0008-000000000001",
            }
        ],
    }
