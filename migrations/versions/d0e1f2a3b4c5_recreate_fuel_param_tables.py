"""recreate gs_fue_equipment_group_fuel_param and gs_fue_equipment_group_extra_fuel_param

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-03-05 21:10:00.000000

Удаляет и заново создаёт таблицы gs_fue_equipment_group_fuel_param и
gs_fue_equipment_group_extra_fuel_param. Схема соответствует моделям.
"""
from alembic import op
import sqlalchemy as sa
from config import SCHEMA_FUEL, SCHEMA_REFDATA, SCHEMA_FUE_EM


revision = "d0e1f2a3b4c5"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None

NUMERIC = sa.Numeric(20, 6)


def _drop_tables(conn):
    conn.execute(sa.text(f"DROP TABLE IF EXISTS {SCHEMA_FUEL}.gs_fue_equipment_group_fuel_param CASCADE"))
    conn.execute(sa.text(f"DROP TABLE IF EXISTS {SCHEMA_FUEL}.gs_fue_equipment_group_extra_fuel_param CASCADE"))


def _create_fuel_param(op_obj):
    # Гарантируем наличие уникального индекса на code в gs_fue_em_equipment_group,
    # т.к. FK obor -> gs_fue_em_equipment_group.code требует уникальности целевой колонки.
    op_obj.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_fue_em_equipment_group_code "
        f"ON {SCHEMA_FUE_EM}.gs_fue_em_equipment_group (code)"
    )

    # Гарантируем наличие уникального индекса на external_id в gs_fue_em_business_unit,
    # т.к. FK be -> gs_fue_em_business_unit.external_id требует уникальности целевой колонки.
    op_obj.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS uq_gs_fue_em_business_unit_external_id "
        f"ON {SCHEMA_FUE_EM}.gs_fue_em_business_unit (external_id)"
    )

    op_obj.create_table(
        "gs_fue_equipment_group_fuel_param",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("equipment_group_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(512), nullable=True),
        sa.Column("year_number", sa.Integer(), nullable=True),
        sa.Column("nust", NUMERIC, nullable=True),
        sa.Column("nr", NUMERIC, nullable=True),
        sa.Column("e", NUMERIC, nullable=True),
        sa.Column("ewtp", NUMERIC, nullable=True),
        sa.Column("eotp", NUMERIC, nullable=True),
        sa.Column("eurt", NUMERIC, nullable=True),
        sa.Column("eust", NUMERIC, nullable=True),
        sa.Column("snk", NUMERIC, nullable=True),
        sa.Column("q", NUMERIC, nullable=True),
        sa.Column("qotr", NUMERIC, nullable=True),
        sa.Column("turt", NUMERIC, nullable=True),
        sa.Column("tust", NUMERIC, nullable=True),
        sa.Column("sn_t", NUMERIC, nullable=True),
        sa.Column("b", NUMERIC, nullable=True),
        sa.Column("gaz", NUMERIC, nullable=True),
        sa.Column("isk_gaz", NUMERIC, nullable=True),
        sa.Column("mazut", NUMERIC, nullable=True),
        sa.Column("torf", NUMERIC, nullable=True),
        sa.Column("slan", NUMERIC, nullable=True),
        sa.Column("proch", NUMERIC, nullable=True),
        sa.Column("ugol", NUMERIC, nullable=True),
        sa.Column("don", NUMERIC, nullable=True),
        sa.Column("podm", NUMERIC, nullable=True),
        sa.Column("pech", NUMERIC, nullable=True),
        sa.Column("arkt", NUMERIC, nullable=True),
        sa.Column("kuzn", NUMERIC, nullable=True),
        sa.Column("ural", NUMERIC, nullable=True),
        sa.Column("bashk", NUMERIC, nullable=True),
        sa.Column("kazah", NUMERIC, nullable=True),
        sa.Column("kan", NUMERIC, nullable=True),
        sa.Column("tung", NUMERIC, nullable=True),
        sa.Column("irkut", NUMERIC, nullable=True),
        sa.Column("hak", NUMERIC, nullable=True),
        sa.Column("tuv", NUMERIC, nullable=True),
        sa.Column("bur", NUMERIC, nullable=True),
        sa.Column("chit", NUMERIC, nullable=True),
        sa.Column("yakut", NUMERIC, nullable=True),
        sa.Column("amur", NUMERIC, nullable=True),
        sa.Column("urg", NUMERIC, nullable=True),
        sa.Column("ushum", NUMERIC, nullable=True),
        sa.Column("prim", NUMERIC, nullable=True),
        sa.Column("mag", NUMERIC, nullable=True),
        sa.Column("chukot", NUMERIC, nullable=True),
        sa.Column("kamch", NUMERIC, nullable=True),
        sa.Column("sah", NUMERIC, nullable=True),
        sa.Column("nt", NUMERIC, nullable=True),
        sa.Column("nt_sum", NUMERIC, nullable=True),
        sa.Column("numb1120", sa.Integer(), nullable=True),
        sa.Column("numb1", sa.Integer(), nullable=True),
        sa.Column("obor", sa.Integer(), nullable=True),
        sa.Column("ved", sa.Integer(), nullable=True),
        sa.Column("вед", sa.Integer(), nullable=True),
        sa.Column("obl", sa.String(80), nullable=True),
        sa.Column("dep", sa.String(80), nullable=True),
        sa.Column("oes", sa.String(80), nullable=True),
        sa.Column("ees", sa.Integer(), nullable=True),
        sa.Column("er", sa.String(80), nullable=True),
        sa.Column("gk", sa.String(80), nullable=True),
        sa.Column("be", sa.String(80), nullable=True),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["equipment_group_id"], [f"{SCHEMA_FUEL}.gs_fue_equipment_groups.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["obor"], [f"{SCHEMA_FUE_EM}.gs_fue_em_equipment_group.code"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["obl"], [f"{SCHEMA_FUE_EM}.gs_fue_em_territories_energy.external_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["dep"], [f"{SCHEMA_FUE_EM}.gs_fue_em_department.external_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["oes"], [f"{SCHEMA_FUE_EM}.gs_fue_em_union_energy_system.external_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["er"], [f"{SCHEMA_FUE_EM}.gs_fue_em_economic_region.external_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["gk"], [f"{SCHEMA_FUE_EM}.gs_fue_em_gen_company.external_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["be"], [f"{SCHEMA_FUE_EM}.gs_fue_em_business_unit.external_id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["database_version_id"], [f"{SCHEMA_REFDATA}.gs_database_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("equipment_group_id", "year_number", name="uq_equipment_group_fuel_param_group_year"),
        schema=SCHEMA_FUEL,
    )
    op_obj.create_index("ix_gs_fue_equipment_group_fuel_param_equipment_group_id", "gs_fue_equipment_group_fuel_param", ["equipment_group_id"], schema=SCHEMA_FUEL)
    op_obj.create_index("ix_gs_fue_equipment_group_fuel_param_year_number", "gs_fue_equipment_group_fuel_param", ["year_number"], schema=SCHEMA_FUEL)
    op_obj.create_index("ix_gs_fue_equipment_group_fuel_param_obor", "gs_fue_equipment_group_fuel_param", ["obor"], schema=SCHEMA_FUEL)
    op_obj.create_index("ix_gs_fue_equipment_group_fuel_param_obl", "gs_fue_equipment_group_fuel_param", ["obl"], schema=SCHEMA_FUEL)
    op_obj.create_index("ix_gs_fue_equipment_group_fuel_param_dep", "gs_fue_equipment_group_fuel_param", ["dep"], schema=SCHEMA_FUEL)
    op_obj.create_index("ix_gs_fue_equipment_group_fuel_param_oes", "gs_fue_equipment_group_fuel_param", ["oes"], schema=SCHEMA_FUEL)
    op_obj.create_index("ix_gs_fue_equipment_group_fuel_param_er", "gs_fue_equipment_group_fuel_param", ["er"], schema=SCHEMA_FUEL)
    op_obj.create_index("ix_gs_fue_equipment_group_fuel_param_gk", "gs_fue_equipment_group_fuel_param", ["gk"], schema=SCHEMA_FUEL)
    op_obj.create_index("ix_gs_fue_equipment_group_fuel_param_be", "gs_fue_equipment_group_fuel_param", ["be"], schema=SCHEMA_FUEL)
    op_obj.create_index("ix_gs_fue_equipment_group_fuel_param_database_version_id", "gs_fue_equipment_group_fuel_param", ["database_version_id"], schema=SCHEMA_FUEL)


def _create_extra_fuel_param(op_obj):
    op_obj.create_table(
        "gs_fue_equipment_group_extra_fuel_param",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("equipment_group_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(512), nullable=True),
        sa.Column("year_number", sa.Integer(), nullable=True),
        sa.Column("gaz_prir", NUMERIC, nullable=True),
        sa.Column("gazpp", NUMERIC, nullable=True),
        sa.Column("disel", NUMERIC, nullable=True),
        sa.Column("maztop", NUMERIC, nullable=True),
        sa.Column("gtt", NUMERIC, nullable=True),
        sa.Column("nft_proch", NUMERIC, nullable=True),
        sa.Column("domen_g", NUMERIC, nullable=True),
        sa.Column("koks_g", NUMERIC, nullable=True),
        sa.Column("prochgaz", NUMERIC, nullable=True),
        sa.Column("tvproch", NUMERIC, nullable=True),
        sa.Column("szh_gaz", NUMERIC, nullable=True),
        sa.Column("inoe", NUMERIC, nullable=True),
        sa.Column("nazar", NUMERIC, nullable=True),
        sa.Column("ibor", NUMERIC, nullable=True),
        sa.Column("berez", NUMERIC, nullable=True),
        sa.Column("per", NUMERIC, nullable=True),
        sa.Column("irbei", NUMERIC, nullable=True),
        sa.Column("kansk", NUMERIC, nullable=True),
        sa.Column("gusin", NUMERIC, nullable=True),
        sa.Column("tugn", NUMERIC, nullable=True),
        sa.Column("okino", NUMERIC, nullable=True),
        sa.Column("azey", NUMERIC, nullable=True),
        sa.Column("mug", NUMERIC, nullable=True),
        sa.Column("cher", NUMERIC, nullable=True),
        sa.Column("jer", NUMERIC, nullable=True),
        sa.Column("karab", NUMERIC, nullable=True),
        sa.Column("vork", NUMERIC, nullable=True),
        sa.Column("intin", NUMERIC, nullable=True),
        sa.Column("sver", NUMERIC, nullable=True),
        sa.Column("chel", NUMERIC, nullable=True),
        sa.Column("kizel", NUMERIC, nullable=True),
        sa.Column("har", NUMERIC, nullable=True),
        sa.Column("urt", NUMERIC, nullable=True),
        sa.Column("tataur", NUMERIC, nullable=True),
        sa.Column("tarbag", NUMERIC, nullable=True),
        sa.Column("zab_kam", NUMERIC, nullable=True),
        sa.Column("rai", NUMERIC, nullable=True),
        sa.Column("erk", NUMERIC, nullable=True),
        sa.Column("ogodj", NUMERIC, nullable=True),
        sa.Column("svo", NUMERIC, nullable=True),
        sa.Column("bikin", NUMERIC, nullable=True),
        sa.Column("razdol", NUMERIC, nullable=True),
        sa.Column("hankai", NUMERIC, nullable=True),
        sa.Column("neru", NUMERIC, nullable=True),
        sa.Column("zyryan", NUMERIC, nullable=True),
        sa.Column("pyak", NUMERIC, nullable=True),
        sa.Column("kuzngd", NUMERIC, nullable=True),
        sa.Column("kuznt", NUMERIC, nullable=True),
        sa.Column("kuznss", NUMERIC, nullable=True),
        sa.Column("kuznun", NUMERIC, nullable=True),
        sa.Column("bering", NUMERIC, nullable=True),
        sa.Column("anad", NUMERIC, nullable=True),
        sa.Column("ekib", NUMERIC, nullable=True),
        sa.Column("maikub", NUMERIC, nullable=True),
        sa.Column("karag", NUMERIC, nullable=True),
        sa.Column("karajyra", NUMERIC, nullable=True),
        sa.Column("teniz", NUMERIC, nullable=True),
        sa.Column("numb1120", sa.Integer(), nullable=True),
        sa.Column("numb1", sa.Integer(), nullable=True),
        sa.Column("database_version_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["equipment_group_id"], [f"{SCHEMA_FUEL}.gs_fue_equipment_groups.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["database_version_id"], [f"{SCHEMA_REFDATA}.gs_database_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("equipment_group_id", "year_number", name="uq_equipment_group_extra_fuel_param_group_year"),
        schema=SCHEMA_FUEL,
    )
    op_obj.create_index("ix_gs_fue_equipment_group_extra_fuel_param_equipment_group_id", "gs_fue_equipment_group_extra_fuel_param", ["equipment_group_id"], schema=SCHEMA_FUEL)
    op_obj.create_index("ix_gs_fue_equipment_group_extra_fuel_param_year_number", "gs_fue_equipment_group_extra_fuel_param", ["year_number"], schema=SCHEMA_FUEL)
    op_obj.create_index("ix_gs_fue_equipment_group_extra_fuel_param_numb1120", "gs_fue_equipment_group_extra_fuel_param", ["numb1120"], schema=SCHEMA_FUEL)
    op_obj.create_index("ix_gs_fue_equipment_group_extra_fuel_param_database_version_id", "gs_fue_equipment_group_extra_fuel_param", ["database_version_id"], schema=SCHEMA_FUEL)


def upgrade():
    conn = op.get_bind()
    _drop_tables(conn)
    _create_fuel_param(op)
    _create_extra_fuel_param(op)


def downgrade():
    conn = op.get_bind()
    _drop_tables(conn)
