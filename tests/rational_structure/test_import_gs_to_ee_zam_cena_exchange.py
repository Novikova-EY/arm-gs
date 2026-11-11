from copy import deepcopy

import pytest
from openpyxl import load_workbook
from sqlalchemy import select
from werkzeug.datastructures import MultiDict

from test_calculation_pages import calculation_database
from test_marginal_price_matching import matched_database
from test_technical_characteristics import database
from app.api.routes.exchange_api_routes import exchange_api_bp
from app.api.services.import_gs_to_ee_zam_cena_exchange_services import (
    load_import_gs_to_ee_zam_cena_dataset,
)
from app.api.services.output_documents_excel_export_services import (
    build_dataset_excel_bytes,
    load_output_document_payload_for_excel,
)
from app.extensions import db
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.generation.models.station.station_model import Station
from app.rational_structure.models import CalculationWorkbook
from app.rational_structure.services.marginal_price_services import build_marginal_price_context
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.years.year_feature_model import YearFeature
from app.refdata.models.years.year_model import Year


@pytest.fixture
def price_database(matched_database):
    for model in (UnionEnergySystem, RegionalEnergySystem):
        model.__table__.create(db.engine)
    db.session.execute(UnionEnergySystem.__table__.insert(), [
        {"id": 1, "name": "ОЭС Средней Волги", "database_version_id": 1},
        {"id": 2, "name": "Чужая ОЭС", "database_version_id": 2},
    ])
    db.session.execute(RegionalEnergySystem.__table__.insert(), [
        {"id": 1, "name": "РЭС", "name_full": "РЭС", "name_rp": "РЭС",
         "id_union_energy_system": 1, "database_version_id": 1},
        {"id": 2, "name": "Чужая РЭС", "name_full": "Чужая РЭС", "name_rp": "Чужой РЭС",
         "id_union_energy_system": 2, "database_version_id": 2},
    ])
    db.session.execute(Station.__table__.update().where(Station.id == 1).values(
        id_regional_energy_system=1,
        external_code="00000000-0000-0000-0016-100000000001",
    ))
    db.session.execute(YearFeature.__table__.insert(), [
        {"id": 1, "name": "План", "database_version_id": 1},
        {"id": 2, "name": "Факт", "database_version_id": 1},
        {"id": 3, "name": "Чужой признак", "database_version_id": 2},
    ])
    db.session.execute(Year.__table__.insert(), [
        {"number": 2042, "id_year_feature": 1, "database_version_id": 1},
        {"number": 2041, "id_year_feature": 2, "database_version_id": 1},
        {"number": 2042, "id_year_feature": 3, "database_version_id": 2},
    ])
    book = db.session.scalar(select(CalculationWorkbook).filter_by(kind="marginal_price"))
    data = deepcopy(book.data)
    for table in data.values():
        for row in table["rows"]:
            row["values"].update(N=30.23456789, O=500.12345678, Q=999999)
    book.data = data
    db.session.commit()
    return matched_database


def test_contract_and_page_values_with_mock_rounding(price_database):
    payload = load_import_gs_to_ee_zam_cena_dataset(version_id=1)
    assert payload["dataset"] == "import_gs_to_ee_zam_cena"
    assert payload["database_version"] == payload["version"] == 1
    assert payload["version_number"] == "v1"
    assert payload["comment"] == ""
    assert len(payload["rows"]) == 15
    assert {row["Группа ОЭС (ЗЦ)"] for row in payload["rows"]} == {
        "Европ.часть", "Юг", "Урал", "Сибирь", "Восток",
    }
    row = next(row for row in payload["rows"] if row["Группа ОЭС (ЗЦ)"] == "Восток")
    assert row == {
        "Группа ОЭС (ЗЦ)": "Восток",
        "ОЭС (ЗЦ)": "ОЭС Средней Волги",
        "Год": 2042,
        "План/Факт (ЗЦ)": "План",
        "Номер ступени": 1,
        "Название замыкающей станции ступени": "ТЭЦ Альфа",
        "Прогнозная цена электроэнергии замыкающей станции ГС, руб. без НДС/кВт*ч": 1.23,
        "Прогнозная продолжительность периода (полочки), час": 30.2,
        "Прогнозная мощность (полоски), МВт": 500.1,
        "Прогнозная выработка электроэнергии периода ГС (ЗЦ), млн кВт*ч": 100.0,
        "Прогнозная годовая выработка электроэнергии (ЗЦ), млн кВт*ч": 200,
        "station_external_code_zc": "00000000-0000-0000-0016-100000000001",
        "external_code": None,
    }
    context = build_marginal_price_context(MultiDict({"territory": "east", "rounding_digits": "-1"}), 1)
    assert row["Прогнозная годовая выработка электроэнергии (ЗЦ), млн кВт*ч"] == context["rows"][0]["annual_energy"]


