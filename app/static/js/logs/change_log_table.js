/**
 * Общая логика таблиц «Журнал изменений»:
 * - объединённый столбец «Дата и время»
 * - фильтр дат с/по + текстовые фильтры
 * - сборка строк для load-more
 */
(function (global) {
  "use strict";

  function escapeAttr(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/"/g, "&quot;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function datetimeOf(log) {
    if (!log) return "";
    if (log.datetime) return String(log.datetime);
    var d = log.date || "";
    var t = log.time || "";
    return (d + (t ? " " + t : "")).trim();
  }

  function cellVal(node, dataKey) {
    if (!node) return "";
    var camel = dataKey.replace(/-([a-z])/g, function (_, c) {
      return c.toUpperCase();
    });
    if (node.dataset && node.dataset[camel]) return node.dataset[camel];
    return (node.textContent || "").trim().toLowerCase();
  }

  function rowFromLog(log) {
    var tr = document.createElement("tr");
    var dt = datetimeOf(log);
    var date = (log && log.date) || "";
    tr.innerHTML =
      '<td data-datetime="' +
      escapeAttr(dt) +
      '" data-date="' +
      escapeAttr(date) +
      '">' +
      escapeAttr(dt) +
      "</td>" +
      '<td data-user="' +
      escapeAttr((log && log.username_lower) || "") +
      '">' +
      escapeAttr((log && log.username) || "") +
      "</td>" +
      '<td><div data-action="' +
      escapeAttr((log && log.action_lower) || "") +
      '">' +
      escapeAttr((log && log.action) || "") +
      "</div></td>" +
      '<td data-database-version="' +
      escapeAttr(String((log && log.database_version) || "").toLowerCase()) +
      '">' +
      escapeAttr((log && log.database_version) || "") +
      "</td>" +
      "<td></td>";
    if (log && log.details) {
      var detailsDiv = document.createElement("div");
      detailsDiv.setAttribute("data-details", (log.details_lower || String(log.details).toLowerCase()));
      detailsDiv.style.whiteSpace = "pre-wrap";
      detailsDiv.textContent = log.details;
      tr.cells[4].appendChild(detailsDiv);
    }
    return tr;
  }

  function applyFilters(table) {
    if (!table || !table.tHead || !table.tBodies[0]) return;
    var filterRow = table.tHead.querySelector("tr.log-filter-row");
    if (!filterRow) return;
    var tbody = table.tBodies[0];
    var dateFrom = (filterRow.querySelector(".log-date-from") || {}).value || "";
    var dateTo = (filterRow.querySelector(".log-date-to") || {}).value || "";
    var textInputs = Array.prototype.slice.call(
      filterRow.querySelectorAll('input[type="text"]')
    );
    var terms = textInputs.map(function (i) {
      return i.value.trim().toLowerCase();
    });
    Array.prototype.forEach.call(tbody.rows, function (tr) {
      if (tr.querySelector("td[colspan]")) return;
      var rowDate = cellVal(tr.cells[0], "date");
      var okDate = true;
      if (dateFrom && rowDate && rowDate < dateFrom) okDate = false;
      if (dateTo && rowDate && rowDate > dateTo) okDate = false;
      if ((dateFrom || dateTo) && !rowDate) okDate = false;
      var dUser = cellVal(tr.cells[1], "user");
      var dAction = cellVal(
        (tr.cells[2] && tr.cells[2].querySelector("[data-action]")) || tr.cells[2],
        "action"
      );
      var dVer = cellVal(tr.cells[3], "database-version");
      var dDetails = cellVal(
        (tr.cells[4] && tr.cells[4].querySelector("[data-details]")) || tr.cells[4],
        "details"
      );
      var data = [dUser, dAction, dVer, dDetails];
      var okText = terms.every(function (t, i) {
        return t === "" || (data[i] && data[i].indexOf(t) !== -1);
      });
      tr.style.display = okDate && okText ? "" : "none";
    });
  }

  function initSortFilter(table) {
    if (!table || !table.tHead || !table.tBodies[0]) return table;
    if (table._changeLogFiltersReady) return table;
    table._changeLogFiltersReady = true;

    var thead = table.tHead;
    var tbody = table.tBodies[0];
    var sortState = { key: "datetime", asc: false };

    function sortBy(key) {
      var rows = Array.prototype.slice.call(tbody.rows);
      rows.sort(function (r1, r2) {
        var a = "";
        var b = "";
        if (key === "datetime") {
          a = cellVal(r1.cells[0], "datetime");
          b = cellVal(r2.cells[0], "datetime");
        } else if (key === "user") {
          a = cellVal(r1.cells[1], "user");
          b = cellVal(r2.cells[1], "user");
        } else if (key === "action") {
          a = cellVal(
            (r1.cells[2] && r1.cells[2].querySelector("[data-action]")) || r1.cells[2],
            "action"
          );
          b = cellVal(
            (r2.cells[2] && r2.cells[2].querySelector("[data-action]")) || r2.cells[2],
            "action"
          );
        } else if (key === "database_version") {
          a = cellVal(r1.cells[3], "database-version");
          b = cellVal(r2.cells[3], "database-version");
        } else if (key === "details") {
          a = cellVal(
            (r1.cells[4] && r1.cells[4].querySelector("[data-details]")) || r1.cells[4],
            "details"
          );
          b = cellVal(
            (r2.cells[4] && r2.cells[4].querySelector("[data-details]")) || r2.cells[4],
            "details"
          );
        }
        if (a < b) return sortState.asc ? -1 : 1;
        if (a > b) return sortState.asc ? 1 : -1;
        return 0;
      });
      rows.forEach(function (r) {
        tbody.appendChild(r);
      });
      sortState = { key: key, asc: !sortState.asc };
    }

    thead.addEventListener("click", function (e) {
      if (e.target.closest("input, label, select, button, a")) return;
      var th = e.target.closest("th[data-key]");
      if (!th) return;
      sortBy(th.dataset.key);
    });

    if (!thead.querySelector("tr.log-filter-row")) {
      var filterRow = document.createElement("tr");
      filterRow.className = "log-filter-row";
      ["datetime", "user", "action", "database_version", "details"].forEach(function (key) {
        var td = document.createElement("td");
        if (key === "datetime") {
          var wrap = document.createElement("div");
          wrap.className = "log-datetime-filter";
          wrap.innerHTML =
            "<div>" +
            '<label class="form-label">Дата с</label>' +
            '<input type="date" class="form-control form-control-sm log-date-from" title="Дата с">' +
            "</div>" +
            "<div>" +
            '<label class="form-label">Дата по</label>' +
            '<input type="date" class="form-control form-control-sm log-date-to" title="Дата по">' +
            "</div>";
          Array.prototype.forEach.call(wrap.querySelectorAll("input"), function (inp) {
            inp.addEventListener("change", function () {
              applyFilters(table);
            });
            inp.addEventListener("input", function () {
              applyFilters(table);
            });
          });
          td.appendChild(wrap);
        } else {
          var input = document.createElement("input");
          input.type = "text";
          input.className = "form-control form-control-sm";
          input.placeholder = "Фильтр";
          input.addEventListener("input", function () {
            applyFilters(table);
          });
          td.appendChild(input);
        }
        filterRow.appendChild(td);
      });
      thead.appendChild(filterRow);
    }

    table._applyLogFilters = function () {
      applyFilters(table);
    };
    return table;
  }

  function ensureHeaderKeys(table) {
    if (!table || !table.tHead) return;
    var headerRow = table.tHead.querySelector("tr:not(.log-filter-row)");
    if (!headerRow) return;
    var keys = ["datetime", "user", "action", "database_version", "details"];
    Array.prototype.forEach.call(headerRow.cells, function (th, idx) {
      if (!th.getAttribute("data-key") && keys[idx]) {
        th.setAttribute("data-key", keys[idx]);
        th.style.cursor = "pointer";
      }
    });
  }

  function autoInit() {
    Array.prototype.forEach.call(
      document.querySelectorAll("table.change-log-table"),
      function (table) {
        ensureHeaderKeys(table);
        if (table.getAttribute("data-change-log-filters") !== "0") {
          initSortFilter(table);
        }
      }
    );
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", autoInit);
  } else {
    autoInit();
  }

  global.ChangeLogTable = {
    datetimeOf: datetimeOf,
    rowFromLog: rowFromLog,
    applyFilters: applyFilters,
    initSortFilter: initSortFilter,
    ensureHeaderKeys: ensureHeaderKeys,
  };
})(window);
