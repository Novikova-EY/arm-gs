/**
 * Построчная вставка из Excel (значения через Tab) в любую таблицу с ячейками ввода:
 * фокус в ячейке → Ctrl+V. Несколько строк буфера идут в следующие редактируемые строки.
 * Страницы со особыми ячейками (отложенные инпуты, дата/время) регистрируют адаптер
 * через initPowerDemandSummaryRowPaste(table, options).
 */
(function () {
    "use strict";

    if (window.__armGsTableRowPasteInstalled) {
        return;
    }
    window.__armGsTableRowPasteInstalled = true;

    var adapters = typeof WeakMap === "function" ? new WeakMap() : null;

    var VALUE_FAMILIES = [
        "pd-coeff-medium-k-input",
        "pd-coeff-manual-input",
        "lt-ei-coef-input",
        "forecast-paste-input",
        "ves-ses-value",
        "pb-custom-value",
        "ot-edit-value",
        "ee-control-value",
        "fuel-calc-chchium-input",
        "fuel-detail-sync-input",
        "fuel-param-input"
    ];

    var SKIP_INPUT_CLASSES = [
        "power-demand-summary-note-field",
        "ec-formula-text-input",
        "pb-custom-label",
        "ec-col-filter",
        "pd-coeff-display-mw"
    ];

    function getAdapter(table) {
        if (!table || !adapters) {
            return {};
        }
        return adapters.get(table) || {};
    }

    function normalizePastedCellValue(val) {
        var s = String(val == null ? "" : val)
            .replace(/\u00a0/g, " ")
            .replace(/\u202f/g, " ");
        s = s.replace(/\s*\r?\n\s*/g, " ");
        s = s.replace(/\s+/g, " ").trim();
        while (s.length >= 2 && s.charAt(0) === s.charAt(s.length - 1) && "\"'«»“”".indexOf(s.charAt(0)) >= 0) {
            s = s.slice(1, -1).trim();
        }
        return s.replace(/^["'«»“”]+/, "").replace(/["'«»“”]+$/, "").trim();
    }

    function looksLikeTimeOnly(s) {
        return /^\d{1,2}[:\-]\d{2}(?::\d{2})?$/.test(String(s || "").trim());
    }

    function looksLikeDatePrefix(s) {
        return /\d{1,2}\.\d{1,2}/.test(String(s || ""));
    }

    function parseClipboardGrid(text) {
        var raw = String(text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n");
        if (!raw) {
            return [];
        }
        if (raw.indexOf("\t") === -1) {
            var one = normalizePastedCellValue(raw);
            return one ? [[one]] : [];
        }

        var parts = raw.split("\t");
        var rows = [[]];
        for (var p = 0; p < parts.length; p++) {
            var sub = String(parts[p] == null ? "" : parts[p]).split("\n");
            var current = rows[rows.length - 1];
            current.push(normalizePastedCellValue(sub[0]));
            for (var s = 1; s < sub.length; s++) {
                var extra = sub[s];
                if (!String(extra || "").trim()) {
                    continue;
                }
                var lastCell = current.length ? current[current.length - 1] : "";
                if (looksLikeTimeOnly(extra) && looksLikeDatePrefix(lastCell)) {
                    current[current.length - 1] = normalizePastedCellValue(lastCell + " " + extra);
                    continue;
                }
                current = [];
                rows.push(current);
                current.push(normalizePastedCellValue(extra));
            }
        }
        return rows.filter(function (row) {
            return row.some(function (cell) {
                return String(cell || "").trim() !== "";
            });
        });
    }

    function looksLikeDataCell(s) {
        s = String(s || "").trim();
        if (!s) {
            return true;
        }
        if (/^-?\d+([.,]\d+)?$/.test(s.replace(/\s/g, ""))) {
            return true;
        }
        if (/^\d{4}$/.test(s)) {
            return true;
        }
        if (/\d{1,2}\.\d{1,2}\.\d{2,4}/.test(s)) {
            return true;
        }
        if (/^\d{1,2}\.\d{1,2}(\s+\d{1,2}[:\-]\d{2})?$/.test(s)) {
            return true;
        }
        if (/\d{1,2}[:\-]\d{2}/.test(s)) {
            return true;
        }
        return false;
    }

    function looksLikeParamLabel(s) {
        s = String(s || "").toLowerCase();
        return (
            s.indexOf("максимум") >= 0 ||
            s.indexOf("дата") >= 0 ||
            s.indexOf("тнв") >= 0 ||
            s.indexOf("совмещ") >= 0 ||
            s.indexOf("мвт") >= 0 ||
            s.indexOf("мск") >= 0 ||
            s.indexOf("потреблен") >= 0 ||
            s.indexOf("прирост") >= 0 ||
            s.indexOf("озп") >= 0 ||
            s.indexOf("сипр") >= 0 ||
            s.indexOf("млн") >= 0 ||
            s.indexOf("квт") >= 0 ||
            s.indexOf("гаэс") >= 0 ||
            s.indexOf("заряд") >= 0
        );
    }

    function maybeTrimExcelLeadingColumns(values, startIdx) {
        if (startIdx !== 0 || values.length < 2) {
            return values;
        }
        var trimmed = values.slice();
        while (trimmed.length >= 2) {
            var v0 = trimmed[0];
            var v1 = trimmed[1];
            if (!looksLikeDataCell(v0) && looksLikeParamLabel(v1)) {
                trimmed = trimmed.slice(2);
                continue;
            }
            if (
                !looksLikeDataCell(v0) &&
                !looksLikeDataCell(v1) &&
                trimmed.length >= 3 &&
                looksLikeDataCell(trimmed[2])
            ) {
                trimmed = trimmed.slice(2);
                continue;
            }
            if (!looksLikeDataCell(v0) && looksLikeDataCell(v1)) {
                trimmed = trimmed.slice(1);
                continue;
            }
            break;
        }
        return trimmed;
    }

    function familyClassOf(el) {
        if (!el || !el.classList) {
            return "";
        }
        for (var i = 0; i < VALUE_FAMILIES.length; i++) {
            if (el.classList.contains(VALUE_FAMILIES[i])) {
                return VALUE_FAMILIES[i];
            }
        }
        return "";
    }

    function hasSkipClass(inp) {
        for (var i = 0; i < SKIP_INPUT_CLASSES.length; i++) {
            if (inp.classList.contains(SKIP_INPUT_CLASSES[i])) {
                return true;
            }
        }
        return false;
    }

    function defaultIsPasteableInput(inp) {
        if (!inp || inp.readOnly || inp.disabled) {
            return false;
        }
        if (inp.closest("thead, tfoot")) {
            return false;
        }
        var type = String(inp.type || "text").toLowerCase();
        if (
            type === "hidden" ||
            type === "checkbox" ||
            type === "radio" ||
            type === "file" ||
            type === "password" ||
            type === "search" ||
            type === "button" ||
            type === "submit" ||
            type === "reset" ||
            type === "color" ||
            type === "range"
        ) {
            return false;
        }
        if (!inp.matches("input, textarea")) {
            return false;
        }
        if (hasSkipClass(inp)) {
            return false;
        }
        if (inp.closest(".summary-entity-note-cell, .ot-note-cell, .ot-source-cell")) {
            return false;
        }
        var td = inp.closest("td");
        if (td && (td.classList.contains("summary-plan-empty") || td.classList.contains("summary-hist-cell-disabled"))) {
            return false;
        }
        return true;
    }

    function sameFamily(sample, inp) {
        var a = familyClassOf(sample);
        var b = familyClassOf(inp);
        if (a) {
            return a === b;
        }
        return !b;
    }

    function defaultGetRowPasteTargets(tr, sampleInput) {
        if (!tr) {
            return [];
        }
        var sample = sampleInput || null;
        var nodes = tr.querySelectorAll("input, textarea");
        var targets = [];
        for (var i = 0; i < nodes.length; i++) {
            var inp = nodes[i];
            if (inp.closest("tr") !== tr) {
                continue;
            }
            if (!defaultIsPasteableInput(inp)) {
                continue;
            }
            if (sample && !sameFamily(sample, inp)) {
                continue;
            }
            targets.push(inp);
        }
        return targets;
    }

    function collectFollowingPasteRows(startTr, count, getTargets) {
        var rows = [];
        var tr = startTr;
        while (tr && rows.length < count) {
            if (getTargets(tr).length) {
                rows.push(tr);
            }
            tr = tr.nextElementSibling;
        }
        return rows;
    }

    function applyPastedValues(targets, startIdx, values, formatPeakDatetime) {
        for (var i = 0; i < values.length; i++) {
            var ti = startIdx + i;
            if (ti >= targets.length) {
                break;
            }
            var inp = targets[ti];
            inp.value = values[i];
            if (typeof formatPeakDatetime === "function" && inp.dataset.parameterKey === "peak_datetime") {
                formatPeakDatetime(inp);
            }
            inp.dispatchEvent(new Event("input", { bubbles: true }));
            inp.dispatchEvent(new Event("change", { bubbles: true }));
        }
    }

    function resolveRowTargetsFn(options, sampleInput) {
        if (options.getRowPasteTargets) {
            return function (tr) {
                return options.getRowPasteTargets(tr);
            };
        }
        return function (tr) {
            return defaultGetRowPasteTargets(tr, sampleInput);
        };
    }

    function initPowerDemandSummaryRowPaste(table, options) {
        if (!table || !adapters) {
            return;
        }
        adapters.set(table, options || {});
    }

    function initProspectivePlaceForecastRowPaste(table) {
        initPowerDemandSummaryRowPaste(table);
    }

    document.addEventListener("paste", function (e) {
        if (e.defaultPrevented) {
            return;
        }
        var target = e.target;
        if (!target || !target.closest) {
            return;
        }
        var table = target.closest("table");
        if (!table) {
            return;
        }
        var options = getAdapter(table);
        var matchInput = options.isPasteableInput || defaultIsPasteableInput;
        if (!matchInput(target)) {
            return;
        }
        var clipboardData = e.clipboardData || window.clipboardData;
        if (!clipboardData) {
            return;
        }
        var text = clipboardData.getData("text/plain");
        if (!text) {
            return;
        }

        var formatPeakDatetime = options.formatPeakDatetime;
        if (text.indexOf("\t") === -1) {
            if (target.dataset && target.dataset.parameterKey === "peak_datetime" && typeof formatPeakDatetime === "function") {
                setTimeout(function () {
                    formatPeakDatetime(target);
                }, 0);
            }
            return;
        }

        var grid = parseClipboardGrid(text);
        if (!grid.length) {
            return;
        }

        e.preventDefault();

        var rowTargets = resolveRowTargetsFn(options, target);
        var startTr = target.closest("tr");
        var rowTrs = collectFollowingPasteRows(startTr, grid.length, rowTargets);
        if (!rowTrs.length) {
            return;
        }

        var startIdx = rowTargets(rowTrs[0]).indexOf(target);
        if (startIdx < 0) {
            startIdx = 0;
        }

        window.__armGsTableRowPasteActive = true;
        try {
            for (var r = 0; r < rowTrs.length; r++) {
                var values = maybeTrimExcelLeadingColumns(grid[r] || [], startIdx);
                applyPastedValues(
                    rowTargets(rowTrs[r]),
                    startIdx,
                    values,
                    formatPeakDatetime
                );
            }
        } finally {
            window.__armGsTableRowPasteActive = false;
        }
    });

    window.initPowerDemandSummaryRowPaste = initPowerDemandSummaryRowPaste;
    window.initProspectivePlaceForecastRowPaste = initProspectivePlaceForecastRowPaste;
})();
