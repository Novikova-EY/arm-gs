(function () {
    "use strict";

    const root = document.getElementById("energyBalanceDataRefresh");
    if (!root) return;
    const config = JSON.parse(document.getElementById("energy-balance-refresh-config").textContent);
    const button = document.getElementById("energyBalanceRefreshButton");
    const label = document.getElementById("energyBalanceRefreshLabel");
    const status = document.getElementById("energyBalanceRefreshStatus");
    const loadedAt = document.getElementById("dataRefreshLoadedAt");
    const heading = Array.from(document.querySelectorAll("h1")).find(element => element.getClientRects().length);
    if (heading) {
        const headingRow = document.createElement("div");
        headingRow.className = "d-flex flex-wrap align-items-center justify-content-center gap-2 gap-md-3 mb-3";
        heading.before(headingRow);
        headingRow.append(heading, loadedAt);
        heading.classList.remove("mb-2", "mb-3", "mb-4");
        heading.classList.add("mb-0");
    }
    const dateFormat = new Intl.DateTimeFormat("ru-RU", {dateStyle: "short", timeStyle: "medium"});
    function formatTime(value) {
        const date = new Date(value);
        return Number.isNaN(date.getTime()) ? "" : dateFormat.format(date);
    }
    if (config.loadedAt) {
        loadedAt.textContent = "Данные страницы на " + formatTime(config.loadedAt);
    }
    function historyUrl(base) {
        const url = new URL(base, window.location.href);
        if (config.historyCursor) url.searchParams.set("history_cursor", config.historyCursor);
        return url.href;
    }
    const selector = "table tbody input:not([type=hidden]):not([readonly]):not(:disabled), table tbody textarea:not([readonly]):not(:disabled), table tbody select:not(:disabled), table tbody [contenteditable=true]";
    const initialValues = new Map();
    let editSequence = 0;
    let checking = false;
    let refreshing = false;
    let saving = 0;
    let saveSequence = 0;

    function value(field) {
        if (field.isContentEditable) return field.textContent;
        if (field.type === "checkbox" || field.type === "radio") return field.checked;
        if (field.multiple) return Array.from(field.selectedOptions, option => option.value).join("\u0000");
        return field.value;
    }

    function captureInitialValues() {
        document.querySelectorAll(selector).forEach(field => {
            if (!initialValues.has(field)) initialValues.set(field, value(field));
        });
    }
    // Сводки восстанавливают настройки и форматируют значения при DOMContentLoaded.
    if (document.readyState !== "complete") {
        document.addEventListener("DOMContentLoaded", captureInitialValues, {once: true});
    } else {
        captureInitialValues();
    }
    document.addEventListener("focusin", function (event) {
        if (event.target.matches(selector) && !initialValues.has(event.target)) {
            initialValues.set(event.target, value(event.target));
        }
    });
    function noteEdit(event) {
        if (!event.target.matches(selector)) return;
        // Вставка из Excel может менять динамическое поле без предварительного focusin.
        if (!initialValues.has(event.target)) {
            initialValues.set(event.target, event.target.defaultValue ?? "");
        }
        editSequence++;
    }
    document.addEventListener("input", noteEdit, true);
    document.addEventListener("change", noteEdit, true);

    function hasEdits() {
        if (document.querySelector("table .is-save-error, table .pd-summary-cell-save-error, table [aria-invalid=true]")) return true;
        return Array.from(initialValues).some(([field, initial]) => field.isConnected && value(field) !== (
            field.type !== "checkbox" && field.type !== "radio" && !field.multiple
                ? (field.dataset.initial ?? initial) : initial
        ));
    }

    async function readResponse(response) {
        if (response.redirected) throw new Error("Сессия изменилась. Войдите в систему в другой вкладке и повторите обновление.");
        if (!response.ok) throw new Error("Не удалось обновить данные. Код ответа: " + response.status);
        const result = await response.json();
        if (!result.ok || typeof result.revision !== "string") throw new Error("Не удалось получить состояние данных.");
        return result;
    }

    document.addEventListener("module-data:saving", function (event) {
        saving += event.detail.active ? 1 : -1;
        saveSequence++;
    });

    function acknowledgeSave(event) {
        if (event.detail.before !== config.revision) return;
        config.revision = event.detail.revision;
        button.classList.remove("btn-danger", "text-white");
        button.classList.add("btn-warning", "text-dark");
        label.textContent = "Обновить данные";
    }
    document.addEventListener("energy-consumption:saved", acknowledgeSave);
    document.addEventListener("module-data:saved", acknowledgeSave);

    async function checkRevision() {
        if (checking || refreshing || saving || document.hidden) return;
        checking = true;
        const checkedRevision = config.revision;
        const checkedSaveSequence = saveSequence;
        try {
            const result = await readResponse(await fetch(historyUrl(config.statusUrl), {
                credentials: "same-origin", cache: "no-store", headers: {Accept: "application/json"}
            }));
            if (checkedRevision !== config.revision || saving || checkedSaveSequence !== saveSequence) return;
            const count = result.history?.count || 0;
            // Общий счетчик модуля меняется и при сохранении в других версиях БД.
            const changed = result.revision !== config.revision &&
                (result.history?.available !== true || count > 0);
            button.classList.toggle("btn-warning", !changed);
            button.classList.toggle("text-dark", !changed);
            button.classList.toggle("btn-danger", changed);
            button.classList.toggle("text-white", changed);
            label.textContent = changed ? "Версия базы данных изменилась. Обновите страницу." : "Обновить данные";
            status.textContent = "";
        } catch (error) {
            status.textContent = "Не удалось проверить актуальность данных. Можно повторить обновление вручную.";
        } finally {
            checking = false;
        }
    }

    button.addEventListener("click", async function () {
        if (refreshing) return;
        // Не выводим состояние «сохранено» по цвету ячейки: старый ответ может прийти после новой правки.
        if ((saving || hasEdits()) && !window.confirm(
            "В таблице есть введенные значения. Обновление может удалить несохраненные правки. " +
            "Убедитесь, что сохранение завершено. Обновить таблицу?"
        )) return;
        const sequence = editSequence;
        refreshing = true;
        button.disabled = true;
        status.textContent = "Обновление данных...";
        try {
            await readResponse(await fetch(config.refreshUrl, {
                method: "POST", credentials: "same-origin", cache: "no-store",
                headers: {"X-CSRFToken": root.dataset.csrfToken, Accept: "application/json"}
            }));
            if (sequence !== editSequence) {
                status.textContent = "Появились новые правки. Данные не перезагружены. Завершите редактирование и повторите обновление.";
                return;
            }
            window.location.reload();
        } catch (error) {
            status.textContent = error.message || "Не удалось обновить данные. Введенные значения сохранены на странице.";
        } finally {
            refreshing = false;
            button.disabled = false;
        }
    });

    window.setInterval(checkRevision, 20000);
    document.addEventListener("visibilitychange", checkRevision);
    window.addEventListener("focus", checkRevision);
    window.addEventListener("pageshow", checkRevision);
}());
