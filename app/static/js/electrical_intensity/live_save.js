(function () {
    "use strict";

    let initialized = false;

    function initializeElectricalIntensityLiveSave() {
        if (initialized) return;
        const table = document.getElementById("powerDemandSummaryTable");
        if (!table || !table.dataset.saveCellUrl || typeof window.bindConsumptionLiveSave !== "function") {
            return;
        }

        const form = document.getElementById("electrical-intensity-form");
        if (!form || typeof window.bindConsumptionLiveSave !== "function") return;
        initialized = true;

        const selector = 'input.fuel-param-input:not([readonly]):not(:disabled)';
        table.querySelectorAll(selector).forEach(function (field) {
            field.dataset.initial = field.value;
        });

        function checkboxFor(field) {
            const cell = field.closest("td.summary-year-cell");
            return cell ? cell.querySelector(".lt-ei-graph-point-exclude-toggle") : null;
        }

        table.querySelectorAll(".lt-ei-graph-point-exclude-toggle").forEach(function (checkbox) {
            const field = checkbox.closest("td").querySelector('input[name="cell_value[]"]');
            if (!field) return;
            field.dataset.initialExcluded = checkbox.checked ? "1" : "0";
        });

        async function saveField(field) {
            const checkbox = checkboxFor(field);
            const excluded = checkbox && checkbox.checked ? "1" : "0";
            const exclusionChanged = checkbox && excluded !== field.dataset.initialExcluded;
            if (field.value === field.dataset.initial && !exclusionChanged) return;

            const container = field.closest("td.summary-year-cell")
                || field.closest(".lt-ei-coef-inline")
                || field.closest(".lt-ei-param-inline");
            if (!container || !field.name) throw new Error("Не удалось определить сохраняемую ячейку.");

            const body = new FormData();
            body.append("csrf_token", table.dataset.csrfToken || "");
            container.querySelectorAll('input[type="hidden"][name]').forEach(function (hidden) {
                if (hidden.disabled) return;
                if (hidden.name === "cell_exclude[]" && checkbox) {
                    body.append(hidden.name, excluded);
                } else {
                    body.append(hidden.name, hidden.value);
                }
            });
            body.append(field.name, field.value);

            const response = await fetch(table.dataset.saveCellUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {"X-Requested-With": "XMLHttpRequest"},
                body: body
            });
            const data = await response.json().catch(function () { return null; });
            if (!response.ok || !data || !data.ok) {
                throw new Error(data && data.error || "Не удалось сохранить ячейку.");
            }

            field.dataset.initial = field.value;
            field.defaultValue = field.value;
            field.dataset.roundingValue = field.value;
            field.dataset.roundingRenderedValue = field.value;
            const yearCell = field.closest("td.summary-year-cell");
            if (yearCell) yearCell.dataset.roundingValue = field.value;
            if (checkbox) {
                field.dataset.initialExcluded = excluded;
                checkbox.defaultChecked = checkbox.checked;
            }
        }

        const live = window.bindConsumptionLiveSave(table, selector, saveField);
        table.addEventListener("change", function (event) {
            const checkbox = event.target.closest(".lt-ei-graph-point-exclude-toggle");
            if (!checkbox) return;
            const cell = checkbox.closest("td.summary-year-cell");
            const field = cell && cell.querySelector('input[name="cell_value[]"]');
            if (!field) return;

            const hiddenFlag = cell.querySelector('input[name="cell_exclude[]"]');
            if (hiddenFlag) hiddenFlag.value = checkbox.checked ? "1" : "0";
            field.readOnly = checkbox.checked;
            field.dispatchEvent(new Event("input", {bubbles: true}));
            live.enqueue(field, true);
        });
        table.addEventListener("focusout", function (event) {
            const field = event.target;
            if (field.matches(selector) && field.closest(".lt-ei-coef-inline, .lt-ei-param-inline")) {
                live.enqueue(field);
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initializeElectricalIntensityLiveSave, {once: true});
    } else {
        initializeElectricalIntensityLiveSave();
    }
    window.addEventListener("load", initializeElectricalIntensityLiveSave, {once: true});
})();
