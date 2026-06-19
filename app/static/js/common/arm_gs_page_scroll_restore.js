/**
 * Восстановление прокрутки после сохранения (POST / reload).
 * Учитывает wrapTablePages() в base.html — restore только после window.load.
 */
(function (window, document) {
    "use strict";

    var PREFIX = "armGsScrollRestore_";
    var LOAD_RETRY_MS = [0, 60, 280, 450];
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

    function getHScrollEl(opts) {
        if (opts && opts.hScrollEl) {
            return opts.hScrollEl;
        }
        return document.getElementById("powerDemandSummaryScrollWrap");
    }

    function getTableEl(opts) {
        if (opts && opts.table) {
            return opts.table;
        }
        return document.getElementById("powerDemandSummaryTable")
            || document.querySelector("table.power-demand-summary-table");
    }

    function save(opts) {
        opts = opts || {};
        var table = getTableEl(opts);
        var scope = opts.scope || defaultScope(table);
        var scrollWrap = document.querySelector(".page-table-scroll");
        var hScroll = getHScrollEl(opts);
        var anchorEl = resolveAnchorElement(opts);
        var anchorTr = anchorEl && anchorEl.closest ? anchorEl.closest("tr") : null;
        setSession(storageKey(scope), JSON.stringify({
            rowAnchor: buildGenericRowAnchor(anchorTr),
            scrollTop: scrollWrap ? scrollWrap.scrollTop : (window.scrollY || 0),
            scrollLeft: hScroll ? hScroll.scrollLeft : 0,
            tableSelector: table && table.id ? ("#" + table.id) : null
        }));
        return scope;
    }

    function restore(scope, opts) {
        opts = opts || {};
        var consume = opts.consume !== false;
        var key = storageKey(scope);
        var raw = trySession(key);
        if (!raw) {
            return false;
        }
        var state;
        try {
            state = JSON.parse(raw);
        } catch (e) {
            if (consume) {
                removeSession(key);
            }
            return false;
        }
        var table = getTableEl(opts);
        if (!table && state.tableSelector) {
            table = document.querySelector(state.tableSelector);
        }
        var scrollWrap = document.querySelector(".page-table-scroll");
        var hScroll = getHScrollEl(opts);

        function apply() {
            var restored = false;
            var root = table || document;
            if (state.rowAnchor) {
                var row = findRowByAnchor(root, state.rowAnchor);
                if (row) {
                    row.scrollIntoView({ block: "center", inline: "nearest" });
                    restored = true;
                }
            }
            if (!restored && typeof state.scrollTop === "number") {
                if (scrollWrap) {
                    scrollWrap.scrollTop = state.scrollTop;
                } else {
                    window.scrollTo(0, state.scrollTop);
                }
            }
            if (typeof state.scrollLeft === "number" && hScroll) {
                hScroll.scrollLeft = state.scrollLeft;
            }
            if (typeof window.refreshPowerDemandSummaryLayout === "function") {
                window.refreshPowerDemandSummaryLayout();
            }
        }

        apply();
        window.requestAnimationFrame(function () {
            apply();
        });
        if (consume) {
            removeSession(key);
        }
        return true;
    }

    function scheduleRestore(scope, opts) {
        if (!trySession(storageKey(scope))) {
            return;
        }
        if (scheduledScopes[scope]) {
            return;
        }
        scheduledScopes[scope] = true;

        function attempt(consume) {
            if (!trySession(storageKey(scope))) {
                return;
            }
            restore(scope, Object.assign({}, opts || {}, { consume: consume }));
        }

        function onLoad() {
            attempt(false);
            LOAD_RETRY_MS.forEach(function (ms) {
                setTimeout(function () {
                    attempt(ms === 450);
                }, ms);
            });
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
        defaultScope: defaultScope
    };

    bindSaveForms();
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initAutoRestore);
    } else {
        initAutoRestore();
    }
})(window, document);
