const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('app/static/js/rational_structure/territory_cells.js', 'utf8');
const tick = () => new Promise(resolve => setImmediate(resolve));

function element(properties = {}) {
    const handlers = {};
    const classes = new Set();
    const attributes = {};
    return Object.assign({
        hidden: false, value: '', dataset: {}, title: '',
        classList: {
            add: (...names) => names.forEach(name => classes.add(name)),
            remove: (...names) => names.forEach(name => classes.delete(name)),
            toggle: (name, active) => active ? classes.add(name) : classes.delete(name),
            contains: name => classes.has(name),
        },
        addEventListener: (event, handler) => { handlers[event] = handler; },
        emit(event) { return handlers[event]?.({currentTarget: this, preventDefault() {}}); },
        getAttribute: name => attributes[name],
        setAttribute: (name, value) => { attributes[name] = value; },
    }, properties);
}

function fixture(fetcher = async () => ({ok: true, json: async () => ({ok: true, value: '25.5'})}),
    {transferButtons = [], transferRows = [], extraCells = [], countButton = null, emptyButton = null,
        countRows = [], valueRows = [], rollupRows = [], equipmentRows = [], checkButton = null,
        checkRows = [], sourceRows = [], exportLink = null, savedExportLink = null} = {}) {
    let retry;
    const td = element({hasAttribute: () => false});
    const cell = element({value: '12,346', dataset: {field: 'value', rowKey: '0', year: '2025', raw: '12.3456789'}, closest: () => td});
    const status = element({after: button => { retry = button; }});
    const calls = [];
    const mirrors = [];
    const windowHandlers = {};
    const downloads = [];
    const editor = element({
        dataset: {saveUrl: '/cell', versionId: '1', zoneId: '10', sheet: 'years', rounding: '3'},
        querySelector: selector => ({
            '[data-save-status]': status, '[name="csrf_token"]': {value: 'token'},
            '#territory-equipment-counts': countButton, '#territory-empty-rows': emptyButton,
            '#territory-equipment-verification': checkButton, '[data-territory-export]': exportLink,
            '[data-export-saved-cells]': savedExportLink,
        })[selector] || null,
        querySelectorAll: selector => ({
            '.rs-cell-input': [cell, ...extraCells], '[data-limit-row-id]': mirrors,
            '[data-transfer-toggle]': transferButtons, '[data-transfer-parent]': transferRows,
            '[data-equipment-count-row]': countRows, '[data-value-row]': valueRows,
            '[data-equipment-rollup]': rollupRows, '[data-equipment-group]': equipmentRows,
            '[data-equipment-row-key]': sourceRows, '[data-equipment-check-sources]': checkRows,
            '[data-equipment-verification]': checkRows,
        })[selector] || [],
    });
    const document = {activeElement: null, querySelector: () => editor, createElement: () => element()};
    vm.runInNewContext(source, {
        document, window: {location: {href: 'http://localhost/territory_inputs', assign: href => downloads.push(href)},
            addEventListener: (event, handler) => { windowHandlers[event] = handler; }},
        Intl, URL, setTimeout: () => 1, clearTimeout: () => {},
        fetch: async (url, options) => { calls.push({url, options, body: JSON.parse(options.body)}); return fetcher(calls.length); },
    });
    return {cell, td, calls, status, retry, document, editor, windowHandlers, mirrors, downloads,
        edit(value) { document.activeElement = cell; cell.emit('focus'); cell.value = value; cell.emit('input'); cell.emit('change'); },
    };
}

test('focusing a rounded cell without editing does not save or lose full precision', async () => {
    const ui = fixture();
    ui.document.activeElement = ui.cell;
    ui.cell.emit('focus');
    assert.equal(ui.cell.value, '12.3456789');
    ui.document.activeElement = null;
    ui.cell.emit('blur');
    await tick();
    assert.equal(ui.calls.length, 0);
    assert.equal(ui.cell.dataset.raw, '12.3456789');
    assert.equal(ui.cell.value, '12,346');
});

test('saving sends the edited cell with version, zone and CSRF and highlights it green', async () => {
    const ui = fixture();
    ui.edit('25,5');
    await tick();
    assert.deepEqual(ui.calls[0].body, {database_version_id: 1, energy_zone_id: 10, sheet: 'years', row_key: '0', year: 2025, field: 'value', value: '25,5'});
    assert.equal(ui.calls[0].options.headers['X-CSRFToken'], 'token');
    assert.equal(ui.cell.dataset.raw, '25.5');
    assert.equal(ui.td.classList.contains('is-save-success'), true);
    assert.equal(ui.status.textContent, 'Сохранено');
});

