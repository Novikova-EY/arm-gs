"""Schema baseline captured from gs_gen on 2026-10-29.

The revision ID deliberately matches the last pre-squash head. Databases already
at that head must not execute this snapshot or repeat historical data changes.
"""
from pathlib import Path

from alembic import op
import sqlalchemy as sa

revision = "gs26102702"
down_revision = None
branch_labels = None
depends_on = None

SCHEMAS = (
    "gs_auth", "gs_bem", "gs_ec", "gs_eco", "gs_ei", "gs_ekp", "gs_fue",
    "gs_fue_em", "gs_gen", "gs_logs", "gs_pd", "gs_rs", "gs_sys", "gs_ter",
)


def upgrade():
    if not op.get_context().as_sql:
        existing = op.get_bind().execute(sa.text("""
            SELECT n.nspname, c.relname
            FROM pg_catalog.pg_class c
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = ANY(:schemas)
              AND c.relkind IN ('r', 'p', 'v', 'm', 'f', 'S')
              AND NOT (n.nspname = 'gs_auth' AND c.relname = 'alembic_version')
            LIMIT 1
        """), {"schemas": list(SCHEMAS)}).first()
        if existing:
            raise RuntimeError(
                "Baseline requires an empty application schema. "
                "For an existing database, restore the previous migration files "
                "and upgrade to gs26102702 before deploying the squashed history. "
                "Do not use stamp to bypass missing migrations."
            )

    snapshot = Path(__file__).resolve().parents[1] / "baseline" / "gs26102702.sql"
    # Escape TextClause bind markers, not PostgreSQL casts or colons in comments.
    statement = sa.text(snapshot.read_text(encoding="utf-8").replace(":", r"\:"))
    op.execute(statement)


def downgrade():
    # There is no meaningful pre-baseline schema to restore without losing data.
    raise RuntimeError(
        "Downgrade below gs26102702 is disabled. Restore a verified database "
        "backup together with the matching application release instead."
    )
