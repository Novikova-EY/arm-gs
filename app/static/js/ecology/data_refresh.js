(function () {
    "use strict";

    const root = document.getElementById("ecologyDataRefresh");
    if (!root) return;

    const button = document.getElementById("ecologyRefreshButton");
    const loadedAt = document.getElementById("ecologyRefreshLoadedAt");
    const status = document.getElementById("ecologyRefreshStatus");
    const placement = document.getElementById("ecologyRefreshPlacement");
    const heading = Array.from(document.querySelectorAll("h1")).find(function (element) {
        return element.getClientRects().length;
    });
    const roundingLabel = Array.from(document.querySelectorAll("label")).find(function (label) {
        return label.textContent.trim().startsWith("Округл");
    });
    if (roundingLabel) {
        const roundingControl = roundingLabel.closest("div");
        if (roundingControl) roundingControl.insertBefore(root, roundingControl.firstChild);
    } else if (heading?.parentNode) {
        heading.parentNode.insertBefore(root, heading);
    }
    if (heading && loadedAt) {
        const headingRow = document.createElement("div");
        headingRow.className = "d-flex flex-wrap align-items-center justify-content-center gap-2 gap-md-3 mb-3";
        heading.before(headingRow);
        headingRow.append(heading, loadedAt);
        heading.classList.remove("mb-2", "mb-3", "mb-4");
        heading.classList.add("mb-0");
    }
    placement?.classList.add("d-none");

    const timestamp = root.dataset.loadedAt;
    if (timestamp) {
        const date = new Date(timestamp);
        if (!Number.isNaN(date.getTime())) {
            loadedAt.textContent = "Данные страницы на " + new Intl.DateTimeFormat("ru-RU", {
                dateStyle: "short",
                timeStyle: "medium"
            }).format(date);
        }
    }

    button.addEventListener("click", async function () {
        if (button.disabled) return;
        const activeEdit = document.activeElement?.matches(
            "table tbody input:not([type=hidden]):not([readonly]):not(:disabled), " +
            "table tbody textarea:not([readonly]):not(:disabled), " +
            "table tbody [contenteditable=true]"
        );
        const failedEdit = document.querySelector("table .is-save-error, table [aria-invalid=true]");
        if ((activeEdit || failedEdit) && !window.confirm(
            "Есть несохраненные или ошибочные изменения в таблице. Обновить страницу?"
        )) return;

        button.disabled = true;
        status.textContent = "Обновление данных...";
        try {
            const response = await fetch(root.dataset.refreshUrl, {
                method: "POST",
                credentials: "same-origin",
                cache: "no-store",
                headers: {
                    "X-CSRFToken": root.dataset.csrfToken,
                    "Accept": "application/json"
                }
            });
            if (response.redirected) throw new Error("Сессия изменилась. Войдите в систему и повторите обновление.");
            if (!response.ok) throw new Error("Не удалось обновить данные. Код ответа: " + response.status);
            const result = await response.json();
            if (!result.ok) throw new Error("Не удалось обновить данные.");
            window.location.reload();
        } catch (error) {
            status.textContent = error.message || "Не удалось обновить данные. Повторите попытку.";
            button.disabled = false;
        }
    });
}());
