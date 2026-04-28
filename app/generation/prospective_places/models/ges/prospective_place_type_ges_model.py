# -*- coding: utf-8 -*-
"""
ProspectivePlaceTypeGES — тип перспективной площадки ГЭС (справочник refdata).

Ровно три допустимых наименования — см. PROSPECTIVE_PLACE_TYPE_GES_CANONICAL_NAMES.
Отдельно от справочника типов АЭС (ProspectivePlaceTypeAES).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_GENERATION
from app.common.models.audit_mixin import AuditMixin

# Три фиксированных вида типа площадки ГЭС (полное наименование для поля name в БД)
PROSPECTIVE_PLACE_TYPE_GES_CANONICAL_NAMES = (
    "Перечень ГЭС в соответствии с Генеральной схемой до 2042 года. Распоряжение Правительства от 30.12.2024 №4153-р",
    "Перечень дополнительных ГЭС, необходимость и целесообразность реализация которых в настоящее время прорабатывается рабочей группой по вопросам подготовки плана-графика реализации механизмов привлечения инвестиций и строительства ГЭС на территории РФ",
    "Площадки размещения новых ГЭС",
)


class ProspectivePlaceTypeGES(db.Model, AuditMixin):
    """Справочник типов площадки ГЭС (ровно три канонических наименования)."""

    __tablename__ = "gs_gen_prospective_place_types_ges"
    __table_args__ = {"schema": SCHEMA_GENERATION}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, unique=True, nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    ges_tep_source_indicators = db.relationship(
        "ProspectivePlaceGesTepSource",
        back_populates="prospective_place_type_ges",
        primaryjoin="ProspectivePlaceTypeGES.id == ProspectivePlaceGesTepSource.id_prospective_place_type_ges",
    )

    def __repr__(self) -> str:
        return f"<ProspectivePlaceTypeGES id={self.id} name={self.name!r}>"
