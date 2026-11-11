const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('app/static/js/energy_balance/ee_balance_ves_ses_live.js', 'utf8');

function groupTable({ coefficientMode = false, editable = true } = {}) {
    const year = 2026;
    const handlers = {};
    function cell(value, kind) {
        const attrs = { 'data-year': String(year), 'data-raw': value, 'data-orig': value };
        if (kind) Object.assign(attrs, { 'data-kind': kind, 'data-ves-deferred': '1' });
        return {
            tagName: kind ? 'SPAN' : 'TD', textContent: value, value,
            getAttribute: name => attrs[name] ?? null,
            setAttribute: (name, value) => { attrs[name] = String(value); },
            removeAttribute: name => { delete attrs[name]; },
            classList: { contains: () => false, remove() {} },
            querySelector: () => null,
        };
    }
    const controls = {
        energy: cell('0,1578', 'energy'),
        own_needs: cell('', 'own_needs'),
        own_needs_percent: cell('7,25', 'own_needs_percent'),
    };
    const cells = {};
    const rows = {};
    const metrics = {
        capacity: 'capacity', energy: 'energy', chiim: 'chiim',
        own_needs_energy: 'own-needs-energy', own_needs: 'own-needs', delivery: 'delivery',
    };
    const kinds = { energy: 'energy', own_needs_energy: 'own_needs', own_needs: 'own_needs_percent' };
    for (const [metric, column] of Object.entries(metrics)) {
        const kind = kinds[metric];
        const control = editable ? controls[kind] : null;
        const td = cell(control ? control.textContent : (controls[kind]?.textContent || '10'));
        if (metric === 'own_needs_energy') td.setAttribute('data-own-needs-calculated', '1');
        td.querySelector = () => control;
        cells[metric] = td;
        rows[metric] = {
            getAttribute: name => ({ 'data-station-id': 'g7', 'data-is-group': '1' })[name] ?? null,
            querySelector: () => null,
            querySelectorAll: selector => selector.includes(`data-ves-col='${column}'`) ? [td]
                : control && selector.includes('data-kind') ? [control] : [],
        };
        if (control) {
            control.closest = () => rows[metric];
            control.matches = selector => selector.includes('input.ves-ses-value');
        }
    }
    const table = {
        querySelector: selector => {
            if (selector.includes(':not(')) return null;
            const metric = selector.match(/data-ves-metric='([^']+)'/);
            return metric ? rows[metric[1]] || null : null;
        },
        querySelectorAll: selector => {
            if (selector === "tr[data-ves-station='1']") return [rows.capacity];
            if (selector.includes('data-ves-agg')) return [];
            const metric = selector.match(/data-ves-metric='([^']+)'/);
            return metric && rows[metric[1]] ? [rows[metric[1]]] : [];
        },
        addEventListener: (event, handler) => { handlers[event] = handler; },
    };
    const context = { window: { setTimeout: () => 1, clearTimeout() {} }, document: { activeElement: null } };
    vm.createContext(context);
    vm.runInContext(source, context);
    context.window.initVesSesLiveTotals(table, { years: [year], planYears: [], ownerYears: [], digits: 3, coefficientMode });
    function edit(kind, value) {
        const control = controls[kind];
        control.tagName = 'INPUT';
        control.value = value;
        context.window.armGsRefreshVesSesStationControl(control);
        handlers.input({ target: control });
    }
    return { cells, controls, edit, recalc: () => context.window.armGsRecalcVesSesLive('g7') };
}

for (const coefficientMode of [false, true]) {
    test(`group own needs follows generation and percent without saving (hydro=${coefficientMode})`, () => {
        const { controls, cells, edit, recalc } = groupTable({ coefficientMode });
        recalc();
        assert.equal(controls.own_needs.textContent, '0,011');
        assert.equal(Number(controls.own_needs.getAttribute('data-raw').replace(',', '.')), 0.0114405);
        assert.equal(controls.own_needs_percent.getAttribute('data-readonly'), null);
        edit('own_needs_percent', '10');
        assert.equal(controls.own_needs.textContent, '0,016');
        edit('energy', '200');
        assert.equal(controls.own_needs.textContent, '20,000');
        assert.equal(cells.delivery.textContent, '180,000');
        edit('own_needs_percent', '0');
        assert.equal(controls.own_needs.textContent, '0,000');
        assert.equal(controls.own_needs.getAttribute('data-raw'), '0');
        edit('own_needs_percent', '');
        assert.equal(controls.own_needs.textContent, '');
        assert.equal(controls.own_needs.getAttribute('data-raw'), null);
    });
}

test('manual group own needs takes priority and clearing it restores live calculation', () => {
    const { controls, cells, edit, recalc } = groupTable();
    controls.own_needs.setAttribute('data-orig', '5');
    controls.own_needs.setAttribute('data-raw', '5');
    recalc();
    assert.equal(controls.own_needs_percent.getAttribute('data-readonly'), '1');
    edit('energy', '100');
    assert.equal(controls.own_needs_percent.textContent, '5,000');
    assert.equal(cells.delivery.textContent, '95,000');
    edit('own_needs', '');
    assert.equal(controls.own_needs_percent.getAttribute('data-readonly'), null);
    assert.equal(controls.own_needs.placeholder, '5,000');
    edit('own_needs_percent', '10');
    assert.equal(controls.own_needs.value, '');
    assert.equal(controls.own_needs.placeholder, '10,000');
    assert.equal(cells.delivery.textContent, '90,000');
});

test('group own needs is also calculated for read-only viewers', () => {
    const { cells, recalc } = groupTable({ editable: false });
    recalc();
    assert.equal(cells.own_needs_energy.textContent, '0,011');
    recalc();
    assert.equal(cells.own_needs.textContent, '7,250');
    assert.equal(cells.own_needs_energy.textContent, '0,011');
    cells.own_needs.setAttribute('data-raw', '0');
    recalc();
    assert.equal(cells.own_needs.textContent, '0,000');
    assert.equal(cells.own_needs_energy.textContent, '0,000');
    assert.equal(cells.own_needs_energy.getAttribute('data-raw'), '0');
});
