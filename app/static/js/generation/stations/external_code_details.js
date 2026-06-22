(function () {
    "use strict";

    function normalizeValue(value) {
        return String(value || "").trim();
    }

    function markInputState(input, saveBtn) {
        const changed = normalizeValue(input.value) !== normalizeValue(input.dataset.originalValue || "");
        input.classList.toggle("is-changed", changed);
        if (saveBtn) {
            saveBtn.disabled = !changed;
        }
    }

    async function saveExternalCode(input, saveBtn, updateUrl, csrfToken) {
        const entityType = input.dataset.entityType;
        const recordId = parseInt(input.dataset.recordId, 10);
        const newCode = normalizeValue(input.value);

        if (!entityType || !recordId) {
            alert("Не удалось определить запись для сохранения.");
            return;
        }
        if (!newCode) {
            alert("external_code не может быть пустым.");
            return;
        }

        const originalHtml = saveBtn.innerHTML;
        saveBtn.disabled = true;
        saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span>';

        try {
            const response = await fetch(updateUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": csrfToken || "",
                },
                body: JSON.stringify({
                    updates: [{
                        entity_type: entityType,
                        record_id: recordId,
                        new_external_code: newCode,
                    }],
                }),
            });
            const data = await response.json().catch(function () {
                return null;
            });

            if (!response.ok || !data || !data.ok) {
                const message = (data && (data.error || (data.errors && data.errors.join("; "))))
                    || "Не удалось сохранить external_code.";
                alert(message);
                saveBtn.innerHTML = originalHtml;
                markInputState(input, saveBtn);
                return;
            }

            input.dataset.originalValue = newCode;
            markInputState(input, saveBtn);
            saveBtn.innerHTML = originalHtml;
        } catch (e) {
            alert("Ошибка сети при сохранении external_code.");
            saveBtn.innerHTML = originalHtml;
            markInputState(input, saveBtn);
        }
    }

    document.addEventListener("DOMContentLoaded", function () {
        const configNode = document.getElementById("external-code-details-config");
        if (!configNode) {
            return;
        }

        let config = {};
        try {
            config = JSON.parse(configNode.textContent || "{}");
        } catch (e) {
            return;
        }

        const updateUrl = config.externalCodeUpdateUrl;
        const csrfToken = config.csrfToken || "";

        document.querySelectorAll(".external-code-details-input").forEach(function (input) {
            const saveBtn = input.closest(".external-code-header-widget")?.querySelector(".external-code-details-save-btn");
            if (!saveBtn) {
                return;
            }

            input.addEventListener("input", function () {
                markInputState(input, saveBtn);
            });

            input.addEventListener("keydown", function (event) {
                if (event.key === "Enter") {
                    event.preventDefault();
                    if (!saveBtn.disabled && updateUrl) {
                        saveExternalCode(input, saveBtn, updateUrl, csrfToken);
                    }
                }
            });

            saveBtn.addEventListener("click", function () {
                if (!updateUrl) {
                    alert("URL сохранения external_code не настроен.");
                    return;
                }
                saveExternalCode(input, saveBtn, updateUrl, csrfToken);
            });
        });
    });
})();