test('failed save retains the draft, marks red and retries without retyping', async () => {
    const ui = fixture(async attempt => attempt === 1
        ? {ok: false, json: async () => ({ok: false, error: 'storage unavailable'})}
        : {ok: true, json: async () => ({ok: true, value: '25.5'})});
    ui.edit('25,5');
    await tick();
    assert.equal(ui.cell.value, '25,5');
    assert.equal(ui.cell.dataset.raw, '12.3456789');
    assert.equal(ui.td.classList.contains('is-save-error'), true);
    assert.equal(ui.retry.hidden, false);
    let prevented = false;
    ui.windowHandlers.beforeunload({preventDefault() { prevented = true; }});
    assert.equal(prevented, true);
    ui.retry.emit('click');
    await tick();
    assert.equal(ui.calls.length, 2);
    assert.equal(ui.td.classList.contains('is-save-error'), false);
    assert.equal(ui.td.classList.contains('is-save-success'), true);
    assert.equal(ui.retry.hidden, true);
});

test('rapid edits are saved sequentially and an older response does not overwrite the draft', async () => {
    let release;
    const ui = fixture(async attempt => {
        if (attempt === 1) await new Promise(resolve => { release = resolve; });
        return {ok: true, json: async () => ({ok: true, value: attempt === 1 ? '20' : '30'})};
    });
    ui.edit('20');
    await tick();
    ui.cell.value = '30'; ui.cell.emit('input'); ui.cell.emit('change');
    await tick();
    assert.equal(ui.calls.length, 1);
    release();
    await tick();
    assert.equal(ui.calls.length, 2);
    assert.equal(ui.cell.value, '30');
    assert.equal(ui.cell.dataset.raw, '30');
});

test('Excel download waits for pending cell changes to be saved', async () => {
    let release;
    const link = element({href: '/territory_technologies/export?rounding_digits=3'});
    const ui = fixture(async () => {
        await new Promise(resolve => { release = resolve; });
        return {ok: true, json: async () => ({ok: true, value: '25.5'})};
    }, {savedExportLink: link});
    ui.cell.value = '25,5';
    ui.cell.emit('input');
    const download = link.emit('click');
    await tick();
    assert.equal(ui.calls[0].body.value, '25,5');
    assert.deepEqual(ui.downloads, []);
    release();
    await download;
    assert.deepEqual(ui.downloads, [link.href]);
    assert.equal(ui.cell.dataset.raw, '25.5');
});

test('Excel download is blocked when cell saving fails and can be retried', async () => {
    const link = element({href: '/territory_technologies/export'});
    const ui = fixture(async attempt => attempt === 1
        ? {ok: false, json: async () => ({ok: false, error: 'storage unavailable'})}
        : {ok: true, json: async () => ({ok: true, value: '25.5'})}, {savedExportLink: link});
    ui.cell.value = '25,5';
    ui.cell.emit('input');
    await link.emit('click');
    assert.deepEqual(ui.downloads, []);
    assert.match(ui.status.textContent, /несохраненные/);
    await link.emit('click');
    assert.deepEqual(ui.downloads, [link.href]);
});

test('Excel download without edits does not save cells', async () => {
    const link = element({href: '/territory_technologies/export'});
    const ui = fixture(undefined, {savedExportLink: link});
    await link.emit('click');
    assert.equal(ui.calls.length, 0);
    assert.deepEqual(ui.downloads, [link.href]);
});

test('transfer totals expand and collapse only their own detail rows without saving', () => {
    const attributes = {'aria-expanded': 'false'};
    const icon = element();
    icon.classList.add('bi-plus-square');
    const button = element({
        dataset: {transferToggle: '7'},
        getAttribute: name => attributes[name],
        setAttribute: (name, value) => { attributes[name] = value; },
        querySelector: () => icon,
    });
    const exportRow = element({dataset: {transferParent: '7'}});
    const importRow = element({dataset: {transferParent: '9'}});
    exportRow.classList.add('territory-transfer-hidden');
    importRow.classList.add('territory-transfer-hidden');
    const ui = fixture(undefined, {transferButtons: [button], transferRows: [exportRow, importRow]});
    button.emit('click');
    assert.equal(attributes['aria-expanded'], 'true');
    assert.equal(exportRow.classList.contains('territory-transfer-hidden'), false);
    assert.equal(importRow.classList.contains('territory-transfer-hidden'), true);
    assert.equal(icon.classList.contains('bi-dash-square'), true);
    button.emit('click');
    assert.equal(attributes['aria-expanded'], 'false');
    assert.equal(exportRow.classList.contains('territory-transfer-hidden'), true);
    assert.equal(icon.classList.contains('bi-plus-square'), true);
    assert.equal(ui.calls.length, 0);
});

