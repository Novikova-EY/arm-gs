"""EquipmentGroup: drop id_regional_district, id_regional_energy_system; use regional_district_id, regional_energy_system_id

Revision ID: a9b8c7d6e5f4
Revises: 7fc50e8085d8
Create Date: 2026-03-11

Удаляет id_regional_district и id_regional_energy_system из EquipmentGroup.
Добавляет regional_district_id и regional_energy_system_id.
Если старые колонки есть — копирует данные и удаляет их.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from config import SCHEMA_FUEL, SCHEMA_REFDATA


revision = "a9b8c7d6e5f4"
down_revision = "7fc50e8085d8"
branch_labels = None
depends_on = None

TABLE = "gs_fue_equipment_groups"
RD_TABLE = "gs_regional_districts"
RES_TABLE = "gs_regional_energy_systems"


def _column_exists(conn, schema, table, column):
    r = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = :schema AND table_name = :table AND column_name = :col
            """
        ),
        {"schema": schema, "table": table, "col": column},
    ).scalar()
    return r is not None


def upgrade():
    conn = op.get_bind()
    has_old_rd = _column_exists(conn, SCHEMA_FUEL, TABLE, "id_regional_district")
    has_old_res = _column_exists(conn, SCHEMA_FUEL, TABLE, "id_regional_energy_system")
    has_new_rd = _column_exists(conn, SCHEMA_FUEL, TABLE, "regional_district_id")
    has_new_res = _column_exists(conn, SCHEMA_FUEL, TABLE, "regional_energy_system_id")

    # 1. Добавляем новые колонки, если их ещё нет
    if not has_new_rd:
        op.add_column(
            TABLE,
            sa.Column("regional_district_id", sa.Integer(), nullable=True),
            schema=SCHEMA_FUEL,
        )
    if not has_new_res:
        op.add_column(
            TABLE,
            sa.Column("regional_energy_system_id", sa.Integer(), nullable=True),
            schema=SCHEMA_FUEL,
        )

    # 2. Копируем данные из старых колонок (если они есть)
    if has_old_rd and has_old_res:
        conn.execute(
            text(
                f"""
                UPDATE {SCHEMA_FUEL}.{TABLE}
                SET regional_district_id = id_regional_district,
                    regional_energy_system_id = id_regional_energy_system
                """
            )
        )
    elif has_old_rd:
        conn.execute(
            text(
                f"""
                UPDATE {SCHEMA_FUEL}.{TABLE}
                SET regional_district_id = id_regional_district
                """
            )
        )
    elif has_old_res:
        conn.execute(
            text(
                f"""
                UPDATE {SCHEMA_FUEL}.{TABLE}
                SET regional_energy_system_id = id_regional_energy_system
                """
            )
        )

    # 3. Удаляем старые колонки (если есть)
    if has_old_rd or has_old_res:
        for cname in ("fk_equipment_group_regional_energy_system", "fk_equipment_group_regional_district"):
            try:
                op.drop_constraint(cname, TABLE, schema=SCHEMA_FUEL, type_="foreignkey")
            except Exception:
                pass
        for iname in ("ix_gs_fue_equipment_groups_id_regional_energy_system", "ix_gs_fue_equipment_groups_id_regional_district"):
            try:
                op.drop_index(iname, table_name=TABLE, schema=SCHEMA_FUEL)
            except Exception:
                pass
        if has_old_res:
            op.drop_column(TABLE, "id_regional_energy_system", schema=SCHEMA_FUEL)
        if has_old_rd:
            op.drop_column(TABLE, "id_regional_district", schema=SCHEMA_FUEL)

    # 4. Создаём FK и индексы для новых колонок (если ещё нет)
    for fk_name, col, ref_table in [
        ("fk_equipment_group_regional_district", "regional_district_id", RD_TABLE),
        ("fk_equipment_group_regional_energy_system", "regional_energy_system_id", RES_TABLE),
    ]:
        try:
            op.create_foreign_key(
                fk_name,
                TABLE,
                ref_table,
                [col],
                ["id"],
                source_schema=SCHEMA_FUEL,
                referent_schema=SCHEMA_REFDATA,
                ondelete="SET NULL",
            )
        except Exception:
            pass
    for idx_name, col in [
        ("ix_gs_fue_equipment_groups_regional_district_id", "regional_district_id"),
        ("ix_gs_fue_equipment_groups_regional_energy_system_id", "regional_energy_system_id"),
    ]:
        try:
            op.create_index(idx_name, TABLE, [col], unique=False, schema=SCHEMA_FUEL)
        except Exception:
            pass


def downgrade():
    conn = op.get_bind()
    has_old_rd = _column_exists(conn, SCHEMA_FUEL, TABLE, "id_regional_district")
    has_old_res = _column_exists(conn, SCHEMA_FUEL, TABLE, "id_regional_energy_system")

    # 1. Добавляем старые колонки, если их нет
    if not has_old_rd:
        op.add_column(
            TABLE,
            sa.Column("id_regional_district", sa.Integer(), nullable=True),
            schema=SCHEMA_FUEL,
        )
    if not has_old_res:
        op.add_column(
            TABLE,
            sa.Column("id_regional_energy_system", sa.Integer(), nullable=True),
            schema=SCHEMA_FUEL,
        )

    # 2. Копируем данные
    conn.execute(
        text(
            f"""
            UPDATE {SCHEMA_FUEL}.{TABLE}
            SET id_regional_district = regional_district_id,
                id_regional_energy_system = regional_energy_system_id
            """
        )
    )

    # 3. Удаляем FK и индексы новых колонок
    op.drop_index(
        "ix_gs_fue_equipment_groups_regional_energy_system_id",
        table_name=TABLE,
        schema=SCHEMA_FUEL,
    )
    op.drop_index(
        "ix_gs_fue_equipment_groups_regional_district_id",
        table_name=TABLE,
        schema=SCHEMA_FUEL,
    )
    op.drop_constraint(
        "fk_equipment_group_regional_energy_system",
        TABLE,
        schema=SCHEMA_FUEL,
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_equipment_group_regional_district",
        TABLE,
        schema=SCHEMA_FUEL,
        type_="foreignkey",
    )

    # 4. Удаляем новые колонки
    op.drop_column(TABLE, "regional_energy_system_id", schema=SCHEMA_FUEL)
    op.drop_column(TABLE, "regional_district_id", schema=SCHEMA_FUEL)

    # 5. Восстанавливаем FK и индексы старых колонок
    op.create_foreign_key(
        "fk_equipment_group_regional_district",
        TABLE,
        RD_TABLE,
        ["id_regional_district"],
        ["id"],
        source_schema=SCHEMA_FUEL,
        referent_schema=SCHEMA_REFDATA,
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_equipment_group_regional_energy_system",
        TABLE,
        RES_TABLE,
        ["id_regional_energy_system"],
        ["id"],
        source_schema=SCHEMA_FUEL,
        referent_schema=SCHEMA_REFDATA,
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_gs_fue_equipment_groups_id_regional_district",
        TABLE,
        ["id_regional_district"],
        unique=False,
        schema=SCHEMA_FUEL,
    )
    op.create_index(
        "ix_gs_fue_equipment_groups_id_regional_energy_system",
        TABLE,
        ["id_regional_energy_system"],
        unique=False,
        schema=SCHEMA_FUEL,
    )
