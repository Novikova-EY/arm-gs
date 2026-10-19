# -*- coding: utf-8 -*-
"""Параметры анализа ЗВ (копия/правка отчетных данных ГИС ТЭК).

Revision ID: z8v9p0c1a2l3
Revises: ee2610120306
Create Date: 2026-10-19
"""
import os
import sys

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "z8v9p0c1a2l3"
down_revision = "ee2610120306"
branch_labels = None
depends_on = None

SCHEMA_ECO = "gs_eco"
SCHEMA_REFDATA = "gs_sys"
TABLE = "gs_eco_analysis_zv_params"

_COLUMN_COMMENTS = {
    "id": "Уникальный идентификатор записи",
    "sheet_slug": "Страница анализа: zv-vse или zv-bez-kot",
    "station_numb": "Код группы оборудования (numb1120), связь с отчетными ЗВ",
    "year_number": "Год (связь с gs_sys.gs_sys_years по number и database_version_id)",
    "solid_substances": "Твердые вещества, т (TVERD_V ← Твердые вещества)",
    "sulfur_dioxide": "Диоксид серы, т (SO2_gaz ← диоксид серы)",
    "carbon_monoxide": "Оксид углерода [CO], т (CO_gaz ← оксид углерода)",
    "nitrogen_oxides": "Оксиды азота [в пересчете на NO2], т (NOx_gaz ← оксиды азота)",
    "hydrocarbons": (
        "Углеводороды [без летучих органических соединений], т (UGLEVOD ← углеводороды)"
    ),
    "voc": "Летучие органические соединения [ЛОС], т (LOS ← ЛОС)",
    "other_gaseous_and_liquid": (
        "В т.ч. прочие газообразные и жидкие, т (PROCH_ekol ← прочие)"
    ),
    "note": "Примечание",
    "created_by": "Пользователь, создавший запись",
    "modified_by": "Пользователь, последним изменивший запись",
    "created_at": "Дата и время создания записи",
    "updated_at": "Дата и время последнего изменения записи",
    "database_version_id": "Версия базы данных (FK -> gs_sys.gs_database_versions)",
}


def _schema_exists(connection, schema: str) -> bool:
    r = connection.execute(
        text("SELECT 1 FROM information_schema.schemata WHERE schema_name = :schema"),
        {"schema": schema},
    )
    return r.fetchone() is not None


def _comment_on_table(conn, schema: str, table: str, comment: str) -> None:
    conn.execute(
        text(f'COMMENT ON TABLE "{schema}"."{table}" IS :comment'),
        {"comment": comment},
    )


def _comment_on_column(conn, schema: str, table: str, column: str, comment: str) -> None:
    conn.execute(
        text(f'COMMENT ON COLUMN "{schema}"."{table}"."{column}" IS :comment'),
        {"comment": comment},
    )


def upgrade():
    conn = op.get_bind()
    ref_db_versions = column_utils.database_versions_physical_table_name(conn, SCHEMA_REFDATA)
    if ref_db_versions is None:
        raise RuntimeError(f"Не найдена таблица версий БД в {SCHEMA_REFDATA}")
    years = column_utils.refdata_table_name(conn, SCHEMA_REFDATA, "gs_years")
    if years is None:
        raise RuntimeError(f"Не найдена таблица годов в {SCHEMA_REFDATA}")
    if not _schema_exists(conn, SCHEMA_ECO):
        op.execute(sa.text(f'CREATE SCHEMA "{SCHEMA_ECO}"'))

    if column_utils.table_exists(conn, SCHEMA_ECO, TABLE):
        return

    numeric = sa.Numeric(36, 16)
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("sheet_slug", sa.String(length=40), nullable=False),
        sa.Column("station_numb", sa.Integer(), nullable=False),
        sa.Column("year_number", sa.Integer(), nullable=False),
        sa.Column("solid_substances", numeric, nullable=True),
        sa.Column("sulfur_dioxide", numeric, nullable=True),
        sa.Column("carbon_monoxide", numeric, nullable=True),
        sa.Column("nitrogen_oxides", numeric, nullable=True),
        sa.Column("hydrocarbons", numeric, nullable=True),
        sa.Column("voc", numeric, nullable=True),
        sa.Column("other_gaseous_and_liquid", numeric, nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("modified_by", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_eco_analysis_zv_year_ver",
        ),
        sa.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.{ref_db_versions}.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "sheet_slug",
            "station_numb",
            "year_number",
            "database_version_id",
            name="uq_eco_analysis_zv_sheet_numb_year_ver",
        ),
        schema=SCHEMA_ECO,
    )
    op.create_index(
        f"ix_{TABLE}_sheet_slug",
        TABLE,
        ["sheet_slug"],
        unique=False,
        schema=SCHEMA_ECO,
    )
    op.create_index(
        f"ix_{TABLE}_station_numb",
        TABLE,
        ["station_numb"],
        unique=False,
        schema=SCHEMA_ECO,
    )
    op.create_index(
        f"ix_{TABLE}_year_number",
        TABLE,
        ["year_number"],
        unique=False,
        schema=SCHEMA_ECO,
    )
    op.create_index(
        f"ix_{TABLE}_database_version_id",
        TABLE,
        ["database_version_id"],
        unique=False,
        schema=SCHEMA_ECO,
    )

    _comment_on_table(
        conn,
        SCHEMA_ECO,
        TABLE,
        "Параметры анализа ЗВ: выверенная копия отчетных данных ГИС ТЭК "
        "для страниц zv-vse / zv-bez-kot",
    )
    for column, comment in _COLUMN_COMMENTS.items():
        _comment_on_column(conn, SCHEMA_ECO, TABLE, column, comment)


def downgrade():
    conn = op.get_bind()
    if column_utils.table_exists(conn, SCHEMA_ECO, TABLE):
        op.drop_table(TABLE, schema=SCHEMA_ECO)
