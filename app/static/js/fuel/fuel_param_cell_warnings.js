/**
 * Живая подсветка ячеек топливных параметров:
 * - qotr: (qotr/nt)*1000 >= 8000
 * - q: (q/nt_sum)*1000 >= 8000
 * - h (ЧЧИУМ): h >= 8000
 * - qotr: nust изменился к предыдущему году и qotr тот же
 * - data-parts-sum-mismatch-msg: Σ групп ≠ значение родителя (|Δ|>0.5)
 */
(function (global) {
  "use strict";

  var RATIO_THRESHOLD = 8000;
  var RATIO_SCALE = 1000;
  var CLASS_DANGER = "table-danger";
  var CLASS_WARN = "table-warning";
  var CLASS_CELL_WARN = "fuel-param-cell-warn";
  var MSG_COMPOSITION =
    "Произошло изменение состава агрегатов! Проверьте значение!";

  function parseFuelNum(raw) {
    if (raw == null) return null;
    var s = String(raw).replace(/\s+/g, "").replace(",", ".").trim();
    if (!s || s === "—" || s === "-" || s.toLowerCase() === "none") return null;
    var n = Number(s);
    return isFinite(n) ? n : null;
  }

  function effectiveNum(n) {
    if (n == null || n === 0) return null;
    return n;
  }

  function numsEqual(a, b) {
    return effectiveNum(a) === effectiveNum(b);
  }

  function computeHoursRatio(numer, denom) {
    if (numer == null || denom == null || denom === 0) return null;
    return (numer / denom) * RATIO_SCALE;
  }

  function formatHoursForWarn(hours) {
    if (hours == null || !isFinite(hours)) return "?";
    return String(Math.round(hours));
  }

  function hoursRatioWarnMessage(hours) {
    return (
      "ЧЧИ тепловой мощности = " +
      formatHoursForWarn(hours) +
      " (> " +
      RATIO_THRESHOLD +
      ", проверьте значение!)"
    );
  }

  function hHoursWarnMessage(hours) {
    return (
      "ЧЧИУМ " +
      formatHoursForWarn(hours) +
      " (> " +
      RATIO_THRESHOLD +
      ", проверьте значение!)"
    );
  }

  function getCellTd(tr, attr) {
    return tr.querySelector('td[data-column="' + attr + '"]');
  }

  function getCellNum(tr, attr) {
    var td = getCellTd(tr, attr);
    if (!td) return null;
    var inp = td.querySelector(
      "input.fuel-param-input, input.fuel-hier-sum-input, input.fuel-detail-sync-input",
    );
    if (inp) return parseFuelNum(inp.value);
    return parseFuelNum(td.textContent);
  }

  function rowIsCompletelyEmpty(tr) {
    if (!tr) return true;
    var tds = tr.querySelectorAll("td[data-column]");
    var hasMetricTd = false;
    for (var i = 0; i < tds.length; i++) {
      var attr = tds[i].getAttribute("data-column");
      if (attr === "numb1120") continue;
      hasMetricTd = true;
      if (getCellNum(tr, attr) != null) return false;
      var inp = tds[i].querySelector(
        "input.fuel-param-input, select.fuel-param-input, textarea",
      );
      if (inp) {
        var v = (inp.value || "").trim();
        if (v && v !== "—" && v !== "-" && v.toLowerCase() !== "none") return false;
      } else {
        var t = (tds[i].textContent || "").trim();
        if (t && t !== "—" && t !== "-" && t.toLowerCase() !== "none") return false;
      }
    }
    if (tr.getAttribute("data-row-empty") === "1") return true;
    return hasMetricTd;
  }

  function getPrevCompare(table, tr) {
    var gid = tr.getAttribute("data-fuel-detail-group-id");
    var year = parseInt(tr.getAttribute("data-fuel-detail-year") || "", 10);
    if (table && gid && isFinite(year)) {
      for (var y = year - 1; y >= year - 25; y--) {
        var prevTr = table.querySelector(
          'tr[data-fuel-detail-group-id="' +
            gid.replace(/"/g, '\\"') +
            '"][data-fuel-detail-year="' +
            y +
            '"]',
        );
        if (!prevTr) {
          break;
        }
        if (rowIsCompletelyEmpty(prevTr)) continue;
        return {
          nust: getCellNum(prevTr, "nust"),
          qotr: getCellNum(prevTr, "qotr"),
          hasPrev: true,
        };
      }
    }
    if (
      !tr.hasAttribute("data-prev-nust") &&
      !tr.hasAttribute("data-prev-qotr")
    ) {
      return { nust: null, qotr: null, hasPrev: false };
    }
    return {
      nust: parseFuelNum(tr.getAttribute("data-prev-nust")),
      qotr: parseFuelNum(tr.getAttribute("data-prev-qotr")),
      hasPrev: true,
    };
  }

  function setCellTitle(td, title) {
    if (!td) return;
    if (title) td.setAttribute("title", title);
    else td.removeAttribute("title");
    var inp = td.querySelector(
      "input.fuel-param-input, input.fuel-detail-sync-input",
    );
    if (inp) {
      if (title) inp.setAttribute("title", title);
      else inp.removeAttribute("title");
    }
  }

  function restoreDefaultTitle(td) {
    if (!td) return;
    var def = td.getAttribute("data-default-title");
    setCellTitle(td, def || "");
  }

  function applyDanger(td, messages) {
    if (!td) return;
    td.classList.remove(CLASS_WARN);
    td.classList.add(CLASS_DANGER, CLASS_CELL_WARN);
    setCellTitle(td, messages.join(" "));
  }

  function applyNustYellow(td) {
    if (!td) return;
    td.classList.remove(CLASS_DANGER, CLASS_CELL_WARN);
    td.classList.add(CLASS_WARN);
    restoreDefaultTitle(td);
  }

  function clearWarnClasses(td) {
    if (!td) return;
    td.classList.remove(CLASS_DANGER, CLASS_CELL_WARN, CLASS_WARN);
    restoreDefaultTitle(td);
  }

  function getYearTd(tr) {
    var tds = tr.querySelectorAll("td");
    for (var i = 0; i < tds.length; i++) {
      if (
        !tds[i].hasAttribute("data-column") &&
        !tds[i].classList.contains("fuel-param-group-span")
      ) {
        var txt = (tds[i].textContent || "").trim();
        if (/^\d{4}$/.test(txt)) return tds[i];
      }
    }
    return null;
  }

  function applyRowWarnings(table, tr) {
    if (!tr) return;

    // Итоги РЭС без сверки; строка родителя «…, всего» — только серверный
    // контроль Σ частей (data-parts-sum-mismatch-msg), без qotr/nust live-логики.
    if (
      tr.classList.contains("fuel-param-summary-row") &&
      !tr.classList.contains("fuel-param-composite-parent-row")
    ) {
      return;
    }
    if (
      tr.classList.contains("fuel-param-summary-row") &&
      tr.classList.contains("fuel-param-composite-parent-row")
    ) {
      var parentTds = tr.querySelectorAll("td[data-column]");
      for (var pi = 0; pi < parentTds.length; pi++) {
        var ptd = parentTds[pi];
        var pmsg = ptd.getAttribute("data-parts-sum-mismatch-msg");
        if (pmsg) applyDanger(ptd, [pmsg]);
      }
      return;
    }

    if (rowIsCompletelyEmpty(tr)) {
      var emptyYearTd = getYearTd(tr);
      if (emptyYearTd) emptyYearTd.classList.remove(CLASS_WARN);
      var emptyTds = tr.querySelectorAll("td[data-column]");
      for (var ei = 0; ei < emptyTds.length; ei++) {
        if (emptyTds[ei].getAttribute("data-column") === "numb1120") continue;
        clearWarnClasses(emptyTds[ei]);
      }
      tr.removeAttribute("data-row-yellow");
      return;
    }

    var qotr = getCellNum(tr, "qotr");
    var nt = getCellNum(tr, "nt");
    var q = getCellNum(tr, "q");
    var ntSum = getCellNum(tr, "nt_sum");
    var nust = getCellNum(tr, "nust");
    var hVal = getCellNum(tr, "h");

    var qotrHours = computeHoursRatio(qotr, nt);
    var qSumHours = computeHoursRatio(q, ntSum);
    var qotrNtWarn = qotrHours != null && qotrHours >= RATIO_THRESHOLD;
    var qSumNtWarn = qSumHours != null && qSumHours >= RATIO_THRESHOLD;
    var hHoursWarn = hVal != null && hVal >= RATIO_THRESHOLD;

    var prev = getPrevCompare(table, tr);
    var nustChanged = false;
    var compositionWarn = false;
    if (prev.hasPrev) {
      nustChanged = !numsEqual(prev.nust, nust);
      compositionWarn = nustChanged && numsEqual(prev.qotr, qotr);
    }

    var yearTd = getYearTd(tr);
    if (yearTd) {
      if (nustChanged) yearTd.classList.add(CLASS_WARN);
      else yearTd.classList.remove(CLASS_WARN);
    }

    var tds = tr.querySelectorAll("td[data-column]");
    for (var i = 0; i < tds.length; i++) {
      var td = tds[i];
      var attr = td.getAttribute("data-column");
      if (attr === "numb1120") continue;

      var partsMsg = td.getAttribute("data-parts-sum-mismatch-msg");
      var msgs = [];
      if (partsMsg) msgs.push(partsMsg);

      if (attr === "qotr") {
        if (qotrNtWarn) msgs.push(hoursRatioWarnMessage(qotrHours));
        if (compositionWarn) msgs.push(MSG_COMPOSITION);
      }
      if (attr === "q" && qSumNtWarn) {
        msgs.push(hoursRatioWarnMessage(qSumHours));
      }
      if (attr === "h" && hHoursWarn) {
        msgs.push(hHoursWarnMessage(hVal));
      }

      if (msgs.length) {
        applyDanger(td, msgs);
        continue;
      }

      if (nustChanged && yearTd) applyNustYellow(td);
      else clearWarnClasses(td);
    }
  }

  function refreshGroupOrRow(table, tr) {
    if (!table || !tr) return;
    var gid = tr.getAttribute("data-fuel-detail-group-id");
    if (gid) {
      var rows = table.querySelectorAll(
        'tr.fuel-param-detail-row[data-fuel-detail-group-id="' +
          gid.replace(/"/g, '\\"') +
          '"]',
      );
      for (var i = 0; i < rows.length; i++) applyRowWarnings(table, rows[i]);
      return;
    }
    applyRowWarnings(table, tr);
  }

  function bindFuelParamCellWarnings(table, options) {
    if (!table) return;
    options = options || {};

    function onEdit(ev) {
      var inp =
        ev.target && ev.target.closest
          ? ev.target.closest(
              "input.fuel-param-input[name], input.fuel-detail-sync-input[name]",
            )
          : null;
      if (!inp) return;
      var tr = inp.closest("tr.fuel-param-detail-row");
      if (!tr) return;
      refreshGroupOrRow(table, tr);
    }

    if (options.listen !== false) {
      table.addEventListener("input", onEdit);
      table.addEventListener("change", onEdit);
    }

    var rows = table.querySelectorAll("tbody tr.fuel-param-detail-row");
    for (var i = 0; i < rows.length; i++) applyRowWarnings(table, rows[i]);
  }

  global.bindFuelParamCellWarnings = bindFuelParamCellWarnings;
  global.refreshFuelParamCellWarningsForRow = refreshGroupOrRow;
})(window);
