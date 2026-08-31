/**
 * Толстая граница между блоками сущностей на сводках потребления
 * (как applyPdEntityLevelBorders на /power_demand/summary/oes/).
 */
(function () {
    "use strict";

    function rowIsVisible(tr) {
        return (
            !tr.classList.contains("summary-row-hidden") &&
            !tr.classList.contains("summary-row-empty-block-hidden")
        );
    }

    function isSpuriousVerifyBlockStart(tr) {
        return tr.classList.contains("pd-ec-verify-for-row");
    }

    function isNextEntityBlockStart(tr, startTr) {
        return (
            !!tr &&
            tr !== startTr &&
            tr.classList.contains("summary-row-param") &&
            tr.getAttribute("data-is-block-start") === "1" &&
            !isSpuriousVerifyBlockStart(tr)
        );
    }

    function collectEntityBlockRows(startTr) {
        var blockRows = [];
        var tr = startTr;
        while (tr) {
            if (tr.classList.contains("summary-row-param")) {
                if (isNextEntityBlockStart(tr, startTr)) {
                    break;
                }
                blockRows.push(tr);
            }
            tr = tr.nextElementSibling;
        }
        return blockRows;
    }

    function applyEcEntityLevelBorders() {
        var summaryTable = document.getElementById("powerDemandSummaryTable");
        if (!summaryTable) {
            return;
        }
        var tbody = summaryTable.querySelector("tbody");
        if (!tbody) {
            return;
        }
        Array.prototype.forEach.call(
            tbody.querySelectorAll("tr.pd-summary-entity-block-first"),
            function (tr) {
                tr.classList.remove("pd-summary-entity-block-first");
            }
        );

        var blocks = [];
        var startRows = tbody.querySelectorAll(
            'tr.summary-row-param[data-is-block-start="1"]'
        );
        Array.prototype.forEach.call(startRows, function (startTr) {
            if (isSpuriousVerifyBlockStart(startTr)) {
                return;
            }
            var blockRows = collectEntityBlockRows(startTr);
            if (!blockRows.length) {
                return;
            }
            var visibleRows = blockRows.filter(rowIsVisible);
            if (!visibleRows.length) {
                return;
            }
            blocks.push({ visibleRows: visibleRows });
        });

        for (var i = 1; i < blocks.length; i++) {
            blocks[i].visibleRows[0].classList.add("pd-summary-entity-block-first");
        }
    }

    window.__pdEcSummaryApplyEntityLevelBorders = applyEcEntityLevelBorders;

    document.addEventListener("DOMContentLoaded", function () {
        applyEcEntityLevelBorders();
    });
    document.addEventListener("pd-summary-rows-rendered", applyEcEntityLevelBorders);
    document.addEventListener("ec-summary-rows-rendered", applyEcEntityLevelBorders);
})();
