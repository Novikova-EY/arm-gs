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

    if (typeof window.initPowerDemandSummaryRowPaste === "function") {
        window.initPowerDemandSummaryRowPaste(table);
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
        if (!s || s === "—" || s === "-" || s === "–") {
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
            return "—";
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
            if (text && text !== "—") {
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

    var saveBtn = document.getElementById("ozpMaximaSaveBtn");
    var saveUrl = table.dataset.saveUrl;
    if (!saveBtn || !saveUrl) {
        return;
    }

    function runOzpMaximaSave() {
        if (saveBtn.disabled) {
            return;
        }
        var cells = [];
        table.querySelectorAll("input.fuel-param-input[data-parameter-key=\"max_power\"][data-slice]").forEach(
            function (inp) {
                cells.push({
                    ozp_end_year: inp.getAttribute("data-slice"),
                    parameter_key: inp.getAttribute("data-parameter-key"),
                    value: inp.value,
                });
            }
        );
        var headers = {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "X-CSRFToken": window.__ozpMaximaCsrfToken || "",
        };
        saveBtn.disabled = true;
        fetch(saveUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: headers,
            body: JSON.stringify({ cells: cells }),
        })
            .then(function (resp) {
                return resp.json().then(function (data) {
                    return { ok: resp.ok && data && data.ok, data: data };
                });
            })
            .then(function (payload) {
                if (!payload.ok) {
                    window.alert((payload.data && payload.data.error) || "Не удалось сохранить.");
                    return;
                }
                saveBtn.classList.remove("btn-primary");
                saveBtn.classList.add("btn-success");
                saveBtn.textContent = "Сохранено";
                setTimeout(function () {
                    saveBtn.classList.add("btn-primary");
                    saveBtn.classList.remove("btn-success");
                    saveBtn.textContent = "Сохранить";
                }, 1200);
            })
            .catch(function () {
                window.alert("Не удалось сохранить.");
            })
            .finally(function () {
                saveBtn.disabled = false;
            });
    }

    saveBtn.addEventListener("click", runOzpMaximaSave);

    table.addEventListener("keydown", function (e) {
        if (e.key !== "Enter" || e.repeat) {
            return;
        }
        if (!e.target || !e.target.matches("input.fuel-param-input")) {
            return;
        }
        e.preventDefault();
        runOzpMaximaSave();
    });
})();
