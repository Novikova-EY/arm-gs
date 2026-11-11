document.addEventListener("DOMContentLoaded", function () {
    "use strict";

    const yearSelect = document.getElementById("rs-year");
    const importForm = document.getElementById("rsImportForm");

    async function readSaveResponse(response) {
        if (response.redirected || response.status === 401) {
            throw new Error("Сессия истекла. Обновите страницу и войдите снова.");
        }
        if (!(response.headers.get("Content-Type") || "").includes("application/json")) {
            throw new Error(`Не удалось сохранить данные: сервер вернул HTTP ${response.status} вместо JSON. Обновите страницу и повторите попытку.`);
        }
        return response.json();
    }

    if (importForm) {
        const importYear = document.getElementById("rs-import-year");
        const importButton = document.getElementById("rs-import-button");
        const fileInput = document.getElementById("rs-file");

        function syncImportYear() {
            if (!importYear || !yearSelect) return;
            importYear.value = yearSelect.value;
        }

        syncImportYear();
        importButton.addEventListener("click", function () {
            fileInput.click();
        });
        fileInput.addEventListener("change", function () {
            if (fileInput.files.length > 0) {
                importForm.requestSubmit();
            }
        });
        if (yearSelect) yearSelect.addEventListener("change", syncImportYear);
        importForm.addEventListener("submit", function () {
            syncImportYear();
            importButton.disabled = true;
            importButton.innerHTML = '<span class="spinner-border spinner-border-sm" aria-hidden="true"></span> Импорт... (подождите)';
        });
    }

    // Инициализация тултипов для кнопок информации о сопоставлении
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    tooltipTriggerList.forEach(function (tooltipTriggerEl) {
        new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Автосохранение ID агрегата (как на ee_transfers)
    const table = document.querySelector(".rs-technical-table");
    if (table) {
        table.addEventListener("keydown", function (event) {
            const input = event.target.closest("input.machine-id-input");
            if (!input) return;
            if (event.key === "Enter") {
                event.preventDefault();
                input.blur();
            } else if (event.key === "Escape") {
                input.value = input.dataset.original || "";
                input.blur();
            }
        });

        table.addEventListener("change", async function (event) {
            const input = event.target.closest("input.machine-id-input");
            if (!input || input.value === input.dataset.original) return;
            const cell = input.closest("td");
            if (!cell) return;

            input.disabled = true;
            cell.classList.remove("is-save-success", "is-save-error");
            try {
                const response = await fetch(input.dataset.saveUrl, {
                    method: "PATCH",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                        "X-CSRFToken": document.querySelector('meta[name="csrf-token"]')?.content || "",
                    },
                    body: JSON.stringify({
                        turbine_id: input.dataset.turbineId,
                        machine_id: input.value || null,
                        station_id: input.dataset.stationId || null,
                    }),
                });
                const result = await readSaveResponse(response);
                if (!response.ok || result.ok === false) {
                    throw new Error(result.error || "Ошибка сохранения ID агрегата");
                }
                const displayId = result.machine_id
                    ? (result.pgu_machine_id ? result.machine_id + "/" + result.pgu_machine_id : String(result.machine_id))
                    : "";
                input.value = displayId;
                input.dataset.original = displayId;
                cell.classList.add("is-save-success");
                // Обновляем статус сопоставления если нужно
                if (result.match_status) {
                    const row = input.closest("tr");
                    if (row) {
                        row.dataset.matchStatus = result.match_status;
                        row.className = row.className.replace(/rs-match-\w+/, "rs-match-" + result.match_status);
                        row.className = row.className.replace(/table-(warning|info|danger|success)/, "");
                        if (result.match_status === "partial") row.classList.add("table-warning");
                        else if (result.match_status === "ambiguous") row.classList.add("table-info");
                        else if (result.match_status === "unmatched") row.classList.add("table-danger");
                        else if (result.match_status === "matched") row.classList.add("table-success");
                    }
                }
            } catch (error) {
                input.value = input.dataset.original || "";
                cell.classList.add("is-save-error");
                window.alert(error.message || "Ошибка сохранения ID агрегата");
            } finally {
                input.disabled = false;
            }
        });
    }

    // Автосохранение кода Техинспекции в карточке агрегата
    const tiCodeInput = document.querySelector('input[name="technical_inspection_code"]');
    if (tiCodeInput) {
        tiCodeInput.dataset.original = tiCodeInput.value;
        tiCodeInput.addEventListener("keydown", function (event) {
            if (event.key === "Enter") {
                event.preventDefault();
                this.blur();
            } else if (event.key === "Escape") {
                this.value = this.dataset.original || "";
                this.blur();
            }
        });

        tiCodeInput.addEventListener("change", async function (event) {
            if (this.value === this.dataset.original) return;

            this.disabled = true;
            this.classList.remove("is-save-success", "is-save-error");
            try {
                const response = await fetch(this.dataset.saveUrl, {
                    method: "PATCH",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-Requested-With": "XMLHttpRequest",
                        "X-CSRFToken": document.querySelector('meta[name="csrf-token"]')?.content || "",
                    },
                    body: JSON.stringify({
                        machine_id: this.dataset.machineId || null,
                        pgu_machine_id: this.dataset.pguMachineId || null,
                        equipment_code: this.value || null,
                        previous_code: this.dataset.original || null,
                    }),
                });
                const result = await readSaveResponse(response);
                if (!response.ok || result.ok === false) {
                    throw new Error(result.error || "Ошибка сохранения кода Техинспекции");
                }
                this.value = result.equipment_code || "";
                this.dataset.original = result.equipment_code || "";
                this.classList.add("is-save-success");
            } catch (error) {
                this.value = this.dataset.original || "";
                this.classList.add("is-save-error");
                window.alert(error.message || "Ошибка сохранения кода Техинспекции");
            } finally {
                this.disabled = false;
            }
        });
    }

});
