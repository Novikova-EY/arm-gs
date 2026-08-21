# -*- coding: utf-8 -*-
"""
Семантика составных станций Access → АРМ (родительская EG + дочерние группы).

Справочник «Имена_станций» → EquipmentGroup:
  numb  — код строки (станции или группы) = NUMB1120 в параметрах;
  main  — у дочерней группы = numb родителя; у родителя / простой станции = 0/NULL;
  comp  — у родителя = 1, если станция разбита (или может быть разбита) на группы;
  niv   — признак группы оборудования (обычно 1 у детей).

Рабочая таблица «Станции(Схема)» → EquipmentGroupFuelParam:
  ved   — операционный код строки за год (не путать с EquipmentGroup.vedomstvo);
          подписи — FUEL_PARAM_VED_LABELS.

Антидубль в расчёте Access: фильтры вида (ved>0) на рабочей таблице.
Родитель после появления детей получает ved=0 и выпадает из Коэфф/Распред/Топливо.

Режим детализации параметров за год (без отдельной таблицы на первом этапе):
  by_groups    — у детей ved>0 (родитель ved=0 или отсутствует);
  station_only — у родителя ved>0, у детей нет участия (ved≤0 / нет строк);
  unknown      — нет активного уровня (данные не загружены).
"""
from __future__ import annotations

from typing import Any, Iterable, Literal, Sequence

ParamsDetailLevel = Literal["by_groups", "station_only", "unknown"]

# Подписи FuelParam.ved: «цифра — значение» (select/title на карточке EG, каталог).
FUEL_PARAM_VED_LABELS: dict[int, str] = {
    0: "0 — оболочка родителя составной станции",
    1: "1 — КЭС, отрасль",
    2: "2 — ТЭЦ, отрасль",
    3: "3 — ТЭЦ, промпредприятия",
    4: "4 — КЭС, промпредприятия",
    99: "99 — родитель помечен к разбиению, группы еще не вставлены",
}

# Подпись в колонке «Тип группы оборудования» для родителя составной станции
# (MAIN пуст, COMP=1): это оболочка станции, не тип оборудования.
COMPOSITE_PARENT_GROUP_TYPE_LABEL = "станция"


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def is_main_empty(main: Any) -> bool:
    """MAIN пуст / 0 → строка уровня станции (родитель или простая ТЭС)."""
    v = _as_int(main)
    return v is None or v == 0


def is_composite_parent_group(equipment_group: Any) -> bool:
    """
    Родитель составной станции в справочнике:
    MAIN пуст и (COMP=1 или NIV не группа).
    Достаточный pragmatic-критерий: MAIN пуст и COMP=1.
    """
    if equipment_group is None:
        return False
    if not is_main_empty(getattr(equipment_group, "main", None)):
        return False
    return _as_int(getattr(equipment_group, "comp", None)) == 1


def is_composite_child_group(equipment_group: Any) -> bool:
    """Дочерняя группа оборудования: MAIN > 0."""
    if equipment_group is None:
        return False
    main = _as_int(getattr(equipment_group, "main", None))
    return main is not None and main > 0


def equipment_group_type_display_name(
    equipment_group: Any,
    group_type: Any = None,
) -> str:
    """
    Отображаемый тип группы:
      родитель составной — «станция»;
      иначе — name из справочника типов / «—».
    """
    if is_composite_parent_group(equipment_group):
        return COMPOSITE_PARENT_GROUP_TYPE_LABEL
    name = getattr(group_type, "name", None) if group_type is not None else None
    if name and str(name).strip():
        return str(name).strip()
    return "—"


def fuel_param_ved_participates(ved: Any) -> bool:
    """
    Access: условие (ved>0) на рабочей строке года.
    NULL и 0 — не участвуют (оболочка родителя / пустая строка).
    """
    v = _as_int(ved)
    return v is not None and v > 0


def fuel_param_row_participates(param: Any) -> bool:
    """Строка FuelParam участвует в расчётных суммах / отборе ved>0."""
    if param is None:
        return False
    return fuel_param_ved_participates(getattr(param, "ved", None))


def classify_station_groups(
    equipment_groups: Sequence[Any],
) -> tuple[Any | None, list[Any]]:
    """
    Среди EG одной станции/кластера: (родитель или None, список детей).
    Составность только по COMP/MAIN (не по числу EG на одной Generation Station).
    """
    parent = None
    children: list[Any] = []
    plain: list[Any] = []
    for eg in equipment_groups:
        if eg is None:
            continue
        if is_composite_child_group(eg):
            children.append(eg)
        elif is_composite_parent_group(eg):
            parent = eg
        else:
            plain.append(eg)
    if parent is None and children and plain:
        # Редкое смешение: plain не считаем детьми.
        pass
    # Составность только по comp/main. Несколько EG на одной Station без MAIN
    # больше не считаются «детьми» (суррогат grouping_station снят).
    return parent, children


def resolve_params_detail_level_for_year(
    *,
    parent_param: Any | None,
    child_params: Iterable[Any | None],
) -> ParamsDetailLevel:
    """
    Режим детализации за один year_number по факту FuelParam.ved.
    """
    children_active = any(fuel_param_row_participates(p) for p in child_params)
    parent_active = fuel_param_row_participates(parent_param)
    if children_active:
        return "by_groups"
    if parent_active:
        return "station_only"
    return "unknown"


def should_edit_fuel_param_row(
    *,
    detail_level: ParamsDetailLevel,
    equipment_group: Any,
    has_composite_structure: bool,
) -> bool:
    """
    Редактируемость канонических параметров:
      by_groups    — только дети (или все «siblings» без родителя);
      station_only — только родитель;
      без структуры составной станции — как обычно (все строки).
    """
    if not has_composite_structure:
        return True
    if detail_level == "by_groups":
        if is_composite_parent_group(equipment_group):
            return False
        return True
    if detail_level == "station_only":
        return is_composite_parent_group(equipment_group) or (
            is_main_empty(getattr(equipment_group, "main", None))
            and not is_composite_child_group(equipment_group)
        )
    return True


def should_show_station_summary_for_detail_level(
    detail_level: ParamsDetailLevel,
    *,
    participating_group_count: int,
) -> bool:
    """Жёлтая «станция, всего» — только когда за год учёт по группам и ≥2 участников."""
    if detail_level != "by_groups":
        return False
    return participating_group_count > 1
