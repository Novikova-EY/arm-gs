# -*- coding: utf-8 -*-
"""Комментарии к таблицам и полям схем gs_ekp и gs_ter (по классам моделей).

Revision ID: q0r1s2t3u4v5
Revises: p9q0r1s2t3u4
Create Date: 2026-06-05
"""
import os
import sys

from alembic import op
from sqlalchemy import text

_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if _MIGRATIONS not in sys.path:
    sys.path.insert(0, _MIGRATIONS)
import column_utils  # noqa: E402

revision = "q0r1s2t3u4v5"
down_revision = "p9q0r1s2t3u4"
branch_labels = None
depends_on = None

_COMMON_COLUMNS = {
    "id": "Уникальный идентификатор записи",
    "created_by": "Пользователь, создавший запись",
    "modified_by": "Пользователь, последним изменивший запись",
    "created_at": "Дата и время создания записи",
    "updated_at": "Дата и время последнего изменения записи",
    "database_version_id": "Версия базы данных (FK -> gs_sys.gs_database_versions)",
    "note": "Примечание",
}

_FEDERAL_DISTRICT_FK = "Федеральный округ (FK -> gs_sys.gs_sys_federal_districts)"
_ECONOMIC_ACTIVITY_TYPE_FK = (
    "Вид экономической деятельности (FK -> gs_sys.gs_sys_economic_activity_types)"
)
_YEAR_NUMBER = "Номер года (связь с gs_sys.gs_sys_years по number и database_version_id)"

