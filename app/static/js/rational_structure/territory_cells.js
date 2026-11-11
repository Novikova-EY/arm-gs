(() => {
    'use strict';
    const editor = document.querySelector('[data-territory-editor]');
    if (!editor) return;
    const status = editor.querySelector('[data-save-status]');
    const dirty = new Set();
    const failed = new Set();
    const states = new WeakMap();
    let queue = Promise.resolve();
    const retry = document.createElement('button');
    retry.type = 'button';
    retry.className = 'btn btn-outline-danger btn-sm';
    retry.textContent = 'Повторить сохранение';
    retry.hidden = true;
    if (status) status.after(retry);

    function format(raw, field, rounding = editor.dataset.rounding) {
        if (field === 'note' || raw === '') return raw;
        const digits = ['technology_number', 'zone_membership', 'zone_paths'].includes(field) ? -1 : Number(rounding);
        if (digits === 0) return raw.replace('.', ',');
        return new Intl.NumberFormat('ru-RU', {
            minimumFractionDigits: digits < 0 ? 0 : digits,
            maximumFractionDigits: digits < 0 ? 0 : digits,
        }).format(Number(raw));
    }

    function mark(cell, state) {
        for (const target of [cell, cell.closest('td')]) {
            target.classList.remove('is-save-success', 'is-save-error', 'is-saving');
            if (state) target.classList.add(state);
        }
        cell.setAttribute('aria-invalid', state === 'is-save-error' ? 'true' : 'false');
    }

    let selectedEquipmentGroups = null;
    const unfilteredEquipmentTotals = new WeakMap();

    function hasRowValues(row) {
        return [...row.querySelectorAll('[data-raw-value]')].some(td => {
            const input = td.querySelector('input');
            const value = input ? input.dataset.raw : td.dataset.rawValue;
            return value !== '' && Number(value) !== 0;
        });
    }

    function refreshEquipmentGroupFilter() {
        for (const row of editor.querySelectorAll('[data-equipment-block]')) {
            const excluded = selectedEquipmentGroups !== null && (row.dataset.equipmentRollup
                ? !hasRowValues(row)
                : !selectedEquipmentGroups.has(row.dataset.equipmentFilterGroup));
            row.classList.toggle('territory-group-filter-hidden', excluded);
        }
    }

    function refreshEmptyRows() {
        const button = editor.querySelector('#territory-empty-rows');
        if (!button) return;
        const show = button.getAttribute('aria-pressed') === 'true';
        for (const row of editor.querySelectorAll('[data-value-row]')) {
            if (row.dataset.equipmentCheckSources) continue;
            const hasValues = hasRowValues(row);
            const note = row.querySelector('[data-field="note"]');
            const selectedGroup = selectedEquipmentGroups?.has(row.dataset.equipmentFilterGroup);
            row.hidden = !selectedGroup && !show && !hasValues && !(note && note.value.trim());
        }
        refreshEquipmentGroupFilter();
    }

    function sumEquipmentValues(values, signs = values.map(() => 1)) {
        const decimals = values.map(value => {
            const parts = (value || '0').match(/^([+-]?)(\d*)(?:\.(\d*))?(?:[eE]([+-]?\d+))?$/);
            const fraction = parts[3] || '';
            return {integer: BigInt(`${parts[1]}${parts[2]}${fraction}`),
                scale: fraction.length - Number(parts[4] || 0)};
        });
        const scale = Math.max(0, ...decimals.map(value => value.scale));
        const total = decimals.reduce((sum, value, index) =>
            sum + value.integer * BigInt(signs[index]) * 10n ** BigInt(scale - value.scale), 0n);
        const digits = (total < 0n ? -total : total).toString().padStart(scale + 1, '0');
        const raw = scale ? `${digits.slice(0, -scale)}.${digits.slice(-scale)}`.replace(/\.?0+$/, '') : digits;
        return `${total < 0n ? '-' : ''}${raw}`;
    }

    function refreshEquipmentVerification() {
        const rows = new Map([...editor.querySelectorAll('[data-equipment-row-key]')]
            .map(row => [row.dataset.equipmentRowKey, row]));
        for (const check of editor.querySelectorAll('[data-equipment-check-sources]')) {
            const sources = JSON.parse(check.dataset.equipmentCheckSources)
                .map(key => [...rows.get(key).querySelectorAll('[data-raw-value]')]);
            [...check.querySelectorAll('[data-raw-value]')].forEach((td, index) => {
                const raw = sumEquipmentValues(sources.map(row => row[index].dataset.rawValue), [1, -1, -1, -1]);
                td.dataset.rawValue = raw;
                td.title = format(raw, 'value', 0);
                td.textContent = format(raw, 'value', check.dataset.equipmentUnit === 'шт' ? -1 : editor.dataset.rounding);
                td.classList.toggle('territory-verification-error', raw !== '0');
            });
        }
    }

    function refreshEquipmentTotals() {
        const summaries = [...editor.querySelectorAll('[data-equipment-rollup]')]
            .filter(row => ['type', 'thermal', 'block'].includes(row.dataset.equipmentRollup));
        for (const summary of summaries) {
            for (const td of summary.querySelectorAll('[data-raw-value]')) {
                if (selectedEquipmentGroups !== null) {
                    if (!unfilteredEquipmentTotals.has(td)) {
                        unfilteredEquipmentTotals.set(td, {raw: td.dataset.rawValue, text: td.textContent, title: td.title});
                    }
                } else if (unfilteredEquipmentTotals.has(td)) {
                    const original = unfilteredEquipmentTotals.get(td);
                    td.dataset.rawValue = original.raw;
                    td.textContent = original.text;
                    td.title = original.title;
                    unfilteredEquipmentTotals.delete(td);
                }
            }
        }
        const leaves = [...editor.querySelectorAll('[data-equipment-group]')]
            .filter(row => !row.dataset.equipmentRollup
                && (selectedEquipmentGroups === null || selectedEquipmentGroups.has(row.dataset.equipmentFilterGroup)));
        for (const kind of ['type', 'thermal', 'block']) {
            for (const summary of summaries.filter(row => row.dataset.equipmentRollup === kind)) {
                const sources = (kind === 'type' ? leaves : summaries.filter(row => row.dataset.equipmentRollup === 'type'))
                    .filter(row => row.dataset.equipmentUnit === summary.dataset.equipmentUnit
                        && (kind === 'type' ? row.dataset.equipmentGroup === summary.dataset.equipmentGroup
                            : row.dataset.equipmentBlock === summary.dataset.equipmentBlock)
                        && (kind !== 'thermal' || row.dataset.equipmentGenerationType === 'ТЭС'));
                if (!sources.length && selectedEquipmentGroups === null) continue;
                const cells = sources.map(row => [...row.querySelectorAll('[data-raw-value]')]);
                [...summary.querySelectorAll('[data-raw-value]')].forEach((td, index) => {
                    const total = sumEquipmentValues(cells.map(row => row[index].dataset.rawValue));
                    const raw = total === '0' ? '' : total;
                    td.dataset.rawValue = raw;
                    td.title = format(raw, 'value', 0);
                    td.textContent = format(raw, 'value', summary.dataset.equipmentUnit === 'шт' ? -1 : editor.dataset.rounding);
                });
            }
        }
    }

    function enqueue(cell) {
        const state = states.get(cell);
        clearTimeout(state.timer);
        if (!dirty.has(cell) || state.enqueued === cell.value) return;
        const draft = cell.value;
        state.enqueued = draft;
        queue = queue.then(async () => {
            mark(cell, 'is-saving');
            if (status) { status.className = 'small text-muted'; status.textContent = 'Сохранение…'; }
            const payload = {
                database_version_id: Number(editor.dataset.versionId),
                sheet: editor.dataset.sheet,
                field: cell.dataset.field,
                value: draft,
            };
            if (cell.dataset.rowKey !== undefined) {
                Object.assign(payload, {energy_zone_id: Number(editor.dataset.zoneId), row_key: cell.dataset.rowKey});
                if (cell.dataset.year) payload.year = Number(cell.dataset.year);
            } else {
                Object.assign(payload, {row_id: Number(cell.dataset.rowId), zone_number: cell.dataset.zoneNumber});
            }
            try {
                const response = await fetch(editor.dataset.saveUrl, {
                    method: 'PATCH',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': editor.querySelector('[name="csrf_token"]')?.value || ''},
                    body: JSON.stringify(payload),
                });
                if (response.redirected) throw new Error('Сессия истекла. Войдите в систему и повторите сохранение.');
                const result = await response.json();
                if (!response.ok || !result.ok) throw new Error(result.error || 'Значение не сохранено.');
                cell.dataset.raw = result.value;
                if (result.year_values) {
                    for (const next of editor.querySelectorAll('.rs-cell-input')) {
                        if (next === cell || next.dataset.field !== 'value' || next.dataset.rowKey !== cell.dataset.rowKey
                            || !Object.hasOwn(result.year_values, next.dataset.year)) continue;
                        const value = result.year_values[next.dataset.year];
                        next.dataset.raw = value;
                        next.closest('td').dataset.rawValue = value;
                        if (!dirty.has(next)) {
                            next.value = format(value, next.dataset.field);
                            next.title = '';
                            mark(next, 'is-save-success');
                        }
                    }
                }
                for (const limit of editor.querySelectorAll('[data-limit-row-id]')) {
                    if (limit.dataset.limitRowId === cell.dataset.rowId && limit.dataset.limitField === cell.dataset.field) {
                        limit.textContent = result.value === '' ? '–' : format(String(Number(result.value) * Number(limit.dataset.limitSign)), cell.dataset.field);
                    }
                }
                if (cell.closest('td').hasAttribute('data-raw-value')) cell.closest('td').dataset.rawValue = result.value;
                if (cell.value === draft) {
                    dirty.delete(cell);
                    failed.delete(cell);
                    cell.title = '';
                    if (document.activeElement !== cell) cell.value = format(result.value, cell.dataset.field);
                    mark(cell, 'is-save-success');
                }
                if (status) {
                    status.className = failed.size ? 'small text-danger' : 'small text-success';
                    status.textContent = failed.size ? 'Есть несохраненные ячейки' : dirty.size ? 'Сохранение…' : 'Сохранено';
                }
                if (cell.dataset.field === 'value') {
                    refreshEquipmentTotals();
                    refreshEquipmentVerification();
                }
                refreshEmptyRows();
            } catch (error) {
                if (cell.value === draft) {
                    failed.add(cell);
                    state.enqueued = null;
                    cell.title = error.message;
                    mark(cell, 'is-save-error');
                }
                if (status) { status.className = 'small text-danger'; status.textContent = error.message; }
            }
            if (state.enqueued === draft) state.enqueued = null;
            retry.hidden = failed.size === 0;
        });
    }

    for (const cell of editor.querySelectorAll('.rs-cell-input')) {
        const state = {timer: null, enqueued: null};
        states.set(cell, state);
        cell.addEventListener('focus', () => {
            if (!dirty.has(cell)) cell.value = cell.dataset.raw;
        });
        cell.addEventListener('input', () => {
            dirty.add(cell);
            mark(cell, '');
            clearTimeout(state.timer);
            state.timer = setTimeout(() => enqueue(cell), 650);
        });
        cell.addEventListener('change', () => enqueue(cell));
        cell.addEventListener('blur', () => {
            enqueue(cell);
            if (!dirty.has(cell)) cell.value = format(cell.dataset.raw, cell.dataset.field);
        });
        cell.addEventListener('keydown', event => {
            if (event.key === 'Enter') { event.preventDefault(); enqueue(cell); cell.blur(); }
        });
    }
    retry.addEventListener('click', () => {
        for (const cell of failed) enqueue(cell);
    });
    for (const button of editor.querySelectorAll('[data-transfer-toggle]')) {
        button.addEventListener('click', () => {
            const expanded = button.getAttribute('aria-expanded') !== 'true';
            button.setAttribute('aria-expanded', String(expanded));
            button.title = expanded ? 'Скрыть составляющие суммы' : 'Показать составляющие суммы';
            button.setAttribute('aria-label', button.title);
            const icon = button.querySelector('.bi');
            icon.classList.toggle('bi-plus-square', !expanded);
            icon.classList.toggle('bi-dash-square', expanded);
            for (const row of editor.querySelectorAll('[data-transfer-parent]')) {
                if (row.dataset.transferParent === button.dataset.transferToggle) {
                    row.classList.toggle('territory-transfer-hidden', !expanded);
                }
            }
        });
    }
    editor.querySelector('#territory-empty-rows')?.addEventListener('click', event => {
        const button = event.currentTarget;
        const show = button.getAttribute('aria-pressed') !== 'true';
        button.setAttribute('aria-pressed', String(show));
        button.classList.toggle('btn-primary', show);
        button.classList.toggle('btn-outline-primary', !show);
        refreshEmptyRows();
    });
    editor.querySelector('#territory-equipment-counts')?.addEventListener('click', event => {
        const button = event.currentTarget;
        const show = button.getAttribute('aria-pressed') !== 'true';
        button.setAttribute('aria-pressed', String(show));
        button.classList.toggle('btn-primary', show);
        button.classList.toggle('btn-outline-primary', !show);
        button.title = show ? 'Скрыть строки с количеством агрегатов' : 'Показать строки с количеством агрегатов';
        for (const row of editor.querySelectorAll('[data-equipment-count-row]')) {
            row.classList.toggle('territory-count-hidden', !show);
        }
    });
    editor.querySelector('#territory-equipment-verification')?.addEventListener('click', event => {
        const button = event.currentTarget;
        const show = button.getAttribute('aria-pressed') !== 'true';
        button.setAttribute('aria-pressed', String(show));
        button.classList.toggle('btn-info', show);
        button.classList.toggle('btn-outline-info', !show);
        button.title = show ? 'Скрыть проверочный раздел' : 'Показать проверочный раздел';
        for (const row of editor.querySelectorAll('[data-equipment-verification]')) {
            row.classList.toggle('territory-verification-hidden', !show);
        }
        const link = editor.querySelector('[data-territory-export]');
        const url = new URL(link.href, window.location.href);
        if (show) url.searchParams.set('equipment_check', '1');
        else url.searchParams.delete('equipment_check');
        link.href = url.toString();
    });
    editor.querySelector('[data-export-saved-cells]')?.addEventListener('click', async event => {
        event.preventDefault();
        const link = event.currentTarget;
        if (!link.href) return;
        for (const cell of dirty) enqueue(cell);
        await queue;
        if (dirty.size) {
            if (status) {
                status.className = 'small text-danger';
                status.textContent = 'Перед выгрузкой сохраните все изменения. Есть несохраненные ячейки.';
            }
            return;
        }
        window.location.assign(link.href);
    });
    editor.querySelector('[data-rounding-control]')?.addEventListener('change', event => {
        const url = new URL(window.location.href);
        url.searchParams.set('rounding_digits', event.target.value);
        window.location.assign(url.toString());
    });
    const groupFilter = editor.querySelector('[data-equipment-filter]');
    if (groupFilter) {
        const toggle = groupFilter.querySelector('[data-equipment-filter-toggle]');
        const search = groupFilter.querySelector('[data-equipment-filter-search]');
        const selectAll = groupFilter.querySelector('[data-equipment-filter-all]');
        const options = groupFilter.querySelector('[data-equipment-filter-options]');
        const filterStatus = groupFilter.querySelector('[data-equipment-filter-status]');
        const groups = new Map();
        for (const row of editor.querySelectorAll('[data-equipment-filter-group]')) {
            groups.set(row.dataset.equipmentFilterGroup, row.dataset.equipmentFilterLabel);
        }
        const choices = [];
        for (const [id, name] of groups) {
            const label = document.createElement('label');
            label.className = 'd-flex gap-2 align-items-start py-1';
            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'form-check-input flex-shrink-0';
            checkbox.checked = true;
            const text = document.createElement('span');
            text.textContent = name;
            label.append(checkbox, text);
            options.append(label);
            choices.push({id, name, label, checkbox});
        }
        function refreshSelectAll() {
            const visible = choices.filter(choice => !choice.label.hidden);
            selectAll.checked = visible.length > 0 && visible.every(choice => choice.checkbox.checked);
            selectAll.indeterminate = visible.some(choice => choice.checkbox.checked) && !selectAll.checked;
        }
        function searchGroups() {
            const query = search.value.trim().toLocaleLowerCase('ru');
            for (const choice of choices) {
                choice.label.hidden = !choice.name.toLocaleLowerCase('ru').includes(query);
            }
            refreshSelectAll();
        }
        search.addEventListener('input', searchGroups);
        options.addEventListener('change', refreshSelectAll);
        selectAll.addEventListener('change', () => {
            for (const choice of choices) {
                if (!choice.label.hidden) choice.checkbox.checked = selectAll.checked;
            }
            refreshSelectAll();
        });
        groupFilter.addEventListener('show.bs.dropdown', () => {
            search.value = '';
            for (const choice of choices) {
                choice.checkbox.checked = selectedEquipmentGroups === null || selectedEquipmentGroups.has(choice.id);
            }
            searchGroups();
        });
        function applyGroups(reset) {
            const selected = choices.filter(choice => choice.checkbox.checked);
            selectedEquipmentGroups = reset || selected.length === choices.length
                ? null : new Set(selected.map(choice => choice.id));
            const active = selectedEquipmentGroups !== null;
            toggle.classList.toggle('btn-primary', active);
            toggle.classList.toggle('btn-outline-secondary', !active);
            filterStatus.textContent = active ? String(selected.length) : '';
            toggle.title = active ? `Фильтр групп оборудования: ${selected.length}` : 'Фильтр групп оборудования';
            refreshEquipmentTotals();
            refreshEquipmentVerification();
            refreshEmptyRows();
            toggle.click();
        }
        groupFilter.querySelector('[data-equipment-filter-apply]').addEventListener('click', () => applyGroups(false));
        groupFilter.querySelector('[data-equipment-filter-reset]').addEventListener('click', () => applyGroups(true));
    }
    window.addEventListener('beforeunload', event => {
        if (!dirty.size) return;
        event.preventDefault();
        event.returnValue = '';
    });
})();