test('count rows stay hidden by default and toggle independently of empty rows without saving', () => {
    const countButton = element();
    countButton.setAttribute('aria-pressed', 'false');
    const emptyButton = element();
    emptyButton.setAttribute('aria-pressed', 'true');
    const header = element();
    const valueRow = raw => element({
        querySelectorAll: () => [element({dataset: {rawValue: raw}, querySelector: () => null})],
        querySelector: () => null,
    });
    const populated = valueRow('1');
    const empty = valueRow('');
    const power = valueRow('150');
    const countRows = [header, populated, empty];
    countRows.forEach(row => row.classList.add('territory-count-hidden'));
    const ui = fixture(undefined, {countButton, emptyButton, countRows, valueRows: [populated, empty, power]});
    assert.equal(countButton.getAttribute('aria-pressed'), 'false');
    assert.ok(countRows.every(row => row.classList.contains('territory-count-hidden')));

    emptyButton.emit('click');
    assert.equal(empty.hidden, true);
    assert.ok(countRows.every(row => row.classList.contains('territory-count-hidden')));
    countButton.emit('click');
    assert.equal(countButton.getAttribute('aria-pressed'), 'true');
    assert.equal(countButton.classList.contains('btn-primary'), true);
    assert.ok(countRows.every(row => !row.classList.contains('territory-count-hidden')));
    assert.equal(populated.hidden, false);
    assert.equal(empty.hidden, true);
    assert.equal(power.hidden, false);
    assert.equal(power.classList.contains('territory-count-hidden'), false);

    emptyButton.emit('click');
    assert.equal(empty.hidden, false);
    countButton.emit('click');
    assert.equal(countButton.getAttribute('aria-pressed'), 'false');
    assert.equal(countButton.classList.contains('btn-outline-primary'), true);
    assert.ok(countRows.every(row => row.classList.contains('territory-count-hidden')));
    emptyButton.emit('click');
    emptyButton.emit('click');
    assert.ok(countRows.every(row => row.classList.contains('territory-count-hidden')));
    assert.equal(ui.calls.length, 0);
});

test('equipment block grouping stays independent of counts, empty rows and other blocks', () => {
    const makeButton = block => {
        const icon = element();
        icon.classList.add('bi-dash-square');
        const button = element({dataset: {transferToggle: block}, querySelector: () => icon});
        button.setAttribute('aria-expanded', 'true');
        return button;
    };
    const first = makeButton('equipment_block_0');
    const second = makeButton('equipment_block_1');
    const countButton = element();
    countButton.setAttribute('aria-pressed', 'false');
    const emptyButton = element();
    emptyButton.setAttribute('aria-pressed', 'true');
    const makeRow = (block, raw) => element({dataset: {transferParent: block}, querySelector: () => null,
        querySelectorAll: () => [element({dataset: {rawValue: raw}, querySelector: () => null})]});
    const count = makeRow('equipment_block_0', '2');
    const empty = makeRow('equipment_block_0', '');
    const power = makeRow('equipment_block_0', '150');
    const other = makeRow('equipment_block_1', '50');
    count.classList.add('territory-count-hidden');
    empty.classList.add('territory-count-hidden');
    const ui = fixture(undefined, {transferButtons: [first, second], transferRows: [count, empty, power, other],
        countButton, emptyButton, countRows: [count, empty], valueRows: [count, empty, power, other]});
    first.emit('click');
    assert.equal(first.getAttribute('aria-expanded'), 'false');
    assert.ok(power.classList.contains('territory-transfer-hidden'));
    assert.equal(other.classList.contains('territory-transfer-hidden'), false);
    countButton.emit('click');
    assert.equal(count.classList.contains('territory-count-hidden'), false);
    assert.ok(count.classList.contains('territory-transfer-hidden'));
    emptyButton.emit('click');
    first.emit('click');
    assert.equal(power.classList.contains('territory-transfer-hidden'), false);
    assert.equal(count.classList.contains('territory-transfer-hidden'), false);
    assert.equal(empty.hidden, true);
    countButton.emit('click');
    second.emit('click');
    assert.ok(count.classList.contains('territory-count-hidden'));
    assert.equal(power.classList.contains('territory-transfer-hidden'), false);
    assert.ok(other.classList.contains('territory-transfer-hidden'));
    assert.equal(ui.calls.length, 0);
});

