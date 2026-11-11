from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.rational_structure.equipment_types import MATCHABLE_TYPES
from app.rational_structure.models import TurbineTechnicalCharacteristic
from app.rational_structure.services.technical_characteristic_excel_services import read_technical_characteristics
from app.rational_structure.services.technical_characteristic_machine_services import load_machine_candidates, load_pgu_machine_candidates, get_machine_station_id
from app.rational_structure.services.technical_characteristic_matching import MachineMatcher
from app.rational_structure.services.technical_inspection_code_services import TechnicalInspectionCodes


def import_technical_characteristics(raw: bytes, version_id: int, username: str, *, report_year: int | None = None) -> dict[str, int]:
    """Импортирует все годы файла; report_year не ограничивает загрузку."""
    if version_id is None:
        raise ValueError("Выберите версию базы данных перед загрузкой.")
    records = read_technical_characteristics(raw)
    model = TurbineTechnicalCharacteristic
    # Обратная совместимость: старые ключи + новые статусы
    counts = {"created": 0, "updated": 0, "steam": 0, "gas": 0, "matched": 0, "partial": 0, "ambiguous": 0, "unmatched": 0}

    try:
        codes = TechnicalInspectionCodes()
        matchers = {}
        years = {record["report_year"] for record in records}
        existing = db.session.scalars(select(model).where(
            model.database_version_id == version_id, model.report_year.in_(years)))
        by_key = {(row.turbine_type, row.equipment_code, row.report_year): row for row in existing}
        for record in records:
            key = (record["turbine_type"], record["equipment_code"], record["report_year"])
            row = by_key.get(key)
            if row is None:
                row = model(database_version_id=version_id, created_by=username, **record)
                db.session.add(row)
                by_key[key] = row
                counts["created"] += 1
            else:
                for field, value in record.items():
                    setattr(row, field, value)
                row.modified_by = username
                counts["updated"] += 1

            # У котлов нет соответствующего электрогенерирующего агрегата.
            if record["turbine_type"] in MATCHABLE_TYPES:
                match_result = codes.match(record["equipment_code"], version_id)
                if match_result is None:
                    year = record["report_year"]
                    if year not in matchers:
                        candidates = load_machine_candidates(version_id, year) + load_pgu_machine_candidates(version_id, year)
                        matchers[year] = MachineMatcher(candidates)
                    match_result = matchers[year].match(record)
                if match_result["match_status"] == "matched":
                    codes.remember(record["equipment_code"], match_result["machine_id"],
                                   match_result.get("pgu_machine_id"), username)
            else:
                match_result = {"match_status": "not_checked", "match_details": {}}
            row.machine_id = match_result.get("machine_id")
            row.pgu_machine_id = match_result.get("pgu_machine_id")
            row.match_status = match_result["match_status"]
            match_details = match_result.get("match_details", {})
            # Добавляем station_id для формирования ссылки на machine_details
            if row.machine_id:
                station_id = get_machine_station_id(row.machine_id, version_id)
                if station_id:
                    match_details["station_id"] = station_id
            row.match_details = match_details
            if record["turbine_type"] in MATCHABLE_TYPES:
                counts[row.match_status] = counts.get(row.match_status, 0) + 1

            equipment_type = record["turbine_type"]
            counts[equipment_type] = counts.get(equipment_type, 0) + 1
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        raise
    return counts
