# -*- coding: utf-8 -*-
"""
ForeignBorderCountry model (Зарубежная страна, имеющая общие границы с РФ).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin
from app.refdata.models.refdata_uuid_mixin import RefdataUuidMixin


class ForeignBorderCountry(db.Model, AuditMixin, VersionedModelMixin, RefdataUuidMixin):
    __tablename__ = 'gs_sys_foreign_border_countries'
    __table_args__ = (
        db.UniqueConstraint(
            'database_version_id',
            'name',
            name='uq_gs_sys_foreign_border_countries_ver_name',
        ),
        {"schema": SCHEMA_REFDATA},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Порядок отображения
    display_order = db.Column(db.Integer, nullable=True)

    # Наименование
    name = db.Column(db.String(255), nullable=False, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<ForeignBorderCountry id={self.id} name={self.name!r}>"
