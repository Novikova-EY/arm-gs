const powerDemandSummaryLoaderShell = document.getElementById("powerDemandSummaryLoaderShell");
const powerDemandSummaryLoadingOverlay = document.getElementById("powerDemandSummaryLoadingOverlay");
const powerDemandSummaryScrollWrap = document.getElementById("powerDemandSummaryScrollWrap");

function refreshPowerDemandSummaryLayout() {
    if (typeof window.armGsUpdatePdSummaryControlsStickyHeight === "function") {
        window.armGsUpdatePdSummaryControlsStickyHeight();
    }
    if (typeof window.armGsUpdatePdCoeffTableHostMaxHeight === "function") {
        window.armGsUpdatePdCoeffTableHostMaxHeight();
    }
    if (typeof window.armGsApplyStickyTheadOffsets === "function") {
        window.armGsApplyStickyTheadOffsets();
    }
    if (typeof window.armGsUpdateHorizontalScrollFlags === "function") {
        window.armGsUpdateHorizontalScrollFlags();
    }
    if (typeof window.__pdCoeffClipStickyLeadHeaders === "function") {
        window.__pdCoeffClipStickyLeadHeaders();
    }
}

/**
 * Chrome рисует sticky-top period/year th поверх sticky-left шапки в одной строке.
 * Обрезаем левый край «наезжающих» th по границе столбца «Наименование параметров».
 */
window.__pdCoeffClipStickyLeadHeaders = function pdCoeffClipStickyLeadHeaders() {
    var wrap = powerDemandSummaryScrollWrap;
    var table = document.getElementById("powerDemandSummaryTable");
    if (!wrap || !table || !table.classList.contains("pd-coeff-year-seg-table")) {
        return;
    }
    var param =
        table.querySelector("thead th.summary-parameter-col.pd-coeff-sticky-head-label") ||
        table.querySelector("thead th.summary-parameter-col");
    if (!param) {
        return;
    }
    var wrapRect = wrap.getBoundingClientRect();
    var edge = param.getBoundingClientRect().right - wrapRect.left;
    if (!(edge > 0)) {
        return;
    }
    var sel =
        "thead th.power-demand-coeff-period-th, " +
        "thead th.power-demand-coeff-mixin-group-th, " +
        "thead th.summary-year-col, " +
        "thead th.power-demand-coeff-mixin-th";
    table.querySelectorAll(sel).forEach(function (th) {
        var r = th.getBoundingClientRect();
        var thLeft = r.left - wrapRect.left;
        var cut = edge - thLeft;
        if (cut <= 0.5) {
            th.style.clipPath = "";
            return;
        }
        if (cut >= r.width - 0.5) {
            th.style.clipPath = "inset(0 0 0 100%)";
            return;
        }
        th.style.clipPath = "inset(0 0 0 " + Math.ceil(cut) + "px)";
    });
};

if (powerDemandSummaryScrollWrap) {
    powerDemandSummaryScrollWrap.addEventListener(
        "scroll",
        function () {
            if (typeof window.__pdCoeffClipStickyLeadHeaders === "function") {
                window.__pdCoeffClipStickyLeadHeaders();
            }
        },
        { passive: true }
    );
}
window.addEventListener("resize", function () {
    if (typeof window.__pdCoeffClipStickyLeadHeaders === "function") {
        window.__pdCoeffClipStickyLeadHeaders();
    }
});

function finishPowerDemandSummaryInitialRenderNow() {
    if (!powerDemandSummaryLoaderShell || powerDemandSummaryLoaderShell.dataset.ready === "1") {
        return;
    }
    powerDemandSummaryLoaderShell.dataset.ready = "1";
    window.requestAnimationFrame(function () {
        window.requestAnimationFrame(function () {
            if (powerDemandSummaryScrollWrap) {
                powerDemandSummaryScrollWrap.style.visibility = "";
            }
            if (powerDemandSummaryLoadingOverlay) {
                powerDemandSummaryLoadingOverlay.style.display = "none";
            }
            powerDemandSummaryLoaderShell.setAttribute("aria-busy", "false");
            if (typeof window.__pdPdSummarySyncNoteFieldHeights === "function") {
                window.__pdPdSummarySyncNoteFieldHeights();
            }
            if (typeof window.__pdPdSummarySyncPerimeterVariantLabels === "function") {
                window.__pdPdSummarySyncPerimeterVariantLabels();
            }
            if (typeof window.__pdPdSummaryInitTableTooltips === "function") {
                window.__pdPdSummaryInitTableTooltips();
            }
            refreshPowerDemandSummaryLayout();
            window.requestAnimationFrame(function () {
                refreshPowerDemandSummaryLayout();
                if (window.armGsPageScrollRestore) {
                    var pdSummaryTable = document.getElementById("powerDemandSummaryTable");
                    if (pdSummaryTable) {
                        var pdVScrollEl =
                            (powerDemandSummaryScrollWrap
                                && powerDemandSummaryScrollWrap.classList.contains(
                                    "pd-coeff-summary-scroll-wrap"
                                ))
                                ? powerDemandSummaryScrollWrap
                                : document.querySelector(".page-table-scroll");
                        window.armGsPageScrollRestore.restore(
                            window.armGsPageScrollRestore.defaultScope(pdSummaryTable),
                            {
                                table: pdSummaryTable,
                                hScrollEl: powerDemandSummaryScrollWrap,
                                vScrollEl: pdVScrollEl || undefined,
                                // Не consume здесь: optional-сегменты и финальная
                                // видимость ещё могут сдвинуть layout (см. pd-summary-ui-settled).
                                consume: false
                            }
                        );
                    }
                }
                document.dispatchEvent(new CustomEvent("pd-summary-initial-render-finished"));
            });
        });
    });
}

var _pdSummaryFinishScheduled = false;
function finishPowerDemandSummaryInitialRender() {
    if (!powerDemandSummaryLoaderShell || powerDemandSummaryLoaderShell.dataset.ready === "1") {
        return;
    }
    if (_pdSummaryFinishScheduled) {
        return;
    }
    _pdSummaryFinishScheduled = true;
    if (window.__pdSummaryRowsReady && typeof window.__pdSummaryRowsReady.then === "function") {
        window.__pdSummaryRowsReady.then(
            function () {
                finishPowerDemandSummaryInitialRenderNow();
            },
            function () {
                finishPowerDemandSummaryInitialRenderNow();
            }
        );
        return;
    }
    finishPowerDemandSummaryInitialRenderNow();
}

window.__pdPdSummaryFinishInitialRender = finishPowerDemandSummaryInitialRender;

