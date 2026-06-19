# -*- coding: utf-8 -*-
"""Генерация миграции COMMENT ON для gs_ec, gs_pd, gs_fue."""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app import create_app
from app.extensions import db

REVISION = "s2t3u4v5w6x7"
DOWN_REVISION = "q0r1s2t3u4v5"
OUTPUT = Path("migrations/versions/s2t3u4v5w6x7_add_gs_ec_gs_pd_gs_fue_table_comments.py")

SCHEMAS = ("gs_ec", "gs_pd", "gs_fue")
MODEL_DIRS = (
    Path("app/energy_consumption"),
    Path("app/power_demand"),
    Path("app/fuel/models"),
)

_COMMON_COLUMNS = {
    "id": "Уникальный идентификатор записи",
    "created_by": "Пользователь, создавший запись",
    "modified_by": "Пользователь, последним изменивший запись",
    "created_at": "Дата и время создания записи",
    "updated_at": "Дата и время последнего изменения записи",
    "database_version_id": "Версия базы данных (FK -> gs_sys.gs_database_versions)",
    "note": "Примечание",
    "year_number": "Номер года",
    "perimeter_variant_code": "Код варианта периметра (NULL — без варианта)",
    "formula_key": "Ключ формулы",
    "formula_text": "Текст формулы",
    "external_code": "Внешний код (UUID)",
    "external_id": "Внешний идентификатор",
    "external_name": "Внешнее наименование",
    "name": "Наименование",
    "is_historical_maximum": "Признак исторического максимума (true — без года)",
    "parameter_value": "Значение показателя за год (числовое, зависит от row_kind)",
    "row_kind": "Тип строки показателя (intensity, graph_point, calculated, delta)",
}

_FK_COLUMNS = {
    "id_federal_district": "Федеральный округ (FK -> gs_sys.gs_sys_federal_districts)",
    "id_regional_district": "Субъект РФ (FK -> gs_sys.gs_sys_regional_districts)",
    "id_economic_activity_type": "Вид экономической деятельности (FK -> gs_sys.gs_sys_economic_activity_types)",
    "id_energy_area": "Энергорайон (FK -> gs_sys.gs_sys_energy_areas)",
    "id_energy_unit": "Энергоузел (FK -> gs_sys.gs_sys_energy_units)",
    "id_energy_zone": "Энергозона (FK -> gs_sys.gs_sys_energy_zones)",
    "id_energy_system_type": "Тип энергосистемы (FK -> gs_sys.gs_sys_energy_system_types)",
    "id_regional_energy_system": "Региональная энергосистема (FK -> gs_sys.gs_sys_regional_energy_systems)",
    "id_union_energy_system": "Объединённая энергосистема (FK -> gs_sys.gs_sys_union_energy_systems)",
    "id_synchronous_area": "Синхронная зона (FK -> gs_sys.gs_sys_synchronous_areas)",
    "id_equipment_group": "Группа оборудования (FK -> gs_fue.gs_fue_equipment_groups)",
    "id_equipment_group_set": "Набор групп оборудования (FK -> gs_fue.gs_fue_equipment_group_sets)",
    "id_station": "Электростанция (FK -> gs_gen.gs_gen_stations)",
    "id_machine": "Энергоблок (FK -> gs_gen.gs_gen_machines)",
    "id_fuel": "Топливо (FK -> gs_sys.gs_sys_fuels)",
    "id_fuel_type": "Тип топлива (FK -> gs_sys.gs_sys_fuel_types)",
    "id_year_specific_product_output": "Год цен (FK -> gs_sys.gs_sys_years)",
    "id_year": "Расчётный год (FK -> gs_sys.gs_sys_years)",
    "id_base_year": "Базовый год (FK -> gs_sys.gs_sys_years)",
    "id_department": "Департамент (FK -> gs_sys.gs_sys_departments)",
    "regional_district_id": "Субъект РФ (FK -> gs_sys.gs_sys_regional_districts)",
    "regional_energy_system_id": "Региональная энергосистема (FK -> gs_sys.gs_sys_regional_energy_systems)",
    "union_energy_system_id": "Объединённая энергосистема (FK -> gs_sys.gs_sys_union_energy_systems)",
    "federal_district_ref_uuid": "UUID федерального округа для связки",
    "equipment_group_id": "Группа оборудования (FK -> gs_fue.gs_fue_equipment_groups)",
    "distribution_parameter_id": "Параметр распределения (FK -> gs_fue.gs_fue_distribution_parameters)",
    "machine_id": "Энергоблок (FK -> gs_gen.gs_gen_machines)",
    "station_id": "Электростанция (FK -> gs_gen.gs_gen_stations)",
    "equipment_group_type_id": "Тип группы оборудования (FK -> gs_sys.gs_sys_equipment_groups)",
    "equipment_group_set_station_id": "Связка станция+тип группы (FK -> gs_fue.gs_fue_equipment_group_type_stations)",
}

