# -*- coding: utf-8 -*-
"""
Ограничения (аналог таблицы «Ограничения» из Access, см. Ограничения.xsd).
Сортировка по умолчанию при открытии формы в Access: по полю obl.
"""
from sqlalchemy.sql import func

from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_REFDATA


class FuelRestriction(db.Model):
    __tablename__ = "gs_fue_restrictions"
    __table_args__ = {"schema": SCHEMA_FUEL}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Год (в Access — double)
    year = db.Column(db.Numeric(36, 16), nullable=True)
    # Код ОЭС (oes)
    oes = db.Column(db.Numeric(36, 16), nullable=True)
    # Наименование (поле name в Access)
    restriction_name = db.Column("name", db.String(50), nullable=True)
    # Код субъекта РФ (obl)
    obl = db.Column(db.Numeric(36, 16), nullable=True)
    # Минимальная выработка (emin)
    emin = db.Column(db.Numeric(36, 16), nullable=True)
    # Максимальная выработка (emax)
    emax = db.Column(db.Numeric(36, 16), nullable=True)
    # Текущая выработка (ecur)
    ecur = db.Column(db.Numeric(36, 16), nullable=True)
    # Поле H в Access
    h = db.Column("h", db.Numeric(36, 16), nullable=True)
    # Текущая выработка с учётом ограничения (ecurdis)
    ecurdis = db.Column(db.Numeric(36, 16), nullable=True)
    # H с учётом ограничения (hdis)
    hdis = db.Column(db.Numeric(36, 16), nullable=True)
    # Выработка Этц (etp)
    etp = db.Column(db.Numeric(36, 16), nullable=True)
    # Коэффициент по субъекту (kobl)
    kobl = db.Column(db.Numeric(36, 16), nullable=True)
    # Текущий коэффициент (kcur)
    kcur = db.Column(db.String(50), nullable=True)

    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# Заголовки столбцов (порядок как в XSD / форме Access)
FUEL_RESTRICTION_LIST_COLUMN_HEADINGS: list[tuple[str, str]] = [
    ("year", "Год"),
    ("oes", "ОЭС (oes)"),
    ("restriction_name", "Наименование (name)"),
    ("obl", "obl"),
    ("emin", "emin"),
    ("emax", "emax"),
    ("ecur", "ecur"),
    ("h", "H"),
    ("ecurdis", "ecurdis"),
    ("hdis", "Hdis"),
    ("etp", "etp"),
    ("kobl", "kobl"),
    ("kcur", "kcur"),
]
