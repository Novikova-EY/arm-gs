"""remove station_equipment_groups

Revision ID: d1e2f3a4b5c6
Revises: 8656120d4c9b
Create Date: 2026-01-26 00:00:00.000000

Переносит данные в equipment_group_sets, удаляет station_equipment_groups
и заменяет FK в machines на equipment_group_set_id.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from config import SCHEMA_GENERATION, SCHEMA_REFDATA


# revision identifiers, used by Alembic.
revision = "d1e2f3a4b5c6"
down_revision = "8656120d4c9b"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    # 1) Расширяем equipment_group_sets
    op.add_column("equipment_group_sets", sa.Column("niv", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("comp", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("main", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("d", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("r", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("form", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("type", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("vedomstvo", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("obl", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("dep", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("oes", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("er", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("fo", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("numb", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("tm", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("n1", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("n2", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("p1", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("p2", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("ordnumb", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("addr", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("note", sa.String(length=1000), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("codegor", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("be", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("gk", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("gkf", sa.String(length=255), nullable=True), schema=SCHEMA_GENERATION)
    op.add_column("equipment_group_sets", sa.Column("external_code", sa.String(length=36), nullable=True), schema=SCHEMA_GENERATION)
    op.create_index(
        "ix_equipment_group_sets_external_code",
        "equipment_group_sets",
        ["external_code"],
        unique=False,
        schema=SCHEMA_GENERATION,
    )

    # 2) Добавляем equipment_group_set_id в machines
    op.add_column(
        "machines",
        sa.Column("equipment_group_set_id", sa.Integer(), nullable=True),
        schema=SCHEMA_GENERATION,
    )
    op.create_index(
        "ix_machine_equipment_group_set_id",
        "machines",
        ["equipment_group_set_id"],
        unique=False,
        schema=SCHEMA_GENERATION,
    )
    op.create_foreign_key(
        "fk_machines_equipment_group_set_id",
        "machines",
        "equipment_group_sets",
        ["equipment_group_set_id"],
        ["id"],
        source_schema=SCHEMA_GENERATION,
        referent_schema=SCHEMA_GENERATION,
        ondelete="RESTRICT",
    )

    # 3) Переносим данные из station_equipment_groups
    if inspector.has_table("station_equipment_groups", schema=SCHEMA_GENERATION):
        op.execute(
            f"""
            INSERT INTO {SCHEMA_GENERATION}.equipment_group_sets (
                id, id_equipment_group, name, database_version_id,
                niv, comp, main, d, r, form, type, vedomstvo, obl, dep, oes, er, fo, numb, tm,
                n1, n2, p1, p2, ordnumb, addr, note, codegor, be, gk, gkf, external_code
            )
            SELECT
                seg.id, seg.id_equipment_group, seg.name, seg.database_version_id,
                seg.niv, seg.comp, seg.main, seg.d, seg.r, seg.form, seg.type, seg.vedomstvo,
                seg.obl, seg.dep, seg.oes, seg.er, seg.fo, seg.numb, seg.tm,
                seg.n1, seg.n2, seg.p1, seg.p2, seg.ordnumb, seg.addr, seg.note, seg.codegor,
                seg.be, seg.gk, seg.gkf, seg.external_code
            FROM {SCHEMA_GENERATION}.station_equipment_groups seg
            WHERE NOT EXISTS (
                SELECT 1 FROM {SCHEMA_GENERATION}.equipment_group_sets egs WHERE egs.id = seg.id
            )
            """
        )

        op.execute(
            f"""
            INSERT INTO {SCHEMA_GENERATION}.equipment_group_set_stations (
                equipment_group_set_id, station_id, database_version_id
            )
            SELECT
                seg.id, seg.id_station, seg.database_version_id
            FROM {SCHEMA_GENERATION}.station_equipment_groups seg
            WHERE NOT EXISTS (
                SELECT 1
                FROM {SCHEMA_GENERATION}.equipment_group_set_stations link
                WHERE link.equipment_group_set_id = seg.id
                  AND link.station_id = seg.id_station
            )
            """
        )

        op.execute(
            f"""
            UPDATE {SCHEMA_GENERATION}.machines
            SET equipment_group_set_id = station_equipment_group_id
            WHERE station_equipment_group_id IS NOT NULL
            """
        )

        # Синхронизируем последовательность, если она есть
        op.execute(
            f"""
            SELECT setval(
                '{SCHEMA_GENERATION}.equipment_group_sets_id_seq',
                (SELECT COALESCE(MAX(id), 1) FROM {SCHEMA_GENERATION}.equipment_group_sets)
            )
            """
        )

        # 4) Удаляем старые FK/колонку/таблицу
        fks = inspector.get_foreign_keys("machines", schema=SCHEMA_GENERATION)
        fk_names = {fk.get("name") for fk in fks}
        if "fk_machines_station_equipment_group_id" in fk_names:
            op.drop_constraint(
                "fk_machines_station_equipment_group_id",
                "machines",
                schema=SCHEMA_GENERATION,
                type_="foreignkey",
            )

        if any(ix.get("name") == "ix_machine_station_equipment_group_id" for ix in inspector.get_indexes("machines", schema=SCHEMA_GENERATION)):
            op.drop_index(
                "ix_machine_station_equipment_group_id",
                table_name="machines",
                schema=SCHEMA_GENERATION,
            )

        op.drop_column("machines", "station_equipment_group_id", schema=SCHEMA_GENERATION)
        op.drop_table("station_equipment_groups", schema=SCHEMA_GENERATION)


def downgrade():
    conn = op.get_bind()
    inspector = inspect(conn)

    # Восстанавливаем station_equipment_groups
    if not inspector.has_table("station_equipment_groups", schema=SCHEMA_GENERATION):
        op.create_table(
            "station_equipment_groups",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("id_station", sa.Integer(), nullable=False),
            sa.Column("id_equipment_group", sa.Integer(), nullable=False),
            sa.Column("database_version_id", sa.Integer(), nullable=True),
            sa.Column("version", sa.Integer(), server_default="1", nullable=False),
            sa.Column("name", sa.String(length=255), nullable=True),
            sa.Column("niv", sa.String(length=255), nullable=True),
            sa.Column("comp", sa.String(length=255), nullable=True),
            sa.Column("main", sa.String(length=255), nullable=True),
            sa.Column("d", sa.String(length=255), nullable=True),
            sa.Column("r", sa.String(length=255), nullable=True),
            sa.Column("form", sa.String(length=255), nullable=True),
            sa.Column("type", sa.String(length=255), nullable=True),
            sa.Column("vedomstvo", sa.String(length=255), nullable=True),
            sa.Column("obl", sa.String(length=255), nullable=True),
            sa.Column("dep", sa.String(length=255), nullable=True),
            sa.Column("oes", sa.String(length=255), nullable=True),
            sa.Column("er", sa.String(length=255), nullable=True),
            sa.Column("fo", sa.String(length=255), nullable=True),
            sa.Column("numb", sa.String(length=255), nullable=True),
            sa.Column("tm", sa.String(length=255), nullable=True),
            sa.Column("n1", sa.String(length=255), nullable=True),
            sa.Column("n2", sa.String(length=255), nullable=True),
            sa.Column("p1", sa.String(length=255), nullable=True),
            sa.Column("p2", sa.String(length=255), nullable=True),
            sa.Column("ordnumb", sa.String(length=255), nullable=True),
            sa.Column("addr", sa.String(length=255), nullable=True),
            sa.Column("note", sa.String(length=1000), nullable=True),
            sa.Column("codegor", sa.String(length=255), nullable=True),
            sa.Column("be", sa.String(length=255), nullable=True),
            sa.Column("gk", sa.String(length=255), nullable=True),
            sa.Column("gkf", sa.String(length=255), nullable=True),
            sa.Column("external_code", sa.String(length=36), nullable=False),
            sa.ForeignKeyConstraint(
                ["id_station"],
                [f"{SCHEMA_GENERATION}.stations.id"],
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["id_equipment_group"],
                [f"{SCHEMA_REFDATA}.gs_equipment_groups.id"],
                ondelete="RESTRICT",
            ),
            sa.ForeignKeyConstraint(
                ["database_version_id"],
                [f"{SCHEMA_REFDATA}.gs_database_versions.id"],
                ondelete="SET NULL",
            ),
            sa.UniqueConstraint(
                "id_station",
                "id_equipment_group",
                name="uq_station_equipment_groups_station_equipment_group",
            ),
            schema=SCHEMA_GENERATION,
        )

        op.create_index(
            "ix_station_equipment_groups_id_station",
            "station_equipment_groups",
            ["id_station"],
            unique=False,
            schema=SCHEMA_GENERATION,
        )
        op.create_index(
            "ix_station_equipment_groups_id_equipment_group",
            "station_equipment_groups",
            ["id_equipment_group"],
            unique=False,
            schema=SCHEMA_GENERATION,
        )
        op.create_index(
            "ix_station_equipment_groups_database_version_id",
            "station_equipment_groups",
            ["database_version_id"],
            unique=False,
            schema=SCHEMA_GENERATION,
        )
        op.create_index(
            "ix_station_equipment_groups_external_code",
            "station_equipment_groups",
            ["external_code"],
            unique=False,
            schema=SCHEMA_GENERATION,
        )

    # Восстанавливаем колонку в machines
    if "station_equipment_group_id" not in [c["name"] for c in inspector.get_columns("machines", schema=SCHEMA_GENERATION)]:
        op.add_column(
            "machines",
            sa.Column("station_equipment_group_id", sa.Integer(), nullable=True),
            schema=SCHEMA_GENERATION,
        )
        op.create_index(
            "ix_machine_station_equipment_group_id",
            "machines",
            ["station_equipment_group_id"],
            unique=False,
            schema=SCHEMA_GENERATION,
        )
        op.create_foreign_key(
            "fk_machines_station_equipment_group_id",
            "machines",
            "station_equipment_groups",
            ["station_equipment_group_id"],
            ["id"],
            source_schema=SCHEMA_GENERATION,
            referent_schema=SCHEMA_GENERATION,
            ondelete="RESTRICT",
        )

    # Пробуем восстановить данные из equipment_group_sets
    if inspector.has_table("equipment_group_sets", schema=SCHEMA_GENERATION):
        op.execute(
            f"""
            INSERT INTO {SCHEMA_GENERATION}.station_equipment_groups (
                id_station, id_equipment_group, name, database_version_id,
                niv, comp, main, d, r, form, type, vedomstvo, obl, dep, oes, er, fo, numb, tm,
                n1, n2, p1, p2, ordnumb, addr, note, codegor, be, gk, gkf, external_code
            )
            SELECT
                link.station_id, egs.id_equipment_group, egs.name, egs.database_version_id,
                egs.niv, egs.comp, egs.main, egs.d, egs.r, egs.form, egs.type, egs.vedomstvo,
                egs.obl, egs.dep, egs.oes, egs.er, egs.fo, egs.numb, egs.tm,
                egs.n1, egs.n2, egs.p1, egs.p2, egs.ordnumb, egs.addr, egs.note, egs.codegor,
                egs.be, egs.gk, egs.gkf, COALESCE(egs.external_code, '')
            FROM {SCHEMA_GENERATION}.equipment_group_sets egs
            JOIN {SCHEMA_GENERATION}.equipment_group_set_stations link
              ON link.equipment_group_set_id = egs.id
            """
        )

        op.execute(
            f"""
            UPDATE {SCHEMA_GENERATION}.machines m
            SET station_equipment_group_id = seg.id
            FROM {SCHEMA_GENERATION}.station_equipment_groups seg
            WHERE seg.id_station = m.id_station
              AND seg.id_equipment_group = m.id_equipment_group
            """
        )

    # Удаляем новые поля и связи
    if any(ix.get("name") == "ix_machine_equipment_group_set_id" for ix in inspector.get_indexes("machines", schema=SCHEMA_GENERATION)):
        op.drop_index(
            "ix_machine_equipment_group_set_id",
            table_name="machines",
            schema=SCHEMA_GENERATION,
        )
    fks = inspector.get_foreign_keys("machines", schema=SCHEMA_GENERATION)
    fk_names = {fk.get("name") for fk in fks}
    if "fk_machines_equipment_group_set_id" in fk_names:
        op.drop_constraint(
            "fk_machines_equipment_group_set_id",
            "machines",
            schema=SCHEMA_GENERATION,
            type_="foreignkey",
        )
    if "equipment_group_set_id" in [c["name"] for c in inspector.get_columns("machines", schema=SCHEMA_GENERATION)]:
        op.drop_column("machines", "equipment_group_set_id", schema=SCHEMA_GENERATION)

    # Удаляем дополнительные колонки из equipment_group_sets
    for col_name in [
        "niv", "comp", "main", "d", "r", "form", "type", "vedomstvo", "obl", "dep", "oes", "er", "fo",
        "numb", "tm", "n1", "n2", "p1", "p2", "ordnumb", "addr", "note", "codegor", "be", "gk", "gkf",
        "external_code",
    ]:
        if col_name in [c["name"] for c in inspector.get_columns("equipment_group_sets", schema=SCHEMA_GENERATION)]:
            op.drop_column("equipment_group_sets", col_name, schema=SCHEMA_GENERATION)