_VALUE_COLUMNS = {
    "energy_consumption_mln_kvt_ch": "Потребление электроэнергии, млн кВт·ч",
    "energy_consumption_sipr_mln_kvt_ch": "Потребление электроэнергии (СИПР), млн кВт·ч",
    "max_power_consumption_mw": "Максимальное потребление мощности, МВт",
    "peak_datetime_msk": "Дата и время максимума потребления мощности (МСК)",
    "avg_daily_air_temp_c": "Средняя дневная температура воздуха, °C",
    "combined_on_oes": "Совмещённый максимум на ОЭС, МВт",
    "combined_on_ees": "Совмещённый максимум на ЕЭС, МВт",
    "combined_on_es": "Совмещённый максимум на РЭС, МВт",
    "coefficient_a": "Коэффициент A",
    "coefficient_x": "Коэффициент X",
    "coeff_k_combined_on_oes": "Коэффициент k для показателя «Совмещённый на ОЭС, МВт»",
    "coeff_k_combined_on_ees": "Коэффициент k для показателя «Совмещённый на ЕЭС, МВт»",
    "coeff_k_calculated_max_power_mw": "Коэффициент k для показателя «Расчетный максимум ОЭС, МВт»",
    "coeff_k_calculated_combined_on_ees_mw": "Коэффициент k для показателя «Расчетный совмещенный на ЕЭС, МВт»",
    "calculated_max_power_mw": "Расчетный максимум ОЭС, МВт",
    "calculated_combined_on_ees_mw": "Расчетный совмещенный на ЕЭС, МВт",
    "electrical_intensity_kvt_ch_per_person": "Электроёмкость, кВт·ч/чел.",
    "population_thousand_persons": "Численность населения, тыс. чел.",
    "population_consumption_mln_kvt_ch": "Потребление населения, млн кВт·ч",
    "transfer_mln_kvt_ch": "Переток электроэнергии, млн кВт·ч",
    "name_ext": "Наименование (БД Топливо)",
    "niv": "Признак группы оборудования",
    "comp": "Признак электростанции, разбитой на группы оборудования",
    "main": "Код электростанции, в которую входит группа оборудования",
    "d": "Признак действующей электростанции",
    "r": "Признак расширяемой электростанции",
    "forem": "Признак ФОРЭМ",
    "vedomstvo": "Ведомство",
    "obl": "Код субъекта РФ (внешний идентификатор)",
    "dep": "Код департамента (внешний идентификатор)",
    "oes": "Код ОЭС (внешний идентификатор)",
    "er": "Код экономического района (внешний идентификатор)",
    "gk": "Код генерирующей компании (внешний идентификатор)",
    "gk_branch": "Код филиала генерирующей компании (внешний идентификатор)",
    "be": "Код бизнес-единицы (внешний идентификатор)",
    "city": "Код города (внешний идентификатор)",
    "equipment_group_k": "Код группы оборудования (внешний идентификатор)",
    "filter_text": "Текст фильтра",
    "e": "Выработка ТЭС / выработка электроэнергии (E)",
    "k": "Коэффициент загрузки",
    "kplus": "Верхняя граница коэффициента загрузки (k+)",
    "kmin": "Нижняя граница коэффициента загрузки (k−)",
    "kn": "Коэффициент загрузки нового оборудования (расчётный)",
    "knps": "Коэффициент загрузки нового паросилового оборудования (расчётный)",
    "kngt": "Коэффициент загрузки нового газотурбинного оборудования (расчётный)",
    "knpg": "Коэффициент загрузки нового парогазового оборудования (расчётный)",
    "hnps": "ЧЧИУМ нового паросилового оборудования",
    "hngt": "ЧЧИУМ нового газотурбинного оборудования",
    "hnpg": "ЧЧИУМ нового парогазового оборудования",
    "doptim": "Коэффициент допустимого отклонения",
    "lim": "Наличие ограничений по выработке для РЭС",
    "bkl": "Вспомогательный номер территории для распределения выработки по станциям ОЭС",
    "numb": "Порядковый номер",
    "wname": "Наименование таблицы с обобщёнными показателями по станциям",
    "uname": "Наименование таблицы с удельными технико-экономическими показателями",
    "toplname": "Наименование таблицы со структурой топливного баланса",
    "dopname": "Наименование таблицы с детализацией видов топлива",
    "base_year": "Базовый год (номер)",
    "e_target": "Целевая выработка электроэнергии (E_целевое)",
    "bnust": "Сумма установленной мощности (N_уст), базовый год, МВт",
    "be": "Сумма выработки электроэнергии (E), базовый год",
    "betp": "Сумма теплофикационной выработки (Этц), базовый год",
    "bq": "Сумма отпуска тепла (Q), базовый год",
    "bqotr": "Сумма тепла на отработку (Q_отр), базовый год",
    "bptp": "Доля тепла в электроэнергии, %, базовый год",
    "bh": "Удельные часы (Н), базовый год",
    "cnust": "Сумма установленной мощности (N_уст), расчётный год, МВт",
    "cnustn": "Сумма мощности новых агрегатов (N_нов), расчётный год, МВт",
    "cnustngt": "Мощность нового газотурбинного оборудования, расчётный год, МВт",
    "cnustnpg": "Мощность нового парогазового оборудования, расчётный год, МВт",
    "cnustnps": "Мощность нового паросилового оборудования, расчётный год, МВт",
    "cetp": "Сумма теплофикационной выработки (Этц), расчётный год",
    "cq": "Сумма отпуска тепла (Q), расчётный год",
    "cqotr": "Сумма тепла на отработку (Q_отр), расчётный год",
    "cptp": "Доля тепла в электроэнергии, %, расчётный год",
    "ch": "Удельные часы (Н), расчётный год",
    "pe": "Отношение выработки E (расчётный/базовый год)",
    "ph": "Удельные часы на действующую часть парка (PH)",
    "ph1": "Вспомогательный показатель удельных часов (PH1)",
    "pq": "Отношение отпуска тепла Q (расчётный/базовый год)",
    "potr": "Отношение тепла на отработку (расчётный/базовый год)",
    "hd": "Удельные часы на действующую часть парка (hd)",
    "coeff_base": "Базовый коэффициент загрузки (этап «Коэфф»)",
    "coeff_min": "Нижняя граница коэффициента загрузки (этап «Коэфф»)",
    "coeff_max": "Верхняя граница коэффициента загрузки (этап «Коэфф»)",
    "coeff_effective": "Эффективный коэффициент загрузки (этап «Коэфф»)",
    "formtxt": "Текст формулы топлива",
    "variant_number": "Номер варианта формулы (поле v из Access)",
    "addr": "Адрес электростанции",
    "codegor": "Код города",
    "fo": "Код федерального округа (внешний идентификатор)",
    "gkf": "Код филиала генерирующей компании (внешний идентификатор)",
    "n1": "Мощность блока в группе оборудования, вариант 1",
    "n2": "Мощность блока в группе оборудования, вариант 2",
    "p1": "Давление пара перед турбиной, вариант 1",
    "p2": "Давление пара перед турбиной, вариант 2",
    "ordnumb": "Порядковый номер электростанции",
    "tm": "Название типов турбин",
    "stnumb": "Номер агрегата",
    "yearin": "Год ввода в эксплуатацию",
    "dem": "Год демонтажа",
    "grcode": "Код группы оборудования",
    "stname": "Название электростанции",
    "opesname": "Тип (марка) оборудования",
    "year": "Год",
    "restriction_name": "Наименование ограничения",
    "group": "Группа цен (sost/group из Access)",
    "sost": "Состав/группа цен (sost из Access)",
    "ved": "Ведомство (ved)",
    "ees": "Энергосистема (ees)",
    "obor": "Код группы оборудования (obor)",
    "numb1": "Номер",
    "numb1120": "Код электростанции",
    "gtt": "Газотурбинное топливо",
    "inoe": "Иное топливо",
    "luch": "Лучегорское (уголь)",
    "вед": "Ведомство (вед)",
}

