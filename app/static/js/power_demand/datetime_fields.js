(function () {
    "use strict";

    function twoLineDatetime(text) {
        return text.replace(/^\s*(\d{1,2}\.\d{1,2}(?:\.\d{2,4})?)\s+(\d{1,2}:\d{2}(?::\d{2})?)\s*$/, "$1\n$2");
    }

    function init() {
        const tables = document.querySelectorAll("#powerDemandSummaryTable, #power-demand-edit-table, #ozpMaximaTable");
        if (!tables.length) return;

        const selector = 'tbody td > textarea:is([data-parameter-key="peak_datetime"], [name="dt[]"])';
        const displaySelector = 'tr[data-parameter-key="peak_datetime"] > td:is(.summary-year-cell, .summary-hist-cell):not(.summary-year-k-cell), .power-demand-view-datetime-cell';
        let scheduled = false;

        function syncHeights() {
            scheduled = false;
            const fields = Array.from(tables).flatMap(table => Array.from(table.querySelectorAll(selector)));
            tables.forEach(table => {
                table.querySelectorAll(displaySelector).forEach(cell => {
                    if (cell.childElementCount) return;
                    const text = twoLineDatetime(cell.textContent.trim());
                    if (cell.textContent !== text) cell.textContent = text;
                });
            });
            fields.forEach(field => {
                const text = twoLineDatetime(field.value);
                if (field.value !== text) {
                    const start = field.selectionStart, end = field.selectionEnd, direction = field.selectionDirection;
                    field.value = text;
                    if (field === document.activeElement) field.setSelectionRange(start, end, direction);
                }
                // Формат отображения не должен создавать несохраненные изменения.
                if (field.hasAttribute("data-initial")) {
                    const initial = twoLineDatetime(field.dataset.initial);
                    if (field.dataset.initial !== initial) field.dataset.initial = initial;
                }
                field.style.removeProperty("--pd-datetime-height");
                field.style.paddingTop = "";
                field.style.paddingBottom = "";
            });
            // Сначала измеряем естественную высоту всех строк, затем растягиваем поля.
            const measurements = fields.map(field => {
                const style = getComputedStyle(field);
                const height = field.closest("td").clientHeight;
                const extra = Math.max(0, height - field.offsetHeight) / 2;
                return {
                    height: height,
                    paddingTop: parseFloat(style.paddingTop) + extra,
                    paddingBottom: parseFloat(style.paddingBottom) + extra
                };
            });
            fields.forEach((field, index) => {
                const size = measurements[index];
                if (size.height) {
                    field.style.setProperty("--pd-datetime-height", size.height + "px");
                    field.style.paddingTop = size.paddingTop + "px";
                    field.style.paddingBottom = size.paddingBottom + "px";
                }
            });
        }

        function schedule() {
            if (!scheduled) {
                scheduled = true;
                requestAnimationFrame(syncHeights);
            }
        }

        const resizeObserver = new ResizeObserver(schedule);
        const mutationObserver = new MutationObserver(records => {
            if (records.some(record => record.type === "childList" || record.attributeName === "data-initial" || record.target.matches("tr, table"))) {
                schedule();
            }
        });
        tables.forEach(table => {
            resizeObserver.observe(table);
            mutationObserver.observe(table, {
                childList: true, subtree: true, attributes: true, attributeFilter: ["class", "hidden", "data-initial"]
            });
            ["input", "change", "focusout"].forEach(event => table.addEventListener(event, schedule));
        });
        window.addEventListener("resize", schedule);
        schedule();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
}());
