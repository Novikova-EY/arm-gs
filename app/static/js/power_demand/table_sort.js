/**
 * Клиентская сортировка строк таблиц раздела «Нагрузки».
 * Строки формы переставляются целиком — поля POST остаются согласованными.
 */
(function () {
    'use strict';

    function cellSortKey(td) {
        const sel = td.querySelector('select');
        if (sel) {
            const v = sel.value;
            if (v === 'hist') {
                return '\u0000hist';
            }
            if (v === '') {
                return '\u0001empty';
            }
            if (/^\d+$/.test(v)) {
                return '\u0002' + v.padStart(8, '0');
            }
            return '\u0003' + v;
        }
        const inp = td.querySelector('input:not([type="checkbox"]):not([type="hidden"])');
        if (inp) {
            const raw = (inp.value || '').trim().replace(/\s+/g, ' ').replace(',', '.');
            if (raw === '') {
                return '\uFFFF';
            }
            const dt = raw.match(/^(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})/);
            if (dt) {
                return (
                    'D' +
                    dt[3] +
                    dt[2] +
                    dt[1] +
                    dt[4] +
                    dt[5]
                );
            }
            const num = parseFloat(raw);
            if (!Number.isNaN(num)) {
                return 'N' + String(1e15 + num).padStart(24, '0');
            }
            return 'T' + raw.toLowerCase();
        }
        const a = td.querySelector('a[href]');
        if (a) {
            const href = a.getAttribute('href') || '';
            const m = href.match(/(\d+)(?:\/?|\?|#|$)/);
            if (m) {
                return 'I' + m[1].padStart(12, '0');
            }
        }
        let t = td.textContent.trim();
        if (t === '—' || t === '') {
            return '\uFFFE';
        }
        if (t === 'Исторический максимум') {
            return '\u0000hist';
        }
        const yn = /^\d+$/.test(t) ? parseInt(t, 10) : NaN;
        if (!Number.isNaN(yn)) {
            return '\u0002' + String(yn).padStart(8, '0');
        }
        const num = parseFloat(t.replace(',', '.').replace(/\s/g, ''));
        if (!Number.isNaN(num)) {
            return 'N' + String(1e15 + num).padStart(24, '0');
        }
        const dt2 = t.match(/^(\d{2})\.(\d{2})\.(\d{4})\s+(\d{2}):(\d{2})/);
        if (dt2) {
            return 'D' + dt2[3] + dt2[2] + dt2[1] + dt2[4] + dt2[5];
        }
        return 'S' + t.toLowerCase();
    }

    function getDataRows(tbody, options) {
        const rows = Array.from(tbody.querySelectorAll('tr'));
        return rows.filter(function (tr) {
            if (options.pinLastRowSelector && tr.matches(options.pinLastRowSelector)) {
                return false;
            }
            const c0 = tr.cells[0];
            if (c0 && c0.colSpan > 1) {
                return false;
            }
            return true;
        });
    }

    function sortTable(table, colIndex, ascending, options) {
        const tbody = table.tBodies[0];
        if (!tbody) {
            return;
        }
        const dataRows = getDataRows(tbody, options);
        if (dataRows.length < 2) {
            return;
        }

        const pinned = options.pinLastRowSelector
            ? tbody.querySelector(options.pinLastRowSelector)
            : null;

        const decorated = dataRows.map(function (tr) {
            const td = tr.cells[colIndex];
            const key = td ? cellSortKey(td) : '';
            return { tr: tr, key: key };
        });

        decorated.sort(function (a, b) {
            const cmp = a.key < b.key ? -1 : a.key > b.key ? 1 : 0;
            return ascending ? cmp : -cmp;
        });

        dataRows.forEach(function (tr) {
            tr.remove();
        });
        decorated.forEach(function (x) {
            tbody.appendChild(x.tr);
        });
        if (pinned) {
            tbody.appendChild(pinned);
        }
    }

    function clearIndicators(table) {
        table.querySelectorAll('thead th .power-demand-sort-indicator').forEach(function (el) {
            el.remove();
        });
        table.querySelectorAll('thead th[data-sort-active]').forEach(function (th) {
            th.removeAttribute('data-sort-active');
        });
    }

    function initTable(table, options) {
        options = options || {};
        const thead = table.tHead;
        const tbody = table.tBodies[0];
        if (!thead || !tbody) {
            return;
        }

        const headers = thead.querySelectorAll('tr > th');
        headers.forEach(function (th, idx) {
            if (th.hasAttribute('data-no-sort')) {
                return;
            }
            th.classList.add('power-demand-sortable-th');
            th.setAttribute('title', 'Сортировать по столбцу');

            th.addEventListener('click', function () {
                const active = table.querySelector('thead th[data-sort-active="1"]');
                let ascending = true;
                if (active === th) {
                    ascending = th.dataset.sortDir !== 'asc';
                }
                clearIndicators(table);
                th.dataset.sortActive = '1';
                th.dataset.sortDir = ascending ? 'asc' : 'desc';
                const ind = document.createElement('span');
                ind.className = 'power-demand-sort-indicator ms-1';
                ind.textContent = ascending ? '↑' : '↓';
                ind.setAttribute('aria-hidden', 'true');
                th.appendChild(ind);

                sortTable(table, idx, ascending, options);
            });
        });
    }

    window.initPowerDemandTableSort = initTable;
})();