@pytest.mark.parametrize("energies, expected_periods, expected_annual", [
    (["100.24", "100.25"], [100.2, 100.3], 200),
    (["100.25", "100.25"], [100.3, 100.3], 201),
    (["-100.25", "-100.25"], [-100.3, -100.3], -201),
])
def test_api_and_excel_round_like_mock_after_annual_sum(
    price_database, energies, expected_periods, expected_annual,
):
    book = db.session.scalar(select(CalculationWorkbook).filter_by(kind="marginal_price"))
    data = deepcopy(book.data)
    source_rows = [row for row in data["east"]["rows"] if int(row["values"]["A"]) == 2042]
    for source, energy in zip(source_rows, energies, strict=True):
        source["values"].update(C="2.005", N="30.25", O="500.05", P=energy)
    book.data = data
    db.session.commit()
    original_data = deepcopy(book.data)

    price_database.register_blueprint(exchange_api_bp, url_prefix="/api")
    response = price_database.test_client().get("/api/datasets/1/import_gs_to_ee_zam_cena?year=2042")
    assert response.status_code == 200
    rows = [row for row in response.json["rows"] if row["Группа ОЭС (ЗЦ)"] == "Восток"]
    assert len(rows) == 2
    for row, period in zip(rows, expected_periods, strict=True):
        assert row["Прогнозная цена электроэнергии замыкающей станции ГС, руб. без НДС/кВт*ч"] == 2.01
        assert row["Прогнозная продолжительность периода (полочки), час"] == 30.3
        assert row["Прогнозная мощность (полоски), МВт"] == 500.1
        assert row["Прогнозная выработка электроэнергии периода ГС (ЗЦ), млн кВт*ч"] == period
        annual = row["Прогнозная годовая выработка электроэнергии (ЗЦ), млн кВт*ч"]
        assert annual == expected_annual
        assert type(annual) is int

    payload = load_output_document_payload_for_excel("import_gs_to_ee_zam_cena", database_version=1)
    workbook = load_workbook(build_dataset_excel_bytes(payload))
    sheet = workbook.active
    headers = [cell.value for cell in sheet[1]]
    excel_rows = [dict(zip(headers, values)) for values in sheet.iter_rows(min_row=2, values_only=True)]
    assert [row for row in excel_rows if row["Группа ОЭС (ЗЦ)"] == "Восток" and row["Год"] == 2042] == rows
    workbook.close()

    db.session.expire(book)
    assert book.data == original_data


@pytest.mark.parametrize("filters, expected_years, count", [
    ({"year": 2041}, {2041}, 5),
    ({"start_year": 2042, "end_year": 2042}, {2042}, 10),
    ({"end_year": 2040}, set(), 0),
    ({"year": 2034}, set(), 0),
])
def test_year_filters(price_database, filters, expected_years, count):
    rows = load_import_gs_to_ee_zam_cena_dataset(version_id=1, **filters)["rows"]
    assert len(rows) == count
    assert {row["Год"] for row in rows} == expected_years
    if expected_years == {2041}:
        assert {row["План/Факт (ЗЦ)"] for row in rows} == {"Факт"}


@pytest.mark.parametrize("feature_name", ["факт", "план", "текущий (оценка)"])
def test_each_row_uses_its_year_feature_from_reference(price_database, feature_name):
    price_database.register_blueprint(exchange_api_bp, url_prefix="/api")
    client = price_database.test_client()
    url = "/api/datasets/1/import_gs_to_ee_zam_cena"
    initial_rows = client.get(url).json["rows"]
    assert {row["Год"] for row in initial_rows} == {2041, 2042}
    assert all(row["План/Факт (ЗЦ)"] == {2041: "Факт", 2042: "План"}[row["Год"]]
               for row in initial_rows)

    db.session.execute(YearFeature.__table__.update().where(
        YearFeature.id == 2,
    ).values(name=feature_name))
    db.session.commit()

    response = client.get(url)
    assert response.status_code == 200
    rows = response.json["rows"]
    assert len(rows) == len(initial_rows)
    expected_features = {2041: feature_name, 2042: "План"}
    assert all(row["План/Факт (ЗЦ)"] == expected_features[row["Год"]] for row in rows)


def test_missing_year_does_not_use_another_year_or_version_feature(price_database):
    db.session.execute(Year.__table__.delete().where(
        Year.database_version_id == 1, Year.number == 2042,
    ))
    db.session.commit()
    rows = load_import_gs_to_ee_zam_cena_dataset(version_id=1)["rows"]
    assert {row["Год"] for row in rows} == {2041, 2042}
    expected_features = {2041: "Факт", 2042: None}
    assert all(row["План/Факт (ЗЦ)"] == expected_features[row["Год"]] for row in rows)


