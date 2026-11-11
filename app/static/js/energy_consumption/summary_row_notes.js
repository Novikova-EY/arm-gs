(function () {
    "use strict";
    document.addEventListener("DOMContentLoaded", function () {
        const table = document.getElementById("powerDemandSummaryTable");
        if (!table || !table.dataset.noteSaveUrl) return;
        const live = window.bindConsumptionLiveSave(table, "textarea.ec-summary-row-note", async function (field) {
            const value = field.value;
            if (value === (field.dataset.initial || "")) return;
            const response = await fetch(table.dataset.noteSaveUrl, {
                method: "POST", credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": table.dataset.csrfToken,
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: JSON.stringify({ row_key: field.dataset.noteKey, value: value, database_version_id: field.dataset.noteVersion })
            });
            const data = await response.json().catch(function () { return null; });
            if (!response.ok || !data || !data.ok) {
                throw new Error(data && data.error || "Не удалось сохранить примечание.");
            }
            field.dataset.initial = value;
        });
        const saveButton = document.getElementById("demandSummarySaveBtn");
        if (saveButton) saveButton.addEventListener("click", async function (event) {
            const notes = Array.from(table.querySelectorAll("textarea.ec-summary-row-note"))
                .filter(field => field.value !== (field.dataset.initial || ""));
            if (!notes.length) return;
            event.preventDefault();
            event.stopImmediatePropagation();
            notes.forEach(field => live.enqueue(field));
            saveButton.disabled = true;
            await live.whenIdle();
            saveButton.disabled = false;
            if (notes.some(field => field.value !== (field.dataset.initial || ""))) return;
            const numericChanges = Array.from(table.querySelectorAll("[data-model][data-slice][data-initial], .pd-ec-perimeter-variant-select"))
                .some(field => !field.readOnly && !field.disabled && field.value !== (field.dataset.initial || ""));
            if (numericChanges) saveButton.click();
        }, true);
    });
})();
