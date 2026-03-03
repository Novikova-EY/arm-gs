"""gs_years: unique on (number, database_version_id) вместо (number)

Revision ID: a7b8c9d0e1f2
Revises: p2q3r4s5t6u7
Create Date: 2026-02-25 12:00:00.000000

Позволяет иметь одинаковый год (number) в разных версиях БД.
- Удаляет uq_gs_years_number (если есть)
- Создаёт uq_gs_years_number_version на (number, database_version_id)
"""

from alembic import op
from sqlalchemy import inspect, text
from config import SCHEMA_REFDATA, SCHEMA_GENERATION, SCHEMA_FUEL


revision = "a7b8c9d0e1f2"
down_revision = "510b27321036"
branch_labels = None
depends_on = None

YEARS_TABLE = "gs_years"
REFDATA_SCHEMA = SCHEMA_REFDATA
GEN_SCHEMA = SCHEMA_GENERATION
FUEL_SCHEMA = SCHEMA_FUEL

# Таблицы с FK year_number -> gs_years.number (сначала удаляем FK, потом создаём составные)
FK_TABLES = [
    (GEN_SCHEMA, "station_powers", "year_number"),
    (GEN_SCHEMA, "machine_powers", "year_number"),
    (GEN_SCHEMA, "machine_fuels", "year_number"),
    (GEN_SCHEMA, "machine_tes_types", "year_number"),
    (GEN_SCHEMA, "machine_names", "year_number"),
    (GEN_SCHEMA, "pgu_machine_powers", "year_number"),
    (FUEL_SCHEMA, "gs_fue_equipment_group_toplivo_param", "year_number"),
]


def _constraint_exists(conn, table, constraint_name, schema):
    """Проверяет наличие ограничения."""
    insp = inspect(conn)
    uqs = insp.get_unique_constraints(table, schema=schema)
    return any(uq.get("name") == constraint_name for uq in uqs)


def _get_fk_to_years(conn, table, schema, year_col):
    """Возвращает имя FK year_number -> gs_years.number."""
    insp = inspect(conn)
    fks = insp.get_foreign_keys(table, schema=schema)
    for fk in fks:
        ref_table = fk.get("referred_table", "")
        ref_schema = fk.get("referred_schema") or REFDATA_SCHEMA
        if (ref_table == YEARS_TABLE and
                fk.get("constrained_columns") == [year_col] and
                fk.get("referred_columns") == ["number"]):
            return fk.get("name")
    return None


