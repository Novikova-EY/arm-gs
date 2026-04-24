# -*- coding: utf-8 -*-
"""Заполнение справочника ProspectivePlaceTypeGES тремя каноническими наименованиями."""
from app.extensions import db
from app.generation.prospective_places.models.ges.prospective_place_type_ges_model import (
    PROSPECTIVE_PLACE_TYPE_GES_CANONICAL_NAMES,
    ProspectivePlaceTypeGES,
)


def ensure_canonical_prospective_place_types_ges() -> int:
    """
    Добавляет отсутствующие строки с точным текстом из PROSPECTIVE_PLACE_TYPE_GES_CANONICAL_NAMES.

    Returns:
        Число вставленных записей.
    """
    existing = {row[0] for row in db.session.query(ProspectivePlaceTypeGES.name).all()}
    added = 0
    for name in PROSPECTIVE_PLACE_TYPE_GES_CANONICAL_NAMES:
        if name not in existing:
            db.session.add(ProspectivePlaceTypeGES(name=name))
            added += 1
    if added:
        db.session.commit()
    return added
