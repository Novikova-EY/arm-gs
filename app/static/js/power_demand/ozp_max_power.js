/**
 * Таблица «Максимумы потребления мощности ОЗП»:
 * сохранение, экспорт, округление, построчная вставка.
 */
(function () {
    "use strict";

    function parseFilenameFromContentDisposition(cd) {
        if (!cd) {
            return "export.xlsx";
        }
        var mUtf = /filename\*=UTF-8''([^;\n]+)/i.exec(cd);
        if (mUtf && mUtf[1]) {
            try {
                return decodeURIComponent(mUtf[1].trim());
            } catch (e1) {
                return mUtf[1].trim();
            }
        }
        var mQuot = /filename="([^"]+)"/i.exec(cd);
        if (mQuot && mQuot[1]) {
            return mQuot[1].trim();
        }
        var mBare = /filename=([^;\n]+)/i.exec(cd);
        if (mBare && mBare[1]) {
            return mBare[1].trim().replace(/^["']|["']$/g, "");
        }
        return "export.xlsx";
    }

    document.getElementById("rounding_digits")?.addEventListener("change", function () {
        var url = new URL(window.location.href);
        url.searchParams.set("rounding_digits", this.value);
        window.location.href = url.toString();
    });

    (function initExport() {
        var form = document.getElementById("ozpMaximaExportForm");
        var exportBtn = document.getElementById("ozpMaximaExportBtn");
        if (!form || !exportBtn) {
            return;
        }
        exportBtn.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (exportBtn.disabled) {
                return;
            }
            var params = new URLSearchParams(window.location.search);
            var rdSel = document.getElementById("rounding_digits");
            if (rdSel) {
                params.set("rounding_digits", rdSel.value);
            }
            var url = form.getAttribute("action") + (params.toString() ? "?" + params.toString() : "");
            var originalHtml = exportBtn.innerHTML;
            exportBtn.disabled = true;
            exportBtn.innerHTML =
                '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Экспорт…';
            fetch(url, {
                method: "GET",
                credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" },
            })
                .then(function (resp) {
                    if (!resp.ok) {
                        throw new Error("export failed");
                    }
                    var filename = parseFilenameFromContentDisposition(
                        resp.headers.get("Content-Disposition")
                    );
                    return resp.blob().then(function (blob) {
                        return { blob: blob, filename: filename };
                    });
                })
                .then(function (payload) {
                    var objectUrl = URL.createObjectURL(payload.blob);
                    var a = document.createElement("a");
                    a.href = objectUrl;
                    a.download = payload.filename || "export.xlsx";
                    document.body.appendChild(a);
                    a.click();
                    a.remove();
                    URL.revokeObjectURL(objectUrl);
                })
                .catch(function () {
                    window.alert("Не удалось выгрузить файл.");
                })
                .finally(function () {
                    exportBtn.disabled = false;
                    exportBtn.innerHTML = originalHtml;
                });
        });
    })();

    var table = document.getElementById("ozpMaximaTable");
    if (!table) {
        return;
    }

    function formatOzpPeakDatetimeInput(inp) {
        if (!inp || inp.dataset.parameterKey !== "peak_datetime") {
            return;
        }
        var raw = String(inp.value || "").trim();
        if (!raw) {
            return;
        }
        var m = /(\d{1,2})\.(\d{1,2})(?:\.(\d{2,4}))?\s+(\d{1,2})[:\-.](\d{2})/.exec(raw);
        if (!m) {
            return;
        }
        var dd = String(parseInt(m[1], 10)).padStart(2, "0");
        var mm = String(parseInt(m[2], 10)).padStart(2, "0");
        var datePart = dd + "." + mm;
        if (m[3]) {
            var y = parseInt(m[3], 10);
            if (m[3].length === 2) {
                y = y <= 68 ? 2000 + y : 1900 + y;
            }
            datePart += "." + String(y).padStart(4, "0");
        }
        var hh = String(parseInt(m[4], 10)).padStart(2, "0");
        inp.value = datePart + " " + hh + ":" + m[5];
    }

    if (typeof window.initPowerDemandSummaryRowPaste === "function") {
        window.initPowerDemandSummaryRowPaste(table, {
            formatPeakDatetime: formatOzpPeakDatetimeInput,
        });
    }

    if (typeof bootstrap !== "undefined" && bootstrap.Tooltip) {
        table.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function (el) {
            new bootstrap.Tooltip(el);
        });
    }

    function parseDisplayNumber(raw) {
        if (raw == null) {
            return null;
        }
        var s = String(raw)
            .trim()
            .replace(/\u2212/g, "-")
            .replace(/[\u00a0\u202f ]/g, "")
            .replace(",", ".");
        if (!s || s === "–" || s === "-" || s === "–") {
            return null;
        }
        var n = parseFloat(s);
        return Number.isFinite(n) ? n : null;
    }

    function applyThousandGrouping(s) {
        if (!s) {
            return s;
        }
        var sign = "";
        if (s.charAt(0) === "-") {
            sign = "-";
            s = s.slice(1);
        }
        return sign + s.replace(/\B(?=(\d{3})+(?!\d))/g, " ");
    }

    function formatGrowthPct(num, digits) {
        if (!Number.isFinite(num)) {
            return "–";
        }
        var d = Number.isFinite(digits) ? digits : 2;
        var sign = num < 0 ? -1 : 1;
        var mult = Math.pow(10, d);
        var rounded = (sign * Math.round(Math.abs(num) * mult)) / mult;
        return applyThousandGrouping(rounded.toFixed(d).replace(".", ","));
    }

    function recalcOzpGrowth() {
        var mwInputs = table.querySelectorAll(
            'tr[data-parameter-key="max_power"] input.fuel-param-input[data-parameter-key="max_power"][data-slice]'
        );
        var growthCells = table.querySelectorAll("span.ozp-growth-value");
        if (!mwInputs.length || !growthCells.length) {
            return;
        }
        var digits = parseInt(table.getAttribute("data-growth-digits") || "2", 10);
        var prev = parseDisplayNumber(table.getAttribute("data-prev-max"));
        for (var i = 0; i < growthCells.length; i++) {
            var current = null;
            if (i < mwInputs.length) {
                current = parseDisplayNumber(mwInputs[i].value);
            }
            var growth = null;
            if (current != null && prev != null && prev !== 0) {
                growth = (current / prev) * 100 - 100;
            }
            var text = formatGrowthPct(growth, digits);
            growthCells[i].textContent = text;
            if (text && text !== "–") {
                growthCells[i].setAttribute("title", text);
            } else {
                growthCells[i].removeAttribute("title");
            }
            prev = current;
        }
    }

    table.addEventListener("input", function (e) {
        if (e.target && e.target.matches('input.fuel-param-input[data-parameter-key="max_power"]')) {
            recalcOzpGrowth();
        }
    });
    table.addEventListener("change", function (e) {
        if (e.target && e.target.matches('input.fuel-param-input[data-parameter-key="max_power"]')) {
            recalcOzpGrowth();
        }
    });
    table.addEventListener("blur", function (e) {
        if (e.target && e.target.matches('.fuel-param-input[data-parameter-key="peak_datetime"]')) {
            formatOzpPeakDatetimeInput(e.target);
        }
    }, true);

    var saveBtn = document.getElementById("ozpMaximaSaveBtn");
    var saveUrl = table.dataset.saveUrl;
    if (!saveBtn || !saveUrl) {
        return;
    }

    const selector = ".fuel-param-input[data-parameter-key][data-slice]";
    table.querySelectorAll(selector).forEach(function (field) {
        field.dataset.initial = field.value;
    });
    const live = window.bindConsumptionLiveSave(table, selector, async function (field) {
        formatOzpPeakDatetimeInput(field);
        const value = field.value;
        if (value === field.dataset.initial) return;
        const response = await window.powerDemandSaveFetch(saveUrl, {
            method: "POST", credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "X-CSRFToken": window.__ozpMaximaCsrfToken || ""
            },
            body: JSON.stringify({cells: [{
                ozp_end_year: field.dataset.slice,
                parameter_key: field.dataset.parameterKey,
                value: value
            }]})
        });
        const data = await response.json().catch(function () { return null; });
        if (!response.ok || !data || !data.ok) {
            throw new Error(data && data.error || "Не удалось сохранить данные.");
        }
        field.dataset.initial = value;
    });

    saveBtn.addEventListener("click", async function () {
        table.querySelectorAll(selector).forEach(function (field) {
            if (field.value !== field.dataset.initial) live.enqueue(field);
        });
        saveBtn.disabled = true;
        try {
            await live.whenIdle();
        } finally {
            saveBtn.disabled = false;
        }
    });
})();
