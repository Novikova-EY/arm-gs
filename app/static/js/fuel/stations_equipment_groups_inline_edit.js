(function () {
    "use strict";

    function init() {
        const table = document.getElementById("stationsEquipmentGroupsTable");
        if (!table) return;
        const inputs = Array.from(table.querySelectorAll(".seg-fuel-input"));
        if (!inputs.length) return;
        const queues = new Map();
        const timers = new Map();
        const revisions = new Map();
        const selects = inputs.filter(input => input.tagName === "SELECT");
        let choicesRequest;

        function url(groupId) {
            return table.dataset.inlineUrl.replace("/0/inline", "/" + groupId + "/inline");
        }

        function updateDisplay(input) {
            if (input.value === input.dataset.displayValue) return;
            const label = input.closest("td").querySelector(".seg-fuel-display");
            const option = input.tagName === "SELECT" ?
                Array.from(input.options).find(option => option.value === input.value) : null;
            label.textContent = option ? option.textContent : (input.value || "–");
            input.dataset.displayValue = input.value;
        }

        function status(input, state, message) {
            const cell = input.closest("td");
            cell.classList.toggle("seg-save-success", state === "success");
            cell.classList.toggle("seg-save-error", state === "error");
            cell.title = message;
            input.classList.toggle("seg-save-success", state === "success");
            input.classList.toggle("seg-save-error", state === "error");
            input.setAttribute("aria-invalid", state === "error" ? "true" : "false");
            input.title = message;
        }

        async function readResponse(response) {
            if (response.redirected) throw new Error("Сессия истекла. Обновите страницу и войдите снова.");
            if (!(response.headers.get("content-type") || "").includes("application/json")) {
                throw new Error("Сервер не подтвердил сохранение. Обновите страницу или повторите попытку.");
            }
            const data = await response.json();
            if (!response.ok || !data.success) throw new Error(data.message || "Ошибка сохранения.");
            return data;
        }

        async function loadChoices() {
            if (!selects.length) return;
            if (!choicesRequest) {
                choicesRequest = fetch(url(inputs[0].dataset.groupId), { credentials: "same-origin" })
                    .then(readResponse);
            }
            try {
                const data = await choicesRequest;
                selects.forEach(input => {
                    if (input.dataset.choicesLoaded) return;
                    const current = input.value;
                    const currentLabel = input.options[0].textContent;
                    const options = data.choices[input.dataset.field].map(([value, label]) =>
                        new Option(label, value == null ? "" : String(value)));
                    if (!options.some(option => option.value === current)) {
                        options.push(new Option(currentLabel, current));
                    }
                    input.replaceChildren(...options);
                    input.value = current;
                    input.dataset.choicesLoaded = "1";
                    input.disabled = false;
                    status(input, "", "Выберите значение – оно сохранится автоматически.");
                });
            } catch (error) {
                choicesRequest = null;
                selects.forEach(input => {
                    input.disabled = false;
                    status(input, "error", "Не удалось загрузить справочник. Выберите поле повторно для загрузки. " + error.message);
                });
            }
        }

        function save(input) {
            clearTimeout(timers.get(input));
            const value = input.value;
            if (input.dataset.pendingValue === value) return;
            if (value === input.dataset.savedValue && !input.hasAttribute("data-pending-value")) return;
            const groupId = input.dataset.groupId;
            const field = input.dataset.field;
            const revision = (revisions.get(input) || 0) + 1;
            revisions.set(input, revision);
            input.dataset.pendingValue = value;
            status(input, "", "Сохранение…");
            const previous = queues.get(groupId) || Promise.resolve();
            const pending = previous.then(async () => {
                try {
                    const form = new URLSearchParams({ field, value, csrf_token: table.dataset.csrfToken });
                    const data = await fetch(url(groupId), {
                        method: "POST",
                        credentials: "same-origin",
                        body: form,
                    }).then(readResponse);
                    inputs.filter(peer => peer.dataset.groupId === groupId && peer.dataset.field === field)
                        .forEach(peer => {
                            const unchanged = peer === input ? peer.value === value && revisions.get(input) === revision :
                                peer.value === peer.dataset.savedValue && !peer.hasAttribute("data-pending-value");
                            peer.dataset.savedValue = data.value;
                            if (unchanged) {
                                peer.value = data.value;
                                updateDisplay(peer);
                                status(peer, "success", "Сохранено");
                            }
                        });
                } catch (error) {
                    if (revisions.get(input) === revision && input.value === value) {
                        status(input, "error", error.message + " Измените значение или выйдите из поля для повторной попытки.");
                    }
                } finally {
                    if (revisions.get(input) === revision) delete input.dataset.pendingValue;
                }
            });
            queues.set(groupId, pending);
        }

        inputs.forEach(input => {
            const cell = input.closest("td");
            const label = cell.querySelector(".seg-fuel-display");
            cell.classList.add("seg-fuel-editable");
            input.dataset.displayValue = input.value;

            function edit() {
                if (!input.hidden) return;
                cell.classList.add("seg-editing");
                input.hidden = false;
                label.tabIndex = -1;
                input.focus();
            }

            cell.addEventListener("click", edit);
            label.addEventListener("keydown", event => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    edit();
                }
            });
            input.addEventListener("input", () => {
                status(input, "", "Изменение ожидает сохранения…");
                clearTimeout(timers.get(input));
                if (input.tagName !== "SELECT") timers.set(input, setTimeout(() => save(input), 500));
            });
            input.addEventListener("change", () => save(input));
            input.addEventListener("blur", () => {
                save(input);
                updateDisplay(input);
                input.hidden = true;
                label.tabIndex = 0;
                cell.classList.remove("seg-editing");
            });
            input.addEventListener("focus", () => {
                if (input.tagName === "SELECT" && !input.dataset.choicesLoaded) loadChoices();
            });
            input.addEventListener("keydown", event => {
                if (event.key === "Enter" && input.tagName !== "SELECT" && input.dataset.field !== "note") {
                    event.preventDefault();
                    input.blur();
                }
            });
        });
        window.addEventListener("beforeunload", event => {
            if (inputs.some(input => input.value !== input.dataset.savedValue || input.hasAttribute("data-pending-value"))) {
                event.preventDefault();
                event.returnValue = "";
            }
        });
        loadChoices();
    }

    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
    else init();
})();
