/**
 * Скрытие пустых строк на страницах edit_data и stations_equipment_group_fuel_params
 * (аналог «Пустые строки» в power_demand/summary).
 *
 * Кнопка #fuelEditHideEmptyToggle: нажата = показать пустые.
 * edit_data: по умолчанию пустые показаны; жёлтые (изменение Nуст) всегда видны.
 * fuel_params (data-default-show-empty="0"): по умолчанию скрыты строки,
 * у которых заполнен только код группы (numb / numb1120).
 */
(function () {
    "use strict";

    var HIDDEN_CLASS = "fuel-edit-empty-row-hidden";
    var STORAGE_KEY = "fuelEditShowEmptyRows_v2";
    var DEFAULT_TITLE_ON =
        "Скрыть строки, у которых показатели не заполнены (жёлтые строки изменения Nуст всегда видны)";
    var DEFAULT_TITLE_OFF =
        "Показать строки, у которых показатели не заполнены (жёлтые строки изменения Nуст всегда видны)";

    function tableEl() {
        return (
            document.getElementById("specificFcEditTable") ||
            document.getElementById("fuelParamsTable") ||
            document.getElementById("fuelFormulaTable")
        );
    }

    function toggleBtn() {
        return document.getElementById("fuelEditHideEmptyToggle");
    }

    function attrOr(btn, name, fallback) {
        if (!btn) {
            return fallback;
        }
        var v = btn.getAttribute(name);
        return v == null || v === "" ? fallback : v;
    }

    function defaultShowEmpty(btn) {
        return attrOr(btn, "data-default-show-empty", "1") !== "0";
    }

    function emptyMode(btn) {
        return attrOr(btn, "data-empty-mode", "");
    }

    function toggleStyle(btn) {
        return attrOr(btn, "data-toggle-style", "secondary");
    }

    function storageKey(btn) {
        return attrOr(btn, "data-storage-key", STORAGE_KEY);
    }

    function rowIsYellow(tr) {
        if (tr.getAttribute("data-row-yellow") === "1") {
            return true;
        }
        return !!tr.querySelector("td.table-warning");
    }

    function inputHasValue(el) {
        var v = (el.value || "").trim();
        return v !== "";
    }

    function valueIsMeaningful(raw) {
        var t = String(raw == null ? "" : raw).replace(/\s+/g, " ").trim();
        if (!t || t === "—" || t === "-" || t === "–" || t.toLowerCase() === "none") {
            return false;
        }
        var n = parseFloat(t.replace(/\s/g, "").replace(",", "."));
        if (Number.isFinite(n)) {
            return n !== 0;
        }
        return true;
    }

    function cellHasMeaningfulValue(td) {
        if (!td) {
            return false;
        }
        var col = td.getAttribute("data-column") || "";
        if (col === "numb1120" || col === "numb") {
            return false;
        }
        var inputs = td.querySelectorAll("input, select, textarea");
        var i;
        for (i = 0; i < inputs.length; i++) {
            var el = inputs[i];
            if (el.type === "hidden" && !el.classList.contains("fuel-hier-sum-input")) {
                continue;
            }
            if (valueIsMeaningful(el.value)) {
                return true;
            }
        }
        var derived = td.querySelector(".fuel-param-derived-value, .fuel-hier-sum-value");
        if (derived && valueIsMeaningful(derived.textContent)) {
            return true;
        }
        if (!inputs.length && !derived) {
            return valueIsMeaningful(td.textContent);
        }
        return false;
    }

    function rowIsEmptyOnlyNumb(tr) {
        var tds = tr.querySelectorAll("td");
        for (var i = 0; i < tds.length; i++) {
            var td = tds[i];
            if (!td.getAttribute("data-column")) {
                continue;
            }
            if (cellHasMeaningfulValue(td)) {
                return false;
            }
        }
        return true;
    }

    function rowIsEmpty(tr, mode) {
        if (mode === "only-numb") {
            return rowIsEmptyOnlyNumb(tr);
        }
        var inputs = tr.querySelectorAll(
            "input.form-control, input.fuel-param-input, select.fuel-param-input, select.form-select, textarea.form-control, textarea.fuel-formula-formtxt-input"
        );
        for (var i = 0; i < inputs.length; i++) {
            if (inputHasValue(inputs[i])) {
                return false;
            }
        }
        /* Только годы без записи в БД (data-row-empty); заполненные записи не прячем. */
        return tr.getAttribute("data-row-empty") === "1";
    }

    /**
     * rowspan-ячейки группы (название + код numb1120). При скрытии пустых лет
     * нельзя править только название: иначе код «вылезает» в чужие строки и
     * съезжает сетка (мощность, «Пересчет» и т.д.).
     */
    function collectGroupSpanCells(rows) {
        var cells = [];
        rows.forEach(function (tr) {
            tr.querySelectorAll(
                "td.fuel-param-group-span, td[data-fuel-group-label], td[data-fuel-group-span]"
            ).forEach(function (td) {
                if (cells.indexOf(td) === -1) {
                    cells.push(td);
                }
            });
        });
        cells.sort(function (a, b) {
            var aLabel = a.hasAttribute("data-fuel-group-label") ? 0 : 1;
            var bLabel = b.hasAttribute("data-fuel-group-label") ? 0 : 1;
            return aLabel - bLabel;
        });
        return cells;
    }

    function insertGroupSpanCell(host, td) {
        if (td.hasAttribute("data-fuel-group-label")) {
            host.insertBefore(td, host.firstChild);
            return;
        }
        /* numb1120 и прочие rowspan-ячейки группы — после «Пересчет», иначе год. */
        var anchor =
            host.querySelector("td.fuel-composite-recalc-cell") ||
            host.querySelector("td[data-fuel-group-label]");
        if (anchor && anchor.nextSibling) {
            host.insertBefore(td, anchor.nextSibling);
        } else if (anchor) {
            host.appendChild(td);
        } else {
            host.appendChild(td);
        }
    }

    function fixGroupRowspans(table) {
        var byGroup = {};
        table.querySelectorAll("tbody tr[data-fuel-group-id]").forEach(function (tr) {
            var gid = tr.getAttribute("data-fuel-group-id");
            if (!gid) {
                return;
            }
            if (!byGroup[gid]) {
                byGroup[gid] = [];
            }
            byGroup[gid].push(tr);
        });

        Object.keys(byGroup).forEach(function (gid) {
            var rows = byGroup[gid];
            var visible = rows.filter(function (tr) {
                return !tr.classList.contains(HIDDEN_CLASS);
            });
            var spanCells = collectGroupSpanCells(rows);
            var i;
            for (i = 0; i < rows.length; i++) {
                rows[i].classList.remove("fuel-param-group-last");
            }
            var last = visible.length ? visible[visible.length - 1] : rows[rows.length - 1];
            if (last) {
                last.classList.add("fuel-param-group-last");
            }
            if (!spanCells.length) {
                return;
            }
            var host = visible.length ? visible[0] : rows[0];
            var span = Math.max(visible.length, 1);
            for (i = 0; i < spanCells.length; i++) {
                if (spanCells[i].parentNode) {
                    spanCells[i].parentNode.removeChild(spanCells[i]);
                }
            }
            for (i = 0; i < spanCells.length; i++) {
                spanCells[i].rowSpan = span;
                insertGroupSpanCell(host, spanCells[i]);
            }
        });
    }

    function getGroupLevel(r) {
        var groupRowClasses = ["table-light", "table-primary", "table-secondary"];
        for (var i = 0; i < groupRowClasses.length; i++) {
            if (r.classList.contains(groupRowClasses[i])) {
                return i;
            }
        }
        return -1;
    }

    /**
     * Скрыть заголовки ЕЭС / ОЭС / РЭС, под которыми нет видимых строк данных
     * (иначе при скрытых пустых строках остаётся «лесенка» пустых шапок).
     */
    function hideEmptyHierarchyHeaders(table) {
        var tbody = table.querySelector("tbody");
        if (!tbody) {
            return;
        }
        var allRows = Array.prototype.slice.call(tbody.querySelectorAll("tr"));

        allRows.forEach(function (row) {
            var myLevel = getGroupLevel(row);
            if (myLevel < 0) {
                return;
            }
            var next = row.nextElementSibling;
            var hasVisibleChild = false;
            while (next) {
                var nextLevel = getGroupLevel(next);
                if (nextLevel >= 0 && nextLevel <= myLevel) {
                    break;
                }
                if (
                    next.getAttribute("data-fuel-edit-data-row") === "1" &&
                    !next.classList.contains(HIDDEN_CLASS)
                ) {
                    hasVisibleChild = true;
                    break;
                }
                next = next.nextElementSibling;
            }
            row.classList.toggle(HIDDEN_CLASS, !hasVisibleChild);
        });
    }

    function hideEmptySummaryRows(table, showEmpty) {
        var tbody = table.querySelector("tbody");
        if (!tbody) {
            return;
        }
        tbody.querySelectorAll("tr.fuel-param-summary-row:not([data-fuel-detail-group-id])").forEach(function (sumTr) {
            if (showEmpty) {
                sumTr.classList.remove(HIDDEN_CLASS);
                return;
            }
            var prev = sumTr.previousElementSibling;
            var hasVisibleData = false;
            while (prev) {
                if (getGroupLevel(prev) >= 0) {
                    break;
                }
                if (
                    prev.getAttribute("data-fuel-edit-data-row") === "1" &&
                    !prev.classList.contains(HIDDEN_CLASS)
                ) {
                    hasVisibleData = true;
                    break;
                }
                prev = prev.previousElementSibling;
            }
            sumTr.classList.toggle(HIDDEN_CLASS, !hasVisibleData);
        });
    }

    function applyHideEmptyRows() {
        var table = tableEl();
        var btn = toggleBtn();
        if (!table) {
            return;
        }
        var showEmpty = window.__fuelEditShowEmptyMode === true;
        var mode = emptyMode(btn);
        table.querySelectorAll("tbody tr[data-fuel-edit-data-row]").forEach(function (tr) {
            var hide = !showEmpty && rowIsEmpty(tr, mode) && !rowIsYellow(tr);
            tr.classList.toggle(HIDDEN_CLASS, hide);
        });
        if (mode === "only-numb") {
            hideEmptySummaryRows(table, showEmpty);
        }
        fixGroupRowspans(table);
        hideEmptyHierarchyHeaders(table);
    }

    function syncToggleUi(btn) {
        var on = window.__fuelEditShowEmptyMode === true;
        var style = toggleStyle(btn);
        btn.setAttribute("aria-pressed", on ? "true" : "false");
        if (style === "primary") {
            btn.classList.toggle("btn-primary", on);
            btn.classList.toggle("btn-outline-primary", !on);
            btn.classList.remove("btn-secondary", "btn-outline-secondary");
        } else {
            btn.classList.toggle("btn-secondary", on);
            btn.classList.toggle("btn-outline-secondary", !on);
            btn.classList.remove("btn-primary", "btn-outline-primary");
        }
        var titleOn = attrOr(btn, "data-title-on", DEFAULT_TITLE_ON);
        var titleOff = attrOr(btn, "data-title-off", DEFAULT_TITLE_OFF);
        btn.title = on ? titleOn : titleOff;
    }

    function init() {
        var btn = toggleBtn();
        var table = tableEl();
        if (!btn || !table) {
            return;
        }
        var defOn = defaultShowEmpty(btn);
        try {
            var params = new URLSearchParams(window.location.search || "");
            var forceShowEmpty = params.get("show_empty_rows") === "1";
            if (defOn) {
                forceShowEmpty = forceShowEmpty || params.has("equipment_group_ids");
            }
            if (forceShowEmpty) {
                window.__fuelEditShowEmptyMode = true;
            } else {
                var stored = sessionStorage.getItem(storageKey(btn));
                window.__fuelEditShowEmptyMode =
                    stored === null ? defOn : stored === "1";
            }
        } catch (e) {
            window.__fuelEditShowEmptyMode = defOn;
        }
        syncToggleUi(btn);
        applyHideEmptyRows();

        btn.addEventListener("click", function () {
            window.__fuelEditShowEmptyMode = !window.__fuelEditShowEmptyMode;
            try {
                sessionStorage.setItem(
                    storageKey(btn),
                    window.__fuelEditShowEmptyMode ? "1" : "0"
                );
            } catch (eSt) { /* ignore */ }
            syncToggleUi(btn);
            applyHideEmptyRows();
        });

        table.addEventListener("input", function (ev) {
            if (!ev.target || !ev.target.closest) {
                return;
            }
            if (!ev.target.closest("tr[data-fuel-edit-data-row]")) {
                return;
            }
            if (window.__fuelEditShowEmptyMode === true) {
                return;
            }
            applyHideEmptyRows();
        });

        window.__fuelEditApplyHideEmptyRows = applyHideEmptyRows;
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
