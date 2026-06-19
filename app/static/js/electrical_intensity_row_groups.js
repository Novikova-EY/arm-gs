/**
 * Группировка строк на странице электроёмкости (РФ / ФО / секции ВЭД) — сворачивание как в Excel.
 */
(function () {
    "use strict";

    var TERRITORY_HEADER = "lt-ei-territory-header-row";
    var VED_HEADER = "lt-ei-ved-header-row";
    var HIDDEN_BY_TERRITORY = "lt-ei-territory-collapsed-hidden";
    var HIDDEN_BY_VED = "lt-ei-ved-collapsed-hidden";
    var HIDDEN_BY_INDUSTRIAL_GROUP = "lt-ei-industrial-group-collapsed-hidden";
    var HIDDEN_BY_INDUSTRIAL_CHILD = "lt-ei-industrial-child-collapsed-hidden";
    var GROUP_STATE_STORAGE_PREFIX = "armGs.ltEiRowGroupState:";

    function getGroupStateStorageKey() {
        return GROUP_STATE_STORAGE_PREFIX + window.location.pathname;
    }

    function readGroupStateMap() {
        try {
            var raw = localStorage.getItem(getGroupStateStorageKey());
            if (!raw) return {};
            var parsed = JSON.parse(raw);
            return parsed && typeof parsed === "object" ? parsed : {};
        } catch (_) {
            return {};
        }
    }

    function writeGroupStateMap(map) {
        try {
            localStorage.setItem(getGroupStateStorageKey(), JSON.stringify(map));
        } catch (_) {}
    }

    function readGroupExpanded(groupKey, defaultExpanded) {
        if (!groupKey) return defaultExpanded;
        var map = readGroupStateMap();
        if (!Object.prototype.hasOwnProperty.call(map, groupKey)) return defaultExpanded;
        return map[groupKey] !== "0";
    }

    function persistGroupExpanded(groupKey, expanded) {
        if (!groupKey) return;
        var map = readGroupStateMap();
        map[groupKey] = expanded ? "1" : "0";
        writeGroupStateMap(map);
    }

    function findPreviousTerritoryKey(headerRow) {
        var prev = headerRow.previousElementSibling;
        while (prev) {
            if (isTerritoryHeader(prev)) {
                return resolveGroupKey(prev).replace(/^t:/, "");
            }
            prev = prev.previousElementSibling;
        }
        return "";
    }

    function resolveGroupKey(headerRow) {
        var key = headerRow.getAttribute("data-lt-ei-group-key");
        if (key) return key;
        if (isTerritoryHeader(headerRow)) {
            var territoryLabel = headerRow.querySelector(".lt-ei-territory-header-label");
            return "t:" + (territoryLabel ? territoryLabel.textContent.trim() : "");
        }
        if (isVedHeader(headerRow)) {
            var vedLabel = headerRow.querySelector(".lt-ei-ved-header-label");
            var territoryPart = findPreviousTerritoryKey(headerRow);
            return (
                "v:" +
                territoryPart +
                "|" +
                (vedLabel ? vedLabel.textContent.trim() : "")
            );
        }
        return "";
    }

    function collectRowsUntil(headerRow, stopPredicate) {
        var rows = [];
        var next = headerRow.nextElementSibling;
        while (next) {
            if (stopPredicate(next)) break;
            rows.push(next);
            next = next.nextElementSibling;
        }
        return rows;
    }

    function isTerritoryHeader(row) {
        return row.classList.contains(TERRITORY_HEADER);
    }

    function isVedHeader(row) {
        return row.classList.contains(VED_HEADER);
    }

    function isIndustrialGroupHeader(row) {
        return isVedHeader(row) && row.getAttribute("data-lt-ei-industrial-group") === "1";
    }

    function isIndustrialGroupChildHeader(row) {
        return isVedHeader(row) && row.getAttribute("data-lt-ei-industrial-group-child") === "1";
    }

    function createToggleButton(expanded, collapseTitle, expandTitle) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn btn-sm lt-ei-group-toggle";
        btn.setAttribute("aria-expanded", expanded ? "true" : "false");
        btn.setAttribute("title", expanded ? collapseTitle : expandTitle);
        btn.setAttribute("aria-label", expanded ? collapseTitle : expandTitle);
        var icon = document.createElement("span");
        icon.className = "lt-ei-group-toggle-icon";
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = expanded ? "−" : "+";
        btn.appendChild(icon);
        return btn;
    }

    function updateToggleButton(headerRow, expanded, collapseTitle, expandTitle) {
        var btn = headerRow.querySelector(".lt-ei-group-toggle");
        if (!btn) return;
        btn.setAttribute("aria-expanded", expanded ? "true" : "false");
        btn.title = expanded ? collapseTitle : expandTitle;
        btn.setAttribute("aria-label", expanded ? collapseTitle : expandTitle);
        var icon = btn.querySelector(".lt-ei-group-toggle-icon");
        if (icon) icon.textContent = expanded ? "−" : "+";
    }

    function setRowsHidden(rows, hiddenClass, hidden) {
        rows.forEach(function (row) {
            row.classList.toggle(hiddenClass, hidden);
        });
    }

    function insertToggleButton(headerRow, btn) {
        var labelHost = headerRow.querySelector(".lt-ei-entity-sticky-center");
        if (labelHost) {
            labelHost.insertBefore(btn, labelHost.firstChild);
            return;
        }
        var td = headerRow.querySelector("td");
        if (td) td.insertBefore(btn, td.firstChild);
    }

    var LT_EI_ROW_STACK_Z_CAP = 50;

    function assignLtEiRowStackIndices() {
        var tbody = document.querySelector("#powerDemandSummaryTable tbody");
        if (!tbody) return;
        Array.prototype.forEach.call(tbody.rows, function (row, idx) {
            row.style.setProperty(
                "--lt-ei-row-stack",
                String(Math.min(idx + 1, LT_EI_ROW_STACK_Z_CAP))
            );
        });
    }

    function readLtEiRowStack(row) {
        var raw = row.style.getPropertyValue("--lt-ei-row-stack");
        var n = parseInt(raw, 10);
        return Number.isFinite(n) ? n : 0;
    }

    function clearLtEiStickyHoverZ(row) {
        row.querySelectorAll("td.summary-parameter-cell, td.summary-unit-cell").forEach(function (td) {
            td.style.zIndex = "";
        });
    }

    function raiseLtEiStickyHoverZ(row) {
        if (
            row.classList.contains(TERRITORY_HEADER) ||
            row.classList.contains(VED_HEADER) ||
            row.classList.contains("lt-ei-ved-separator-row")
        ) {
            return;
        }
        var stack = readLtEiRowStack(row);
        var capped = Math.min(stack, LT_EI_ROW_STACK_Z_CAP);
        row.querySelectorAll("td.summary-parameter-cell").forEach(function (td) {
            td.style.zIndex = String(500 + capped);
        });
        row.querySelectorAll("td.summary-unit-cell").forEach(function (td) {
            td.style.zIndex = String(490 + capped);
        });
    }

    function initLtEiStickyHoverStackFix() {
        var table = document.querySelector("#powerDemandSummaryTable.lt-ei-sticky-lead-cols");
        if (!table) return;
        var tbody = table.querySelector("tbody");
        if (!tbody || tbody.dataset.ltEiStickyHoverInit === "1") return;
        tbody.dataset.ltEiStickyHoverInit = "1";

        tbody.addEventListener(
            "mouseover",
            function (evt) {
                var row = evt.target.closest("tr");
                if (!row || row.parentElement !== tbody) return;
                raiseLtEiStickyHoverZ(row);
            },
            true
        );
        tbody.addEventListener(
            "mouseout",
            function (evt) {
                var row = evt.target.closest("tr");
                if (!row || row.parentElement !== tbody) return;
                var rel = evt.relatedTarget;
                if (rel && row.contains(rel)) return;
                clearLtEiStickyHoverZ(row);
            },
            true
        );
    }

    function refreshTableLayout() {
        assignLtEiRowStackIndices();
        initLtEiStickyHoverStackFix();
        if (typeof window.armGsUpdatePdSummaryControlsStickyHeight === "function") {
            window.armGsUpdatePdSummaryControlsStickyHeight();
        }
        if (typeof window.armGsUpdateHorizontalScrollFlags === "function") {
            window.armGsUpdateHorizontalScrollFlags();
        }
        if (typeof window.armGsApplyStickyTheadOffsets === "function") {
            window.armGsApplyStickyTheadOffsets();
        }
    }

    function applyGroupExpandedState(
        headerRow,
        expanded,
        memberRows,
        hiddenClass,
        collapseTitle,
        expandTitle
    ) {
        headerRow.dataset.ltEiGroupExpanded = expanded ? "1" : "0";
        updateToggleButton(headerRow, expanded, collapseTitle, expandTitle);
        setRowsHidden(memberRows, hiddenClass, !expanded);
    }

    function attachGroupToggle(headerRow, hiddenClass, getMemberRows, labels) {
        if (headerRow.dataset.ltEiGroupInit === "1") return;
        headerRow.dataset.ltEiGroupInit = "1";

        var groupKey = resolveGroupKey(headerRow);
        var expanded = readGroupExpanded(groupKey, true);
        var collapseTitle = (labels && labels.collapse) || "Свернуть строки группы";
        var expandTitle = (labels && labels.expand) || "Развернуть строки группы";
        var btn = createToggleButton(expanded, collapseTitle, expandTitle);
        insertToggleButton(headerRow, btn);

        var memberRows = getMemberRows();
        applyGroupExpandedState(
            headerRow,
            expanded,
            memberRows,
            hiddenClass,
            collapseTitle,
            expandTitle
        );

        btn.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            var isExpanded = headerRow.dataset.ltEiGroupExpanded !== "0";
            var nextExpanded = !isExpanded;
            applyGroupExpandedState(
                headerRow,
                nextExpanded,
                memberRows,
                hiddenClass,
                collapseTitle,
                expandTitle
            );
            persistGroupExpanded(groupKey, nextExpanded);
            refreshTableLayout();
        });
    }

    function collectIndustrialGroupOwnRows(industrialHeaderRow) {
        var rows = [];
        var next = industrialHeaderRow.nextElementSibling;
        while (next) {
            if (isTerritoryHeader(next) || isIndustrialGroupHeader(next)) break;
            if (isIndustrialGroupChildHeader(next) || isVedHeader(next)) break;
            rows.push(next);
            next = next.nextElementSibling;
        }
        return rows;
    }

    function collectIndustrialGroupChildRows(industrialHeaderRow) {
        var rows = [];
        var next = industrialHeaderRow.nextElementSibling;
        while (next) {
            if (isTerritoryHeader(next) || isIndustrialGroupHeader(next)) break;
            if (isIndustrialGroupChildHeader(next)) {
                rows.push(next);
                var bodyRows = collectRowsUntil(next, function (row) {
                    return isTerritoryHeader(row) || isVedHeader(row);
                });
                rows = rows.concat(bodyRows);
                next = bodyRows.length
                    ? bodyRows[bodyRows.length - 1].nextElementSibling
                    : next.nextElementSibling;
                continue;
            }
            if (isVedHeader(next)) break;
            next = next.nextElementSibling;
        }
        return rows;
    }

    function applyIndustrialGroupExpandedState(
        headerRow,
        expanded,
        ownRows,
        childRows,
        collapseTitle,
        expandTitle
    ) {
        headerRow.dataset.ltEiGroupExpanded = expanded ? "1" : "0";
        updateToggleButton(headerRow, expanded, collapseTitle, expandTitle);
        setRowsHidden(ownRows, HIDDEN_BY_INDUSTRIAL_GROUP, !expanded);
        setRowsHidden(childRows, HIDDEN_BY_INDUSTRIAL_CHILD, !expanded);
    }

    function attachIndustrialGroupToggle(headerRow) {
        if (headerRow.dataset.ltEiGroupInit === "1") return;
        headerRow.dataset.ltEiGroupInit = "1";

        var groupKey = resolveGroupKey(headerRow);
        var expanded = readGroupExpanded(groupKey, true);
        var collapseTitle =
            "Свернуть «Промышленное производство» и подблоки «Добывающие» / «Обрабатывающие производства»";
        var expandTitle =
            "Развернуть «Промышленное производство» и подблоки «Добывающие» / «Обрабатывающие производства»";
        var btn = createToggleButton(expanded, collapseTitle, expandTitle);
        insertToggleButton(headerRow, btn);

        var ownRows = collectIndustrialGroupOwnRows(headerRow);
        var childRows = collectIndustrialGroupChildRows(headerRow);
        applyIndustrialGroupExpandedState(
            headerRow,
            expanded,
            ownRows,
            childRows,
            collapseTitle,
            expandTitle
        );

        btn.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            var isExpanded = headerRow.dataset.ltEiGroupExpanded !== "0";
            var nextExpanded = !isExpanded;
            applyIndustrialGroupExpandedState(
                headerRow,
                nextExpanded,
                ownRows,
                childRows,
                collapseTitle,
                expandTitle
            );
            persistGroupExpanded(groupKey, nextExpanded);
            refreshTableLayout();
        });
    }

    function initElectricalIntensityRowGroups() {
        var tbody = document.querySelector("#powerDemandSummaryTable tbody");
        if (!tbody) return;

        tbody.querySelectorAll("tr." + TERRITORY_HEADER).forEach(function (headerRow) {
            attachGroupToggle(headerRow, HIDDEN_BY_TERRITORY, function () {
                return collectRowsUntil(headerRow, isTerritoryHeader);
            });
        });

        tbody.querySelectorAll("tr." + VED_HEADER).forEach(function (headerRow) {
            if (isIndustrialGroupHeader(headerRow)) {
                attachIndustrialGroupToggle(headerRow);
                return;
            }
            attachGroupToggle(headerRow, HIDDEN_BY_VED, function () {
                return collectRowsUntil(headerRow, function (row) {
                    return isVedHeader(row) || isTerritoryHeader(row);
                });
            });
        });

        assignLtEiRowStackIndices();
        initLtEiStickyHoverStackFix();
        refreshTableLayout();
    }

    window.armGsAssignLtEiRowStackIndices = assignLtEiRowStackIndices;

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initElectricalIntensityRowGroups);
    } else {
        initElectricalIntensityRowGroups();
    }
})();