_RUNTIME_FUEL_LABELS: dict[str, str] = {}


def first_docstring(src: str) -> str:
    match = re.search(r'"""(.*?)"""', src, re.DOTALL)
    if not match:
        return ""
    text = " ".join(match.group(1).strip().split())
    return text.split(". ")[0].rstrip(".")


def extract_inline_column_comments(src: str) -> dict[str, str]:
    comments: dict[str, str] = {}
    pending_group: str | None = None
    pending: str | None = None
    for line in src.splitlines():
        stripped = line.strip()
        if (
            stripped.startswith("#")
            and "db.Column" not in stripped
            and "db.relationship" not in stripped
            and not stripped.startswith("# FK")
            and not stripped.startswith("# ---")
            and stripped not in ("#",)
        ):
            text = stripped.lstrip("#").strip()
            if text.endswith(":"):
                pending_group = text.rstrip(":")
                pending = None
            else:
                pending = f"{pending_group}: {text}" if pending_group else text
            continue
        match = re.search(r"(\w+)\s*=\s*db\.Column\(", line)
        if match:
            if pending:
                comments[match.group(1)] = pending
            pending = None
            pending_group = None
        elif stripped and not stripped.startswith("#"):
            if not stripped.endswith(","):
                pending_group = None
                pending = None
    return comments


