(function () {
    "use strict";

    const buttons = Array.from(document.querySelectorAll("[data-territory-filter-button]"));
    const menu = document.getElementById("otTerritoryFilterMenu");
    if (!buttons.length || !menu) return;

    // Keep the popup outside the scrolling table and its sticky header.
    document.body.appendChild(menu);
    const options = Array.from(menu.querySelectorAll("[data-territory-option]"));
    const selectAll = menu.querySelector("[data-territory-all]");
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
    const tables = buttons.map(button => {
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

    function updateSelectAll() {
        const count = options.filter(option => option.checked).length;
        selectAll.checked = count === options.length;
        selectAll.indeterminate = count > 0 && count < options.length;
    }

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
            button.querySelector("span").textContent = active ? `Выбрано: ${selected.size}` : "Все столбцы";
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
            updateSelectAll();
            menu.hidden = false;
            button.setAttribute("aria-expanded", "true");
            placeMenu();
            selectAll.focus({preventScroll: true});
        });
    });
    options.forEach(option => option.addEventListener("change", updateSelectAll));
    selectAll.addEventListener("change", () => {
        options.forEach(option => { option.checked = selectAll.checked; });
        updateSelectAll();
    });
    menu.querySelector("[data-territory-apply]").addEventListener("click", () => {
        selected = new Set(options.filter(option => option.checked).map(option => option.value));
        commit();
    });
    menu.querySelector("[data-territory-reset]").addEventListener("click", () => {
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
})();
