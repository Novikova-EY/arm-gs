/**
 * Совместимость: реализация в js/common/table_row_paste.js (подключается из base.html).
 */
(function () {
    "use strict";
    if (typeof window.initProspectivePlaceForecastRowPaste === "function") {
        return;
    }
    window.initProspectivePlaceForecastRowPaste = function (table) {
        if (typeof window.initPowerDemandSummaryRowPaste === "function") {
            window.initPowerDemandSummaryRowPaste(table);
        }
    };
})();
