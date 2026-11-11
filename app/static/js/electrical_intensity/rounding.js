(function () {
    "use strict";

    const table = document.getElementById("powerDemandSummaryTable");
    const numberSelect = document.getElementById("rounding_digits");
    const coefficientSelect = document.getElementById("coefficient_rounding_digits");
    if (!table || (!numberSelect && !coefficientSelect)) return;

    const formulaRowKinds = new Set(["intensity", "calculated", "delta"]);

    function parseDecimal(raw) {
        const value = String(raw == null ? "" : raw)
            .replace(/[\s\u00a0\u202f]/g, "")
            .replace(/[\u2212]/g, "-")
            .replace(/,/g, ".");
        const match = value.match(/^([+-]?)(\d+)(?:\.(\d*))?$/);
        if (!match) return null;
        return {
            negative: match[1] === "-",
            whole: match[2].replace(/^0+(?=\d)/, ""),
            fraction: match[3] || ""
        };
    }

    function formatDecimal(raw, digits) {
        const parts = parseDecimal(raw);
        if (!parts) return null;

        let whole = parts.whole;
        let fraction = parts.fraction;
        if (digits === -1) {
            if (fraction.charAt(0) >= "5" && fraction.length) {
                whole = (BigInt(whole) + 1n).toString();
            }
            fraction = "";
        } else if (digits > 0 && fraction.length > digits) {
            const scale = 10n ** BigInt(digits);
            let scaled = BigInt(whole) * scale
                + BigInt(fraction.slice(0, digits).padEnd(digits, "0") || "0");
            if (fraction.charAt(digits) >= "5") scaled += 1n;
            whole = (scaled / scale).toString();
            fraction = (scaled % scale).toString().padStart(digits, "0");
        }

        fraction = fraction.replace(/0+$/, "");
        const isZero = /^0+$/.test(whole) && !fraction;
        const groupedWhole = whole.replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0");
        return (parts.negative && !isZero ? "-" : "")
            + groupedWhole
            + (fraction ? "," + fraction : "");
    }

    function setUrlParameter(name, value) {
        const url = new URL(window.location.href);
        url.searchParams.set(name, value);
        window.history.replaceState(window.history.state, "", url.toString());

        document.querySelectorAll('input[type="hidden"][name="' + name + '"]').forEach(function (field) {
            field.value = value;
        });
        const query = url.searchParams.toString();
        document.querySelectorAll('input[type="hidden"][name="preserve_qs"]').forEach(function (field) {
            field.value = query;
        });
    }

    function renderCell(cell, digits, coefficientMode) {
        const raw = cell.dataset.roundingValue;
        const input = cell.querySelector('input[name="cell_value[]"]');
        const target = input || cell;
        if (!Object.prototype.hasOwnProperty.call(target.dataset, "roundingRenderedValue")) {
            target.dataset.roundingRenderedValue = input ? input.value : cell.textContent.trim();
        }
        if (input && input.value !== target.dataset.roundingRenderedValue) return;

        const kind = cell.dataset.roundingKind;
        let effectiveDigits = digits;
        if (kind === "graph_point" && !coefficientMode) {
            effectiveDigits = 9;
        } else if (digits === 0 && formulaRowKinds.has(kind)) {
            effectiveDigits = 10;
        }
        const shown = formatDecimal(raw, effectiveDigits);
        if (shown === null) return;

        if (input) {
            const unchanged = input.value === input.defaultValue;
            input.value = shown;
            if (unchanged) {
                input.defaultValue = shown;
                input.dataset.initial = shown;
            }
            input.dataset.roundingRenderedValue = shown;
        } else {
            cell.textContent = shown;
            cell.dataset.roundingRenderedValue = shown;
        }
    }

    function renderTable(digits) {
        table.querySelectorAll("td.summary-year-cell[data-rounding-value]").forEach(function (cell) {
            renderCell(cell, digits);
        });
        table.dataset.roundingDigits = String(digits);
        if (coefficientSelect) renderCoefficients(Number(coefficientSelect.value));
    }

    function renderCoefficients(digits) {
        table.querySelectorAll('td.summary-year-cell[data-rounding-kind="graph_point"][data-rounding-value]').forEach(function (cell) {
            renderCell(cell, digits, true);
        });
        table.querySelectorAll(".lt-ei-rounding-coefficient[data-rounding-value]").forEach(function (item) {
            const raw = item.dataset.roundingValue;
            if (!raw) return;
            const input = item.matches("input") ? item : null;
            const target = input || item;
            if (!Object.prototype.hasOwnProperty.call(target.dataset, "roundingRenderedValue")) {
                target.dataset.roundingRenderedValue = input ? input.value : item.textContent;
            }
            if (input && input.value !== target.dataset.roundingRenderedValue) return;

            const shown = formatDecimal(raw, digits);
            if (shown === null) return;
            if (input) {
                const unchanged = input.value === input.defaultValue;
                input.value = shown;
                if (unchanged) {
                    input.defaultValue = shown;
                    input.dataset.initial = shown;
                }
                input.dataset.roundingRenderedValue = shown;
            } else {
                item.textContent = shown;
                item.dataset.roundingRenderedValue = shown;
            }
        });
    }

    if (numberSelect) {
        numberSelect.addEventListener("change", function () {
            const digits = Number(numberSelect.value);
            const hidden = document.getElementById("rounding_digits_hidden");
            if (hidden) hidden.value = numberSelect.value;
            setUrlParameter("rounding_digits", numberSelect.value);
            renderTable(digits);
        });
        renderTable(Number(numberSelect.value));
    }

    if (coefficientSelect) {
        coefficientSelect.addEventListener("change", function () {
            setUrlParameter("coefficient_rounding_digits", coefficientSelect.value);
            renderCoefficients(Number(coefficientSelect.value));
        });
        renderCoefficients(Number(coefficientSelect.value));
        document.addEventListener("lt-ei-graph-points-rendered", function () {
            renderCoefficients(Number(coefficientSelect.value));
        });
    }
}());
