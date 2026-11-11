(function () {
    "use strict";
    document.addEventListener("DOMContentLoaded", function () {
        const form = document.getElementById("demand-params-form");
        if (!form) return;
        const tbody = form.querySelector("#demand-rows");
        const selector = 'select[name="slice_year[]"], input[name="p_max[]"], textarea[name="dt[]"], input[name="tnv[]"], input[name="oes[]"]:not([type="hidden"]), input[name="ees[]"]:not([type="hidden"]), input[name="es[]"]:not([type="hidden"]), input[name="ez[]"]:not([type="hidden"]), input[name="del[]"]';
        const blankRow = tbody.querySelector("tr.table-light").cloneNode(true);

        function remember(row) {
            row.querySelectorAll(selector).forEach(function (field) {
                field.dataset.initial = field.value;
            });
        }
        tbody.querySelectorAll("tr").forEach(remember);

        const live = window.bindConsumptionLiveSave(form, selector, async function (field) {
            if (field.type !== "checkbox" && field.value === (field.dataset.initial || "")) return;
            const row = field.closest("tr");
            const year = row.querySelector('[name="slice_year[]"]').value;
            const deletion = row.querySelector('[name="del[]"]');
            if (!year && !(deletion && deletion.checked)) {
                throw new Error("Выберите год для сохранения строки.");
            }
            const body = new FormData();
            const snapshot = new Map();
            row.querySelectorAll("input, select, textarea").forEach(function (input) {
                if (input.type !== "checkbox" || input.checked) body.append(input.name, input.value);
                snapshot.set(input, input.value);
            });
            body.append("csrf_token", form.querySelector('[name="csrf_token"]').value);
            body.append("rounding_digits", form.querySelector('[name="rounding_digits"]').value);
            const response = await window.powerDemandSaveFetch(form.action || window.location.href, {
                method: "POST", credentials: "same-origin",
                headers: { "X-Requested-With": "XMLHttpRequest" }, body: body
            });
            const data = await response.json().catch(function () { return null; });
            if (!response.ok || !data || !data.ok) {
                throw new Error(data && data.error || "Не удалось сохранить данные.");
            }
            if (body.has("del[]")) {
                row.remove();
                return;
            }
            const saved = data.rows.find(function (item) { return String(item.year) === year; });
            if (!saved) throw new Error("Сервер не вернул сохраненную строку.");
            const id = row.querySelector('[name="row_id[]"]');
            if (!id.value) {
                id.value = saved.id;
                row.classList.remove("table-light");
                const cell = id.closest("td");
                cell.classList.remove("text-muted");
                Array.from(cell.childNodes).forEach(function (node) {
                    if (node.nodeType === Node.TEXT_NODE) node.remove();
                });
                const checkbox = document.createElement("input");
                checkbox.type = "checkbox";
                checkbox.name = "del[]";
                checkbox.value = saved.id;
                cell.prepend(checkbox);
                remember(checkbox.closest("tr"));
                const next = blankRow.cloneNode(true);
                remember(next);
                tbody.appendChild(next);
            }
            row.querySelector('[name="p_max_db[]"]').value = saved.p_max;
            row.querySelector('[name="p_max[]"]').title = saved.p_max;
            snapshot.forEach(function (value, input) {
                input.dataset.initial = value;
                if (input.matches(selector) && input.value === value) {
                    input.classList.remove("is-save-error");
                    input.classList.add("is-save-success");
                    input.removeAttribute("aria-invalid");
                    if (input.dataset.saveError) {
                        input.title = input.dataset.saveOriginalTitle;
                        delete input.dataset.saveOriginalTitle;
                        delete input.dataset.saveError;
                    }
                }
            });
        });

        form.addEventListener("submit", async function (event) {
            event.preventDefault();
            form.querySelectorAll(selector).forEach(function (field) {
                if (field.type === "checkbox" ? field.checked : field.value !== (field.dataset.initial || "")) {
                    live.enqueue(field);
                }
            });
            const buttons = form.querySelectorAll('[type="submit"]');
            buttons.forEach(function (button) { button.disabled = true; });
            await live.whenIdle();
            buttons.forEach(function (button) { button.disabled = false; });
        });
    });
})();
