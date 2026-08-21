# -*- coding: utf-8 -*-
"""Страницы «Расчет балансов мощности» по макету БМ_ЕЭС.

Формулы строк взяты из БМ_ЕЭС_макет.xlsx. Входные ячейки пока пустые —
данные из других модулей будут сопоставлены строкам по ключу ``key``.
"""

from __future__ import annotations

import logging
import re
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlencode

from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
    get_energy_system_type_list_full,
)
from app.common.services.get_services.energy_systems.synchronous_area_get_services import (
    get_synchronous_area_list_full,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_list_full,
)
from app.common.services.get_services.years.years_get_services import (
    get_filter_end_year,
    get_filter_start_year,
    get_sipr_end_year,
    get_sipr_start_year,
    get_year_feature_dict,
    get_year_numbers_sorted_for_current_db_version,
)
from app.common.services.help_services import format_decimal_trim_for_display
from app.energy_balance.services.power_balance_demand_max_services import (
    load_power_balance_demand_max_inputs,
)
from app.energy_balance.services.power_balance_export_services import (
    EXPORT_ROW_KEY,
    load_power_balance_export_inputs,
)
from app.energy_balance.services.power_balance_installed_capacity_services import (
    get_power_balance_station_type_groups,
    installed_type_keys,
    load_power_balance_installed_capacity_inputs,
    resolve_sheet_territory,
)

logger = logging.getLogger(__name__)
_DYNAMIC_SHEET_SLUG_RE = re.compile(r"^(?:sz|oes|ees)-(\d+)$")

KIND_VALUE = "value"
KIND_TOTAL = "total"
KIND_CHILD = "child"
KIND_TRANSFER = "transfer"

CUSTOM_FLOW_IN = "flow_in"
CUSTOM_FLOW_OUT = "flow_out"
CUSTOM_FLOW_DIRECTIONS = (CUSTOM_FLOW_IN, CUSTOM_FLOW_OUT)
FLOW_BLOCK_KEYS = frozenset(
    {"flow_total", CUSTOM_FLOW_IN, CUSTOM_FLOW_OUT, "surplus_deficit_with_flow"}
)
# Старые фиксированные строки ОЭС Востока: теперь обычные пользовательские перетоки.
_LEGACY_CUSTOM_FLOW_PARENTS = {
    "flow_in_peleduy": CUSTOM_FLOW_IN,
    "flow_out_udokan": CUSTOM_FLOW_OUT,
    "flow_out_rzd": CUSTOM_FLOW_OUT,
}
VOSTOK_LAYOUT_SEED_PARENT = "__layout_seeded_oes_vostok__"
VOSTOK_DEFAULT_CUSTOM_FLOWS = (
    (
        CUSTOM_FLOW_IN,
        "питание ПС 220 кВ Пеледуй и НПС-10, Чаяндинский НГКМ, НПС-11 от ОЭС Сибири",
    ),
    (CUSTOM_FLOW_OUT, "питание Удоканского ГОКа"),
    (CUSTOM_FLOW_OUT, 'питание тяговых ПС АО "РЖД"'),
)
# Два уровня под «Получение/Передача»: группа (indent 2) и детализация (indent 3).
MAX_CUSTOM_FLOW_INDENT = 3

POWER_BALANCE_ROUNDING_DIGITS = 1
POWER_BALANCE_ROUNDING_CHOICES = (-1, 0, 1, 2, 3)
# Единица измерения всех строк таблиц БМ (заголовок макета: «Баланс мощности …, МВт»).
POWER_BALANCE_UNIT = "МВт"

# Останов крупнейшего агрегата на листе «Калининградская СЗ ЕЭС» (константа макета).
KALININGRAD_LARGEST_UNIT_MW = Decimal("225")

# Составляющие ЕЭС России (R8…R15 макета).
EES_SOURCE_SLUGS = (
    "severo-zapad",
    "centr",
    "srednyaya-volga",
    "yug",
    "ural",
    "sibir",
    "2-sz-ees-vostok",
)
# 1-я СЗ ЕЭС = ОЭС 1-й зоны минус Калининград.
SZ1_ADD_SLUGS = (
    "severo-zapad",
    "centr",
    "srednyaya-volga",
    "yug",
    "ural",
    "sibir",
)
SZ1_SUB_SLUGS = ("kaliningradskaya-sz-ees",)

GROUP_EES = "ees"
GROUP_SZ = "sz"
GROUP_OES = "oes"
SHEET_GROUP_ORDER = (GROUP_EES, GROUP_SZ, GROUP_OES)

# Запасной каталог, если справочники версии БД недоступны. Порядок: ЕЭС → СЗ → ОЭС.
POWER_BALANCE_SHEETS: tuple[dict[str, Any], ...] = (
    {
        "slug": "ees-rossii",
        "sheet_name": "ЕЭС России",
        "group": GROUP_EES,
        "title": "Баланс мощности ЕЭС России",
        "layout": "ees_rossii",
        "skip_direct_capacity": True,
    },
    {
        "slug": "1-sz-ees",
        "sheet_name": "1-я СЗ ЕЭС",
        "group": GROUP_SZ,
        "title": "Баланс мощности 1-я СЗ ЕЭС",
        "layout": "sz1",
        "skip_direct_capacity": True,
    },
    {
        "slug": "2-sz-ees-vostok",
        "sheet_name": "2-я СЗ ЕЭС (ОЭС Востока)",
        "group": GROUP_SZ,
        "title": "Баланс мощности 2-я СЗ ЕЭС (ОЭС Востока)",
        "layout": "oes_vostok",
    },
    {
        "slug": "kaliningradskaya-sz-ees",
        "sheet_name": "Калининградская СЗ ЕЭС",
        "group": GROUP_SZ,
        "title": "Баланс мощности Калининградская СЗ ЕЭС",
        "layout": "kaliningrad",
    },
    {
        "slug": "severo-zapad",
        "sheet_name": "Северо-Запад",
        "group": GROUP_OES,
        "title": "Баланс мощности Северо-Запад",
        "layout": "oes_standard",
        "is_ees_member": True,
    },
    {
        "slug": "centr",
        "sheet_name": "Центр",
        "group": GROUP_OES,
        "title": "Баланс мощности Центр",
        "layout": "oes_standard",
        "is_ees_member": True,
    },
    {
        "slug": "srednyaya-volga",
        "sheet_name": "Средняя Волга",
        "group": GROUP_OES,
        "title": "Баланс мощности Средняя Волга",
        "layout": "oes_standard",
        "is_ees_member": True,
    },
    {
        "slug": "yug",
        "sheet_name": "Юг",
        "group": GROUP_OES,
        "title": "Баланс мощности Юг",
        "layout": "oes_yug",
        "is_ees_member": True,
    },
    {
        "slug": "ural",
        "sheet_name": "Урал",
        "group": GROUP_OES,
        "title": "Баланс мощности Урал",
        "layout": "oes_standard",
        "is_ees_member": True,
    },
    {
        "slug": "sibir",
        "sheet_name": "Сибирь",
        "group": GROUP_OES,
        "title": "Баланс мощности Сибирь",
        "layout": "oes_sibir",
        "is_ees_member": True,
    },
)


def _norm_label(text: str | None) -> str:
    return (
        (text or "")
        .casefold()
        .replace("ё", "е")
        .replace("-", " ")
        .replace("  ", " ")
        .strip()
    )


def _is_unspecified_ref(obj: Any) -> bool:
    obj_id = getattr(obj, "id", None)
    try:
        if obj_id is None or int(obj_id) <= 0:
            return True
    except (TypeError, ValueError):
        return True
    name = _norm_label(getattr(obj, "name", None))
    return (not name) or ("не указано" in name)


def _is_ees_type_name(name: str | None) -> bool:
    n = _norm_label(name)
    return "еэс" in n and "не указано" not in n


