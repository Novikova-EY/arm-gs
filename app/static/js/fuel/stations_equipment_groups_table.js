/**
 * Сортировка и фильтрация таблицы groups оборудования электростанций.
 * Использует data-col-0 ... data-col-31 на строках с классом .data-row.
 */
(function () {
    "use strict";

    const COLUMN_COUNT = 32;

    function init() {
        const table = document.getElementById("stationsEquipmentGroupsTable");
        if (!table) return;

        const dataRows = Array.from(table.querySelectorAll("tbody tr.data-row"));
        if (!dataRows.length) return;

        const filterRow = table.querySelector("thead tr.sort-filter-row");
        if (!filterRow) return;

        const headerRow = filterRow.previousElementSibling;
        if (!headerRow) return;

        // Собираем уникальные значения по каждому столбцу
        const columnValues = Array.from({ length: COLUMN_COUNT }, () => new Set());
        dataRows.forEach(function (row) {
            for (let c = 0; c < COLUMN_COUNT; c++) {
                const val = (row.getAttribute("data-col-" + c) || "").trim();
                if (val) columnValues[c].add(val);
            }
        });

        // Заполняем выпадающие списки
        const filterSelects = filterRow.querySelectorAll("select.column-filter");
        filterSelects.forEach(function (select, idx) {
            const values = Array.from(columnValues[idx]).sort(collatorCompare);
            values.forEach(function (v) {
                const opt = document.createElement("option");
                opt.value = v;
                opt.textContent = v;
                select.appendChild(opt);
            });
        });

        // Инициализация Select2 для выпадающих списков (если доступен)
        if (typeof window.jQuery !== "undefined" && window.jQuery.fn.select2) {
            const $ = window.jQuery;
            filterSelects.forEach(function (sel) {
                $(sel).select2({
                    width: "100%",
                    allowClear: true,
                    placeholder: "Выбрать",
                });
            });
        }

        // Обработчик изменения фильтра
        filterSelects.forEach(function (select, colIdx) {
            select.addEventListener("change", function () {
                applyFilters(filterSelects, dataRows);
            });
        });

        // Сортировка по клику на заголовок
        const headerCells = headerRow.querySelectorAll("th");
        let sortCol = -1;
        let sortDir = 1; // 1 = asc, -1 = desc

        headerCells.forEach(function (th, idx) {
            th.style.cursor = "pointer";
            th.title = "Клик для сортировки по столбцу";
            th.addEventListener("click", function () {
                if (sortCol === idx) {
                    sortDir = -sortDir;
                } else {
                    sortCol = idx;
                    sortDir = 1;
                }
                sortTable(table, dataRows, sortCol, sortDir);
                updateSortIndicator(headerCells, sortCol, sortDir);
            });
        });

        // Скрываем групповые строки при фильтрации, если под ними нет видимых данных
        applyFilters(filterSelects, dataRows);
    }

    function collatorCompare(a, b) {
        return String(a).localeCompare(String(b), "ru", { sensitivity: "base" });
    }

    function getRowValue(row, colIdx) {
        return (row.getAttribute("data-col-" + colIdx) || "").trim();
    }

    function applyFilters(filterSelects, dataRows) {
        const filters = [];
        filterSelects.forEach(function (sel) {
            const v = (sel.value || "").trim();
            filters.push(v);
        });

        dataRows.forEach(function (row) {
            let visible = true;
            for (let c = 0; c < filters.length && visible; c++) {
                if (filters[c]) {
                    const rowVal = getRowValue(row, c);
                    visible = rowVal === filters[c];
                }
            }
            row.style.display = visible ? "" : "none";
        });

        // Скрываем групповые строки, если все дочерние данные скрыты
        hideEmptyGroupRows(dataRows);
    }

    function hideEmptyGroupRows(dataRows) {
        const tbody = dataRows[0] && dataRows[0].parentElement;
        if (!tbody) return;

        const allRows = Array.from(tbody.querySelectorAll("tr"));
        const groupRowClasses = ["table-light", "table-primary", "table-info", "table-secondary"];

        function getGroupLevel(r) {
            for (let i = 0; i < groupRowClasses.length; i++) {
                if (r.classList.contains(groupRowClasses[i])) return i;
            }
            return -1;
        }

        allRows.forEach(function (row) {
            const myLevel = getGroupLevel(row);
            if (myLevel < 0) return;

            // Ищем видимую data-row среди следующих строк до следующей групповой того же уровня
            let next = row.nextElementSibling;
            let hasVisibleChild = false;
            while (next) {
                const nextLevel = getGroupLevel(next);
                if (nextLevel >= 0 && nextLevel <= myLevel) break;
                if (next.classList.contains("data-row") && next.style.display !== "none") {
                    hasVisibleChild = true;
                    break;
                }
                next = next.nextElementSibling;
            }
            row.style.display = hasVisibleChild ? "" : "none";
        });
    }

    function sortTable(table, dataRows, sortCol, sortDir) {
        const tbody = table.querySelector("tbody");
        if (!tbody) return;

        const groupRowClasses = ["table-light", "table-primary", "table-info", "table-secondary"];

        const visibleDataRows = dataRows.filter(function (r) {
            return r.style.display !== "none";
        });

        const sorted = visibleDataRows.slice().sort(function (a, b) {
            const va = getRowValue(a, sortCol);
            const vb = getRowValue(b, sortCol);
            const cmp = collatorCompare(va, vb);
            return sortDir * cmp;
        });

        // Скрываем групповые строки при сортировке
        const allRows = Array.from(tbody.querySelectorAll("tr"));
        allRows.forEach(function (row) {
            if (groupRowClasses.some(function (c) {
                return row.classList.contains(c);
            })) {
                row.style.display = "none";
            }
        });

        // Перемещаем data-rows в отсортированном порядке
        sorted.forEach(function (row) {
            tbody.appendChild(row);
        });
    }

    function updateSortIndicator(headerCells, sortCol, sortDir) {
        headerCells.forEach(function (th, idx) {
            th.style.position = "relative";
            th.querySelectorAll(".sort-indicator").forEach(function (el) {
                el.remove();
            });
            if (idx === sortCol) {
                const span = document.createElement("span");
                span.className = "sort-indicator ms-1";
                span.textContent = sortDir > 0 ? "▲" : "▼";
                span.style.fontSize = "0.7em";
                span.style.opacity = "0.7";
                th.appendChild(span);
            }
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
