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
        var readonlyKeys = cfg.pd_readonly_parameter_keys || [];
        var readonlySet = {};
        readonlyKeys.forEach(function (k) {
            readonlySet[k] = true;
        });

        if (row.pd_pd_verify_for_row) {
            classes.push("pd-pd-verify-for-row");
        }
        if (row.pd_pd_chi_row) {
            classes.push("pd-pd-chi-row", "summary-row-hidden");
        } else if (
            active === "oes" &&
            pk &&
            readonlySet[pk]
        ) {
            classes.push("pd-pd-calc-max-row", "summary-row-hidden");
        }
        if (row.pd_pd_verify_for_row) {
            classes.push("summary-row-hidden");
        } else if (
            active in { oes: 1, fo: 1, ez: 1 } &&
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
        return canEditSlice(row, cfg) && !READONLY_KEYS[pk];
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
        } else if (
            cfg.active_summary === "ez" &&
            pk === "calculated_max_ez_mw" &&
            row.hist_value === "—"
        ) {
            /* пусто */
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
        if (row.pd_pd_chi_row) {
            tr.setAttribute("data-pd-pd-chi-row", "1");
        }
        if (row.pd_pd_verify_a_parameter_key) {
            tr.setAttribute("data-pd-pd-verify-a", row.pd_pd_verify_a_parameter_key);
            tr.setAttribute("data-pd-pd-verify-b", row.pd_pd_verify_b_parameter_key);
        }
        tr.setAttribute("data-entity-block-size", String(row.entity_rowspan || 1));
        if (row.show_entity_cell) {
            tr.setAttribute("data-is-block-start", "1");
        }
        if (row.show_entity_cell && row.pd_pd_entity_label_compact_nt) {
            tr.setAttribute("data-pd-pd-entity-label-full", row.entity_label || "");
            tr.setAttribute(
                "data-pd-pd-entity-label-compact-nt",
                row.pd_pd_entity_label_compact_nt
            );
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
        if (document.getElementById("pd-oes-live-calc-data")) {
            return;
        }
        var el = document.createElement("script");
        el.type = "application/json";
        el.id = "pd-oes-live-calc-data";
        el.textContent = JSON.stringify(payload.pd_oes_live_calc_js);
        document.body.appendChild(el);
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

    function buildDataUrl() {
        var path = shellConfig.data_path;
        var qs = window.location.search || "";
        return path + qs;
    }

    window.__pdSummaryRowsReady = fetch(buildDataUrl(), {
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
                throw new Error((payload && payload.error) || "Ошибка загрузки данных");
            }
            renderSummaryTableBody(payload);
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
