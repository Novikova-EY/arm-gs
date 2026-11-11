(function () {
    "use strict";

    document.addEventListener("DOMContentLoaded", function () {
        const table = document.getElementById("externalCodeCheckTable");
        const button = document.getElementById("externalCodeVersionFilter");
        if (!table || !button) return;

        const menu = document.getElementById("externalCodeVersionMenu");
        const search = document.getElementById("externalCodeVersionSearch");
        const selectAll = document.getElementById("externalCodeVersionSelectAll");
        const error = document.getElementById("externalCodeVersionError");
        const checkboxes = Array.from(menu.querySelectorAll("#externalCodeVersionList input"));
        const cells = Array.from(table.querySelectorAll("[data-external-code-version]"));
        const spanningCells = Array.from(table.querySelectorAll("tbody [colspan]")).filter(cell => cell.colSpan > 3);
        const storageKey = "externalCodeCheck.hiddenVersions";
        let hiddenVersions = new Set();

        // Storage can be disabled by browser privacy settings.
        try {
            const saved = JSON.parse(localStorage.getItem(storageKey) || "[]");
            if (Array.isArray(saved)) hiddenVersions = new Set(saved.filter(value => typeof value === "string"));
        } catch (error) {
            console.warn("Не удалось восстановить выбор версий", error);
        }
        if (checkboxes.every(checkbox => hiddenVersions.has(checkbox.value))) hiddenVersions.clear();

        function applyColumns() {
            const count = checkboxes.filter(checkbox => !hiddenVersions.has(checkbox.value)).length;
            cells.forEach(cell => {
                cell.hidden = hiddenVersions.has(cell.dataset.externalCodeVersion);
            });
            document.getElementById("externalCodeVersionsHeading").colSpan = Math.max(1, count);
            spanningCells.forEach(cell => { cell.colSpan = 3 + count; });
            document.getElementById("externalCodeVersionCount").textContent = count === checkboxes.length
                ? "Все версии" : "Версии: " + count + " из " + checkboxes.length;
            button.classList.toggle("btn-outline-primary", count < checkboxes.length);
            button.classList.toggle("btn-outline-secondary", count === checkboxes.length);
        }

        function updateSelection() {
            const found = checkboxes.filter(checkbox => !checkbox.closest("label").classList.contains("d-none"));
            const checked = found.filter(checkbox => checkbox.checked).length;
            selectAll.checked = found.length > 0 && checked === found.length;
            selectAll.indeterminate = checked > 0 && checked < found.length;
            selectAll.disabled = found.length === 0;
            document.getElementById("externalCodeVersionEmpty").classList.toggle("d-none", found.length > 0);
            error.classList.add("d-none");
        }

        function filterOptions() {
            const query = search.value.trim().toLocaleLowerCase("ru");
            checkboxes.forEach(checkbox => {
                const label = checkbox.closest("label");
                label.classList.toggle("d-none", !label.textContent.toLocaleLowerCase("ru").includes(query));
            });
            updateSelection();
        }

        function closeMenu(focusButton) {
            menu.classList.add("d-none");
            button.setAttribute("aria-expanded", "false");
            if (focusButton) button.focus();
        }

        function positionMenu() {
            const rect = button.getBoundingClientRect();
            const left = Math.max(8, Math.min(rect.right - menu.offsetWidth, window.innerWidth - menu.offsetWidth - 8));
            const top = Math.max(8, Math.min(rect.bottom + 4, window.innerHeight - menu.offsetHeight - 8));
            menu.style.left = left + "px";
            menu.style.top = top + "px";
        }

        // Keep the popup outside sticky table headers and scroll clipping.
        document.body.appendChild(menu);
        button.addEventListener("click", function () {
            if (!menu.classList.contains("d-none")) {
                closeMenu(false);
                return;
            }
            checkboxes.forEach(checkbox => { checkbox.checked = !hiddenVersions.has(checkbox.value); });
            search.value = "";
            filterOptions();
            menu.classList.remove("d-none");
            button.setAttribute("aria-expanded", "true");
            positionMenu();
            search.focus();
        });
        search.addEventListener("input", filterOptions);
        checkboxes.forEach(checkbox => checkbox.addEventListener("change", updateSelection));
        selectAll.addEventListener("change", function () {
            checkboxes.filter(checkbox => !checkbox.closest("label").classList.contains("d-none"))
                .forEach(checkbox => { checkbox.checked = selectAll.checked; });
            updateSelection();
        });
        document.getElementById("externalCodeVersionReset").addEventListener("click", function () {
            checkboxes.forEach(checkbox => { checkbox.checked = true; });
            search.value = "";
            filterOptions();
        });
        document.getElementById("externalCodeVersionCancel").addEventListener("click", () => closeMenu(true));
        document.getElementById("externalCodeVersionApply").addEventListener("click", function () {
            if (!checkboxes.some(checkbox => checkbox.checked)) {
                error.classList.remove("d-none");
                return;
            }
            hiddenVersions = new Set(checkboxes.filter(checkbox => !checkbox.checked).map(checkbox => checkbox.value));
            applyColumns();
            try {
                localStorage.setItem(storageKey, JSON.stringify(Array.from(hiddenVersions)));
            } catch (error) {
                console.warn("Не удалось сохранить выбор версий", error);
            }
            closeMenu(true);
        });
        document.addEventListener("click", function (event) {
            if (!menu.contains(event.target) && !button.contains(event.target)) closeMenu(false);
        });
        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && !menu.classList.contains("d-none")) closeMenu(true);
        });
        window.addEventListener("resize", function () {
            if (!menu.classList.contains("d-none")) positionMenu();
        });
        document.addEventListener("scroll", function (event) {
            if (!menu.classList.contains("d-none") && !menu.contains(event.target)) positionMenu();
        }, true);
        applyColumns();
    });
})();