_SCHEMA_COMMENTS: dict[str, dict[str, dict[str, str]]] = {
    "gs_ekp": {
        "gs_ekp_federal_district_accum_fixed_capital_params": {
            "_table": (
                "Накопленные инвестиции в основной капитал по ВЭД "
                "для федерального округа (долгосрочный прогноз)"
            ),
            "id_federal_district": _FEDERAL_DISTRICT_FK,
            "id_economic_activity_type": _ECONOMIC_ACTIVITY_TYPE_FK,
            "year_number": _YEAR_NUMBER,
            "accumulated_fixed_capital_investment_mln_rub": (
                "Накопленные инвестиции в основной капитал, млн руб."
            ),
        },
        "gs_ekp_federal_district_accum_monetary_income_params": {
            "_table": "Накопленные денежные доходы населения по федеральному округу и году",
            "id_federal_district": _FEDERAL_DISTRICT_FK,
            "year_number": _YEAR_NUMBER,
            "accum_monetary_income_mln_rub": "Накопленные денежные доходы населения, млн руб.",
        },
        "gs_ekp_federal_district_eat_consumption_params": {
            "_table": "Потребление ЭЭ по ВЭД для федерального округа (долгосрочный прогноз)",
            "id_federal_district": _FEDERAL_DISTRICT_FK,
            "id_economic_activity_type": _ECONOMIC_ACTIVITY_TYPE_FK,
            "year_number": _YEAR_NUMBER,
            "energy_consumption_mln_kvt_ch": "Потребление электроэнергии, млн кВт·ч",
        },
        "gs_ekp_federal_district_population_params": {
            "_table": "Численность населения по федеральному округу и году (долгосрочный прогноз)",
            "id_federal_district": _FEDERAL_DISTRICT_FK,
            "year_number": _YEAR_NUMBER,
            "population_thousand_persons": "Численность населения, тыс. чел.",
        },
        "gs_ekp_federal_district_product_output_params": {
            "_table": (
                "Накопленный выпуск продукции по ВЭД "
                "для федерального округа (долгосрочный прогноз)"
            ),
            "id_federal_district": _FEDERAL_DISTRICT_FK,
            "id_economic_activity_type": _ECONOMIC_ACTIVITY_TYPE_FK,
            "year_number": _YEAR_NUMBER,
            "accumulated_product_output_mln_rub": "Накопленный выпуск продукции, млн руб.",
            "id_year_specific_product_output": (
                "Год цен для накопленного выпуска продукции (FK -> gs_sys.gs_sys_years)"
            ),
        },
        "gs_ekp_russia_federation_accum_fixed_capital_params": {
            "_table": (
                "Накопленные инвестиции в основной капитал по ВЭД "
                "для РФ в целом (долгосрочный прогноз)"
            ),
            "id_economic_activity_type": _ECONOMIC_ACTIVITY_TYPE_FK,
            "year_number": _YEAR_NUMBER,
            "accumulated_fixed_capital_investment_mln_rub": (
                "Накопленные инвестиции в основной капитал, млн руб."
            ),
        },
        "gs_ekp_russia_federation_consumption_params": {
            "_table": "Потребление ЭЭ по ВЭД для РФ в целом (долгосрочный прогноз)",
            "id_economic_activity_type": _ECONOMIC_ACTIVITY_TYPE_FK,
            "year_number": _YEAR_NUMBER,
            "energy_consumption_mln_kvt_ch": "Потребление электроэнергии, млн кВт·ч",
        },
        "gs_ekp_russia_federation_product_output_params": {
            "_table": (
                "Накопленный выпуск продукции по ВЭД "
                "для РФ в целом (долгосрочный прогноз)"
            ),
            "id_economic_activity_type": _ECONOMIC_ACTIVITY_TYPE_FK,
            "year_number": _YEAR_NUMBER,
            "accumulated_product_output_mln_rub": "Накопленный выпуск продукции, млн руб.",
            "id_year_specific_product_output": (
                "Год цен для накопленного выпуска продукции (FK -> gs_sys.gs_sys_years)"
            ),
        },
        "gs_ekp_accum_fixed_capital_formula_texts": {
            "_table": "Переопределения текстов формул для накопленных инвестиций в основной капитал",
            "formula_key": "Ключ формулы",
            "formula_text": "Текст формулы",
        },
        "gs_ekp_product_output_formula_texts": {
            "_table": "Переопределения текстов формул для выпуска продукции (долгосрочный прогноз)",
            "formula_key": "Ключ формулы",
            "formula_text": "Текст формулы",
        },
        "gs_ekp_ved_consumption_formula_texts": {
            "_table": "Переопределения текстов формул для потребления ЭЭ по ВЭД (долгосрочный прогноз)",
            "formula_key": "Ключ формулы",
            "formula_text": "Текст формулы",
        },
    },
    "gs_ter": {
        "gs_ter_energy_unit_power_transfers": {
            "_table": "Переток мощности энергоузла (субъект РФ, направление)",
            "id_energy_unit": "Энергоузел (FK -> gs_sys.gs_sys_energy_units)",
            "id_regional_district": "Субъект РФ (FK -> gs_sys.gs_sys_regional_districts)",
            "direction": "Направление перетока",
        },
        "gs_ter_energy_unit_power_transfer_values": {
            "_table": "Значения перетока электроэнергии по годам (млн кВт·ч)",
            "id_energy_unit_power_transfer": (
                "Переток энергоузла (FK -> gs_ter.gs_ter_energy_unit_power_transfers)"
            ),
            "year_number": "Год",
            "transfer_mln_kvt_ch": "Переток электроэнергии, млн кВт·ч",
        },
    },
}


def _comment_on_table(conn, schema: str, table: str, comment: str | None) -> None:
    if not column_utils.table_exists(conn, schema, table):
        return
    conn.execute(
        text(f'COMMENT ON TABLE "{schema}"."{table}" IS :comment'),
        {"comment": comment},
    )


def _comment_on_column(
    conn, schema: str, table: str, column: str, comment: str | None
) -> None:
    if not column_utils.table_has_column(conn, schema, table, column):
        return
    conn.execute(
        text(f'COMMENT ON COLUMN "{schema}"."{table}"."{column}" IS :comment'),
        {"comment": comment},
    )


def _apply_comments(conn, schema_comments: dict[str, dict[str, dict[str, str]]], clear: bool) -> None:
    for schema, tables in schema_comments.items():
        for table, comments in tables.items():
            table_comment = None if clear else comments.get("_table")
            _comment_on_table(conn, schema, table, table_comment)

            merged_columns = {**_COMMON_COLUMNS, **comments}
            for column, comment in merged_columns.items():
                if column == "_table":
                    continue
                column_comment = None if clear else comment
                _comment_on_column(conn, schema, table, column, column_comment)


def upgrade():
    conn = op.get_bind()
    _apply_comments(conn, _SCHEMA_COMMENTS, clear=False)


def downgrade():
    conn = op.get_bind()
    _apply_comments(conn, _SCHEMA_COMMENTS, clear=True)
