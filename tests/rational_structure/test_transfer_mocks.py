import pytest


@pytest.mark.parametrize("dataset,version,comment,row", [
    (
        "rational_struct_functionals", "2026-07-01T00:00:00Z", "",
        {
            "Имя функционала": "Отн. недоотпуск",
            "Единица измерения функционала": "о.е.",
            "Максимальное значение функционала": -2.0,
            "external_code": "00000000-0000-0000-0008-000000000001",
        },
    ),
    (
        "rational_struct_k0", "2026-07-01T00:00:00Z",
        "Матрица коэффициентов k0 с именами зон",
        {
            "gs_k0_koef": 1.0,
            "Имя зоны начала (k0)": "z1",
            "Имя зоны конца (k0)": "z3",
            "external_code": "00000000-0000-0000-0010-000000000001",
        },
    ),
    (
        "rational_struct_load_graf_import_to_java", "2026-09-25T00:00:00Z",
        "Графики нагрузки по энергозонам",
        {
            "Код энергозоны": 1,
            "Год": 2026,
            "Период": 1,
            "Значение нагрузки, МВт": 14135.1,
            "external_code": "00000000-0000-0000-1001-000000000001",
        },
    ),
    (
        "rational_struct_zones", "2026-07-01T00:00:00Z",
        "Данные по энергозонам с текстовыми именами параметров",
        {
            "Ущербы по узлам": 200.0,
            "Коэффициенты наклона графиков нагрузки": 0.154,
            "Название зоны для рац.структуры": "z1",
            "Вектор МДП (0)": 780.0,
            "Вектор МДП (1)": 765.0,
            "Номер зоны для рац.структуры": 1,
            "external_code": "00000000-0000-0000-0009-000000000001",
        },
    ),
])
def test_transfer_mock_returns_exact_json(app, dataset, version, comment, row):
    response = app.test_client().get(f"/static/mocks/{dataset}.json")
    assert response.status_code == 200
    assert response.mimetype == "application/json"
    assert "attachment" not in response.headers.get("Content-Disposition", "")
    assert response.get_json() == {
        "dataset": dataset, "version": version, "comment": comment, "rows": [row],
    }


def test_mock_and_external_links_are_not_listed_as_public_datasets():
    from app.api.services.output_documents_catalog import (
        build_output_document_groups,
        list_enabled_output_document_datasets,
    )

    groups = build_output_document_groups(public_datasets=[])
    calculation = next(group for group in groups if group["title"] == "rational_struct_calc")
    for item in calculation["files"]:
        assert item["enabled"] is (item["kind"] in {"mock", "external"})
    assert list_enabled_output_document_datasets(public_datasets=[]) == ["database_versions"]
