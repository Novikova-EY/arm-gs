(function () {
    "use strict";

    function init() {
        const transferPage = document.getElementById("bindingTransferPage");
        if (!transferPage) return;
        const field = name => document.getElementById("bindingTransfer" + name);
        const parameters = new URLSearchParams(window.location.search);
        const groupId = parameters.has("group_id") ? Number(parameters.get("group_id")) : null;
        let versions = [];
        const selected = new Set();
        let plan = null;
        let token = null;
        let targetVersionId = null;
        let busy = false;
        let completed = false;
        let page = 0;
        const pageSize = 100;
        const comparisonFields = [
            "current_group", "source_group", "current_group_external_code", "source_group_external_code",
            "current_type_ref_uuid", "source_type_ref_uuid", "current_station_link", "source_station_link", "reason",
        ];

        function message(text, type = "info") {
            field("Message").textContent = text;
            field("Message").className = "alert alert-" + type;
        }

        function updateButtons() {
            field("Preview").disabled = busy || completed || !field("Source").value;
            field("Apply").disabled = busy || completed || !token || !selected.size || !field("Confirm").checked;
            field("Source").disabled = busy || completed || groupId !== null || field("Source").options.length < 2;
            field("Destination").disabled = busy || completed || !versions.length;
            field("Create").disabled = busy || completed;
            field("Select").disabled = busy || completed;
            field("Clear").disabled = busy || completed;
            field("Confirm").disabled = busy || completed;
            field("Download").disabled = busy || !plan;
            field("Back").setAttribute("aria-disabled", String(busy));
            field("Rows").querySelectorAll("input").forEach(input => { input.disabled = busy || completed; });
        }

        function selectionChanged() {
            field("Confirm").checked = false;
            updateButtons();
        }

        function reset() {
            plan = null;
            token = null;
            selected.clear();
            field("Results").hidden = true;
            field("Confirmation").hidden = true;
            field("Download").hidden = true;
            field("Confirm").checked = false;
            field("Message").className = "alert d-none";
            updateButtons();
        }

        async function request(body, excel = false) {
            const response = await fetch(transferPage.dataset.url, {
                method: body ? "POST" : "GET",
                credentials: "same-origin",
                headers: body ? { "Content-Type": "application/json", "X-CSRF-Token": transferPage.dataset.csrfToken } : {},
                body: body ? JSON.stringify(body) : undefined,
            });
            const contentType = response.headers.get("content-type") || "";
            if (excel && response.ok && !response.redirected && contentType.includes("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")) {
                return response.blob();
            }
            if (response.redirected || !contentType.includes("application/json")) {
                throw new Error("Сессия истекла или сервер недоступен. Обновите страницу.");
            }
            const data = await response.json();
            if (!response.ok || !data.success || excel) throw new Error(data.message || "Не удалось выполнить запрос.");
            return data;
        }

        function render() {
            if (!plan) return;
            const filter = field("Filter").value;
            const search = field("Search").value.trim().toLocaleLowerCase("ru");
            const rows = plan.rows.filter(row =>
                (filter === "all" || (filter === "changes" ? row.status !== "same" : row.status === filter)) &&
                (!search || [row.station, row.equipment, ...comparisonFields.map(key => row[key])]
                    .join(" ").toLocaleLowerCase("ru").includes(search)));
            const pages = Math.max(1, Math.ceil(rows.length / pageSize));
            page = Math.min(page, pages - 1);
            const fragment = document.createDocumentFragment();
            rows.slice(page * pageSize, (page + 1) * pageSize).forEach(row => {
                const tr = document.createElement("tr");
                if (row.status === "conflict") tr.className = "table-warning";
                if (row.status === "blocked") tr.className = "table-secondary";
                const choice = document.createElement("td");
                if (row.status === "ready" || row.status === "conflict") {
                    const input = document.createElement("input");
                    input.type = "checkbox";
                    input.className = "form-check-input";
                    input.checked = selected.has(row.key);
                    input.disabled = busy || completed;
                    input.setAttribute("aria-label", "Перенести: " + row.station + ", " + row.equipment);
                    input.addEventListener("change", () => {
                        if (input.checked) selected.add(row.key); else selected.delete(row.key);
                        selectionChanged();
                        render();
                    });
                    choice.append(input);
                }
                tr.append(choice);
                [row.station + "\n" + row.equipment, ...comparisonFields.map(key => row[key])].forEach(value => {
                    const cell = document.createElement("td");
                    cell.textContent = value;
                    cell.style.whiteSpace = "pre-line";
                    tr.append(cell);
                });
                fragment.append(tr);
            });
            field("Rows").replaceChildren(fragment);
            const replacements = plan.rows.filter(row => row.status === "conflict" && selected.has(row.key)).length;
            field("Selection").textContent = `Выбрано: ${selected.size}, из них замен: ${replacements}. Показано: ${rows.length}. Страница ${page + 1} из ${pages}.`;
            field("Previous").disabled = page === 0;
            field("Next").disabled = page + 1 >= pages;
        }

        window.addEventListener("beforeunload", event => {
            if (busy) {
                event.preventDefault();
                event.returnValue = "";
            }
        });
        field("Back").addEventListener("click", event => { if (busy) event.preventDefault(); });

        async function loadVersions() {
            busy = true;
            updateButtons();
            try {
                const data = await request();
                versions = data.versions;
                if (groupId !== null && (!Number.isSafeInteger(groupId) || groupId <= 0)) {
                    throw new Error("Некорректная исходная группа в ссылке. Откройте перенос из таблицы проверки заново.");
                }
                const sourceId = parameters.get("source_version_id") || "";
                const destinationId = parameters.get("destination_version_id") || String(data.target.id);
                if (!versions.some(version => String(version.id) === destinationId) ||
                    (groupId !== null && !versions.some(version => String(version.id) === sourceId && String(version.id) !== destinationId))) {
                    throw new Error("Версии из ссылки недоступны или совпадают. Откройте перенос из таблицы проверки заново.");
                }
                versions.forEach(version => {
                    const option = new Option(version.name, version.id);
                    option.disabled = groupId !== null && String(version.id) === sourceId;
                    field("Destination").add(option);
                });
                field("Destination").value = destinationId;
                refreshSources(sourceId);
                if (groupId !== null) {
                    field("Create").checked = parameters.get("create_missing") === "1";
                    field("Scope").textContent = `План только для исходной группы ID ${groupId}, ее связей и типов связанных агрегатов. Остальные группы не переносятся.`;
                    field("Scope").hidden = false;
                }
                if (versions.length < 2) message("Нет других версий базы данных для переноса.");
            } catch (error) {
                message(error.message, "danger");
            } finally {
                busy = false;
                updateButtons();
            }
        }
        function refreshSources(sourceId) {
            targetVersionId = Number(field("Destination").value);
            field("Target").textContent = field("Destination").selectedOptions[0].textContent;
            field("Source").replaceChildren(new Option("Выберите версию", ""));
            versions.filter(version => version.id !== targetVersionId)
                .forEach(version => field("Source").add(new Option(version.name, version.id)));
            field("Source").value = sourceId;
        }
        field("Destination").addEventListener("change", () => {
            refreshSources(field("Source").value);
            reset();
        });
        field("Source").addEventListener("change", reset);
        field("Create").addEventListener("change", reset);
        field("Confirm").addEventListener("change", updateButtons);
        field("Filter").addEventListener("change", () => { page = 0; render(); });
        field("Search").addEventListener("input", () => { page = 0; render(); });
        field("Previous").addEventListener("click", () => { page--; render(); });
        field("Next").addEventListener("click", () => { page++; render(); });
        field("Select").addEventListener("click", () => {
            plan.rows.filter(row => row.status === "ready").forEach(row => selected.add(row.key));
            selectionChanged();
            render();
        });
        field("Clear").addEventListener("click", () => { selected.clear(); selectionChanged(); render(); });
        field("Preview").addEventListener("click", async () => {
            reset();
            busy = true;
            updateButtons();
            message("Анализ связей… Данные не изменяются.");
            try {
                const data = await request({ action: "preview", source_version_id: Number(field("Source").value), destination_version_id: targetVersionId, create_missing: field("Create").checked, group_id: groupId });
                plan = data.plan;
                token = data.token;
                plan.rows.filter(row => row.status === "ready").forEach(row => selected.add(row.key));
                const counts = plan.counts;
                field("Summary").textContent = `Можно перенести: ${counts.ready || 0}. Замен: ${counts.conflict || 0}. Проблем: ${counts.blocked || 0}. Уже совпадает: ${counts.same || 0}.`;
                field("Results").hidden = false;
                field("Confirmation").hidden = false;
                field("Download").hidden = false;
                page = 0;
                render();
                message(plan.rows.length ? "Проверьте план и подтвердите выбранные строки. План действует без ограничения по времени, пока данные не изменились. Группы создаются только для выбранных связей и их родителей." : "В исходной версии нет типов агрегатов, явных привязок или связей станций для переноса.");
            } catch (error) {
                message(error.message, "danger");
            } finally {
                busy = false;
                updateButtons();
            }
        });
        field("Apply").addEventListener("click", async () => {
            busy = true;
            updateButtons();
            message("Перенос выбранных связей… Не закрывайте страницу.");
            try {
                const data = await request({ action: "apply", token, keys: Array.from(selected) });
                completed = true;
                field("Reload").hidden = false;
                field("Repeat").hidden = false;
                field("Confirmation").hidden = true;
                message(`Перенос завершен. Обработано агрегатов: ${data.result.machines}. Создано групп: ${data.result.groups}, связей станций с типами: ${data.result.station_links}, связей итоговых групп: ${data.result.links}. Остальные строки не изменены. Откройте таблицу или обновите исходную вкладку словаря.`, "success");
            } catch (error) {
                token = null;
                field("Confirm").checked = false;
                message(error.message + " Перед новой попыткой повторите анализ. Если ответ потерян, анализ покажет фактическое состояние связей.", "danger");
            } finally {
                busy = false;
                updateButtons();
            }
        });
        field("Download").addEventListener("click", async () => {
            if (!plan || busy) return;
            busy = true;
            updateButtons();
            try {
                const report = { source: field("Source").selectedOptions[0].textContent, target: field("Target").textContent,
                    selected_keys: Array.from(selected), completed, rows: plan.rows };
                const blob = await request({ action: "report", report }, true);
                const url = URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = url;
                link.download = "equipment_group_binding_transfer.xlsx";
                link.click();
                setTimeout(() => URL.revokeObjectURL(url), 1000);
            } catch (error) {
                message(error.message, "danger");
            } finally {
                busy = false;
                updateButtons();
            }
        });
        field("Repeat").addEventListener("click", () => {
            completed = false;
            field("Reload").hidden = true;
            field("Repeat").hidden = true;
            reset();
            message("Выберите следующую целевую версию и повторите анализ. В уже заполненной версии повторный план не создаст дубликаты.");
        });
        field("Reload").addEventListener("click", () => window.location.assign(transferPage.dataset.catalogUrl));
        loadVersions();
    }
    document.addEventListener("DOMContentLoaded", init);
})();
