"""fix station unique exclusion from env list

Revision ID: 5f6a7b8c9d0e
Revises: 4e5f6a7b8c9d
Create Date: 2026-01-30 00:00:00.000000

"""
from alembic import op
import os


# revision identifiers, used by Alembic.
revision = "5f6a7b8c9d0e"
down_revision = "4e5f6a7b8c9d"
branch_labels = None
depends_on = None


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade():
    raw_names = os.getenv("STATION_UNIQUE_EXCLUDED_DISTRICT_NAMES", "Амурская область")
    raw_uuids = os.getenv("STATION_UNIQUE_EXCLUDED_DISTRICT_UUIDS", "")

    names = [n.strip() for n in raw_names.split(",") if n.strip()]
    uuids = [u.strip() for u in raw_uuids.split(",") if u.strip()]

    if not names and not uuids:
        raise RuntimeError("No excluded districts provided via env.")

    names_array_sql = "ARRAY[" + ", ".join(_sql_literal(n) for n in names) + "]" if names else "ARRAY[]::text[]"
    uuids_array_sql = "ARRAY[" + ", ".join(_sql_literal(u) for u in uuids) + "]" if uuids else None

    query_sql = (
        f"SELECT array_agg(id) FROM %I.gs_regional_districts "
        f"WHERE (name = ANY({names_array_sql}) OR name_full = ANY({names_array_sql}))"
    )
    if uuids_array_sql:
        query_sql += f" OR ref_uuid = ANY({uuids_array_sql})"
    query_sql_literal = _sql_literal(query_sql)

    op.execute(
        f"""
        DO $$
        DECLARE
            v_schema text;
            v_ids int[];
            v_ids_sql text;
        BEGIN
            SELECT n.nspname INTO v_schema
            FROM pg_class t
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE t.relname = 'gs_regional_districts'
              AND n.nspname IN ('gs_sys', 'refdata')
            ORDER BY n.nspname
            LIMIT 1;

            IF v_schema IS NULL THEN
                RAISE EXCEPTION 'gs_regional_districts not found in gs_sys/refdata';
            END IF;

            EXECUTE format(
                {query_sql_literal},
                v_schema
            ) INTO v_ids;

            IF v_ids IS NULL OR array_length(v_ids, 1) IS NULL THEN
                RAISE EXCEPTION 'Regional districts not found for exclusion';
            END IF;

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

            v_ids_sql := array_to_string(v_ids, ',');
            EXECUTE format(
                'CREATE UNIQUE INDEX uq_station_name_district_version ON gs_gen.stations (name, id_regional_district, database_version_id) WHERE id_regional_district NOT IN (%s)',
                v_ids_sql
            );
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