def extract_dict_label_maps(src: str) -> dict[str, str]:
    labels: dict[str, str] = {}
    for const_name in (
        "COLUMN_LABELS",
        "DISTRIBUTION_PARAMETER_FIELD_LABELS",
        "FUEL_PARAM_LABELS",
        "MAIN_PARAM_LABELS",
        "EXTRA_FUEL_PARAM_LABELS",
    ):
        match = re.search(rf"{const_name}\s*=\s*(\{{.*?\}})", src, re.DOTALL)
        if not match:
            continue
        try:
            parsed = ast.literal_eval(match.group(1))
        except (SyntaxError, ValueError):
            continue
        if isinstance(parsed, dict):
            labels.update({k: v for k, v in parsed.items() if isinstance(k, str) and isinstance(v, str)})
    for const_name in ("DISTRIBUTION_PARAMETER_LIST_COLUMN_HEADINGS", "FUEL_RESTRICTION_LIST_COLUMN_HEADINGS"):
        match = re.search(rf"{const_name}\s*:\s*list\[tuple\[str, str\]\]\s*=\s*(\[.*?\])", src, re.DOTALL)
        if not match:
            match = re.search(rf"{const_name}\s*=\s*(\[.*?\])", src, re.DOTALL)
        if not match:
            continue
        try:
            parsed = ast.literal_eval(match.group(1))
        except (SyntaxError, ValueError):
            continue
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, (list, tuple)) and len(item) == 2:
                    labels[str(item[0])] = str(item[1])
    return labels


