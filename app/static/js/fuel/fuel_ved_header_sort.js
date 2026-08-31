/**
 * Сортировка групп оборудования по столбцу Тип ТЭС (VED) кликом по шапке.
 * Годы одной группы остаются вместе; шапки ЕЭС/ОЭС/РЭС скрываются, как при
 * сортировке словаря станций.
 */
(function () {
    "use strict";

    var TABLE_ID = "specificFcEditTable";
    var INDICATOR_CLASS = "specific-fc-sort-indicator";

    function tableEl() {
        return document.getElementById(TABLE_ID);
    }

    function parseVed(raw) {
        if (raw == null || raw === "") {
            return null;
        }
        var n = parseInt(String(raw).trim(), 10);
        return Number.isFinite(n) ? n : null;
    }

    function rowVed(tr) {
        var fromRow = parseVed(tr.getAttribute("data-ved"));
        if (fromRow !== null) {
            return fromRow;
        }
        var td = tr.querySelector('td[data-column="ved"]');
        if (!td) {
            return null;
        }
        return parseVed(td.getAttribute("data-ved") || td.textContent);
    }

    function groupBlocks(tbody) {
        var rows = Array.prototype.slice.call(
            tbody.querySelectorAll("tr[data-fuel-edit-data-row]")
        );
        var blocks = [];
        var current = null;
        rows.forEach(function (tr, idx) {
            var gid = tr.getAttribute("data-fuel-group-id") || "";
            if (!current || current.gid !== gid) {
                current = { gid: gid, rows: [], orig: blocks.length, firstIdx: idx };
                blocks.push(current);
            }
            current.rows.push(tr);
        });
        return blocks;
    }

    function blockVed(block) {
        for (var i = 0; i < block.rows.length; i++) {
            var n = rowVed(block.rows[i]);
            if (n !== null) {
                return n;
            }
        }
        return null;
    }

    function sortBlocks(tbody, dir) {
        var blocks = groupBlocks(tbody);
        if (blocks.length < 2) {
            return;
        }
        blocks.sort(function (a, b) {
            var va = blockVed(a);
            var vb = blockVed(b);
            var aEmpty = va === null;
            var bEmpty = vb === null;
            if (aEmpty && bEmpty) {
                return a.orig - b.orig;
            }
            if (aEmpty) {
                return 1;
            }
            if (bEmpty) {
                return -1;
            }
            if (va !== vb) {
                return dir * (va - vb);
            }
            return a.orig - b.orig;
        });
        blocks.forEach(function (block) {
            block.rows.forEach(function (tr) {
                tbody.appendChild(tr);
            });
        });
        if (typeof window.__fuelEditApplyHideEmptyRows === "function") {
            window.__fuelEditApplyHideEmptyRows();
        }
    }

    function setIndicator(th, dir) {
        th.querySelectorAll("." + INDICATOR_CLASS).forEach(function (el) {
            el.remove();
        });
        var span = document.createElement("span");
        span.className = INDICATOR_CLASS + " ms-1";
        span.setAttribute("aria-hidden", "true");
        span.textContent = dir > 0 ? "▲" : "▼";
        th.appendChild(span);
        th.setAttribute("aria-sort", dir > 0 ? "ascending" : "descending");
        th.setAttribute("data-sort-dir", dir > 0 ? "asc" : "desc");
    }

    function syncVedColumnWidth(table) {
        var numbTh = table.querySelector("th.fuel-param-col-numb1120");
        if (!numbTh) {
            return;
        }
        var w = Math.round(numbTh.getBoundingClientRect().width);
        if (w <= 0) {
            return;
        }
        var prev = table.style.getPropertyValue("--specific-fc-ved-col-width");
        var prevPx = parseInt(prev, 10) || 0;
        if (prev && Math.abs(w - prevPx) <= 1) {
            return;
        }
        table.style.setProperty("--specific-fc-ved-col-width", w + "px");
    }

    function initVedColumnWidth(table) {
        syncVedColumnWidth(table);
        var numbTh = table.querySelector("th.fuel-param-col-numb1120");
        if (!numbTh || typeof ResizeObserver === "undefined") {
            window.addEventListener("resize", function () {
                syncVedColumnWidth(table);
            });
            return;
        }
        var ro = new ResizeObserver(function () {
            syncVedColumnWidth(table);
        });
        ro.observe(numbTh);
    }

    function init() {
        var table = tableEl();
        if (!table) {
            return;
        }
        var th = table.querySelector('thead th[data-column="ved"]');
        if (!th) {
            return;
        }
        th.classList.add("specific-fc-sortable-th");
        th.setAttribute("role", "columnheader");
        th.setAttribute("tabindex", "0");
        if (!th.getAttribute("title")) {
            th.setAttribute("title", "Сортировать по типу ТЭС");
        }
        if (!th.getAttribute("aria-sort")) {
            th.setAttribute("aria-sort", "none");
        }
        initVedColumnWidth(table);

        function toggleSort() {
            var nextDir = th.getAttribute("data-sort-dir") === "asc" ? -1 : 1;
            var tbody = table.tBodies[0];
            if (!tbody) {
                return;
            }
            sortBlocks(tbody, nextDir);
            setIndicator(th, nextDir);
        }

        th.addEventListener("click", function (e) {
            e.preventDefault();
            toggleSort();
        });
        th.addEventListener("keydown", function (e) {
            if (e.key !== "Enter" && e.key !== " ") {
                return;
            }
            e.preventDefault();
            toggleSort();
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
