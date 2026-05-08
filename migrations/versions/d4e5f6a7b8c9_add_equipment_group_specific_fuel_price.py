"""add_equipment_group_specific_fuel_price

Revision ID: d4e5f6a7b8c9
Revises: c3a2f1b8e4d5
Create Date: 2026-03-12 20:00:00.000000

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


# revision identifiers, used by Alembic.
revision = 'd4e5f6a7b8c9'
down_revision = 'c3a2f1b8e4d5'
branch_labels = None
depends_on = None

SCHEMA = 'gs_fue'
TABLE = 'gs_fue_equipment_group_specific_fuel_price'


def _table_exists(connection):
    result = connection.execute(
        text(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = :schema AND table_name = :table"
        ),
        {"schema": SCHEMA, "table": TABLE},
    )
    return result.fetchone() is not None


def upgrade():
    conn = op.get_bind()
    if _table_exists(conn):
        return
    ref_versions = column_utils.database_versions_physical_table_name(conn, "gs_sys")
    if ref_versions is None:
        raise RuntimeError(
            "Не найдена таблица версий БД в gs_sys "
            "(gs_sys_database_versions или gs_database_versions как BASE TABLE)"
        )
    op.create_table(TABLE,
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('equipment_group_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=512), nullable=True),
        sa.Column('year_number', sa.Integer(), nullable=True),
        sa.Column('obl', sa.String(length=80), nullable=True),
        sa.Column('gaz_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('gazpp_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('gaz_prir_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('mazut_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('disel_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('maztop_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('gtt_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('nft_proch_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('torf_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('isk_gaz_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('domen_g_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('koks_g_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('prochgaz_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('proch_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('tvproch_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('szh_gaz_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('inoe_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('don_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('podm_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('pech_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('vork_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('intin_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kuzn_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kuzngd_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kuznt_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kuznss_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kuznun_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('ural_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('sver_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('chel_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kizel_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('bashk_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kazah_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('ekib_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('maikub_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('karag_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('karajyra_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('teniz_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kan_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('nazar_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('ibor_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('berez_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('per_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('irbei_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kansk_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('irkut_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('azey_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('mug_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('cher_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('tung_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('jer_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('karab_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('hak_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('tuv_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('bur_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('gusin_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('tugn_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('okino_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('chit_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('har_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('urt_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('tataur_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('tarbag_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('zab_kam_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('amur_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('rai_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('erk_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('ogodj_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('svo_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('urg_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('ushum_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('prim_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('bikin_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('razdol_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('hankai_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('yakut_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('neru_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('zyryan_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('pyak_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('mag_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('chukot_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('anad_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('bering_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('kamch_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('sah_c', sa.Numeric(precision=20, scale=6), nullable=True),
        sa.Column('numb1120', sa.Integer(), nullable=True),
        sa.Column('sost', sa.String(length=80), nullable=True),
        sa.Column('group', sa.String(length=80), nullable=True),
        sa.Column('database_version_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['database_version_id'], [f'gs_sys.{ref_versions}.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['equipment_group_id'], ['gs_fue.gs_fue_equipment_groups.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('equipment_group_id', 'year_number', name='uq_equipment_group_specific_fuel_price_group_year'),
        schema=SCHEMA,
    )


def downgrade():
    op.drop_table(TABLE, schema=SCHEMA)