test('saving equipment power updates type and block totals without counting quantity or clearing storage', async () => {
    const td = raw => element({dataset: {rawValue: raw}});
    const row = (dataset, cell) => element({dataset, querySelectorAll: () => [cell]});
    const typeCell = td('22.3456789');
    const blockCell = td('122.3456789');
    const storageCell = td('100');
    const countCell = td('7');
    const otherCell = td('17');
    const typeData = {equipmentRollup: 'type', equipmentBlock: 'b0', equipmentGroup: 'g0', equipmentUnit: 'МВт'};
    const summaries = [row(typeData, typeCell),
        row({equipmentRollup: 'block', equipmentBlock: 'b0', equipmentUnit: 'МВт'}, blockCell),
        row({...typeData, equipmentGroup: 'storage'}, storageCell),
        row({...typeData, equipmentUnit: 'шт'}, countCell),
        row({...typeData, equipmentGroup: 'other', equipmentBlock: 'b1'}, otherCell)];
    let ui;
    const editableRow = element({dataset: {equipmentGroup: 'g0', equipmentBlock: 'b0', equipmentUnit: 'МВт'},
        querySelectorAll: () => [ui.td]});
    const staticRow = row({equipmentGroup: 'g0', equipmentBlock: 'b0', equipmentUnit: 'МВт'}, td('10'));
    const quantityRow = row({equipmentGroup: 'g0', equipmentBlock: 'b0', equipmentUnit: 'шт'}, td('7'));
    ui = fixture(undefined, {rollupRows: summaries, equipmentRows: [editableRow, staticRow, quantityRow, ...summaries]});
    ui.td.hasAttribute = name => name === 'data-raw-value';
    ui.td.dataset.rawValue = '12.3456789';
    ui.edit('25.5');
    await tick();
    assert.equal(typeCell.dataset.rawValue, '35.5');
    assert.equal(typeCell.textContent, '35,500');
    assert.equal(blockCell.dataset.rawValue, '135.5');
    assert.equal(storageCell.dataset.rawValue, '100');
    assert.equal(countCell.dataset.rawValue, '7');
    assert.equal(countCell.textContent, '7');
    assert.equal(otherCell.dataset.rawValue, '17');
    assert.equal(ui.calls.length, 1);
});

test('saving a reverse limit updates its signed footer without changing another section', async () => {
    const ui = fixture();
    ui.cell.dataset = {field: 'reverse_limit', rowId: '7', raw: '90'};
    ui.editor.dataset.sheet = 'transfers';
    const footer = element({textContent: '-90,000', dataset: {limitRowId: '7', limitField: 'reverse_limit', limitSign: '-1'}});
    const otherSection = element({textContent: '-80,000', dataset: {limitRowId: '8', limitField: 'reverse_limit', limitSign: '-1'}});
    const forwardLimit = element({textContent: '100,000', dataset: {limitRowId: '7', limitField: 'forward_limit', limitSign: '1'}});
    ui.mirrors.push(footer, otherSection, forwardLimit);
    ui.edit('25,5');
    await tick();
    assert.deepEqual(ui.calls[0].body, {database_version_id: 1, sheet: 'transfers', row_id: 7, field: 'reverse_limit', value: '25,5'});
    assert.equal(footer.textContent, '-25,500');
    assert.equal(otherSection.textContent, '-80,000');
    assert.equal(forwardLimit.textContent, '100,000');
});

test('verification toggles independently, uses the summary button styles and exports only when enabled', () => {
    const button = element();
    button.setAttribute('aria-pressed', 'false');
    button.classList.add('btn-outline-info');
    const power = element();
    const count = element();
    for (const row of [power, count]) row.classList.add('territory-verification-hidden');
    count.classList.add('territory-count-hidden');
    const exportLink = {href: 'http://localhost/export?sheet=equipment&energy_zone_id=387'};
    const ui = fixture(undefined, {checkButton: button, checkRows: [power, count], exportLink});
    button.emit('click');
    assert.equal(button.getAttribute('aria-pressed'), 'true');
    assert.ok(button.classList.contains('btn-info'));
    assert.equal(button.classList.contains('btn-outline-info'), false);
    assert.equal(power.classList.contains('territory-verification-hidden'), false);
    assert.ok(count.classList.contains('territory-count-hidden'));
    assert.equal(new URL(exportLink.href).searchParams.get('equipment_check'), '1');
    assert.equal(new URL(exportLink.href).searchParams.get('energy_zone_id'), '387');
    button.emit('click');
    assert.equal(button.getAttribute('aria-pressed'), 'false');
    assert.ok(button.classList.contains('btn-outline-info'));
    assert.ok(power.classList.contains('territory-verification-hidden'));
    assert.ok(count.classList.contains('territory-verification-hidden'));
    assert.equal(new URL(exportLink.href).searchParams.has('equipment_check'), false);
    assert.equal(ui.calls.length, 0);
});

