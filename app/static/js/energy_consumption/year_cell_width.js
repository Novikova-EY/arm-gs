(function () {
    "use strict";

    const fieldSelector = [
        '#powerDemandSummaryTable td:is(.summary-year-cell, .summary-hist-cell) input:not([type="hidden"])',
        '#powerDemandSummaryTable td:is(.summary-year-cell, .summary-hist-cell) textarea',
        '#power-demand-edit-table input[name="ec_mln[]"]',
        '#power-demand-edit-table input[name="ec_sipr[]"]'
    ].join(",");
    const measure = document.createElement("canvas").getContext("2d");
    const pending = new Set();
    let frame = 0;

    function horizontalSpace(style) {
        return ["paddingLeft", "paddingRight", "borderLeftWidth", "borderRightWidth"]
            .reduce(function (sum, name) { return sum + (parseFloat(style[name]) || 0); }, 0);
    }

    function resize() {
        frame = 0;
        const widths = new Map();
        pending.forEach(function (field) {
            if (!field.isConnected) return;
            const cell = field.closest("td");
            const style = getComputedStyle(field);
            const value = field.value.replace(/[\r\n]+/g, " ");
            measure.font = style.font;
            const spacing = (parseFloat(style.letterSpacing) || 0) * value.length;
            const width = Math.ceil(measure.measureText(value).width + spacing
                + horizontalSpace(style) + horizontalSpace(getComputedStyle(cell)) + 4);
            widths.set(cell, Math.max(width, widths.get(cell) || 0));
        });
        pending.clear();
        widths.forEach(function (width, cell) {
            // Абсолютно позиционированные поля не участвуют в расчете ширины столбца.
            cell.style.setProperty("--ec-year-field-width", width + "px");
        });
    }

    function collect(root) {
        if (root.nodeType !== Node.ELEMENT_NODE) return;
        if (root.matches(fieldSelector)) pending.add(root);
        root.querySelectorAll(fieldSelector).forEach(function (field) { pending.add(field); });
        if (pending.size && !frame) frame = requestAnimationFrame(resize);
    }

    document.querySelectorAll("#powerDemandSummaryTable, #power-demand-edit-table").forEach(function (table) {
        collect(table);
        ["input", "change"].forEach(function (name) {
            table.addEventListener(name, function (event) { collect(event.target); });
        });
        new MutationObserver(function (records) {
            records.forEach(function (record) {
                if (record.type === "attributes") collect(record.target);
                else record.addedNodes.forEach(collect);
            });
        }).observe(table, { subtree: true, childList: true, attributes: true, attributeFilter: ["value", "data-initial"] });
        document.fonts.ready.then(function () { collect(table); });
    });
})();
