(function () {
    "use strict";

    const table = document.getElementById("fuel-review-table");
    if (!table) return;

    const emptyRow = document.getElementById("fuel-review-empty");
    const status = document.getElementById("fuel-review-filter-status");
    const rows = Array.from(table.tBodies[0].rows).filter(row => row !== emptyRow);
    const filters = [];
    let closeActive = null;

    function applyFilters() {
        let visible = 0;
        rows.forEach(row => {
            row.hidden = !filters.every(filter =>
                filter.selected.has(row.cells[filter.column].textContent.trim())
            );
            if (!row.hidden) visible += 1;
        });
        emptyRow.hidden = visible !== 0;
        status.hidden = false;
        status.textContent = `Показано строк: ${visible} из ${rows.length}. Фильтры не меняют состав пакета для акцепта.`;
    }

    table.querySelectorAll(".fuel-review-filter").forEach((button, index) => {
        const column = Number(button.dataset.column);
        const values = Array.from(new Set(rows.map(row => row.cells[column].textContent.trim())))
            .sort((a, b) => a.localeCompare(b, "ru"));
        const filter = {column, selected: new Set(values)};
        filters.push(filter);

        const menu = document.getElementById("fuel-review-filter-template").content.firstElementChild.cloneNode(true);
        menu.id = `fuel-review-filter-${index}`;
        menu.setAttribute("aria-label", `Фильтр: ${button.dataset.label}`);
        menu.querySelector("[data-filter-title]").textContent = button.dataset.label;
        button.setAttribute("aria-controls", menu.id);
        const search = menu.querySelector('input[type="search"]');
        const selectAll = menu.querySelector("[data-filter-all]");
        const list = menu.querySelector(".fuel-review-filter-values");
        const noValues = menu.querySelector("[data-filter-no-values]");
        const options = values.map(value => {
            const label = document.createElement("label");
            label.className = "d-flex align-items-center gap-2";
            const checkbox = document.createElement("input");
            checkbox.type = "checkbox";
            label.append(checkbox, document.createTextNode(value || "(Пустые)"));
            list.appendChild(label);
            checkbox.addEventListener("change", updateSelectAll);
            return {value, label, checkbox};
        });
        document.body.appendChild(menu);
        button.hidden = false;

        function updateSelectAll() {
            const shown = options.filter(option => !option.label.hidden);
            const checked = shown.filter(option => option.checkbox.checked).length;
            selectAll.checked = shown.length > 0 && checked === shown.length;
            selectAll.indeterminate = checked > 0 && checked < shown.length;
            selectAll.disabled = shown.length === 0;
            noValues.hidden = shown.length !== 0;
        }

        function close(restoreFocus = false) {
            menu.hidden = true;
            button.setAttribute("aria-expanded", "false");
            if (closeActive === close) closeActive = null;
            if (restoreFocus) button.focus();
        }

        function placeMenu() {
            const rect = button.getBoundingClientRect();
            const width = menu.offsetWidth;
            const height = menu.offsetHeight;
            menu.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - width - 8))}px`;
            menu.style.top = `${Math.max(8, Math.min(rect.bottom + 4, window.innerHeight - height - 8))}px`;
        }

        button.addEventListener("click", () => {
            if (!menu.hidden) {
                close();
                return;
            }
            if (closeActive) closeActive();
            search.value = "";
            options.forEach(option => {
                option.checkbox.checked = filter.selected.has(option.value);
                option.label.hidden = false;
            });
            updateSelectAll();
            menu.hidden = false;
            closeActive = close;
            button.setAttribute("aria-expanded", "true");
            placeMenu();
            search.focus({preventScroll: true});
        });
        search.addEventListener("input", () => {
            const query = search.value.trim().toLocaleLowerCase("ru");
            options.forEach(option => {
                option.label.hidden = !option.value.toLocaleLowerCase("ru").includes(query);
            });
            updateSelectAll();
            placeMenu();
        });
        selectAll.addEventListener("change", () => {
            options.filter(option => !option.label.hidden).forEach(option => {
                option.checkbox.checked = selectAll.checked;
            });
            updateSelectAll();
        });

        function commitSelection() {
            const active = filter.selected.size !== values.length;
            button.querySelector("span").textContent = active ? `Выбрано: ${filter.selected.size}` : "Все";
            button.classList.toggle("btn-outline-primary", active);
            button.classList.toggle("btn-outline-secondary", !active);
            button.querySelector("i").className = active ? "bi bi-funnel-fill" : "bi bi-funnel";
            applyFilters();
            close(true);
        }

        menu.querySelector("[data-filter-apply]").addEventListener("click", () => {
            filter.selected = new Set(options.filter(option => option.checkbox.checked).map(option => option.value));
            commitSelection();
        });
        menu.querySelector("[data-filter-reset]").addEventListener("click", () => {
            filter.selected = new Set(values);
            commitSelection();
        });
        menu.addEventListener("keydown", event => {
            if (event.key === "Escape") {
                event.preventDefault();
                close(true);
            }
        });
        document.addEventListener("click", event => {
            if (!menu.hidden && !menu.contains(event.target) && !button.contains(event.target)) close();
        });
        document.addEventListener("focusin", event => {
            if (!menu.hidden && !menu.contains(event.target) && !button.contains(event.target)) close();
        });
        window.addEventListener("resize", () => close());
        window.addEventListener("scroll", event => {
            if (!menu.hidden && !menu.contains(event.target)) placeMenu();
        }, true);
    });
})();
