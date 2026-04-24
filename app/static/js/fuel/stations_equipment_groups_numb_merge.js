/**
 * Объединение подряд идущих строк с одинаковым numb (data-col-8)
 * внутри одной и той же группы оборудования (data-col-1):
 * rowspan только для fuel-столбцов.
 *
 * Station-level столбцы модуля «Генерация» («Генерирующая компания»,
 * «Субъект РФ», «Региональная энергосистема») объединяются отдельной логикой
 * по станции в шаблоне страницы и здесь не должны затрагиваться, иначе
 * возникает смещение ячеек.
 *
 * Важно: в шаблоне пустой numb рендерится как «—» — по одному ключу «—» совпало бы
 * слишком много строк; такие группы не объединяем (см. isMergeableNumbKey).
 */
(function () {
    "use strict";

    var NUM_COLS = 24;
    /** Индексы столбцов: 0-7 — модуль «Генерация», их тут не трогаем; 23 — Примечание */
    var MERGE_COLS = [1, 2, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23];

    /** Значения-заглушки: общий «код» для пустого numb — не группируем */
    function isMergeableNumbKey(key) {
        if (!key || !key.length) {
            return false;
        }
        if (key === "—" || key === "\u2014") {
            return false;
        }
        if (key === "-" || key === "\u2013" || key === "\u2010") {
            return false;
        }
        return true;
    }

    function mergeKey(row) {
        var groupName = (row.getAttribute("data-col-1") || "").trim();
        var numb = (row.getAttribute("data-col-8") || "").trim();
        return groupName + "||" + numb;
    }

    function findRowIndex(td, dataRows) {
        var tr = td.closest("tr");
        return dataRows.indexOf(tr);
    }

    /**
     * Карта ячеек по строкам: только прямые дочерние td с позицией в сетке.
     */
    function buildPerRowGrid(dataRows) {
        var n = dataRows.length;
        var occupied = [];
        var r, c, cc, rs, cs, sc, td, tds, ri, cell;
        for (r = 0; r < n; r++) {
            occupied[r] = Array(NUM_COLS).fill(false);
        }
        var perRow = [];
        for (ri = 0; ri < n; ri++) {
            var cells = [];
            c = 0;
            tds = dataRows[ri].querySelectorAll(":scope > td");
            for (var t = 0; t < tds.length; t++) {
                td = tds[t];
                while (c < NUM_COLS && occupied[ri][c]) {
                    c++;
                }
                cs = td.colSpan || 1;
                rs = td.rowSpan || 1;
                sc = c;
                cells.push({ td: td, startCol: sc, colspan: cs, rowspan: rs });
                for (r = 0; r < rs; r++) {
                    for (cc = 0; cc < cs; cc++) {
                        if (ri + r < n) {
                            occupied[ri + r][sc + cc] = true;
                        }
                    }
                }
                c += cs;
            }
            perRow.push(cells);
        }
        return perRow;
    }

    /**
     * Ячейка, покрывающая логический столбец col в строке ri (с учётом rowspan сверху).
     */
    function cellAtColumn(perRow, ri, col) {
        var r, k, cell, startCol, colspan, rowspan, lastRow;
        for (r = 0; r <= ri; r++) {
            for (k = 0; k < perRow[r].length; k++) {
                cell = perRow[r][k];
                startCol = cell.startCol;
                colspan = cell.colspan;
                rowspan = cell.rowspan;
                if (col < startCol || col >= startCol + colspan) {
                    continue;
                }
                lastRow = r + rowspan - 1;
                if (ri >= r && ri <= lastRow) {
                    return cell.td;
                }
            }
        }
        return null;
    }

    function mergeOneColumn(dataRows, perRow, r0, n, col) {
        var keeper = cellAtColumn(perRow, r0, col);
        if (!keeper) {
            return;
        }
        var startRow = findRowIndex(keeper, dataRows);
        if (startRow < r0) {
            return;
        }
        if (startRow > r0) {
            return;
        }

        var seen = new Set();
        var i, c, td;
        for (i = 0; i < n; i++) {
            td = cellAtColumn(perRow, r0 + i, col);
            if (td) {
                seen.add(td);
            }
        }

        if (seen.size === 1) {
            td = keeper;
            var cur = parseInt(td.getAttribute("rowspan") || "1", 10) || 1;
            if (cur !== n) {
                td.setAttribute("rowspan", String(n));
            }
            return;
        }

        for (i = 1; i < n; i++) {
            c = cellAtColumn(perRow, r0 + i, col);
            if (c && c !== keeper) {
                c.remove();
            }
        }
        keeper.setAttribute("rowspan", String(n));
    }

    function mergeGroup(dataRows, r0, n) {
        var ci, perRow;
        if (n < 2) {
            return;
        }
        for (ci = 0; ci < MERGE_COLS.length; ci++) {
            perRow = buildPerRowGrid(dataRows);
            mergeOneColumn(dataRows, perRow, r0, n, MERGE_COLS[ci]);
        }
    }

    function runMerge() {
        var table = document.getElementById("stationsEquipmentGroupsTable");
        if (!table) {
            return;
        }
        var dataRows = Array.from(table.querySelectorAll("tbody tr.data-row"));
        if (dataRows.length < 2) {
            return;
        }

        var i = 0;
        var j;
        var key;
        var len;
        while (i < dataRows.length) {
            j = i + 1;
            key = mergeKey(dataRows[i]);
            while (j < dataRows.length && mergeKey(dataRows[j]) === key) {
                j++;
            }
            len = j - i;
            if (len >= 2 && isMergeableNumbKey((dataRows[i].getAttribute("data-col-8") || "").trim())) {
                mergeGroup(dataRows, i, len);
            }
            i = j;
        }
    }

    function init() {
        try {
            runMerge();
        } catch (e) {
            console.error("[stations_equipment_groups_numb_merge]", e);
        }
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            window.requestAnimationFrame(function () {
                setTimeout(init, 0);
            });
        });
    } else {
        window.requestAnimationFrame(function () {
            setTimeout(init, 0);
        });
    }
})();
