"""Копирование связок Техинспекции по external_code во все версии БД.

Проверка без сохранения:
  python scripts/backfill_technical_inspection_codes.py
Применение:
  python scripts/backfill_technical_inspection_codes.py --apply

Параметры оборудования и годы не копируются. Неоднозначные связи пропускаются.
Для составляющих ПГУ используется external_code родителя и id_ti либо номер
составляющей. Без однозначного соответствия связь в другую версию не переносится.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.exc import SQLAlchemyError

from app import create_app
from app.extensions import db
from app.rational_structure.services.technical_inspection_code_services import TechnicalInspectionCodes


def backfill(*, apply=False, username="technical-inspection-backfill"):
    try:
        report = TechnicalInspectionCodes().backfill(username)
        db.session.flush()
        if apply:
            db.session.commit()
        else:
            db.session.rollback()
        return {"applied": apply, **report}
    except SQLAlchemyError:
        db.session.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Сохранить связи во всех версиях")
    args = parser.parse_args()
    app = create_app()
    with app.app_context():
        print(json.dumps(backfill(apply=args.apply), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