(async function () {
    if (typeof window.__pdPdSummaryFinishInitialRender === "function") {
        window.__pdPdSummaryFinishInitialRender();
    }
    if (window.__pdSummaryRowsReady && typeof window.__pdSummaryRowsReady.then === "function") {
        try {
            await window.__pdSummaryRowsReady;
        } catch (ePdSummaryRowsReady) {
            /* сообщение об ошибке уже в tbody */
        }
    }

const summaryTable = document.getElementById("powerDemandSummaryTable");
if (summaryTable) {
    if (typeof window.pdSummaryAggregationLevelColspan !== "function") {
        window.pdSummaryAggregationLevelColspan = function (yearCount) {
            var n = 3 + (yearCount || 0);
            if (window.__pdPdSummaryPerimeterVariantMode === true) {
                n += 1;
            }
            if (window.__pdPdSummaryHistMode === true) {
                n += 1;
            }
            return n;
        };
    }
    if (typeof window.pdSummarySyncAggregationLevelColspans !== "function") {
        window.pdSummaryCountSummaryYearColumns = function () {
            var table = document.getElementById("powerDemandSummaryTable");
            if (!table) {
                return 0;
            }
            var yearHeaders = table.querySelectorAll("thead th.summary-year-col");
            if (yearHeaders.length) {
                return yearHeaders.length;
            }
            return table.querySelectorAll("colgroup col.summary-col-year").length;
        };
        window.pdSummarySyncAggregationLevelColspans = function () {
            var table = document.getElementById("powerDemandSummaryTable");
            if (!table) {
                return;
            }
            var yearCount = window.pdSummaryCountSummaryYearColumns();
            var colspan = window.pdSummaryAggregationLevelColspan(yearCount);
            table
                .querySelectorAll(
                    'tbody tr[data-pd-pd-aggregation-level="1"] > td[data-pd-aggregation-header-cell="1"]'
                )
                .forEach(function (td) {
                    td.colSpan = colspan;
                });
        };
    }

    const FILTER_STORAGE_KEY = "powerDemandSummaryRowFilter";
    var pdPdNtStorageKey =
        "pdPdSummaryNtDetail_" + (summaryTable.getAttribute("data-summary-view") || "oes");
    try {
        window.__pdPdSummaryNtDetailMode = sessionStorage.getItem(pdPdNtStorageKey) === "1";
    } catch (ePdPdNtInit) {
        window.__pdPdSummaryNtDetailMode = false;
    }

    var pdPdSummaryViewKey = summaryTable.getAttribute("data-summary-view") || "oes";
    var pdPdTerritoryCompactKey = "pdPdSummaryTerritoryCompact_" + pdPdSummaryViewKey;
    var pdPdPaginationBeforeCompactKey =
        "pdPdSummaryPaginationBeforeCompact_" + pdPdSummaryViewKey;
    var pdPdTerritoryCompactBtn = document.getElementById("pdPdSummaryTerritoryCompactToggle");
    function syncPdPdTerritoryCompactToggleUi() {
        if (!pdPdTerritoryCompactBtn) {
            return;
        }
        var on = window.__pdPdSummaryTerritoryCompactMode === true;
        pdPdTerritoryCompactBtn.setAttribute("aria-pressed", on ? "true" : "false");
        pdPdTerritoryCompactBtn.classList.toggle("btn-success", on);
        pdPdTerritoryCompactBtn.classList.toggle("btn-outline-success", !on);
    }
    function pdSummaryServerEntityPaginationPageSizeFromUrl() {
        var params = new URLSearchParams(window.location.search || "");
        var raw = params.get("pd_page_size");
        if (raw === null || String(raw).trim() === "") {
            return 2;
        }
        var n = parseInt(raw, 10);
        if (isNaN(n) || n < 0) {
            return 2;
        }
        return n;
    }
    function pdSummaryServerEntityPaginationUrlIsPaginated() {
        return pdSummaryServerEntityPaginationPageSizeFromUrl() > 0;
    }
    function pdSummarySavePaginationBeforeCompact() {
        try {
            var params = new URLSearchParams(window.location.search || "");
            var prevSize = pdSummaryServerEntityPaginationPageSizeFromUrl();
            var prevPage = parseInt(params.get("pd_page") || "1", 10);
            if (prevSize > 0) {
                var saved = {
                    page: isNaN(prevPage) || prevPage < 1 ? 1 : prevPage,
                    pageSize: prevSize,
                };
                window.__pdPdSummaryPaginationBeforeCompact = saved;
                sessionStorage.setItem(
                    pdPdPaginationBeforeCompactKey,
                    JSON.stringify(saved)
                );
            }
        } catch (ePagSave) { /* */ }
    }
    function pdSummaryReadPaginationBeforeCompact() {
        var saved = window.__pdPdSummaryPaginationBeforeCompact || null;
        window.__pdPdSummaryPaginationBeforeCompact = null;
        if (saved && saved.pageSize > 0) {
            try {
                sessionStorage.removeItem(pdPdPaginationBeforeCompactKey);
            } catch (ePagClrMem) { /* */ }
            return saved;
        }
        try {
            var raw = sessionStorage.getItem(pdPdPaginationBeforeCompactKey);
            sessionStorage.removeItem(pdPdPaginationBeforeCompactKey);
            if (!raw) {
                return null;
            }
            saved = JSON.parse(raw);
            if (saved && saved.pageSize > 0) {
                return saved;
            }
        } catch (ePagRead) { /* */ }
        return null;
    }
    function pdSummaryNavigateServerEntityPagination(page, pageSize) {
        // Не тащить позицию после save на другую страницу пагинации.
        if (window.armGsPageScrollRestore) {
            try {
                var navTable = document.getElementById("powerDemandSummaryTable");
                window.armGsPageScrollRestore.clear(
                    window.armGsPageScrollRestore.defaultScope(navTable)
                );
            } catch (eNavClr) { /* */ }
        }
        var params = new URLSearchParams(window.location.search || "");
        if (pageSize > 0) {
            params.set("pd_page_size", String(pageSize));
            params.set("pd_page", String(Math.max(1, page || 1)));
        } else {
            params.set("pd_page_size", "0");
            params.delete("pd_page");
        }
        var qs = params.toString();
        window.location.assign(
            qs ? window.location.pathname + "?" + qs : window.location.pathname
        );
    }
    if (pdPdTerritoryCompactBtn) {
        try {
            window.__pdPdSummaryTerritoryCompactMode =
                sessionStorage.getItem(pdPdTerritoryCompactKey) === "1";
        } catch (eTerrSt) {
            window.__pdPdSummaryTerritoryCompactMode = false;
        }
        if (window.__pdPdSummaryTerritoryCompactMode) {
            /** При «Сводной таблице» — все секции на одной странице (список короткий). */
            if (
                typeof window.__pdSummaryLoadEntityPaginationPage !== "function" &&
                pdSummaryServerEntityPaginationUrlIsPaginated()
            ) {
                pdSummarySavePaginationBeforeCompact();
                pdSummaryNavigateServerEntityPagination(1, 0);
            }
        }
        syncPdPdTerritoryCompactToggleUi();
        pdPdTerritoryCompactBtn.addEventListener("click", function () {
            window.__pdPdSummaryTerritoryCompactMode = !window.__pdPdSummaryTerritoryCompactMode;
            try {
                sessionStorage.setItem(
                    pdPdTerritoryCompactKey,
                    window.__pdPdSummaryTerritoryCompactMode ? "1" : "0"
                );
            } catch (eTc) { /* */ }
            /**
             * Rerender uses last core payload and rebuilds tbody, so optional
             * segments (ЧЧИ / ЭЭ / проверка / расчётные макс.) must be loaded
             * again after rerender — otherwise toggle buttons stay pressed
             * but their rows are missing until the user re-clicks them.
             */
            function collectActiveOptionalSegmentsAfterCompact() {
                if (
                    typeof window.__pdPdSummaryCollectActiveOptionalSegments ===
                    "function"
                ) {
                    return window.__pdPdSummaryCollectActiveOptionalSegments();
                }
                var view = summaryTable.getAttribute("data-summary-view") || "oes";
                var segs = [];
                if (window.__pdPdSummaryNtDetailMode === true) {
                    segs.push("nt_extra");
                }
                if (window.__pdPdSummaryCalcMaxMode === true) {
                    segs.push("calc_max");
                }
                if (window.__pdPdSummaryEeMode === true) {
                    if (
                        (view === "oes" || view === "fo") &&
                        segs.indexOf("nt_extra") < 0
                    ) {
                        segs.push("nt_extra");
                    }
                    segs.push("ee");
                }
                if (window.__pdPdSummaryChiMode === true) {
                    if (
                        (view === "oes" || view === "fo") &&
                        segs.indexOf("nt_extra") < 0
                    ) {
                        segs.push("nt_extra");
                    }
                    segs.push("chi");
                }
                if (window.__pdPdSummaryVerificationMode === true) {
                    if (segs.indexOf("calc_max") < 0) {
                        segs.push("calc_max");
                    }
                    segs.push("verify");
                }
                if (typeof window.__pdPdSummarySegmentsForVisibleRows === "function") {
                    window.__pdPdSummarySegmentsForVisibleRows().forEach(function (seg) {
                        if (
                            seg &&
                            seg !== "core" &&
                            segs.indexOf(seg) < 0
                        ) {
                            segs.push(seg);
                        }
                    });
                }
                return segs;
            }
            function afterCompactLayoutRefresh() {
                if (
                    window.__pdPdSummaryCalcMaxMode === true &&
                    typeof window.__pdPdSummarySetCalcMaxRowKeysVisible === "function"
                ) {
                    window.__pdPdSummarySetCalcMaxRowKeysVisible(true);
                } else if (typeof window.__pdPdSummaryReapplyRowVisibility === "function") {
                    window.__pdPdSummaryReapplyRowVisibility();
                }
                syncPdPdNtAdjustedEntityLabels();
            }
            function ensureOptionalThenFinish() {
                var optionalSegs = collectActiveOptionalSegmentsAfterCompact();
                if (
                    optionalSegs.length &&
                    typeof window.__pdSummaryEnsureSegments === "function"
                ) {
                    window.__pdSummaryEnsureSegments(optionalSegs).then(
                        afterCompactLayoutRefresh,
                        afterCompactLayoutRefresh
                    );
                    return;
                }
                afterCompactLayoutRefresh();
            }
            function reapplyAfterCompactToggle(opts) {
                syncPdPdTerritoryCompactToggleUi();
                // Pagination reload already remeshed optional segments — only
                // refresh visibility/labels. A second tbody rebuild would drop
                // them again and race with in-flight segment merges.
                if (opts && opts.skipRerender) {
                    afterCompactLayoutRefresh();
                    return;
                }
                if (typeof window.__pdPdSummaryRerenderTableBody === "function") {
                    var rerenderPromise = window.__pdPdSummaryRerenderTableBody();
                    if (rerenderPromise && typeof rerenderPromise.then === "function") {
                        rerenderPromise.then(
                            ensureOptionalThenFinish,
                            ensureOptionalThenFinish
                        );
                        return;
                    }
                }
                ensureOptionalThenFinish();
            }
            if (window.__pdPdSummaryTerritoryCompactMode) {
                var needsAllSectionsClient =
                    typeof window.__pdSummaryEntityPaginationUrlIsPaginated ===
                        "function" &&
                    window.__pdSummaryEntityPaginationUrlIsPaginated();
                if (
                    needsAllSectionsClient &&
                    typeof window.__pdSummaryLoadEntityPaginationPage === "function"
                ) {
                    pdSummarySavePaginationBeforeCompact();
                    window.__pdSummaryLoadEntityPaginationPage(1, 0).then(
                        function () {
                            reapplyAfterCompactToggle({ skipRerender: true });
                        },
                        function () {
                            reapplyAfterCompactToggle({ skipRerender: true });
                        }
                    );
                    return;
                }
                if (
                    typeof window.__pdSummaryLoadEntityPaginationPage !== "function" &&
                    pdSummaryServerEntityPaginationUrlIsPaginated()
                ) {
                    pdSummarySavePaginationBeforeCompact();
                    pdSummaryNavigateServerEntityPagination(1, 0);
                    return;
                }
                reapplyAfterCompactToggle();
                return;
            }
            var savedPag = pdSummaryReadPaginationBeforeCompact();
            if (
                savedPag &&
                savedPag.pageSize > 0 &&
                typeof window.__pdSummaryLoadEntityPaginationPage === "function"
            ) {
                window.__pdSummaryLoadEntityPaginationPage(
                    savedPag.page || 1,
                    savedPag.pageSize
                ).then(
                    function () {
                        reapplyAfterCompactToggle({ skipRerender: true });
                    },
                    function () {
                        reapplyAfterCompactToggle({ skipRerender: true });
                    }
                );
                return;
            }
            if (
                savedPag &&
                savedPag.pageSize > 0 &&
                typeof window.__pdSummaryLoadEntityPaginationPage !== "function"
            ) {
                pdSummaryNavigateServerEntityPagination(
                    savedPag.page || 1,
                    savedPag.pageSize
                );
                return;
            }
            reapplyAfterCompactToggle();
        });
    } else {
        window.__pdPdSummaryTerritoryCompactMode = false;
    }

    function pdSummaryCollectSegmentsForKeyMap(keyMap, rowKeys) {
        var segs = {};
        rowKeys.forEach(function (k) {
            if (keyMap[k] === false) {
                return;
            }
            if (typeof window.__pdSummarySegmentForParameterKey === "function") {
                var seg = window.__pdSummarySegmentForParameterKey(k);
                if (seg) {
                    segs[seg] = true;
                }
            }
        });
        return Object.keys(segs);
    }

    function pdSummaryFindEntityLabelWrap(startTr) {
        var wrap = startTr.querySelector("td.summary-entity-cell div");
        if (wrap) {
            return wrap;
        }
        if (typeof pdSummaryCollectEntityBlockRows === "function") {
            var blockRows = pdSummaryCollectEntityBlockRows(startTr);
            for (var i = 0; i < blockRows.length; i++) {
                wrap = blockRows[i].querySelector("td.summary-entity-cell div");
                if (wrap) {
                    return wrap;
                }
            }
        }
        return null;
    }

    function syncPdPdNtAdjustedEntityLabels() {
        var ntDetailBtnPresent = document.getElementById("pdPdSummaryNtDetailToggle");
        var ntDetailOn = !ntDetailBtnPresent || window.__pdPdSummaryNtDetailMode === true;
        var territoryCompactOn = window.__pdPdSummaryTerritoryCompactMode === true;
        var tbody = summaryTable.querySelector("tbody");
        if (!tbody) {
            return;
        }
        tbody
            .querySelectorAll(
                "tr[data-pd-pd-entity-label-full], tr[data-pd-pd-entity-label-territory-compact]"
            )
            .forEach(function (tr) {
            var wrap = pdSummaryFindEntityLabelWrap(tr);
            var entityCell = null;
            if (!wrap) {
                entityCell = tr.querySelector("td.summary-entity-cell");
                if (!entityCell) {
                    return;
                }
                wrap = entityCell;
            }
            var fullL = tr.getAttribute("data-pd-pd-entity-label-full");
            var cn = tr.getAttribute("data-pd-pd-entity-label-compact-nt");
            var ntDet = tr.getAttribute("data-pd-pd-entity-label-nt-detail");
            var terrCompact = tr.getAttribute("data-pd-pd-entity-label-territory-compact");
            var text;
            if (territoryCompactOn && terrCompact) {
                text = terrCompact;
            } else if (ntDetailOn) {
                text = ntDet || fullL;
            } else {
                text = cn || fullL;
            }
            var dzMark = wrap.querySelector ? wrap.querySelector(".pd-pd-dz-mark") : null;
            wrap.textContent = text || "";
            if (dzMark) {
                wrap.appendChild(document.createTextNode(" "));
                wrap.appendChild(dzMark);
            }
        });
    }

    function pdSummaryRowIsDomVisible(tr) {
        if (
            tr.classList.contains("summary-row-hidden") ||
            tr.classList.contains("summary-row-empty-block-hidden")
        ) {
            return false;
        }
        if (
            tr.classList.contains("summary-row-coeff-k") &&
            summaryTable.classList.contains("pd-coeff-hide-k-columns")
        ) {
            return false;
        }
        return true;
    }

    /** Следующий блок сущности: не считать «Проверка …» стартом (иначе она выпадает из rowspan). */
    function pdSummaryIsNextEntityBlockStart(tr, startTr) {
        return (
            !!tr &&
            tr !== startTr &&
            tr.classList.contains("summary-row-param") &&
            tr.getAttribute("data-is-block-start") === "1" &&
            !tr.classList.contains("pd-pd-verify-for-row")
        );
    }

    function pdSummaryDetachSpuriousVerifyBlockStart(tr) {
        if (
            tr &&
            tr.classList.contains("pd-pd-verify-for-row") &&
            tr.getAttribute("data-is-block-start") === "1"
        ) {
            tr.removeAttribute("data-is-block-start");
        }
    }

    /** Фон видимых строк показателя на coeff — как table-striped на /summary/oes/ (по блокам entity). */
    function applyPdBlockRowBackgrounds() {
        if (summaryTable.getAttribute("data-ec-unify-block-bg") !== "1") {
            return;
        }
        var tbody = summaryTable.querySelector("tbody");
        if (!tbody) {
            return;
        }
        Array.prototype.forEach.call(
            tbody.querySelectorAll("tr.summary-row-param"),
            function (tr) {
                tr.removeAttribute("data-ec-block-stripe");
            }
        );
        var blockParity = 0;
        var startRows = tbody.querySelectorAll('tr.summary-row-param[data-is-block-start="1"]');
        Array.prototype.forEach.call(startRows, function (startTr) {
            if (startTr.classList.contains("pd-pd-verify-for-row")) {
                pdSummaryDetachSpuriousVerifyBlockStart(startTr);
                return;
            }
            var blockRows = pdSummaryCollectEntityBlockRows(startTr);
            var visibleRows = blockRows.filter(function (r) {
                return pdSummaryRowIsDomVisible(r);
            });
            var stripe = String(blockParity % 2);
            visibleRows.forEach(function (r) {
                r.setAttribute("data-ec-block-stripe", stripe);
            });
            blockParity += 1;
        });
    }

    window.__pdPdSummaryApplyBlockRowBackgrounds = applyPdBlockRowBackgrounds;

    /**
     * Толстая граница между блоками энергосистем (кроме после последнего),
     * как fuel-param-group-last — между сущностями любого уровня
     * (ОЭС→ЭС, ЭС→город, город→область и т.п.), без линий внутри блока.
     *
     * Рисуем border-top на первой видимой строке следующего блока (все td,
     * включая rowspan «Энергосистема»/«Примечание»): sticky/z-index иначе
     * перекрывает нижнюю границу предыдущего блока.
     */
    function applyPdEntityLevelBorders() {
        var tbody = summaryTable.querySelector("tbody");
        if (!tbody) {
            return;
        }
        Array.prototype.forEach.call(
            tbody.querySelectorAll(
                "tr.pd-summary-entity-block-last, tr.pd-summary-entity-block-first"
            ),
            function (tr) {
                tr.classList.remove(
                    "pd-summary-entity-block-last",
                    "pd-summary-entity-block-first"
                );
            }
        );
        Array.prototype.forEach.call(
            tbody.querySelectorAll(
                "td.pd-summary-entity-block-span, td.pd-summary-entity-block-span-start"
            ),
            function (td) {
                td.classList.remove(
                    "pd-summary-entity-block-span",
                    "pd-summary-entity-block-span-start"
                );
            }
        );

        var blocks = [];
        var startRows = tbody.querySelectorAll(
            'tr.summary-row-param[data-is-block-start="1"]'
        );
        Array.prototype.forEach.call(startRows, function (startTr) {
            if (startTr.classList.contains("pd-pd-verify-for-row")) {
                pdSummaryDetachSpuriousVerifyBlockStart(startTr);
                return;
            }
            var blockRows;
            if (startTr.getAttribute("data-pd-pd-aggregation-level") === "1") {
                blockRows = [startTr];
            } else {
                blockRows = pdSummaryCollectEntityBlockRows(startTr);
            }
            if (!blockRows.length) {
                return;
            }
            var layoutRows = pdSummaryBlockRowsForRowspan(blockRows);
            var visibleRows = layoutRows.filter(function (r) {
                return pdSummaryRowIsDomVisible(r);
            });
            if (!visibleRows.length) {
                return;
            }
            blocks.push({
                blockRows: blockRows,
                visibleRows: visibleRows,
            });
        });

        for (var bj = 1; bj < blocks.length; bj++) {
            blocks[bj].visibleRows[0].classList.add("pd-summary-entity-block-first");
        }
    }

    window.__pdPdSummaryApplyEntityLevelBorders = applyPdEntityLevelBorders;

    function pdSummaryCoeffKRowForMwTr(mwTr) {
        if (!mwTr) {
            return null;
        }
        var pk = mwTr.getAttribute("data-parameter-key") || "";
        if (pk === "max_power") {
            return null;
        }
        var nx = mwTr.nextElementSibling;
        // На coeff «Проверка …» стоит сразу после расчётной строки, перед k.
        while (
            nx &&
            nx.classList.contains("summary-row-param") &&
            nx.classList.contains("pd-pd-verify-for-row")
        ) {
            var aKey = nx.getAttribute("data-pd-pd-verify-a") || "";
            var vPk = nx.getAttribute("data-parameter-key") || "";
            if (aKey === pk || vPk === "verify_for_" + pk) {
                nx = nx.nextElementSibling;
                continue;
            }
            break;
        }
        if (nx && nx.classList.contains("summary-row-coeff-k")) {
            if ((nx.getAttribute("data-parameter-key") || "") === pk) {
                return nx;
            }
        }
        return null;
    }

    function pdSummaryCollectEntityBlockRows(startTr) {
        var blockRows = [];
        var tr = startTr;
        while (tr) {
            if (tr.classList.contains("summary-row-param")) {
                if (pdSummaryIsNextEntityBlockStart(tr, startTr)) {
                    break;
                }
                pdSummaryDetachSpuriousVerifyBlockStart(tr);
                blockRows.push(tr);
            }
            tr = tr.nextElementSibling;
        }
        if (blockRows.length) {
            var rs = String(blockRows.length);
            blockRows[0].setAttribute("data-entity-block-size", rs);
            blockRows.forEach(function (rowTr) {
                rowTr.setAttribute("data-entity-block-size", rs);
            });
        }
        return blockRows;
    }

    function pdSummaryTerritoryCompactShouldHideRow(tr) {
        if (
            tr.getAttribute("data-pd-pd-summary-table-only") === "1" &&
            window.__pdPdSummaryTerritoryCompactMode !== true
        ) {
            return true;
        }
        if (window.__pdPdSummaryTerritoryCompactMode !== true) {
            return false;
        }
        // Блок «Новые территории» (+НТ): в «Сводной таблице» видим при нажатом «+ НТ».
        if (tr.getAttribute("data-pd-pd-nt-extra") === "1") {
            return false;
        }
        if (tr.getAttribute("data-pd-pd-territory-compact-hide") === "1") {
            return true;
        }
        return false;
    }

    function pdSummaryApplyOptionalRowLayers() {
        if (summaryView !== "oes" && summaryView !== "fo" && summaryView !== "ez") {
            return;
        }
        var eeBtn = document.getElementById("pdPdSummaryEeToggle");
        if (eeBtn) {
            var eeOn = window.__pdPdSummaryEeMode === true;
            var ntDetailBtnForEe = document.getElementById("pdPdSummaryNtDetailToggle");
            var ntDetailOnForEe = !ntDetailBtnForEe || window.__pdPdSummaryNtDetailMode === true;
            summaryTable
                .querySelectorAll('tbody tr[data-pd-pd-ee-row="1"], tbody tr.pd-pd-ee-row')
                .forEach(function (tr) {
                    var hide =
                        !eeOn ||
                        (tr.getAttribute("data-pd-pd-nt-extra") === "1" && !ntDetailOnForEe) ||
                        pdSummaryTerritoryCompactShouldHideRow(tr) ||
                        (window.__pdPdSummaryTerritoryCompactMode === true &&
                            tr.getAttribute("data-pd-pd-territory-detail") === "1" &&
                            tr.getAttribute("data-pd-pd-nt-extra") !== "1");
                    tr.classList.toggle("summary-row-hidden", hide);
                    var kRowEe = pdSummaryCoeffKRowForMwTr(tr);
                    if (kRowEe) {
                        kRowEe.classList.toggle("summary-row-hidden", hide);
                    }
                });
        }
        var chiBtn = document.getElementById("pdPdSummaryChiToggle");
        if (chiBtn) {
            var chiOn = window.__pdPdSummaryChiMode === true;
            var ntDetailBtnPresent = document.getElementById("pdPdSummaryNtDetailToggle");
            var ntDetailOn = !ntDetailBtnPresent || window.__pdPdSummaryNtDetailMode === true;
            summaryTable
                .querySelectorAll('tbody tr[data-pd-pd-chi-row="1"], tbody tr.pd-pd-chi-row')
                .forEach(function (tr) {
                    var hide =
                        !chiOn ||
                        (tr.getAttribute("data-pd-pd-nt-extra") === "1" && !ntDetailOn) ||
                        pdSummaryTerritoryCompactShouldHideRow(tr) ||
                        (window.__pdPdSummaryTerritoryCompactMode === true &&
                            tr.getAttribute("data-pd-pd-territory-detail") === "1" &&
                            tr.getAttribute("data-pd-pd-nt-extra") !== "1");
                    tr.classList.toggle("summary-row-hidden", hide);
                    var kRowChi = pdSummaryCoeffKRowForMwTr(tr);
                    if (kRowChi) {
                        kRowChi.classList.toggle("summary-row-hidden", hide);
                    }
                });
        }
        var verificationBtn = document.getElementById("pdPdSummaryVerificationToggle");
        if (verificationBtn) {
            var verOn = window.__pdPdSummaryVerificationMode === true;
            var ntBtnPresent2 = document.getElementById("pdPdSummaryNtDetailToggle");
            var ntOn2 = !ntBtnPresent2 || window.__pdPdSummaryNtDetailMode === true;
            summaryTable.querySelectorAll("tbody tr.summary-row-param").forEach(function (tr) {
                var isVer =
                    tr.classList.contains("pd-pd-verification-row") ||
                    tr.classList.contains("pd-pd-verify-for-row");
                if (!isVer) {
                    return;
                }
                var hide =
                    !verOn ||
                    (tr.getAttribute("data-pd-pd-nt-extra") === "1" && !ntOn2) ||
                    pdSummaryTerritoryCompactShouldHideRow(tr) ||
                    (window.__pdPdSummaryTerritoryCompactMode === true &&
                        tr.getAttribute("data-pd-pd-territory-detail") === "1" &&
                        tr.getAttribute("data-pd-pd-nt-extra") !== "1");
                tr.classList.toggle("summary-row-hidden", hide);
                var kRow = pdSummaryCoeffKRowForMwTr(tr);
                if (kRow) {
                    kRow.classList.toggle("summary-row-hidden", hide);
                }
            });
        }
    }

    /**
     * Строки блока для rowspan — в порядке DOM (показатель, «Проверка …», k).
     * Логическая пара «показатель + k» даёт неверный firstVis, если между ними
     * вставлена проверка: ячейка «Энергосистема» не покрывает эту строку.
     */
    function pdSummaryCollectEntityBlockLayoutRows(startTr) {
        var out = [];
        var tr = startTr;
        while (tr) {
            if (pdSummaryIsNextEntityBlockStart(tr, startTr)) {
                break;
            }
            if (
                tr.classList.contains("summary-row-param") ||
                tr.classList.contains("summary-row-coeff-k")
            ) {
                pdSummaryDetachSpuriousVerifyBlockStart(tr);
                out.push(tr);
            }
            tr = tr.nextElementSibling;
        }
        return out;
    }

    function pdSummaryBlockRowsForRowspan(blockRows) {
        if (!blockRows || !blockRows.length) {
            return [];
        }
        return pdSummaryCollectEntityBlockLayoutRows(blockRows[0]);
    }

    function pdSummaryCellHasMeaningfulValue(cell, parameterKey) {
        if (!cell) {
            return false;
        }
        var target = cell;
        if (cell.classList.contains("summary-year-mw-cell")) {
            var mwLine = cell.querySelector(".pd-coeff-mw-line");
            if (mwLine) {
                target = mwLine;
            }
        }
        if (cell.classList.contains("summary-plan-empty")) {
            return false;
        }
        var inp = target.querySelector("input, textarea");
        var t = inp ? String(inp.value || "").trim() : String(target.textContent || "").trim();
        if (t === "" || t === "—") {
            return false;
        }
        if (parameterKey === "peak_datetime") {
            return true;
        }
        var n = parseFloat(t.replace(/\s/g, "").replace(",", "."));
        if (!Number.isFinite(n)) {
            return true;
        }
        return n !== 0;
    }

    function pdSummaryParamRowIsEmpty(tr) {
        var pk = tr.getAttribute("data-parameter-key") || "";
        var cells = tr.querySelectorAll(
            "td.summary-hist-cell, td.summary-year-cell, td.summary-year-mw-cell"
        );
        for (var i = 0; i < cells.length; i++) {
            if (pdSummaryCellHasMeaningfulValue(cells[i], pk)) {
                return false;
            }
        }
        return true;
    }

    function pdSummaryEntityBlockIsEmpty(blockRows) {
        for (var i = 0; i < blockRows.length; i++) {
            if (
                blockRows[i].classList.contains("pd-pd-verification-row") ||
                blockRows[i].classList.contains("pd-pd-verify-for-row") ||
                blockRows[i].classList.contains("pd-pd-calc-max-row") ||
                blockRows[i].classList.contains("pd-pd-chi-row") ||
                blockRows[i].classList.contains("pd-pd-ee-row")
            ) {
                continue;
            }
            if (!pdSummaryParamRowIsEmpty(blockRows[i])) {
                return false;
            }
        }
        return true;
    }

    function applyPdSummaryHideEmptyEntityBlocks() {
        var showEmptyOn = window.__pdPdSummaryShowEmptyMode === true;
        var tbody = summaryTable.querySelector("tbody");
        if (!tbody) {
            return;
        }
        tbody.querySelectorAll('tr.summary-row-param[data-is-block-start="1"]').forEach(function (startTr) {
            if (startTr.classList.contains("pd-pd-verify-for-row")) {
                pdSummaryDetachSpuriousVerifyBlockStart(startTr);
                return;
            }
            var blockRows = pdSummaryCollectEntityBlockRows(startTr);
            var isEmpty = pdSummaryEntityBlockIsEmpty(blockRows);
            var skipEmptyHide = blockRows.some(function (tr) {
                return tr.getAttribute("data-pd-pd-skip-empty-hide") === "1";
            });
            var keepDespiteEmpty = skipEmptyHide;
            blockRows.forEach(function (tr) {
                var hideBlock = !showEmptyOn && isEmpty && !keepDespiteEmpty;
                if (hideBlock) {
                    tr.classList.add("summary-row-empty-block-hidden");
                } else {
                    tr.classList.remove("summary-row-empty-block-hidden");
                }
                var kRow = pdSummaryCoeffKRowForMwTr(tr);
                if (kRow) {
                    if (hideBlock) {
                        kRow.classList.add("summary-row-empty-block-hidden");
                    } else {
                        kRow.classList.remove("summary-row-empty-block-hidden");
                    }
                }
            });
        });
    }

    window.__pdPdSummaryRefreshLayoutAfterVisibility = function () {
        if (typeof window.pdSummarySyncAggregationLevelColspans === "function") {
            window.pdSummarySyncAggregationLevelColspans();
        }
        applyPdSummaryHideEmptyEntityBlocks();
        if (typeof window.__pdPdSummaryRepositionEntityCells === "function") {
            window.__pdPdSummaryRepositionEntityCells();
        }
    };

    var pdPdHideEmptyBtn = document.getElementById("pdPdSummaryHideEmptyToggle");
    if (pdPdHideEmptyBtn) {
        var pdPdHideEmptyStorageKey =
            "pdPdSummaryShowEmpty_" +
            (summaryTable.getAttribute("data-summary-view") || "oes") +
            "_" +
            (summaryTable.getAttribute("data-summary-route-variant") || "max");
        function syncPdPdHideEmptyToggleUi() {
            var on = window.__pdPdSummaryShowEmptyMode === true;
            pdPdHideEmptyBtn.setAttribute("aria-pressed", on ? "true" : "false");
            pdPdHideEmptyBtn.classList.toggle("btn-primary", on);
            pdPdHideEmptyBtn.classList.toggle("btn-outline-primary", !on);
        }
        try {
            var storedHideEmpty = sessionStorage.getItem(pdPdHideEmptyStorageKey);
            window.__pdPdSummaryShowEmptyMode =
                storedHideEmpty === null ? false : storedHideEmpty === "1";
        } catch (eHideEmptyInit) {
            window.__pdPdSummaryShowEmptyMode = false;
        }
        syncPdPdHideEmptyToggleUi();
        pdPdHideEmptyBtn.addEventListener("click", function () {
            window.__pdPdSummaryShowEmptyMode = !window.__pdPdSummaryShowEmptyMode;
            try {
                sessionStorage.setItem(
                    pdPdHideEmptyStorageKey,
                    window.__pdPdSummaryShowEmptyMode ? "1" : "0"
                );
            } catch (eHideEmptySt) { /* */ }
            syncPdPdHideEmptyToggleUi();
            if (typeof window.__pdPdSummaryReapplyRowVisibility === "function") {
                window.__pdPdSummaryReapplyRowVisibility();
            } else if (typeof window.__pdPdSummaryRefreshLayoutAfterVisibility === "function") {
                window.__pdPdSummaryRefreshLayoutAfterVisibility();
            }
        });
    }

    function initPdSummaryRowPicker(spec) {
        var ROW_KEYS = spec.rowKeys;
        var storageKey = spec.storageKey;
        var modalId = spec.modalId;
        var applyBtnId = spec.applyBtnId;
        var lastApplied = null;
        var defaultHiddenKeys = spec.defaultHiddenKeys || [];

        function buildDefaultKeyMap() {
            var def = {};
            ROW_KEYS.forEach(function (k) {
                def[k] = true;
            });
            defaultHiddenKeys.forEach(function (k) {
                if (Object.prototype.hasOwnProperty.call(def, k)) {
                    def[k] = false;
                }
            });
            return def;
        }

        /**
         * Ячейка «Энергосистема» в разметке только у первой строки блока (обычно max_power).
         * Если эту строку скрывают, без переноса ячейки таблица «ломается» (колонки съезжают).
         * Переносим td.summary-entity-cell на первую видимую строку блока и выставляем rowspan.
         */
        function clampRowspansBeforeAggregationHeaders(tbody) {
            if (!tbody) {
                return;
            }
            var layoutTr = [];
            var walk = tbody.firstElementChild;
            while (walk) {
                if (
                    (walk.classList.contains("summary-row-param") ||
                        walk.classList.contains("summary-row-coeff-k")) &&
                    pdSummaryRowIsDomVisible(walk)
                ) {
                    layoutTr.push(walk);
                }
                walk = walk.nextElementSibling;
            }
            var aggIndices = [];
            for (var a = 0; a < layoutTr.length; a++) {
                if (layoutTr[a].getAttribute("data-pd-pd-aggregation-level") === "1") {
                    aggIndices.push(a);
                }
            }
            if (!aggIndices.length) {
                return;
            }
            for (var i = 0; i < layoutTr.length; i++) {
                var cells = layoutTr[i].cells;
                for (var c = 0; c < cells.length; c++) {
                    var td = cells[c];
                    var rs = parseInt(td.getAttribute("rowspan") || "1", 10);
                    if (rs <= 1) {
                        continue;
                    }
                    for (var ai = 0; ai < aggIndices.length; ai++) {
                        var aggIdx = aggIndices[ai];
                        if (i < aggIdx && i + rs > aggIdx) {
                            td.setAttribute("rowspan", String(Math.max(1, aggIdx - i)));
                            break;
                        }
                    }
                }
            }
        }

        function clearSummaryNoteFieldHeights() {
            summaryTable.querySelectorAll("td.summary-entity-note-cell > .summary-entity-note-wrap").forEach(function (wrap) {
                wrap.style.height = "";
                var ta = wrap.querySelector("textarea.power-demand-summary-note-field");
                if (!ta) {
                    return;
                }
                ta.style.height = "";
                ta.style.minHeight = "";
                ta.style.paddingTop = "";
                ta.style.paddingBottom = "";
            });
        }

        function syncSummaryNoteFieldHeights() {
            // Сброс зафиксированных px-высот: иначе после скрытия строк фильтром
            // старая высота «Примечания» растягивает оставшиеся строки блока.
            clearSummaryNoteFieldHeights();
            void summaryTable.offsetHeight;

            summaryTable.querySelectorAll("td.summary-entity-note-cell > .summary-entity-note-wrap").forEach(function (wrap) {
                var td = wrap.closest("td.summary-entity-note-cell");
                if (!td || td.offsetHeight < 1) {
                    return;
                }
                var cellH = td.clientHeight;
                wrap.style.height = cellH + "px";
                var ta = wrap.querySelector("textarea.power-demand-summary-note-field");
                if (!ta) {
                    return;
                }
                ta.style.height = "auto";
                ta.style.minHeight = "0";
                ta.style.paddingTop = "0";
                ta.style.paddingBottom = "0";
                var contentH = ta.scrollHeight;
                ta.style.height = cellH + "px";
                ta.style.minHeight = cellH + "px";
                if (contentH <= cellH) {
                    var padTotal = cellH - contentH;
                    var padTop = Math.floor(padTotal / 2);
                    ta.style.paddingTop = padTop + "px";
                    ta.style.paddingBottom = (padTotal - padTop) + "px";
                } else {
                    ta.style.paddingTop = "0.2rem";
                    ta.style.paddingBottom = "0.2rem";
                }
            });
        }

        function repositionEntityCellsAndRowspans() {
            var tbody = summaryTable.querySelector("tbody");
            if (!tbody) {
                return;
            }
            // До смены rowspan убрать px-высоты примечаний, иначе блок не сожмётся.
            clearSummaryNoteFieldHeights();
            var startRows = tbody.querySelectorAll(
                'tr.summary-row-param[data-is-block-start="1"]'
            );
            Array.prototype.forEach.call(startRows, function (startTr) {
                if (startTr.getAttribute("data-pd-pd-aggregation-level") === "1") {
                    return;
                }
                if (startTr.classList.contains("pd-pd-verify-for-row")) {
                    pdSummaryDetachSpuriousVerifyBlockStart(startTr);
                    return;
                }
                var blockRows = pdSummaryCollectEntityBlockRows(startTr);
                if (blockRows.length === 0) {
                    return;
                }
                var entityTd = null;
                for (var k = 0; k < blockRows.length; k++) {
                    var et = blockRows[k].querySelector("td.summary-entity-cell");
                    if (et) {
                        entityTd = et;
                        break;
                    }
                }
                var variantTd = null;
                for (var kv = 0; kv < blockRows.length; kv++) {
                    var vt = blockRows[kv].querySelector("td.summary-perimeter-variant-cell");
                    if (vt) {
                        variantTd = vt;
                        break;
                    }
                }
                if (!entityTd && !variantTd) {
                    return;
                }
                var domRows = pdSummaryBlockRowsForRowspan(blockRows);
                var visibleRows = domRows.filter(function (r) {
                    return pdSummaryRowIsDomVisible(r);
                });
                if (visibleRows.length === 0) {
                    if (entityTd) {
                        entityTd.setAttribute("rowspan", "1");
                    }
                    if (variantTd) {
                        variantTd.setAttribute("rowspan", "1");
                    }
                    var noteTdZero = null;
                    for (var knz = 0; knz < blockRows.length; knz++) {
                        var ntz = blockRows[knz].querySelector("td.summary-entity-note-cell");
                        if (ntz) {
                            noteTdZero = ntz;
                            break;
                        }
                    }
                    if (noteTdZero) {
                        noteTdZero.setAttribute("rowspan", "1");
                    }
                    return;
                }
                var firstVis = visibleRows[0];
                var paramCell = firstVis.querySelector("td.summary-parameter-cell");
                if (variantTd) {
                    var insertBeforeVariant =
                        firstVis.querySelector("td.summary-entity-cell") || paramCell;
                    if (insertBeforeVariant && variantTd.parentNode !== firstVis) {
                        firstVis.insertBefore(variantTd, insertBeforeVariant);
                    } else if (!insertBeforeVariant && variantTd.parentNode !== firstVis) {
                        firstVis.insertBefore(variantTd, firstVis.firstChild);
                    }
                    variantTd.setAttribute("rowspan", String(visibleRows.length));
                }
                if (entityTd) {
                    if (paramCell && entityTd.parentNode !== firstVis) {
                        firstVis.insertBefore(entityTd, paramCell);
                    }
                    entityTd.setAttribute("rowspan", String(visibleRows.length));
                }

                var noteTd = null;
                for (var kn = 0; kn < blockRows.length; kn++) {
                    var nt = blockRows[kn].querySelector("td.summary-entity-note-cell");
                    if (nt) {
                        noteTd = nt;
                        break;
                    }
                }
                if (noteTd && visibleRows.length > 0) {
                    var firstVisNote = visibleRows[0];
                    // Always append so a misplaced note stays the last cell.
                    firstVisNote.appendChild(noteTd);
                    noteTd.setAttribute("rowspan", String(visibleRows.length));
                }
            });
            clampRowspansBeforeAggregationHeaders(tbody);
            syncSummaryNoteFieldHeights();
            applyPdBlockRowBackgrounds();
            applyPdEntityLevelBorders();
        }

        if (!summaryTable.dataset.pdNoteFieldInputBound) {
            summaryTable.dataset.pdNoteFieldInputBound = "1";
            summaryTable.addEventListener("input", function (e) {
                if (e.target && e.target.matches("textarea.power-demand-summary-note-field")) {
                    syncSummaryNoteFieldHeights();
                }
            });
        }

        function buildModalKeyMapFromDom(keyMap) {
            var map = {};
            ROW_KEYS.forEach(function (k) {
                var rows = summaryTable.querySelectorAll(
                    'tbody tr.summary-row-param[data-parameter-key="' + k + '"]'
                );
                if (!rows.length) {
                    map[k] = keyMap[k] !== false;
                    return;
                }
                var visible = false;
                Array.prototype.forEach.call(rows, function (tr) {
                    if (pdSummaryRowIsDomVisible(tr)) {
                        visible = true;
                    }
                });
                map[k] = visible;
            });
            return map;
        }

        function syncCalcMaxModeFromKeyMap(keyMap) {
            if (
                summaryView !== "oes" &&
                summaryView !== "fo" &&
                summaryView !== "ez"
            ) {
                return;
            }
            var calcKeys = pdSummaryCalcMaxPickerKeysForView(summaryView, routeVariant);
            var anyOn = calcKeys.some(function (k) {
                return keyMap[k] !== false;
            });
            window.__pdPdSummaryCalcMaxMode = anyOn;
            try {
                sessionStorage.setItem(
                    "pdPdSummaryCalcMax_" + summaryView + "_" + routeVariant,
                    anyOn ? "1" : "0"
                );
            } catch (eCalcMaxSync) { /* */ }
            var calcMaxBtn = document.getElementById("pdPdSummaryCalcMaxToggle");
            if (calcMaxBtn) {
                calcMaxBtn.setAttribute("aria-pressed", anyOn ? "true" : "false");
                calcMaxBtn.classList.toggle("btn-success", anyOn);
                calcMaxBtn.classList.toggle("btn-outline-success", !anyOn);
            }
        }

        function applyCalcMaxRowKeysVisible(visible) {
            var calcKeys = pdSummaryCalcMaxPickerKeysForView(summaryView, routeVariant);
            calcKeys.forEach(function (k) {
                if (ROW_KEYS.indexOf(k) >= 0) {
                    lastApplied[k] = !!visible;
                }
            });
            applyVisibilityFromKeys(lastApplied);
            try {
                sessionStorage.setItem(
                    storageKey,
                    JSON.stringify(serializeKeys(lastApplied))
                );
            } catch (eCalcMaxKeysSt) { /* */ }
        }

        window.__pdPdSummarySetCalcMaxRowKeysVisible = applyCalcMaxRowKeysVisible;

        function migrateCalcMaxKeysInKeyMap(keyMap) {
            var calcKeys = pdSummaryCalcMaxPickerKeysForView(summaryView, routeVariant);
            if (!calcKeys.length) {
                return keyMap;
            }
            var calcOn = window.__pdPdSummaryCalcMaxMode === true;
            calcKeys.forEach(function (k) {
                if (Object.prototype.hasOwnProperty.call(keyMap, k)) {
                    keyMap[k] = calcOn;
                }
            });
            return keyMap;
        }

        function readKeysFromCheckboxes() {
            var set = {};
            ROW_KEYS.forEach(function (k) {
                set[k] = false;
            });
            document.querySelectorAll("#" + modalId + " input[data-pd-row-key]").forEach(function (inp) {
                var k = inp.getAttribute("data-pd-row-key");
                if (!k) {
                    return;
                }
                set[k] = inp.checked;
            });
            return set;
        }

        function syncCheckboxesFromKeys(keyMap) {
            document.querySelectorAll("#" + modalId + " input[data-pd-row-key]").forEach(function (inp) {
                var k = inp.getAttribute("data-pd-row-key");
                if (!k) {
                    return;
                }
                inp.checked = keyMap[k] !== false;
            });
        }

        function applyVisibilityFromKeys(keyMap) {
            var ntDetailBtnPresent = document.getElementById("pdPdSummaryNtDetailToggle");
            var ntDetailOn = !ntDetailBtnPresent || window.__pdPdSummaryNtDetailMode === true;
            function applyRowVisibilityOne(tr) {
                if (tr.getAttribute("data-pd-pd-aggregation-level") === "1") {
                    var hideAgg = false;
                    if (
                        tr.getAttribute("data-pd-pd-nt-extra") === "1" &&
                        !ntDetailOn
                    ) {
                        hideAgg = true;
                    }
                    if (pdSummaryTerritoryCompactShouldHideRow(tr)) {
                        hideAgg = true;
                    }
                    tr.classList.toggle("summary-row-hidden", hideAgg);
                    return;
                }
                if (tr.classList.contains("pd-pd-verify-for-row")) {
                    return;
                }
                if (
                    (summaryView === "oes" ||
                        summaryView === "fo" ||
                        summaryView === "ez") &&
                    (tr.getAttribute("data-pd-pd-chi-row") === "1" ||
                        tr.classList.contains("pd-pd-chi-row") ||
                        tr.getAttribute("data-pd-pd-ee-row") === "1" ||
                        tr.classList.contains("pd-pd-ee-row"))
                ) {
                    return;
                }
                var pk = tr.getAttribute("data-parameter-key") || "";
                var show = keyMap[pk] !== false;
                if (
                    show &&
                    tr.getAttribute("data-pd-pd-nt-extra") === "1" &&
                    !ntDetailOn
                ) {
                    show = false;
                }
                if (show && pdSummaryTerritoryCompactShouldHideRow(tr)) {
                    show = false;
                }
                if (
                    show &&
                    window.__pdPdSummaryTerritoryCompactMode === true &&
                    tr.getAttribute("data-pd-pd-territory-detail") === "1" &&
                    tr.getAttribute("data-pd-pd-nt-extra") !== "1"
                ) {
                    show = false;
                }
                if (show) {
                    tr.classList.remove("summary-row-hidden");
                } else {
                    tr.classList.add("summary-row-hidden");
                }
            }
            summaryTable.querySelectorAll("tbody tr.summary-row-param").forEach(applyRowVisibilityOne);
            summaryTable.querySelectorAll("tbody tr.summary-row-coeff-k").forEach(applyRowVisibilityOne);
            pdSummaryApplyOptionalRowLayers();
            applyPdSummaryHideEmptyEntityBlocks();
            repositionEntityCellsAndRowspans();
            syncPdPdNtAdjustedEntityLabels();
            applyPdBlockRowBackgrounds();
            applyPdEntityLevelBorders();
            if (
                summaryTable.classList.contains("pd-coeff-year-seg-table") &&
                typeof window.refreshPowerDemandCoeffMixins === "function"
            ) {
                window.refreshPowerDemandCoeffMixins();
            }
        }

        window.__pdPdSummaryRepositionEntityCells = repositionEntityCellsAndRowspans;
        window.__pdPdSummarySyncNoteFieldHeights = syncSummaryNoteFieldHeights;

        window.__pdPdSummaryReapplyRowVisibility = function () {
            if (typeof window.__pdPdSummaryReapplyCoeffYearVisibility === "function") {
                window.__pdPdSummaryReapplyCoeffYearVisibility();
            }
            applyVisibilityFromKeys(lastApplied);
        };

        window.__pdPdSummarySegmentsForVisibleRows = function () {
            return pdSummaryCollectSegmentsForKeyMap(lastApplied, ROW_KEYS);
        };

        function parseFromStorage(raw) {
            var def = buildDefaultKeyMap();
            if (!raw) {
                return def;
            }
            try {
                var arr = JSON.parse(raw);
                if (!Array.isArray(arr) || arr.length === 0) {
                    return def;
                }
                var out = {};
                ROW_KEYS.forEach(function (k) {
                    out[k] = arr.indexOf(k) !== -1;
                });
                defaultHiddenKeys.forEach(function (k) {
                    if (Object.prototype.hasOwnProperty.call(out, k)) {
                        out[k] = false;
                    }
                });
                return out;
            } catch (e) {
                return def;
            }
        }

        function serializeKeys(keyMap) {
            return ROW_KEYS.filter(function (k) {
                return keyMap[k] !== false;
            });
        }

        try {
            var stored = sessionStorage.getItem(storageKey);
            if (!stored) {
                var legacy = sessionStorage.getItem(FILTER_STORAGE_KEY);
                if (legacy === "max_power") {
                    var onlyMax = {};
                    ROW_KEYS.forEach(function (k) {
                        onlyMax[k] = k === "max_power";
                    });
                    lastApplied = onlyMax;
                }
            }
            if (!lastApplied) {
                lastApplied = parseFromStorage(stored);
            }
        } catch (e) {
            lastApplied = parseFromStorage(null);
        }

        lastApplied = migrateCalcMaxKeysInKeyMap(lastApplied);

        syncCheckboxesFromKeys(lastApplied);
        applyVisibilityFromKeys(lastApplied);
        try {
            sessionStorage.setItem(storageKey, JSON.stringify(serializeKeys(lastApplied)));
        } catch (e2) { /* */ }

        var modalEl = document.getElementById(modalId);
        if (modalEl) {
            modalEl.addEventListener("show.bs.modal", function () {
                syncCheckboxesFromKeys(buildModalKeyMapFromDom(lastApplied));
            });
        }
        var applyBtn = document.getElementById(applyBtnId);
        if (applyBtn && modalEl) {
            applyBtn.addEventListener("click", function () {
                var keyMap = readKeysFromCheckboxes();
                syncCalcMaxModeFromKeyMap(keyMap);
                var segList = pdSummaryCollectSegmentsForKeyMap(keyMap, ROW_KEYS);
                var applyRowKeys = function () {
                    lastApplied = keyMap;
                    applyVisibilityFromKeys(keyMap);
                    try {
                        sessionStorage.setItem(
                            storageKey,
                            JSON.stringify(serializeKeys(keyMap))
                        );
                    } catch (e3) { /* */ }
                    var inst = bootstrap.Modal.getInstance(modalEl);
                    if (inst) {
                        inst.hide();
                    }
                };
                if (
                    segList.length &&
                    typeof window.__pdSummaryEnsureSegments === "function"
                ) {
                    window.__pdSummaryEnsureSegments(segList).then(
                        applyRowKeys,
                        applyRowKeys
                    );
                } else {
                    applyRowKeys();
                }
            });
        }
    }

    function pdSummaryCalcMaxPickerKeysForView(view, routeVar) {
        if (view === "oes") {
            return [
                "calculated_max_power_mw",
                "calculated_max_power_consumption_mw",
                "calculated_combined_on_ees_mw",
                "calculated_max_ees_via_oes_mw",
                "calculated_max_ees_russia_mw",
                "calculated_max_ees_via_es_mw",
            ];
        }
        if (view === "fo") {
            // Как на /summary/federal_districts/: расчётные ФО/ЦЗ + префикс ЕЭС/ЭЭС/СЗ.
            return [
                "calculated_max_power_mw",
                "calculated_max_power_consumption_mw",
                "calculated_combined_on_cz_mw",
                "calculated_max_ees_via_oes_mw",
                "calculated_max_ees_russia_mw",
                "calculated_max_ees_via_es_mw",
                "cz_calculated_max_cz_russia_mw",
            ];
        }
        if (view === "ez") {
            return [
                "calculated_max_power_mw",
                "calculated_max_power_consumption_mw",
                "calculated_combined_on_ees_mw",
                "calculated_max_ees_via_oes_mw",
                "calculated_max_ees_russia_mw",
                "calculated_max_ees_via_es_mw",
                "calculated_max_ees_via_ez_mw",
            ];
        }
        return [];
    }

    var summaryView = summaryTable.getAttribute("data-summary-view");
    var routeVariant = summaryTable.getAttribute("data-summary-route-variant") || "max";
    var coeffDefaultHidden = routeVariant === "coeff" ? ["peak_datetime", "avg_temp"] : [];
    var rowPickerDefaultHidden = coeffDefaultHidden.slice();
    pdSummaryCalcMaxPickerKeysForView(summaryView, routeVariant).forEach(function (k) {
        if (rowPickerDefaultHidden.indexOf(k) < 0) {
            rowPickerDefaultHidden.push(k);
        }
    });

    // Кнопка «Потребление ЭЭ» — строки потребления со сводок energy_consumption (только чтение).
    var pdPdEeBtn = document.getElementById("pdPdSummaryEeToggle");
    var pdPdEeStorageKey =
        "pdPdSummaryEe_" +
        (summaryTable.getAttribute("data-summary-view") || "oes") +
        "_" +
        (summaryTable.getAttribute("data-summary-route-variant") || "max");
    try {
        window.__pdPdSummaryEeMode = sessionStorage.getItem(pdPdEeStorageKey) === "1";
    } catch (ePdPdEeInit) {
        window.__pdPdSummaryEeMode = false;
    }
    function enableNtDetailForEeVariants() {
        if (
            (summaryView !== "oes" && summaryView !== "fo") ||
            window.__pdPdSummaryEeMode !== true
        ) {
            return;
        }
        window.__pdPdSummaryNtDetailMode = true;
        try {
            sessionStorage.setItem(pdPdNtStorageKey, "1");
        } catch (eEeNt) { /* */ }
        var ntBtn = document.getElementById("pdPdSummaryNtDetailToggle");
        if (ntBtn) {
            ntBtn.setAttribute("aria-pressed", "true");
            ntBtn.classList.add("btn-primary");
            ntBtn.classList.remove("btn-outline-secondary");
        }
    }
    if (window.__pdPdSummaryEeMode) {
        enableNtDetailForEeVariants();
    }
    function syncPdPdEeToggleUi() {
        if (!pdPdEeBtn) {
            return;
        }
        var on = window.__pdPdSummaryEeMode === true;
        pdPdEeBtn.setAttribute("aria-pressed", on ? "true" : "false");
        pdPdEeBtn.classList.toggle("btn-danger", on);
        pdPdEeBtn.classList.toggle("btn-outline-danger", !on);
    }
    function applyPdPdEeVisibility() {
        pdSummaryApplyOptionalRowLayers();
        if (typeof window.__pdPdSummaryRefreshLayoutAfterVisibility === "function") {
            window.__pdPdSummaryRefreshLayoutAfterVisibility();
        }
    }
    window.__pdPdSummaryApplyEeVisibility = applyPdPdEeVisibility;
    if (pdPdEeBtn) {
        syncPdPdEeToggleUi();
        pdPdEeBtn.addEventListener("click", function () {
            window.__pdPdSummaryEeMode = !window.__pdPdSummaryEeMode;
            try {
                sessionStorage.setItem(
                    pdPdEeStorageKey,
                    window.__pdPdSummaryEeMode ? "1" : "0"
                );
            } catch (ePdPdEeSt) { /* */ }
            if (window.__pdPdSummaryEeMode) {
                enableNtDetailForEeVariants();
            }
            var applyEe = function () {
                syncPdPdEeToggleUi();
                if (typeof window.__pdPdSummaryReapplyRowVisibility === "function") {
                    window.__pdPdSummaryReapplyRowVisibility();
                } else {
                    applyPdPdEeVisibility();
                }
            };
            if (
                window.__pdPdSummaryEeMode &&
                typeof window.__pdSummaryEnsureSegments === "function"
            ) {
                var eeSegments =
                    summaryView === "oes" || summaryView === "fo"
                        ? ["nt_extra", "ee"]
                        : ["ee"];
                window.__pdSummaryEnsureSegments(eeSegments).then(applyEe, applyEe);
            } else {
                applyEe();
            }
        });
    }

    // Кнопка «ЧЧИ» — до initPdSummaryRowPicker, чтобы видимость
    // пересчитывалась вместе с фильтром строк и «Скрыть пустые».
    var pdPdChiBtn = document.getElementById("pdPdSummaryChiToggle");
    var pdPdChiStorageKey =
        "pdPdSummaryChi_" +
        (summaryTable.getAttribute("data-summary-view") || "oes") +
        "_" +
        (summaryTable.getAttribute("data-summary-route-variant") || "max");
    try {
        window.__pdPdSummaryChiMode = sessionStorage.getItem(pdPdChiStorageKey) === "1";
    } catch (ePdPdChiInit) {
        window.__pdPdSummaryChiMode = false;
    }
    function enableNtDetailForChiVariants() {
        if (
            (summaryView !== "oes" && summaryView !== "fo") ||
            window.__pdPdSummaryChiMode !== true
        ) {
            return;
        }
        window.__pdPdSummaryNtDetailMode = true;
        try {
            sessionStorage.setItem(pdPdNtStorageKey, "1");
        } catch (eChiNt) { /* */ }
        var ntBtn = document.getElementById("pdPdSummaryNtDetailToggle");
        if (ntBtn) {
            ntBtn.setAttribute("aria-pressed", "true");
            ntBtn.classList.add("btn-primary");
            ntBtn.classList.remove("btn-outline-secondary");
        }
    }
    if (window.__pdPdSummaryChiMode) {
        enableNtDetailForChiVariants();
    }
    function syncPdPdChiToggleUi() {
        if (!pdPdChiBtn) {
            return;
        }
        var on = window.__pdPdSummaryChiMode === true;
        pdPdChiBtn.setAttribute("aria-pressed", on ? "true" : "false");
        pdPdChiBtn.classList.toggle("btn-warning", on);
        pdPdChiBtn.classList.toggle("btn-outline-warning", !on);
    }
    function applyPdPdChiVisibility() {
        pdSummaryApplyOptionalRowLayers();
        if (typeof window.__pdPdSummaryRefreshLayoutAfterVisibility === "function") {
            window.__pdPdSummaryRefreshLayoutAfterVisibility();
        }
    }
    window.__pdPdSummaryApplyChiVisibility = applyPdPdChiVisibility;
    if (pdPdChiBtn) {
        syncPdPdChiToggleUi();
        pdPdChiBtn.addEventListener("click", function () {
            window.__pdPdSummaryChiMode = !window.__pdPdSummaryChiMode;
            try {
                sessionStorage.setItem(
                    pdPdChiStorageKey,
                    window.__pdPdSummaryChiMode ? "1" : "0"
                );
            } catch (ePdPdChiSt) { /* */ }
            if (window.__pdPdSummaryChiMode) {
                enableNtDetailForChiVariants();
            }
            var applyChi = function () {
                syncPdPdChiToggleUi();
                if (typeof window.__pdPdSummaryReapplyRowVisibility === "function") {
                    window.__pdPdSummaryReapplyRowVisibility();
                } else {
                    applyPdPdChiVisibility();
                }
            };
            if (
                window.__pdPdSummaryChiMode &&
                typeof window.__pdSummaryEnsureSegments === "function"
            ) {
                var chiSegments =
                    summaryView === "oes" || summaryView === "fo"
                        ? ["nt_extra", "chi"]
                        : ["chi"];
                window.__pdSummaryEnsureSegments(chiSegments).then(applyChi, applyChi);
            } else {
                applyChi();
            }
        });
    }

    var pdPdCalcMaxStorageKey =
        "pdPdSummaryCalcMax_" +
        (summaryTable.getAttribute("data-summary-view") || "oes") +
        "_" +
        (summaryTable.getAttribute("data-summary-route-variant") || "max");
    try {
        window.__pdPdSummaryCalcMaxMode =
            sessionStorage.getItem(pdPdCalcMaxStorageKey) === "1";
    } catch (ePdPdCalcMaxInitEarly) {
        window.__pdPdSummaryCalcMaxMode = false;
    }
    var pdPdVerificationStorageKey =
        "pdPdSummaryVerification_" +
        (summaryTable.getAttribute("data-summary-view") || "oes") +
        "_" +
        (summaryTable.getAttribute("data-summary-route-variant") || "max");
    try {
        window.__pdPdSummaryVerificationMode =
            sessionStorage.getItem(pdPdVerificationStorageKey) === "1";
    } catch (ePdPdVerInitEarly) {
        window.__pdPdSummaryVerificationMode = false;
    }

    function pdSummaryStoredOptionalSegmentsFromSession() {
        var segs = [];
        if (window.__pdPdSummaryNtDetailMode === true) {
            segs.push("nt_extra");
        }
        if (window.__pdPdSummaryCalcMaxMode === true) {
            segs.push("calc_max");
        }
        if (window.__pdPdSummaryEeMode === true) {
            if (
                (summaryView === "oes" || summaryView === "fo") &&
                segs.indexOf("nt_extra") < 0
            ) {
                segs.push("nt_extra");
            }
            segs.push("ee");
        }
        if (window.__pdPdSummaryChiMode === true) {
            if (
                (summaryView === "oes" || summaryView === "fo") &&
                segs.indexOf("nt_extra") < 0
            ) {
                segs.push("nt_extra");
            }
            segs.push("chi");
        }
        if (window.__pdPdSummaryVerificationMode === true) {
            segs.push("verify");
            if (segs.indexOf("calc_max") < 0) {
                segs.push("calc_max");
            }
        }
        return segs;
    }

    function pdSummaryMergeSegmentNames(baseSegs, extraSegs) {
        var out = (baseSegs || []).slice();
        (extraSegs || []).forEach(function (seg) {
            if (seg && out.indexOf(seg) < 0) {
                out.push(seg);
            }
        });
        return out;
    }

    if (typeof window.__pdSummaryEnsureSegments === "function") {
        try {
            window.__pdPdSummaryDeferSegmentVisibility = true;
            var sessionOptionalSegments = pdSummaryStoredOptionalSegmentsFromSession();
            if (sessionOptionalSegments.length) {
                await window.__pdSummaryEnsureSegments(sessionOptionalSegments);
            }
        } catch (eEarlyOptionalSeg) { /* */ }
    }

    if (summaryView === "oes") {
        initPdSummaryRowPicker({
            rowKeys: ["max_power", "calculated_max_power_mw", "peak_datetime", "calculated_max_power_consumption_mw", "avg_temp", "combined_on_oes", "combined_on_ees", "calculated_combined_on_ees_mw", "calculated_max_ees_via_oes_mw", "calculated_max_ees_russia_mw", "calculated_max_ees_via_es_mw", "combined_on_es"],
            defaultHiddenKeys: rowPickerDefaultHidden,
            storageKey: routeVariant === "coeff" ? "powerDemandSummaryOesCoeffVisibleRowKeysV2" : "powerDemandSummaryOesVisibleRowKeysV3",
            modalId: "powerDemandOesRowsModal",
            applyBtnId: "powerDemandOesRowsApply"
        });
    } else if (summaryView === "fo") {
        var foRowKeys = [
            "max_power",
            "calculated_max_power_mw",
            "calculated_max_power_consumption_mw",
            "peak_datetime",
            "avg_temp",
            "combined_on_cz",
            "calculated_combined_on_cz_mw",
            "combined_on_fo",
            "calculated_max_ees_via_oes_mw",
            "calculated_max_ees_russia_mw",
            "calculated_max_ees_via_es_mw",
            "cz_calculated_max_cz_russia_mw",
        ];
        initPdSummaryRowPicker({
            rowKeys: foRowKeys,
            defaultHiddenKeys: rowPickerDefaultHidden,
            storageKey: routeVariant === "coeff" ? "powerDemandSummaryFoCoeffVisibleRowKeysV4" : "powerDemandSummaryFoVisibleRowKeysV2",
            modalId: "powerDemandFoRowsModal",
            applyBtnId: "powerDemandFoRowsApply"
        });
    } else if (summaryView === "ez") {
        initPdSummaryRowPicker({
            rowKeys: [
                "max_power",
                "calculated_max_power_mw",
                "calculated_max_power_consumption_mw",
                "peak_datetime",
                "avg_temp",
                "combined_on_ez",
                "combined_on_ees",
                "calculated_combined_on_ees_mw",
                "calculated_max_ees_via_oes_mw",
                "calculated_max_ees_russia_mw",
                "calculated_max_ees_via_es_mw",
                "calculated_max_ees_via_ez_mw",
            ],
            defaultHiddenKeys: rowPickerDefaultHidden,
            storageKey: routeVariant === "coeff" ? "powerDemandSummaryEzCoeffVisibleRowKeysV2" : "powerDemandSummaryEzVisibleRowKeysV2",
            modalId: "powerDemandEzRowsModal",
            applyBtnId: "powerDemandEzRowsApply"
        });
    }

    var ntDetailBtn = document.getElementById("pdPdSummaryNtDetailToggle");
    if (ntDetailBtn) {
        function pdPdNtDetailUiIsOn() {
            return (
                window.__pdPdSummaryNtDetailMode === true ||
                ntDetailBtn.getAttribute("aria-pressed") === "true" ||
                ntDetailBtn.classList.contains("btn-primary")
            );
        }
        function syncPdPdNtDetailToggleUi() {
            var on = window.__pdPdSummaryNtDetailMode === true;
            ntDetailBtn.setAttribute("aria-pressed", on ? "true" : "false");
            ntDetailBtn.classList.toggle("btn-primary", on);
            ntDetailBtn.classList.toggle("btn-outline-secondary", !on);
        }
        function reapplyPdPdNtDetailVisibility() {
            if (typeof window.__pdPdSummaryReapplyRowVisibility === "function") {
                window.__pdPdSummaryReapplyRowVisibility();
            } else {
                syncPdPdNtAdjustedEntityLabels();
            }
        }
        function reapplyPdPdNtDetailVisibilitySoon() {
            reapplyPdPdNtDetailVisibility();
            if (typeof window.requestAnimationFrame === "function") {
                window.requestAnimationFrame(reapplyPdPdNtDetailVisibility);
            }
            window.setTimeout(reapplyPdPdNtDetailVisibility, 50);
        }
        function ensurePdPdNtDetailRowsVisible() {
            if (pdPdNtDetailUiIsOn()) {
                window.__pdPdSummaryNtDetailMode = true;
                try {
                    sessionStorage.setItem(pdPdNtStorageKey, "1");
                } catch (eNtSyncSt) { /* */ }
            }
            syncPdPdNtDetailToggleUi();
            if (
                window.__pdPdSummaryNtDetailMode &&
                typeof window.__pdSummaryEnsureSegments === "function"
            ) {
                window.__pdSummaryEnsureSegments(["nt_extra"]).then(
                    reapplyPdPdNtDetailVisibilitySoon,
                    reapplyPdPdNtDetailVisibilitySoon
                );
            } else {
                reapplyPdPdNtDetailVisibilitySoon();
            }
        }
        function syncPdPdNtDetailAfterRowsRendered() {
            // Do not call ensureSegments here: merge of nt_extra dispatches
            // pd-summary-rows-rendered and would remesh in an infinite loop.
            if (pdPdNtDetailUiIsOn()) {
                window.__pdPdSummaryNtDetailMode = true;
                try {
                    sessionStorage.setItem(pdPdNtStorageKey, "1");
                } catch (eNtSyncRender) { /* */ }
            }
            syncPdPdNtDetailToggleUi();
            reapplyPdPdNtDetailVisibilitySoon();
        }
        if (pdPdNtDetailUiIsOn()) {
            window.__pdPdSummaryNtDetailMode = true;
        }
        syncPdPdNtDetailToggleUi();
        ntDetailBtn.addEventListener("click", function () {
            window.__pdPdSummaryNtDetailMode = !window.__pdPdSummaryNtDetailMode;
            try {
                sessionStorage.setItem(pdPdNtStorageKey, window.__pdPdSummaryNtDetailMode ? "1" : "0");
            } catch (eNtSt) { /* */ }
            syncPdPdNtDetailToggleUi();
            ensurePdPdNtDetailRowsVisible();
        });
        document.addEventListener(
            "pd-summary-rows-rendered",
            syncPdPdNtDetailAfterRowsRendered
        );
        ensurePdPdNtDetailRowsVisible();
    }

    // Кнопка «Варианты периметра» — столбец «Варианты периметра»
    var pdPdPerimeterVariantBtn = document.getElementById("pdPdSummaryPerimeterVariantToggle");
    var pdPdPerimeterVariantStorageKey =
        "pdPdSummaryPerimeterVariant_" +
        (summaryTable.getAttribute("data-summary-view") || "oes") +
        "_" +
        (summaryTable.getAttribute("data-summary-route-variant") || "max");
    try {
        window.__pdPdSummaryPerimeterVariantMode =
            sessionStorage.getItem(pdPdPerimeterVariantStorageKey) === "1";
    } catch (ePdPdPvInit) {
        window.__pdPdSummaryPerimeterVariantMode = false;
    }
    function syncPdPdPerimeterVariantToggleUi() {
        if (!pdPdPerimeterVariantBtn) {
            return;
        }
        var on = window.__pdPdSummaryPerimeterVariantMode === true;
        pdPdPerimeterVariantBtn.setAttribute("aria-pressed", on ? "true" : "false");
        pdPdPerimeterVariantBtn.classList.toggle("btn-info", on);
        pdPdPerimeterVariantBtn.classList.toggle("btn-outline-info", !on);
    }
    function applyPdPdPerimeterVariantColVisibility() {
        if (!summaryTable) {
            return;
        }
        summaryTable.classList.toggle(
            "pd-summary-perimeter-variant-col-hidden",
            window.__pdPdSummaryPerimeterVariantMode !== true
        );
        if (typeof window.__pdPdSummaryRefreshLayoutAfterVisibility === "function") {
            window.__pdPdSummaryRefreshLayoutAfterVisibility();
        }
    }
    window.__pdPdSummaryApplyPerimeterVariantColVisibility = applyPdPdPerimeterVariantColVisibility;
    if (pdPdPerimeterVariantBtn) {
        syncPdPdPerimeterVariantToggleUi();
        applyPdPdPerimeterVariantColVisibility();
        pdPdPerimeterVariantBtn.addEventListener("click", function () {
            window.__pdPdSummaryPerimeterVariantMode = !window.__pdPdSummaryPerimeterVariantMode;
            try {
                sessionStorage.setItem(
                    pdPdPerimeterVariantStorageKey,
                    window.__pdPdSummaryPerimeterVariantMode ? "1" : "0"
                );
            } catch (ePdPdPvSt) { /* */ }
            syncPdPdPerimeterVariantToggleUi();
            applyPdPdPerimeterVariantColVisibility();
        });
        document.addEventListener("pd-summary-rows-rendered", applyPdPdPerimeterVariantColVisibility);
    }

    // Кнопка «Исторические максимумы» — столбец «Исторический собственный максимум»
    var pdPdHistBtn = document.getElementById("pdPdSummaryHistToggle");
    var pdPdHistStorageKey =
        "pdPdSummaryHist_" +
        (summaryTable.getAttribute("data-summary-view") || "oes") +
        "_" +
        (summaryTable.getAttribute("data-summary-route-variant") || "max");
    try {
        window.__pdPdSummaryHistMode = sessionStorage.getItem(pdPdHistStorageKey) === "1";
    } catch (ePdPdHistInit) {
        window.__pdPdSummaryHistMode = false;
    }
    function syncPdPdHistToggleUi() {
        if (!pdPdHistBtn) {
            return;
        }
        var on = window.__pdPdSummaryHistMode === true;
        pdPdHistBtn.setAttribute("aria-pressed", on ? "true" : "false");
        pdPdHistBtn.classList.toggle("btn-secondary", on);
        pdPdHistBtn.classList.toggle("btn-outline-secondary", !on);
    }
    function applyPdPdHistColVisibility() {
        if (!summaryTable) {
            return;
        }
        summaryTable.classList.toggle(
            "pd-summary-hist-col-hidden",
            window.__pdPdSummaryHistMode !== true
        );
        if (typeof window.__pdPdSummaryRefreshLayoutAfterVisibility === "function") {
            window.__pdPdSummaryRefreshLayoutAfterVisibility();
        }
    }
    window.__pdPdSummaryApplyHistColVisibility = applyPdPdHistColVisibility;
    if (pdPdHistBtn) {
        syncPdPdHistToggleUi();
        applyPdPdHistColVisibility();
        pdPdHistBtn.addEventListener("click", function () {
            window.__pdPdSummaryHistMode = !window.__pdPdSummaryHistMode;
            try {
                sessionStorage.setItem(
                    pdPdHistStorageKey,
                    window.__pdPdSummaryHistMode ? "1" : "0"
                );
            } catch (ePdPdHistSt) { /* */ }
            syncPdPdHistToggleUi();
            applyPdPdHistColVisibility();
        });
        document.addEventListener("pd-summary-rows-rendered", applyPdPdHistColVisibility);
    }

    // Кнопка «Расчетные максимумы» (/summary/oes/, не coeff)
    var pdPdCalcMaxBtn = document.getElementById("pdPdSummaryCalcMaxToggle");
    function syncPdPdCalcMaxToggleUi() {
        if (!pdPdCalcMaxBtn) {
            return;
        }
        var on = window.__pdPdSummaryCalcMaxMode === true;
        pdPdCalcMaxBtn.setAttribute("aria-pressed", on ? "true" : "false");
        pdPdCalcMaxBtn.classList.toggle("btn-success", on);
        pdPdCalcMaxBtn.classList.toggle("btn-outline-success", !on);
    }
    function applyPdPdCalcMaxVisibility() {
        pdSummaryApplyOptionalRowLayers();
        if (typeof window.__pdPdSummaryRefreshLayoutAfterVisibility === "function") {
            window.__pdPdSummaryRefreshLayoutAfterVisibility();
        }
    }
    window.__pdPdSummaryApplyCalcMaxVisibility = applyPdPdCalcMaxVisibility;
    if (pdPdCalcMaxBtn) {
        syncPdPdCalcMaxToggleUi();
        pdPdCalcMaxBtn.addEventListener("click", function () {
            window.__pdPdSummaryCalcMaxMode = !window.__pdPdSummaryCalcMaxMode;
            try {
                sessionStorage.setItem(
                    pdPdCalcMaxStorageKey,
                    window.__pdPdSummaryCalcMaxMode ? "1" : "0"
                );
            } catch (ePdPdCalcMaxSt) { /* */ }
            var applyCalcMax = function () {
                syncPdPdCalcMaxToggleUi();
                if (typeof window.__pdPdSummarySetCalcMaxRowKeysVisible === "function") {
                    window.__pdPdSummarySetCalcMaxRowKeysVisible(
                        window.__pdPdSummaryCalcMaxMode === true
                    );
                } else if (typeof window.__pdPdSummaryReapplyRowVisibility === "function") {
                    window.__pdPdSummaryReapplyRowVisibility();
                } else {
                    applyPdPdCalcMaxVisibility();
                }
            };
            if (
                window.__pdPdSummaryCalcMaxMode &&
                typeof window.__pdSummaryEnsureSegments === "function"
            ) {
                window.__pdSummaryEnsureSegments(["calc_max"]).then(
                    applyCalcMax,
                    applyCalcMax
                );
            } else {
                applyCalcMax();
            }
        });
    }

    // Кнопка «Проверка» (по аналогии с energy_consumption/summary/oes)
    var pdPdVerificationBtn = document.getElementById("pdPdSummaryVerificationToggle");
    function syncPdPdVerificationToggleUi() {
        if (!pdPdVerificationBtn) {
            return;
        }
        var on = window.__pdPdSummaryVerificationMode === true;
        pdPdVerificationBtn.setAttribute("aria-pressed", on ? "true" : "false");
        pdPdVerificationBtn.classList.toggle("btn-info", on);
        pdPdVerificationBtn.classList.toggle("btn-outline-info", !on);
    }
    function applyPdPdVerificationVisibility() {
        pdSummaryApplyOptionalRowLayers();
        if (typeof window.__pdPdSummaryRefreshLayoutAfterVisibility === "function") {
            window.__pdPdSummaryRefreshLayoutAfterVisibility();
        }
    }
    window.__pdPdSummaryApplyVerificationVisibility = applyPdPdVerificationVisibility;
    if (pdPdVerificationBtn) {
        syncPdPdVerificationToggleUi();
        pdPdVerificationBtn.addEventListener("click", function () {
            window.__pdPdSummaryVerificationMode = !window.__pdPdSummaryVerificationMode;
            try {
                sessionStorage.setItem(
                    pdPdVerificationStorageKey,
                    window.__pdPdSummaryVerificationMode ? "1" : "0"
                );
            } catch (ePdPdVerSt) { /* */ }
            var applyVerify = function () {
                syncPdPdVerificationToggleUi();
                if (typeof window.__pdPdSummaryReapplyRowVisibility === "function") {
                    window.__pdPdSummaryReapplyRowVisibility();
                } else {
                    applyPdPdVerificationVisibility();
                }
                if (
                    window.__pdPdSummaryVerificationMode &&
                    typeof window.__pdPdOesMaxRefreshVerification === "function"
                ) {
                    window.__pdPdOesMaxRefreshVerification();
                }
            };
            if (
                window.__pdPdSummaryVerificationMode &&
                typeof window.__pdSummaryEnsureSegments === "function"
            ) {
                window.__pdSummaryEnsureSegments(["calc_max", "verify"]).then(
                    applyVerify,
                    applyVerify
                );
            } else {
                applyVerify();
            }
        });
    }

    if (typeof window.__pdSummaryEnsureSegments === "function") {
        try {
            var rowPickerOptionalSegments = [];
            if (typeof window.__pdPdSummarySegmentsForVisibleRows === "function") {
                window.__pdPdSummarySegmentsForVisibleRows().forEach(function (seg) {
                    if (rowPickerOptionalSegments.indexOf(seg) < 0) {
                        rowPickerOptionalSegments.push(seg);
                    }
                });
            }
            rowPickerOptionalSegments = pdSummaryMergeSegmentNames(
                [],
                rowPickerOptionalSegments
            ).filter(function (seg) {
                return (
                    pdSummaryStoredOptionalSegmentsFromSession().indexOf(seg) < 0
                );
            });
            if (rowPickerOptionalSegments.length) {
                await window.__pdSummaryEnsureSegments(rowPickerOptionalSegments);
            }
        } catch (eRowPickerSeg) { /* */ }
    }
    window.__pdPdSummaryDeferSegmentVisibility = false;
    if (typeof window.__pdPdSummaryReapplyRowVisibility === "function") {
        window.__pdPdSummaryReapplyRowVisibility();
    }
    if (typeof window.pdSummarySyncAggregationLevelColspans === "function") {
        window.pdSummarySyncAggregationLevelColspans();
    }
    // После optional-сегментов и финальной видимости — финальный scroll restore после save.
    window.requestAnimationFrame(function () {
        if (window.armGsPageScrollRestore) {
            var settledTable = document.getElementById("powerDemandSummaryTable");
            if (settledTable) {
                var settledWrap = document.getElementById("powerDemandSummaryScrollWrap");
                var settledVScroll =
                    (settledWrap
                        && settledWrap.classList.contains("pd-coeff-summary-scroll-wrap"))
                        ? settledWrap
                        : document.querySelector(".page-table-scroll");
                window.armGsPageScrollRestore.restore(
                    window.armGsPageScrollRestore.defaultScope(settledTable),
                    {
                        table: settledTable,
                        hScrollEl: settledWrap || undefined,
                        vScrollEl: settledVScroll || undefined,
                        consume: true
                    }
                );
            }
        }
        document.dispatchEvent(new CustomEvent("pd-summary-ui-settled"));
    });

}
})();
