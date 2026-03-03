"""rename gs_fue_machine_toplivo_param to gs_fue_machine_fuel_param

Revision ID: h7i8j9k0l1m2
Revises: g6h7i8j9k0l1
Create Date: 2026-02-27

Переименовывает таблицу gs_fue_machine_toplivo_param в gs_fue_machine_fuel_param
и колонки topl_agr_* в короткие имена (numb, stnumb, grcode, ...).
Идемпотентно: выполняется только если gs_fue_machine_toplivo_param существует.
"""

from alembic import op
from sqlalchemy import inspect
from config import SCHEMA_FUEL


revision = "h7i8j9k0l1m2"
down_revision = "g6h7i8j9k0l1"
branch_labels = None
depends_on = None

OLD_TABLE = "gs_fue_machine_toplivo_param"
NEW_TABLE = "gs_fue_machine_fuel_param"
SCHEMA = SCHEMA_FUEL

# (old_name, new_name) — порядок важен: альтернативы после основных
COLUMN_RENAMES = [
    ("topl_agr_numb", "numb"),
    ("topl_agr_stnumb", "stnumb"),
    ("topl_agr_number", "stnumb"),  # альт. имя из l2m3n4o5p6q7
    ("topl_agr_station_number", "stnumb"),
    ("topl_agr_yearin", "yearin"),
    ("topl_agr_dem", "dem"),
    ("topl_agr_nt", "nt"),
    ("topl_agr_numb1120", "numb1120"),
    ("topl_agr_grcode", "grcode"),
    ("topl_agr_stname", "stname"),
    ("topl_agr_station_name", "stname"),  # альт. имя
    ("topl_agr_opesname", "opesname"),
    ("topl_agr_note", "note"),
]


def _table_exists(conn, table):
    inspector = inspect(conn)
    return inspector.has_table(table, schema=SCHEMA)


def _column_exists(conn, table, col):
    inspector = inspect(conn)
    cols = [c["name"] for c in inspector.get_columns(table, schema=SCHEMA)]
    return col in cols


def _rename_column_if_exists(conn, table, old_name, new_name):
    if _column_exists(conn, table, old_name) and not _column_exists(conn, table, new_name):
        op.alter_column(
            table,
            old_name,
            new_column_name=new_name,
            schema=SCHEMA,
        )


def upgrade():
    conn = op.get_bind()
    if not _table_exists(conn, OLD_TABLE):
        return
    if _table_exists(conn, NEW_TABLE):
        return

    # 1. Удалить FK и индекс на topl_agr_grcode (IF EXISTS — без исключения, транзакция не рвётся)
    op.execute(
        f"ALTER TABLE {SCHEMA}.{OLD_TABLE} DROP CONSTRAINT IF EXISTS fk_machine_toplivo_param_topl_agr_grcode"
    )
    op.execute(
        f"DROP INDEX IF EXISTS {SCHEMA}.ix_gs_fue_machine_toplivo_param_topl_agr_grcode"
    )

    # 2. Переименовать колонки (только существующие, без дубликатов)
    done_new = set()
    for old_name, new_name in COLUMN_RENAMES:
        if new_name in done_new:
            continue
        if _column_exists(conn, OLD_TABLE, old_name):
            op.alter_column(
                OLD_TABLE,
                old_name,
                new_column_name=new_name,
                schema=SCHEMA,
            )
            done_new.add(new_name)

    # 3. Переименовать unique constraint (EXCEPTION внутри PL/pgSQL — транзакция не рвётся)
    op.execute(
        f"""
        DO $$
        BEGIN
          ALTER TABLE {SCHEMA}.{OLD_TABLE}
          RENAME CONSTRAINT uq_machine_toplivo_param_machine_id TO uq_machine_fuel_param_machine_id;
        EXCEPTION WHEN undefined_object THEN
          NULL;
        END $$;
        """
    )

    # 4. Переименовать таблицу
    op.rename_table(OLD_TABLE, NEW_TABLE, schema=SCHEMA)

    # 5. Переименовать индексы (EXCEPTION в PL/pgSQL — транзакция не рвётся)
    for old_ix, new_ix in [
        ("ix_gs_fue_machine_toplivo_param_database_version_id", "ix_gs_fue_machine_fuel_param_database_version_id"),
        ("ix_gs_fue_machine_toplivo_param_machine_id", "ix_gs_fue_machine_fuel_param_machine_id"),
    ]:
        op.execute(
            f"""
            DO $$
            BEGIN
              ALTER INDEX IF EXISTS {SCHEMA}.{old_ix} RENAME TO {new_ix};
            EXCEPTION WHEN OTHERS THEN
              NULL;
            END $$;
            """
        )

    # 6. Создать индекс на grcode (без FK — связь в модели)
    if _column_exists(conn, NEW_TABLE, "grcode"):
        op.create_index(
            "ix_gs_fue_machine_fuel_param_grcode",
            NEW_TABLE,
            ["grcode"],
            unique=False,
            schema=SCHEMA,
        )


def downgrade():
    conn = op.get_bind()
    if not _table_exists(conn, NEW_TABLE):
        return

    op.execute(
        f"DROP INDEX IF EXISTS {SCHEMA}.ix_gs_fue_machine_fuel_param_grcode"
    )

    op.execute(
        f"ALTER INDEX IF EXISTS {SCHEMA}.ix_gs_fue_machine_fuel_param_machine_id "
        f"RENAME TO ix_gs_fue_machine_toplivo_param_machine_id"
    )
    op.execute(
        f"ALTER INDEX IF EXISTS {SCHEMA}.ix_gs_fue_machine_fuel_param_database_version_id "
        f"RENAME TO ix_gs_fue_machine_toplivo_param_database_version_id"
    )
    op.rename_table(NEW_TABLE, OLD_TABLE, schema=SCHEMA)
    op.execute(
        f"""
        DO $$
        BEGIN
          ALTER TABLE {SCHEMA}.{OLD_TABLE}
          RENAME CONSTRAINT uq_machine_fuel_param_machine_id TO uq_machine_toplivo_param_machine_id;
        EXCEPTION WHEN undefined_object THEN
          NULL;
        END $$;
        """
    )

    done_old = set()
    REVERSE = [(new, old) for old, new in COLUMN_RENAMES]
    for new_name, old_name in REVERSE:
        if old_name in done_old:
            continue
        if _column_exists(conn, OLD_TABLE, new_name):
            op.alter_column(
                OLD_TABLE,
                new_name,
                new_column_name=old_name,
                schema=SCHEMA,
            )
            done_old.add(old_name)
