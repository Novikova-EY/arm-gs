# -*- coding: utf-8 -*-
"""
ProspectivePlaceTypeGAES — тип перспективной площадки ГАЭС (справочник refdata).

Три канонических наименования (как у справочника ГЭС) — см. PROSPECTIVE_PLACE_TYPE_GAES_CANONICAL_NAMES.
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_GENERATION
from app.common.models.audit_mixin import AuditMixin

PROSPECTIVE_PLACE_TYPE_GAES_CANONICAL_NAMES = (
    "Перечень ГАЭС в соответствии с Генеральной схемой до 2042 года. Распоряжение Правительства от 30.12.2024 №4153-р",
    "Перечень дополнительных ГАЭС, необходимость и целесообразность реализация которых в настоящее время прорабатывается рабочей группой по вопросам подготовки плана-графика реализации механизмов привлечения инвестиций и определения механизмов и площадок реализации проектов сооружения ГАЭС на территории РФ",
    "Площадки размещения новых ГАЭС",
)


class ProspectivePlaceTypeGAES(db.Model, AuditMixin):
    """Справочник типов площадки ГАЭС (ровно три канонических наименования)."""

    __tablename__ = "gs_gen_prospective_place_types_gaes"
    __table_args__ = {"schema": SCHEMA_GENERATION}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, unique=True, nullable=False)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    gaes_tep_source_indicators = db.relationship(
        "ProspectivePlaceGaesTepSource",
        back_populates="prospective_place_type_gaes",
        primaryjoin="ProspectivePlaceTypeGAES.id == ProspectivePlaceGaesTepSource.id_prospective_place_type_gaes",
    )

    def __repr__(self) -> str:
        return f"<ProspectivePlaceTypeGAES id={self.id} name={self.name!r}>"
