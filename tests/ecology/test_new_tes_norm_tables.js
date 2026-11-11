const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const template = fs.readFileSync(path.join(__dirname, '../../app/templates/ecology/operating_tes/operating_tes_table.html'), 'utf8');
const start = template.indexOf('    const getFieldValue = function');
const end = template.indexOf('\n  });', start);
assert.ok(start > 0 && end > start);
const script = template.slice(start, end).replace(/const CSRF = .*;/, "const CSRF = 'test-token';");

function setup(canEdit = true, success = true) {
    const requests = [];
    const tables = ['le100', 'gt100'].map(capacity => {
        const listeners = {};
        const classes = new Set();
        const cell = {
            classList: {add(name) { classes.add(name); }, remove(...names) { names.forEach(name => classes.delete(name)); }},
            removeAttribute() {}
        };
        const table = {
            dataset: {canEdit: canEdit ? '1' : '0', updateUrl: `/value/?capacity_class=${capacity}`, autosave: '1'},
            querySelectorAll() { return [field]; }
        };
        const field = {
            value: '2', dataset: {year: '2026', field: 'ash'},
            classList: {add() {}, remove() {}}, setAttribute() {}, removeAttribute() {},
            closest(selector) { return selector === 'td' ? cell : selector === 'table' ? table : {dataset: {rowKey: 'mazut'}}; },
            addEventListener(name, listener) { listeners[name] = listener; }
        };
        return Object.assign(table, {field, listeners, classes});
    });
    vm.runInNewContext(script, {
        document: {querySelectorAll() { return tables; }},
        setTimeout() { return 1; }, clearTimeout() {},
        async fetch(url, options) {
            requests.push({url, body: JSON.parse(options.body)});
            return {ok: success, async json() { return {ok: success, error: 'Save failed'}; }};
        }
    });
    return {tables, requests};
}

test('each norm table saves to its own capacity and keeps save state independent', async () => {
    const {tables, requests} = setup();
    for (const [index, table] of tables.entries()) {
        table.field.value = String(index + 5);
        table.listeners.input();
        table.listeners.change();
    }
    await new Promise(setImmediate);
    assert.deepEqual(requests, [
        {url: '/value/?capacity_class=le100', body: {year: '2026', row_key: 'mazut', field: 'ash', value: '5'}},
        {url: '/value/?capacity_class=gt100', body: {year: '2026', row_key: 'mazut', field: 'ash', value: '6'}}
    ]);
    for (const table of tables) {
        assert.ok(table.classes.has('is-save-success'));
        table.listeners.change();
    }
    assert.equal(requests.length, 2);
});

test('failed saves show an error in either table', async () => {
    const {tables} = setup(true, false);
    for (const table of tables) {
        table.field.value = '9';
        table.listeners.change();
    }
    await new Promise(setImmediate);
    for (const table of tables) assert.ok(table.classes.has('is-save-error'));
});

test('read-only norm tables have no save listeners', () => {
    const {tables, requests} = setup(false);
    for (const table of tables) assert.deepEqual(table.listeners, {});
    assert.deepEqual(requests, []);
});
