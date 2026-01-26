# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app
from app.common.models.database_version_model import DatabaseVersion
from app.refdata.models.years.year_feature_model import YearFeature


def main() -> None:
    app = create_app()
    with app.app_context():
        active_version = DatabaseVersion.query.filter_by(is_active=True).first()
        if not active_version:
            raise SystemExit("Active version not found")
        features = (
            YearFeature.query.filter_by(database_version_id=active_version.id)
            .order_by(YearFeature.id)
            .all()
        )
        print("Active version:", active_version.id)
        for feature in features:
            name = feature.name or ""
            codepoints = [hex(ord(ch)) for ch in name]
            print(feature.id, repr(name), codepoints)


if __name__ == "__main__":
    main()
