(function () {
    "use strict";

    const growthSelect = document.getElementById("growth_rounding_digits");
    const numberSelect = document.getElementById("rounding_digits");
    if (!growthSelect && !numberSelect) return;
    const growthKeys = new Set(["energy_consumption_yoy_growth_pct", "energy_consumption_sipr_yoy_growth_pct"]);
    const siprIntegerKeys = new Set(["energy_consumption_sipr_mln_kvt_ch", "energy_consumption_sipr_abs_growth_mln", "gaes_charge_consumption_mln_kvt_ch"]);

    function numeric(raw) {
        const value = String(raw || "").split(":").pop().replace(/\s/g, "").replace(",", ".");
        return /^[+-]?\d+(?:\.\d+)?$/.test(value) ? value : null;
    }

    function format(value, digits, growth) {
        if (digits === 0 && !growth) {
            const parts = value.split(".");
            const fraction = (parts[1] || "").replace(/0+$/, "");
            return parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, " ") + (fraction ? "," + fraction : "");
        }
        const places = digits === 0 ? 6 : Math.max(0, digits);
        // Decimal-строка сохраняет точность исходного значения при форматировании.
        let shown = new Intl.NumberFormat("ru-RU", {
            minimumFractionDigits: growth ? places : 0,
            maximumFractionDigits: places
        }).format(value).replace(/\s/g, " ");
        if (/^-0(?:,0+)?$/.test(shown)) shown = shown.slice(1);
        return shown;
    }

    function targetFor(cell) {
        return cell.querySelector('input:not([type="hidden"]), textarea') || cell.querySelector("span") || cell;
    }

    function applyCell(cell, digits, growth) {
        if (cell.matches(".summary-plan-empty, .pd-ec-variant-year-out")) return;
        const target = targetFor(cell);
        const isField = target.matches("input, textarea");
        if (isField && target.hasAttribute("data-initial") && target.value !== target.dataset.initial) return;
        const raw = cell.dataset.roundingRaw || (target.dataset.roundingEdited ? target.dataset.initial :
            target.getAttribute("data-db-full") || cell.getAttribute("data-db-full")
            || cell.title || cell.getAttribute("data-bs-original-title") || target.title
            || target.getAttribute("data-bs-original-title")) || (isField ? target.value : target.textContent);
        const value = numeric(raw);
        if (value === null) return;
        cell.dataset.roundingRaw = value;
        const row = cell.closest("tr");
        const key = row.dataset.parameterKey || "";
        const integer = !growth && digits !== 0 && window.__pdEcSummarySiprMode === true && (
            row.getAttribute("data-pd-ec-sipr-integer-display") === "1"
            || (window.pdEcSummaryTableStandalone === true && siprIntegerKeys.has(key))
        );
        cell.removeAttribute("data-pd-ec-sipr-rounded-backup");
        if (integer) cell.setAttribute("data-pd-ec-sipr-rounded-backup", format(value, digits, false));
        const shown = format(value, integer ? -1 : digits, growth);
        if (isField) {
            target.value = shown;
            target.dataset.initial = shown;
        } else {
            target.textContent = shown;
        }
    }

    function apply() {
        const digits = numberSelect ? Number(numberSelect.value) : 1;
        document.querySelectorAll("#powerDemandSummaryTable tbody tr").forEach(function (row) {
            const key = row.dataset.parameterKey || "";
            if (key === "peak_datetime" || key === "entity_note") return;
            const growth = growthKeys.has(key);
            if (growth && !growthSelect) return;
            const places = growth ? Number(growthSelect.value) :
                (row.classList.contains("pd-ec-verification-row") && digits !== 0 ? 6 : digits);
            row.querySelectorAll("td.summary-year-cell, td.summary-hist-cell").forEach(function (cell) {
                applyCell(cell, places, growth);
            });
        });
        if (numberSelect) {
            document.querySelectorAll('#power-demand-edit-table td:has(input[name="ec_mln[]"], input[name="ec_sipr[]"]), #power-demand-view-table td[title]')
                .forEach(function (cell) { applyCell(cell, digits, false); });
        }
    }

    function bind(select, parameter) {
        if (!select) return;
        select.addEventListener("change", function () {
            const url = new URL(window.location.href);
            url.searchParams.set(parameter, select.value);
            window.history.replaceState(window.history.state, "", url.toString());
            if (parameter === "rounding_digits") {
                document.querySelectorAll("#powerDemandSummaryTable").forEach(function (table) {
                    table.dataset.roundingDigits = select.value;
                    table.dataset.pdRoundingDigits = select.value;
                });
                document.querySelectorAll('input[type="hidden"][name="rounding_digits"]').forEach(function (field) {
                    field.value = select.value;
                });
            }
            apply();
        });
    }

    document.addEventListener("input", function (event) {
        const field = event.target;
        if (!field.matches('#powerDemandSummaryTable td:is(.summary-year-cell, .summary-hist-cell) input, #power-demand-edit-table input[name="ec_mln[]"], #power-demand-edit-table input[name="ec_sipr[]"]')) return;
        const cell = field.closest("td");
        delete cell.dataset.roundingRaw;
        field.dataset.roundingEdited = "1";
    });
    bind(growthSelect, "growth_rounding_digits");
    bind(numberSelect, "rounding_digits");
    document.addEventListener("ec-summary-rows-rendered", apply);
    apply();
})();
