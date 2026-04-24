# -*- coding: utf-8 -*-
"""gaes_tep_source_project_indicators: новые поля ТЭП ГАЭС и переименование среднемноголетней выработки по очередям.

Revision ID: e7f8a9b0c1d2
Revises: d5e6f7a8b9c1
Create Date: 2026-03-31

- Переименование generation_average_multiyear_billion_kwh_stage_{1,2}
  -> generation_average_multiyear_million_kwh_stage_{1,2} (при наличии старых имен).
- Добавление колонок: среднемноголетняя по очередям (млн кВт·ч), потребление на заряд, капвложения млрд руб.
"""
from alembic import op
import sqlalchemy as sa


revision = "e7f8a9b0c1d2"
down_revision = "d5e6f7a8b9c1"
branch_labels = None
depends_on = None

SCHEMA_GEN = "gs_gen"
TABLE = "gaes_tep_source_project_indicators"

OLD_TO_NEW = (
    (
        "generation_average_multiyear_billion_kwh_stage_1",
        "generation_average_multiyear_million_kwh_stage_1",
    ),
    (
        "generation_average_multiyear_billion_kwh_stage_2",
        "generation_average_multiyear_million_kwh_stage_2",
    ),
)

ADD_COLUMNS = (
    "generation_average_multiyear_million_kwh_stage_1",
    "generation_average_multiyear_million_kwh_stage_2",
    "annual_charging_electricity_consumption_million_kwh_stage_1",
    "annual_charging_electricity_consumption_million_kwh_stage_2",
    "capital_investment_gaes_construction_current_prices_billion_rub",
)


def _table_columns(bind) -> set[str]:
    insp = sa.inspect(bind)
    try:
        names = insp.get_table_names(schema=SCHEMA_GEN)
    except Exception:
        return set()
    if TABLE not in names:
        return set()
    return {c["name"] for c in insp.get_columns(TABLE, schema=SCHEMA_GEN)}


def upgrade():
    bind = op.get_bind()
    cols = _table_columns(bind)
    if not cols:
        return

    for old, new in OLD_TO_NEW:
        if old in cols and new not in cols:
            op.execute(
                sa.text(
                    f'ALTER TABLE "{SCHEMA_GEN}"."{TABLE}" '
                    f'RENAME COLUMN "{old}" TO "{new}"'
                )
            )
            cols.discard(old)
            cols.add(new)

    for name in ADD_COLUMNS:
        if name not in cols:
            op.add_column(
                TABLE,
                sa.Column(name, sa.String(length=100), nullable=True),
                schema=SCHEMA_GEN,
            )
            cols.add(name)


def downgrade():
    bind = op.get_bind()
    cols = _table_columns(bind)
    if not cols:
        return

    for name in (
        "capital_investment_gaes_construction_current_prices_billion_rub",
        "annual_charging_electricity_consumption_million_kwh_stage_2",
        "annual_charging_electricity_consumption_million_kwh_stage_1",
    ):
        if name in cols:
            op.drop_column(TABLE, name, schema=SCHEMA_GEN)
            cols.discard(name)

    for old, new in OLD_TO_NEW:
        if new in cols and old not in cols:
            op.execute(
                sa.text(
                    f'ALTER TABLE "{SCHEMA_GEN}"."{TABLE}" '
                    f'RENAME COLUMN "{new}" TO "{old}"'
                )
            )
            cols.discard(new)
            cols.add(old)

    for name in (
        "generation_average_multiyear_million_kwh_stage_2",
        "generation_average_multiyear_million_kwh_stage_1",
    ):
        if name in cols:
            op.drop_column(TABLE, name, schema=SCHEMA_GEN)
