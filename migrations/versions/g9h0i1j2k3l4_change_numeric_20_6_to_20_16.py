"""change_numeric_20_6_to_20_16

Revision ID: g9h0i1j2k3l4
Revises: f8g9h0i1j2k3
Create Date: 2026-03-15

Замена всех колонок Numeric(20, 6) на Numeric(20, 16) в таблицах gs_fue.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g9h0i1j2k3l4'
down_revision = 'f8g9h0i1j2k3'
branch_labels = None
depends_on = None

SCHEMA = 'gs_fue'
# NUMERIC(20, 6) -> NUMERIC(36, 16): 20 цифр до запятой, 16 после
# (20,16) дает лишь 4 цифры до запятой — данные не помещаются
NEW_TYPE = sa.Numeric(precision=36, scale=16)
OLD_TYPE = sa.Numeric(precision=20, scale=6)

# Таблицы и колонки для изменения (Numeric(20,6) -> Numeric(20,16))
TABLES_COLUMNS = {
    'gs_fue_equipment_group_fuel_param': [
        'nust', 'nr', 'e', 'ewtp', 'eotp', 'eurt', 'eust', 'snk', 'q', 'qotr',
        'turt', 'tust', 'sn_t', 'b', 'gaz', 'isk_gaz', 'mazut', 'torf', 'slan',
        'proch', 'ugol', 'don', 'podm', 'pech', 'arkt', 'kuzn', 'ural', 'bashk',
        'kazah', 'kan', 'tung', 'irkut', 'hak', 'tuv', 'bur', 'chit', 'yakut',
        'amur', 'urg', 'ushum', 'prim', 'mag', 'chukot', 'kamch', 'sah',
        'nt', 'nt_sum',
    ],
    'gs_fue_equipment_group_extra_fuel_param': [
        'gaz_prir', 'gazpp', 'disel', 'maztop', 'gtt', 'nft_proch', 'domen_g',
        'koks_g', 'prochgaz', 'tvproch', 'szh_gaz', 'inoe', 'nazar', 'ibor',
        'berez', 'per', 'irbei', 'kansk', 'gusin', 'tugn', 'okino', 'azey', 'mug',
        'cher', 'jer', 'karab', 'vork', 'intin', 'sver', 'chel', 'kizel', 'har',
        'urt', 'tataur', 'tarbag', 'zab_kam', 'rai', 'erk', 'ogodj', 'svo',
        'bikin', 'razdol', 'hankai', 'neru', 'zyryan', 'pyak', 'kuzngd', 'kuznt',
        'kuznss', 'kuznun', 'bering', 'anad', 'ekib', 'maikub', 'karag',
        'karajyra', 'teniz',
    ],
    'gs_fue_equipment_group_specific_fuel_consumption': [
        'y', 'btp', 'sntp', 'bk', 'snk', 'y_calc', 'btp_calc', 'sntp_calc',
        'bk_calc', 'snk_calc',
    ],
    'gs_fue_equipment_group_specific_fuel_price': [
        'gaz_c', 'gazpp_c', 'gaz_prir_c', 'mazut_c', 'disel_c', 'maztop_c',
        'gtt_c', 'nft_proch_c', 'torf_c', 'isk_gaz_c', 'domen_g_c', 'koks_g_c',
        'prochgaz_c', 'proch_c', 'tvproch_c', 'szh_gaz_c', 'inoe_c', 'don_c',
        'podm_c', 'pech_c', 'vork_c', 'intin_c', 'kuzn_c', 'kuzngd_c', 'kuznt_c',
        'kuznss_c', 'kuznun_c', 'ural_c', 'sver_c', 'chel_c', 'kizel_c',
        'bashk_c', 'kazah_c', 'ekib_c', 'maikub_c', 'karag_c', 'karajyra_c',
        'teniz_c', 'kan_c', 'nazar_c', 'ibor_c', 'berez_c', 'per_c', 'irbei_c',
        'kansk_c', 'irkut_c', 'azey_c', 'mug_c', 'cher_c', 'tung_c', 'jer_c',
        'karab_c', 'hak_c', 'tuv_c', 'bur_c', 'gusin_c', 'tugn_c', 'okino_c',
        'chit_c', 'har_c', 'urt_c', 'tataur_c', 'tarbag_c', 'zab_kam_c',
        'amur_c', 'rai_c', 'erk_c', 'ogodj_c', 'svo_c', 'urg_c', 'ushum_c',
        'prim_c', 'bikin_c', 'razdol_c', 'hankai_c', 'yakut_c', 'neru_c',
        'zyryan_c', 'pyak_c', 'mag_c', 'chukot_c', 'anad_c', 'bering_c',
        'kamch_c', 'sah_c',
    ],
    'gs_fue_equipment_group_specific_fuel_cost': [
        'gaz', 'gaz_prir', 'gazpp', 'mazut', 'disel', 'maztop', 'gtt',
        'nft_proch', 'torf', 'isk_gaz', 'domen_g', 'koks_g', 'prochgaz', 'proch',
        'tvproch', 'szh_gaz', 'inoe', 'ugol', 'don', 'podm', 'pech', 'vork',
        'intin', 'kuzn', 'kuzngd', 'kuznt', 'kuznss', 'kuznun', 'ural', 'sver',
        'chel', 'kizel', 'bashk', 'kazah', 'ekib', 'maikub', 'karag', 'karajyra',
        'teniz', 'kan', 'nazar', 'ibor', 'berez', 'per', 'irbei', 'kansk',
        'irkut', 'azey', 'mug', 'cher', 'tung', 'jer', 'karab', 'hak', 'tuv',
        'bur', 'gusin', 'tugn', 'okino', 'chit', 'har', 'urt', 'tataur', 'tarbag',
        'zab_kam', 'amur', 'rai', 'erk', 'ogodj', 'svo', 'urg', 'ushum', 'prim',
        'bikin', 'razdol', 'hankai', 'yakut', 'neru', 'zyryan', 'pyak', 'mag',
        'chukot', 'anad', 'bering', 'kamch', 'sah',
    ],
}


def upgrade():
    for table, columns in TABLES_COLUMNS.items():
        for col in columns:
            op.alter_column(
                table,
                col,
                existing_type=OLD_TYPE,
                type_=NEW_TYPE,
                existing_nullable=True,
                schema=SCHEMA,
            )


def downgrade():
    for table, columns in TABLES_COLUMNS.items():
        for col in columns:
            op.alter_column(
                table,
                col,
                existing_type=NEW_TYPE,
                type_=OLD_TYPE,
                existing_nullable=True,
                schema=SCHEMA,
            )
