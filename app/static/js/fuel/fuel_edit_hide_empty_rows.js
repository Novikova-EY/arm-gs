/**
 * Скрытие пустых строк на страницах edit_data (аналог «Пустые строки» в power_demand/summary).
 * По умолчанию пустые строки показаны; жёлтые (изменение Nуст) всегда остаются видимыми.
 * Кнопка #fuelEditHideEmptyToggle: нажата (btn-secondary) = показать пустые.
 */
(function () {
    "use strict";

    var HIDDEN_CLASS = "fuel-edit-empty-row-hidden";
    var STORAGE_KEY = "fuelEditShowEmptyRows_v2";

    function tableEl() {
        return (
            document.getElementById("specificFcEditTable") ||
            document.getElementById("fuelParamsTable") ||
            document.getElementById("fuelFormulaTable")
        );
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

    function rowIsEmpty(tr) {
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
            var labelTd = null;
            for (var i = 0; i < rows.length; i++) {
                var found = rows[i].querySelector("td[data-fuel-group-label]");
                if (found) {
                    labelTd = found;
                    break;
                }
            }
            if (!labelTd) {
                return;
            }
            var visible = rows.filter(function (tr) {
                return !tr.classList.contains(HIDDEN_CLASS);
            });
            if (labelTd.parentNode) {
                labelTd.parentNode.removeChild(labelTd);
            }
            var host = visible.length ? visible[0] : rows[0];
            host.insertBefore(labelTd, host.firstChild);
            labelTd.rowSpan = Math.max(visible.length, 1);
        });
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
        var groupRowClasses = ["table-light", "table-primary", "table-secondary"];

        function getGroupLevel(r) {
            for (var i = 0; i < groupRowClasses.length; i++) {
                if (r.classList.contains(groupRowClasses[i])) {
                    return i;
                }
            }
            return -1;
        }

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

    function applyHideEmptyRows() {
        var table = tableEl();
        if (!table) {
            return;
        }
        var showEmpty = window.__fuelEditShowEmptyMode === true;
        table.querySelectorAll("tbody tr[data-fuel-edit-data-row]").forEach(function (tr) {
            var hide = !showEmpty && rowIsEmpty(tr) && !rowIsYellow(tr);
            tr.classList.toggle(HIDDEN_CLASS, hide);
        });
        fixGroupRowspans(table);
        hideEmptyHierarchyHeaders(table);
    }

    function syncToggleUi(btn) {
        var on = window.__fuelEditShowEmptyMode === true;
        btn.setAttribute("aria-pressed", on ? "true" : "false");
        btn.classList.toggle("btn-secondary", on);
        btn.classList.toggle("btn-outline-secondary", !on);
        btn.classList.remove("btn-primary", "btn-outline-primary");
        btn.title = on
            ? "Скрыть строки, у которых показатели не заполнены (жёлтые строки изменения Nуст всегда видны)"
            : "Показать строки, у которых показатели не заполнены (жёлтые строки изменения Nуст всегда видны)";
    }

    function init() {
        var btn = document.getElementById("fuelEditHideEmptyToggle");
        var table = tableEl();
        if (!btn || !table) {
            return;
        }
        try {
            var params = new URLSearchParams(window.location.search || "");
            var forceShowEmpty =
                params.get("show_empty_rows") === "1" ||
                params.has("equipment_group_ids");
            if (forceShowEmpty) {
                window.__fuelEditShowEmptyMode = true;
            } else {
                var stored = sessionStorage.getItem(STORAGE_KEY);
                window.__fuelEditShowEmptyMode = stored === null ? true : stored === "1";
            }
        } catch (e) {
            window.__fuelEditShowEmptyMode = true;
        }
        syncToggleUi(btn);
        applyHideEmptyRows();

        btn.addEventListener("click", function () {
            window.__fuelEditShowEmptyMode = !window.__fuelEditShowEmptyMode;
            try {
                sessionStorage.setItem(
                    STORAGE_KEY,
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