def _is_non_ees_system_name(name: str | None) -> bool:
    n = _norm_label(name).replace("э", "е")
    return "титес" in n or "децентрализ" in n


def _is_new_territories_name(name: str | None) -> bool:
    return "новые территор" in _norm_label(name)


def _is_oes_vostok_name(name: str | None) -> bool:
    """ОЭС Востока, без ТИТЭС Востока и децентрализованных зон."""
    n = _norm_label(name)
    return "восток" in n and not _is_non_ees_system_name(name)


def _oes_layout_and_slug(name: str, obj_id: int) -> tuple[str, str]:
    n = _norm_label(name)
    if _is_non_ees_system_name(name):
        return "oes_standard", f"oes-{int(obj_id)}"
    if "юг" in n:
        return "oes_yug", "yug"
    if "сибир" in n:
        return "oes_sibir", "sibir"
    if "восток" in n:
        return "oes_vostok", "vostok"
    if "северо" in n and "запад" in n:
        return "oes_standard", "severo-zapad"
    if "центр" in n and "северо" not in n:
        return "oes_standard", "centr"
    if "волг" in n:
        return "oes_standard", "srednyaya-volga"
    if "урал" in n:
        return "oes_standard", "ural"
    return "oes_standard", f"oes-{int(obj_id)}"


def _sz_haystack(name: str | None, name_full: str | None = None, number: str | None = None) -> str:
    return _norm_label(" ".join(str(part) for part in (name, name_full, number) if part))


def _compact_label(text: str) -> str:
    return text.replace(" ", "")


def _sz_layout_and_slug(
    name: str,
    obj_id: int,
    *,
    name_full: str | None = None,
    number: str | None = None,
) -> tuple[str, str]:
    """Макет листа СЗ по наименованию / полному имени / номеру — не только с начала строки."""
    n = _sz_haystack(name, name_full, number)
    compact = _compact_label(n)
    num = _norm_label(number)

    if "калининград" in n:
        return "kaliningrad", "kaliningradskaya-sz-ees"

    named_second = (
        "втор" in n
        or compact.startswith("2я")
        or compact.startswith("2ая")
        or n.startswith("2 я")
        or n.startswith("2 ая")
        or "2 я сз" in n
        or "2 ая сз" in n
        or "2 я синхрон" in n
        or "2 ая синхрон" in n
    )
    named_first = (
        "перв" in n
        or compact.startswith("1я")
        or compact.startswith("1ая")
        or n.startswith("1 я")
        or n.startswith("1 ая")
        or "1 я сз" in n
        or "1 ая сз" in n
        or "1 я синхрон" in n
        or "1 ая синхрон" in n
    )
    if named_second:
        return "oes_vostok", "2-sz-ees-vostok"
    if named_first:
        return "sz1", "1-sz-ees"
    if num in {"2", "ii"}:
        return "oes_vostok", "2-sz-ees-vostok"
    if num in {"1", "i"}:
        return "sz1", "1-sz-ees"
    return "oes_standard", f"sz-{int(obj_id)}"


def _make_sheet(
    *,
    slug: str,
    sheet_name: str,
    group: str,
    layout: str,
    title: str | None = None,
    source_slugs: tuple[str, ...] = (),
    subtract_slugs: tuple[str, ...] = (),
    territory: dict[str, Any] | None = None,
    is_ees_member: bool = False,
    skip_direct_capacity: bool = False,
) -> dict[str, Any]:
    return {
        "slug": slug,
        "sheet_name": sheet_name,
        "group": group,
        "layout": layout,
        "title": title or f"Баланс мощности {sheet_name}",
        "source_slugs": tuple(source_slugs),
        "subtract_slugs": tuple(subtract_slugs),
        "territory": territory,
        "is_ees_member": is_ees_member,
        "skip_direct_capacity": skip_direct_capacity,
        "table_number": 0,
    }


def _ensure_unique_slugs(sheets: list[dict[str, Any]]) -> None:
    seen: set[str] = set()
    for sheet in sheets:
        slug = str(sheet.get("slug") or "").strip() or "sheet"
        if slug in seen:
            extra = (sheet.get("territory") or {}).get("id")
            slug = f"{slug}-{extra}" if extra is not None else f"{slug}-{len(seen) + 1}"
            sheet["slug"] = slug
        seen.add(sheet["slug"])


def _apply_cross_sheet_sources(sheets: list[dict[str, Any]]) -> None:
    oes_ees = [
        sheet["slug"]
        for sheet in sheets
        if sheet.get("group") == GROUP_OES and sheet.get("is_ees_member")
    ]
    has_vostok_oes = any(
        _is_oes_vostok_name(sheet.get("sheet_name"))
        for sheet in sheets
        if sheet.get("group") == GROUP_OES
    )
    if not has_vostok_oes:
        for sheet in sheets:
            if sheet.get("group") == GROUP_SZ and sheet.get("layout") == "oes_vostok":
                oes_ees.append(sheet["slug"])
                break
    sz1_add = [
        sheet["slug"]
        for sheet in sheets
        if sheet.get("group") == GROUP_OES
        and sheet.get("is_ees_member")
        and not _is_oes_vostok_name(sheet.get("sheet_name"))
    ]
    kal_slug = next(
        (sheet["slug"] for sheet in sheets if sheet.get("layout") == "kaliningrad"),
        None,
    )
    for sheet in sheets:
        if sheet.get("layout") == "ees_rossii":
            sheet["source_slugs"] = tuple(oes_ees or EES_SOURCE_SLUGS)
            sheet["skip_direct_capacity"] = True
        elif sheet.get("layout") == "sz1":
            sheet["source_slugs"] = tuple(sz1_add or SZ1_ADD_SLUGS)
            sheet["subtract_slugs"] = (kal_slug,) if kal_slug else tuple(SZ1_SUB_SLUGS)
            sheet["skip_direct_capacity"] = True


