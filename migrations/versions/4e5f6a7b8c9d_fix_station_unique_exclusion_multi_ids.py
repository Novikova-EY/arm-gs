"""fix station unique exclusion across versions

Revision ID: 4e5f6a7b8c9d
Revises: 3d4e5f6a7b8c
Create Date: 2026-01-30 00:00:00.000000

"""
from alembic import op
import os


# revision identifiers, used by Alembic.
revision = "4e5f6a7b8c9d"
down_revision = "3d4e5f6a7b8c"
branch_labels = None
depends_on = None


def upgrade():
    district_name = os.getenv("STATION_UNIQUE_EXCLUDED_DISTRICT_NAME", "Амурская область").strip()
    district_uuid = os.getenv("STATION_UNIQUE_EXCLUDED_DISTRICT_UUID", "").strip()

    def _sql_literal(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"

    name_literal = _sql_literal(district_name) if district_name else "NULL"
    uuid_literal = _sql_literal(district_uuid) if district_uuid else "NULL"

    op.execute(
        f"""
        DO $$
        DECLARE
            v_schema text;
            v_ids int[];
            v_ids_sql text;
            v_name text := {name_literal};
            v_uuid text := {uuid_literal};
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

            IF v_uuid IS NOT NULL AND v_uuid <> '' THEN
                EXECUTE format(
                    'SELECT array_agg(id) FROM %I.gs_regional_districts WHERE ref_uuid = %L',
                    v_schema, v_uuid
                ) INTO v_ids;
            ELSE
                EXECUTE format(
                    'SELECT array_agg(id) FROM %I.gs_regional_districts WHERE name = %L OR name_full = %L',
                    v_schema, v_name, v_name
                ) INTO v_ids;
            END IF;

            IF v_ids IS NULL OR array_length(v_ids, 1) IS NULL THEN
                RAISE EXCEPTION 'Regional district not found for exclusion (name=%, uuid=%)', v_name, v_uuid;
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
    # Возврат к обычной уникальности без исключения
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