def test_unmatched_station_is_not_replaced_by_equipment_group_name(price_database):
    row = load_import_gs_to_ee_zam_cena_dataset(version_id=1)["rows"][0]
    assert row["Название замыкающей станции ступени"] is None
    assert row["ОЭС (ЗЦ)"] is None
    assert row["station_external_code_zc"] is None
    assert row["Прогнозная выработка электроэнергии периода ГС (ЗЦ), млн кВт*ч"] == 100


def test_multiple_stations_keep_individual_codes_and_shared_annual_energy(price_database):
    db.session.execute(EquipmentGroupSetStation.__table__.insert(), {
        "id": 32, "station_id": 2, "database_version_id": 1,
    })
    db.session.execute(EquipmentGroupSet.__table__.insert(), {
        "equipment_group_id": 10, "equipment_group_set_station_id": 32,
    })
    db.session.commit()
    rows = [row for row in load_import_gs_to_ee_zam_cena_dataset(version_id=1)["rows"]
            if row["Группа ОЭС (ЗЦ)"] == "Восток" and row["Год"] == 2042 and row["Номер ступени"] == 1]
    assert [row["Название замыкающей станции ступени"] for row in rows] == ["ТЭЦ Альфа", "ТЭЦ Бета"]
    assert [row["station_external_code_zc"] for row in rows] == [
        "00000000-0000-0000-0016-100000000001", "station-2",
    ]
    assert [row["ОЭС (ЗЦ)"] for row in rows] == ["ОЭС Средней Волги", None]
    assert {row["Прогнозная годовая выработка электроэнергии (ЗЦ), млн кВт*ч"] for row in rows} == {200}


def test_errors_nulls_zeros_and_missing_year_feature(price_database):
    book = db.session.scalar(select(CalculationWorkbook).filter_by(kind="marginal_price"))
    data = deepcopy(book.data)
    data["east"]["rows"][0]["values"].update(C=0, N=None, O="#DIV/0!", P="#N/A")
    data["east"]["rows"][0]["errors"] = ["O", "P"]
    book.data = data
    db.session.execute(Year.__table__.update().where(
        Year.database_version_id == 1, Year.number == 2042,
    ).values(id_year_feature=None))
    db.session.commit()
    rows = [row for row in load_import_gs_to_ee_zam_cena_dataset(version_id=1)["rows"]
            if row["Группа ОЭС (ЗЦ)"] == "Восток" and row["Год"] == 2042]
    assert rows[0]["Прогнозная цена электроэнергии замыкающей станции ГС, руб. без НДС/кВт*ч"] == 0
    assert rows[0]["Прогнозная продолжительность периода (полочки), час"] is None
    assert rows[0]["Прогнозная мощность (полоски), МВт"] is None
    assert rows[0]["Прогнозная выработка электроэнергии периода ГС (ЗЦ), млн кВт*ч"] is None
    assert all(row["Прогнозная годовая выработка электроэнергии (ЗЦ), млн кВт*ч"] is None for row in rows)
    assert all(row["План/Факт (ЗЦ)"] is None for row in rows)


def test_reference_links_do_not_leak_other_version(price_database):
    db.session.execute(Station.__table__.update().where(Station.id == 1).values(id_regional_energy_system=2))
    db.session.execute(Year.__table__.update().where(
        Year.database_version_id == 1, Year.number == 2042,
    ).values(id_year_feature=3))
    db.session.commit()
    rows = load_import_gs_to_ee_zam_cena_dataset(version_id=1, year=2042)["rows"]
    assert all(row["ОЭС (ЗЦ)"] is None for row in rows)
    assert all(row["План/Факт (ЗЦ)"] is None for row in rows)


def test_api_version_isolation_and_excel(price_database):
    price_database.register_blueprint(exchange_api_bp, url_prefix="/api")
    client = price_database.test_client()
    url = "/api/datasets/1/import_gs_to_ee_zam_cena"
    response = client.get(url + "?start_year=2042&end_year=2042")
    assert response.status_code == 200
    assert len(response.json["rows"]) == 10
    assert client.get("/api/datasets/2/import_gs_to_ee_zam_cena").json["rows"] == []
    assert client.get("/api/datasets/999/import_gs_to_ee_zam_cena").status_code == 404
    assert "import_gs_to_ee_zam_cena" in client.get("/api/datasets/1").json["datasets"]
    payload = load_output_document_payload_for_excel("import_gs_to_ee_zam_cena", database_version=1)
    workbook = load_workbook(build_dataset_excel_bytes(payload))
    sheet = workbook.active
    headers = [cell.value for cell in sheet[1]]
    assert sheet.max_row == 16
    row = dict(zip(headers, [cell.value for cell in sheet[14]]))
    assert row["station_external_code_zc"] == "00000000-0000-0000-0016-100000000001"
    assert row["Прогнозная мощность (полоски), МВт"] == 500.1
    assert row["external_code"] is None
    workbook.close()
