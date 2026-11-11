const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const liveSource = fs.readFileSync('app/static/js/energy_balance/ee_balance_ves_ses_live.js', 'utf8');
const template = fs.readFileSync('app/templates/energy_balance/ee_balance/ee_balance_ves_ses.html', 'utf8');
const editorSource = template.slice(template.indexOf('    function extendHydroCoefficient('), template.indexOf('    function materializeDeferred('));

function cell(year, value, tagName = 'TD') {
    const attrs = { 'data-year': String(year), 'data-raw': value, 'data-orig': value };
    return {
        tagName, value, textContent: value, dataset: {},
        getAttribute: name => attrs[name] ?? null,
        hasAttribute: name => Object.hasOwn(attrs, name),
        setAttribute: (name, value) => { attrs[name] = String(value); },
        removeAttribute: name => { delete attrs[name]; },
        querySelector: () => null,
        classList: { contains: () => false, remove: () => {} },
    };
}

function hydroTable() {
    const years = [2026, 2027];
    const capacity = years.map(year => cell(year, '10'));
    const energy = years.map(year => cell(year, year === 2026 ? '100' : '200'));
    const coefficients = years.map(year => cell(year, '1', 'SPAN'));
    const ownNeeds = years.map(year => cell(year, '1'));
    const delivery = years.map(year => cell(year, '99'));
    const chiim = years.map(year => cell(year, '10000'));
    coefficients.forEach(control => {
        control.setAttribute('data-kind', 'coefficient');
        control.setAttribute('data-ves-deferred', '1');
    });
    function row(metric, cells, column) {
        return {
            getAttribute: name => name === 'data-station-id' ? '1' : null,
            querySelector: () => null,
            querySelectorAll: selector => selector.includes(`data-ves-col='${column}'`)
                || (metric === 'own_needs_coefficient' && selector.includes('data-kind')) ? cells : [],
        };
    }
    const rows = {
        capacity: row('capacity', capacity, 'capacity'),
        energy: row('energy', energy, 'energy'),
        chiim: row('chiim', chiim, 'chiim'),
        own_needs: row('own_needs', ownNeeds, 'own-needs'),
        delivery: row('delivery', delivery, 'delivery'),
        own_needs_coefficient: row('own_needs_coefficient', coefficients, 'own-needs-coefficient'),
    };
    const handlers = {};
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
    const context = {
        window: { setTimeout: () => 1, clearTimeout: () => {} },
        document: { activeElement: null }, saveInput: () => {},
    };
    vm.createContext(context);
    vm.runInContext(liveSource, context);
    vm.runInContext(editorSource, context);
    context.window.initVesSesLiveTotals(table, { years, planYears: [], ownerYears: [], digits: 1, coefficientMode: true });
    // Opening a deferred field must replace the cached span with the active input.
    const input = cell(2026, '1', 'INPUT');
    input.setAttribute('data-kind', 'coefficient');
    input.closest = () => rows.own_needs_coefficient;
    input.matches = selector => selector.includes('input.ves-ses-value');
    input.addEventListener = () => {};
    context.window.armGsRefreshVesSesStationControl(input);
    coefficients[0] = input;
    return { context, input, coefficients, ownNeeds, delivery, handlers };
}

test('GES own needs and delivery recalculate on each keystroke before saving, including prolonged years', () => {
    const { context, input, coefficients, ownNeeds, delivery, handlers } = hydroTable();
    input.value = '3';
    context.extendHydroCoefficient(input);
    handlers.input({ target: input });
    assert.equal(coefficients[1].textContent, '3');
    assert.deepEqual(ownNeeds.map(td => td.textContent), ['3,0', '6,0']);
    assert.deepEqual(delivery.map(td => td.textContent), ['97,0', '194,0']);
    input.value = '0';
    context.extendHydroCoefficient(input);
    handlers.input({ target: input });
    assert.deepEqual(ownNeeds.map(td => td.textContent), ['0,0', '0,0']);
    assert.deepEqual(ownNeeds.map(td => td.getAttribute('data-raw')), ['0', '0']);
    assert.deepEqual(delivery.map(td => td.textContent), ['100,0', '200,0']);
});