def upgrade():
    conn = op.get_bind()

    # 1) Сначала удаляем все FK, ссылающиеся на gs_years.number (без этого нельзя снять uq_gs_years_number)
    for schema, table, col in FK_TABLES:
        fk_name = _get_fk_to_years(conn, table, schema, col)
        if fk_name:
            op.drop_constraint(fk_name, table, schema=schema, type_="foreignkey")

    # 2) Удаляем старый UNIQUE на (number)
    if _constraint_exists(conn, YEARS_TABLE, "uq_gs_years_number", REFDATA_SCHEMA):
        op.drop_constraint(
            "uq_gs_years_number",
            YEARS_TABLE,
            schema=REFDATA_SCHEMA,
            type_="unique",
        )

    # 3) Создаём новый UNIQUE на (number, database_version_id)
    op.create_unique_constraint(
        "uq_gs_years_number_version",
        YEARS_TABLE,
        ["number", "database_version_id"],
        schema=REFDATA_SCHEMA,
    )

    # 4) Заполняем недостающие годы: добавляем (number, database_version_id) для версий,
    #    у которых есть данные в generation/fuel, но нет строк в gs_years.
    #    Включаем только пары, где database_version_id существует в gs_database_versions
    #    (отбрасываем orphaned rows, оставшиеся после удаления версий БД).
    backfill_sql = text(f"""
        INSERT INTO {REFDATA_SCHEMA}.{YEARS_TABLE} (number, database_version_id, id_year_feature)
        SELECT DISTINCT num, vid, (
            SELECT y.id_year_feature FROM {REFDATA_SCHEMA}.{YEARS_TABLE} y
            WHERE y.number = num ORDER BY y.id_year_feature LIMIT 1
        )
        FROM (
            SELECT year_number AS num, database_version_id AS vid FROM {GEN_SCHEMA}.station_powers
            WHERE year_number IS NOT NULL AND database_version_id IS NOT NULL
            UNION
            SELECT year_number, database_version_id FROM {GEN_SCHEMA}.machine_powers
            WHERE year_number IS NOT NULL AND database_version_id IS NOT NULL
            UNION
            SELECT year_number, database_version_id FROM {GEN_SCHEMA}.machine_fuels
            WHERE year_number IS NOT NULL AND database_version_id IS NOT NULL
            UNION
            SELECT year_number, database_version_id FROM {GEN_SCHEMA}.machine_tes_types
            WHERE year_number IS NOT NULL AND database_version_id IS NOT NULL
            UNION
            SELECT year_number, database_version_id FROM {GEN_SCHEMA}.machine_names
            WHERE year_number IS NOT NULL AND database_version_id IS NOT NULL
            UNION
            SELECT year_number, database_version_id FROM {GEN_SCHEMA}.pgu_machine_powers
            WHERE year_number IS NOT NULL AND database_version_id IS NOT NULL
            UNION
            SELECT year_number, database_version_id FROM {FUEL_SCHEMA}.gs_fue_equipment_group_toplivo_param
            WHERE year_number IS NOT NULL AND database_version_id IS NOT NULL
        ) pairs
        WHERE pairs.vid IN (SELECT id FROM {REFDATA_SCHEMA}.gs_database_versions)
        AND NOT EXISTS (
            SELECT 1 FROM {REFDATA_SCHEMA}.{YEARS_TABLE} y2
            WHERE y2.number = pairs.num AND y2.database_version_id = pairs.vid
        )
    """)
    conn.execute(backfill_sql)

    # 5) Очищаем orphaned строки: database_version_id отсутствует в gs_database_versions.
    #    Иначе создание составного FK в шаге 6 завершится с ошибкой.
    for schema, table, col in FK_TABLES:
        cleanup_sql = text(f"""
            UPDATE {schema}.{table}
            SET database_version_id = NULL
            WHERE database_version_id IS NOT NULL
            AND database_version_id NOT IN (SELECT id FROM {REFDATA_SCHEMA}.gs_database_versions)
        """)
        conn.execute(cleanup_sql)

    # 6) Создаём составные FK: (year_number, database_version_id) -> (number, database_version_id)
    for schema, table, col in FK_TABLES:
        op.create_foreign_key(
            f"fk_{table}_{col}_years",
            table,
            YEARS_TABLE,
            [col, "database_version_id"],
            ["number", "database_version_id"],
            source_schema=schema,
            referent_schema=REFDATA_SCHEMA,
            ondelete="RESTRICT",
        )


def downgrade():
    conn = op.get_bind()

    # 1) Удаляем составные FK
    for schema, table, col in FK_TABLES:
        op.drop_constraint(
            f"fk_{table}_{col}_years",
            table,
            schema=schema,
            type_="foreignkey",
        )

    # 2) Восстанавливаем простые FK year_number -> number
    for schema, table, col in FK_TABLES:
        op.create_foreign_key(
            None,
            table,
            YEARS_TABLE,
            [col],
            ["number"],
            source_schema=schema,
            referent_schema=REFDATA_SCHEMA,
            ondelete="RESTRICT",
        )

    # 3) Удаляем составной UNIQUE
    op.drop_constraint(
        "uq_gs_years_number_version",
        YEARS_TABLE,
        schema=REFDATA_SCHEMA,
        type_="unique",
    )

    # 4) Восстанавливаем UNIQUE на (number)
    op.create_unique_constraint(
        "uq_gs_years_number",
        YEARS_TABLE,
        ["number"],
        schema=REFDATA_SCHEMA,
    )
