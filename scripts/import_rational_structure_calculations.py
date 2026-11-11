"""Загрузка сохраненных результатов двух Excel-книг в явно выбранную версию БД.

Сначала разбор без записи:
  python scripts/import_rational_structure_calculations.py --runtime FILE --price FILE
Запись после применения миграции rs26102605:
  python scripts/import_rational_structure_calculations.py --runtime FILE --price FILE --apply --version-id 46
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app import create_app
from app.common.models.database_version_model import DatabaseVersion
from app.extensions import db
from app.rational_structure.models import CalculationWorkbook
from app.rational_structure.services.equipment_runtime_services import read_equipment_runtime_workbook
from app.rational_structure.services.marginal_price_services import read_marginal_price_workbook


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, required=True)
    parser.add_argument("--price", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--version-id", type=int)
    args = parser.parse_args()
    if args.apply and args.version_id is None:
        parser.error("Для записи укажите --version-id.")
    records = []
    for kind, path, reader in (("equipment_runtime", args.runtime, read_equipment_runtime_workbook),
                               ("marginal_price", args.price, read_marginal_price_workbook)):
        raw = path.read_bytes()
        records.append(dict(kind=kind, source_filename=path.name,
                            source_sha256=hashlib.sha256(raw).hexdigest(), data=reader(raw)))
    report = {record["kind"]: {
        "source": record["source_filename"], "sha256": record["source_sha256"],
        "sheets": {key: {"rows": len(table["rows"]), "errors": table["error_count"]}
                   for key, table in record["data"].items()},
    } for record in records}
    if args.apply:
        app = create_app()
        with app.app_context():
            version = db.session.get(DatabaseVersion, args.version_id)
            if version is None:
                raise ValueError("Указанная версия БД не найдена.")
            report["version"] = version.version_number
            report["version_id"] = version.id
            try:
                for record in records:
                    row = db.session.scalar(select(CalculationWorkbook).where(
                        CalculationWorkbook.database_version_id == version.id,
                        CalculationWorkbook.kind == record["kind"]))
                    if row is None:
                        row = CalculationWorkbook(database_version_id=version.id,
                                                  created_by="Импорт расчетных книг Excel")
                        db.session.add(row)
                    for field, value in record.items():
                        setattr(row, field, value)
                db.session.commit()
            except SQLAlchemyError:
                db.session.rollback()
                raise
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