test('verification aggregation collapses only its children and survives the verification visibility toggle', () => {
    const icon = element();
    icon.classList.add('bi-dash-square');
    const collapse = element({dataset: {transferToggle: 'equipment_check'}, querySelector: () => icon});
    collapse.setAttribute('aria-expanded', 'true');
    const checkButton = element();
    checkButton.setAttribute('aria-pressed', 'false');
    const root = element();
    const power = element({dataset: {transferParent: 'equipment_check'}});
    const count = element({dataset: {transferParent: 'equipment_check'}});
    const other = element({dataset: {transferParent: 'equipment_block_0'}});
    const checkRows = [root, power, count];
    for (const row of checkRows) row.classList.add('territory-verification-hidden');
    count.classList.add('territory-count-hidden');
    const ui = fixture(undefined, {checkButton, checkRows, transferButtons: [collapse],
        transferRows: [power, count, other], exportLink: {href: 'http://localhost/export'}});
    checkButton.emit('click');
    collapse.emit('click');
    assert.equal(collapse.getAttribute('aria-expanded'), 'false');
    assert.ok(icon.classList.contains('bi-plus-square'));
    assert.ok(power.classList.contains('territory-transfer-hidden'));
    assert.ok(count.classList.contains('territory-transfer-hidden'));
    assert.equal(root.classList.contains('territory-transfer-hidden'), false);
    assert.equal(other.classList.contains('territory-transfer-hidden'), false);
    checkButton.emit('click');
    checkButton.emit('click');
    assert.ok(power.classList.contains('territory-transfer-hidden'));
    collapse.emit('click');
    assert.equal(collapse.getAttribute('aria-expanded'), 'true');
    assert.ok(icon.classList.contains('bi-dash-square'));
    assert.equal(power.classList.contains('territory-transfer-hidden'), false);
    assert.equal(count.classList.contains('territory-transfer-hidden'), false);
    assert.ok(count.classList.contains('territory-count-hidden'));
    assert.equal(ui.calls.length, 0);
});

for (const [before, remaining, expected] of [
    ['0.3', '', '0'], ['0.3000000001', '', '0.0000000001'], ['0.2999999999', '', '-0.0000000001'],
    ['1e3', '999.7', '0'],
]) {
    test(`verification refreshes after saving with exact decimals: ${before} -> ${expected}`, async () => {
        const checkCell = element({dataset: {rawValue: 'old'}});
        checkCell.classList.add('territory-verification-error');
        const check = element({dataset: {equipmentCheckSources: '["total","first","second","after"]', equipmentUnit: 'МВт'},
            querySelectorAll: () => [checkCell]});
        const row = (key, td) => element({dataset: {equipmentRowKey: key}, querySelectorAll: () => [td]});
        let ui;
        const first = element({dataset: {equipmentRowKey: 'first'}, querySelectorAll: () => [ui.td]});
        const sources = [row('total', element({dataset: {rawValue: before}})), first,
            row('second', element({dataset: {rawValue: '0.2'}})), row('after', element({dataset: {rawValue: remaining}}))];
        ui = fixture(async () => ({ok: true, json: async () => ({ok: true, value: '0.1'})}),
            {checkRows: [check], sourceRows: sources});
        ui.td.hasAttribute = name => name === 'data-raw-value';
        ui.edit('0,1');
        await tick();
        assert.equal(checkCell.dataset.rawValue, expected);
        assert.equal(checkCell.classList.contains('territory-verification-error'), expected !== '0');
        assert.equal(checkCell.title, expected.replace('.', ','));
    });
}