def table_schema(table_name: str) -> str | None:
    for schema in SCHEMAS:
        if table_name.startswith(f"{schema}_"):
            return schema
    return None


def load_model_metadata() -> dict[str, dict]:
    """table_name -> {doc, inline_comments, dict_labels, file}"""
    result: dict[str, dict] = {}
    for base in MODEL_DIRS:
        for path in base.rglob("*_model.py"):
            src = path.read_text(encoding="utf-8")
            match = re.search(r'__tablename__\s*=\s*["\']([^"\']+)["\']', src)
            if not match:
                continue
            table = match.group(1)
            if table_schema(table) is None:
                continue
            inline = extract_inline_column_comments(src)
            dict_labels = extract_dict_label_maps(src)
            if table in result:
                inline = {**result[table]["inline"], **inline}
                dict_labels = {**result[table].get("dict_labels", {}), **dict_labels}
            result[table] = {
                "doc": first_docstring(src),
                "inline": inline,
                "dict_labels": dict_labels,
                "file": str(path),
            }
    return result


def load_runtime_fuel_labels() -> dict[str, str]:
    labels: dict[str, str] = {}
    try:
        from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
            FUEL_PARAM_LABELS,
            MAIN_PARAM_LABELS,
        )

        labels.update(FUEL_PARAM_LABELS)
        labels.update(MAIN_PARAM_LABELS)
    except Exception:
        pass
    try:
        from app.fuel.models.fue_distribution_parameter_model import (
            DISTRIBUTION_PARAMETER_FIELD_LABELS,
        )

        labels.update(DISTRIBUTION_PARAMETER_FIELD_LABELS)
    except Exception:
        pass
    try:
        from app.fuel.models.fue_equipment_group_specific_fuel_consumption_model import (
            EquipmentGroupSpecificFuelConsumption,
        )

        labels.update(EquipmentGroupSpecificFuelConsumption.COLUMN_LABELS)
    except Exception:
        pass
    try:
        from app.fuel.services.calculation.fuel_calculation_edit_data_services import (
            build_fuel_nazvl_to_name_map,
        )

        labels.update(build_fuel_nazvl_to_name_map())
    except Exception:
        pass
    return labels


def _is_placeholder_comment(column: str, comment: str) -> bool:
    col = column.lower().strip()
    txt = comment.lower().strip()
    if not txt or txt == col:
        return True
    if txt == col.replace("_", " "):
        return True
    if txt.replace(" ", "_") == col:
        return True
    if txt.replace(" ", "") == col.replace("_", ""):
        return True
    return False


def _resolve_base_label(column: str, labels: dict[str, str]) -> str | None:
    if column in labels and not _is_placeholder_comment(column, labels[column]):
        return labels[column]
    if column in _VALUE_COLUMNS:
        return _VALUE_COLUMNS[column]
    return None


def _fuel_label(column: str, labels: dict[str, str]) -> str | None:
    direct = _resolve_base_label(column, labels)
    if direct:
        return direct
    if column.endswith("_calc"):
        base_label = _resolve_base_label(column[:-5], labels)
        if base_label:
            return f"{base_label} (расчётное)"
    if column.endswith("_c"):
        base_label = _resolve_base_label(column[:-2], labels)
        if base_label:
            return f"Цена, {base_label}"
    return None


