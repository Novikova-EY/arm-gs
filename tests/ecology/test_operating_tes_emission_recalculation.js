const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const template = fs.readFileSync(path.join(__dirname, '../../app/templates/ecology/operating_tes/operating_tes_table.html'), 'utf8');
const start = template.indexOf('    const getFieldValue = function');
assert.notEqual(start, -1);
const end = template.indexOf('\n    const CSRF', start);

function setup({total = '1234.5678', digits = '2', defaultCoefficient = '0.85'} = {}) {
    const target = {textContent: 'initial'};
    const field = {value: '', dataset: {
        emittedKey: 'ash_emitted', column: 'centr:2026', captureTotal: total, defaultCoefficient
    }};
    const table = {
        dataset: {roundingDigits: digits},
        querySelector(selector) {
            assert.equal(selector, 'tr[data-row-key="ash_emitted"] td[data-column="centr:2026"]');
            return target;
        }
    };
    field.closest = () => table;
    const context = vm.createContext({table});
    vm.runInContext(template.slice(start, end) + '\nglobalThis.recalculate = recalculateEmitted;', context);
    return {
        field, target,
        enter(value) { field.value = value; context.recalculate(field); return target.textContent; }
    };
}

test('emitted mass updates immediately using full mass and Russian decimal input', () => {
    const row = setup();
    assert.equal(row.enter('0,25'), '925,93');
    assert.equal(row.enter('0.5'), '617,28');
    assert.equal(row.enter('1'), '0');
    assert.equal(row.enter('0'), '1 234,57');
});

test('rounding options match the page: -1 integer, 0 unrounded, positive decimal places', () => {
    assert.equal(setup({digits: '-1'}).enter('0'), '1 235');
    assert.equal(setup({digits: '0'}).enter('0'), '1 234,5678');
    assert.equal(setup({digits: '1'}).enter('0'), '1 234,6');
    assert.equal(setup({digits: '3'}).enter('0'), '1 234,568');
});

test('clearing restores the reference coefficient, including zero and full suppression', () => {
    assert.equal(setup().enter(''), '185,19');
    assert.equal(setup({defaultCoefficient: '0'}).enter('  '), '1 234,57');
    assert.equal(setup({defaultCoefficient: '1'}).enter(''), '0');
});

test('missing mass and invalid drafts do not produce a misleading number', () => {
    assert.equal(setup({total: ''}).enter('0,5'), '–');
    for (const value of ['bad', 'NaN', 'Infinity']) {
        assert.equal(setup().enter(value), '–');
    }
    assert.equal(setup({total: '0'}).enter('0,85'), '0');
});

test('other editable fields do not change emission values', () => {
    const row = setup();
    delete row.field.dataset.emittedKey;
    assert.equal(row.enter('0.5'), 'initial');
});

function editableCoefficient({digits = '1', success = true, count = 1, pasteActive = false} = {}) {
    const listeners = {};
    const classes = new Set();
    const cell = {classList: {
        add(name) { classes.add(name); },
        remove(...names) { names.forEach(name => classes.delete(name)); }
    }, removeAttribute() {}};
    const field = {
        value: '0,9',
        dataset: {
            rawValue: '0,8567', emittedKey: 'ash_emitted', captureTotal: '1000',
            defaultCoefficient: '0.85', column: 'vsego:2026', year: '2026',
            territory: 'vsego', affiliation: 'all', field: 'ash_eta', updateUrl: '/koeff/value/'
        },
        classList: {add() {}, remove() {}},
        setAttribute() {}, removeAttribute() {},
        closest(selector) { return selector === 'td' ? cell : {dataset: {rowKey: 'ash_eta'}}; },
        addEventListener(name, listener) { listeners[name] = listener; }
    };
    const target = {textContent: '143,3'};
    const fields = [field];
    const targets = [target];
    const fieldListeners = [listeners];
    const row = {dataset: {rowKey: 'ash_eta'}, querySelectorAll() { return fields; }};
    field.closest = selector => selector === 'td' ? cell : selector === 'table' ? table : row;
    for (let i = 1; i < count; i++) {
        const nextListeners = {};
        fields.push({
            ...field,
            dataset: {...field.dataset, column: `territory${i}:2026`, territory: `territory${i}`},
            addEventListener(name, listener) { nextListeners[name] = listener; }
        });
        targets.push({textContent: '143,3'});
        fieldListeners.push(nextListeners);
    }
    const requests = [];
    const table = {
        dataset: {roundingDigits: '2', coefficientRoundingDigits: digits, canEdit: '1', updateUrl: '/zola/value/', autosave: '1'},
        querySelector(selector) {
            const index = fields.findIndex(item => selector.includes(`data-column="${item.dataset.column}"`));
            return targets[index];
        },
        querySelectorAll() { return fields; }
    };
    const context = vm.createContext({
        table, document: {querySelectorAll() { return [table]; }},
        window: {__armGsTableRowPasteActive: pasteActive},
        setTimeout() { return 1; }, clearTimeout() {},
        async fetch(url, options) {
            requests.push({url, body: JSON.parse(options.body)});
            return {ok: success, async json() { return {ok: success, error: 'Save failed'}; }};
        }
    });
    const scriptEnd = template.indexOf('\n  });', start);
    const script = template.slice(start, scriptEnd).replace(/const CSRF = .*;/, "const CSRF = 'test-token';");
    vm.runInContext(script, context);
    return {field, target, fields, targets, requests, classes,
        emit(name, index = 0) { fieldListeners[index][name](); }};
}

