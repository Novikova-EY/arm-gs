(function () {
    "use strict";

    function parseInitialState() {
        const node = document.getElementById("initial-state-json");
        if (!node) {
            return {};
        }
        try {
            return JSON.parse(node.textContent || "{}");
        } catch (e) {
            return {};
        }
    }

    function normalizeValue(value) {
        return String(value || "").trim();
    }

    function getChangedInputs(table) {
        return Array.from(table.querySelectorAll(".external-code-input")).filter(function (input) {
            return normalizeValue(input.value) !== normalizeValue(input.dataset.originalValue || "");
        });
    }

    function updateSaveBar(table, saveBtn, hintNode) {
        const changed = getChangedInputs(table);
        const count = changed.length;
        saveBtn.disabled = count === 0;
        if (count === 0) {
            hintNode.textContent = "";
            hintNode.classList.add("d-none");
            return;
        }
        hintNode.textContent = "Изменено полей: " + count;
        hintNode.classList.remove("d-none");
    }

    function markInputState(input) {
        const changed = normalizeValue(input.value) !== normalizeValue(input.dataset.originalValue || "");
        input.classList.toggle("is-changed", changed);
    }

    async function saveChanges(table, saveBtn, updateUrl, csrfToken) {
        const changed = getChangedInputs(table);
        if (!changed.length) {
            return;
        }

        const updates = changed.map(function (input) {
            return {
                entity_type: input.dataset.entityType,
                record_id: parseInt(input.dataset.recordId, 10),
                new_external_code: normalizeValue(input.value),
            };
        }).filter(function (item) {
            return item.entity_type && item.record_id && item.new_external_code;
        });

        if (!updates.length) {
            alert("Нет данных для сохранения.");
            return;
        }

        const originalHtml = saveBtn.innerHTML;
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Сохранение...';

        try {
            const response = await fetch(updateUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": csrfToken || "",
                },
                body: JSON.stringify({ updates: updates }),
            });
            const data = await response.json().catch(function () {
                return null;
            });

            if (!response.ok || !data || !data.ok) {
                let message = (data && (data.error || (data.errors && data.errors.join("; ")))) || "Не удалось сохранить.";
                alert(message);
                saveBtn.innerHTML = originalHtml;
                updateSaveBar(table, saveBtn, document.getElementById("externalCodeChangedHint"));
                return;
            }

            changed.forEach(function (input) {
                input.dataset.originalValue = normalizeValue(input.value);
                markInputState(input);
            });
            updateSaveBar(table, saveBtn, document.getElementById("externalCodeChangedHint"));
            saveBtn.innerHTML = originalHtml;

            if (typeof data.updated === "number" && data.updated > 0) {
                window.location.reload();
            }
        } catch (e) {
            alert("Ошибка сети при сохранении.");
            saveBtn.innerHTML = originalHtml;
            updateSaveBar(table, saveBtn, document.getElementById("externalCodeChangedHint"));
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        const table = document.getElementById("externalCodeCheckTable");
        const saveBtn = document.getElementById("externalCodeSaveBtn");
        const hintNode = document.getElementById("externalCodeChangedHint");
        if (!table || !saveBtn || !hintNode) {
            return;
        }

        const state = parseInitialState();
        const updateUrl = state.externalCodeUpdateUrl;
        const csrfToken = state.csrfToken || "";

        table.addEventListener("input", function (event) {
            const target = event.target;
            if (!target.classList.contains("external-code-input")) {
                return;
            }
            markInputState(target);
            updateSaveBar(table, saveBtn, hintNode);
        });

        saveBtn.addEventListener("click", function () {
            if (!updateUrl) {
                alert("URL сохранения не настроен.");
                return;
            }
            saveChanges(table, saveBtn, updateUrl, csrfToken);
        });
    });
})();
