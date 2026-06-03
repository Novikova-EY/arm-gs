"""Страница «Потребление электрической энергии ГАЭС на заряд»: только синтетические строки заряда ГАЭС."""

from __future__ import annotations

from typing import Any

from app.energy_consumption.services.energy_consumption_summary_services import (
    GAES_CHARGE_PARAMETER_KEY,
    _format_gaes_related_entity_label,
    _KALININGRAD_ES_LABEL_SUFFIX_WITHOUT,
    _KALININGRAD_ES_LABEL_SUFFIX_WITH,
    _split_kaliningrad_suffix_from_label,
    tag_energy_consumption_summary_rows_for_ui_toggles,
)

_EES_RU_LABEL_WO_NT = "ЕЭС России без НТ"
_EES_RU_LABEL_WITH_NT = "ЕЭС России с НТ"


def strip_gaes_charge_marker_from_entity_label(label: str) -> str:
    """Убирает пометку « (заряд ГАЭС)» из подписи территории на отдельной странице заряда."""
    s = str(label or "").strip()
    token = " (заряд ГАЭС)"
    while token in s:
        s = s.replace(token, "")
    while "  " in s:
        s = s.replace("  ", " ")
    return s.strip()


def _patch_gaes_charge_page_ees_russia_nt_screen_labels(rows: list[dict[str, Any]]) -> None:
    """Кнопка +НТ: выкл. — строка без НТ в колонке как «ЕЭС России …»; вкл. — обе строки.

    После общего ``tag_energy_consumption_*`` задаёт надёжно ``compact_nt`` и ``pd_ec_nt_extra_row``.
    """
    kal_opts = (_KALININGRAD_ES_LABEL_SUFFIX_WITH, _KALININGRAD_ES_LABEL_SUFFIX_WITHOUT)
    if not rows:
        return
    for row in rows:
        if row.get("parameter_key") != GAES_CHARGE_PARAMETER_KEY:
            continue
        raw = str(row.get("entity_label") or "").strip()
        core, kal_q = _split_kaliningrad_suffix_from_label(raw)
        if core.startswith(_EES_RU_LABEL_WO_NT):
            inner_tail = core[len(_EES_RU_LABEL_WO_NT) :].strip()
            plain = ("ЕЭС России" + (f" {inner_tail}" if inner_tail else "")).strip()
            rebuilt = plain
            if kal_q:
                hit = False
                for suf in kal_opts:
                    if suf.strip() == kal_q.strip():
                        rebuilt = plain + suf
                        hit = True
                        break
                if not hit:
                    rebuilt = f"{plain} {kal_q}"
            row["pd_ec_entity_label_compact_nt"] = _format_gaes_related_entity_label(
                rebuilt, ""
            ).strip()
            row["pd_ec_nt_extra_row"] = False
        elif core.startswith(_EES_RU_LABEL_WITH_NT):
            row["pd_ec_nt_extra_row"] = True


def _reset_gaes_charge_page_row_visibility_flags(rows: list[dict[str, Any]]) -> None:
    """На отдельной странице заряда ГАЭС не скрывать строки «+ Заряд ГАЭС» / сводной таблицы.

    ``pd_ec_nt_extra_row`` не трогаем — переключатель «+ НТ» управляет строками ЕЭС России.
    """
    for row in rows:
        row["pd_ec_gaes_extra_row"] = False
        row.pop("pd_ec_territory_detail_row", None)
        row.pop("pd_ec_territory_detail_relaxed_compact_nt_gaes", None)
        if row.get("pd_ec_first_sa_gaes_compact_variant") == "detail":
            row.pop("pd_ec_first_sa_gaes_compact_variant", None)


def build_energy_consumption_gaes_charge_only_context(base: dict[str, Any]) -> dict[str, Any]:
    """Оставляет в ``summary_rows`` только строки ``gaes_charge_consumption_mln_kvt_ch``; задаёт заголовок страницы.

    Строку «ОЭС Юга без НТ» (промежуточный суммарный заряд по ОЭС) не включаем: те же станции
    уже выведены под РЭС дубль не нужен отдельной строкой сверху ЕЭС России.
    """
    out = dict(base)
    rows_in = list(base.get("summary_rows") or [])
    filtered: list[dict[str, Any]] = []
    for row in rows_in:
        if row.get("parameter_key") != GAES_CHARGE_PARAMETER_KEY:
            continue
        if row.get("entity_kind") == "oes_south_without_nt":
            continue
        new_row = dict(row)
        new_row["entity_label"] = strip_gaes_charge_marker_from_entity_label(
            str(row.get("entity_label") or "")
        )
        new_row["entity_rowspan"] = 1
        new_row["show_entity_cell"] = True
        new_row["show_entity_note_cell"] = True
        filtered.append(new_row)

    tag_energy_consumption_summary_rows_for_ui_toggles(filtered)
    _patch_gaes_charge_page_ees_russia_nt_screen_labels(filtered)
    _reset_gaes_charge_page_row_visibility_flags(filtered)

    out["summary_rows"] = filtered
    out["page_title"] = "Заряд ГАЭС"
    out["energy_consumption_gaes_charge_only_page"] = True
    # Правку ячеек (администратор) задаёт базовый context маршрута — не отключать на этой странице.
    return out


def exclude_gaes_charge_summary_rows(
    summary_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Убирает строки ``gaes_charge_consumption_mln_kvt_ch``; пересчитывает ``entity_rowspan``."""
    if not summary_rows:
        return []
    out: list[dict[str, Any]] = []
    i = 0
    n = len(summary_rows)
    while i < n:
        row = summary_rows[i]
        if row.get("parameter_key") == GAES_CHARGE_PARAMETER_KEY:
            i += 1
            continue
        if not row.get("show_entity_cell"):
            out.append(dict(row))
            i += 1
            continue
        block_size = max(int(row.get("entity_rowspan") or 1), 1)
        block = summary_rows[i : i + block_size]
        kept = [
            dict(r)
            for r in block
            if r.get("parameter_key") != GAES_CHARGE_PARAMETER_KEY
        ]
        for j, r in enumerate(kept):
            r["show_entity_cell"] = j == 0
            r["entity_rowspan"] = len(kept)
            if j == 0:
                r["show_entity_note_cell"] = True
            out.append(r)
        i += block_size
    return out


def remove_gaes_charge_rows_from_summary_context(
    context: dict[str, Any],
) -> dict[str, Any]:
    """Сводка без строк заряда ГАЭС (страница /summary/energy-zones/)."""
    out = dict(context)
    out["summary_rows"] = exclude_gaes_charge_summary_rows(
        list(context.get("summary_rows") or [])
    )
    return out


def remove_oes_and_subject_rows_from_gaes_charge_context(
    context: dict[str, Any],
) -> dict[str, Any]:
    """Для сводной таблицы заряда ГАЭС скрывает промежуточные уровни ОЭС и субъектов РФ."""
    hidden_model_names = {
        "UnionEnergySystemEnergyConsumptionParameter",
        "RegionalDistrictEnergyConsumptionParameter",
    }
    out = dict(context)
    out["summary_rows"] = [
        row
        for row in list(context.get("summary_rows") or [])
        if row.get("demand_model_name") not in hidden_model_names
    ]
    return out