test('empty rows control keeps zero verification rows available', () => {
    const button = element();
    button.setAttribute('aria-pressed', 'true');
    const check = element({dataset: {equipmentCheckSources: '[]'}, querySelectorAll: () => [], querySelector: () => null});
    const ui = fixture(undefined, {emptyButton: button, valueRows: [check]});
    button.emit('click');
    assert.equal(check.hidden, false);
    assert.equal(ui.calls.length, 0);
});

function rateCell(year, rowKey = '24') {
    const td = element({hasAttribute: name => name === 'data-raw-value', dataset: {rawValue: '4'}});
    return element({value: '4,000', dataset: {field: 'value', rowKey, year, raw: '4'}, closest: () => td});
}

test('EES rate save fills subsequent years and marks saved cells green without changing preceding years or other rows', async () => {
    const previous = rateCell('2025');
    const next = rateCell('2027');
    const last = rateCell('2042');
    const other = rateCell('2027', '6');
    const ui = fixture(async () => ({ok: true, json: async () => ({
        ok: true, value: '5.123456789', year_values: {'2026': '5.123456789', '2027': '5.123456789', '2042': '5.123456789'},
    })}), {extraCells: [previous, next, last, other]});
    ui.cell.dataset.rowKey = '24';
    ui.cell.dataset.year = '2026';
    ui.editor.dataset.zoneId = '0';
    ui.edit('5,123456789');
    await tick();
    assert.equal(ui.calls.length, 1);
    assert.equal(ui.calls[0].body.energy_zone_id, 0);
    for (const cell of [next, last]) {
        assert.equal(cell.dataset.raw, '5.123456789');
        assert.equal(cell.value, '5,123');
        assert.equal(cell.closest('td').dataset.rawValue, '5.123456789');
        assert.equal(cell.closest('td').classList.contains('is-save-success'), true);
    }
    assert.equal(ui.cell.classList.contains('is-save-success'), true);
    assert.equal(previous.dataset.raw, '4');
    assert.equal(other.dataset.raw, '4');
});

test('failed EES rate save is red and leaves following years unchanged until a successful retry', async () => {
    const next = rateCell('2027');
    const ui = fixture(async attempt => attempt === 1
        ? {ok: false, json: async () => ({ok: false, error: 'storage unavailable'})}
        : {ok: true, json: async () => ({ok: true, value: '5', year_values: {'2026': '5', '2027': '5'}})},
    {extraCells: [next]});
    ui.cell.dataset.rowKey = '24';
    ui.cell.dataset.year = '2026';
    ui.editor.dataset.zoneId = '0';
    ui.edit('5');
    await tick();
    assert.equal(ui.cell.classList.contains('is-save-error'), true);
    assert.equal(next.dataset.raw, '4');
    assert.equal(next.classList.contains('is-save-success'), false);
    ui.retry.emit('click');
    await tick();
    assert.equal(ui.cell.classList.contains('is-save-error'), false);
    assert.equal(ui.cell.classList.contains('is-save-success'), true);
    assert.equal(next.dataset.raw, '5');
    assert.equal(next.classList.contains('is-save-success'), true);
});

test('prolongation does not overwrite a newer draft in a subsequent cell', async () => {
    let release;
    const next = rateCell('2027');
    const ui = fixture(async attempt => {
        if (attempt === 1) await new Promise(resolve => { release = resolve; });
        const value = attempt === 1 ? '5' : '8';
        return {ok: true, json: async () => ({ok: true, value, year_values: {'2027': value}})};
    }, {extraCells: [next]});
    ui.cell.dataset.rowKey = '24';
    ui.cell.dataset.year = '2026';
    ui.editor.dataset.zoneId = '0';
    ui.edit('5');
    await tick();
    next.value = '8';
    next.emit('input');
    next.emit('change');
    release();
    await tick();
    assert.equal(next.value, '8,000');
    assert.equal(next.dataset.raw, '8');
    assert.equal(ui.calls.length, 2);
    assert.equal(ui.calls[1].body.year, 2027);
    assert.equal(ui.calls[1].body.value, '8');
});

test('clearing the EES rate clears subsequent values after successful saving', async () => {
    const next = rateCell('2027');
    const ui = fixture(async () => ({ok: true, json: async () => ({
        ok: true, value: '', year_values: {'2026': '', '2027': ''},
    })}), {extraCells: [next]});
    ui.cell.dataset.rowKey = '24';
    ui.cell.dataset.year = '2026';
    ui.editor.dataset.zoneId = '0';
    ui.edit('');
    await tick();
    assert.equal(next.value, '');
    assert.equal(next.dataset.raw, '');
    assert.equal(next.classList.contains('is-save-success'), true);
});