test('focusing exposes full precision and blurring restores rounded display without saving', () => {
    const row = editableCoefficient();
    row.emit('focus');
    assert.equal(row.field.value, '0,8567');
    row.emit('change');
    row.emit('blur');
    assert.equal(row.field.value, '0,9');
    assert.equal(row.field.dataset.rawValue, '0,8567');
    assert.equal(row.requests.length, 0);
});

test('saving and recalculation use full precision even after the input loses focus', async () => {
    const row = editableCoefficient();
    row.emit('focus');
    row.field.value = '0,85321';
    row.emit('input');
    assert.equal(row.target.textContent, '146,79');
    row.emit('change');
    row.emit('blur');
    assert.equal(row.field.value, '0,9');
    await new Promise(setImmediate);
    assert.equal(row.requests.length, 1);
    assert.equal(row.requests[0].url, '/koeff/value/');
    assert.equal(row.requests[0].body.value, '0,85321');
    assert.equal(row.field.dataset.rawValue, '0,85321');
    assert.ok(row.classes.has('is-save-success'));
    row.emit('focus');
    assert.equal(row.field.value, '0,85321');
});

test('failed saves remain red after rounded display is restored', async () => {
    const row = editableCoefficient({success: false});
    row.emit('focus');
    row.field.value = '0,85321';
    row.emit('input');
    row.emit('change');
    row.emit('blur');
    await new Promise(setImmediate);
    assert.equal(row.requests.length, 1);
    assert.ok(row.classes.has('is-save-error'));
    assert.ok(!row.classes.has('is-save-success'));
});

test('coefficient precision modes do not alter the raw input or mass rounding', () => {
    for (const [digits, display] of [['-1', '1'], ['0', '0,8567'], ['1', '0,9'], ['2', '0,86'], ['3', '0,857']]) {
        const row = editableCoefficient({digits});
        row.emit('focus');
        row.emit('input');
        row.emit('blur');
        assert.equal(row.field.value, display);
        assert.equal(row.field.dataset.rawValue, '0,8567');
        assert.equal(row.target.textContent, '143,3');
    }
});

test('cleared and invalid coefficients are not displayed as a rounded zero', () => {
    for (const value of ['', 'bad']) {
        const row = editableCoefficient();
        row.emit('focus');
        row.field.value = value;
        row.emit('input');
        row.emit('blur');
        assert.equal(row.field.value, value);
        assert.equal(row.field.dataset.rawValue, value);
    }
});

test('editing a coefficient recalculates and saves only the selected territory', async () => {
    const row = editableCoefficient({count: 4});
    row.emit('focus', 1);
    row.fields[1].value = '0,75321';
    row.emit('input', 1);
    assert.deepEqual(row.fields.map(field => field.dataset.rawValue),
        ['0,8567', '0,75321', '0,8567', '0,8567']);
    assert.deepEqual(row.fields.map(field => field.value), ['0,9', '0,75321', '0,9', '0,9']);
    assert.deepEqual(row.targets.map(target => target.textContent), ['143,3', '246,79', '143,3', '143,3']);
    row.emit('change', 1);
    row.emit('blur', 1);
    await new Promise(setImmediate);
    assert.deepEqual(row.requests.map(request => [request.body.territory, request.body.value]),
        [['territory1', '0,75321']]);
    row.emit('focus', 3);
    assert.equal(row.fields[3].value, '0,8567');
});

test('editing zero or the last cell leaves other coefficient values intact', async () => {
    const row = editableCoefficient({count: 3});
    row.emit('focus');
    row.field.value = '0';
    row.emit('input');
    row.emit('change');
    await new Promise(setImmediate);
    assert.deepEqual(row.fields.map(field => field.dataset.rawValue), ['0', '0,8567', '0,8567']);
    assert.deepEqual(row.targets.map(target => target.textContent), ['1 000', '143,3', '143,3']);
    assert.equal(row.requests.length, 1);
    row.emit('focus', 2);
    row.fields[2].value = '1';
    row.emit('input', 2);
    row.emit('change', 2);
    await new Promise(setImmediate);
    assert.deepEqual(row.fields.map(field => field.dataset.rawValue), ['0', '0,8567', '1']);
    assert.equal(row.requests.length, 2);
});

test('clearing, unchanged focus and row paste do not overwrite later coefficients', async () => {
    for (const mode of ['clear', 'unchanged', 'paste']) {
        const row = editableCoefficient({count: 3, pasteActive: mode === 'paste'});
        row.emit('focus');
        if (mode !== 'unchanged') {
            row.field.value = mode === 'clear' ? '' : '0,25';
            row.emit('input');
        }
        row.emit('change');
        row.emit('blur');
        await new Promise(setImmediate);
        assert.deepEqual(row.fields.slice(1).map(field => field.dataset.rawValue), ['0,8567', '0,8567']);
        assert.equal(row.requests.length, mode === 'unchanged' ? 0 : 1);
    }
});
