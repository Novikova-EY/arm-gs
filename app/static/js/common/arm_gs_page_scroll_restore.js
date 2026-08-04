/**
 * Восстановление прокрутки после сохранения (POST / reload).
 * Учитывает wrapTablePages() в base.html — restore только после window.load.
 */
(function (window, document) {
    "use strict";

    var PREFIX = "armGsScrollRestore_";
    var LOAD_RETRY_MS = [0, 60, 280, 450];
    var FINAL_CONSUME_MS = 8000;
    var scheduledScopes = Object.create(null);
    var lastFocusedEditable = null;

    document.addEventListener("focusin", function (e) {
        var t = e.target;
        if (
            t &&
            t.matches &&
            (
                t.matches(".fuel-param-input") ||
                t.matches("input.fuel-param-input") ||
                t.matches("textarea.fuel-param-input") ||
                t.matches(".ec-formula-text-input")
            )
        ) {
            lastFocusedEditable = t;
        }
    }, true);

    function storageKey(scope) {
        return PREFIX + scope;
    }

    function trySession(key) {
        try {
            return sessionStorage.getItem(key);
        } catch (e) {
            return null;
        }
    }

    function setSession(key, val) {
        try {
            sessionStorage.setItem(key, val);
        } catch (e) {}
    }

    function removeSession(key) {
        try {
            sessionStorage.removeItem(key);
        } catch (e) {}
    }

    function defaultScope(tableEl) {
        var base = window.location.pathname;
        if (tableEl) {
            var view = tableEl.getAttribute("data-summary-view");
            if (view) {
                var variant = tableEl.getAttribute("data-summary-route-variant") || "max";
                return base + ":" + view + ":" + variant;
            }
        }
        return base;
    }

    function clear(scope) {
        if (!scope) {
            var table = getTableEl();
            scope = defaultScope(table);
        }
        removeSession(storageKey(scope));
        scheduledScopes[scope] = false;
    }

    /**
     * Сброс вертикального скролла таблицы к верху.
     * На max/oes/fo/ez скролл у .page-table-scroll; на coeff — у .pd-coeff-summary-scroll-wrap.
     */
    function scrollTableTop(opts) {
        opts = opts || {};
        var vScroll = getVScrollEl(opts);
        var hScroll = getHScrollEl(opts);
        if (vScroll) {
            vScroll.scrollTop = 0;
        } else {
            window.scrollTo(0, 0);
        }
        if (hScroll) {
            hScroll.scrollLeft = 0;
        }
    }

    function buildSummaryRowAnchor(tr) {
        if (!tr) {
            return null;
        }
        var pk = tr.getAttribute("data-parameter-key");
        if (!pk) {
            return null;
        }
        var parts = ["pk:" + pk];
        [
            "data-id-union-energy-system",
            "data-id-regional-energy-system",
            "data-id-regional-district",
            "data-id-energy-unit",
            "data-id-synchronous-area",
            "data-perimeter-variant-code",
            "data-parent-id",
            "data-parent-fk-column"
        ].forEach(function (attr) {
            var v = tr.getAttribute(attr);
            if (v) {
                parts.push(attr + ":" + v);
            }
        });
        return parts.join("|");
    }

    function buildGenericRowAnchor(tr) {
        if (!tr) {
            return null;
        }
        var summary = buildSummaryRowAnchor(tr);
        if (summary) {
            return summary;
        }

        var vi = tr.querySelector('input[name="ved_id[]"]');
        if (vi) {
            var tk = tr.querySelector('input[name="territory_kind[]"]');
            var ti = tr.querySelector('input[name="territory_id[]"]');
            return "ved|" + (tk ? tk.value : "") + "|" + (ti ? ti.value : "") + "|" + vi.value;
        }

        var fd = tr.querySelector('input[name="fd_id[]"]');
        if (fd) {
            return "fd|" + fd.value;
        }

        var rk = tr.querySelector('input[name="row_kind[]"]');
        if (rk) {
            var tkEi = tr.querySelector('input[name="territory_kind[]"]');
            var tiEi = tr.querySelector('input[name="territory_id[]"]');
            var viEi = tr.querySelector('input[name="cell_ved_id[]"]');
            return "ei|"
                + (tkEi ? tkEi.value : "")
                + "|"
                + (tiEi ? tiEi.value : "")
                + "|"
                + (viEi ? viEi.value : "")
                + "|"
                + rk.value;
        }

        var coefTk = tr.querySelector('input[name="coef_territory_kind[]"]');
        if (coefTk) {
            var coefTi = tr.querySelector('input[name="coef_territory_id[]"]');
            var coefVi = tr.querySelector('input[name="coef_ved_id[]"]');
            return "coef|"
                + coefTk.value
                + "|"
                + (coefTi ? coefTi.value : "")
                + "|"
                + (coefVi ? coefVi.value : "");
        }

        var fdTotalK = tr.querySelector('input[name="fd_total_k_row_kind[]"]');
        if (fdTotalK) {
            var fdTk = tr.querySelector('input[name="fd_total_k_territory_kind[]"]');
            var fdTi = tr.querySelector('input[name="fd_total_k_territory_id[]"]');
            return "fd_k|"
                + (fdTk ? fdTk.value : "")
                + "|"
                + (fdTi ? fdTi.value : "")
                + "|"
                + fdTotalK.value;
        }

        var rowKey = tr.getAttribute("data-formula-key");
        if (rowKey) {
            return "formula:" + rowKey;
        }

        var tbody = tr.closest("tbody");
        if (tbody) {
            var rows = tbody.querySelectorAll("tr");
            for (var i = 0; i < rows.length; i++) {
                if (rows[i] === tr) {
                    return "rowidx:" + i;
                }
            }
        }
        return null;
    }

    function findRowByAnchor(root, anchor) {
        if (!root || !anchor) {
            return null;
        }
        if (anchor.indexOf("pk:") === 0) {
            var rows = root.querySelectorAll("tr[data-parameter-key]");
            for (var i = 0; i < rows.length; i++) {
                if (buildSummaryRowAnchor(rows[i]) === anchor) {
                    return rows[i];
                }
            }
            return null;
        }
        if (anchor.indexOf("formula:") === 0) {
            var key = anchor.slice(8).replace(/\\/g, "\\\\").replace(/"/g, '\\"');
            return root.querySelector('tr[data-formula-key="' + key + '"]');
        }
        if (anchor.indexOf("rowidx:") === 0) {
            var idx = parseInt(anchor.slice(7), 10);
            var tbody = root.querySelector("tbody");
            if (tbody && !Number.isNaN(idx)) {
                var trs = tbody.querySelectorAll("tr");
                return trs[idx] || null;
            }
        }
        if (anchor.indexOf("ved|") === 0) {
            var rows2 = root.querySelectorAll("tbody tr");
            for (var j = 0; j < rows2.length; j++) {
                var r = rows2[j];
                var v = r.querySelector('input[name="ved_id[]"]');
                if (!v) {
                    continue;
                }
                var tk2 = r.querySelector('input[name="territory_kind[]"]');
                var ti2 = r.querySelector('input[name="territory_id[]"]');
                var a = "ved|" + (tk2 ? tk2.value : "") + "|" + (ti2 ? ti2.value : "") + "|" + v.value;
                if (a === anchor) {
                    return r;
                }
            }
        }
        if (anchor.indexOf("fd|") === 0) {
            var fdId = anchor.slice(3);
            var rows3 = root.querySelectorAll("tbody tr");
            for (var k = 0; k < rows3.length; k++) {
                var fdInp = rows3[k].querySelector('input[name="fd_id[]"]');
                if (fdInp && fdInp.value === fdId) {
                    return rows3[k];
                }
            }
        }
        if (anchor.indexOf("ei|") === 0) {
            var rows4 = root.querySelectorAll("tbody tr");
            for (var m = 0; m < rows4.length; m++) {
                if (buildGenericRowAnchor(rows4[m]) === anchor) {
                    return rows4[m];
                }
            }
        }
        if (anchor.indexOf("coef|") === 0) {
            var rows5 = root.querySelectorAll("tbody tr");
            for (var n = 0; n < rows5.length; n++) {
                if (buildGenericRowAnchor(rows5[n]) === anchor) {
                    return rows5[n];
                }
            }
        }
        if (anchor.indexOf("fd_k|") === 0) {
            var rows6 = root.querySelectorAll("tbody tr");
            for (var p = 0; p < rows6.length; p++) {
                if (buildGenericRowAnchor(rows6[p]) === anchor) {
                    return rows6[p];
                }
            }
        }
        return null;
    }

    function pickBottomMostElement(elements) {
        if (!elements || !elements.length) {
            return null;
        }
        if (elements.length === 1) {
            return elements[0];
        }
        var best = elements[0];
        var bestTop = best.getBoundingClientRect().top;
        for (var i = 1; i < elements.length; i++) {
            var top = elements[i].getBoundingClientRect().top;
            if (top > bestTop) {
                bestTop = top;
                best = elements[i];
            }
        }
        return best;
    }

    function resolveAnchorElement(opts) {
        opts = opts || {};
        if (opts.anchorElement && opts.anchorElement.closest) {
            return opts.anchorElement;
        }
        if (opts.changedInputs && opts.changedInputs.length) {
            return pickBottomMostElement(opts.changedInputs);
        }
        var active = document.activeElement;
        if (
            active &&
            active.closest &&
            active.matches &&
            (
                active.matches(".fuel-param-input") ||
                active.matches("input.fuel-param-input") ||
                active.matches("textarea.fuel-param-input") ||
                active.matches(".ec-formula-text-input")
            )
        ) {
            return active;
        }
        if (lastFocusedEditable && lastFocusedEditable.isConnected) {
            return lastFocusedEditable;
        }
        return null;
    }

    function getVScrollEl(opts) {
        if (opts && opts.vScrollEl) {
            return opts.vScrollEl;
        }
        var coeffWrap = document.querySelector(
            ".page-table-scroll .pd-coeff-summary-scroll-wrap"
        );
        if (coeffWrap) {
            return coeffWrap;
        }
        return document.querySelector(".page-table-scroll");
    }

    function getHScrollEl(opts) {
        if (opts && opts.hScrollEl) {
            var explicit = opts.hScrollEl;
            // На max/oes/fo/ez wrap с overflow:visible — X-скролл у .page-table-scroll.
            if (
                explicit
                && explicit.id === "powerDemandSummaryScrollWrap"
                && !(
                    explicit.classList
                    && explicit.classList.contains("pd-coeff-summary-scroll-wrap")
                )
            ) {
                var pageWrap = document.querySelector(".page-table-scroll");
                if (pageWrap) {
                    return pageWrap;
                }
            }
            return explicit;
        }
        var host = document.querySelector(
            ".page-table-scroll .pd-summary-table-x-scroll-host, "
            + ".page-table-scroll .pd-coeff-summary-scroll-wrap"
        );
        if (host) {
            return host;
        }
        return document.querySelector(".page-table-scroll");
    }

    function getTableEl(opts) {
        if (opts && opts.table) {
            return opts.table;
        }
        return document.getElementById("powerDemandSummaryTable")
            || document.querySelector("table.power-demand-summary-table");
    }

    function isPdSummaryClientRenderPage() {
        return !!document.getElementById("pd-summary-client-render-config");
    }

    function isPdSummaryClientRenderPending() {
        if (!isPdSummaryClientRenderPage()) {
            return false;
        }
        var shell = document.getElementById("powerDemandSummaryLoaderShell");
        return !!(shell && shell.dataset.ready !== "1");
    }

    function isPdSummaryUiSettling() {
        return window.__pdPdSummaryDeferSegmentVisibility === true;
    }

    /**
     * На PD client-render не снимаем sessionStorage, пока:
     * - shell ещё не ready, или
     * - ещё грузятся optional-сегменты / финальная видимость, или
     * - якорь строки задан, но строка ещё не в DOM.
     * Иначе restore «успешен» по scrollTop=0 у .page-table-scroll (coeff)
     * и позиция после save теряется.
     */
    function shouldDeferPdSummaryConsume(state, result) {
        if (!state || !isPdSummaryClientRenderPage()) {
            return false;
        }
        if (isPdSummaryClientRenderPending() || isPdSummaryUiSettling()) {
            return true;
        }
        if (state.rowAnchor && !(result && result.rowFound)) {
            return true;
        }
        return false;
    }

    function save(opts) {
        opts = opts || {};
        var table = getTableEl(opts);
        var scope = opts.scope || defaultScope(table);
        var vScroll = getVScrollEl(opts);
        var hScroll = getHScrollEl(opts);
        var anchorEl = resolveAnchorElement(opts);
        var anchorTr = anchorEl && anchorEl.closest ? anchorEl.closest("tr") : null;
        setSession(storageKey(scope), JSON.stringify({
            rowAnchor: buildGenericRowAnchor(anchorTr),
            scrollTop: vScroll ? vScroll.scrollTop : (window.scrollY || 0),
            scrollLeft: hScroll ? hScroll.scrollLeft : 0,
            tableSelector: table && table.id ? ("#" + table.id) : null
        }));
        return scope;
    }

    function applyRestoreState(state, opts) {
        var table = getTableEl(opts);
        if (!table && state.tableSelector) {
            table = document.querySelector(state.tableSelector);
        }
        var vScroll = getVScrollEl(opts);
        var hScroll = getHScrollEl(opts);
        var root = table || document;
        var rowFound = false;

        if (state.rowAnchor) {
            var row = findRowByAnchor(root, state.rowAnchor);
            if (row) {
                row.scrollIntoView({ block: "center", inline: "nearest" });
                rowFound = true;
            }
        }
        var scrollApplied = false;
        if (!rowFound && typeof state.scrollTop === "number") {
            if (vScroll) {
                vScroll.scrollTop = state.scrollTop;
                scrollApplied = true;
            } else if (!state.rowAnchor) {
                window.scrollTo(0, state.scrollTop);
                scrollApplied = true;
            }
        }
        if (typeof state.scrollLeft === "number" && hScroll) {
            hScroll.scrollLeft = state.scrollLeft;
        }
        if (typeof window.refreshPowerDemandSummaryLayout === "function") {
            window.refreshPowerDemandSummaryLayout();
        }
        // Если цель — конкретная строка, «успех» только при её нахождении.
        // Иначе scrollTop (часто 0 на coeff) раньше считался успехом и consume
        // убивал состояние до появления строки в DOM.
        var success = state.rowAnchor ? rowFound : (rowFound || scrollApplied);
        return {
            rowFound: rowFound,
            scrollApplied: scrollApplied,
            success: success
        };
    }

    function restore(scope, opts) {
        opts = opts || {};
        var consume = opts.consume === true;
        var forceConsume = opts.forceConsume === true;
        var key = storageKey(scope);
        var raw = trySession(key);
        if (!raw) {
            return { hadState: false, success: false };
        }
        var state;
        try {
            state = JSON.parse(raw);
        } catch (e) {
            if (consume || forceConsume) {
                removeSession(key);
            }
            return { hadState: false, success: false };
        }

        var result = applyRestoreState(state, opts);
        window.requestAnimationFrame(function () {
            var again = applyRestoreState(state, opts);
            if (again.success) {
                result.success = true;
                result.rowFound = result.rowFound || again.rowFound;
                result.scrollApplied = result.scrollApplied || again.scrollApplied;
            }
        });

        if (((consume && result.success) || forceConsume) && !shouldDeferPdSummaryConsume(state, result)) {
            removeSession(key);
        }
        result.hadState = true;
        return result;
    }

    function scheduleRestore(scope, opts) {
        if (!trySession(storageKey(scope))) {
            return;
        }
        if (scheduledScopes[scope]) {
            return;
        }
        scheduledScopes[scope] = true;
        opts = opts || {};

        function clearSchedule() {
            scheduledScopes[scope] = false;
        }

        function tryRestore(consumeOnSuccess, forceConsume) {
            if (!trySession(storageKey(scope))) {
                clearSchedule();
                return false;
            }
            var result = restore(scope, {
                table: opts.table,
                hScrollEl: opts.hScrollEl,
                consume: !!consumeOnSuccess,
                forceConsume: !!forceConsume
            });
            if (consumeOnSuccess && result.success) {
                clearSchedule();
            }
            if (forceConsume) {
                clearSchedule();
            }
            return result.success;
        }

        function afterDeferredContent() {
            if (!trySession(storageKey(scope))) {
                return;
            }
            if (tryRestore(true, false)) {
                return;
            }
            window.requestAnimationFrame(function () {
                tryRestore(true, false);
            });
        }

        function onLoad() {
            tryRestore(false, false);
            LOAD_RETRY_MS.forEach(function (ms) {
                setTimeout(function () {
                    tryRestore(true, false);
                }, ms);
            });

            document.addEventListener("pd-summary-rows-rendered", afterDeferredContent);
            function afterUiSettled() {
                if (!trySession(storageKey(scope))) {
                    return;
                }
                window.requestAnimationFrame(function () {
                    tryRestore(true, false);
                    window.requestAnimationFrame(function () {
                        tryRestore(true, false);
                    });
                });
            }
            document.addEventListener("pd-summary-initial-render-finished", afterUiSettled);
            document.addEventListener("pd-summary-ui-settled", afterUiSettled);

            if (window.__pdSummaryRowsReady && typeof window.__pdSummaryRowsReady.then === "function") {
                window.__pdSummaryRowsReady.then(afterDeferredContent, function () {
                    removeSession(storageKey(scope));
                    clearSchedule();
                });
            }

            setTimeout(function () {
                if (trySession(storageKey(scope))) {
                    tryRestore(false, true);
                }
            }, FINAL_CONSUME_MS);
        }

        if (document.readyState === "complete") {
            onLoad();
        } else {
            window.addEventListener("load", onLoad, { once: true });
        }
    }

    function reload(opts) {
        save(opts);
        window.location.reload();
    }

    function initAutoRestore() {
        var table = getTableEl();
        scheduleRestore(defaultScope(table), { table: table });
    }

    function bindSaveForms() {
        document.addEventListener("submit", function (e) {
            var form = e.target;
            if (!form || form.tagName !== "FORM") {
                return;
            }
            if (form.getAttribute("data-arm-gs-scroll-restore") === "0") {
                return;
            }
            var method = (form.getAttribute("method") || "get").toLowerCase();
            if (method !== "post") {
                return;
            }
            if (!form.querySelector(".fuel-param-input, input.fuel-param-input, textarea.fuel-param-input")) {
                return;
            }
            var table = form.querySelector("#powerDemandSummaryTable, table.power-demand-summary-table");
            save({
                scope: defaultScope(table),
                table: table,
                anchorElement: lastFocusedEditable || document.activeElement
            });
        }, true);
    }

    window.armGsPageScrollRestore = {
        save: save,
        restore: restore,
        schedule: scheduleRestore,
        reload: reload,
        clear: clear,
        scrollTableTop: scrollTableTop,
        defaultScope: defaultScope
    };

    bindSaveForms();
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initAutoRestore);
    } else {
        initAutoRestore();
    }
})(window, document);
