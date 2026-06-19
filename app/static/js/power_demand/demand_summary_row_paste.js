/**
 * Построчная вставка из Excel (tab-separated) в сводках «Нагрузки»:
 * копируете строку значений → фокус в первую ячейку строки → Ctrl+V.
 */
(function () {
    "use strict";

    function normalizePastedCellValue(val) {
        var s = String(val == null ? "" : val)
            .replace(/\u00a0/g, " ")
            .replace(/\u202f/g, " ");
        // В Excel «ДД.ММ.ГГГГ» и «ЧЧ:ММ» часто в одной ячейке через перенос строки.
        s = s.replace(/\s*\r?\n\s*/g, " ");
        return s.replace(/\s+/g, " ").trim();
    }

    function parseClipboardRow(text) {
        var raw = String(text || "");
        if (!raw) {
            return [];
        }
        if (raw.indexOf("\t") === -1) {
            return [normalizePastedCellValue(raw)];
        }

        // Строка Excel: столбцы через таб; переносы внутри ячейки (дата/время) не режем.
        var rowText = raw;
        var crnl = raw.indexOf("\r\n");
        if (crnl !== -1) {
            rowText = raw.slice(0, crnl);
        }
        rowText = rowText.replace(/\r/g, "");
        return rowText.split("\t").map(normalizePastedCellValue);
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
        if (/\d{1,2}:\d{2}/.test(s)) {
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
            s.indexOf("мск") >= 0
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
            if (!looksLikeDataCell(v0) && looksLikeDataCell(v1)) {
                trimmed = trimmed.slice(1);
                continue;
            }
            break;
        }
        return trimmed;
    }

    function isPasteableInput(inp) {
        if (!inp || inp.readOnly) {
            return false;
        }
        if (!inp.matches("input.fuel-param-input[data-model][data-slice], textarea.fuel-param-input[data-model][data-slice]")) {
            return false;
        }
        if (inp.classList.contains("power-demand-summary-note-field")) {
            return false;
        }
        var td = inp.closest("td");
        if (td && td.classList.contains("summary-plan-empty")) {
            return false;
        }
        return true;
    }

    function getRowPasteTargets(tr) {
        if (!tr) {
            return [];
        }
        var targets = [];
        var histTd = tr.querySelector("td.summary-hist-cell");
        if (histTd) {
            var histInp = histTd.querySelector("input.fuel-param-input, textarea.fuel-param-input");
            if (isPasteableInput(histInp)) {
                targets.push(histInp);
            }
        }
        tr.querySelectorAll("td.summary-year-cell, td.summary-year-mw-cell").forEach(function (td) {
            if (td.classList.contains("summary-plan-empty")) {
                return;
            }
            var inp = td.querySelector("input.fuel-param-input, textarea.fuel-param-input");
            if (isPasteableInput(inp)) {
                targets.push(inp);
            }
        });
        return targets;
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

    function initPowerDemandSummaryRowPaste(table, options) {
        if (!table || table.__pdSummaryRowPasteBound) {
            return;
        }
        options = options || {};
        var formatPeakDatetime = options.formatPeakDatetime;

        table.addEventListener("paste", function (e) {
            var target = e.target;
            if (!isPasteableInput(target)) {
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

            if (text.indexOf("\t") === -1) {
                if (target.dataset.parameterKey === "peak_datetime" && typeof formatPeakDatetime === "function") {
                    setTimeout(function () {
                        formatPeakDatetime(target);
                    }, 0);
                }
                return;
            }

            e.preventDefault();

            var values = parseClipboardRow(text);
            if (!values.length) {
                return;
            }

            var tr = target.closest("tr");
            var targets = getRowPasteTargets(tr);
            if (!targets.length) {
                return;
            }

            var startIdx = targets.indexOf(target);
            if (startIdx < 0) {
                startIdx = 0;
            }
            values = maybeTrimExcelLeadingColumns(values, startIdx);

            applyPastedValues(targets, startIdx, values, formatPeakDatetime);
        });

        table.__pdSummaryRowPasteBound = true;
    }

    window.initPowerDemandSummaryRowPaste = initPowerDemandSummaryRowPaste;
})();
