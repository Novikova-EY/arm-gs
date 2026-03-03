"""fix station unique exclusion from env list

Revision ID: 5f6a7b8c9d0e
Revises: 4e5f6a7b8c9d
Create Date: 2026-01-30 00:00:00.000000

"""
from alembic import op
from sqlalchemy import text
import os


# revision identifiers, used by Alembic.
revision = "5f6a7b8c9d0e"
down_revision = "4e5f6a7b8c9d"
branch_labels = None
depends_on = None


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade():
    raw_ids = os.getenv("STATION_UNIQUE_EXCLUDED_DISTRICT_IDS", "")
    raw_uuids = os.getenv("STATION_UNIQUE_EXCLUDED_DISTRICT_UUIDS", "")

    ids_from_env = []
    for p in raw_ids.split(","):
        p = p.strip()
        if p:
            try:
                ids_from_env.append(int(p))
            except ValueError:
                pass

    uuids = [u.strip() for u in raw_uuids.split(",") if u.strip()]

    if not ids_from_env and not uuids:
        raise RuntimeError(
            "No excluded districts provided via env (STATION_UNIQUE_EXCLUDED_DISTRICT_IDS or STATION_UNIQUE_EXCLUDED_DISTRICT_UUIDS)."
        )

    all_ids = set(ids_from_env)
    if uuids:
        conn = op.get_bind()
        schema_result = conn.execute(
            text(
                "SELECT n.nspname FROM pg_class t JOIN pg_namespace n ON n.oid = t.relnamespace "
                "WHERE t.relname = 'gs_regional_districts' AND n.nspname IN ('gs_sys', 'refdata') "
                "ORDER BY n.nspname LIMIT 1"
            )
        ).fetchone()
        if schema_result:
            schema = schema_result[0]
            uuids_sql = ", ".join(_sql_literal(u) for u in uuids)
            lookup_sql = f"SELECT id FROM {schema}.gs_regional_districts WHERE ref_uuid = ANY(ARRAY[{uuids_sql}]::text[])"
            rows = conn.execute(text(lookup_sql)).fetchall()
            all_ids.update(r[0] for r in rows)

    if not all_ids:
        raise RuntimeError(
            "Regional districts not found for exclusion "
            "(check STATION_UNIQUE_EXCLUDED_DISTRICT_IDS and STATION_UNIQUE_EXCLUDED_DISTRICT_UUIDS)."
        )

    v_ids_sql = ",".join(str(i) for i in all_ids)

    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE c.conname = 'uq_station_name_district_version'
                  AND n.nspname = 'gs_gen'
                  AND t.relname = 'stations'
            ) THEN
                ALTER TABLE gs_gen.stations DROP CONSTRAINT uq_station_name_district_version;
            END IF;

            IF EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE c.conname = 'uq_station_name_district'
                  AND n.nspname = 'gs_gen'
                  AND t.relname = 'stations'
            ) THEN
                ALTER TABLE gs_gen.stations DROP CONSTRAINT uq_station_name_district;
            END IF;

            IF EXISTS (
                SELECT 1
                FROM pg_class t
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE t.relname = 'uq_station_name_district_version'
                  AND n.nspname = 'gs_gen'
            ) THEN
                DROP INDEX gs_gen.uq_station_name_district_version;
            END IF;

            EXECUTE 'CREATE UNIQUE INDEX uq_station_name_district_version ON gs_gen.stations (name, id_regional_district, database_version_id) WHERE id_regional_district NOT IN (' || '{v_ids_sql}' || ')';
        END $$;
        """
    )


def downgrade():
    op.drop_index(
        "uq_station_name_district_version",
        table_name="stations",
        schema="gs_gen",
    )
    op.create_unique_constraint(
        "uq_station_name_district_version",
        "stations",
        ["name", "id_regional_district", "database_version_id"],
        schema="gs_gen",
    )