def _finalize_sheets(sheets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {group: [] for group in SHEET_GROUP_ORDER}
    for sheet in sheets:
        group = sheet.get("group") if sheet.get("group") in grouped else GROUP_OES
        grouped[group].append(dict(sheet))
    ordered = [sheet for group in SHEET_GROUP_ORDER for sheet in grouped[group]]
    _ensure_unique_slugs(ordered)
    _apply_cross_sheet_sources(ordered)
    for index, sheet in enumerate(ordered, start=1):
        sheet["table_number"] = index
        sheet["title"] = f"Баланс мощности {sheet['sheet_name']}"
    return ordered


def _ref_view(item: Any) -> Any | None:
    """Снимок полей справочника: не держим ORM после закрытия сессии."""
    try:
        obj_id = getattr(item, "id", None)
        if obj_id is None or int(obj_id) <= 0:
            return None
        name = getattr(item, "name", None)
        view = SimpleNamespace(
            id=int(obj_id),
            name=name,
            name_full=getattr(item, "name_full", None),
            number=getattr(item, "number", None),
            id_energy_system_type=getattr(item, "id_energy_system_type", None),
        )
        if _is_unspecified_ref(view):
            return None
        return view
    except Exception:
        logger.warning("Не удалось прочитать запись справочника для листов баланса мощности", exc_info=True)
        return None


def _sheets_from_refdata() -> list[dict[str, Any]] | None:
    try:
        est_raw = list(get_energy_system_type_list_full() or [])
        ues_raw = list(get_union_energy_system_list_full() or [])
        sa_raw = list(get_synchronous_area_list_full() or [])
    except Exception:
        logger.warning("Не удалось загрузить справочники для листов баланса мощности", exc_info=True)
        return None
    est_list = [view for item in est_raw if (view := _ref_view(item))]
    ues_list = [view for item in ues_raw if (view := _ref_view(item))]
    sa_list = [view for item in sa_raw if (view := _ref_view(item))]
    if not est_list and not ues_list and not sa_list:
        return None

    est_by_id = {int(item.id): item for item in est_list}
    sheets: list[dict[str, Any]] = []
    ees_types = [
        item
        for item in est_list
        if _is_ees_type_name(item.name) and not _is_non_ees_system_name(item.name)
    ]
    if ees_types:
        for est in ees_types:
            est_name = str(est.name).strip()
            est_norm = _norm_label(est_name)
            slug = "ees-rossii"
            if len(ees_types) > 1 and not ("росси" in est_norm):
                slug = f"ees-{int(est.id)}"
            sheets.append(
                _make_sheet(
                    slug=slug,
                    sheet_name=est_name,
                    group=GROUP_EES,
                    layout="ees_rossii",
                    territory={"kind": "est", "id": int(est.id), "name": est_name},
                    skip_direct_capacity=True,
                )
            )
    else:
        sheets.append(
            _make_sheet(
                slug="ees-rossii",
                sheet_name="ЕЭС России",
                group=GROUP_EES,
                layout="ees_rossii",
                skip_direct_capacity=True,
            )
        )

    for area in sa_list:
        name = str(area.name).strip()
        layout, slug = _sz_layout_and_slug(
            name,
            int(area.id),
            name_full=getattr(area, "name_full", None),
            number=getattr(area, "number", None),
        )
        sheets.append(
            _make_sheet(
                slug=slug,
                sheet_name=name,
                group=GROUP_SZ,
                layout=layout,
                territory={"kind": "sa", "id": int(area.id), "name": name},
                skip_direct_capacity=(layout == "sz1"),
            )
        )

    for ues in ues_list:
        name = str(ues.name).strip()
        if _is_new_territories_name(name) or _is_oes_vostok_name(name):
            continue
        layout, slug = _oes_layout_and_slug(name, int(ues.id))
        est = est_by_id.get(int(getattr(ues, "id_energy_system_type", 0) or 0))
        if est is not None:
            is_ees_member = _is_ees_type_name(est.name) and not _is_non_ees_system_name(est.name)
        else:
            is_ees_member = not _is_non_ees_system_name(name)
        sheets.append(
            _make_sheet(
                slug=slug,
                sheet_name=name,
                group=GROUP_OES,
                layout=layout,
                territory={"kind": "ues", "id": int(ues.id), "name": name},
                is_ees_member=is_ees_member,
            )
        )
    return sheets


def _row_css_class(kind: str) -> str:
    classes: list[str] = []
    if kind == KIND_TOTAL:
        classes.append("table-info")
    elif kind == KIND_TRANSFER:
        classes.append("table-warning")
    return " ".join(classes)


def _sum_formula(*row_keys: str) -> dict[str, Any]:
    return {"terms": [{"row_key": key} for key in row_keys]}


def _diff_formula(left_key: str, *subtract_keys: str, const: Decimal | int | None = None) -> dict[str, Any]:
    terms: list[dict[str, Any]] = [{"row_key": left_key}]
    for key in subtract_keys:
        terms.append({"row_key": key, "coeff": -1})
    if const is not None:
        terms.append({"const": const})
    return {"terms": terms}


def _sheet_sum_formula(
    row_key: str,
    slugs: tuple[str, ...] | list[str],
    subtract_slugs: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    terms: list[dict[str, Any]] = [{"slug": slug, "row_key": row_key} for slug in slugs]
    for slug in subtract_slugs:
        terms.append({"slug": slug, "row_key": row_key, "coeff": -1})
    return {"terms": terms}


def _row(
    key: str,
    label: str,
    *,
    indent: int = 0,
    kind: str = KIND_VALUE,
    italic: bool = False,
    formula: dict[str, Any] | None = None,
    unit: str = POWER_BALANCE_UNIT,
    editable_values: bool = False,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "unit": unit,
        "indent": indent,
        "kind": kind,
        "italic": italic,
        "css_class": _row_css_class(kind),
        "formula": formula,
        "formula_tooltip": "",
        "formula_client": None,
        "formula_ext_raw": {},
        "year_values": {},
        "year_values_raw": {},
        "is_custom": False,
        "can_add_custom_flow": False,
        "editable_label": False,
        "editable_values": editable_values,
        "is_flow_block": kind == KIND_TRANSFER or key in FLOW_BLOCK_KEYS,
    }


def is_power_balance_flow_block_row(row: dict[str, Any]) -> bool:
    """Строки перетока и дефицита с учётом перетока — скрываются кнопкой «+Перетоки»."""
    if row.get("is_flow_block"):
        return True
    key = str(row.get("key") or "")
    if key in FLOW_BLOCK_KEYS:
        return True
    if row.get("is_custom") or row.get("flow_section"):
        return True
    return row.get("kind") == KIND_TRANSFER


def custom_flow_row_key(direction: str, row_id: int) -> str:
    return f"{direction}_custom_{int(row_id)}"


def parse_custom_flow_row_id(row_key: str) -> int | None:
    text = str(row_key or "")
    for direction in CUSTOM_FLOW_DIRECTIONS:
        prefix = f"{direction}_custom_"
        if text.startswith(prefix):
            try:
                return int(text[len(prefix) :])
            except (TypeError, ValueError):
                return None
    return None


def aggregated_custom_flow_key(source_slug: str, origin_key: str) -> str:
    return f"{source_slug}__{origin_key}"


def resolve_custom_flow_parent_key(parent_key: str | None, direction: str) -> str:
    key = str(parent_key or direction or "").strip() or str(direction or "")
    return _LEGACY_CUSTOM_FLOW_PARENTS.get(key, key)


def _section_insert_index(rows: list[dict[str, Any]], parent_key: str) -> int | None:
    parent_idx = next((i for i, row in enumerate(rows) if row.get("key") == parent_key), None)
    if parent_idx is None:
        return None
    parent_indent = int(rows[parent_idx].get("indent") or 0)
    end = parent_idx + 1
    while end < len(rows) and int(rows[end].get("indent") or 0) > parent_indent:
        end += 1
    return end


def _append_formula_terms(row: dict[str, Any], extra_keys: list[str]) -> None:
    if not extra_keys:
        return
    formula = dict(row.get("formula") or {})
    terms = list(formula.get("terms") or [])
    existing = {
        str(term.get("row_key"))
        for term in terms
        if term.get("row_key") and not term.get("slug")
    }
    for key in extra_keys:
        if key not in existing:
            terms.append({"row_key": key})
    row["formula"] = {"terms": terms}


def _custom_flow_nesting_depth(item: dict[str, Any], by_id: dict[int, dict[str, Any]]) -> int:
    depth = 0
    seen: set[int] = set()
    current: dict[str, Any] | None = item
    while current is not None:
        parent_key = str(current.get("parent_key") or current.get("direction") or "")
        parent_id = parse_custom_flow_row_id(parent_key)
        if parent_id is None and "__" in parent_key:
            parent_id = parse_custom_flow_row_id(parent_key.rpartition("__")[2])
        if parent_id is None or parent_id in seen:
            break
        parent_item = by_id.get(parent_id)
        if parent_item is None:
            break
        seen.add(parent_id)
        depth += 1
        current = parent_item
        if depth > 5:
            break
    return depth


def _mark_custom_flow_add_targets(rows: list[dict[str, Any]]) -> None:
    current_section: str | None = None
    for row in rows:
        key = str(row.get("key") or "")
        indent = int(row.get("indent") or 0)
        if key in CUSTOM_FLOW_DIRECTIONS:
            current_section = key
            row["flow_section"] = key
            row["can_add_custom_flow"] = True
            continue
        if current_section is not None and indent > 1:
            row["flow_section"] = current_section
            row["can_add_custom_flow"] = bool(row.get("is_custom")) and indent == 2
        else:
            current_section = None
            if not row.get("can_add_custom_flow"):
                row["can_add_custom_flow"] = False


def inject_custom_flow_rows(
    rows: list[dict[str, Any]],
    custom_rows: list[dict[str, Any]] | None,
) -> dict[str, dict[int, Any]]:
    """Вставляет пользовательские строки под родителя и расширяет формулы итогов.

    Два уровня: группа (indent 2) суммируется в Получение/Передачу,
    детализация (indent 3) суммируется в группу.
    """
    inputs: dict[str, dict[int, Any]] = {}
    items = [item for item in (custom_rows or []) if item.get("id") is not None]
    by_id = {int(item["id"]): item for item in items}
    items.sort(
        key=lambda item: (
            _custom_flow_nesting_depth(item, by_id),
            int(item.get("sort_order") or 0),
            int(item.get("id") or 0),
        )
    )
    for item in items:
        direction = str(item.get("direction") or "")
        if direction not in CUSTOM_FLOW_DIRECTIONS:
            continue
        if str(item.get("parent_key") or "") == VOSTOK_LAYOUT_SEED_PARENT:
            continue
        parent_key = resolve_custom_flow_parent_key(
            str(item.get("parent_key") or direction).strip() or direction,
            direction,
        )
        insert_at = _section_insert_index(rows, parent_key)
        if insert_at is None:
            continue
        parent = next(row for row in rows if row.get("key") == parent_key)
        child_indent = int(parent.get("indent") or 0) + 1
        if child_indent > MAX_CUSTOM_FLOW_INDENT:
            continue
        row_id = int(item["id"])
        key = str(item.get("key") or custom_flow_row_key(direction, row_id))
        year_map = item.get("values") or item.get("year_values") or {}
        inputs[key] = {int(year): value for year, value in year_map.items()}
        built = _row(
            key,
            str(item.get("label") or ""),
            indent=child_indent,
            kind=KIND_TRANSFER,
            italic=child_indent >= 3,
        )
        built["is_custom"] = True
        built["custom_id"] = row_id
        built["custom_direction"] = direction
        built["custom_parent_key"] = parent_key
        built["flow_section"] = direction
        built["editable_label"] = True
        built["editable_values"] = True
        built["can_add_custom_flow"] = child_indent == 2
        if item.get("source_slug"):
            built["custom_origin_slug"] = str(item.get("source_slug") or "")
            built["custom_origin_key"] = str(item.get("origin_key") or key)
            built["origin_sheet_name"] = str(item.get("origin_sheet_name") or "")
        rows.insert(insert_at, built)
        _append_formula_terms(parent, [key])
        if parent.get("is_custom"):
            parent["editable_values"] = False
    for row in rows:
        if row.get("is_custom") and row.get("formula"):
            row["editable_values"] = False
    _mark_custom_flow_add_targets(rows)
    return inputs


def apply_custom_flows_to_tables(
    tables: dict[str, dict[str, Any]],
    custom_by_slug: dict[str, list[dict[str, Any]]] | None,
) -> dict[str, dict[str, dict[int, Any]]]:
    extra_inputs: dict[str, dict[str, dict[int, Any]]] = {}
    custom_by_slug = custom_by_slug or {}
    sheets_by_slug = {slug: (payload.get("sheet") or {}) for slug, payload in tables.items()}
    for slug, payload in tables.items():
        extra = inject_custom_flow_rows(payload["rows"], custom_by_slug.get(slug) or [])
        sheet = payload.get("sheet") or {}
        if sheet.get("layout") in {"sz1", "ees_rossii"}:
            extra.update(
                inject_aggregated_source_flows(
                    payload["rows"],
                    custom_by_slug,
                    tuple(sheet.get("source_slugs") or ()),
                    subtract_slugs=tuple(sheet.get("subtract_slugs") or ()),
                    sheets_by_slug=sheets_by_slug,
                    skip_slug=slug,
                )
            )
        if extra:
            extra_inputs[slug] = extra
    return extra_inputs


def inject_aggregated_source_flows(
    rows: list[dict[str, Any]],
    custom_by_slug: dict[str, list[dict[str, Any]]],
    source_slugs: tuple[str, ...] | list[str],
    *,
    subtract_slugs: tuple[str, ...] | list[str] = (),
    sheets_by_slug: dict[str, dict[str, Any]] | None = None,
    skip_slug: str | None = None,
) -> dict[str, dict[int, Any]]:
    """Копирует пользовательские перетоки входящих ОЭС на накопительный лист."""
    inputs: dict[str, dict[int, Any]] = {}
    sheets_by_slug = sheets_by_slug or {}
    skip = {str(item) for item in subtract_slugs if item}
    if skip_slug:
        skip.add(str(skip_slug))
    for source_slug in source_slugs:
        source_slug = str(source_slug or "").strip()
        if not source_slug or source_slug in skip:
            continue
        source_items = [
            item
            for item in (custom_by_slug.get(source_slug) or [])
            if item.get("id") is not None
            and str(item.get("parent_key") or "") != VOSTOK_LAYOUT_SEED_PARENT
        ]
        if not source_items:
            continue
        sheet_name = str(
            (sheets_by_slug.get(source_slug) or {}).get("sheet_name") or source_slug
        )
        remapped: list[dict[str, Any]] = []
        for item in source_items:
            direction = str(item.get("direction") or "")
            if direction not in CUSTOM_FLOW_DIRECTIONS:
                continue
            origin_key = str(
                item.get("key") or custom_flow_row_key(direction, int(item["id"]))
            )
            parent = resolve_custom_flow_parent_key(
                str(item.get("parent_key") or direction).strip() or direction,
                direction,
            )
            if parent not in CUSTOM_FLOW_DIRECTIONS:
                parent = aggregated_custom_flow_key(source_slug, parent)
            remapped.append(
                {
                    **item,
                    "key": aggregated_custom_flow_key(source_slug, origin_key),
                    "parent_key": parent,
                    "source_slug": source_slug,
                    "origin_key": origin_key,
                    "origin_sheet_name": sheet_name,
                }
            )
        inputs.update(inject_custom_flow_rows(rows, remapped))
    return inputs


def load_power_balance_custom_flows(
    sheets: list[dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    try:
        from app.energy_balance.services.power_balance_custom_flow_services import (
            load_power_balance_custom_flows as _load,
        )

        return _load(sheets=sheets)
    except Exception:
        return {}


def _jsonable_formula(formula: dict[str, Any] | None) -> dict[str, Any] | None:
    if not formula:
        return None
    terms: list[dict[str, Any]] = []
    for term in formula.get("terms") or []:
        item: dict[str, Any] = {}
        if term.get("row_key"):
            item["row_key"] = term["row_key"]
        if term.get("slug"):
            item["slug"] = term["slug"]
        if "coeff" in term:
            coeff = term.get("coeff")
            try:
                item["coeff"] = int(coeff)
            except (TypeError, ValueError):
                item["coeff"] = str(coeff)
        if "const" in term:
            item["const"] = format(_to_decimal(term["const"]), "f")
        terms.append(item)
    if not terms:
        return None
    return {"terms": terms}


def _installed_capacity_rows(*, type_formula_builder=None) -> list[dict[str, Any]]:
    type_groups = get_power_balance_station_type_groups()
    type_keys = installed_type_keys(type_groups)
    rows = [
        _row(
            "installed_total",
            "Установленная мощность",
            kind=KIND_TOTAL,
            formula=_sum_formula(*type_keys) if type_keys else None,
        ),
    ]
    for group in type_groups:
        formula = type_formula_builder(group["key"]) if type_formula_builder is not None else None
        rows.append(
            _row(
                group["key"],
                group["label"],
                indent=1,
                kind=KIND_CHILD,
                formula=formula,
            )
        )
    return rows


def _demand_and_coverage_rows(
    *,
    surplus_deficit_label: str | None = None,
    surplus_const: Decimal | int | None = None,
    source_slugs: tuple[str, ...] | None = None,
    subtract_slugs: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    def _agg(row_key: str) -> dict[str, Any] | None:
        if not source_slugs:
            return None
        return _sheet_sum_formula(row_key, source_slugs, subtract_slugs)

    return [
        _row("demand_max", "Максимум потребления мощности"),
        _row(EXPORT_ROW_KEY, "Экспорт мощности", editable_values=True),
        _row(
            "demand_total",
            "Итого потребность в мощности",
            kind=KIND_TOTAL,
            formula=_sum_formula("demand_max", EXPORT_ROW_KEY),
        ),
        *_installed_capacity_rows(type_formula_builder=_agg if source_slugs else None),
        _row("constraints", "Ограничения мощности", formula=_agg("constraints")),
        _row(
            "commissioning_after_max",
            "Вводы мощности после прохождения максимума",
            formula=_agg("commissioning_after_max"),
        ),
        _row(
            "coverage_total",
            "Итого покрытие потребности",
            kind=KIND_TOTAL,
            formula=_diff_formula("installed_total", "constraints", "commissioning_after_max"),
        ),
        _row(
            "surplus_deficit",
            surplus_deficit_label or "Дефицит (-)/избыток (+)",
            kind=KIND_TOTAL,
            formula=_diff_formula("coverage_total", "demand_total", const=surplus_const),
        ),
    ]


def _transfer_header(*, formula: dict[str, Any] | None = None) -> dict[str, Any]:
    return _row(
        "flow_total",
        "Переток мощности в смежные энергосистемы выдача (-)/прием (+)",
        kind=KIND_TOTAL,
        formula=formula,
    )


def _final_surplus_row(
    key: str = "surplus_deficit_with_flow",
    label: str | None = None,
    *,
    formula: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _row(
        key,
        label
        or "Дефицит (-)/избыток (+) с учетом перетока мощности в смежные энергосистемы",
        kind=KIND_TOTAL,
        formula=formula or _sum_formula("surplus_deficit", "flow_total"),
    )


def _rows_oes_standard() -> list[dict[str, Any]]:
    return [
        *_demand_and_coverage_rows(),
        _transfer_header(formula=_sum_formula("flow_in", "flow_out")),
        _row("flow_in", "Получение мощности (+)", indent=1, kind=KIND_TRANSFER),
        _row("flow_out", "Передача мощности (-)", indent=1, kind=KIND_TRANSFER),
        _final_surplus_row(),
    ]


def _rows_oes_yug() -> list[dict[str, Any]]:
    return _rows_oes_standard()


def _rows_oes_sibir() -> list[dict[str, Any]]:
    return _rows_oes_standard()


def _rows_oes_vostok() -> list[dict[str, Any]]:
    return _rows_oes_standard()


def _rows_ees_rossii(
    source_slugs: tuple[str, ...] | list[str] | None = None,
) -> list[dict[str, Any]]:
    slugs = tuple(source_slugs or EES_SOURCE_SLUGS)
    return [
        *_demand_and_coverage_rows(source_slugs=slugs),
        _transfer_header(formula=_sum_formula("flow_in", "flow_out")),
        _row("flow_in", "Получение мощности (+)", indent=1, kind=KIND_TRANSFER),
        _row("flow_out", "Передача мощности (-)", indent=1, kind=KIND_TRANSFER),
        _final_surplus_row(),
    ]


def _rows_sz1(
    source_slugs: tuple[str, ...] | list[str] | None = None,
    subtract_slugs: tuple[str, ...] | list[str] | None = None,
) -> list[dict[str, Any]]:
    add_slugs = tuple(source_slugs or SZ1_ADD_SLUGS)
    sub_slugs = tuple(SZ1_SUB_SLUGS if subtract_slugs is None else subtract_slugs)
    return [
        *_demand_and_coverage_rows(source_slugs=add_slugs, subtract_slugs=sub_slugs),
        _transfer_header(formula=_sum_formula("flow_in", "flow_out")),
        _row("flow_in", "Получение мощности (+)", indent=1, kind=KIND_TRANSFER),
        _row("flow_out", "Передача мощности (-)", indent=1, kind=KIND_TRANSFER),
        _final_surplus_row(),
    ]


def _rows_kaliningrad() -> list[dict[str, Any]]:
    return [
        *_demand_and_coverage_rows(
            surplus_deficit_label=(
                "Дефицит (-)/избыток (+) с учетом останова 1-й единицы "
                "генерирующего оборудования с наибольшей располагаемой мощностью"
            ),
            surplus_const=-KALININGRAD_LARGEST_UNIT_MW,
        ),
        _row(
            "flow_total",
            "Переток мощности в смежные энергосистемы выдача (-)/прием (+)",
            kind=KIND_TRANSFER,
            formula=_sum_formula("flow_in", "flow_out"),
        ),
        _row("flow_in", "Получение мощности (+)", indent=1, kind=KIND_TRANSFER),
        _row("flow_out", "Передача мощности (-)", indent=1, kind=KIND_TRANSFER),
        _final_surplus_row(
            key="surplus_deficit_second_unit",
            label=(
                "Дефицит (-)/избыток (+) с учетом останова 2-й единицы "
                "генерирующего оборудования с наибольшей располагаемой мощностью"
            ),
            formula=_diff_formula("surplus_deficit", const=-KALININGRAD_LARGEST_UNIT_MW),
        ),
    ]


_LAYOUT_BUILDERS = {
    "oes_standard": _rows_oes_standard,
    "oes_yug": _rows_oes_yug,
    "oes_sibir": _rows_oes_sibir,
    "oes_vostok": _rows_oes_vostok,
    "ees_rossii": _rows_ees_rossii,
    "sz1": _rows_sz1,
    "kaliningrad": _rows_kaliningrad,
}


def get_power_balance_sheets() -> list[dict[str, Any]]:
    built = _sheets_from_refdata()
    if built:
        return _finalize_sheets(built)
    return _finalize_sheets([dict(sheet) for sheet in POWER_BALANCE_SHEETS])


def is_persistable_power_balance_slug(slug: str) -> bool:
    """Slug, в который можно писать ручной ввод, даже если каталог временно запасной."""
    text = str(slug or "").strip()
    if not text:
        return False
    if any(str(item.get("slug") or "") == text for item in POWER_BALANCE_SHEETS):
        return True
    return _DYNAMIC_SHEET_SLUG_RE.fullmatch(text) is not None


def _ref_by_id(loader, obj_id: int) -> Any | None:
    try:
        items = list(loader() or [])
    except Exception:
        return None
    for item in items:
        view = _ref_view(item)
        if view is not None and int(view.id) == int(obj_id):
            return view
    return None


def _synthetic_sheet_for_slug(slug: str) -> dict[str, Any] | None:
    """Лист ``sz-112`` / ``oes-N`` по id, если запасной каталог его не содержит."""
    text = str(slug or "").strip()
    match = _DYNAMIC_SHEET_SLUG_RE.fullmatch(text)
    if match is None:
        return None
    obj_id = int(match.group(1))
    kind = text.split("-", 1)[0]
    if kind == "sz":
        area = _ref_by_id(get_synchronous_area_list_full, obj_id)
        if area is None:
            return None
        name = str(area.name or "").strip() or text
        layout, _canonical = _sz_layout_and_slug(
            name,
            obj_id,
            name_full=getattr(area, "name_full", None),
            number=getattr(area, "number", None),
        )
        sheet = _make_sheet(
            slug=text,
            sheet_name=name,
            group=GROUP_SZ,
            layout=layout,
            territory={"kind": "sa", "id": obj_id, "name": name},
            skip_direct_capacity=(layout == "sz1"),
        )
    elif kind == "oes":
        ues = _ref_by_id(get_union_energy_system_list_full, obj_id)
        if ues is None:
            return None
        name = str(ues.name or "").strip() or text
        layout, _canonical = _oes_layout_and_slug(name, obj_id)
        sheet = _make_sheet(
            slug=text,
            sheet_name=name,
            group=GROUP_OES,
            layout=layout,
            territory={"kind": "ues", "id": obj_id, "name": name},
        )
    else:
        est = _ref_by_id(get_energy_system_type_list_full, obj_id)
        if est is None:
            return None
        name = str(est.name or "").strip() or text
        sheet = _make_sheet(
            slug=text,
            sheet_name=name,
            group=GROUP_EES,
            layout="ees_rossii",
            territory={"kind": "est", "id": obj_id, "name": name},
            skip_direct_capacity=True,
        )
    sheet["table_number"] = 0
    sheet["title"] = f"Баланс мощности {sheet['sheet_name']}"
    return sheet


def get_power_balance_sheet(slug: str) -> dict[str, Any] | None:
    wanted = str(slug or "").strip()
    if not wanted:
        return None
    for sheet in get_power_balance_sheets():
        if sheet["slug"] == wanted:
            return sheet
    return _synthetic_sheet_for_slug(wanted)


def _sheets_including_slug(slug: str) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    wanted = str(slug or "").strip()
    sheets = get_power_balance_sheets()
    sheet = next((item for item in sheets if item["slug"] == wanted), None)
    if sheet is not None:
        return sheets, sheet
    sheet = _synthetic_sheet_for_slug(wanted)
    if sheet is None:
        return sheets, None
    sheet = dict(sheet)
    sheet["table_number"] = len(sheets) + 1
    return list(sheets) + [sheet], sheet


def group_power_balance_sheets(
    sheets: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    items = sheets if sheets is not None else get_power_balance_sheets()
    buckets: dict[str, list[dict[str, Any]]] = {group: [] for group in SHEET_GROUP_ORDER}
    for sheet in items:
        group = sheet.get("group") if sheet.get("group") in buckets else GROUP_OES
        buckets[group].append(sheet)
    return [
        {"group": group, "sheets": buckets[group]}
        for group in SHEET_GROUP_ORDER
        if buckets[group]
    ]


def get_power_balance_filter_year_list() -> list[int]:
    """Годы для выпадающих списков: справочник Year текущей версии плюс период СиПР."""
    numbers: set[int] = set()
    try:
        numbers.update(int(n) for n in (get_year_numbers_sorted_for_current_db_version() or []) if n is not None)
    except Exception:
        pass
    try:
        filter_start = int(get_filter_start_year())
        filter_end = int(get_filter_end_year())
        if filter_start > filter_end:
            filter_start, filter_end = filter_end, filter_start
        numbers.update(range(filter_start, filter_end + 1))
    except Exception:
        pass
    try:
        sipr_start = int(get_sipr_start_year())
        sipr_end = int(get_sipr_end_year())
        if sipr_start > sipr_end:
            sipr_start, sipr_end = sipr_end, sipr_start
        numbers.update(range(sipr_start, sipr_end + 1))
    except Exception:
        pass
    return sorted(numbers)


def get_power_balance_year_features() -> dict[int, str]:
    """Признаки годов из справочника Year / YearFeature текущей версии БД."""
    try:
        raw = get_year_feature_dict() or {}
    except Exception:
        return {}
    result: dict[int, str] = {}
    for key, name in raw.items():
        try:
            year = int(key)
        except (TypeError, ValueError):
            continue
        label = str(name or "").strip()
        if label:
            result[year] = label
    return result


def _parse_optional_year(value: Any, default: int) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def resolve_power_balance_rounding_digits(value: Any = None) -> int:
    if value in (None, ""):
        return POWER_BALANCE_ROUNDING_DIGITS
    try:
        digits = int(value)
    except (TypeError, ValueError):
        return POWER_BALANCE_ROUNDING_DIGITS
    if digits in POWER_BALANCE_ROUNDING_CHOICES:
        return digits
    return POWER_BALANCE_ROUNDING_DIGITS


def get_power_balance_year_columns(
    start_year: Any = None,
    end_year: Any = None,
) -> list[int]:
    default_start = int(get_sipr_start_year())
    default_end = int(get_sipr_end_year())
    if default_start > default_end:
        default_start, default_end = default_end, default_start
    start = _parse_optional_year(start_year, default_start)
    end = _parse_optional_year(end_year, default_end)
    if start > end:
        start, end = end, start
    bounds = get_power_balance_filter_year_list()
    if bounds:
        lo, hi = bounds[0], bounds[-1]
        start = max(lo, min(start, hi))
        end = max(lo, min(end, hi))
        if start > end:
            start, end = end, start
    return list(range(start, end + 1))


def build_power_balance_rows(
    layout: str,
    *,
    source_slugs: tuple[str, ...] | list[str] | None = None,
    subtract_slugs: tuple[str, ...] | list[str] | None = None,
) -> list[dict[str, Any]]:
    if layout == "ees_rossii":
        return _rows_ees_rossii(source_slugs=source_slugs)
    if layout == "sz1":
        return _rows_sz1(source_slugs=source_slugs, subtract_slugs=subtract_slugs)
    builder = _LAYOUT_BUILDERS.get(layout)
    if builder is None:
        raise KeyError(f"Неизвестный макет баланса мощности: {layout}")
    return builder()


def format_power_balance_cell(value: Any, digits: int | None = None) -> str:
    return format_decimal_trim_for_display(
        value,
        digits=POWER_BALANCE_ROUNDING_DIGITS if digits is None else digits,
    )


def _cell_is_effectively_empty(value: Any) -> bool:
    if value in (None, "", "—", "-", "–"):
        return True
    try:
        return _to_decimal(value) == 0
    except Exception:
        return False


def power_balance_row_values_empty(row: dict[str, Any], years: list[int]) -> bool:
    raw_map = row.get("year_values_raw") or {}
    display_map = row.get("year_values") or {}
    for year in years:
        if year in raw_map:
            if not _cell_is_effectively_empty(raw_map[year]):
                return False
            continue
        if not _cell_is_effectively_empty(display_map.get(year)):
            return False
    return True


def mark_power_balance_empty_rows(rows: list[dict[str, Any]], years: list[int]) -> None:
    """Помечает строки без ненулевых значений для скрытия кнопкой «Пустые строки».

    Пользовательские перетоки и строки с ручным вводом всегда остаются
    видимыми, как и их родители по indent (чтобы не терялась шапка секции).
    """
    n = len(rows)
    values_empty = [power_balance_row_values_empty(row, years) for row in rows]
    visible = [False] * n
    for i, row in enumerate(rows):
        if row.get("is_custom") or row.get("editable_values") or not values_empty[i]:
            visible[i] = True
    for i in range(n):
        if not visible[i]:
            continue
        need_indent = int(rows[i].get("indent") or 0)
        for j in range(i - 1, -1, -1):
            j_indent = int(rows[j].get("indent") or 0)
            if j_indent < need_indent:
                visible[j] = True
                need_indent = j_indent
            if need_indent <= 0:
                break
    for i, row in enumerate(rows):
        row["values_empty"] = values_empty[i]
        row["hide_when_empty"] = not visible[i]


def _to_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str):
        return Decimal(value.replace(" ", "").replace(",", "."))
    return Decimal(str(value))


def _raw_cell(row: dict[str, Any], year: int) -> Decimal:
    raw = (row.get("year_values_raw") or {}).get(year)
    if raw is not None:
        return _to_decimal(raw)
    display = (row.get("year_values") or {}).get(year)
    if display in (None, "", "—"):
        return Decimal("0")
    return _to_decimal(display)


def _sheet_has_cross_refs(rows: list[dict[str, Any]]) -> bool:
    for row in rows:
        formula = row.get("formula") or {}
        for term in formula.get("terms") or []:
            if term.get("slug"):
                return True
    return False


def _same_sheet_deps(formula: dict[str, Any] | None) -> list[str]:
    if not formula:
        return []
    return [
        str(term["row_key"])
        for term in formula.get("terms") or []
        if term.get("row_key") and not term.get("slug")
    ]


def _format_const(value: Any, digits: int | None = None) -> str:
    return format_power_balance_cell(_to_decimal(value), digits=digits)


def _formula_tooltip(
    row: dict[str, Any],
    *,
    current_slug: str,
    rows_by_slug: dict[str, dict[str, dict[str, Any]]],
    sheets_by_slug: dict[str, dict[str, Any]],
    rounding_digits: int | None = None,
) -> str:
    formula = row.get("formula")
    if not formula:
        return ""
    terms = list(formula.get("terms") or [])
    if not terms:
        return ""

    def _sheet_name(slug: str) -> str:
        return (sheets_by_slug.get(slug) or {}).get("sheet_name") or slug

    slug_terms = [term for term in terms if term.get("slug") and term.get("row_key")]
    row_keys = {term.get("row_key") for term in slug_terms}
    if slug_terms and len(slug_terms) == len(terms) and len(row_keys) == 1 and len(slug_terms) > 1:
        plus_names = [
            _sheet_name(term["slug"])
            for term in slug_terms
            if term.get("coeff", 1) > 0
        ]
        minus_names = [
            _sheet_name(term["slug"])
            for term in slug_terms
            if term.get("coeff", 1) < 0
        ]
        expression = " + ".join(plus_names)
        if minus_names:
            expression = f"{expression} − {' − '.join(minus_names)}" if expression else " − ".join(minus_names)
            if not plus_names:
                expression = f"− {expression}"
        return f"{row['label']} = {expression}"

    pieces: list[str] = []
    for index, term in enumerate(terms):
        coeff = int(term.get("coeff", 1))
        if "const" in term:
            text = _format_const(abs(_to_decimal(term["const"])), digits=rounding_digits)
            const_negative = _to_decimal(term["const"]) < 0
            if const_negative:
                coeff = -abs(coeff) if coeff > 0 else abs(coeff)
        elif term.get("slug"):
            sheet_name = _sheet_name(term["slug"])
            src_row = (rows_by_slug.get(term["slug"]) or {}).get(term["row_key"]) or {}
            src_label = src_row.get("label") or term["row_key"]
            text = f"{sheet_name}: {src_label}"
        else:
            src_row = rows_by_slug[current_slug].get(term["row_key"]) or {}
            text = src_row.get("label") or "…"

        if index == 0:
            pieces.append(f"− {text}" if coeff < 0 else text)
        elif coeff < 0:
            pieces.append(f"− {text}")
        else:
            pieces.append(f"+ {text}")
    return f"{row['label']} = {' '.join(pieces)}"


def _attach_formula_tooltips(
    tables: dict[str, dict[str, Any]],
    sheets_by_slug: dict[str, dict[str, Any]],
    rounding_digits: int | None = None,
) -> None:
    rows_by_slug = {
        slug: {row["key"]: row for row in payload["rows"]}
        for slug, payload in tables.items()
    }
    for slug, payload in tables.items():
        for row in payload["rows"]:
            if row.get("key") in CUSTOM_FLOW_DIRECTIONS and not row.get("formula"):
                row["formula_tooltip"] = ""
            else:
                row["formula_tooltip"] = _formula_tooltip(
                    row,
                    current_slug=slug,
                    rows_by_slug=rows_by_slug,
                    sheets_by_slug=sheets_by_slug,
                    rounding_digits=rounding_digits,
                )
            row["formula_client"] = _jsonable_formula(row.get("formula"))


def _eval_formula_row(
    row: dict[str, Any],
    *,
    current_slug: str,
    years: list[int],
    rows_by_slug: dict[str, dict[str, dict[str, Any]]],
    rounding_digits: int | None = None,
) -> None:
    formula = row.get("formula") or {}
    terms = list(formula.get("terms") or [])
    for year in years:
        total = Decimal("0")
        ext = Decimal("0")
        for term in terms:
            coeff = _to_decimal(term.get("coeff", 1))
            if "const" in term:
                part = _to_decimal(term["const"]) * coeff
                total += part
                ext += part
                continue
            src_slug = term.get("slug") or current_slug
            src_row = rows_by_slug.get(src_slug, {}).get(term["row_key"])
            part = _raw_cell(src_row or {}, year) * coeff
            total += part
            if term.get("slug"):
                ext += part
        row.setdefault("year_values_raw", {})[year] = total
        row.setdefault("year_values", {})[year] = format_power_balance_cell(
            total, digits=rounding_digits
        )
        row.setdefault("formula_ext_raw", {})[year] = format(ext, "f")


def _eval_sheet(
    slug: str,
    tables: dict[str, dict[str, Any]],
    years: list[int],
    rounding_digits: int | None = None,
) -> None:
    rows = tables[slug]["rows"]
    rows_by_slug = {
        item_slug: {row["key"]: row for row in payload["rows"]}
        for item_slug, payload in tables.items()
    }
    remaining = {row["key"] for row in rows if row.get("formula")}
    by_key = {row["key"]: row for row in rows}
    for _ in range(len(remaining) + 1):
        if not remaining:
            break
        progressed = False
        for key in list(remaining):
            deps = _same_sheet_deps(by_key[key].get("formula"))
            if any(dep in remaining for dep in deps):
                continue
            _eval_formula_row(
                by_key[key],
                current_slug=slug,
                years=years,
                rows_by_slug=rows_by_slug,
                rounding_digits=rounding_digits,
            )
            remaining.remove(key)
            progressed = True
        if not progressed:
            raise RuntimeError(f"Циклические формулы баланса мощности на листе {slug}: {sorted(remaining)}")


def _merge_power_balance_inputs(
    *parts: dict[str, dict[str, dict[int, Any]]] | None,
) -> dict[str, dict[str, dict[int, Any]]]:
    merged: dict[str, dict[str, dict[int, Any]]] = {}
    for part in parts:
        for slug, rows in (part or {}).items():
            merged.setdefault(slug, {}).update(rows)
    return merged


def apply_power_balance_input_values(
    tables: dict[str, dict[str, Any]],
    inputs: dict[str, dict[str, dict[int, Any]]] | None,
    rounding_digits: int | None = None,
) -> None:
    """Записывает входные значения {slug: {row_key: {year: number}}} до расчета формул."""
    if not inputs:
        return
    for slug, row_inputs in inputs.items():
        payload = tables.get(slug)
        if payload is None:
            continue
        by_key = {row["key"]: row for row in payload["rows"]}
        for row_key, year_map in row_inputs.items():
            row = by_key.get(row_key)
            if row is None or row.get("formula"):
                continue
            for year, value in year_map.items():
                year_int = int(year)
                number = _to_decimal(value)
                row.setdefault("year_values_raw", {})[year_int] = number
                row.setdefault("year_values", {})[year_int] = format_power_balance_cell(
                    number, digits=rounding_digits
                )


def evaluate_power_balance_tables(
    tables: dict[str, dict[str, Any]],
    years: list[int],
    rounding_digits: int | None = None,
) -> None:
    independent = [
        slug for slug, payload in tables.items() if not _sheet_has_cross_refs(payload["rows"])
    ]
    dependent = [slug for slug in tables if slug not in independent]
    for slug in independent:
        _eval_sheet(slug, tables, years, rounding_digits=rounding_digits)
    for slug in dependent:
        _eval_sheet(slug, tables, years, rounding_digits=rounding_digits)


def build_power_balance_tables(
    years: list[int] | None = None,
    inputs: dict[str, dict[str, dict[int, Any]]] | None = None,
    rounding_digits: int | None = None,
    custom_flows: dict[str, list[dict[str, Any]]] | None = None,
    sheets: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    if years is None:
        years = get_power_balance_year_columns()
    digits = resolve_power_balance_rounding_digits(rounding_digits)
    if sheets is None:
        sheets = get_power_balance_sheets()
    tables: dict[str, dict[str, Any]] = {}
    sheets_by_slug: dict[str, dict[str, Any]] = {}
    for sheet in sheets:
        slug = sheet["slug"]
        sheets_by_slug[slug] = dict(sheet)
        tables[slug] = {
            "sheet": dict(sheet),
            "rows": build_power_balance_rows(
                sheet["layout"],
                source_slugs=sheet.get("source_slugs"),
                subtract_slugs=sheet.get("subtract_slugs"),
            ),
        }
    if custom_flows is None:
        try:
            custom_flows = load_power_balance_custom_flows(sheets=sheets)
        except Exception:
            custom_flows = {}
    custom_inputs = apply_custom_flows_to_tables(tables, custom_flows)
    if inputs is None:
        capacity_inputs: dict[str, dict[str, dict[int, Any]]] = {}
        demand_inputs: dict[str, dict[str, dict[int, Any]]] = {}
        export_inputs: dict[str, dict[str, dict[int, Any]]] = {}
        try:
            capacity_inputs = load_power_balance_installed_capacity_inputs(years, sheets=sheets)
        except Exception:
            capacity_inputs = {}
        try:
            demand_inputs = load_power_balance_demand_max_inputs(years, sheets=sheets)
        except Exception:
            demand_inputs = {}
        try:
            export_inputs = load_power_balance_export_inputs(years, sheets=sheets)
        except Exception:
            export_inputs = {}
        inputs = _merge_power_balance_inputs(capacity_inputs, demand_inputs, export_inputs)
    inputs = _merge_power_balance_inputs(inputs, custom_inputs)
    apply_power_balance_input_values(tables, inputs, rounding_digits=digits)
    _attach_formula_tooltips(tables, sheets_by_slug, rounding_digits=digits)
    evaluate_power_balance_tables(tables, years, rounding_digits=digits)
    for payload in tables.values():
        mark_power_balance_empty_rows(payload["rows"], years)
    return tables


def _sheet_territory(sheet: dict[str, Any]) -> dict[str, Any] | None:
    territory = sheet.get("territory") or {}
    entity_id = territory.get("id")
    kind = territory.get("kind")
    if entity_id is not None and kind:
        try:
            return {"kind": str(kind), "id": int(entity_id)}
        except (TypeError, ValueError):
            pass
    slug = str(sheet.get("slug") or "")
    if not slug:
        return None
    try:
        return resolve_sheet_territory(slug)
    except Exception:
        return None


def _find_ees_est_id() -> int | None:
    try:
        for est in get_energy_system_type_list_full() or []:
            if _is_unspecified_ref(est):
                continue
            if _is_ees_type_name(est.name) and not _is_non_ees_system_name(est.name):
                return int(est.id)
    except Exception:
        return None
    return None


def _find_oes_vostok_ues_id() -> int | None:
    try:
        for ues in get_union_energy_system_list_full() or []:
            if _is_unspecified_ref(ues):
                continue
            if _is_oes_vostok_name(getattr(ues, "name", None)):
                return int(ues.id)
    except Exception:
        return None
    return None


def _regional_district_ids_for_sa(sa_id: int) -> list[int]:
    try:
        from app.common.services.database_version_services import get_current_version
        from app.refdata.models.territories.regional_district_model import RegionalDistrict

        query = RegionalDistrict.query.filter(RegionalDistrict.id_synchronous_area == int(sa_id))
        current_version = get_current_version()
        if current_version:
            query = query.filter(RegionalDistrict.database_version_id == current_version)
        return [
            int(row.id)
            for row in query.all()
            if getattr(row, "id", None) is not None and int(row.id) > 0
        ]
    except Exception:
        return []


def _ues_ids_for_slugs(slugs: list[str] | tuple[str, ...], sheets: list[dict[str, Any]]) -> list[int]:
    by_slug = {item.get("slug"): item for item in sheets}
    ids: list[int] = []
    seen: set[int] = set()
    for slug in slugs:
        other = by_slug.get(slug) or {"slug": slug}
        territory = _sheet_territory(other)
        if not territory or territory.get("kind") != "ues":
            continue
        entity_id = int(territory["id"])
        if entity_id in seen:
            continue
        seen.add(entity_id)
        ids.append(entity_id)
    return ids


def power_balance_station_list_query(
    sheet: dict[str, Any],
    sheets: list[dict[str, Any]],
    start_year: Any = None,
    end_year: Any = None,
) -> dict[str, Any]:
    """GET-параметры списка станций: годы страницы и фильтр ОЭС / СЗ / ЕЭС."""
    query: dict[str, Any] = {}
    if start_year not in (None, ""):
        query["start_year"] = int(start_year)
    if end_year not in (None, ""):
        query["end_year"] = int(end_year)

    group = sheet.get("group")
    layout = sheet.get("layout")
    territory = _sheet_territory(sheet)

    if layout == "ees_rossii" or group == GROUP_EES:
        est_id = territory["id"] if territory and territory.get("kind") == "est" else _find_ees_est_id()
        if est_id:
            query["energy_system_type_filter"] = int(est_id)
        return query

    if layout == "sz1":
        ues_ids = _ues_ids_for_slugs(sheet.get("source_slugs") or SZ1_ADD_SLUGS, sheets)
        if ues_ids:
            query["union_energy_system_filter"] = ues_ids
        return query

    if territory and territory.get("kind") == "ues":
        query["union_energy_system_filter"] = int(territory["id"])
        return query

    if territory and territory.get("kind") == "sa":
        if layout == "oes_vostok":
            vostok_ids = _ues_ids_for_slugs(("vostok", "2-sz-ees-vostok"), sheets)
            if not vostok_ids:
                found = _find_oes_vostok_ues_id()
                if found:
                    vostok_ids = [found]
            if not vostok_ids:
                resolved = None
                try:
                    resolved = resolve_sheet_territory("vostok") or resolve_sheet_territory(
                        "2-sz-ees-vostok"
                    )
                except Exception:
                    resolved = None
                if resolved and resolved.get("kind") == "ues":
                    vostok_ids = [int(resolved["id"])]
            if vostok_ids:
                query["union_energy_system_filter"] = (
                    vostok_ids[0] if len(vostok_ids) == 1 else vostok_ids
                )
                return query
        rd_ids = _regional_district_ids_for_sa(int(territory["id"]))
        if rd_ids:
            query["regional_district_filter"] = rd_ids
        return query

    return query


def build_power_balance_station_list_url(query: dict[str, Any]) -> str:
    try:
        from flask import url_for

        base = url_for("station_bp.station_list")
    except Exception:
        base = "/generation/stations/station_list"
    pairs: list[tuple[str, str]] = []
    for key, value in query.items():
        if isinstance(value, (list, tuple)):
            for item in value:
                if item is not None and item != "":
                    pairs.append((key, str(item)))
        elif value is not None and value != "":
            pairs.append((key, str(value)))
    if not pairs:
        return base
    joiner = "&" if "?" in base else "?"
    return f"{base}{joiner}{urlencode(pairs)}"


def build_power_balance_table_context(
    slug: str,
    *,
    start_year: Any = None,
    end_year: Any = None,
    rounding_digits: Any = None,
) -> dict[str, Any] | None:
    sheets, sheet = _sheets_including_slug(slug)
    if sheet is None:
        return None
    years = get_power_balance_year_columns(start_year, end_year)
    digits = resolve_power_balance_rounding_digits(rounding_digits)
    tables = build_power_balance_tables(years, rounding_digits=digits, sheets=sheets)
    payload = tables[sheet["slug"]]
    page_title = sheet["title"]
    start = years[0] if years else None
    end = years[-1] if years else None
    station_query = power_balance_station_list_query(sheet, sheets, start, end)
    return {
        "sheet": payload["sheet"],
        "sheets": sheets,
        "sheet_groups": group_power_balance_sheets(sheets),
        "page_title": page_title,
        "years": years,
        "year_features": get_power_balance_year_features(),
        "start_year": start,
        "end_year": end,
        "filter_year_list": get_power_balance_filter_year_list(),
        "rounding_digits": digits,
        "station_list_url": build_power_balance_station_list_url(station_query),
        "rows": payload["rows"],
    }