def column_comment(
    column: str,
    inline: dict[str, str],
    dict_labels: dict[str, str] | None = None,
    *,
    schema: str | None = None,
) -> str:
    for source in (inline, dict_labels or {}, _VALUE_COLUMNS, _RUNTIME_FUEL_LABELS, _FK_COLUMNS, _COMMON_COLUMNS):
        if column in source:
            comment = source[column]
            if column == "year_number" and comment.strip().upper() == "YEAR":
                return _COMMON_COLUMNS["year_number"]
            if not _is_placeholder_comment(column, comment):
                return comment

    if schema == "gs_fue":
        fuel_label = _fuel_label(column, _RUNTIME_FUEL_LABELS)
        if fuel_label:
            if column.endswith("_c"):
                return fuel_label
            if any(
                column in tbl.columns
                for tbl_name, tbl in {
                    t.name: t for t in db.metadata.tables.values() if t.schema == "gs_fue"
                }.items()
                if "specific_fuel_cost" in tbl_name or "extra_fuel" in tbl_name
            ):
                pass
            # Расход/стоимость по видам топлива
            if column.endswith("_calc"):
                return fuel_label
            if not column.endswith("_c"):
                for suffix, prefix in (("specific_fuel_cost", "Стоимость"), ("extra_fuel", "Расход топлива"), ("fuel_param", "Расход топлива")):
                    if any(t.name.endswith(suffix) or suffix in t.name for t in db.metadata.tables.values() if t.schema == "gs_fue" and column in t.columns):
                        return f"{prefix}, {fuel_label.removeprefix('Цена, ')}"

    if column in inline:
        return inline[column]
    if column in _COMMON_COLUMNS:
        return _COMMON_COLUMNS[column]
    if column in _FK_COLUMNS:
        return _FK_COLUMNS[column]
    if column in _VALUE_COLUMNS:
        return _VALUE_COLUMNS[column]
    if column.startswith("id_"):
        entity = column[3:].replace("_", " ")
        return f"Ссылка на {entity}"

    fuel_label = _fuel_label(column, _RUNTIME_FUEL_LABELS)
    if fuel_label:
        if column.endswith("_c"):
            return fuel_label
        return f"Расход топлива, {fuel_label}"

    return column.replace("_", " ")


def py_str(value: str) -> str:
    return repr(value)


def generate_migration(schema_comments: dict[str, dict[str, dict[str, str]]]) -> str:
    lines = [
        '# -*- coding: utf-8 -*-',
        '"""Комментарии к таблицам и полям схем gs_ec, gs_pd и gs_fue (по классам моделей).',
        '',
        f'Revision ID: {REVISION}',
        f'Revises: {DOWN_REVISION}',
        'Create Date: 2026-06-05',
        '"""',
        'import os',
        'import sys',
        '',
        'from alembic import op',
        'from sqlalchemy import text',
        '',
        '_MIGRATIONS = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))',
        'if _MIGRATIONS not in sys.path:',
        '    sys.path.insert(0, _MIGRATIONS)',
        'import column_utils  # noqa: E402',
        '',
        f'revision = "{REVISION}"',
        f'down_revision = "{DOWN_REVISION}"',
        'branch_labels = None',
        'depends_on = None',
        '',
        '_SCHEMA_COMMENTS: dict[str, dict[str, dict[str, str]]] = {',
    ]

    for schema in SCHEMAS:
        lines.append(f'    {py_str(schema)}: {{')
        for table in sorted(schema_comments[schema]):
            comments = schema_comments[schema][table]
            lines.append(f'        {py_str(table)}: {{')
            lines.append(f'            "_table": {py_str(comments["_table"])},')
            for column, comment in sorted(comments.items()):
                if column == "_table":
                    continue
                lines.append(f'            {py_str(column)}: {py_str(comment)},')
            lines.append('        },')
        lines.append('    },')

    lines.extend(
        [
            '}',
            '',
            '',
            'def _comment_on_table(conn, schema: str, table: str, comment: str | None) -> None:',
            '    if not column_utils.table_exists(conn, schema, table):',
            '        return',
            '    conn.execute(',
            '        text(f\'COMMENT ON TABLE "{schema}"."{table}" IS :comment\'),',
            '        {"comment": comment},',
            '    )',
            '',
            '',
            'def _comment_on_column(',
            '    conn, schema: str, table: str, column: str, comment: str | None',
            ') -> None:',
            '    if not column_utils.table_has_column(conn, schema, table, column):',
            '        return',
            '    conn.execute(',
            '        text(f\'COMMENT ON COLUMN "{schema}"."{table}"."{column}" IS :comment\'),',
            '        {"comment": comment},',
            '    )',
            '',
            '',
            'def _apply_comments(',
            '    conn, schema_comments: dict[str, dict[str, dict[str, str]]], clear: bool',
            ') -> None:',
            '    for schema, tables in schema_comments.items():',
            '        for table, comments in tables.items():',
            '            table_comment = None if clear else comments.get("_table")',
            '            _comment_on_table(conn, schema, table, table_comment)',
            '            for column, comment in comments.items():',
            '                if column == "_table":',
            '                    continue',
            '                column_comment = None if clear else comment',
            '                _comment_on_column(conn, schema, table, column, column_comment)',
            '',
            '',
            'def upgrade():',
            '    conn = op.get_bind()',
            '    _apply_comments(conn, _SCHEMA_COMMENTS, clear=False)',
            '',
            '',
            'def downgrade():',
            '    conn = op.get_bind()',
            '    _apply_comments(conn, _SCHEMA_COMMENTS, clear=True)',
            '',
        ]
    )
    return "\n".join(lines) + "\n"


