/**
 * Построчная вставка из Excel (значения через Tab) в таблицы прогноза/выработки
 * перспективных площадок и карточки электростанции: фокус в ячейке строки → Ctrl+V.
 */
(function () {
    "use strict";

    function normalizePastedCellValue(val) {
        var s = String(val == null ? "" : val)
            .replace(/\u00a0/g, " ")
            .replace(/\u202f/g, " ");
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
        var rowText = raw;
        var crnl = raw.indexOf("\r\n");
        if (crnl !== -1) {
            rowText = raw.slice(0, crnl);
        }
        rowText = rowText.replace(/\r/g, "");
        // Берём только первую строку буфера (одна строка таблицы).
        var nl = rowText.indexOf("\n");
        if (nl !== -1) {
            rowText = rowText.slice(0, nl);
        }
        return rowText.split("\t").map(normalizePastedCellValue);
    }

    function looksLikeNumber(s) {
        s = String(s || "").trim().replace(/\s+/g, "").replace(",", ".");
        if (!s) {
            return true;
        }
        return /^-?\d+(\.\d+)?$/.test(s);
    }

    function maybeTrimLeadingLabel(values, startIdx) {
        if (startIdx !== 0 || values.length < 2) {
            return values;
        }
        var trimmed = values.slice();
        // Excel часто копирует подпись строки («Выработка…») первым столбцом.
        while (
            trimmed.length >= 2 &&
            !looksLikeNumber(trimmed[0]) &&
            looksLikeNumber(trimmed[1])
        ) {
            trimmed = trimmed.slice(1);
        }
        return trimmed;
    }

    function isPasteableInput(inp) {
        if (!inp || inp.readOnly || inp.disabled) {
            return false;
        }
        if (inp.type === "hidden") {
            return false;
        }
        return inp.matches("input.forecast-paste-input");
    }

    function getRowPasteTargets(tr) {
        if (!tr) {
            return [];
        }
        return Array.prototype.slice
            .call(tr.querySelectorAll("input.forecast-paste-input"))
            .filter(isPasteableInput);
    }

    function applyPastedValues(targets, startIdx, values) {
        for (var i = 0; i < values.length; i++) {
            var ti = startIdx + i;
            if (ti >= targets.length) {
                break;
            }
            var inp = targets[ti];
            inp.value = values[i];
            inp.dispatchEvent(new Event("input", { bubbles: true }));
            inp.dispatchEvent(new Event("change", { bubbles: true }));
        }
    }

    function initProspectivePlaceForecastRowPaste(table) {
        if (!table || table.__ppForecastRowPasteBound) {
            return;
        }

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
            if (!text || text.indexOf("\t") === -1) {
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
            values = maybeTrimLeadingLabel(values, startIdx);
            applyPastedValues(targets, startIdx, values);
        });

        table.__ppForecastRowPasteBound = true;
    }

    window.initProspectivePlaceForecastRowPaste = initProspectivePlaceForecastRowPaste;
})();
