"""Замыкающие цены из расчетной книги выбранной версии БД."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.api.services.exchange_common_services import (
    clip_years,
    dataset_envelope,
    resolve_database_version,
)
from app.common.services.excel_numeric_cell import parse_excel_numeric
from app.common.services.help_services import rounded_decimal
from app.extensions import db
from app.generation.models.station.station_model import Station
from app.rational_structure.models.calculation_workbook_model import CalculationWorkbook
from app.rational_structure.services.marginal_price_matching_services import match_marginal_price_tables
from app.rational_structure.services.marginal_price_services import (
    TERRITORY_SHEETS,
    calculate_marginal_price_annual_energy,
)
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.years.year_feature_model import YearFeature
from app.refdata.models.years.year_model import Year

DATASET_IMPORT_GS_TO_EE_ZAM_CENA = "import_gs_to_ee_zam_cena"

PRICE_EXCHANGE_FIELDS = (
    ("Прогнозная цена электроэнергии замыкающей станции ГС, руб. без НДС/кВт*ч", "C", 2),
    ("Прогнозная продолжительность периода (полочки), час", "N", 1),
    ("Прогнозная мощность (полоски), МВт", "O", 1),
    ("Прогнозная выработка электроэнергии периода ГС (ЗЦ), млн кВт*ч", "P", 1),
)


def load_import_gs_to_ee_zam_cena_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    resolved_id, version_number = resolve_database_version(version_id)
    workbook = None
    if resolved_id is not None:
        workbook = db.session.scalar(select(CalculationWorkbook).where(
            CalculationWorkbook.database_version_id == resolved_id,
            CalculationWorkbook.kind == "marginal_price",
        ))
    rows = []
    if workbook is not None:
        tables = match_marginal_price_tables(workbook.data, resolved_id)
        years = clip_years(
            (int(row["values"]["A"]) for table in tables.values() for row in table["rows"]),
            year=year, start_year=start_year, end_year=end_year,
        )
        features = dict(db.session.execute(select(Year.number, YearFeature.name).join(
            YearFeature, YearFeature.id == Year.id_year_feature,
        ).where(
            Year.database_version_id == resolved_id,
            YearFeature.database_version_id == resolved_id,
            Year.number.in_(years),
        )).all())
        station_ids = {
            station["id"] for table in tables.values() for row in table["rows"]
            for station in row["stations"]
        }
        stations = {station.id: station for station in db.session.execute(select(
            Station.id, Station.name, Station.external_code,
            UnionEnergySystem.name.label("oes"),
        ).outerjoin(RegionalEnergySystem, (
            (RegionalEnergySystem.id == Station.id_regional_energy_system)
            & (RegionalEnergySystem.database_version_id == resolved_id)
        )).outerjoin(UnionEnergySystem, (
            (UnionEnergySystem.id == RegionalEnergySystem.id_union_energy_system)
            & (UnionEnergySystem.database_version_id == resolved_id)
        )).where(
            Station.database_version_id == resolved_id,
            Station.id.in_(station_ids),
        ))}
        for territory, title in TERRITORY_SHEETS.items():
            if territory not in tables:
                continue
            for source in calculate_marginal_price_annual_energy(tables[territory]["rows"]):
                calculation_year = int(source["values"]["A"])
                if calculation_year not in years:
                    continue
                row = {
                    "Группа ОЭС (ЗЦ)": title,
                    "ОЭС (ЗЦ)": None,
                    "Год": calculation_year,
                    "План/Факт (ЗЦ)": features.get(calculation_year),
                    "Номер ступени": source["values"].get("B") if "B" not in source["errors"] else None,
                    "Название замыкающей станции ступени": None,
                }
                row.update({
                    label: parse_excel_numeric(rounded_decimal(source["values"].get(column), digits))
                    if column not in source["errors"] else None
                    for label, column, digits in PRICE_EXCHANGE_FIELDS
                })
                annual_energy = rounded_decimal(source["annual_energy"], digits=0)
                row["Прогнозная годовая выработка электроэнергии (ЗЦ), млн кВт*ч"] = (
                    int(annual_energy) if annual_energy is not None else None
                )
                row["station_external_code_zc"] = None
                row["external_code"] = None
                # Несопоставленная строка сохраняет показатели, но не получает вымышленную станцию.
                if not source["stations"]:
                    rows.append(row)
                for link in source["stations"]:
                    station = stations[link["id"]]
                    rows.append({
                        **row,
                        "ОЭС (ЗЦ)": station.oes,
                        "Название замыкающей станции ступени": station.name,
                        "station_external_code_zc": station.external_code,
                    })
    return dataset_envelope(
        DATASET_IMPORT_GS_TO_EE_ZAM_CENA,
        database_version=resolved_id,
        version_number=version_number,
        rows=rows,
    )
