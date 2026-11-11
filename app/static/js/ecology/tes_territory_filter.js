(function () {
    "use strict";

    function initFilter(kind, menuId) {
        const buttons = Array.from(document.querySelectorAll(`[data-${kind}-filter-button]`));
        const menu = document.getElementById(menuId);
        if (!buttons.length || !menu) return;

        // Keep the popup outside the scrolling table and its sticky header.
        document.body.appendChild(menu);
        const filterRows = kind === "fuel";
        const fuelRows = filterRows ? buttons.flatMap(button =>
            Array.from(button.closest("table").querySelectorAll("tbody tr[data-row-key]"))
        ) : [];
        if (filterRows) {
            const list = menu.querySelector("[data-fuel-values]");
            const seen = new Set();
            fuelRows.forEach(row => {
                const key = row.dataset.rowKey;
                if (seen.has(key)) return;
                seen.add(key);
                const label = document.createElement("label");
                label.className = "d-flex align-items-center gap-2";
                const option = document.createElement("input");
                option.type = "checkbox";
                option.value = key;
                option.checked = true;
                option.setAttribute("data-fuel-option", "");
                label.append(option, document.createTextNode(row.cells[0].textContent.trim()));
                list.appendChild(label);
            });
        }
        const options = Array.from(menu.querySelectorAll(`[data-${kind}-option]`));
        const selectAll = menu.querySelector(`[data-${kind}-all]`);
        const search = menu.querySelector(`[data-${kind}-search]`);
        const storageKey = menu.dataset.storageKey;
        let selected = new Set(options.map(option => option.value));
        let activeButton = buttons[0];
        if (storageKey) {
            try {
                const saved = JSON.parse(window.localStorage.getItem(storageKey));
                if (Array.isArray(saved) && saved.every(slug => typeof slug === "string")) {
                    selected = new Set(options.filter(option => saved.includes(option.value)).map(option => option.value));
                }
            } catch (error) {
                if (!(error instanceof SyntaxError) && error.name !== "SecurityError") throw error;
                console.warn("Не удалось восстановить фильтр столбцов.", error);
            }
        }
        const tables = filterRows ? [] : buttons.map(button => {
            const table = button.closest("table");
            const columns = Array.from(table.querySelectorAll("colgroup col"));
            let start = 1;
            const groups = Array.from(table.tHead.rows[0].cells).slice(1).map((header, index) => {
                const group = {slug: options[index].value, start, end: start + header.colSpan};
                start = group.end;
                return group;
            });
            // Preserve the original grid, including headers spanning several rows.
            const occupied = [];
            const cells = Array.from(table.rows).flatMap((row, rowIndex) => {
                let column = 0;
                return Array.from(row.cells).map(cell => {
                    while (occupied[column] > rowIndex) column += 1;
                    const start = column;
                    const span = cell.colSpan;
                    for (let offset = 0; offset < span; offset += 1) {
                        occupied[column + offset] = rowIndex + cell.rowSpan;
                    }
                    column += span;
                    return {cell, start, span};
                });
            });
            return {table, columns, groups, cells};
        });

        function matchingOptions() {
            return options.filter(option => !option.parentElement.hidden);
        }

        function updateSelectAll() {
            const visible = search ? matchingOptions() : options;
            const count = visible.filter(option => option.checked).length;
            selectAll.checked = visible.length > 0 && count === visible.length;
            selectAll.indeterminate = count > 0 && count < visible.length;
        }

        function searchOptions() {
            const query = search.value.trim().toLocaleLowerCase("ru");
            options.forEach(option => {
                option.parentElement.hidden = !option.parentElement.textContent.toLocaleLowerCase("ru").includes(query);
            });
            updateSelectAll();
        }
        if (search) search.addEventListener("input", searchOptions);

        function close(restoreFocus = false) {
            menu.hidden = true;
            buttons.forEach(button => button.setAttribute("aria-expanded", "false"));
            if (restoreFocus) activeButton.focus({preventScroll: true});
        }

        function placeMenu() {
            const rect = activeButton.getBoundingClientRect();
            menu.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - menu.offsetWidth - 8))}px`;
            menu.style.top = `${Math.max(8, Math.min(rect.bottom + 4, window.innerHeight - menu.offsetHeight - 8))}px`;
        }

        function apply() {
            // Row filtering must not overwrite cell visibility set by the column filter.
            fuelRows.forEach(row => { row.hidden = !selected.has(row.dataset.rowKey); });
            tables.forEach(({table, columns, groups, cells}) => {
                const hidden = new Set();
                groups.forEach(group => {
                    if (!selected.has(group.slug)) {
                        for (let column = group.start; column < group.end; column += 1) hidden.add(column);
                    }
                });
                columns.forEach((column, index) => { column.hidden = hidden.has(index); });
                cells.forEach(({cell, start, span}) => {
                    let visible = 0;
                    for (let column = start; column < start + span; column += 1) {
                        if (!hidden.has(column)) visible += 1;
                    }
                    cell.hidden = visible === 0;
                    cell.colSpan = visible || span;
                });
                if (table.classList.contains("ot-new-tes-volumes-table")) {
                    table.style.minWidth = `${15 + (columns.length - 1 - hidden.size) * 8.5}rem`;
                }
            });
            const active = selected.size !== options.length;
            buttons.forEach(button => {
                button.classList.toggle("btn-outline-primary", active);
                button.classList.toggle("btn-outline-secondary", !active);
                button.querySelector("i").className = active ? "bi bi-funnel-fill" : "bi bi-funnel";
                button.querySelector("span").textContent = active ? `Выбрано: ${selected.size}` : (filterRows ? "Все виды топлива" : "Все столбцы");
            });
            window.dispatchEvent(new Event("resize"));
        }

        function commit() {
            if (storageKey) {
                try {
                    if (selected.size === options.length) window.localStorage.removeItem(storageKey);
                    else window.localStorage.setItem(storageKey, JSON.stringify(Array.from(selected)));
                } catch (error) {
                    if (!["SecurityError", "QuotaExceededError"].includes(error.name)) throw error;
                    console.warn("Не удалось сохранить фильтр столбцов.", error);
                }
            }
            apply();
            close(true);
        }

        buttons.forEach(button => {
            button.hidden = false;
            button.addEventListener("click", () => {
                if (!menu.hidden && activeButton === button) {
                    close();
                    return;
                }
                close();
                activeButton = button;
                options.forEach(option => { option.checked = selected.has(option.value); });
                if (search) {
                    search.value = "";
                    searchOptions();
                }
                updateSelectAll();
                menu.hidden = false;
                button.setAttribute("aria-expanded", "true");
                placeMenu();
                (search || selectAll).focus({preventScroll: true});
            });
        });
        options.forEach(option => option.addEventListener("change", updateSelectAll));
        selectAll.addEventListener("change", () => {
            (search ? matchingOptions() : options).forEach(option => { option.checked = selectAll.checked; });
            updateSelectAll();
        });
        menu.querySelector(`[data-${kind}-apply]`).addEventListener("click", () => {
            selected = new Set(options.filter(option => option.checked).map(option => option.value));
            commit();
        });
        menu.querySelector(`[data-${kind}-reset]`).addEventListener("click", () => {
            selected = new Set(options.map(option => option.value));
            commit();
        });
        document.addEventListener("keydown", event => {
            if (event.key === "Escape" && !menu.hidden) {
                event.preventDefault();
                close(true);
            }
        });
        document.addEventListener("click", event => {
            if (!menu.hidden && !menu.contains(event.target) && !activeButton.contains(event.target)) close();
        });
        document.addEventListener("focusin", event => {
            if (!menu.hidden && !menu.contains(event.target) && !activeButton.contains(event.target)) close();
        });
        window.addEventListener("resize", () => close());
        window.addEventListener("scroll", event => {
            if (!menu.hidden && !menu.contains(event.target)) placeMenu();
        }, true);
        apply();
    }

    initFilter("territory", "otTerritoryFilterMenu");
    initFilter("fuel", "otFuelFilterMenu");
})();
