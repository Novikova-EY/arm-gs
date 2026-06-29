/**
 * Клиентский рендер tbody сводок «Максимумы» (ОЭС / ФО / ЭЗ).
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

    var READONLY_KEYS = {};
    (shellConfig.pd_readonly_parameter_keys || []).forEach(function (k) {
        READONLY_KEYS[k] = true;
    });
    var SUMMARY_SCOPES = { oes: true, fo: true, ez: true };

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
        if (row.pd_pd_chi_row) {
            classes.push("pd-pd-chi-row", "summary-row-hidden");
        } else if (
            (active === "oes" || active === "fo" || active === "ez") &&
            (cfg.summary_route_variant || "max") !== "coeff" &&
            pk &&
            READONLY_KEYS[pk]
        ) {
            classes.push("pd-pd-calc-max-row", "summary-row-hidden");
        }
        if (row.pd_pd_verify_for_row) {
            classes.push("summary-row-hidden");
        } else if (
            SUMMARY_SCOPES[active] &&
            row.pd_pd_nt_extra_row
        ) {
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

    function canEditCell(row, cfg) {
        var pk = row.parameter_key || "";
        return (
            canEditSlice(row, cfg) &&
            !READONLY_KEYS[pk] &&
            !row.pd_pd_formula_derived_row
        );
    }

    function canEditHistCell(row, cfg) {
        if (!canEditCell(row, cfg)) {
            return false;
        }
        if (cfg.active_summary === "oes") {
            return ["max_power", "peak_datetime", "avg_temp"].indexOf(row.parameter_key) >= 0;
        }
        return true;
    }

    function planHideYearCell(row, year, yearIsPlan) {
        var pk = row.parameter_key || "";
        return !!yearIsPlan[String(year)] && pk !== "max_power";
    }

    function buildParameterCellHtml(row) {
        var label = escapeHtml(row.parameter_label || "");
        if (row.pd_parameter_formula_tooltip) {
            return (
                '<span class="text-wrap">' +
                label +
                '<i class="bi bi-info-circle text-primary ms-1" data-bs-toggle="tooltip" data-bs-placement="top" title="' +
                escapeAttr(row.pd_parameter_formula_tooltip) +
                '" style="cursor: help; font-size: 0.9em; vertical-align: -0.1em;" aria-label="Формула расчёта"></i></span>'
            );
        }
        return label;
    }

    function buildHistCell(row, cfg) {
        var td = document.createElement("td");
        td.className = "text-center summary-hist-cell";
        var pk = row.parameter_key || "";
        var tooltip = row.hist_numeric_tooltip || "";
        if (pk === "peak_datetime") {
            var peakTitle =
                (tooltip ? escapeAttr(tooltip) + " — " : "") +
                "Год (ГГГГ) или дата и время (мск): ДД.ММ.ГГГГ ЧЧ:ММ";
            td.setAttribute("title", peakTitle.replace(/&#39;/g, "'"));
        } else if (tooltip) {
            td.setAttribute("title", tooltip);
        }

        if (canEditHistCell(row, cfg)) {
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
        } else {
            td.textContent = row.hist_value != null ? String(row.hist_value) : "";
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
        var planHide = planHideYearCell(row, year, yearIsPlan);

        td.className = "text-center summary-year-cell";
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

        if (canEditCell(row, cfg)) {
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
        } else {
            td.textContent = value;
        }
        return td;
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

    function buildEntityCell(row, entityRowspan) {
        var td = document.createElement("td");
        td.className =
            "summary-entity-cell summary-depth-" + (row.entity_depth || 0);
        td.rowSpan = entityRowspan > 0 ? entityRowspan : 1;
        td.setAttribute("data-original-rowspan", String(row.entity_rowspan || 1));
        var div = document.createElement("div");
        div.style.paddingLeft = String((row.entity_depth || 0) * 1.5) + "rem";
        div.textContent = row.entity_label || "";
        if (row.pd_pd_decentralized_zone_mark) {
            var mark = document.createElement("span");
            mark.className = "pd-pd-dz-mark ms-1";
            mark.setAttribute("data-bs-toggle", "tooltip");
            mark.setAttribute("data-bs-placement", "top");
            mark.title = "Децентрализованная зона";
            mark.setAttribute("aria-label", "Децентрализованная зона");
            mark.textContent = "ДЗ";
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
        if (row.pd_pd_chi_row) {
            tr.setAttribute("data-pd-pd-chi-row", "1");
        }
        if (row.pd_pd_formula_derived_row) {
            tr.setAttribute("data-pd-pd-formula-derived", "1");
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
            (row.pd_pd_entity_label_compact_nt || row.pd_pd_entity_label_nt_detail)
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
        }

        if (row.pd_pd_aggregation_level_full_row) {
            var aggTd = document.createElement("td");
            var nCols =
                (showHistCol ? 3 : 2) +
                years.length +
                1 +
                (showPerimeterCol ? 1 : 0);
            aggTd.colSpan = nCols;
            aggTd.className =
                "summary-entity-cell summary-depth-" +
                (row.entity_depth || 0) +
                " fw-semibold text-center";
            aggTd.textContent = row.entity_label || "";
            tr.appendChild(aggTd);
            return tr;
        }

        var entityRs = row.entity_rowspan || 1;
        if (row.show_entity_cell) {
            if (showPerimeterCol) {
                tr.appendChild(buildPerimeterVariantCell(row, cfg, entityRs));
            }
            tr.appendChild(buildEntityCell(row, entityRs));
        }

        var paramTd = document.createElement("td");
        paramTd.className = "summary-parameter-cell";
        paramTd.innerHTML = buildParameterCellHtml(row);
        tr.appendChild(paramTd);

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
        var blockSize = parseInt(
            startTr.getAttribute("data-entity-block-size") || "1",
            10
        );
        if (blockSize < 1) {
            blockSize = 1;
        }
        var blockRows = [];
        var tr = startTr;
        while (blockRows.length < blockSize && tr) {
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
        return blockRows;
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
    };

    function findInsertBeforeForMergedRow(blockRows, pk, order) {
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
        var afterPk = MERGE_ROW_INSERT_AFTER[pk];
        if (afterPk) {
            for (var ai = 0; ai < blockRows.length; ai++) {
                if (
                    (blockRows[ai].getAttribute("data-parameter-key") || "") ===
                    afterPk
                ) {
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
        var blockSize = blockRows.length;
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
        if (entityTd) {
            entityTd.setAttribute("rowspan", rs);
        }
        if (variantTd) {
            variantTd.setAttribute("rowspan", rs);
        }
        if (noteTd) {
            noteTd.setAttribute("rowspan", rs);
        }
    }

    function isChiOnlySegmentBlock(block) {
        return (
            block &&
            block.length === 1 &&
            String(block[0].parameter_key || "") === "peak_max_power_usage_hours"
        );
    }

    function orderSegmentLoadNames(segmentNames) {
        var names = (segmentNames || []).slice();
        var scope = (shellConfig && shellConfig.scope) || "";
        if (scope === "oes" && names.indexOf("chi") >= 0 && names.indexOf("nt_extra") < 0) {
            names.unshift("nt_extra");
        }
        var priority = { nt_extra: 0, calc_max: 1, chi: 2, verify: 3 };
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
        var aggRows = tbody.querySelectorAll('tr[data-pd-pd-aggregation-level="1"]');
        for (var i = 0; i < aggRows.length; i++) {
            var tr = aggRows[i];
            if (tr.getAttribute("data-pd-pd-nt-extra") !== "1") {
                continue;
            }
            if (uesId && tr.getAttribute("data-id-union-energy-system") !== uesId) {
                continue;
            }
            return tr;
        }
        return null;
    }

    function findInsertAfterForSouthNtAggregationRow(tbody, row) {
        var uesId =
            row.id_union_energy_system != null
                ? String(row.id_union_energy_system)
                : "";
        if (!uesId) {
            return null;
        }
        var lastEnd = null;
        var inBaseSouth = false;
        var starts = tbody.querySelectorAll('tr[data-is-block-start="1"]');
        for (var i = 0; i < starts.length; i++) {
            var st = starts[i];
            if (st.getAttribute("data-id-union-energy-system") !== uesId) {
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
            var labels = startTrEntityLabels(st);
            var lbl = labels.length ? labels[0] : "";
            if (
                startTrEntityKind(st) === "perimeter_variant" &&
                lbl.indexOf("без НТ") >= 0
            ) {
                inBaseSouth = true;
                continue;
            }
            if (!inBaseSouth) {
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
            .replace(/\s+ДЗ$/, "")
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
        var entityCell = startTr.querySelector("td.summary-entity-cell div");
        if (entityCell) {
            labels.push(entityCell.textContent);
        }
        return labels.map(normalizeEntityLabel).filter(Boolean);
    }

    function findBlockStartByEntity(tbody, row) {
        var targetKind = String(row.entity_kind || "");
        var targetLabel = normalizeEntityLabel(row.entity_label);
        if (!targetKind || !targetLabel) {
            return null;
        }
        var targetNt = row.pd_pd_nt_extra_row ? "1" : "0";
        var targetPvc =
            row.perimeter_variant_code != null
                ? String(row.perimeter_variant_code)
                : "";
        var starts = tbody.querySelectorAll('tr[data-is-block-start="1"]');
        for (var i = 0; i < starts.length; i++) {
            var st = starts[i];
            var startNt = st.getAttribute("data-pd-pd-nt-extra") === "1" ? "1" : "0";
            if (startNt !== targetNt) {
                continue;
            }
            if (startTrEntityKind(st) !== targetKind) {
                continue;
            }
            if (
                targetPvc &&
                (st.getAttribute("data-perimeter-variant-code") || "") !== targetPvc
            ) {
                continue;
            }
            if (startTrEntityLabels(st).indexOf(targetLabel) >= 0) {
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
                inp.value = value !== "—" ? value : "";
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
                var histInp = histTd.querySelector("input.fuel-param-input");
                var histValue = row.hist_value != null ? String(row.hist_value) : "";
                var histTt = row.hist_numeric_tooltip || "";
                if (histInp) {
                    histInp.value = histValue && histValue !== "—" ? histValue : "";
                    if (histTt) {
                        histInp.setAttribute("data-db-full", histTt);
                    } else {
                        histInp.removeAttribute("data-db-full");
                    }
                } else if (!canEditHistCell(row, cfg)) {
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
                paramTd.innerHTML = buildParameterCellHtml(row);
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

    /** После вставки расчётных строк вернуть «Проверка …» сразу под якорной строкой. */
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
                var anchorPk = MERGE_ROW_INSERT_AFTER[verifyPk];
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
                if (verifyIdx === anchorIdx + 1) {
                    continue;
                }
                blockRows.splice(verifyIdx, 1);
                anchorIdx = blockRows.indexOf(anchorTr);
                var insertBefore =
                    anchorIdx + 1 < blockRows.length
                        ? blockRows[anchorIdx + 1]
                        : null;
                blockRows.splice(anchorIdx + 1, 0, verifyTr);
                if (insertBefore) {
                    tbody.insertBefore(verifyTr, insertBefore);
                } else {
                    anchorTr.parentNode.appendChild(verifyTr);
                }
                moved = true;
                break;
            }
            if (!moved) {
                break;
            }
        }
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
            var newTr = buildRowTr(
                mergeRow,
                cfg,
                years,
                yearIsPlan,
                showPerimeterCol,
                showHistCol
            );
            var insertBefore = findInsertBeforeForMergedRow(blockRows, pk, order);
            if (insertBefore) {
                tbody.insertBefore(newTr, insertBefore);
                var ix = blockRows.indexOf(insertBefore);
                if (ix >= 0) {
                    blockRows.splice(ix, 0, newTr);
                } else {
                    blockRows.push(newTr);
                }
            } else {
                var last = blockRows[blockRows.length - 1];
                if (last && last.nextElementSibling) {
                    tbody.insertBefore(newTr, last.nextElementSibling);
                } else if (last) {
                    last.parentNode.appendChild(newTr);
                } else {
                    tbody.appendChild(newTr);
                }
                blockRows.push(newTr);
            }
        });
        repositionVerifyRowsInBlock(tbody, blockRows);
        syncBlockRowspans(startTr, blockRows);
    }

    function insertBlockAfter(tbody, afterTr, block, cfg, years, yearIsPlan, showPerimeterCol, showHistCol) {
        var frag = document.createDocumentFragment();
        var built = [];
        block.forEach(function (row) {
            built.push(
                buildRowTr(row, cfg, years, yearIsPlan, showPerimeterCol, showHistCol)
            );
        });
        built.forEach(function (tr) {
            frag.appendChild(tr);
        });
        if (afterTr && afterTr.nextSibling) {
            tbody.insertBefore(frag, afterTr.nextSibling);
        } else if (afterTr) {
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
        block.forEach(function (row) {
            built.push(
                buildRowTr(row, cfg, years, yearIsPlan, showPerimeterCol, showHistCol)
            );
        });
        built.forEach(function (tr) {
            frag.appendChild(tr);
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
            renderSummaryTableBody(payload);
            return;
        }
        var cfg = payload.config || {};
        var years = payload.years || [];
        var yearIsPlan = payload.year_is_plan || {};
        var rows = payload.summary_rows || [];
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
            if ((!existing || !existing.start) && blockIsVerifyOnly(block)) {
                var verifyFallbackStart = findBlockStartByEntity(tbody, row);
                if (verifyFallbackStart) {
                    existing = {
                        start: verifyFallbackStart,
                        rows: collectBlockRows(verifyFallbackStart),
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
                if (isChiOnlySegmentBlock(block)) {
                    continue;
                }
                var baseStart = findBaseBlockStartForNtRow(tbody, row) || fallbackStart;
                var insertedStart;
                if (baseStart) {
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
                    var afterNtSubtree = findInsertAfterForNtSubtreeRow(tbody, row);
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
                }
                if (insertedStart) {
                    blockMap[fp] = {
                        start: insertedStart,
                        rows: collectBlockRows(insertedStart),
                    };
                }
            } else {
                var insertedBaseStart = insertBlockAfter(
                    tbody,
                    fallbackStart ? lastTrOfBlock(fallbackStart) : tbody.lastElementChild,
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
            }
        }
        document.dispatchEvent(new CustomEvent("pd-summary-rows-rendered"));
    }

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

        var frag = document.createDocumentFragment();
        if (!rows.length) {
            var emptyTr = document.createElement("tr");
            var emptyTd = document.createElement("td");
            emptyTd.colSpan =
                (showHistCol ? 3 : 2) +
                years.length +
                1 +
                (showPerimeterCol ? 1 : 0);
            emptyTd.className = "text-center text-muted";
            emptyTd.textContent = "Нет данных для текущей версии БД.";
            emptyTr.appendChild(emptyTd);
            frag.appendChild(emptyTr);
        } else {
            rows.forEach(function (row) {
                frag.appendChild(
                    buildRowTr(row, cfg, years, yearIsPlan, showPerimeterCol, showHistCol)
                );
            });
        }
        tbody.replaceChildren(frag);
        injectLiveCalcData(payload);
        if (typeof window.__pdPdSummarySyncPerimeterVariantLabels === "function") {
            window.__pdPdSummarySyncPerimeterVariantLabels();
        }
        if (typeof window.__pdPdSummaryInitTableTooltips === "function") {
            window.__pdPdSummaryInitTableTooltips();
        }
        document.dispatchEvent(new CustomEvent("pd-summary-rows-rendered"));
    }

    var loadedSegments = {};
    var segmentLoadPromises = {};
    var segmentLoadingDepth = 0;

    function pdSummarySegmentToggleButtons() {
        return [
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
        var qs = params.toString();
        return qs ? path + "?" + qs : path;
    }

    function fetchSegmentPayload(segments) {
        var sorted = segments.slice().sort();
        var cacheKey = sorted.join(",");
        if (segmentLoadPromises[cacheKey]) {
            return segmentLoadPromises[cacheKey];
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
        if (loadedSegments[segmentName]) {
            return Promise.resolve();
        }
        var tbody =
            document.getElementById("powerDemandSummaryTbody") ||
            document.querySelector("#powerDemandSummaryTable tbody");
        if (!tbody) {
            return Promise.reject(new Error("tbody не найден"));
        }
        var loadPayload = function (name) {
            return fetchSegmentPayload([name]).then(function (payload) {
                mergeSegmentRowsIntoTbody(tbody, payload, false);
            });
        };
        if (
            segmentName === "chi" &&
            (shellConfig.scope === "oes" || shellConfig.scope === "fo") &&
            !loadedSegments.nt_extra
        ) {
            return loadSegmentIntoTable("nt_extra").then(function () {
                return loadPayload("chi");
            });
        }
        return loadPayload(segmentName);
    }

    function loadSegmentsIntoTable(segmentNames) {
        var ordered = orderSegmentLoadNames(segmentNames);
        var needed = ordered.filter(function (name) {
            return name && !loadedSegments[name];
        });
        if (!needed.length) {
            return Promise.resolve();
        }
        var tbody =
            document.getElementById("powerDemandSummaryTbody") ||
            document.querySelector("#powerDemandSummaryTable tbody");
        if (!tbody) {
            return Promise.reject(new Error("tbody не найден"));
        }
        return needed.reduce(function (chain, name) {
            return chain.then(function () {
                return fetchSegmentPayload([name]).then(function (payload) {
                    mergeSegmentRowsIntoTbody(tbody, payload, false);
                });
            });
        }, Promise.resolve());
    }

    window.__pdSummaryEnsureSegments = function (segmentNames) {
        if (!segmentNames || !segmentNames.length) {
            return Promise.resolve();
        }
        var ordered = orderSegmentLoadNames(segmentNames);
        var needed = ordered.filter(function (s) {
            return s && !loadedSegments[s];
        });
        if (!needed.length) {
            return Promise.resolve();
        }
        pdSummaryShowSegmentLoading();
        var loadPromise =
            needed.length === 1
                ? loadSegmentIntoTable(needed[0])
                : loadSegmentsIntoTable(needed);
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
            mergeSegmentRowsIntoTbody(tbody, payload, true);
            return payload;
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
