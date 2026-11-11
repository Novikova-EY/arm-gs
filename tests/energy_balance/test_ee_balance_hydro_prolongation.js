const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const template = fs.readFileSync('app/templates/energy_balance/ee_balance/ee_balance_ves_ses.html', 'utf8');
const source = template.slice(template.indexOf('    function extendHydroCoefficient('), template.indexOf('    function materializeDeferred('));

function rowEditor(values, deferred = [], { kind = 'coefficient', group = false } = {}) {
    const saved = [];
    const context = { window: {}, saveInput: input => saved.push(input.value) };
    vm.createContext(context);
    vm.runInContext(source, context);
    const liveSource = fs.readFileSync('app/static/js/energy_balance/ee_balance_ves_ses_live.js', 'utf8');
    vm.runInContext(liveSource.slice(liveSource.indexOf('    function parseNum('), liveSource.indexOf('    function setControlDisplay(')), context);
    const inputs = values.map((value, index) => {
        const attrs = { 'data-kind': kind, 'data-year': String(2026 + index), 'data-orig': value, 'data-raw': value };
        const listeners = {};
        return {
            value, textContent: value, tagName: deferred.includes(index) ? 'SPAN' : 'INPUT',
            dataset: {}, readOnly: false, disabled: false,
            classList: { contains: () => false },
            getAttribute: name => attrs[name] ?? null,
            setAttribute: (name, value) => { attrs[name] = value; },
            hasAttribute: name => Object.hasOwn(attrs, name),
            removeAttribute: name => { delete attrs[name]; },
            addEventListener: (name, callback) => { listeners[name] = callback; },
            fire: name => listeners[name](),
            closest: () => ({
                getAttribute: name => name === 'data-is-group' && group ? '1' : null,
                querySelectorAll: () => inputs,
            }),
        };
    });
    inputs.forEach(input => context.bindMaterializedInput(input));
    return { inputs, saved, context };
}

test('typing a coefficient overwrites only later years and saving includes the entered value', () => {
    const { inputs, saved } = rowEditor(['0,01', '0,02', '', '0,09']);
    inputs[1].value = '0,03';
    inputs[1].fire('input');
    assert.deepEqual(inputs.map(input => input.value), ['0,01', '0,03', '0,03', '0,03']);
    assert.equal(inputs[2].getAttribute('data-orig'), '');
    assert.equal(inputs[3].getAttribute('data-orig'), '0,09');
    assert.equal(inputs[2].getAttribute('data-dirty'), '1');
    inputs[1].fire('change');
    assert.deepEqual(saved, ['0,03']);
});

test('zero extends through the end but clearing affects only the selected year', () => {
    const { inputs } = rowEditor(['0,01', '0,02', '0,09']);
    inputs[1].value = '0';
    inputs[1].fire('input');
    assert.deepEqual(inputs.map(input => input.value), ['0,01', '0', '0']);
    inputs[1].value = '';
    inputs[1].fire('input');
    assert.deepEqual(inputs.map(input => input.value), ['0,01', '', '0,09']);
    assert.equal(inputs[1].hasAttribute('data-coefficient-extended'), false);
    assert.equal(inputs[2].hasAttribute('data-dirty'), false);
});

test('failed saving restores the previous values of propagated cells', () => {
    const { inputs, context } = rowEditor(['0,01', '', '0,09']);
    inputs[0].value = 'bad';
    inputs[0].fire('input');
    context.restoreHydroCoefficient(inputs[0]);
    assert.deepEqual(inputs.slice(1).map(input => input.value), ['', '0,09']);
    assert.equal(inputs[0].hasAttribute('data-coefficient-extended'), false);
});

test('prolongation updates deferred cells and live calculation reads the new values rather than stale raw data', () => {
    const { inputs, context } = rowEditor(['0,01', '0,02', '0,09'], [1, 2]);
    inputs[0].value = '0,03';
    inputs[0].fire('input');
    assert.deepEqual(inputs.slice(1).map(input => input.textContent), ['0,03', '0,03']);
    assert.equal(context.readControlNumber(inputs[1]), 0.03);
    assert.equal(context.readControlNumber(inputs[2]), 0.03);
    context.restoreHydroCoefficient(inputs[0]);
    assert.deepEqual(inputs.slice(1).map(input => input.textContent), ['0,02', '0,09']);
    assert.equal(context.readControlNumber(inputs[1]), 0.02);
});

test('station-wide GAES coefficient and row paste do not trigger annual prolongation', () => {
    const { inputs, context } = rowEditor(['0,01', '0,02']);
    inputs[0].removeAttribute('data-year');
    inputs[0].value = '0,03';
    inputs[0].fire('input');
    assert.equal(inputs[1].value, '0,02');
    inputs[0].setAttribute('data-year', '2026');
    context.window.__armGsTableRowPasteActive = true;
    inputs[0].fire('input');
    assert.equal(inputs[1].value, '0,02');
});

test('group percent extends to later editable years, including deferred cells, and zero also extends', () => {
    const { inputs, saved, context } = rowEditor(['1', '2', '3', '4', '5'], [2, 3, 4], { kind: 'own_needs_percent', group: true });
    inputs[3].setAttribute('data-readonly', '1');
    inputs[1].value = '7,25';
    inputs[1].fire('input');
    assert.equal(inputs[0].value, '1');
    assert.deepEqual(inputs.slice(2).map(input => input.textContent), ['7,25', '4', '7,25']);
    assert.equal(context.readControlNumber(inputs[2]), 7.25);
    assert.equal(inputs[2].getAttribute('data-orig'), '3');
    inputs[1].fire('change');
    assert.deepEqual(saved, ['7,25']);
    inputs[1].value = '0';
    inputs[1].fire('input');
    assert.deepEqual(inputs.slice(2).map(input => input.textContent), ['0', '4', '0']);
    inputs[1].value = '';
    inputs[1].fire('input');
    assert.deepEqual(inputs.slice(2).map(input => input.textContent), ['3', '4', '5']);
    assert.equal(inputs[2].hasAttribute('data-dirty'), false);
});

test('group percent restores propagated years after a failed save and does not propagate row paste', () => {
    const { inputs, context } = rowEditor(['1', '2', '3'], [1, 2], { kind: 'own_needs_percent', group: true });
    inputs[0].value = 'bad';
    inputs[0].fire('input');
    context.restoreHydroCoefficient(inputs[0]);
    assert.deepEqual(inputs.slice(1).map(input => input.textContent), ['2', '3']);
    context.window.__armGsTableRowPasteActive = true;
    inputs[0].value = '8';
    inputs[0].fire('input');
    assert.deepEqual(inputs.slice(1).map(input => input.textContent), ['2', '3']);
});

test('station AES percent does not acquire group-only prolongation', () => {
    const { inputs } = rowEditor(['1', '2'], [], { kind: 'own_needs_percent' });
    inputs[0].value = '8';
    inputs[0].fire('input');
    assert.equal(inputs[1].value, '2');
});
