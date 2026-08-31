/**
 * Клиентский рендер tbody сводок потребления (ОЭС / ФО / ЭЗ).
 * Shell-страница загружает JSON и строит строки таблицы вместо многомегабайтного HTML.
 */
(function () {
    "use strict";

    var configEl = document.getElementById("ec-summary-client-render-config");
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

    var tableElInit = document.getElementById("powerDemandSummaryTable");
    var summaryViewInit =
        (tableElInit && tableElInit.getAttribute("data-summary-view")) ||
        shellConfig.scope ||
        "oes";
    if (window.__pdEcSummaryTerritoryCompactMode === undefined) {
        try {
            window.__pdEcSummaryTerritoryCompactMode =
                sessionStorage.getItem(
                    "pdEcSummaryTerritoryCompact_" + summaryViewInit
                ) === "1";
        } catch (eCompactInit) {
            window.__pdEcSummaryTerritoryCompactMode = false;
        }
    }
    try {
        if (window.__pdEcSummarySiprMode === undefined) {
            window.__pdEcSummarySiprMode =
                sessionStorage.getItem("pdEcSummarySiprMode_" + summaryViewInit) ===
                "1";
        }
        if (window.__pdEcSummaryGaesDetailMode === undefined) {
            var gaesStored = sessionStorage.getItem(
                "pdEcSummaryWithoutGaes_" + summaryViewInit
            );
            var gaesDefaultOff =
                shellConfig.summary_variant_toggle_default_off !== false;
            window.__pdEcSummaryGaesDetailMode =
                gaesStored === null ? !gaesDefaultOff : gaesStored === "1";
        }
        if (window.__pdEcSummaryNtDetailMode === undefined) {
            window.__pdEcSummaryNtDetailMode =
                sessionStorage.getItem("pdEcSummaryNtDetail_" + summaryViewInit) ===
                "1";
        }
        if (window.__pdEcSummaryIsolatedEnergyUnitsMode === undefined) {
            window.__pdEcSummaryIsolatedEnergyUnitsMode =
                sessionStorage.getItem(
                    "pdEcSummaryIsolatedEnergyUnits_" + summaryViewInit
                ) === "1";
        }
        if (window.__pdEcSummaryVerificationMode === undefined) {
            window.__pdEcSummaryVerificationMode =
                sessionStorage.getItem(
                    "pdEcSummaryVerification_" + summaryViewInit
                ) === "1";
        }
    } catch (eFlagInit) {
        if (window.__pdEcSummarySiprMode === undefined) {
            window.__pdEcSummarySiprMode = false;
        }
        if (window.__pdEcSummaryGaesDetailMode === undefined) {
            window.__pdEcSummaryGaesDetailMode = false;
        }
        if (window.__pdEcSummaryNtDetailMode === undefined) {
            window.__pdEcSummaryNtDetailMode = false;
        }
        if (window.__pdEcSummaryIsolatedEnergyUnitsMode === undefined) {
            window.__pdEcSummaryIsolatedEnergyUnitsMode = false;
        }
        if (window.__pdEcSummaryVerificationMode === undefined) {
            window.__pdEcSummaryVerificationMode = false;
        }
    }

    var READONLY_KEYS = {};
    (shellConfig.pd_readonly_parameter_keys || []).forEach(function (k) {
        READONLY_KEYS[k] = true;
    });
    var SIPR_KEYS = {};
    (shellConfig.pd_ec_sipr_row_keys || []).forEach(function (k) {
        SIPR_KEYS[k] = true;
    });
    var NORMAL_KEYS = {
        energy_consumption_mln_kvt_ch: true,
        energy_consumption_yoy_growth_pct: true,
    };
    var SUMMARY_SCOPES = { oes: true, fo: true, ez: true };
    var RENDER_ROWS_CHUNK_SIZE = 32;

    function escapeAttr(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/"/g, "&quot;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }

    function escapeHtml(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }

    function setDataAttr(el, name, value) {
        if (value === undefined || value === null || value === "") {
            return;
        }
        el.setAttribute(name, String(value));
    }

    function flagAttr(tr, cond, name) {
        if (cond) {
            tr.setAttribute(name, "1");
        }
    }

    function isVerificationRow(row) {
        var label = String(row.entity_label || "");
        return label.indexOf("Проверка ") === 0;
    }

    function isVerifyForRow(row) {
        var label = String(row.entity_label || "");
        return (
            label.indexOf("Проверка для ") === 0 ||
            row.entity_kind === "oes_ees_model_verification" ||
            row.entity_kind === "oes_ees_sync_table_verification"
        );
    }

    function readStoredVisibleKeys() {
        var table = document.getElementById("powerDemandSummaryTable");
        var view =
            (table && table.getAttribute("data-summary-view")) ||
            shellConfig.scope ||
            "oes";
        var route =
            (table && table.getAttribute("data-summary-route-variant")) || "max";
        var key;
        if (view === "fo") {
            key =
                route === "coeff"
                    ? "powerDemandSummaryFoCoeffVisibleRowKeys"
                    : "powerDemandSummaryFoVisibleRowKeysV3";
        } else if (view === "ez") {
            key =
                route === "coeff"
                    ? "powerDemandSummaryEzCoeffVisibleRowKeys"
                    : "powerDemandSummaryEzVisibleRowKeysV3";
        } else {
            key =
                route === "coeff"
                    ? "powerDemandSummaryOesCoeffVisibleRowKeysV2"
                    : "powerDemandSummaryOesVisibleRowKeysV4";
        }
        try {
            var raw = sessionStorage.getItem(key);
            if (!raw) {
                return null;
            }
            var arr = JSON.parse(raw);
            if (!Array.isArray(arr)) {
                return null;
            }
            var set = {};
            arr.forEach(function (k) {
                set[k] = true;
            });
            return set;
        } catch (eKeys) {
            return null;
        }
    }

    function yearValueMeaningful(raw) {
        var t = String(raw == null ? "" : raw).trim();
        if (t === "" || t === "—") {
            return false;
        }
        var n = parseFloat(t.replace(/\s/g, "").replace(",", "."));
        if (!Number.isFinite(n)) {
            return true;
        }
        return n !== 0;
    }

    function rowHasMeaningfulYearValues(row) {
        var values = row.year_values || [];
        for (var i = 0; i < values.length; i++) {
            if (yearValueMeaningful(values[i])) {
                return true;
            }
        }
        return false;
    }

    function rowInitiallyHidden(row, cfg) {
        var pk = row.parameter_key || "";
        var active = cfg.active_summary || "";
        var siprOn = window.__pdEcSummarySiprMode === true;
        var compact = window.__pdEcSummaryTerritoryCompactMode === true;
        var gaesDetailOn = window.__pdEcSummaryGaesDetailMode === true;
        var ntDetailOn = window.__pdEcSummaryNtDetailMode === true;
        var verificationOn = window.__pdEcSummaryVerificationMode === true;
        var isolatedOn = window.__pdEcSummaryIsolatedEnergyUnitsMode === true;
        var collapsedNtGaes = !gaesDetailOn && !ntDetailOn;
        var expandedNtGaes = gaesDetailOn && ntDetailOn;
        var ntOnGaesOff = ntDetailOn && !gaesDetailOn;

        if (siprOn) {
            if (NORMAL_KEYS[pk]) {
                return true;
            }
        } else if (SIPR_KEYS[pk]) {
            return true;
        }
        if (
            cfg._visibleKeys &&
            (NORMAL_KEYS[pk] || SIPR_KEYS[pk]) &&
            !cfg._visibleKeys[pk]
        ) {
            return true;
        }
        if (SUMMARY_SCOPES[active] && row.pd_ec_hide_when_isolated_eu_on && isolatedOn) {
            return true;
        }
        if (SUMMARY_SCOPES[active] && row.pd_ec_o1_form_row && !isolatedOn) {
            return true;
        }
        if (SUMMARY_SCOPES[active] && row.pd_ec_gaes_extra_row && !gaesDetailOn) {
            if (
                !(
                    (collapsedNtGaes && row.pd_ec_collapsed_nt_gaes_visible_row) ||
                    (ntOnGaesOff && row.pd_ec_nt_on_gaes_off_visible_row)
                )
            ) {
                return true;
            }
        }
        if (SUMMARY_SCOPES[active] && row.pd_ec_nt_extra_row && !ntDetailOn) {
            return true;
        }
        if (collapsedNtGaes && row.pd_ec_collapsed_nt_gaes_redundant_row) {
            return true;
        }
        if (ntOnGaesOff && row.pd_ec_nt_on_gaes_off_redundant_row) {
            return true;
        }
        if (expandedNtGaes && row.pd_ec_expanded_nt_gaes_redundant_row) {
            return true;
        }
        if (SUMMARY_SCOPES[active] && row.pd_ec_summary_table_only_row && !compact) {
            return true;
        }
        if (
            SUMMARY_SCOPES[active] &&
            compact &&
            (row.pd_ec_territory_detail_row || row.pd_ec_territory_compact_hide_row)
        ) {
            return true;
        }
        if (row.pd_ec_first_sa_gaes_compact_variant === "detail" && compact) {
            return true;
        }
        if (compact && pk === "gaes_charge_consumption_mln_kvt_ch") {
            return true;
        }
        if ((isVerificationRow(row) || isVerifyForRow(row)) && !verificationOn) {
            return true;
        }
        return false;
    }

    function prepareRowsForClientRender(rows, cfg) {
        var showEmptyOn = window.__pdEcSummaryShowEmptyMode === true;
        var gaesDetailOn = window.__pdEcSummaryGaesDetailMode === true;
        var ntDetailOn = window.__pdEcSummaryNtDetailMode === true;
        var result = [];
        var i = 0;
        while (i < rows.length) {
            var row = rows[i];
            if (!row.show_entity_cell) {
                var stray = Object.assign({}, row);
                stray.is_block_start = false;
                stray.entity_block_size = 1;
                stray._hidden = rowInitiallyHidden(stray, cfg);
                result.push(stray);
                i += 1;
                continue;
            }
            var blockSize = Math.max(parseInt(row.entity_rowspan || 1, 10), 1);
            var block = rows.slice(i, i + blockSize);
            i += blockSize;
            var hiddenFlags = block.map(function (r) {
                return rowInitiallyHidden(r, cfg);
            });
            var isVerifyBlock =
                isVerificationRow(block[0]) || isVerifyForRow(block[0]);
            var skipEmptyHide = block.some(function (r) {
                return !!r.pd_ec_skip_empty_hide_row;
            });
            var blockHasNtExtra = block.some(function (r) {
                return !!r.pd_ec_nt_extra_row;
            });
            var blockHasNtWithout = block.some(function (r) {
                return !!r.pd_ec_nt_without_row;
            });
            var blockHasGaesExtra = block.some(function (r) {
                return !!r.pd_ec_gaes_extra_row;
            });
            var blockHasGaesWithout = block.some(function (r) {
                return !!r.pd_ec_gaes_without_row;
            });
            var blockIsCzRussiaWithoutNt = block.some(function (r) {
                return (
                    r.entity_kind === "centralized_zone" &&
                    !!r.pd_ec_nt_without_row
                );
            });
            var hasVisibleValue = block.some(function (r, idx) {
                return !hiddenFlags[idx] && rowHasMeaningfulYearValues(r);
            });
            var hideEmptyBlock =
                !showEmptyOn &&
                !isVerifyBlock &&
                !skipEmptyHide &&
                !blockIsCzRussiaWithoutNt &&
                !(ntDetailOn && (blockHasNtExtra || blockHasNtWithout)) &&
                !(gaesDetailOn && (blockHasGaesExtra || blockHasGaesWithout)) &&
                !hasVisibleValue;
            var noteSource = null;
            for (var ni = 0; ni < block.length; ni++) {
                if (block[ni].show_entity_note_cell) {
                    noteSource = block[ni];
                    break;
                }
            }
            var firstPaint = -1;
            var paintCount = 0;
            hiddenFlags.forEach(function (hidden, idx) {
                if (!hidden && !hideEmptyBlock) {
                    if (firstPaint < 0) {
                        firstPaint = idx;
                    }
                    paintCount += 1;
                }
            });
            if (firstPaint < 0) {
                firstPaint = 0;
                paintCount = 1;
            }
            block.forEach(function (r, idx) {
                var copy = Object.assign({}, r);
                copy.is_block_start = idx === 0;
                copy.entity_block_size = block.length;
                copy._hidden = hiddenFlags[idx];
                copy._empty_hidden = hideEmptyBlock;
                copy.show_entity_cell = idx === firstPaint;
                copy.entity_rowspan = paintCount;
                if (idx === firstPaint && noteSource) {
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

    function computeRowClasses(row, cfg) {
        var classes = [
            "summary-kind-" + (row.entity_kind || ""),
            "summary-row-param",
        ];
        if (row._hidden || rowInitiallyHidden(row, cfg)) {
            classes.push("summary-row-hidden");
        }
        if (row._empty_hidden) {
            classes.push("summary-row-empty-block-hidden");
        }
        if (isVerificationRow(row)) {
            classes.push("pd-ec-verification-row");
        }
        if (isVerifyForRow(row)) {
            classes.push("pd-ec-verify-for-row");
        }
        return classes.join(" ");
    }

    function canEditSlice(row, cfg) {
        var gaesChargeStation =
            row.parameter_key === "gaes_charge_consumption_mln_kvt_ch" &&
            row.gaes_station_id;
        var withGaesDb =
            row.pd_ec_gaes_with_charge_db_block &&
            row.parameter_key !== "gaes_charge_consumption_mln_kvt_ch" &&
            !row.pd_ec_formula_derived_row;
        var demandOk =
            !!row.demand_model_name || gaesChargeStation || withGaesDb;
        var gaesSynthetic = !!row.pd_ec_gaes_injected_row;
        return (
            demandOk &&
            (row.parent_fk_column == null || row.parent_id != null) &&
            (!gaesSynthetic || gaesChargeStation || withGaesDb)
        );
    }

    function isReadonlyComposite(row) {
        return (
            !!row.pd_ec_summary_readonly_row ||
            row.entity_kind === "ees_energy_consumption_composite"
        );
    }

    function canEditCell(row, cfg) {
        if (!cfg.can_edit_summary_cells) {
            return false;
        }
        var pk = row.parameter_key || "";
        if (READONLY_KEYS[pk]) {
            return false;
        }
        if (isReadonlyComposite(row)) {
            return false;
        }
        if (row.pd_ec_formula_derived_row && !row.pd_ec_cz_o1_with_nt_manual_row) {
            return false;
        }
        return canEditSlice(row, cfg);
    }

    function canEditNote(row, cfg) {
        if (!cfg.can_edit_summary_cells) {
            return false;
        }
        if (isReadonlyComposite(row) || row.pd_ec_gaes_injected_row) {
            return false;
        }
        if (row.pd_ec_formula_derived_row && !row.pd_ec_cz_o1_with_nt_manual_row) {
            return false;
        }
        return (
            !!(row.demand_model_name) &&
            (row.parent_fk_column == null || row.parent_id != null)
        );
    }

    function yearOutOfRange(row, year) {
        if (!row.pd_ec_skip_perimeter_variant_year_bounds) {
            var fromY = row.perimeter_variant_from_year;
            var toY = row.perimeter_variant_to_year;
            if (fromY != null && year < fromY) {
                return true;
            }
            if (toY != null && year > toY) {
                return true;
            }
        }
        var sakhaThrough = row.sakha_membership_through_year;
        if (sakhaThrough != null) {
            if (row.pd_ec_sakha_tites_through_year_row && year > sakhaThrough) {
                return true;
            }
            if (row.pd_ec_sakha_oes_east_from_year_row && year <= sakhaThrough) {
                return true;
            }
        }
        return false;
    }

    function gaesStationYearOutOfRange(row, year) {
        if (
            row.parameter_key !== "gaes_charge_consumption_mln_kvt_ch" ||
            !row.gaes_station_id
        ) {
            return false;
        }
        var ymin = row.gaes_charge_display_year_min;
        var ymax = row.gaes_charge_display_year_max;
        if (ymin != null && year < ymin) {
            return true;
        }
        if (ymax != null && year > ymax) {
            return true;
        }
        return false;
    }

    function applyTrDataAttrs(tr, row) {
        setDataAttr(tr, "data-parameter-key", row.parameter_key);
        setDataAttr(tr, "data-perimeter-variant-code", row.perimeter_variant_code);
        if (row.perimeter_variant_from_year != null) {
            setDataAttr(
                tr,
                "data-perimeter-variant-from-year",
                row.perimeter_variant_from_year
            );
        }
        if (row.perimeter_variant_to_year != null) {
            setDataAttr(
                tr,
                "data-perimeter-variant-to-year",
                row.perimeter_variant_to_year
            );
        }
        setDataAttr(tr, "data-demand-model-name", row.demand_model_name);
        if (row.id_union_energy_system != null) {
            setDataAttr(tr, "data-id-union-energy-system", row.id_union_energy_system);
        }
        flagAttr(tr, row.pd_ec_gaes_extra_row, "data-pd-ec-gaes-extra");
        flagAttr(tr, row.pd_ec_gaes_without_row, "data-pd-ec-gaes-without");
        flagAttr(tr, row.pd_ec_nt_extra_row, "data-pd-ec-nt-extra");
        flagAttr(tr, row.pd_ec_nt_without_row, "data-pd-ec-nt-without");
        flagAttr(
            tr,
            row.pd_ec_collapsed_nt_gaes_visible_row,
            "data-pd-ec-collapsed-nt-gaes-visible"
        );
        flagAttr(
            tr,
            row.pd_ec_collapsed_nt_gaes_redundant_row,
            "data-pd-ec-collapsed-nt-gaes-redundant"
        );
        flagAttr(
            tr,
            row.pd_ec_nt_on_gaes_off_visible_row,
            "data-pd-ec-nt-on-gaes-off-visible"
        );
        flagAttr(
            tr,
            row.pd_ec_nt_on_gaes_off_redundant_row,
            "data-pd-ec-nt-on-gaes-off-redundant"
        );
        flagAttr(
            tr,
            row.pd_ec_expanded_nt_gaes_redundant_row,
            "data-pd-ec-expanded-nt-gaes-redundant"
        );
        flagAttr(tr, row.pd_ec_skip_empty_hide_row, "data-pd-ec-skip-empty-hide");
        flagAttr(
            tr,
            row.pd_ec_sipr_integer_display_row,
            "data-pd-ec-sipr-integer-display"
        );
        flagAttr(tr, row.pd_ec_o1_form_row, "data-pd-ec-o1-form");
        flagAttr(
            tr,
            row.pd_ec_hide_when_isolated_eu_on,
            "data-pd-ec-hide-when-isolated-eu"
        );
        flagAttr(
            tr,
            row.pd_ec_hide_when_summary_table_and_o1,
            "data-pd-ec-hide-when-summary-table-and-o1"
        );
        flagAttr(tr, row.pd_ec_decentralized_zone_mark, "data-pd-ec-decentralized-zone");
        flagAttr(
            tr,
            row.pd_ec_chukotka_reference_align,
            "data-pd-ec-chukotka-reference-align"
        );
        flagAttr(
            tr,
            row.pd_ec_verification_nt_split_only,
            "data-pd-ec-verification-nt-only"
        );
        flagAttr(
            tr,
            row.pd_ec_verification_omit_sipr_abs,
            "data-pd-ec-verification-omit-sipr-abs"
        );
        flagAttr(
            tr,
            row.pd_ec_verification_require_isolated_eu,
            "data-pd-ec-verification-require-isolated-eu"
        );
        if (row.pd_ec_sync_verify_nt_visibility) {
            setDataAttr(
                tr,
                "data-pd-ec-sync-verify-nt-vis",
                row.pd_ec_sync_verify_nt_visibility
            );
        }
        flagAttr(tr, row.pd_ec_territory_detail_row, "data-pd-ec-territory-detail");
        flagAttr(
            tr,
            row.pd_ec_territory_detail_relaxed_compact_nt_gaes,
            "data-pd-ec-territory-detail-relaxed-nt-gaes"
        );
        flagAttr(
            tr,
            row.pd_ec_territory_compact_hide_row,
            "data-pd-ec-territory-compact-hide"
        );
        flagAttr(
            tr,
            row.pd_ec_summary_table_only_row,
            "data-pd-ec-summary-table-only"
        );
        if (row.pd_ec_first_sa_gaes_compact_variant) {
            setDataAttr(
                tr,
                "data-pd-ec-first-sa-gaes",
                row.pd_ec_first_sa_gaes_compact_variant
            );
        }
        var needLabelSync =
            row.pd_ec_entity_label_compact ||
            row.pd_ec_entity_label_compact_nt ||
            row.pd_ec_entity_label_compact_nt_gaes ||
            row.pd_ec_ees_verification_nt_collapsed_label ||
            row.pd_ec_sync_verify_label_matrix;
        if (needLabelSync) {
            setDataAttr(tr, "data-pd-ec-entity-label-full", row.entity_label || "");
            if (row.pd_ec_chersky_transfer_note) {
                setDataAttr(
                    tr,
                    "data-pd-ec-chersky-transfer-note",
                    row.pd_ec_chersky_transfer_note
                );
            }
            if (row.pd_ec_entity_label_compact) {
                setDataAttr(
                    tr,
                    "data-pd-ec-entity-label-compact",
                    row.pd_ec_entity_label_compact
                );
            }
            if (row.pd_ec_entity_label_compact_nt) {
                setDataAttr(
                    tr,
                    "data-pd-ec-entity-label-compact-nt",
                    row.pd_ec_entity_label_compact_nt
                );
            }
            if (row.pd_ec_entity_label_compact_nt_gaes) {
                setDataAttr(
                    tr,
                    "data-pd-ec-entity-label-compact-both",
                    row.pd_ec_entity_label_compact_nt_gaes
                );
            }
            if (row.pd_ec_ees_verification_nt_collapsed_label) {
                setDataAttr(
                    tr,
                    "data-pd-ec-ees-verify-collapsed-label",
                    row.pd_ec_ees_verification_nt_collapsed_label
                );
            }
            if (row.pd_ec_sync_verify_label_matrix) {
                setDataAttr(
                    tr,
                    "data-pd-ec-sync-verify-nt1-gaes1",
                    row.pd_ec_sync_verify_l_nt1_gaes1 || ""
                );
                setDataAttr(
                    tr,
                    "data-pd-ec-sync-verify-nt1-gaes0",
                    row.pd_ec_sync_verify_l_nt1_gaes0 || ""
                );
                setDataAttr(
                    tr,
                    "data-pd-ec-sync-verify-nt0-gaes1",
                    row.pd_ec_sync_verify_l_nt0_gaes1 || ""
                );
                setDataAttr(
                    tr,
                    "data-pd-ec-sync-verify-nt0-gaes0",
                    row.pd_ec_sync_verify_l_nt0_gaes0 || ""
                );
            }
        }
        tr.setAttribute("data-entity-block-size", String(row.entity_block_size || row.entity_rowspan || 1));
        if (row.is_block_start || (row.is_block_start !== false && row.show_entity_cell && row.entity_block_size == null)) {
            tr.setAttribute("data-is-block-start", "1");
        }
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
            var selClass = "form-select form-select-sm pd-ec-perimeter-variant-select";
            if (row.pd_ec_formula_derived_row) {
                selClass += " pd-ec-formula-variant-select";
            }
            sel.className = selClass;
            sel.setAttribute("data-initial", row.perimeter_variant_code || "");
            sel.setAttribute("data-demand-model-name", row.demand_model_name || "");
            sel.setAttribute("data-block-kind", row.pd_ec_summary_block_kind || "base");
            if (row.parent_fk_column) {
                sel.setAttribute("data-parent-fk", row.parent_fk_column);
            }
            if (row.parent_id != null) {
                sel.setAttribute("data-parent-id", String(row.parent_id));
            }
            if (row.pd_ec_summary_block_scope) {
                sel.setAttribute("data-block-scope", row.pd_ec_summary_block_scope);
            }
            if (row.pd_ec_formula_persist_kind) {
                sel.setAttribute("data-formula-persist-kind", row.pd_ec_formula_persist_kind);
            }
            if (row.pd_ec_formula_source_pvc != null) {
                sel.setAttribute(
                    "data-formula-source-pvc",
                    row.pd_ec_formula_source_pvc || ""
                );
            }
            if (row.pd_ec_formula_persist_context) {
                sel.setAttribute(
                    "data-formula-persist-context",
                    JSON.stringify(row.pd_ec_formula_persist_context)
                );
            }
            sel.title = row.pd_ec_formula_derived_row
                ? "Расчётная строка: значения на экране по формуле; выбранный вариант — под каким кодом хранить/читать данные в БД"
                : "Вариант периметра для записи и чтения данных этого блока в БД";
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
            var selectedOpt = sel.options[sel.selectedIndex];
            if (selectedOpt) {
                selectedLabel =
                    String(selectedOpt.textContent || "").trim() || selectedLabel;
            }
            lbl.textContent = selectedLabel || "не указано";
        } else {
            var span = document.createElement("span");
            span.className = "text-wrap";
            if (row.pd_ec_formula_derived_row) {
                span.title =
                    "Расчётная строка — вариант задаётся в выпадающем списке у блока «без заряда ГАЭС»";
            }
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
        var wrap = document.createElement("span");
        wrap.className = "text-wrap";
        wrap.appendChild(document.createTextNode(row.entity_label || ""));
        if (row.pd_ec_chersky_transfer_note) {
            var note = document.createElement("span");
            note.className = "pd-ec-chersky-transfer-note ms-1";
            note.textContent = row.pd_ec_chersky_transfer_note;
            wrap.appendChild(document.createTextNode(" "));
            wrap.appendChild(note);
        }
        if (
            row.pd_ec_decentralized_zone_mark ||
            row.pd_ec_o1_form_row ||
            row.pd_ec_show_o1_badge
        ) {
            var mark = document.createElement("span");
            if (row.pd_ec_decentralized_zone_mark) {
                mark.className = "pd-pd-dz-mark ms-1";
            } else {
                mark.className =
                    "text-danger fw-black d-inline-block pd-ec-o1-form-badge";
                mark.style.cssText =
                    "cursor: help; line-height: 1; font-size: 1.125em; font-weight: 900; vertical-align: middle; margin-left: 0.35em; white-space: nowrap;";
            }
            mark.setAttribute("data-bs-toggle", "tooltip");
            mark.setAttribute("data-bs-placement", "top");
            mark.title = "Форма О-1";
            mark.setAttribute("aria-label", "Форма О-1");
            mark.textContent = "О-1";
            wrap.appendChild(document.createTextNode(" "));
            wrap.appendChild(mark);
        }
        div.appendChild(wrap);
        td.appendChild(div);
        return td;
    }

    function buildParameterCellHtml(row, cfg) {
        var label = escapeHtml(row.parameter_label || "");
        var pk = row.parameter_key || "";
        if (pk === "gaes_charge_consumption_mln_kvt_ch") {
            var stName = escapeHtml(row.gaes_charge_row_station_name || "Без названия");
            var inner;
            if (row.gaes_station_id && shellConfig.station_details_path_template) {
                var href = String(shellConfig.station_details_path_template).replace(
                    "{station_id}",
                    String(row.gaes_station_id)
                );
                var qs = [];
                if (cfg.start_year != null) {
                    qs.push("start_year=" + encodeURIComponent(cfg.start_year));
                }
                if (cfg.end_year != null) {
                    qs.push("end_year=" + encodeURIComponent(cfg.end_year));
                }
                if (cfg.rounding_digits != null) {
                    qs.push(
                        "rounding_digits=" + encodeURIComponent(cfg.rounding_digits)
                    );
                    qs.push(
                        "rounding_digits_gaes=" +
                            encodeURIComponent(cfg.rounding_digits)
                    );
                }
                if (qs.length) {
                    href += (href.indexOf("?") >= 0 ? "&" : "?") + qs.join("&");
                }
                inner =
                    '<a href="' +
                    escapeAttr(href) +
                    '" class="fw-bold link-primary link-underline-opacity-75" target="_blank" rel="noopener noreferrer" title="Карточка электростанции" aria-label="Открыть карточку электростанции «' +
                    escapeAttr(row.gaes_charge_row_station_name || "Без названия") +
                    '» в новом окне">' +
                    stName +
                    "</a>";
            } else {
                inner = "<strong>" + stName + "</strong>";
            }
            return (
                '<span class="text-wrap">Потребление электрической энергии ГАЭС на заряд, млн кВтч (' +
                inner +
                ")</span>"
            );
        }
        var tip = row.pd_parameter_formula_tooltip || "";
        if (tip) {
            return (
                '<span class="text-wrap">' +
                label +
                '<i class="bi bi-info-circle text-primary ms-1" data-bs-toggle="tooltip" data-bs-placement="top" title="' +
                escapeAttr(tip) +
                '" style="cursor: help; font-size: 0.9em; vertical-align: -0.1em;" aria-label="Формула расчёта"></i></span>'
            );
        }
        return label;
    }

    function buildNoteCell(row, cfg, noteRowspan) {
        var td = document.createElement("td");
        td.className = "summary-entity-note-cell align-middle text-start";
        td.rowSpan = noteRowspan > 0 ? noteRowspan : 1;
        td.setAttribute("data-original-note-rowspan", String(row.entity_rowspan || 1));
        var noteText = row.entity_note_text != null ? String(row.entity_note_text) : "";
        if (canEditNote(row, cfg)) {
            var ta = document.createElement("textarea");
            ta.rows = 4;
            ta.autocomplete = "off";
            ta.className =
                "form-control form-control-sm fuel-param-input power-demand-summary-note-field";
            ta.value = noteText;
            ta.setAttribute("data-initial", noteText);
            ta.setAttribute("data-slice", String(cfg.start_year || ""));
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
            td.appendChild(ta);
        } else {
            var span = document.createElement("span");
            span.className = "text-break";
            span.textContent = noteText;
            td.appendChild(span);
        }
        return td;
    }

    function buildYearCell(row, year, ix, cfg) {
        var td = document.createElement("td");
        var pk = row.parameter_key || "";
        var values = row.year_values || [];
        var rowIds = row.year_row_ids || [];
        var tooltips = row.year_numeric_tooltips || [];
        var value =
            ix < values.length && values[ix] != null ? String(values[ix]) : "—";
        var yrid = ix < rowIds.length ? rowIds[ix] : null;
        var yrTt = ix < tooltips.length ? tooltips[ix] || "" : "";
        var membershipOut = yearOutOfRange(row, year);
        var gaesOut = gaesStationYearOutOfRange(row, year);
        if (membershipOut) {
            value = "—";
        }
        if (pk === "energy_consumption_sipr_mln_kvt_ch" && yrTt) {
            yrTt = "Потребление электрической энергии, млн кВтч: " + yrTt;
        }
        td.className = "text-center summary-year-cell";
        if (membershipOut) {
            td.classList.add("summary-plan-empty", "pd-ec-variant-year-out");
        }
        var tableEl = document.getElementById("powerDemandSummaryTable");
        var useYearSeg =
            !!cfg.pd_ec_max_year_segments ||
            (tableEl && tableEl.getAttribute("data-ec-max-year-segments") === "1");
        if (useYearSeg) {
            td.setAttribute("data-ec-summary-col-year", String(year));
        }
        if (yrTt) {
            td.setAttribute("title", yrTt);
        }
        if (membershipOut) {
            return td;
        }
        if (row.pd_ec_verification_full_precision) {
            var redFlags = row.pd_ec_verification_year_red || [];
            var span = document.createElement("span");
            if (ix < redFlags.length && redFlags[ix]) {
                span.className = "text-danger";
            }
            span.textContent = value;
            td.appendChild(span);
            return td;
        }
        if (canEditCell(row, cfg) && !gaesOut && !membershipOut) {
            var yv = value !== "—" ? value : "";
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
            if (row.gaes_station_id) {
                inp.setAttribute("data-gaes-station-id", String(row.gaes_station_id));
            }
            td.appendChild(inp);
        } else {
            td.textContent = value;
        }
        return td;
    }

    function buildRowTr(row, cfg, years) {
        var tr = document.createElement("tr");
        tr.className = computeRowClasses(row, cfg);
        applyTrDataAttrs(tr, row);
        var entityRs = row.entity_rowspan || 1;
        if (row.show_entity_cell) {
            if (cfg.show_perimeter_variant_column) {
                tr.appendChild(buildPerimeterVariantCell(row, cfg, entityRs));
            }
            tr.appendChild(buildEntityCell(row, entityRs));
        }
        var paramTd = document.createElement("td");
        paramTd.className = "summary-parameter-cell";
        paramTd.innerHTML = buildParameterCellHtml(row, cfg);
        tr.appendChild(paramTd);
        years.forEach(function (year, ix) {
            tr.appendChild(buildYearCell(row, year, ix, cfg));
        });
        if (cfg.show_summary_note_col && row.show_entity_note_cell) {
            tr.appendChild(buildNoteCell(row, cfg, entityRs));
        }
        return tr;
    }

    function initTooltips(root) {
        if (!window.bootstrap || !bootstrap.Tooltip) {
            return;
        }
        root.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
            try {
                bootstrap.Tooltip.getOrCreateInstance(el);
            } catch (eTip) {
                /* */
            }
        });
    }

    function copyYearColHiddenFromThead(tbody) {
        var table = document.getElementById("powerDemandSummaryTable");
        if (!table || !tbody) {
            return;
        }
        var hiddenYears = {};
        table
            .querySelectorAll("thead th.summary-year-col.pd-ec-year-col-hidden")
            .forEach(function (th) {
                var y = th.getAttribute("data-ec-summary-col-year");
                if (y) {
                    hiddenYears[y] = true;
                }
            });
        tbody
            .querySelectorAll("td.summary-year-cell[data-ec-summary-col-year]")
            .forEach(function (td) {
                var y = td.getAttribute("data-ec-summary-col-year");
                td.classList.toggle("pd-ec-year-col-hidden", !!hiddenYears[y]);
            });
    }

    function finishClientBodyRender(tbody, payload) {
        copyYearColHiddenFromThead(tbody);
        renderEntityPagination(payload);
        document.dispatchEvent(new CustomEvent("pd-summary-rows-rendered"));
        document.dispatchEvent(new CustomEvent("ec-summary-rows-rendered"));
        function laterTooltips() {
            initTooltips(tbody);
        }
        if (window.requestIdleCallback) {
            window.requestIdleCallback(laterTooltips, { timeout: 1500 });
        } else {
            setTimeout(laterTooltips, 0);
        }
    }

    var currentEntityPagination = null;
    var PAGINATION_BEFORE_COMPACT_KEY =
        "pdEcSummaryPaginationBeforeCompact_" + (shellConfig.scope || "oes");

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
        if (window.__pdEcSummaryTerritoryCompactMode === true) {
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
            window.__pdEcSummaryTerritoryCompactMode === true &&
            paginationScopeEnabled()
        ) {
            syncEntityPaginationUrl(1, entityPaginationAllPageSize());
        }
        if (
            window.__pdEcSummaryTerritoryCompactMode === true ||
            !meta ||
            !meta.enabled ||
            (meta.total_pages || 1) <= 1
        ) {
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

    function scrollSummaryToTopAfterPagination() {
        var table =
            document.getElementById("powerDemandSummaryTable") ||
            document.querySelector("table.power-demand-summary-table");
        var scrollWrap = document.getElementById("powerDemandSummaryScrollWrap");
        if (window.armGsPageScrollRestore) {
            try {
                window.armGsPageScrollRestore.clear(
                    window.armGsPageScrollRestore.defaultScope(table)
                );
            } catch (eClr) {
                /* */
            }
            window.armGsPageScrollRestore.scrollTableTop({
                table: table || undefined,
                hScrollEl: scrollWrap || undefined,
            });
            return;
        }
        var pageWrap = document.querySelector(".page-table-scroll");
        if (pageWrap) {
            pageWrap.scrollTop = 0;
        } else if (scrollWrap) {
            scrollWrap.scrollTop = 0;
        }
    }

    var tableSpinnerDepth = 0;

    function tableSpinnerToggleButtons() {
        return [
            "pdEcSummaryTerritoryCompactToggle",
            "pdEcSummaryGaesDetailToggle",
            "pdEcSummaryNtDetailToggle",
            "pdEcSummaryHideEmptyToggle",
            "pdEcSummaryIsolatedEnergyUnitsToggle",
            "pdEcSummarySiprToggle",
            "pdEcSummaryVerificationToggle",
        ]
            .map(function (id) {
                return document.getElementById(id);
            })
            .filter(Boolean);
    }

    function ensureSegmentLoadingOverlay() {
        var overlay = document.getElementById(
            "powerDemandSummarySegmentLoadingOverlay"
        );
        if (overlay) {
            return overlay;
        }
        var shell = document.getElementById("powerDemandSummaryLoaderShell");
        overlay = document.createElement("div");
        overlay.id = "powerDemandSummarySegmentLoadingOverlay";
        overlay.className = "power-demand-summary-segment-loader-overlay";
        overlay.setAttribute("aria-live", "polite");
        overlay.setAttribute("aria-hidden", "true");
        overlay.hidden = true;
        overlay.style.cssText =
            "position:fixed;inset:0;z-index:1053;display:none;align-items:center;justify-content:center;background:rgba(255,255,255,0.78);cursor:wait;--loader-size:3.5rem;";
        overlay.innerHTML =
            '<div class="text-center">' +
            '<div class="loader loader-dual-ring" aria-hidden="true"></div>' +
            '<div class="mt-2 small text-muted">Загрузка данных…</div>' +
            '<span class="visually-hidden">Загрузка данных</span>' +
            "</div>";
        if (shell) {
            shell.insertBefore(overlay, shell.firstChild);
        } else {
            document.body.appendChild(overlay);
        }
        return overlay;
    }

    function showTableSpinner() {
        var shell = document.getElementById("powerDemandSummaryLoaderShell");
        if (!shell || shell.dataset.ready !== "1") {
            return;
        }
        tableSpinnerDepth += 1;
        if (tableSpinnerDepth > 1) {
            return;
        }
        var overlay = ensureSegmentLoadingOverlay();
        overlay.hidden = false;
        overlay.removeAttribute("hidden");
        overlay.style.display = "flex";
        overlay.setAttribute("aria-hidden", "false");
        shell.setAttribute("aria-busy", "true");
        tableSpinnerToggleButtons().forEach(function (btn) {
            btn.disabled = true;
            btn.setAttribute("aria-disabled", "true");
        });
    }

    function hideTableSpinner() {
        tableSpinnerDepth = Math.max(0, tableSpinnerDepth - 1);
        if (tableSpinnerDepth > 0) {
            return;
        }
        var overlay = document.getElementById(
            "powerDemandSummarySegmentLoadingOverlay"
        );
        if (overlay) {
            overlay.hidden = true;
            overlay.setAttribute("hidden", "hidden");
            overlay.style.display = "none";
            overlay.setAttribute("aria-hidden", "true");
        }
        var shell = document.getElementById("powerDemandSummaryLoaderShell");
        if (shell && shell.dataset.ready === "1") {
            shell.setAttribute("aria-busy", "false");
        }
        tableSpinnerToggleButtons().forEach(function (btn) {
            btn.disabled = false;
            btn.removeAttribute("aria-disabled");
        });
    }

    function showPaginationLoading() {
        showTableSpinner();
    }

    function hidePaginationLoading() {
        hideTableSpinner();
    }

    function savePaginationBeforeCompact() {
        try {
            sessionStorage.setItem(
                PAGINATION_BEFORE_COMPACT_KEY,
                JSON.stringify({
                    page: entityPaginationPageFromUrl(),
                    pageSize: entityPaginationPageSizeFromUrl(),
                })
            );
        } catch (eSave) {
            /* */
        }
    }

    function readPaginationBeforeCompact() {
        try {
            var raw = sessionStorage.getItem(PAGINATION_BEFORE_COMPACT_KEY);
            if (!raw) {
                return null;
            }
            var obj = JSON.parse(raw);
            if (!obj || obj.pageSize == null) {
                return null;
            }
            return obj;
        } catch (eRead) {
            return null;
        }
    }

    function loadEntityPaginationPage(page, pageSize) {
        scrollSummaryToTopAfterPagination();
        syncEntityPaginationUrl(page, pageSize);
        var tbody =
            document.getElementById("powerDemandSummaryTbody") ||
            document.querySelector("#powerDemandSummaryTable tbody");
        if (!tbody) {
            return Promise.reject(new Error("tbody не найден"));
        }
        showPaginationLoading();
        return fetchPayload()
            .then(function (payload) {
                return renderSummaryTableBody(payload).then(function () {
                    return payload;
                });
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
                hidePaginationLoading();
                scrollSummaryToTopAfterPagination();
            });
    }

    function renderSummaryTableBody(payload) {
        var tbody =
            document.getElementById("powerDemandSummaryTbody") ||
            document.querySelector("#powerDemandSummaryTable tbody");
        if (!tbody) {
            return Promise.reject(new Error("tbody не найден"));
        }
        var cfg = Object.assign({}, payload.config || {});
        if (shellConfig.can_edit_summary_cells != null) {
            cfg.can_edit_summary_cells = !!shellConfig.can_edit_summary_cells;
        }
        cfg._visibleKeys = readStoredVisibleKeys();
        var years = payload.years || [];
        var rows = payload.summary_rows || [];
        if (!rows.length) {
            var emptyTr = document.createElement("tr");
            var emptyTd = document.createElement("td");
            emptyTd.colSpan = 10;
            emptyTd.className = "text-center text-muted";
            emptyTd.textContent = "Нет данных для текущей версии БД.";
            emptyTr.appendChild(emptyTd);
            tbody.replaceChildren(emptyTr);
            finishClientBodyRender(tbody, payload);
            return Promise.resolve();
        }
        rows = prepareRowsForClientRender(rows, cfg);

        function appendRows(from, to, target) {
            for (var i = from; i < to; i++) {
                target.appendChild(buildRowTr(rows[i], cfg, years));
            }
        }

        if (rows.length <= RENDER_ROWS_CHUNK_SIZE) {
            var frag = document.createDocumentFragment();
            appendRows(0, rows.length, frag);
            tbody.replaceChildren(frag);
            finishClientBodyRender(tbody, payload);
            return Promise.resolve();
        }

        var offscreenFrag = document.createDocumentFragment();
        var rowIndex = 0;
        return new Promise(function (resolve) {
            function renderChunk() {
                var end = Math.min(rowIndex + RENDER_ROWS_CHUNK_SIZE, rows.length);
                appendRows(rowIndex, end, offscreenFrag);
                rowIndex = end;
                if (rowIndex < rows.length) {
                    window.requestAnimationFrame(renderChunk);
                    return;
                }
                tbody.replaceChildren(offscreenFrag);
                finishClientBodyRender(tbody, payload);
                resolve();
            }
            window.requestAnimationFrame(renderChunk);
        });
    }

    function currentDetailFlagsKey() {
        return [
            window.__pdEcSummarySiprMode ? "1" : "0",
            window.__pdEcSummaryGaesDetailMode ? "1" : "0",
            window.__pdEcSummaryNtDetailMode ? "1" : "0",
            window.__pdEcSummaryVerificationMode ? "1" : "0",
            window.__pdEcSummaryIsolatedEnergyUnitsMode ? "1" : "0",
            window.__pdEcSummaryTerritoryCompactMode ? "1" : "0",
        ].join("");
    }

    var lastFetchedDetailFlags = null;

    function applyDetailFlagsToParams(params) {
        function setFlag(name, on) {
            if (on) {
                params.set(name, "1");
            } else {
                params.delete(name);
            }
        }
        setFlag("pd_ec_sipr", window.__pdEcSummarySiprMode === true);
        setFlag("pd_ec_gaes", window.__pdEcSummaryGaesDetailMode === true);
        setFlag("pd_ec_nt", window.__pdEcSummaryNtDetailMode === true);
        setFlag("pd_ec_verify", window.__pdEcSummaryVerificationMode === true);
        setFlag("pd_ec_o1", window.__pdEcSummaryIsolatedEnergyUnitsMode === true);
        setFlag("pd_ec_compact", window.__pdEcSummaryTerritoryCompactMode === true);
    }

    function dataUrl() {
        var path = shellConfig.data_path;
        var params = new URLSearchParams(window.location.search || "");
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
        applyDetailFlagsToParams(params);
        var qs = params.toString();
        return qs ? path + "?" + qs : path;
    }

    function fetchPayload() {
        lastFetchedDetailFlags = currentDetailFlagsKey();
        return fetch(dataUrl(), {
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        }).then(function (resp) {
            if (!resp.ok) {
                throw new Error("HTTP " + resp.status);
            }
            return resp.json();
        });
    }

    function wrapReapplyForDetailReload() {
        var orig = window.__pdEcSummaryReapplyRowVisibility;
        if (typeof orig !== "function" || orig.__pdEcDetailWrapped) {
            return;
        }
        function wrapped() {
            if (
                paginationScopeEnabled() &&
                lastFetchedDetailFlags !== currentDetailFlagsKey()
            ) {
                var pageSize = effectiveEntityPaginationPageSize();
                loadEntityPaginationPage(
                    effectiveEntityPaginationPage(pageSize),
                    pageSize
                );
                return;
            }
            orig.apply(this, arguments);
        }
        wrapped.__pdEcDetailWrapped = true;
        window.__pdEcSummaryReapplyRowVisibility = wrapped;
    }

    var ready = fetchPayload()
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

    window.__ecSummaryRowsReady = ready;
    window.__pdSummaryRowsReady = ready;
    window.__pdSummaryLoadEntityPaginationPage = loadEntityPaginationPage;
    window.__pdSummaryEntityPaginationUrlIsPaginated = entityPaginationUrlIsPaginated;
    window.__pdEcSummaryShowTableSpinner = showTableSpinner;
    window.__pdEcSummaryHideTableSpinner = hideTableSpinner;
    window.__pdSummaryOnTerritoryCompactToggle = function () {
        if (!paginationScopeEnabled()) {
            if (typeof window.__pdEcSummaryReapplyRowVisibility === "function") {
                window.__pdEcSummaryReapplyRowVisibility();
            }
            return;
        }
        if (window.__pdEcSummaryTerritoryCompactMode === true) {
            savePaginationBeforeCompact();
            loadEntityPaginationPage(1, entityPaginationAllPageSize());
            return;
        }
        var saved = readPaginationBeforeCompact();
        var pagCfg = shellConfig.entity_pagination || {};
        var defSize =
            pagCfg.default_page_size != null ? pagCfg.default_page_size : 2;
        loadEntityPaginationPage(
            saved && saved.pageSize > 0 ? saved.page || 1 : 1,
            saved && saved.pageSize > 0 ? saved.pageSize : defSize
        );
    };

    wrapReapplyForDetailReload();
    setTimeout(wrapReapplyForDetailReload, 0);
    ready.then(wrapReapplyForDetailReload, wrapReapplyForDetailReload);
})();
