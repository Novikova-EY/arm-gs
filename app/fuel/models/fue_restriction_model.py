# -*- coding: utf-8 -*-
"""
Ограничения (аналог таблицы «Ограничения» из Access, см. Ограничения.xsd).
Сортировка по умолчанию при открытии формы в Access: по полю obl.
"""
from sqlalchemy import Integer, cast
from sqlalchemy.sql import func
from sqlalchemy.types import String

from app.extensions import db
from app.fuel.models.external_mapping.fue_em_territories_energy_model import (
    TerritoriesEnergyExternalMapping,
)
from app.fuel.models.external_mapping.fue_em_union_energy_system_model import (
    UnionEnergySystemExternalMapping,
)
from app.refdata.models.energy_systems.regional_energy_system_model import (
    RegionalEnergySystem,
)
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from config import SCHEMA_FUEL, SCHEMA_REFDATA


def _access_code_as_str(column):
    """Numeric Access-код → строковый external_id ('1', не '1.0000…')."""
    return cast(cast(column, Integer), String)


class FuelRestriction(db.Model):
    __tablename__ = "gs_fue_restrictions"
    __table_args__ = {"schema": SCHEMA_FUEL}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Год Access (year) → Year.number (+ database_version_id)
    year = db.Column(db.Numeric(36, 16), nullable=True, index=True)
    year_ref = db.relationship(
        "Year",
        lazy="select",
        primaryjoin=(
            "and_(Year.number==cast(FuelRestriction.year, Integer), "
            "Year.database_version_id==FuelRestriction.database_version_id)"
        ),
        foreign_keys="[FuelRestriction.year, FuelRestriction.database_version_id]",
        viewonly=True,
        uselist=False,
    )
    # Код ОЭС Access (oes) → UnionEnergySystemExternalMapping.external_id
    # → UnionEnergySystem (справочник /fuel/refdata/union_energy_system)
    oes = db.Column(db.Numeric(36, 16), nullable=True, index=True)
    oes_union_energy_system_mapping = db.relationship(
        "UnionEnergySystemExternalMapping",
        foreign_keys=[oes],
        primaryjoin=_access_code_as_str(oes)
        == UnionEnergySystemExternalMapping.external_id,
        viewonly=True,
        uselist=False,
    )
    # Наименование (поле name в Access)
    restriction_name = db.Column("name", db.String(50), nullable=True)
    # Код РЭС Access (obl) → TerritoriesEnergyExternalMapping.external_id
    # → RegionalEnergySystem (справочник /fuel/refdata/territories_energy)
    obl = db.Column(db.Numeric(36, 16), nullable=True, index=True)
    obl_territories_energy = db.relationship(
        "TerritoriesEnergyExternalMapping",
        foreign_keys=[obl],
        primaryjoin=_access_code_as_str(obl)
        == TerritoriesEnergyExternalMapping.external_id,
        viewonly=True,
        uselist=False,
    )
    # Минимальная выработка (emin)
    emin = db.Column(db.Numeric(36, 16), nullable=True)
    # Максимальная выработка (emax)
    emax = db.Column(db.Numeric(36, 16), nullable=True)
    # Текущая выработка (ecur)
    ecur = db.Column(db.Numeric(36, 16), nullable=True)
    # ЧЧИУМ, ч (Access H)
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

    @property
    def union_energy_system(self):
        """ОЭС через oes_union_energy_system_mapping.union_energy_system_ref_uuid."""
        uem = self.oes_union_energy_system_mapping
        if uem is None or uem.union_energy_system_ref_uuid is None:
            return None
        q = UnionEnergySystem.query.filter(
            UnionEnergySystem.ref_uuid == uem.union_energy_system_ref_uuid
        )
        if self.database_version_id is not None:
            q = q.filter(UnionEnergySystem.database_version_id == self.database_version_id)
        return q.first()

    @property
    def regional_energy_system(self):
        """РЭС через obl_territories_energy.regional_energy_system_ref_uuid."""
        tm = self.obl_territories_energy
        if tm is None or tm.regional_energy_system_ref_uuid is None:
            return None
        q = RegionalEnergySystem.query.filter(
            RegionalEnergySystem.ref_uuid == tm.regional_energy_system_ref_uuid
        )
        if self.database_version_id is not None:
            q = q.filter(
                RegionalEnergySystem.database_version_id == self.database_version_id
            )
        return q.first()


# Заголовки столбцов: (attr модели, подпись, имя поля Access/БД в скобках шапки).
FUEL_RESTRICTION_LIST_COLUMN_HEADINGS: list[tuple[str, str, str]] = [
    ("year", "Год", "year"),
    ("restriction_name", "Наименование ограничения", "name"),
    ("oes", "ОЭС", "oes"),
    ("obl", "Региональная энергосистема", "obl"),
    ("emin", "Минимальная выработка", "emin"),
    ("emax", "Максимальная выработка", "emax"),
    ("ecur", "Текущая выработка", "ecur"),
    ("h", "ЧЧИУМ, ч", "H"),
    ("ecurdis", "Текущая выработка с учётом ограничения", "ecurdis"),
    ("hdis", "H с учётом ограничения", "Hdis"),
    ("etp", "Выработка Этц", "etp"),
    ("kobl", "Коэффициент по субъекту", "kobl"),
    ("kcur", "Текущий коэффициент", "kcur"),
]
