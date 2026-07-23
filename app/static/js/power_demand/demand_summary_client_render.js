/**
 * Клиентский рендер tbody сводок «Максимумы» и «Коэффициенты» (ОЭС / ФО / ЭЗ).
 * Shell-страница загружает JSON и строит строки таблицы вместо ~5 МБ HTML.
 */
(function () {
    "use strict";

    var configEl = document.getElementById("pd-summary-client-render-config");
    if (!configEl || !configEl.textContent) {
        return;
    }

    var shellConfig;
    try {
        shellConfig = JSON.parse(configEl.textContent);
    } catch (eCfg) {
        shellConfig = null;
    }
    if (!shellConfig || !shellConfig.data_path) {
        return;
    }

    if (window.__pdPdSummaryTerritoryCompactMode === undefined) {
        var summaryTableEl = document.getElementById("powerDemandSummaryTable");
        var compactView =
            (summaryTableEl &&
                summaryTableEl.getAttribute("data-summary-view")) ||
            shellConfig.scope ||
            "oes";
        try {
            window.__pdPdSummaryTerritoryCompactMode =
                sessionStorage.getItem(
                    "pdPdSummaryTerritoryCompact_" + compactView
                ) === "1";
        } catch (eCompactInit) {
            window.__pdPdSummaryTerritoryCompactMode = false;
        }
    }

    var READONLY_KEYS = {};
    (shellConfig.pd_readonly_parameter_keys || []).forEach(function (k) {
        READONLY_KEYS[k] = true;
    });
    var SUMMARY_SCOPES = { oes: true, fo: true, ez: true };
    var PD_NEW_TERRITORIES_LABEL = "Новые территории";

    function isNtAggregationHeaderRow(row) {
        return (
            !!row.pd_pd_aggregation_level_row &&
            String(row.entity_label || "").trim() === PD_NEW_TERRITORIES_LABEL
        );
    }

    function shouldOmitSummaryTableOnlyRow(row) {
        return (
            !!row.pd_pd_summary_table_only_row &&
            window.__pdPdSummaryTerritoryCompactMode !== true
        );
    }

    function shouldOmitRowInTerritoryCompactMode(row) {
        if (!aggregationLevelUsesCompactLayout()) {
            return false;
        }
        // Блок «Новые территории» в «Сводной таблице» показывается кнопкой «+ НТ»,
        // как в полном дереве ОЭС — не отсекаем его режимом compact.
        if (row.pd_pd_nt_extra_row || isNtAggregationHeaderRow(row)) {
            return false;
        }
        return !!row.pd_pd_territory_compact_hide_row;
    }

    function shouldOmitRowForCurrentView(row) {
        return (
            shouldOmitSummaryTableOnlyRow(row) ||
            shouldOmitRowInTerritoryCompactMode(row)
        );
    }

    /** После отсечения строк «Сводной таблицы» / prefix пересчитать rowspan блоков сущностей. */
    function prepareRowsForClientRender(rows) {
        var result = [];
        var i = 0;
        while (i < rows.length) {
            var row = rows[i];
            if (row.pd_pd_aggregation_level_row) {
                if (!shouldOmitRowForCurrentView(row)) {
                    result.push(Object.assign({}, row));
                }
                i += 1;
                continue;
            }
            if (!row.show_entity_cell) {
                i += 1;
                continue;
            }
            var blockSize = Math.max(parseInt(row.entity_rowspan || 1, 10), 1);
            var block = rows.slice(i, i + blockSize);
            i += blockSize;
            var visible = block.filter(function (r) {
                return !shouldOmitRowForCurrentView(r);
            });
            if (!visible.length) {
                continue;
            }
            var noteSource = null;
            for (var bi = 0; bi < block.length; bi++) {
                if (block[bi].show_entity_note_cell) {
                    noteSource = block[bi];
                    break;
                }
            }
            visible.forEach(function (r, idx) {
                var copy = Object.assign({}, r);
                copy.show_entity_cell = idx === 0;
                copy.entity_rowspan = visible.length;
                if (idx === 0 && noteSource) {
                    copy.show_entity_note_cell = true;
                    if (noteSource.entity_note_text !== undefined) {
                        copy.entity_note_text = noteSource.entity_note_text;
                    }
                    if (noteSource.entity_note_row_id !== undefined) {
                        copy.entity_note_row_id = noteSource.entity_note_row_id;
                    }
                } else {
                    copy.show_entity_note_cell = false;
                }
                result.push(copy);
            });
        }
        return result;
    }

    function pdSummaryRefreshEntityLayout() {
        if (typeof window.__pdPdSummaryRepositionEntityCells === "function") {
            window.__pdPdSummaryRepositionEntityCells();
        }
    }

    /** Столбцы заголовка уровня агрегации («Новые территории» и т.п.). */
    function pdSummaryAggregationLevelColspan(yearCount) {
        var n = 3 + (yearCount || 0);
        if (window.__pdPdSummaryPerimeterVariantMode === true) {
            n += 1;
        }
        if (window.__pdPdSummaryHistMode === true) {
            n += 1;
        }
        return n;
    }

    function pdSummaryCountSummaryYearColumns() {
        var table =
            document.getElementById("powerDemandSummaryTable") ||
            document.querySelector("#powerDemandSummaryTable");
        if (!table) {
            return 0;
        }
        var yearHeaders = table.querySelectorAll("thead th.summary-year-col");
        if (yearHeaders.length) {
            return yearHeaders.length;
        }
        return table.querySelectorAll("colgroup col.summary-col-year").length;
    }

    function pdSummarySyncAggregationLevelColspans() {
        var table =
            document.getElementById("powerDemandSummaryTable") ||
            document.querySelector("#powerDemandSummaryTable");
        if (!table) {
            return;
        }
        var yearCount = pdSummaryCountSummaryYearColumns();
        var colspan = pdSummaryAggregationLevelColspan(yearCount);
        table
            .querySelectorAll(
                'tbody tr[data-pd-pd-aggregation-level="1"] > td[data-pd-aggregation-header-cell="1"]'
            )
            .forEach(function (td) {
                td.colSpan = colspan;
            });
    }

    window.pdSummaryAggregationLevelColspan = pdSummaryAggregationLevelColspan;
    window.pdSummarySyncAggregationLevelColspans = pdSummarySyncAggregationLevelColspans;

    function escapeHtml(text) {
        return String(text == null ? "" : text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function escapeAttr(text) {
        return escapeHtml(text).replace(/'/g, "&#39;");
    }

    function setDataAttr(el, name, value) {
        if (value !== null && value !== undefined && value !== "") {
            el.setAttribute(name, String(value));
        }
    }

    function aggregationLevelUsesCompactLayout() {
        return window.__pdPdSummaryTerritoryCompactMode === true;
    }

    function pdSummaryAggregationLevelLabel(row) {
        if (
            aggregationLevelUsesCompactLayout() &&
            row.pd_pd_entity_label_territory_compact
        ) {
            return row.pd_pd_entity_label_territory_compact;
        }
        return row.entity_label || "";
    }

    function pdSummaryToggleHideRowInitially(row, active) {
        if (!SUMMARY_SCOPES[active]) {
            return false;
        }
        if (row.pd_pd_nt_extra_row && window.__pdPdSummaryNtDetailMode !== true) {
            return true;
        }
        if (shouldOmitRowForCurrentView(row)) {
            return true;
        }
        if (
            window.__pdPdSummaryTerritoryCompactMode === true &&
            row.pd_pd_territory_detail_row &&
            !row.pd_pd_aggregation_level_row &&
            !row.pd_pd_nt_extra_row
        ) {
            return true;
        }
        return false;
    }

    function isCoeffRoute(cfg) {
        return (cfg && cfg.summary_route_variant) === "coeff";
    }

    function coeffBaseYear(cfg) {
        var n = cfg && cfg.coeff_base_year;
        if (n == null || n === "") {
            return null;
        }
        var parsed = parseInt(n, 10);
        return isNaN(parsed) ? null : parsed;
    }

    function coeffYearSegment(year, baseYear) {
        if (baseYear == null) {
            return "";
        }
        var y = parseInt(year, 10);
        if (isNaN(y)) {
            return "";
        }
        if (y >= baseYear - 9 && y <= baseYear) {
            return "reporting";
        }
        if (y >= baseYear + 1 && y <= baseYear + 6) {
            return "medium";
        }
        return "long";
    }

    function isFoCoeffCzTotalRow(row) {
        return !!(row && row.pd_fo_coeff_cz_total);
    }

    function shouldBuildCoeffKRow(row) {
        var pk = row.parameter_key || "";
        if (pk === "max_power") {
            return false;
        }
        if (row.pd_pd_verify_for_row) {
            return false;
        }
        if (row.pd_pd_aggregation_level_full_row || row.pd_pd_aggregation_level_row) {
            return false;
        }
        if (row.pd_pd_chi_row || row.pd_pd_ee_row) {
            return false;
        }
        return true;
    }

    /** Строка «Проверка …» относится к указанному parameter_key (якорь A). */
    function isVerifyRowForParameter(verifyRow, paramKey) {
        if (!verifyRow || !paramKey) {
            return false;
        }
        if (
            !(
                verifyRow.pd_pd_verify_for_row ||
                String(verifyRow.parameter_key || "").indexOf("verify_for_") === 0
            )
        ) {
            return false;
        }
        var a = verifyRow.pd_pd_verify_a_parameter_key;
        if (a && String(a) === String(paramKey)) {
            return true;
        }
        return String(verifyRow.parameter_key || "") === "verify_for_" + paramKey;
    }

    function coeffPlanHideYear(row, year, yearIsPlan, cfg) {
        var pk = row.parameter_key || "";
        if (!yearIsPlan[String(year)] || pk === "max_power") {
            return false;
        }
        if (isFoCoeffCzTotalRow(row)) {
            return false;
        }
        var base = coeffBaseYear(cfg);
        var y = parseInt(year, 10);
        var isMedium =
            base != null && !isNaN(y) && y >= base + 1 && y <= base + 6;
        var inReport =
            base != null && !isNaN(y) && y >= base - 9 && y <= base;
        var resCombinedMediumExempt =
            isMedium &&
            (pk === "combined_on_oes" || pk === "combined_on_ees") &&
            row.demand_model_name === "RegionalEnergySystemDemandParameter";
        var uesCalcPlanUncollapse =
            row.demand_model_name === "UnionEnergySystemDemandParameter" &&
            (pk === "calculated_max_power_mw" ||
                pk === "calculated_combined_on_ees_mw") &&
            (inReport || isMedium);
        var uesCombinedEesMediumOnly =
            isMedium &&
            row.demand_model_name === "UnionEnergySystemDemandParameter" &&
            pk === "combined_on_ees";
        if (
            resCombinedMediumExempt ||
            uesCalcPlanUncollapse ||
            uesCombinedEesMediumOnly
        ) {
            return false;
        }
        return true;
    }

    function computeRowClasses(row, cfg) {
        var classes = [
            "summary-kind-" + (row.entity_kind || ""),
            "summary-row-param",
        ];
        var pk = row.parameter_key || "";
        var active = cfg.active_summary || "";

        if (row.pd_pd_verify_for_row) {
            classes.push("pd-pd-verify-for-row");
        }
        if (row.pd_pd_ee_row) {
            classes.push("pd-pd-ee-row", "summary-row-hidden");
        } else if (row.pd_pd_chi_row) {
            classes.push("pd-pd-chi-row", "summary-row-hidden");
        } else if (
            (active === "oes" || active === "fo" || active === "ez") &&
            pk &&
            READONLY_KEYS[pk]
        ) {
            classes.push("pd-pd-calc-max-row", "summary-row-hidden");
        }
        if (row.pd_pd_verify_for_row) {
            classes.push("summary-row-hidden");
        } else if (
            isCoeffRoute(cfg) &&
            (pk === "peak_datetime" || pk === "avg_temp")
        ) {
            classes.push("summary-row-hidden");
        } else if (pdSummaryToggleHideRowInitially(row, active)) {
            classes.push("summary-row-hidden");
        }
        return classes.join(" ");
    }

    function canEditSlice(row, cfg) {
        return (
            !!row.demand_model_name &&
            (row.parent_fk_column == null || row.parent_id != null) &&
            !!cfg.can_edit_summary_cells
        );
    }

    function isSouthUesWithoutNtManualRow(row) {
        if (!row || row.demand_model_name !== "UnionEnergySystemDemandParameter") {
            return false;
        }
        if (row.pd_pd_south_ues_without_nt_manual_row) {
            return true;
        }
        var code = String(row.perimeter_variant_code || "");
        if (code.indexOf("with_nt") === 0) {
            return false;
        }
        if (code !== "without_nt" && code.indexOf("without_nt") !== 0) {
            return false;
        }
        var label = String(row.entity_label || "")
            .replace(/\s+/g, " ")
            .trim()
            .toLowerCase();
        return label.indexOf("юга") >= 0 && label.indexOf(" с нт") < 0;
    }

    function canEditCell(row, cfg) {
        if (row.pd_pd_chi_row || row.pd_pd_ee_row) {
            return false;
        }
        var pk = row.parameter_key || "";
        var manualSouthWithoutNt = isSouthUesWithoutNtManualRow(row);
        return (
            canEditSlice(row, cfg) &&
            (manualSouthWithoutNt || !READONLY_KEYS[pk]) &&
            !row.pd_pd_formula_derived_row
        );
    }

    function perimeterVariantYearOutOfRange(row, year) {
        if (row.pd_pd_skip_perimeter_variant_year_bounds) {
            return false;
        }
        var code = row.perimeter_variant_code;
        if (!code) {
            return false;
        }
        var yr = parseInt(year, 10);
        if (isNaN(yr)) {
            return false;
        }
        var fromYear = row.perimeter_variant_from_year;
        var toYear = row.perimeter_variant_to_year;
        if (fromYear != null && yr < parseInt(fromYear, 10)) {
            return true;
        }
        if (toYear != null && yr > parseInt(toYear, 10)) {
            return true;
        }
        return false;
    }

    function sakhaMembershipYearOutOfRange(row, year) {
        var yr = parseInt(year, 10);
        if (isNaN(yr)) {
            return false;
        }
        var throughYear = parseInt(
            String(
                row.sakha_membership_through_year != null
                    ? row.sakha_membership_through_year
                    : "2018"
            ),
            10
        );
        if (!Number.isFinite(throughYear)) {
            throughYear = 2018;
        }
        if (row.pd_pd_sakha_tites_through_year_row) {
            return yr > throughYear;
        }
        if (row.pd_pd_sakha_oes_east_from_year_row) {
            return yr <= throughYear;
        }
        return false;
    }

    function summaryYearOutOfRange(row, year) {
        return (
            perimeterVariantYearOutOfRange(row, year) ||
            sakhaMembershipYearOutOfRange(row, year)
        );
    }

    function isHistParameterAllowed(row, cfg) {
        var summary = cfg.active_summary || "";
        if (summary !== "oes" && summary !== "fo" && summary !== "ez") {
            return true;
        }
        return ["max_power", "peak_datetime", "avg_temp"].indexOf(row.parameter_key || "") >= 0;
    }

    function markHistCellDisabled(td) {
        if (!td) {
            return;
        }
        td.classList.add("summary-hist-cell-disabled");
        td.setAttribute("aria-disabled", "true");
        td.tabIndex = -1;
    }

    function clearHistCellDisabled(td) {
        if (!td) {
            return;
        }
        td.classList.remove("summary-hist-cell-disabled");
        td.removeAttribute("aria-disabled");
        td.removeAttribute("tabindex");
    }

    function syncHistCellInteractivity(histTd, row, cfg) {
        if (!histTd) {
            return;
        }
        var allowed = isHistParameterAllowed(row, cfg);
        var histInp = histTd.querySelector("input.fuel-param-input, textarea.fuel-param-input");
        if (!allowed) {
            if (histInp) {
                histInp.remove();
            }
            histTd.textContent = "";
            histTd.removeAttribute("title");
            markHistCellDisabled(histTd);
            return;
        }
        clearHistCellDisabled(histTd);
    }

    function canEditHistCell(row, cfg) {
        if (!canEditCell(row, cfg)) {
            return false;
        }
        return isHistParameterAllowed(row, cfg);
    }

    function planHideYearCell(row, year, yearIsPlan, cfg) {
        if (isCoeffRoute(cfg)) {
            return coeffPlanHideYear(row, year, yearIsPlan, cfg || {});
        }
        var pk = row.parameter_key || "";
        return !!yearIsPlan[String(year)] && pk !== "max_power";
    }

    function buildParameterCellHtml(row, cfg) {
        var label = escapeHtml(row.parameter_label || "");
        var tip =
            row.pd_parameter_formula_tooltip ||
            (isFoCoeffCzTotalRow(row) ? row.pd_fo_coeff_cz_total_tooltip : "") ||
            "";
        var inner;
        if (tip) {
            inner =
                '<span class="text-wrap">' +
                label +
                '<i class="bi bi-info-circle text-primary ms-1" data-bs-toggle="tooltip" data-bs-placement="top" title="' +
                escapeAttr(tip) +
                '" style="cursor: help; font-size: 0.9em; vertical-align: -0.1em;" aria-label="Формула расчёта"></i></span>';
        } else {
            inner = label;
        }
        if (isCoeffRoute(cfg)) {
            return '<div class="pd-coeff-param-name-line">' + inner + "</div>";
        }
        return inner;
    }

    function buildHistCell(row, cfg) {
        var td = document.createElement("td");
        td.className = "text-center summary-hist-cell";
        if (!isHistParameterAllowed(row, cfg)) {
            markHistCellDisabled(td);
        }
        var pk = row.parameter_key || "";
        var tooltip = row.hist_numeric_tooltip || "";
        if (isHistParameterAllowed(row, cfg)) {
            if (pk === "peak_datetime") {
                var peakTitle =
                    (tooltip ? escapeAttr(tooltip) + " — " : "") +
                    "Год (ГГГГ) или дата и время (мск): ДД.ММ.ГГГГ ЧЧ:ММ";
                td.setAttribute("title", peakTitle.replace(/&#39;/g, "'"));
            } else if (tooltip) {
                td.setAttribute("title", tooltip);
            }
        }

        if (canEditHistCell(row, cfg)) {
            clearHistCellDisabled(td);
            var hv = row.hist_value && row.hist_value !== "—" ? String(row.hist_value) : "";
            var inp = document.createElement("input");
            inp.type = "text";
            inp.autocomplete = "off";
            inp.className = "form-control form-control-lg text-center fuel-param-input";
            inp.value = hv;
            inp.setAttribute("data-initial", hv);
            inp.setAttribute("data-slice", "hist");
            inp.setAttribute("data-parameter-key", pk);
            inp.setAttribute("data-model", row.demand_model_name || "");
            inp.setAttribute(
                "aria-label",
                (row.entity_label || "") + " — " + (row.parameter_label || "") + ", исторический максимум"
            );
            if (pk === "peak_datetime") {
                inp.setAttribute("data-bs-toggle", "tooltip");
                inp.setAttribute("data-bs-placement", "top");
                inp.setAttribute("data-bs-custom-class", "power-demand-datetime-format-tooltip");
            } else {
                inp.inputMode = "decimal";
            }
            if (tooltip) {
                inp.setAttribute("data-db-full", tooltip);
            }
            if (row.hist_row_id != null) {
                inp.setAttribute("data-row-id", String(row.hist_row_id));
            }
            if (row.parent_fk_column) {
                inp.setAttribute("data-parent-fk", row.parent_fk_column);
            }
            if (row.parent_id != null) {
                inp.setAttribute("data-parent-id", String(row.parent_id));
            }
            td.appendChild(inp);
        } else if (isHistParameterAllowed(row, cfg)) {
            clearHistCellDisabled(td);
            td.textContent = row.hist_value != null ? String(row.hist_value) : "";
        } else {
            markHistCellDisabled(td);
        }
        return td;
    }

    function buildYearCell(row, year, ix, cfg, yearIsPlan) {
        var td = document.createElement("td");
        var pk = row.parameter_key || "";
        var values = row.year_values || [];
        var rowIds = row.year_row_ids || [];
        var tooltips = row.year_numeric_tooltips || [];
        var value =
            ix < values.length && values[ix] != null ? String(values[ix]) : "—";
        var yrid = ix < rowIds.length ? rowIds[ix] : null;
        var yrTt = ix < tooltips.length ? tooltips[ix] || "" : "";
        var pvYearOutOfRange = summaryYearOutOfRange(row, year);
        if (pvYearOutOfRange) {
            value = "—";
            yrid = null;
            yrTt = "";
        }
        var planHide = planHideYearCell(row, year, yearIsPlan, cfg);
        var coeff = isCoeffRoute(cfg);
        var baseYear = coeffBaseYear(cfg);

        td.className = "text-center summary-year-cell";
        if (coeff) {
            td.classList.add("summary-year-mw-cell");
            td.setAttribute("data-summary-year", String(year));
            if (baseYear != null) {
                td.setAttribute(
                    "data-coeff-year-segment",
                    coeffYearSegment(year, baseYear)
                );
            }
        }
        if (planHide) {
            td.classList.add("summary-plan-empty");
        }
        if (cfg.pd_pd_max_year_segments) {
            td.setAttribute("data-ec-summary-col-year", String(year));
        }
        if (pk === "peak_datetime") {
            td.setAttribute(
                "title",
                (yrTt ? yrTt + " — " : "") +
                    "Дата и время (мск): ДД.ММ.ГГГГ ЧЧ:ММ или год ГГГГ"
            );
        } else if (yrTt) {
            td.setAttribute("title", yrTt);
        }

        if (planHide) {
            return td;
        }

        var uesReadonlyCoeffDisplay =
            coeff &&
            row.demand_model_name === "UnionEnergySystemDemandParameter" &&
            (pk === "calculated_max_power_mw" ||
                pk === "calculated_combined_on_ees_mw");

        if (canEditCell(row, cfg) && !pvYearOutOfRange) {
            var yv = value !== "—" ? value : "";
            if (pk === "peak_datetime") {
                var ta = document.createElement("textarea");
                ta.rows = 2;
                ta.autocomplete = "off";
                ta.className =
                    "form-control form-control-lg text-center fuel-param-input power-demand-summary-datetime-field";
                ta.value = yv;
                ta.setAttribute("data-initial", yv);
                ta.setAttribute("data-slice", String(year));
                ta.setAttribute("data-bs-toggle", "tooltip");
                ta.setAttribute("data-bs-placement", "top");
                ta.setAttribute("data-bs-custom-class", "power-demand-datetime-format-tooltip");
                ta.setAttribute("data-parameter-key", pk);
                ta.setAttribute("data-model", row.demand_model_name || "");
                ta.setAttribute(
                    "aria-label",
                    (row.entity_label || "") +
                        " — " +
                        (row.parameter_label || "") +
                        ", " +
                        year +
                        " год"
                );
                if (yrTt) {
                    ta.setAttribute("data-db-full", yrTt);
                }
                if (yrid != null) {
                    ta.setAttribute("data-row-id", String(yrid));
                }
                if (row.parent_fk_column) {
                    ta.setAttribute("data-parent-fk", row.parent_fk_column);
                }
                if (row.parent_id != null) {
                    ta.setAttribute("data-parent-id", String(row.parent_id));
                }
                td.appendChild(ta);
            } else {
                var inp = document.createElement("input");
                inp.type = "text";
                inp.inputMode = "decimal";
                inp.autocomplete = "off";
                inp.className = "form-control form-control-lg text-center fuel-param-input";
                inp.value = yv;
                inp.setAttribute("data-initial", yv);
                inp.setAttribute("data-slice", String(year));
                inp.setAttribute("data-parameter-key", pk);
                inp.setAttribute("data-model", row.demand_model_name || "");
                inp.setAttribute(
                    "aria-label",
                    (row.entity_label || "") +
                        " — " +
                        (row.parameter_label || "") +
                        ", " +
                        year +
                        " год"
                );
                if (yrTt) {
                    inp.setAttribute("title", yrTt);
                    inp.setAttribute("data-db-full", yrTt);
                }
                if (yrid != null) {
                    inp.setAttribute("data-row-id", String(yrid));
                }
                if (row.parent_fk_column) {
                    inp.setAttribute("data-parent-fk", row.parent_fk_column);
                }
                if (row.parent_id != null) {
                    inp.setAttribute("data-parent-id", String(row.parent_id));
                }
                td.appendChild(inp);
            }
        } else if (uesReadonlyCoeffDisplay || isFoCoeffCzTotalRow(row)) {
            var ro = document.createElement("input");
            ro.type = "text";
            ro.readOnly = true;
            ro.tabIndex = -1;
            ro.lang = "ru";
            ro.className =
                "form-control form-control-lg text-center pd-coeff-display-mw" +
                (isFoCoeffCzTotalRow(row) ? " pd-fo-cz-total-mw" : "");
            ro.value = value;
            ro.setAttribute(
                "aria-label",
                (row.entity_label || "") +
                    " — " +
                    (row.parameter_label || "") +
                    ", " +
                    year +
                    " год"
            );
            if (yrTt) {
                ro.setAttribute("title", yrTt);
                ro.setAttribute("data-db-full", yrTt);
            }
            td.appendChild(ro);
        } else {
            td.textContent = value;
        }
        return td;
    }

    function appendCoeffMixinEmptyCells(tr, row) {
        var pk = row.parameter_key || "";
        var mixinUi =
            pk !== "peak_datetime" &&
            pk !== "max_power" &&
            !isFoCoeffCzTotalRow(row);
        var i;
        if (mixinUi || pk === "max_power") {
            for (i = 0; i < 4; i++) {
                var empty = document.createElement("td");
                empty.className = "summary-coeff-mixin-cell summary-coeff-mixin-empty";
                tr.appendChild(empty);
            }
            var manual = document.createElement("td");
            manual.className =
                "summary-coeff-mixin-cell summary-coeff-mixin-empty summary-coeff-manual-cell";
            tr.appendChild(manual);
            var source = document.createElement("td");
            source.className =
                "summary-coeff-mixin-cell summary-coeff-mixin-empty summary-coeff-source-cell";
            tr.appendChild(source);
            return;
        }
        // peak_datetime / cz totals — заглушки «—»
        var classes = [
            "summary-coeff-gs10-cell",
            "summary-coeff-gs10-minmax-trim-cell",
            "summary-coeff-gs5-cell",
            "summary-coeff-sample-cell",
            "summary-coeff-manual-cell",
            "summary-coeff-source-cell",
        ];
        classes.forEach(function (cls) {
            var td = document.createElement("td");
            td.className = "text-center summary-coeff-mixin-cell " + cls;
            if (
                cls === "summary-coeff-manual-cell" ||
                cls === "summary-coeff-source-cell"
            ) {
                var span = document.createElement("span");
                span.className = "text-muted";
                span.textContent = "—";
                td.appendChild(span);
            } else {
                td.textContent = "—";
            }
            tr.appendChild(td);
        });
    }

    function buildCoeffKRowTr(row, cfg, years, yearIsPlan) {
        var tr = document.createElement("tr");
        var pk = row.parameter_key || "";
        var classes = [
            "summary-kind-" + (row.entity_kind || ""),
            "summary-row-coeff-k",
        ];
        if (
            pk === "peak_datetime" ||
            pk === "avg_temp" ||
            computeRowClasses(row, cfg).indexOf("summary-row-hidden") >= 0
        ) {
            classes.push("summary-row-hidden");
        }
        tr.className = classes.join(" ");
        setDataAttr(tr, "data-parameter-key", row.parameter_key);
        setDataAttr(tr, "data-demand-model-name", row.demand_model_name);
        setDataAttr(tr, "data-id-union-energy-system", row.id_union_energy_system);
        setDataAttr(tr, "data-id-regional-energy-system", row.id_regional_energy_system);
        if (row.id_regional_district != null) {
            setDataAttr(tr, "data-id-regional-district", row.id_regional_district);
        }
        setDataAttr(tr, "data-id-synchronous-area", row.id_synchronous_area);
        setDataAttr(tr, "data-perimeter-variant-code", row.perimeter_variant_code);
        if (row.pd_pd_nt_extra_row) {
            tr.setAttribute("data-pd-pd-nt-extra", "1");
        }
        if (row.pd_pd_summary_table_only_row) {
            tr.setAttribute("data-pd-pd-summary-table-only", "1");
        }
        if (row.pd_pd_territory_detail_row) {
            tr.setAttribute("data-pd-pd-territory-detail", "1");
        }
        if (row.pd_pd_territory_compact_hide_row) {
            tr.setAttribute("data-pd-pd-territory-compact-hide", "1");
        }
        var mixinUi =
            pk !== "peak_datetime" &&
            pk !== "max_power" &&
            !isFoCoeffCzTotalRow(row);
        if (mixinUi) {
            tr.setAttribute(
                "data-pd-coeff-ui-key",
                (row.demand_model_name || "") +
                    "|" +
                    (row.parent_id != null ? String(row.parent_id) : "") +
                    "|" +
                    pk
            );
        }

        var labelTd = document.createElement("td");
        labelTd.className = "summary-parameter-cell summary-coeff-k-label-cell";
        var kTip = row.pd_coeff_k_formula_tooltip || "";
        if (!kTip && isFoCoeffCzTotalRow(row)) {
            kTip = row.pd_fo_coeff_cz_total_tooltip || "";
        }
        labelTd.innerHTML =
            '<span class="pd-coeff-k-label-text">k</span>' +
            (kTip
                ? '<i class="bi bi-info-circle text-primary ms-1" data-bs-toggle="tooltip" data-bs-placement="top" title="' +
                  escapeAttr(kTip) +
                  '" style="cursor: help; font-size: 0.9em; vertical-align: -0.1em;" aria-label="Формула расчёта коэффициента k"></i>'
                : "");
        tr.appendChild(labelTd);

        if (mixinUi) {
            ["gs10", "gs10-minmax-trim", "gs5", "sample"].forEach(function (name) {
                var td = document.createElement("td");
                td.className =
                    "text-center summary-coeff-mixin-cell summary-coeff-" +
                    name +
                    "-cell";
                tr.appendChild(td);
            });
            var manTd = document.createElement("td");
            manTd.className =
                "text-center summary-coeff-mixin-cell summary-coeff-manual-cell";
            var manInp = document.createElement("input");
            manInp.type = "text";
            manInp.inputMode = "decimal";
            manInp.autocomplete = "off";
            manInp.className =
                "form-control form-control-sm text-center pd-coeff-manual-input";
            manInp.value = "";
            manInp.setAttribute(
                "aria-label",
                (row.entity_label || "") +
                    " — " +
                    (row.parameter_label || "") +
                    ", ручной ввод коэффициента совмещения"
            );
            manTd.appendChild(manInp);
            tr.appendChild(manTd);
            var srcTd = document.createElement("td");
            srcTd.className =
                "text-center summary-coeff-mixin-cell summary-coeff-source-cell";
            var sel = document.createElement("select");
            sel.className = "form-select form-select-sm pd-coeff-source-select";
            sel.setAttribute(
                "aria-label",
                (row.entity_label || "") +
                    " — " +
                    (row.parameter_label || "") +
                    ", используемый коэффициент совмещения"
            );
            [
                ["gs5", "СиПР (5 лет)", true],
                ["sample", "период", false],
                ["manual", "ручной ввод", false],
            ].forEach(function (opt) {
                var o = document.createElement("option");
                o.value = opt[0];
                o.textContent = opt[1];
                if (opt[2]) {
                    o.selected = true;
                }
                sel.appendChild(o);
            });
            srcTd.appendChild(sel);
            tr.appendChild(srcTd);
        } else {
            for (var mi = 0; mi < 6; mi++) {
                var dash = document.createElement("td");
                dash.className = "text-center summary-coeff-mixin-cell";
                dash.textContent = "—";
                tr.appendChild(dash);
            }
        }

        var kValues = row.year_k_values || [];
        var kTooltips = row.year_k_full_tooltips || [];
        var baseYear = coeffBaseYear(cfg);
        years.forEach(function (year, ix) {
            var td = document.createElement("td");
            var kDisp =
                ix < kValues.length && kValues[ix] != null
                    ? String(kValues[ix])
                    : "—";
            var kTt = ix < kTooltips.length ? kTooltips[ix] || "" : "";
            var planHide = coeffPlanHideYear(row, year, yearIsPlan, cfg);
            td.className = "text-center summary-year-cell summary-year-k-cell";
            if (planHide) {
                td.classList.add("summary-plan-empty");
            }
            td.setAttribute("data-summary-year", String(year));
            if (baseYear != null) {
                td.setAttribute(
                    "data-coeff-year-segment",
                    coeffYearSegment(year, baseYear)
                );
            }
            if (kTt && !planHide) {
                td.setAttribute("title", kTt);
            }
            td.textContent = kDisp;
            tr.appendChild(td);
        });
        return tr;
    }

    function buildPerimeterVariantCell(row, cfg, entityRowspan) {
        var td = document.createElement("td");
        td.className =
            "summary-perimeter-variant-cell text-center align-middle text-wrap";
        td.rowSpan = entityRowspan > 0 ? entityRowspan : 1;
        td.setAttribute("data-original-rowspan", String(row.entity_rowspan || 1));

        if (cfg.can_edit_summary_cells && row.show_perimeter_variant_select) {
            var wrap = document.createElement("div");
            wrap.className = "pd-ec-perimeter-variant-select-wrap";
            var sel = document.createElement("select");
            sel.className = "form-select form-select-sm pd-ec-perimeter-variant-select";
            sel.setAttribute("data-initial", row.perimeter_variant_code || "");
            sel.setAttribute("data-demand-model-name", row.demand_model_name || "");
            sel.setAttribute("data-block-kind", "base");
            sel.title =
                "Вариант периметра для записи и чтения данных этого блока в БД";
            if (row.parent_fk_column) {
                sel.setAttribute("data-parent-fk", row.parent_fk_column);
            }
            if (row.parent_id != null) {
                sel.setAttribute("data-parent-id", String(row.parent_id));
            }
            var optEmpty = document.createElement("option");
            optEmpty.value = "";
            optEmpty.textContent = "не указано";
            if (!row.perimeter_variant_code) {
                optEmpty.selected = true;
            }
            sel.appendChild(optEmpty);
            (row.perimeter_variant_options || []).forEach(function (opt) {
                var o = document.createElement("option");
                o.value = opt.code || "";
                o.textContent = opt.label || opt.code || "";
                if ((row.perimeter_variant_code || "") === (opt.code || "")) {
                    o.selected = true;
                }
                sel.appendChild(o);
            });
            var lbl = document.createElement("span");
            lbl.className = "pd-ec-perimeter-variant-select-label";
            lbl.setAttribute("aria-hidden", "true");
            wrap.appendChild(sel);
            wrap.appendChild(lbl);
            td.appendChild(wrap);
            var selectedLabel = row.perimeter_variant_label || "";
            var opt = sel.options[sel.selectedIndex];
            if (opt) {
                selectedLabel = String(opt.textContent || "").trim() || selectedLabel;
            }
            lbl.textContent = selectedLabel || "не указано";
            sel.style.height = "auto";
            sel.style.minHeight = Math.max(lbl.scrollHeight + 8, 32) + "px";
        } else {
            var span = document.createElement("span");
            span.className = "text-wrap";
            span.textContent =
                row.perimeter_variant_label ||
                row.perimeter_variant_code ||
                "не указано";
            td.appendChild(span);
        }
        return td;
    }

    function buildEntityCell(row, entityRowspan, cfg) {
        var td = document.createElement("td");
        td.className =
            "summary-entity-cell summary-depth-" + (row.entity_depth || 0);
        td.rowSpan = entityRowspan > 0 ? entityRowspan : 1;
        td.setAttribute("data-original-rowspan", String(row.entity_rowspan || 1));
        if (isCoeffRoute(cfg)) {
            td.setAttribute(
                "data-entity-rowspan-with-k",
                String((row.entity_rowspan || 1) * 2)
            );
        }
        var div = document.createElement("div");
        div.style.paddingLeft = String((row.entity_depth || 0) * 1.5) + "rem";
        div.textContent = row.entity_label || "";
        if (row.pd_pd_decentralized_zone_mark) {
            var mark = document.createElement("span");
            mark.className = "pd-pd-dz-mark ms-1";
            mark.setAttribute("data-bs-toggle", "tooltip");
            mark.setAttribute("data-bs-placement", "top");
            mark.title = "Форма О-1";
            mark.setAttribute("aria-label", "Форма О-1");
            mark.textContent = "О-1";
            div.appendChild(document.createTextNode(" "));
            div.appendChild(mark);
        }
        td.appendChild(div);
        return td;
    }

    function buildNoteCell(row, cfg, noteRowspan) {
        var td = document.createElement("td");
        td.className = "summary-entity-note-cell text-start";
        td.rowSpan = noteRowspan > 0 ? noteRowspan : 1;
        td.setAttribute("data-original-note-rowspan", String(row.entity_rowspan || 1));
        if (isCoeffRoute(cfg)) {
            td.setAttribute(
                "data-original-note-rowspan-with-k",
                String((row.entity_rowspan || 1) * 2)
            );
        }
        var wrap = document.createElement("div");
        wrap.className = "summary-entity-note-wrap";
        var noteText = row.entity_note_text != null ? String(row.entity_note_text) : "";
        if (canEditSlice(row, cfg)) {
            var ta = document.createElement("textarea");
            ta.rows = 1;
            ta.autocomplete = "off";
            ta.className =
                "form-control form-control-sm fuel-param-input power-demand-summary-note-field";
            ta.value = noteText;
            ta.setAttribute("data-initial", noteText);
            ta.setAttribute("data-slice", "hist");
            ta.setAttribute("data-parameter-key", "entity_note");
            if (row.demand_model_name) {
                ta.setAttribute("data-model", row.demand_model_name);
            }
            if (row.entity_note_row_id != null) {
                ta.setAttribute("data-row-id", String(row.entity_note_row_id));
            }
            if (row.parent_fk_column) {
                ta.setAttribute("data-parent-fk", row.parent_fk_column);
            }
            if (row.parent_id != null) {
                ta.setAttribute("data-parent-id", String(row.parent_id));
            }
            ta.setAttribute("aria-label", (row.entity_label || "") + " — примечание");
            wrap.appendChild(ta);
        } else {
            var span = document.createElement("span");
            span.className = "text-break";
            span.textContent = noteText;
            wrap.appendChild(span);
        }
        td.appendChild(wrap);
        return td;
    }

    function buildRowTr(row, cfg, years, yearIsPlan, showPerimeterCol, showHistCol) {
        var tr = document.createElement("tr");
        tr.className = computeRowClasses(row, cfg);
        setDataAttr(tr, "data-parameter-key", row.parameter_key);
        setDataAttr(tr, "data-demand-model-name", row.demand_model_name);
        setDataAttr(tr, "data-id-union-energy-system", row.id_union_energy_system);
        setDataAttr(tr, "data-id-regional-energy-system", row.id_regional_energy_system);
        if (row.id_regional_district != null) {
            setDataAttr(tr, "data-id-regional-district", row.id_regional_district);
        } else if (
            row.parent_fk_column === "id_regional_district" &&
            row.parent_id != null
        ) {
            setDataAttr(tr, "data-id-regional-district", row.parent_id);
        }
        if (row.id_energy_unit != null) {
            setDataAttr(tr, "data-id-energy-unit", row.id_energy_unit);
        } else if (
            row.parent_fk_column === "id_energy_unit" &&
            row.parent_id != null
        ) {
            setDataAttr(tr, "data-id-energy-unit", row.parent_id);
        }
        setDataAttr(tr, "data-parent-fk-column", row.parent_fk_column);
        setDataAttr(tr, "data-parent-id", row.parent_id);
        setDataAttr(tr, "data-id-energy-zone", row.id_energy_zone);
        setDataAttr(tr, "data-id-synchronous-area", row.id_synchronous_area);
        setDataAttr(tr, "data-perimeter-variant-code", row.perimeter_variant_code);
        setDataAttr(
            tr,
            "data-perimeter-variant-from-year",
            row.perimeter_variant_from_year
        );
        setDataAttr(tr, "data-perimeter-variant-to-year", row.perimeter_variant_to_year);
        if (row.pd_pd_nt_extra_row) {
            tr.setAttribute("data-pd-pd-nt-extra", "1");
        }
        if (row.pd_pd_sakha_tites_through_year_row) {
            tr.setAttribute("data-pd-pd-sakha-tites-through-year", "1");
        }
        if (row.pd_pd_sakha_oes_east_from_year_row) {
            tr.setAttribute("data-pd-pd-sakha-oes-east-from-year", "1");
        }
        if (row.sakha_membership_through_year != null) {
            tr.setAttribute(
                "data-sakha-membership-through-year",
                String(row.sakha_membership_through_year)
            );
        }
        if (row.pd_pd_aggregation_level_row) {
            tr.setAttribute("data-pd-pd-aggregation-level", "1");
        }
        if (row.pd_pd_skip_empty_hide_row) {
            tr.setAttribute("data-pd-pd-skip-empty-hide", "1");
        }
        if (row.pd_pd_territory_detail_row) {
            tr.setAttribute("data-pd-pd-territory-detail", "1");
        }
        if (row.pd_pd_territory_compact_hide_row) {
            tr.setAttribute("data-pd-pd-territory-compact-hide", "1");
        }
        if (row.pd_pd_summary_table_only_row) {
            tr.setAttribute("data-pd-pd-summary-table-only", "1");
        }
        if (row.pd_pd_ee_row) {
            tr.setAttribute("data-pd-pd-ee-row", "1");
        }
        if (row.pd_pd_chi_row) {
            tr.setAttribute("data-pd-pd-chi-row", "1");
        }
        if (row.pd_pd_formula_derived_row) {
            tr.setAttribute("data-pd-pd-formula-derived", "1");
        }
        if (row.pd_pd_south_ues_without_nt_manual_row) {
            tr.setAttribute("data-pd-pd-south-without-nt-manual", "1");
        }
        if (row.pd_pd_verify_a_parameter_key) {
            tr.setAttribute("data-pd-pd-verify-a", row.pd_pd_verify_a_parameter_key);
            tr.setAttribute("data-pd-pd-verify-b", row.pd_pd_verify_b_parameter_key);
        }
        tr.setAttribute("data-entity-block-size", String(row.entity_rowspan || 1));
        if (row.show_entity_cell) {
            tr.setAttribute("data-is-block-start", "1");
        }
        if (
            row.show_entity_cell &&
            (row.pd_pd_entity_label_compact_nt ||
                row.pd_pd_entity_label_nt_detail ||
                row.pd_pd_entity_label_territory_compact)
        ) {
            tr.setAttribute("data-pd-pd-entity-label-full", row.entity_label || "");
            if (row.pd_pd_entity_label_compact_nt) {
                tr.setAttribute(
                    "data-pd-pd-entity-label-compact-nt",
                    row.pd_pd_entity_label_compact_nt
                );
            }
            if (row.pd_pd_entity_label_nt_detail) {
                tr.setAttribute(
                    "data-pd-pd-entity-label-nt-detail",
                    row.pd_pd_entity_label_nt_detail
                );
            }
            if (row.pd_pd_entity_label_territory_compact) {
                tr.setAttribute(
                    "data-pd-pd-entity-label-territory-compact",
                    row.pd_pd_entity_label_territory_compact
                );
            }
        }

        if (row.pd_pd_aggregation_level_row && SUMMARY_SCOPES[cfg.active_summary || ""]) {
            var aggHeaderTd = document.createElement("td");
            aggHeaderTd.colSpan = isCoeffRoute(cfg)
                ? 9 + years.length + (showPerimeterCol ? 1 : 0)
                : pdSummaryAggregationLevelColspan(years.length);
            aggHeaderTd.setAttribute("data-pd-aggregation-header-cell", "1");
            aggHeaderTd.className =
                "summary-entity-cell summary-depth-" +
                (row.entity_depth || 0) +
                " fw-semibold text-center";
            aggHeaderTd.textContent = pdSummaryAggregationLevelLabel(row);
            tr.appendChild(aggHeaderTd);
            return tr;
        }

        if (row.pd_pd_aggregation_level_full_row) {
            var aggTd = document.createElement("td");
            var nCols = isCoeffRoute(cfg)
                ? 9 + years.length + (showPerimeterCol ? 1 : 0)
                : (showHistCol ? 3 : 2) +
                  years.length +
                  1 +
                  (showPerimeterCol ? 1 : 0);
            aggTd.colSpan = nCols;
            aggTd.className =
                "summary-entity-cell summary-depth-" +
                (row.entity_depth || 0) +
                " fw-semibold text-center";
            aggTd.textContent = pdSummaryAggregationLevelLabel(row);
            tr.appendChild(aggTd);
            return tr;
        }

        var entityRs = row.entity_rowspan || 1;
        if (row.show_entity_cell) {
            if (showPerimeterCol && !row.pd_pd_aggregation_level_row) {
                tr.appendChild(buildPerimeterVariantCell(row, cfg, entityRs));
            }
            tr.appendChild(buildEntityCell(row, entityRs, cfg));
        }

        var paramTd = document.createElement("td");
        paramTd.className = "summary-parameter-cell";
        paramTd.innerHTML = buildParameterCellHtml(row, cfg);
        tr.appendChild(paramTd);

        if (isCoeffRoute(cfg)) {
            appendCoeffMixinEmptyCells(tr, row);
        }

        if (showHistCol) {
            tr.appendChild(buildHistCell(row, cfg));
        }

        years.forEach(function (year, ix) {
            tr.appendChild(buildYearCell(row, year, ix, cfg, yearIsPlan));
        });

        if (row.show_entity_note_cell) {
            tr.appendChild(buildNoteCell(row, cfg, entityRs));
        }

        return tr;
    }

    /**
     * Одна логическая строка → 1–2 <tr> (на coeff — показатель + строка k).
     * Если следом идёт «Проверка …» для этого показателя — k откладывается
     * и рисуется сразу после проверки (расчётный → проверка → k).
     * opts: { prevRow, nextRow } из соседних summary_rows.
     */
    function buildRowNodes(
        row,
        cfg,
        years,
        yearIsPlan,
        showPerimeterCol,
        showHistCol,
        opts
    ) {
        opts = opts || {};
        var prevRow = opts.prevRow || null;
        var nextRow = opts.nextRow || null;
        var tr = buildRowTr(
            row,
            cfg,
            years,
            yearIsPlan,
            showPerimeterCol,
            showHistCol
        );
        var nodes = [tr];
        if (!isCoeffRoute(cfg)) {
            return nodes;
        }
        var deferOwnK =
            shouldBuildCoeffKRow(row) &&
            nextRow &&
            isVerifyRowForParameter(nextRow, row.parameter_key);
        if (shouldBuildCoeffKRow(row) && !deferOwnK) {
            nodes.push(buildCoeffKRowTr(row, cfg, years, yearIsPlan));
        }
        if (
            isVerifyMergeRow(row) &&
            prevRow &&
            isVerifyRowForParameter(row, prevRow.parameter_key) &&
            shouldBuildCoeffKRow(prevRow)
        ) {
            nodes.push(buildCoeffKRowTr(prevRow, cfg, years, yearIsPlan));
        }
        return nodes;
    }

    function injectLiveCalcData(payload) {
        if (!payload || !payload.pd_oes_live_calc_js) {
            return;
        }
        var el = document.getElementById("pd-oes-live-calc-data");
        if (el) {
            el.textContent = JSON.stringify(payload.pd_oes_live_calc_js);
            return;
        }
        el = document.createElement("script");
        el.type = "application/json";
        el.id = "pd-oes-live-calc-data";
        el.textContent = JSON.stringify(payload.pd_oes_live_calc_js);
        document.body.appendChild(el);
    }

    function parameterInsertOrder(cfg) {
        var seg = (cfg && cfg.segments) || shellConfig.segments || {};
        return (seg.core_parameter_keys || []).concat(seg.calc_max_parameter_keys || []);
    }

    function rowBlockFingerprint(row, includeNt) {
        var nt = row.pd_pd_nt_extra_row ? "1" : "0";
        if (!includeNt) {
            nt = "0";
        }
        return [
            row.demand_model_name || "",
            row.parent_fk_column || "",
            row.parent_id != null ? String(row.parent_id) : "",
            nt,
            row.id_union_energy_system != null ? String(row.id_union_energy_system) : "",
            row.id_regional_energy_system != null ? String(row.id_regional_energy_system) : "",
            row.id_regional_district != null ? String(row.id_regional_district) : "",
            row.id_energy_zone != null ? String(row.id_energy_zone) : "",
            row.id_energy_unit != null ? String(row.id_energy_unit) : "",
            row.id_synchronous_area != null ? String(row.id_synchronous_area) : "",
            row.entity_kind || "",
            row.perimeter_variant_code != null ? String(row.perimeter_variant_code) : "",
            row.pd_pd_aggregation_level_row ? row.entity_label || "" : "",
        ].join("|");
    }

    function trBlockFingerprint(startTr, includeNt) {
        var nt =
            startTr.getAttribute("data-pd-pd-nt-extra") === "1" ? "1" : "0";
        if (!includeNt) {
            nt = "0";
        }
        return [
            startTr.getAttribute("data-demand-model-name") || "",
            startTr.getAttribute("data-parent-fk-column") || "",
            startTr.getAttribute("data-parent-id") || "",
            nt,
            startTr.getAttribute("data-id-union-energy-system") || "",
            startTr.getAttribute("data-id-regional-energy-system") || "",
            startTr.getAttribute("data-id-regional-district") || "",
            startTr.getAttribute("data-id-energy-zone") || "",
            startTr.getAttribute("data-id-energy-unit") || "",
            startTr.getAttribute("data-id-synchronous-area") || "",
            startTr.className.match(/summary-kind-(\S+)/)
                ? startTr.className.match(/summary-kind-(\S+)/)[1]
                : "",
            startTr.getAttribute("data-perimeter-variant-code") || "",
            startTr.getAttribute("data-pd-pd-aggregation-level") === "1"
                ? (startTr.querySelector("td") &&
                      startTr.querySelector("td").textContent) ||
                  ""
                : "",
        ].join("|");
    }

    function collectBlockRows(startTr) {
        var blockRows = [];
        var tr = startTr;
        while (tr) {
            if (tr.classList.contains("summary-row-param")) {
                if (
                    blockRows.length > 0 &&
                    tr.getAttribute("data-is-block-start") === "1"
                ) {
                    break;
                }
                blockRows.push(tr);
            }
            tr = tr.nextElementSibling;
        }
        if (blockRows.length) {
            var rs = String(blockRows.length);
            blockRows[0].setAttribute("data-entity-block-size", rs);
            blockRows.forEach(function (rowTr) {
                rowTr.setAttribute("data-entity-block-size", rs);
            });
        }
        return blockRows;
    }

    function rowCountsForBlockRowspan(tr) {
        if (tr.classList.contains("summary-row-empty-block-hidden")) {
            return false;
        }
        return !tr.classList.contains("summary-row-hidden");
    }

    /** Строка k для показателя (на coeff может идти после «Проверка …»). */
    function coeffKRowAfterParamTr(paramTr) {
        if (!paramTr) {
            return null;
        }
        var pk = paramTr.getAttribute("data-parameter-key") || "";
        if (!pk || pk === "max_power") {
            return null;
        }
        var nx = paramTr.nextElementSibling;
        while (
            nx &&
            nx.classList.contains("summary-row-param") &&
            nx.classList.contains("pd-pd-verify-for-row")
        ) {
            var aKey = nx.getAttribute("data-pd-pd-verify-a") || "";
            var vPk = nx.getAttribute("data-parameter-key") || "";
            if (aKey === pk || vPk === "verify_for_" + pk) {
                nx = nx.nextElementSibling;
                continue;
            }
            break;
        }
        if (
            nx &&
            nx.classList.contains("summary-row-coeff-k") &&
            (nx.getAttribute("data-parameter-key") || "") === pk
        ) {
            return nx;
        }
        return null;
    }

    /** Куда вставлять строку сегмента относительно уже отрисованного блока. */
    var MERGE_ROW_INSERT_AFTER = {
        calculated_max_power_mw: "max_power",
        calculated_combined_on_ees_mw: "combined_on_ees",
        calculated_max_power_consumption_mw: "max_power",
        calculated_max_ees_russia_mw: "max_power",
        calculated_max_ees_via_oes_mw: "calculated_max_ees_russia_mw",
        calculated_max_ees_via_es_mw: "calculated_max_ees_via_oes_mw",
        calculated_max_sa_mw: "combined_on_ees",
        calculated_max_fo_mw: "max_power",
        calculated_combined_on_cz_mw: "combined_on_cz",
        verify_for_calculated_max_power_mw: "calculated_max_power_mw",
        verify_for_calculated_combined_on_cz_mw: "calculated_combined_on_cz_mw",
        verify_for_calculated_combined_on_ees_mw: "calculated_combined_on_ees_mw",
        verify_for_calculated_max_power_consumption_mw: "calculated_max_power_consumption_mw",
        verify_for_calculated_max_ees_russia_mw: "calculated_max_ees_russia_mw",
        verify_for_calculated_max_ees_via_oes_mw: "calculated_max_ees_via_oes_mw",
        verify_for_calculated_max_ees_via_es_mw: "calculated_max_ees_via_es_mw",
        verify_for_calculated_max_sa_mw: "calculated_max_sa_mw",
        peak_combined_on_ees_usage_hours: "combined_on_ees",
        peak_combined_on_cz_usage_hours: "combined_on_cz",
        peak_combined_on_oes_usage_hours: "combined_on_oes",
        peak_combined_on_es_usage_hours: "combined_on_es",
        peak_combined_on_fo_usage_hours: "combined_on_fo",
        peak_combined_on_ez_usage_hours: "combined_on_ez",
    };

    function findInsertBeforeForMergedRow(blockRows, pk, order) {
        if (pk === "energy_consumption_mln_kvt_ch") {
            for (var ei = 0; ei < blockRows.length; ei++) {
                if (
                    (blockRows[ei].getAttribute("data-parameter-key") || "") ===
                    "max_power"
                ) {
                    return blockRows[ei];
                }
            }
            return blockRows.length ? blockRows[0] : null;
        }
        if (pk === "peak_max_power_usage_hours") {
            for (var ci = 0; ci < blockRows.length; ci++) {
                if (
                    (blockRows[ci].getAttribute("data-parameter-key") || "") ===
                    "peak_datetime"
                ) {
                    return blockRows[ci];
                }
            }
        }
        if (
            pk.indexOf("peak_combined_on_") === 0 &&
            pk.slice(-"_usage_hours".length) === "_usage_hours"
        ) {
            var combinedKey = pk.slice("peak_".length, -"_usage_hours".length);
            for (var cai = 0; cai < blockRows.length; cai++) {
                if (
                    (blockRows[cai].getAttribute("data-parameter-key") || "") ===
                    combinedKey
                ) {
                    if (cai + 1 < blockRows.length) {
                        return blockRows[cai + 1];
                    }
                    return null;
                }
            }
        }
        var afterPk = MERGE_ROW_INSERT_AFTER[pk];
        if (afterPk) {
            for (var ai = 0; ai < blockRows.length; ai++) {
                if (
                    (blockRows[ai].getAttribute("data-parameter-key") || "") ===
                    afterPk
                ) {
                    // «Проверка …» — сразу после якоря, перед его строкой k (если есть).
                    if (isVerifyParameterKey(pk)) {
                        var maybeK = coeffKRowAfterParamTr(blockRows[ai]);
                        if (maybeK) {
                            return maybeK;
                        }
                        if (ai + 1 < blockRows.length) {
                            return blockRows[ai + 1];
                        }
                        return null;
                    }
                    if (ai + 1 < blockRows.length) {
                        return blockRows[ai + 1];
                    }
                    return null;
                }
            }
        }
        for (var bi = 0; bi < blockRows.length; bi++) {
            var existingPk = blockRows[bi].getAttribute("data-parameter-key") || "";
            var pkIdx = order.indexOf(pk);
            var exIdx = order.indexOf(existingPk);
            if (pkIdx >= 0 && exIdx >= 0 && pkIdx < exIdx) {
                return blockRows[bi];
            }
        }
        return null;
    }

    function syncBlockRowspans(startTr, blockRows) {
        if (!startTr || !blockRows || !blockRows.length) {
            return;
        }
        var visibleRows = blockRows.filter(rowCountsForBlockRowspan);
        if (!visibleRows.length) {
            return;
        }
        var blockSize = visibleRows.length;
        var rsAll = String(blockRows.length);
        startTr.setAttribute("data-entity-block-size", rsAll);
        blockRows.forEach(function (rowTr) {
            rowTr.setAttribute("data-entity-block-size", rsAll);
        });
        var rs = String(blockSize);
        startTr.setAttribute("data-entity-block-size", rs);
        blockRows.forEach(function (tr) {
            tr.setAttribute("data-entity-block-size", rs);
        });

        var entityTd = null;
        var variantTd = null;
        var noteTd = null;
        for (var k = 0; k < blockRows.length; k++) {
            if (!entityTd) {
                entityTd = blockRows[k].querySelector("td.summary-entity-cell");
            }
            if (!variantTd) {
                variantTd = blockRows[k].querySelector(
                    "td.summary-perimeter-variant-cell"
                );
            }
            if (!noteTd) {
                noteTd = blockRows[k].querySelector("td.summary-entity-note-cell");
            }
        }
        var firstVis = visibleRows[0];
        var paramCell = firstVis.querySelector("td.summary-parameter-cell");
        if (variantTd) {
            var insertBeforeVariant =
                firstVis.querySelector("td.summary-entity-cell") || paramCell;
            if (insertBeforeVariant && variantTd.parentNode !== firstVis) {
                firstVis.insertBefore(variantTd, insertBeforeVariant);
            } else if (!insertBeforeVariant && variantTd.parentNode !== firstVis) {
                firstVis.insertBefore(variantTd, firstVis.firstChild);
            }
            variantTd.setAttribute("rowspan", rs);
        }
        if (entityTd) {
            if (paramCell && entityTd.parentNode !== firstVis) {
                firstVis.insertBefore(entityTd, paramCell);
            }
            entityTd.setAttribute("rowspan", rs);
        }
        if (noteTd && firstVis) {
            // Always append so a misplaced note (e.g. left of param after EE merge)
            // is corrected even when it already lives on firstVis.
            firstVis.appendChild(noteTd);
            noteTd.setAttribute("rowspan", rs);
        }
    }

    function isChiOnlySegmentBlock(block) {
        if (!block || !block.length) {
            return false;
        }
        return block.every(function (row) {
            return !!row.pd_pd_chi_row;
        });
    }

    function isEeOnlySegmentBlock(block) {
        if (!block || !block.length) {
            return false;
        }
        return block.every(function (row) {
            return (
                !!row.pd_pd_ee_row ||
                String(row.parameter_key || "") === "energy_consumption_mln_kvt_ch"
            );
        });
    }

    function orderSegmentLoadNames(segmentNames) {
        var names = (segmentNames || []).slice();
        var scope = (shellConfig && shellConfig.scope) || "";
        if (
            scope === "oes" &&
            (names.indexOf("chi") >= 0 || names.indexOf("ee") >= 0) &&
            names.indexOf("nt_extra") < 0
        ) {
            names.unshift("nt_extra");
        }
        var priority = { nt_extra: 0, calc_max: 1, ee: 2, chi: 3, verify: 4 };
        names.sort(function (a, b) {
            var pa = Object.prototype.hasOwnProperty.call(priority, a)
                ? priority[a]
                : 10;
            var pb = Object.prototype.hasOwnProperty.call(priority, b)
                ? priority[b]
                : 10;
            if (pa !== pb) {
                return pa - pb;
            }
            return names.indexOf(a) - names.indexOf(b);
        });
        var out = [];
        names.forEach(function (name) {
            if (name && out.indexOf(name) < 0) {
                out.push(name);
            }
        });
        return out;
    }

    function baseVariantCodeForNtVariant(code) {
        var s = String(code || "");
        if (s === "with_nt") {
            return "without_nt";
        }
        if (s.indexOf("with_nt_") === 0) {
            return "without_nt_" + s.slice("with_nt_".length);
        }
        return "";
    }

    function rowEntityAnchorWithoutVariant(row) {
        return [
            row.demand_model_name || "",
            row.parent_fk_column || "",
            row.parent_id != null ? String(row.parent_id) : "",
            row.id_union_energy_system != null ? String(row.id_union_energy_system) : "",
            row.id_regional_energy_system != null ? String(row.id_regional_energy_system) : "",
            row.id_regional_district != null ? String(row.id_regional_district) : "",
            row.id_energy_unit != null ? String(row.id_energy_unit) : "",
            row.id_synchronous_area != null ? String(row.id_synchronous_area) : "",
            row.entity_kind || "",
        ].join("|");
    }

    function trEntityAnchorWithoutVariant(startTr) {
        return [
            startTr.getAttribute("data-demand-model-name") || "",
            startTr.getAttribute("data-parent-fk-column") || "",
            startTr.getAttribute("data-parent-id") || "",
            startTr.getAttribute("data-id-union-energy-system") || "",
            startTr.getAttribute("data-id-regional-energy-system") || "",
            startTr.getAttribute("data-id-regional-district") || "",
            startTr.getAttribute("data-id-energy-unit") || "",
            startTr.getAttribute("data-id-synchronous-area") || "",
            startTrEntityKind(startTr),
        ].join("|");
    }

    function findBaseBlockStartForNtRow(tbody, row) {
        var targetBaseCode = baseVariantCodeForNtVariant(row.perimeter_variant_code);
        var targetAnchor = rowEntityAnchorWithoutVariant(row);
        var starts = tbody.querySelectorAll('tr[data-is-block-start="1"]');
        for (var i = 0; i < starts.length; i++) {
            var st = starts[i];
            if (st.getAttribute("data-pd-pd-nt-extra") === "1") {
                continue;
            }
            if (
                targetBaseCode &&
                (st.getAttribute("data-perimeter-variant-code") || "") !== targetBaseCode
            ) {
                continue;
            }
            if (trEntityAnchorWithoutVariant(st) === targetAnchor) {
                return st;
            }
        }
        return null;
    }

    function findNtAggregationLevelTr(tbody, row) {
        var uesId =
            row.id_union_energy_system != null
                ? String(row.id_union_energy_system)
                : "";
        var ezId =
            row.id_energy_zone != null ? String(row.id_energy_zone) : "";
        var fdId =
            row.id_federal_district != null
                ? String(row.id_federal_district)
                : "";
        var aggRows = tbody.querySelectorAll('tr[data-pd-pd-aggregation-level="1"]');
        var fallback = null;
        for (var i = 0; i < aggRows.length; i++) {
            var tr = aggRows[i];
            if (tr.getAttribute("data-pd-pd-nt-extra") !== "1") {
                continue;
            }
            if (!fallback) {
                fallback = tr;
            }
            var trUes = tr.getAttribute("data-id-union-energy-system") || "";
            var trEz = tr.getAttribute("data-id-energy-zone") || "";
            var trFd = tr.getAttribute("data-id-federal-district") || "";
            if (uesId && trUes && trUes === uesId) {
                return tr;
            }
            if (ezId && trEz && trEz === ezId) {
                return tr;
            }
            if (fdId && trFd && trFd === fdId) {
                return tr;
            }
            var labels = startTrEntityLabels(tr);
            var isNtLabel = labels.some(function (lbl) {
                return lbl.indexOf(PD_NEW_TERRITORIES_LABEL) >= 0;
            });
            if (isNtLabel) {
                return tr;
            }
        }
        return fallback;
    }

    function findInsertAfterForSouthNtAggregationRow(tbody, row) {
        var uesId =
            row.id_union_energy_system != null
                ? String(row.id_union_energy_system)
                : "";
        var ezId =
            row.id_energy_zone != null ? String(row.id_energy_zone) : "";
        var fdId =
            row.id_federal_district != null
                ? String(row.id_federal_district)
                : "";
        var lastEnd = null;
        var inBaseSouth = false;
        var starts = tbody.querySelectorAll('tr[data-is-block-start="1"]');
        for (var i = 0; i < starts.length; i++) {
            var st = starts[i];
            var stUes = st.getAttribute("data-id-union-energy-system") || "";
            var stEz = st.getAttribute("data-id-energy-zone") || "";
            var stFd = st.getAttribute("data-id-federal-district") || "";
            var sameScope = false;
            if (uesId && stUes === uesId) {
                sameScope = true;
            } else if (ezId && stEz === ezId) {
                sameScope = true;
            } else if (fdId && stFd === fdId) {
                sameScope = true;
            } else if (
                !uesId &&
                !ezId &&
                !fdId &&
                startTrEntityKind(st) === "perimeter_variant"
            ) {
                var scopeLabels = startTrEntityLabels(st);
                var scopeLbl = scopeLabels.length ? scopeLabels[0] : "";
                if (
                    scopeLbl.indexOf("ОЭС Юга") >= 0 ||
                    scopeLbl.indexOf("Южный ФО") >= 0
                ) {
                    sameScope = true;
                }
            }
            if (!sameScope) {
                if (inBaseSouth) {
                    break;
                }
                continue;
            }
            var pvc = st.getAttribute("data-perimeter-variant-code") || "";
            if (pvc === "with_nt" || pvc.indexOf("with_nt_") === 0) {
                continue;
            }
            if (st.getAttribute("data-pd-pd-aggregation-level") === "1") {
                break;
            }
            if (st.getAttribute("data-pd-pd-nt-extra") === "1") {
                // Уже вставленные субъекты НТ не сдвигают якорь — заголовок
                // должен остаться перед ними.
                break;
            }
            var labels = startTrEntityLabels(st);
            var lbl = labels.length ? labels[0] : "";
            if (
                startTrEntityKind(st) === "perimeter_variant" &&
                lbl.indexOf("без НТ") >= 0
            ) {
                inBaseSouth = true;
                lastEnd = lastTrOfBlock(st);
                continue;
            }
            if (!inBaseSouth) {
                // ЭЗ: якорь — зона ОЭС Юга без варианта периметра.
                if (
                    ezId &&
                    stEz === ezId &&
                    lbl.indexOf("ОЭС Юга") >= 0
                ) {
                    inBaseSouth = true;
                    lastEnd = lastTrOfBlock(st);
                    continue;
                }
                continue;
            }
            lastEnd = lastTrOfBlock(st);
        }
        return lastEnd;
    }

    function findInsertAfterForNtSubtreeRow(tbody, row) {
        var aggTr = findNtAggregationLevelTr(tbody, row);
        if (!aggTr) {
            return null;
        }
        var uesId =
            row.id_union_energy_system != null
                ? String(row.id_union_energy_system)
                : "";
        var after = aggTr;
        var tr = aggTr.nextElementSibling;
        while (tr && tr.classList.contains("summary-row-param")) {
            if (
                tr.getAttribute("data-pd-pd-nt-extra") === "1" &&
                tr.getAttribute("data-pd-pd-aggregation-level") !== "1" &&
                (!uesId || tr.getAttribute("data-id-union-energy-system") === uesId)
            ) {
                after = tr;
                tr = tr.nextElementSibling;
            } else {
                break;
            }
        }
        return after;
    }

    function normalizeEntityLabel(text) {
        return String(text || "")
            .replace(/\s+/g, " ")
            .replace(/\s+(?:ДЗ|О-1)$/, "")
            .trim();
    }

    function startTrEntityKind(startTr) {
        var m = String(startTr.className || "").match(/summary-kind-(\S+)/);
        return m ? m[1] : "";
    }

    function startTrEntityLabels(startTr) {
        var labels = [
            startTr.getAttribute("data-pd-pd-entity-label-full"),
            startTr.getAttribute("data-pd-pd-entity-label-compact-nt"),
            startTr.getAttribute("data-pd-pd-entity-label-nt-detail"),
        ];
        var entityCell = startTr.querySelector("td.summary-entity-cell");
        if (entityCell) {
            var inner = entityCell.querySelector("div");
            labels.push(inner ? inner.textContent : entityCell.textContent);
        }
        return labels.map(normalizeEntityLabel).filter(Boolean);
    }

    function findBlockStartByEntity(tbody, row) {
        var targetKind = String(row.entity_kind || "");
        var targetLabel = normalizeEntityLabel(row.entity_label);
        var targetNt = row.pd_pd_nt_extra_row ? "1" : "0";
        var targetPvc =
            row.perimeter_variant_code != null
                ? String(row.perimeter_variant_code)
                : "";
        var targetSa =
            row.id_synchronous_area != null
                ? String(row.id_synchronous_area)
                : "";
        var targetParentId =
            row.parent_id != null ? String(row.parent_id) : "";
        var targetParentFk = row.parent_fk_column || "";
        var targetDm = row.demand_model_name || "";
        if (!targetKind && !targetSa && !targetParentId) {
            return null;
        }
        var starts = tbody.querySelectorAll('tr[data-is-block-start="1"]');
        for (var i = 0; i < starts.length; i++) {
            var st = starts[i];
            var startNt = st.getAttribute("data-pd-pd-nt-extra") === "1" ? "1" : "0";
            if (startNt !== targetNt) {
                continue;
            }
            if (targetKind && startTrEntityKind(st) !== targetKind) {
                continue;
            }
            if (
                targetPvc &&
                (st.getAttribute("data-perimeter-variant-code") || "") !== targetPvc
            ) {
                continue;
            }
            if (
                targetSa &&
                (st.getAttribute("data-id-synchronous-area") || "") === targetSa
            ) {
                return st;
            }
            if (
                targetDm &&
                targetParentFk &&
                targetParentId &&
                (st.getAttribute("data-demand-model-name") || "") === targetDm &&
                (st.getAttribute("data-parent-fk-column") || "") === targetParentFk &&
                (st.getAttribute("data-parent-id") || "") === targetParentId
            ) {
                return st;
            }
            if (
                targetLabel &&
                startTrEntityLabels(st).indexOf(targetLabel) >= 0
            ) {
                return st;
            }
        }
        return null;
    }

    function blockIsVerifyOnly(block) {
        return (
            block &&
            block.length > 0 &&
            block.every(function (row) {
                return (
                    row.pd_pd_verify_for_row ||
                    String(row.parameter_key || "").indexOf("verify_for_") === 0
                );
            })
        );
    }

    function normInputForCompare(s) {
        return String(s ?? "")
            .trim()
            .replace(/\s+/g, "")
            .replace(",", ".");
    }

    function updateExistingRowTrFromSegmentData(tr, row, cfg, years, yearIsPlan, showHistCol) {
        var values = row.year_values || [];
        var tooltips = row.year_numeric_tooltips || [];
        var yearCells = tr.querySelectorAll("td.summary-year-cell");
        yearCells.forEach(function (td, ix) {
            if (td.classList.contains("summary-plan-empty")) {
                return;
            }
            var value =
                ix < values.length && values[ix] != null ? String(values[ix]) : "—";
            var yrTt = ix < tooltips.length ? tooltips[ix] || "" : "";
            var inp = td.querySelector("input.fuel-param-input, textarea.fuel-param-input");
            if (inp) {
                var initial = inp.getAttribute("data-initial") || "";
                var current = inp.value || "";
                if (normInputForCompare(initial) !== normInputForCompare(current)) {
                    return;
                }
                var nextVal = value !== "—" ? value : "";
                inp.value = nextVal;
                // Синхронизировать initial, иначе value≠data-initial → ложное «грязное»
                // состояние и массовое сохранение / откат после подгрузки сегментов.
                inp.setAttribute("data-initial", nextVal);
                if (yrTt) {
                    inp.setAttribute("title", yrTt);
                    inp.setAttribute("data-db-full", yrTt);
                } else {
                    inp.removeAttribute("title");
                    inp.removeAttribute("data-db-full");
                }
            } else {
                td.textContent = value;
                if (yrTt) {
                    td.setAttribute("title", yrTt);
                } else {
                    td.removeAttribute("title");
                }
            }
        });
        if (showHistCol) {
            var histTd = tr.querySelector("td.summary-hist-cell");
            if (histTd) {
                syncHistCellInteractivity(histTd, row, cfg);
                var histInp = histTd.querySelector("input.fuel-param-input, textarea.fuel-param-input");
                var histValue = row.hist_value != null ? String(row.hist_value) : "";
                var histTt = row.hist_numeric_tooltip || "";
                if (histInp) {
                    var histInitial = histInp.getAttribute("data-initial") || "";
                    var histCurrent = histInp.value || "";
                    if (normInputForCompare(histInitial) !== normInputForCompare(histCurrent)) {
                        // Грязная hist-ячейка: не затираем ввод, но остальные поля строки
                        // (формула и т.п.) ниже всё равно можно обновить.
                    } else {
                        var nextHist =
                            histValue && histValue !== "—" ? histValue : "";
                        histInp.value = nextHist;
                        histInp.setAttribute("data-initial", nextHist);
                        if (histTt) {
                            histInp.setAttribute("data-db-full", histTt);
                        } else {
                            histInp.removeAttribute("data-db-full");
                        }
                    }
                } else if (isHistParameterAllowed(row, cfg)) {
                    histTd.textContent = histValue;
                    if (histTt) {
                        histTd.setAttribute("title", histTt);
                    } else {
                        histTd.removeAttribute("title");
                    }
                }
            }
        }
        if (row.pd_parameter_formula_tooltip) {
            var paramTd = tr.querySelector("td.summary-parameter-cell");
            if (paramTd) {
                paramTd.innerHTML = buildParameterCellHtml(row, cfg);
            }
        }
    }

    function isVerifyParameterKey(pk) {
        return String(pk || "").indexOf("verify_for_") === 0;
    }

    function isVerifyMergeRow(row) {
        return !!(
            row &&
            (row.pd_pd_verify_for_row || isVerifyParameterKey(row.parameter_key))
        );
    }

    function partitionMergeRows(newRows) {
        var calcRows = [];
        var verifyRows = [];
        (newRows || []).forEach(function (row) {
            if (isVerifyMergeRow(row)) {
                verifyRows.push(row);
            } else {
                calcRows.push(row);
            }
        });
        return { calcRows: calcRows, verifyRows: verifyRows };
    }

    /**
     * После вставки расчётных строк вернуть «Проверка …» сразу под якорной
     * строкой показателя (перед строкой k, если она есть).
     */
    function repositionVerifyRowsInBlock(tbody, blockRows) {
        if (!tbody || !blockRows || blockRows.length < 2) {
            return;
        }
        var maxPasses = blockRows.length;
        for (var pass = 0; pass < maxPasses; pass++) {
            var moved = false;
            for (var i = 0; i < blockRows.length; i++) {
                var verifyTr = blockRows[i];
                var verifyPk = verifyTr.getAttribute("data-parameter-key") || "";
                if (!isVerifyParameterKey(verifyPk)) {
                    continue;
                }
                var anchorPk =
                    verifyTr.getAttribute("data-pd-pd-verify-a") ||
                    MERGE_ROW_INSERT_AFTER[verifyPk];
                if (!anchorPk) {
                    continue;
                }
                var anchorTr = null;
                blockRows.forEach(function (tr) {
                    if ((tr.getAttribute("data-parameter-key") || "") === anchorPk) {
                        anchorTr = tr;
                    }
                });
                if (!anchorTr) {
                    continue;
                }
                var anchorIdx = blockRows.indexOf(anchorTr);
                var verifyIdx = blockRows.indexOf(verifyTr);
                var domOk = anchorTr.nextElementSibling === verifyTr;
                var listOk = verifyIdx === anchorIdx + 1;
                if (domOk && listOk) {
                    continue;
                }
                if (!domOk) {
                    // Сразу после якоря: перед k или следующей param-строкой.
                    var ref = anchorTr.nextElementSibling;
                    if (ref === verifyTr) {
                        /* already adjacent */
                    } else if (ref) {
                        tbody.insertBefore(verifyTr, ref);
                    } else {
                        anchorTr.parentNode.appendChild(verifyTr);
                    }
                }
                if (!listOk) {
                    blockRows.splice(verifyIdx, 1);
                    anchorIdx = blockRows.indexOf(anchorTr);
                    blockRows.splice(anchorIdx + 1, 0, verifyTr);
                }
                moved = true;
                break;
            }
            if (!moved) {
                break;
            }
        }
    }

    function repositionAllVerifyRowsInTbody(tbody) {
        if (!tbody) {
            return;
        }
        tbody.querySelectorAll('tr.summary-row-param[data-is-block-start="1"]').forEach(
            function (startTr) {
                repositionVerifyRowsInBlock(tbody, collectBlockRows(startTr));
            }
        );
    }

    function mergeRowsIntoBlock(
        tbody,
        startTr,
        blockRows,
        newRows,
        cfg,
        years,
        yearIsPlan,
        showPerimeterCol,
        showHistCol
    ) {
        var order = parameterInsertOrder(cfg);
        var parts = partitionMergeRows(newRows);
        var orderedNewRows = parts.calcRows.concat(parts.verifyRows);
        orderedNewRows.forEach(function (row) {
            var pk = row.parameter_key || "";
            var existingTr = null;
            blockRows.some(function (tr) {
                if ((tr.getAttribute("data-parameter-key") || "") === pk) {
                    existingTr = tr;
                    return true;
                }
                return false;
            });
            if (existingTr) {
                updateExistingRowTrFromSegmentData(
                    existingTr,
                    row,
                    cfg,
                    years,
                    yearIsPlan,
                    showHistCol
                );
                return;
            }
            var mergeRow = Object.assign({}, row, {
                show_entity_cell: false,
                show_entity_note_cell: false,
            });
            if (
                (mergeRow.pd_pd_verify_for_row ||
                    String(mergeRow.parameter_key || "").indexOf("verify_for_") === 0) &&
                !mergeRow.demand_model_name &&
                startTr
            ) {
                mergeRow.demand_model_name =
                    startTr.getAttribute("data-demand-model-name") || null;
                if (!mergeRow.parent_fk_column) {
                    mergeRow.parent_fk_column =
                        startTr.getAttribute("data-parent-fk-column") || null;
                }
                if (mergeRow.parent_id == null) {
                    var parentId = startTr.getAttribute("data-parent-id");
                    mergeRow.parent_id = parentId ? parseInt(parentId, 10) : null;
                }
                if (mergeRow.id_union_energy_system == null) {
                    var uesId = startTr.getAttribute("data-id-union-energy-system");
                    mergeRow.id_union_energy_system = uesId
                        ? parseInt(uesId, 10)
                        : null;
                }
                if (mergeRow.id_regional_energy_system == null) {
                    var resId = startTr.getAttribute("data-id-regional-energy-system");
                    mergeRow.id_regional_energy_system = resId
                        ? parseInt(resId, 10)
                        : null;
                }
                if (mergeRow.id_regional_district == null) {
                    var rdId = startTr.getAttribute("data-id-regional-district");
                    mergeRow.id_regional_district = rdId ? parseInt(rdId, 10) : null;
                }
                if (mergeRow.id_energy_unit == null) {
                    var euId = startTr.getAttribute("data-id-energy-unit");
                    mergeRow.id_energy_unit = euId ? parseInt(euId, 10) : null;
                }
                if (mergeRow.id_synchronous_area == null) {
                    var saId = startTr.getAttribute("data-id-synchronous-area");
                    mergeRow.id_synchronous_area = saId ? parseInt(saId, 10) : null;
                }
            }
            var newNodes = buildRowNodes(
                mergeRow,
                cfg,
                years,
                yearIsPlan,
                showPerimeterCol,
                showHistCol
            );
            var newTr = newNodes[0];
            var insertBefore = findInsertBeforeForMergedRow(blockRows, pk, order);
            var isEeBeforeBlockStart =
                pk === "energy_consumption_mln_kvt_ch" &&
                insertBefore &&
                insertBefore === startTr &&
                startTr.getAttribute("data-is-block-start") === "1";
            if (insertBefore) {
                newNodes.forEach(function (node) {
                    tbody.insertBefore(node, insertBefore);
                });
                var ix = blockRows.indexOf(insertBefore);
                if (ix >= 0) {
                    blockRows.splice(ix, 0, newTr);
                } else if (
                    insertBefore.classList.contains("summary-row-coeff-k") &&
                    isVerifyParameterKey(pk)
                ) {
                    var anchorPkForList =
                        newTr.getAttribute("data-pd-pd-verify-a") ||
                        MERGE_ROW_INSERT_AFTER[pk];
                    var aIx = -1;
                    if (anchorPkForList) {
                        for (var aj = 0; aj < blockRows.length; aj++) {
                            if (
                                (blockRows[aj].getAttribute("data-parameter-key") ||
                                    "") === anchorPkForList
                            ) {
                                aIx = aj;
                                break;
                            }
                        }
                    }
                    if (aIx >= 0) {
                        blockRows.splice(aIx + 1, 0, newTr);
                    } else {
                        blockRows.push(newTr);
                    }
                } else {
                    blockRows.push(newTr);
                }
            } else {
                var last = blockRows[blockRows.length - 1];
                var anchor = last;
                if (last) {
                    var lastK = coeffKRowAfterParamTr(last);
                    if (lastK) {
                        anchor = lastK;
                    }
                }
                if (anchor && anchor.nextElementSibling) {
                    newNodes.forEach(function (node) {
                        tbody.insertBefore(node, anchor.nextElementSibling);
                    });
                } else if (anchor) {
                    newNodes.forEach(function (node) {
                        anchor.parentNode.appendChild(node);
                    });
                } else {
                    newNodes.forEach(function (node) {
                        tbody.appendChild(node);
                    });
                }
                blockRows.push(newTr);
            }
            if (isEeBeforeBlockStart) {
                startTr.removeAttribute("data-is-block-start");
                newTr.setAttribute("data-is-block-start", "1");
                // Entity/perimeter go before the parameter column; note stays last
                // (same order as server HTML / buildRowTr). Inserting the note
                // before paramCell shifts all year cells one column right.
                ["td.summary-perimeter-variant-cell", "td.summary-entity-cell"].forEach(
                    function (sel) {
                        var cell = startTr.querySelector(sel);
                        if (cell) {
                            var paramCell = newTr.querySelector("td.summary-parameter-cell");
                            if (paramCell) {
                                newTr.insertBefore(cell, paramCell);
                            } else {
                                newTr.insertBefore(cell, newTr.firstChild);
                            }
                        }
                    }
                );
                var noteCell = startTr.querySelector("td.summary-entity-note-cell");
                if (noteCell) {
                    newTr.appendChild(noteCell);
                }
                startTr = newTr;
            }
        });
        repositionVerifyRowsInBlock(tbody, blockRows);
        blockRows = collectBlockRows(startTr);
        syncBlockRowspans(startTr, blockRows);
        if (typeof window.__pdPdSummaryRefreshLayoutAfterVisibility === "function") {
            window.__pdPdSummaryRefreshLayoutAfterVisibility();
        }
    }

    function insertBlockAfter(tbody, afterTr, block, cfg, years, yearIsPlan, showPerimeterCol, showHistCol) {
        var frag = document.createDocumentFragment();
        var built = [];
        block.forEach(function (row, idx) {
            var nodes = buildRowNodes(
                row,
                cfg,
                years,
                yearIsPlan,
                showPerimeterCol,
                showHistCol,
                {
                    prevRow: idx > 0 ? block[idx - 1] : null,
                    nextRow: idx + 1 < block.length ? block[idx + 1] : null,
                }
            );
            built.push(nodes[0]);
            nodes.forEach(function (node) {
                frag.appendChild(node);
            });
        });
        var insertAfter = afterTr;
        if (insertAfter && insertAfter.classList.contains("summary-row-param")) {
            var afterK = coeffKRowAfterParamTr(insertAfter);
            if (afterK) {
                insertAfter = afterK;
            }
        }
        if (insertAfter && insertAfter.nextSibling) {
            tbody.insertBefore(frag, insertAfter.nextSibling);
        } else if (insertAfter) {
            tbody.appendChild(frag);
        } else {
            tbody.appendChild(frag);
        }
        return built.length ? built[0] : null;
    }

    function insertBlockBefore(tbody, beforeTr, block, cfg, years, yearIsPlan, showPerimeterCol, showHistCol) {
        if (!beforeTr) {
            return insertBlockAfter(
                tbody,
                null,
                block,
                cfg,
                years,
                yearIsPlan,
                showPerimeterCol,
                showHistCol
            );
        }
        var frag = document.createDocumentFragment();
        var built = [];
        block.forEach(function (row, idx) {
            var nodes = buildRowNodes(
                row,
                cfg,
                years,
                yearIsPlan,
                showPerimeterCol,
                showHistCol,
                {
                    prevRow: idx > 0 ? block[idx - 1] : null,
                    nextRow: idx + 1 < block.length ? block[idx + 1] : null,
                }
            );
            built.push(nodes[0]);
            nodes.forEach(function (node) {
                frag.appendChild(node);
            });
        });
        tbody.insertBefore(frag, beforeTr);
        return built.length ? built[0] : null;
    }

    function resolveBlockMapEntry(tbody, blockMap, fp) {
        var existing = blockMap[fp];
        if (existing && existing.start && existing.rows && existing.rows.length) {
            return existing;
        }
        var starts = tbody.querySelectorAll('tr[data-is-block-start="1"]');
        for (var si = 0; si < starts.length; si++) {
            var st = starts[si];
            if (trBlockFingerprint(st, true) === fp) {
                var resolved = {
                    start: st,
                    rows: collectBlockRows(st),
                };
                blockMap[fp] = resolved;
                return resolved;
            }
        }
        return existing || null;
    }

    function lastTrOfBlock(startTr) {
        var blockRows = collectBlockRows(startTr);
        return blockRows.length ? blockRows[blockRows.length - 1] : startTr;
    }

    function mergeSegmentRowsIntoTbody(tbody, payload, isInitial) {
        if (isInitial) {
            return renderSummaryTableBody(payload);
        }
        var cfg = payload.config || {};
        var years = payload.years || [];
        var yearIsPlan = payload.year_is_plan || {};
        var rows = payload.summary_rows || [];
        rows = prepareRowsForClientRender(rows);
        var showPerimeterCol = !!cfg.show_perimeter_variant_column;
        var showHistCol = cfg.show_hist_col !== false;

        var blockMap = {};
        tbody.querySelectorAll('tr[data-is-block-start="1"]').forEach(function (startTr) {
            blockMap[trBlockFingerprint(startTr, true)] = {
                start: startTr,
                rows: collectBlockRows(startTr),
            };
        });

        var i = 0;
        while (i < rows.length) {
            var row = rows[i];
            if (row.pd_pd_aggregation_level_row) {
                if (shouldOmitRowForCurrentView(row)) {
                    i += 1;
                    continue;
                }
                if (findNtAggregationLevelTr(tbody, row)) {
                    i += 1;
                    continue;
                }
                var afterAgg = findInsertAfterForSouthNtAggregationRow(tbody, row);
                insertBlockAfter(
                    tbody,
                    afterAgg,
                    [row],
                    cfg,
                    years,
                    yearIsPlan,
                    showPerimeterCol,
                    showHistCol
                );
                i += 1;
                continue;
            }
            if (!row.show_entity_cell) {
                i += 1;
                continue;
            }
            var blockSize = parseInt(row.entity_rowspan || 1, 10);
            if (blockSize < 1) {
                blockSize = 1;
            }
            var block = rows.slice(i, i + blockSize);
            i += blockSize;

            var fp = rowBlockFingerprint(row, true);
            var existing = resolveBlockMapEntry(tbody, blockMap, fp);
            if (
                (!existing || !existing.start) &&
                (blockIsVerifyOnly(block) ||
                    isChiOnlySegmentBlock(block) ||
                    isEeOnlySegmentBlock(block))
            ) {
                var entityFallbackStart = findBlockStartByEntity(tbody, row);
                if (entityFallbackStart) {
                    existing = {
                        start: entityFallbackStart,
                        rows: collectBlockRows(entityFallbackStart),
                    };
                    blockMap[fp] = existing;
                }
            }
            if (existing && existing.start) {
                mergeRowsIntoBlock(
                    tbody,
                    existing.start,
                    existing.rows,
                    block,
                    cfg,
                    years,
                    yearIsPlan,
                    showPerimeterCol,
                    showHistCol
                );
                continue;
            }
            var fallbackStart = findBlockStartByEntity(tbody, row);
            if (row.pd_pd_nt_extra_row) {
                if (isChiOnlySegmentBlock(block) || isEeOnlySegmentBlock(block)) {
                    continue;
                }
                // calc_max / verify: влить в уже отрисованный блок «с НТ», не плодить новый.
                if (fallbackStart) {
                    mergeRowsIntoBlock(
                        tbody,
                        fallbackStart,
                        collectBlockRows(fallbackStart),
                        block,
                        cfg,
                        years,
                        yearIsPlan,
                        showPerimeterCol,
                        showHistCol
                    );
                    blockMap[fp] = {
                        start: fallbackStart,
                        rows: collectBlockRows(fallbackStart),
                    };
                    continue;
                }
                // Субъекты / строки под «Новые территории» — сразу после заголовка агрегации.
                var afterNtSubtree = findInsertAfterForNtSubtreeRow(tbody, row);
                var insertedStart;
                if (afterNtSubtree) {
                    insertedStart = insertBlockAfter(
                        tbody,
                        afterNtSubtree,
                        block,
                        cfg,
                        years,
                        yearIsPlan,
                        showPerimeterCol,
                        showHistCol
                    );
                } else if (
                    block.some(function (r) {
                        return !!r.pd_pd_summary_table_only_row;
                    })
                ) {
                    // Prefix «с НТ» без якоря — не в конец tbody.
                    continue;
                } else {
                    var baseStart = findBaseBlockStartForNtRow(tbody, row);
                    if (baseStart) {
                        // Пары with_nt ↔ without_nt: before «без НТ».
                        insertedStart = insertBlockBefore(
                            tbody,
                            baseStart,
                            block,
                            cfg,
                            years,
                            yearIsPlan,
                            showPerimeterCol,
                            showHistCol
                        );
                    } else {
                        var afterSouth = findInsertAfterForSouthNtAggregationRow(
                            tbody,
                            row
                        );
                        insertedStart = insertBlockAfter(
                            tbody,
                            afterSouth,
                            block,
                            cfg,
                            years,
                            yearIsPlan,
                            showPerimeterCol,
                            showHistCol
                        );
                    }
                }
                if (insertedStart) {
                    blockMap[fp] = {
                        start: insertedStart,
                        rows: collectBlockRows(insertedStart),
                    };
                }
            } else if (fallbackStart) {
                mergeRowsIntoBlock(
                    tbody,
                    fallbackStart,
                    collectBlockRows(fallbackStart),
                    block,
                    cfg,
                    years,
                    yearIsPlan,
                    showPerimeterCol,
                    showHistCol
                );
                blockMap[fp] = {
                    start: fallbackStart,
                    rows: collectBlockRows(fallbackStart),
                };
            } else if (
                block.some(function (r) {
                    return !!r.pd_pd_summary_table_only_row;
                })
            ) {
                // Prefix (ЦЗ / ЕЭС / 1-я СЗ): без блока-якоря в DOM не дописывать
                // в конец страницы — иначе «Расчетное максимальное…» оказывается внизу.
                continue;
            } else {
                var insertedBaseStart = insertBlockAfter(
                    tbody,
                    tbody.lastElementChild,
                    block,
                    cfg,
                    years,
                    yearIsPlan,
                    showPerimeterCol,
                    showHistCol
                );
                if (insertedBaseStart) {
                    blockMap[fp] = {
                        start: insertedBaseStart,
                        rows: collectBlockRows(insertedBaseStart),
                    };
                }
            }
        }

        injectLiveCalcData(payload);
        if (typeof window.__pdPdSummarySyncPerimeterVariantLabels === "function") {
            window.__pdPdSummarySyncPerimeterVariantLabels();
        }
        if (typeof window.__pdPdSummaryInitTableTooltips === "function") {
            window.__pdPdSummaryInitTableTooltips();
        }
        if (!window.__pdPdSummaryDeferSegmentVisibility) {
            if (typeof window.__pdPdSummaryReapplyRowVisibility === "function") {
                window.__pdPdSummaryReapplyRowVisibility();
            } else if (
                typeof window.__pdPdSummaryRefreshLayoutAfterVisibility === "function"
            ) {
                window.__pdPdSummaryRefreshLayoutAfterVisibility();
            } else {
                pdSummaryRefreshEntityLayout();
            }
        } else {
            pdSummaryRefreshEntityLayout();
        }
        if (typeof window.pdSummarySyncAggregationLevelColspans === "function") {
            window.pdSummarySyncAggregationLevelColspans();
        }
        document.dispatchEvent(new CustomEvent("pd-summary-rows-rendered"));
    }

    function finishSummaryTableBodyRender(tbody, payload) {
        lastRenderedSummaryPayload = payload;
        repositionAllVerifyRowsInTbody(tbody);
        injectLiveCalcData(payload);
        if (typeof window.__pdPdSummarySyncPerimeterVariantLabels === "function") {
            window.__pdPdSummarySyncPerimeterVariantLabels();
        }
        if (typeof window.__pdPdSummaryInitTableTooltips === "function") {
            window.__pdPdSummaryInitTableTooltips();
        }
        renderEntityPagination(payload);
        if (!window.__pdPdSummaryDeferSegmentVisibility) {
            if (typeof window.__pdPdSummaryReapplyRowVisibility === "function") {
                window.__pdPdSummaryReapplyRowVisibility();
            } else if (
                typeof window.__pdPdSummaryRefreshLayoutAfterVisibility === "function"
            ) {
                window.__pdPdSummaryRefreshLayoutAfterVisibility();
            } else {
                pdSummaryRefreshEntityLayout();
            }
        } else {
            pdSummaryRefreshEntityLayout();
        }
        if (typeof window.pdSummarySyncAggregationLevelColspans === "function") {
            window.pdSummarySyncAggregationLevelColspans();
        }
        document.dispatchEvent(new CustomEvent("pd-summary-rows-rendered"));
    }

    var RENDER_ROWS_CHUNK_SIZE = 48;
    var lastRenderedSummaryPayload = null;

    function renderSummaryTableBody(payload) {
        var tbody =
            document.getElementById("powerDemandSummaryTbody") ||
            document.querySelector("#powerDemandSummaryTable tbody");
        if (!tbody) {
            throw new Error("tbody не найден");
        }
        var cfg = payload.config || {};
        var years = payload.years || [];
        var yearIsPlan = payload.year_is_plan || {};
        var rows = payload.summary_rows || [];
        var showPerimeterCol = !!cfg.show_perimeter_variant_column;
        var showHistCol = cfg.show_hist_col !== false;

        if (!rows.length) {
            var emptyTr = document.createElement("tr");
            var emptyTd = document.createElement("td");
            emptyTd.colSpan = isCoeffRoute(cfg)
                ? 9 + years.length + (showPerimeterCol ? 1 : 0)
                : (showHistCol ? 3 : 2) +
                  years.length +
                  1 +
                  (showPerimeterCol ? 1 : 0);
            emptyTd.className = "text-center text-muted";
            emptyTd.textContent = "Нет данных для текущей версии БД.";
            emptyTr.appendChild(emptyTd);
            tbody.replaceChildren(emptyTr);
            finishSummaryTableBodyRender(tbody, payload);
            return Promise.resolve();
        }

        rows = prepareRowsForClientRender(rows);

        if (rows.length <= RENDER_ROWS_CHUNK_SIZE) {
            var frag = document.createDocumentFragment();
            rows.forEach(function (row, idx) {
                buildRowNodes(
                    row,
                    cfg,
                    years,
                    yearIsPlan,
                    showPerimeterCol,
                    showHistCol,
                    {
                        prevRow: idx > 0 ? rows[idx - 1] : null,
                        nextRow: idx + 1 < rows.length ? rows[idx + 1] : null,
                    }
                ).forEach(function (node) {
                    frag.appendChild(node);
                });
            });
            tbody.replaceChildren(frag);
            finishSummaryTableBodyRender(tbody, payload);
            return Promise.resolve();
        }

        tbody.replaceChildren();
        var rowIndex = 0;
        return new Promise(function (resolve) {
            function renderChunk() {
                var fragChunk = document.createDocumentFragment();
                var end = Math.min(rowIndex + RENDER_ROWS_CHUNK_SIZE, rows.length);
                for (; rowIndex < end; rowIndex++) {
                    buildRowNodes(
                        rows[rowIndex],
                        cfg,
                        years,
                        yearIsPlan,
                        showPerimeterCol,
                        showHistCol,
                        {
                            prevRow: rowIndex > 0 ? rows[rowIndex - 1] : null,
                            nextRow:
                                rowIndex + 1 < rows.length
                                    ? rows[rowIndex + 1]
                                    : null,
                        }
                    ).forEach(function (node) {
                        fragChunk.appendChild(node);
                    });
                }
                tbody.appendChild(fragChunk);
                if (rowIndex < rows.length) {
                    window.requestAnimationFrame(renderChunk);
                    return;
                }
                finishSummaryTableBodyRender(tbody, payload);
                resolve();
            }
            window.requestAnimationFrame(renderChunk);
        });
    }

    var currentEntityPagination = null;

    function paginationScopeEnabled() {
        if (!shellConfig || !shellConfig.entity_pagination) {
            return false;
        }
        return { oes: true, fo: true, ez: true }[shellConfig.scope] === true;
    }

    function paginationAllLabel() {
        var pagCfg = (shellConfig && shellConfig.entity_pagination) || {};
        if (pagCfg.all_label) {
            return pagCfg.all_label;
        }
        var labels = {
            oes: "Все ОЭС",
            fo: "Все ФО",
            ez: "Все энергозоны",
        };
        return labels[shellConfig.scope] || "Показать всё";
    }

    function entityPaginationPageSizeFromUrl() {
        var pagCfg = (shellConfig && shellConfig.entity_pagination) || {};
        var params = new URLSearchParams(window.location.search || "");
        var raw = params.get("pd_page_size");
        if (raw === null || String(raw).trim() === "") {
            return pagCfg.default_page_size != null
                ? pagCfg.default_page_size
                : 2;
        }
        var n = parseInt(raw, 10);
        if (isNaN(n) || n < 0) {
            return pagCfg.default_page_size != null
                ? pagCfg.default_page_size
                : 2;
        }
        return n;
    }

    function entityPaginationPageFromUrl() {
        var params = new URLSearchParams(window.location.search || "");
        var n = parseInt(params.get("pd_page") || "1", 10);
        return isNaN(n) || n < 1 ? 1 : n;
    }

    function entityPaginationAllPageSize() {
        var pagCfg = (shellConfig && shellConfig.entity_pagination) || {};
        return pagCfg.all_page_size != null ? pagCfg.all_page_size : 0;
    }

    function effectiveEntityPaginationPageSize() {
        if (window.__pdPdSummaryTerritoryCompactMode === true) {
            return entityPaginationAllPageSize();
        }
        return entityPaginationPageSizeFromUrl();
    }

    function effectiveEntityPaginationPage(pageSize) {
        if (pageSize <= 0) {
            return 1;
        }
        return entityPaginationPageFromUrl();
    }

    function entityPaginationUrlIsPaginated() {
        return entityPaginationPageSizeFromUrl() > 0;
    }

    function syncEntityPaginationUrl(page, pageSize) {
        var params = new URLSearchParams(window.location.search || "");
        if (pageSize > 0) {
            params.set("pd_page_size", String(pageSize));
            params.set("pd_page", String(page));
        } else {
            params.set("pd_page_size", "0");
            params.delete("pd_page");
        }
        var qs = params.toString();
        var next = qs
            ? window.location.pathname + "?" + qs
            : window.location.pathname;
        window.history.replaceState(null, "", next);
    }

    function renderEntityPagination(payload) {
        var nav = document.getElementById("pdSummaryEntityPagination");
        if (!nav || !paginationScopeEnabled()) {
            return;
        }
        var meta = (payload && payload.entity_pagination) || null;
        currentEntityPagination = meta;
        if (meta && meta.enabled) {
            syncEntityPaginationUrl(meta.page || 1, meta.page_size || 2);
        } else if (
            window.__pdPdSummaryTerritoryCompactMode === true &&
            paginationScopeEnabled()
        ) {
            syncEntityPaginationUrl(1, entityPaginationAllPageSize());
        }
        if (!meta || !meta.enabled || (meta.total_pages || 1) <= 1) {
            nav.hidden = true;
            nav.setAttribute("hidden", "hidden");
            nav.replaceChildren();
            return;
        }
        nav.hidden = false;
        nav.removeAttribute("hidden");

        var pagCfg = shellConfig.entity_pagination || {};
        var page = meta.page || 1;
        var totalPages = meta.total_pages || 1;
        var pageSize = meta.page_size || pagCfg.default_page_size || 2;
        var titles = (meta.section_titles || []).filter(Boolean);
        var info = document.createElement("div");
        info.className = "small text-muted mb-2 text-center";
        info.textContent =
            "Страница " +
            page +
            " из " +
            totalPages +
            (titles.length ? " — " + titles.join(", ") : "");

        var ul = document.createElement("ul");
        ul.className = "pagination justify-content-center mb-0 flex-wrap";

        function addItem(label, targetPage, disabled, active) {
            var li = document.createElement("li");
            li.className =
                "page-item" +
                (disabled ? " disabled" : "") +
                (active ? " active" : "");
            var a = document.createElement("a");
            a.className = "page-link";
            a.href = "#";
            a.textContent = label;
            if (!disabled && !active) {
                a.addEventListener("click", function (ev) {
                    ev.preventDefault();
                    loadEntityPaginationPage(targetPage, pageSize);
                });
            }
            li.appendChild(a);
            ul.appendChild(li);
        }

        addItem("« Назад", page - 1, !meta.has_prev, false);
        for (var p = 1; p <= totalPages; p++) {
            if (
                totalPages > 7 &&
                p !== 1 &&
                p !== totalPages &&
                Math.abs(p - page) > 1
            ) {
                if (p === 2 || p === totalPages - 1) {
                    addItem("…", p, true, false);
                }
                continue;
            }
            addItem(String(p), p, false, p === page);
        }
        addItem("Вперёд »", page + 1, !meta.has_next, false);

        var allLi = document.createElement("li");
        allLi.className = "page-item ms-2";
        var allA = document.createElement("a");
        allA.className = "page-link";
        allA.href = "#";
        allA.textContent =
            meta.all_label || pagCfg.all_label || paginationAllLabel();
        allA.addEventListener("click", function (ev) {
            ev.preventDefault();
            loadEntityPaginationPage(1, pagCfg.all_page_size || 0);
        });
        allLi.appendChild(allA);
        ul.appendChild(allLi);

        nav.replaceChildren(info, ul);
    }

    function resetLoadedSegmentsState() {
        loadedSegments = {};
        segmentLoadPromises = {};
    }

    /**
     * Active optional segments from view toggles (session-backed window flags).
     * Used after tbody rebuild / pagination so pressed buttons keep their rows.
     */
    function collectActiveOptionalSegmentsFromWindowFlags() {
        var summaryTableEl = document.getElementById("powerDemandSummaryTable");
        var view =
            (shellConfig && shellConfig.scope) ||
            (summaryTableEl &&
                summaryTableEl.getAttribute("data-summary-view")) ||
            "oes";
        var segs = [];
        if (window.__pdPdSummaryNtDetailMode === true) {
            segs.push("nt_extra");
        }
        if (window.__pdPdSummaryCalcMaxMode === true) {
            segs.push("calc_max");
        }
        if (window.__pdPdSummaryEeMode === true) {
            if (
                (view === "oes" || view === "fo") &&
                segs.indexOf("nt_extra") < 0
            ) {
                segs.push("nt_extra");
            }
            segs.push("ee");
        }
        if (window.__pdPdSummaryChiMode === true) {
            if (
                (view === "oes" || view === "fo") &&
                segs.indexOf("nt_extra") < 0
            ) {
                segs.push("nt_extra");
            }
            segs.push("chi");
        }
        if (window.__pdPdSummaryVerificationMode === true) {
            if (segs.indexOf("calc_max") < 0) {
                segs.push("calc_max");
            }
            segs.push("verify");
        }
        if (typeof window.__pdPdSummarySegmentsForVisibleRows === "function") {
            var coreSet = {};
            defaultSegments().forEach(function (s) {
                coreSet[s] = true;
            });
            window.__pdPdSummarySegmentsForVisibleRows().forEach(function (seg) {
                if (seg && !coreSet[seg] && segs.indexOf(seg) < 0) {
                    segs.push(seg);
                }
            });
        }
        return segs;
    }

    function reapplyVisibilityAfterSegmentChange() {
        if (
            window.__pdPdSummaryCalcMaxMode === true &&
            typeof window.__pdPdSummarySetCalcMaxRowKeysVisible === "function"
        ) {
            window.__pdPdSummarySetCalcMaxRowKeysVisible(true);
            return;
        }
        if (typeof window.__pdPdSummaryReapplyRowVisibility === "function") {
            window.__pdPdSummaryReapplyRowVisibility();
        } else if (
            typeof window.__pdPdSummaryRefreshLayoutAfterVisibility === "function"
        ) {
            window.__pdPdSummaryRefreshLayoutAfterVisibility();
        }
        if (typeof refreshPowerDemandSummaryLayout === "function") {
            refreshPowerDemandSummaryLayout();
        }
    }

    function restoreActiveOptionalSegmentsAfterCoreLoad() {
        var optionalSegs = collectActiveOptionalSegmentsFromWindowFlags();
        if (!optionalSegs.length) {
            return Promise.resolve();
        }
        if (typeof window.__pdSummaryEnsureSegments !== "function") {
            return Promise.resolve();
        }
        return window.__pdSummaryEnsureSegments(optionalSegs);
    }

    function loadEntityPaginationPage(page, pageSize) {
        syncEntityPaginationUrl(page, pageSize);
        resetLoadedSegmentsState();
        var tbody =
            document.getElementById("powerDemandSummaryTbody") ||
            document.querySelector("#powerDemandSummaryTable tbody");
        if (!tbody) {
            return Promise.reject(new Error("tbody не найден"));
        }
        pdSummaryShowSegmentLoading();
        var scrollWrap = document.getElementById("powerDemandSummaryScrollWrap");
        if (scrollWrap) {
            scrollWrap.scrollTop = 0;
        }
        return fetchSegmentPayload(defaultSegments())
            .then(function (payload) {
                return renderSummaryTableBody(payload).then(function () {
                    return payload;
                });
            })
            .then(function (payload) {
                // Core rebuild drops optional rows; re-mesh pressed toggles.
                return restoreActiveOptionalSegmentsAfterCoreLoad().then(
                    function () {
                        return payload;
                    },
                    function () {
                        return payload;
                    }
                );
            })
            .catch(function (err) {
                var tr = document.createElement("tr");
                var td = document.createElement("td");
                td.colSpan = 10;
                td.className = "text-center text-danger";
                td.textContent =
                    "Не удалось загрузить страницу: " + (err.message || err);
                tr.appendChild(td);
                tbody.replaceChildren(tr);
                throw err;
            })
            .finally(function () {
                pdSummaryHideSegmentLoading();
                reapplyVisibilityAfterSegmentChange();
            });
    }

    var loadedSegments = {};
    var segmentLoadPromises = {};
    var segmentLoadingDepth = 0;

    function pdSummarySegmentToggleButtons() {
        return [
            document.getElementById("pdPdSummaryTerritoryCompactToggle"),
            document.getElementById("pdPdSummaryEeToggle"),
            document.getElementById("pdPdSummaryNtDetailToggle"),
            document.getElementById("pdPdSummaryChiToggle"),
            document.getElementById("pdPdSummaryCalcMaxToggle"),
            document.getElementById("pdPdSummaryVerificationToggle"),
        ].filter(Boolean);
    }

    function pdSummaryShowSegmentLoading() {
        segmentLoadingDepth += 1;
        if (segmentLoadingDepth > 1) {
            return;
        }
        var overlay = document.getElementById(
            "powerDemandSummarySegmentLoadingOverlay"
        );
        if (overlay) {
            overlay.hidden = false;
            overlay.removeAttribute("hidden");
            overlay.style.display = "flex";
            overlay.setAttribute("aria-hidden", "false");
        }
        var shell = document.getElementById("powerDemandSummaryLoaderShell");
        if (shell) {
            shell.setAttribute("aria-busy", "true");
        }
        pdSummarySegmentToggleButtons().forEach(function (btn) {
            btn.disabled = true;
            btn.setAttribute("aria-disabled", "true");
        });
    }

    function pdSummaryHideSegmentLoading() {
        segmentLoadingDepth = Math.max(0, segmentLoadingDepth - 1);
        if (segmentLoadingDepth > 0) {
            return;
        }
        var overlay = document.getElementById(
            "powerDemandSummarySegmentLoadingOverlay"
        );
        if (overlay) {
            overlay.hidden = true;
            overlay.style.display = "none";
            overlay.setAttribute("aria-hidden", "true");
        }
        var shell = document.getElementById("powerDemandSummaryLoaderShell");
        if (shell && shell.dataset.ready === "1") {
            shell.setAttribute("aria-busy", "false");
        }
        pdSummarySegmentToggleButtons().forEach(function (btn) {
            btn.disabled = false;
            btn.removeAttribute("aria-disabled");
        });
    }

    function defaultSegments() {
        var seg = shellConfig.segments || {};
        return (seg.default_segments || ["core"]).slice();
    }

    function buildDataUrl(segments) {
        var path = shellConfig.data_path;
        var params = new URLSearchParams(window.location.search || "");
        params.set("pd_data_segments", segments.join(","));
        if (paginationScopeEnabled()) {
            var pageSize = effectiveEntityPaginationPageSize();
            if (pageSize > 0) {
                params.set("pd_page_size", String(pageSize));
                params.set(
                    "pd_page",
                    String(effectiveEntityPaginationPage(pageSize))
                );
            } else {
                params.set("pd_page_size", "0");
                params.delete("pd_page");
            }
        }
        var qs = params.toString();
        return qs ? path + "?" + qs : path;
    }

    function fetchSegmentPayload(segments) {
        var sorted = segments.slice().sort();
        // Include pagination in cache key: compact on/off changes page_size.
        var pageSize = effectiveEntityPaginationPageSize();
        var page =
            pageSize > 0 ? effectiveEntityPaginationPage(pageSize) : 1;
        var cacheKey =
            sorted.join(",") + "|p" + String(page) + "|s" + String(pageSize);
        if (segmentLoadPromises[cacheKey]) {
            return segmentLoadPromises[cacheKey].then(function (payload) {
                // Re-mark after tbody rebuild cleared loadedSegments flags.
                sorted.forEach(function (s) {
                    loadedSegments[s] = true;
                });
                return payload;
            });
        }
        segmentLoadPromises[cacheKey] = fetch(buildDataUrl(sorted), {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        })
            .then(function (resp) {
                if (!resp.ok) {
                    throw new Error("HTTP " + resp.status);
                }
                return resp.json();
            })
            .then(function (payload) {
                if (!payload || !payload.ok) {
                    throw new Error(
                        (payload && payload.error) || "Ошибка загрузки данных"
                    );
                }
                sorted.forEach(function (s) {
                    loadedSegments[s] = true;
                });
                return payload;
            });
        return segmentLoadPromises[cacheKey];
    }

    function loadSegmentIntoTable(segmentName) {
        var tbody =
            document.getElementById("powerDemandSummaryTbody") ||
            document.querySelector("#powerDemandSummaryTable tbody");
        if (!tbody) {
            return Promise.reject(new Error("tbody не найден"));
        }
        // Skip remesh when already loaded. Callers that rebuild tbody
        // (pagination / «Сводная таблица») must clear loadedSegments first —
        // otherwise merge + pd-summary-rows-rendered can loop forever.
        if (loadedSegments[segmentName]) {
            return Promise.resolve();
        }
        var loadPayload = function (name) {
            return fetchSegmentPayload([name]).then(function (payload) {
                mergeSegmentRowsIntoTbody(tbody, payload, false);
            });
        };
        if (
            (segmentName === "chi" || segmentName === "ee") &&
            (shellConfig.scope === "oes" || shellConfig.scope === "fo") &&
            !loadedSegments.nt_extra
        ) {
            return loadSegmentIntoTable("nt_extra").then(function () {
                return loadPayload(segmentName);
            });
        }
        return loadPayload(segmentName);
    }

    function loadSegmentsIntoTable(segmentNames) {
        var ordered = orderSegmentLoadNames(segmentNames).filter(Boolean);
        if (!ordered.length) {
            return Promise.resolve();
        }
        var tbody =
            document.getElementById("powerDemandSummaryTbody") ||
            document.querySelector("#powerDemandSummaryTable tbody");
        if (!tbody) {
            return Promise.reject(new Error("tbody не найден"));
        }
        return ordered.reduce(function (chain, name) {
            return chain.then(function () {
                if (loadedSegments[name]) {
                    return;
                }
                return fetchSegmentPayload([name]).then(function (payload) {
                    mergeSegmentRowsIntoTbody(tbody, payload, false);
                });
            });
        }, Promise.resolve());
    }

    window.__pdPdSummaryRerenderTableBody = function () {
        if (!lastRenderedSummaryPayload) {
            return Promise.resolve();
        }
        /**
         * Full tbody rebuild drops optional segment rows. Keep fetch cache, but
         * clear non-core loaded flags so ensureSegments remeshes them into DOM.
         */
        var coreSet = {};
        defaultSegments().forEach(function (s) {
            coreSet[s] = true;
        });
        Object.keys(loadedSegments).forEach(function (s) {
            if (!coreSet[s]) {
                delete loadedSegments[s];
            }
        });
        return renderSummaryTableBody(lastRenderedSummaryPayload);
    };

    window.__pdSummaryLoadEntityPaginationPage = loadEntityPaginationPage;
    window.__pdSummaryEntityPaginationUrlIsPaginated = entityPaginationUrlIsPaginated;
    window.__pdPdSummaryCollectActiveOptionalSegments =
        collectActiveOptionalSegmentsFromWindowFlags;

    window.__pdSummaryEnsureSegments = function (segmentNames) {
        if (!segmentNames || !segmentNames.length) {
            return Promise.resolve();
        }
        var ordered = orderSegmentLoadNames(segmentNames).filter(Boolean);
        var toLoad = ordered.filter(function (s) {
            return s && !loadedSegments[s];
        });
        if (!toLoad.length) {
            return Promise.resolve();
        }
        pdSummaryShowSegmentLoading();
        var loadPromise =
            toLoad.length === 1
                ? loadSegmentIntoTable(toLoad[0])
                : loadSegmentsIntoTable(toLoad);
        return loadPromise.finally(function () {
            pdSummaryHideSegmentLoading();
        });
    };

    window.__pdSummarySegmentForParameterKey = function (parameterKey) {
        var seg = shellConfig.segments || {};
        var map = seg.parameter_key_segments || {};
        var pk = String(parameterKey || "");
        if (map[pk]) {
            return map[pk];
        }
        if (pk.indexOf("verify_for_") === 0) {
            return "verify";
        }
        return null;
    };

    window.__pdSummaryRowsReady = fetchSegmentPayload(defaultSegments())
        .then(function (payload) {
            var tbody =
                document.getElementById("powerDemandSummaryTbody") ||
                document.querySelector("#powerDemandSummaryTable tbody");
            if (!tbody) {
                throw new Error("tbody не найден");
            }
            return renderSummaryTableBody(payload).then(function () {
                return payload;
            });
        })
        .catch(function (err) {
            var tbody =
                document.getElementById("powerDemandSummaryTbody") ||
                document.querySelector("#powerDemandSummaryTable tbody");
            if (tbody) {
                var tr = document.createElement("tr");
                var td = document.createElement("td");
                td.colSpan = 10;
                td.className = "text-center text-danger";
                td.textContent =
                    "Не удалось загрузить данные таблицы: " + (err.message || err);
                tr.appendChild(td);
                tbody.replaceChildren(tr);
            }
            throw err;
        });
})();
