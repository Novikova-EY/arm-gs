"""fix station unique exclusion by name/uuid

Revision ID: 3d4e5f6a7b8c
Revises: 2c3d4e5f6a7b
Create Date: 2026-01-30 00:00:00.000000

"""
from alembic import op
import os


# revision identifiers, used by Alembic.
revision = "3d4e5f6a7b8c"
down_revision = "2c3d4e5f6a7b"
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
            v_ver_schema text;
            v_version_id int;
            v_id int;
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

            SELECT n.nspname INTO v_ver_schema
            FROM pg_class t
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE t.relname = 'gs_database_versions'
              AND n.nspname IN ('gs_sys', 'refdata')
            ORDER BY n.nspname
            LIMIT 1;

            IF v_ver_schema IS NULL THEN
                v_ver_schema := v_schema;
            END IF;

            EXECUTE format(
                'SELECT id FROM %I.gs_database_versions WHERE is_active IS TRUE ORDER BY id DESC LIMIT 1',
                v_ver_schema
            ) INTO v_version_id;

            IF v_uuid IS NOT NULL AND v_uuid <> '' THEN
                IF v_version_id IS NOT NULL THEN
                    EXECUTE format(
                        'SELECT id FROM %I.gs_regional_districts WHERE ref_uuid = %L AND database_version_id = %s ORDER BY id DESC LIMIT 1',
                        v_schema, v_uuid, v_version_id
                    ) INTO v_id;
                END IF;
                IF v_id IS NULL THEN
                    EXECUTE format(
                        'SELECT id FROM %I.gs_regional_districts WHERE ref_uuid = %L ORDER BY id DESC LIMIT 1',
                        v_schema, v_uuid
                    ) INTO v_id;
                END IF;
            ELSE
                IF v_version_id IS NOT NULL THEN
                    EXECUTE format(
                        'SELECT id FROM %I.gs_regional_districts WHERE (name = %L OR name_full = %L) AND database_version_id = %s ORDER BY id DESC LIMIT 1',
                        v_schema, v_name, v_name, v_version_id
                    ) INTO v_id;
                END IF;
                IF v_id IS NULL THEN
                    EXECUTE format(
                        'SELECT id FROM %I.gs_regional_districts WHERE name = %L OR name_full = %L ORDER BY id DESC LIMIT 1',
                        v_schema, v_name, v_name
                    ) INTO v_id;
                END IF;
            END IF;

            IF v_id IS NULL THEN
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

            EXECUTE format(
                'CREATE UNIQUE INDEX uq_station_name_district_version ON gs_gen.stations (name, id_regional_district, database_version_id) WHERE id_regional_district <> %s',
                v_id
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
