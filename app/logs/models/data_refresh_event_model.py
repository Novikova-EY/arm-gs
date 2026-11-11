"""Durable notification summaries, separate from the detailed audit log."""
from app.extensions import db
from config import SCHEMA_LOGS


class DataRefreshState(db.Model):
    __tablename__ = "gs_data_refresh_state"
    __table_args__ = {"schema": SCHEMA_LOGS}

    id = db.Column(db.Integer, primary_key=True)
    epoch = db.Column(db.String(36), nullable=False)
    revision = db.Column(db.BigInteger, nullable=False)


class DataRefreshEvent(db.Model):
    __tablename__ = "gs_data_refresh_events"
    __table_args__ = (
        db.Index("ix_refresh_event_version_revision", "database_version_id", "revision"),
        db.Index("ix_refresh_event_operation", "operation_id"),
        {"schema": SCHEMA_LOGS},
    )

    revision = db.Column(db.BigInteger, primary_key=True, autoincrement=False)
    operation_id = db.Column(db.String(36), nullable=False)
    recorded_at = db.Column(db.DateTime(timezone=True), nullable=False)
    username = db.Column(db.String(100), nullable=False)
    source = db.Column(db.String(40), nullable=False)
    kind = db.Column(db.String(40), nullable=False)
    database_version_id = db.Column(db.Integer, nullable=True)
    scope_known = db.Column(db.Boolean, nullable=False)
    consumption = db.Column(db.Boolean, nullable=False)
    demand = db.Column(db.Boolean, nullable=False)
    balance = db.Column(db.Boolean, nullable=False)
    summary = db.Column(db.JSON, nullable=False)