def _table_prefix_comment(column: str, table_name: str, comment: str) -> str:
    if _is_placeholder_comment(column, comment):
        fuel_label = _fuel_label(column, _RUNTIME_FUEL_LABELS)
        if fuel_label:
            if "specific_fuel_price" in table_name:
                return fuel_label if column.endswith("_c") else f"Цена, {fuel_label.removeprefix('Цена, ')}"
            if "specific_fuel_cost" in table_name:
                return f"Стоимость, {fuel_label.removeprefix('Цена, ').removeprefix('Стоимость, ')}"
            if "extra_fuel" in table_name or table_name.endswith("_fuel_param"):
                return f"Расход топлива, {fuel_label.removeprefix('Цена, ')}"
    return comment


def main() -> None:
    global _RUNTIME_FUEL_LABELS
    model_meta = load_model_metadata()
    app = create_app()
    schema_comments: dict[str, dict[str, dict[str, str]]] = {s: {} for s in SCHEMAS}

    with app.app_context():
        _RUNTIME_FUEL_LABELS = load_runtime_fuel_labels()
        for table_obj in sorted(db.metadata.tables.values(), key=lambda t: (t.schema or "", t.name)):
            if table_obj.schema not in SCHEMAS:
                continue
            table = table_obj.name
            meta = model_meta.get(table, {"doc": table, "inline": {}, "dict_labels": {}})
            entry: dict[str, str] = {"_table": meta["doc"] or table}
            for column in table_obj.columns:
                raw = column_comment(
                    column.name,
                    meta["inline"],
                    meta.get("dict_labels"),
                    schema=table_obj.schema,
                )
                entry[column.name] = _table_prefix_comment(column.name, table, raw)
            schema_comments[table_obj.schema][table] = entry

    OUTPUT.write_text(generate_migration(schema_comments), encoding="utf-8")
    counts = {s: len(schema_comments[s]) for s in SCHEMAS}
    print(f"Written {OUTPUT} — tables: {counts}")

    bad = []
    for table, cols in schema_comments["gs_fue"].items():
        for col, comment in cols.items():
            if col == "_table":
                continue
            if _is_placeholder_comment(col, comment):
                bad.append(f"{table}.{col}")
    print(f"gs_fue placeholder comments remaining: {len(bad)}")
    if bad[:20]:
        print("examples:", ", ".join(bad[:20]))


if __name__ == "__main__":
    main()
