const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const tick = () => new Promise(resolve => setImmediate(resolve));
const response = (data, ok = true) => ({ ok, headers: new Headers(), json: async () => data });

function field(value = '10', variant = false) {
    const attrs = {};
    const classes = new Set();
    const row = {
        hasAttribute: () => false, getAttribute: () => null,
        previousElementSibling: null, nextElementSibling: null,
        querySelector: () => null, closest() { return this; },
        classList: { contains: name => name === 'summary-row-param' },
    };
    return {
        value, dataset: { initial: value, model: 'TestParameter', slice: '2025', parameterKey: 'energy_consumption_mln_kvt_ch' },
        title: 'Full precision', tagName: 'INPUT', isConnected: true,
        matches: selector => selector === '.pd-ec-perimeter-variant-select' ? variant : true,
        closest: () => row,
        getAttribute(name) {
            if (name === 'data-demand-model-name') return 'TestParameter';
            if (name in attrs) return attrs[name];
            const key = name.replace(/^data-/, '').replace(/-([a-z])/g, (_, c) => c.toUpperCase());
            return this.dataset[key] ?? null;
        },
        setAttribute(name, value) { attrs[name] = value; },
        removeAttribute(name) { delete attrs[name]; },
        classList: { add: name => classes.add(name), remove: (...names) => names.forEach(name => classes.delete(name)), contains: name => classes.has(name) },
    };
}

function start(fields, fetch, dataset = {}) {
    const events = {};
    const windowEvents = {};
    const button = { addEventListener: (name, cb) => { events['button:' + name] = cb; } };
    const table = {
        dataset: { saveCellUrl: '/cell', saveBlockVariantUrl: '/variant', csrfToken: 'csrf', summaryLogScope: 'oes', ...dataset },
        addEventListener: (name, cb) => { events[name] = cb; },
        querySelectorAll: () => fields,
        getAttribute: name => name === 'data-summary-log-scope' ? 'oes' : null,
    };
    let reloads = 0;
    const alerts = [];
    const window = {
        alert: message => alerts.push(message),
        addEventListener: (name, cb) => { windowEvents[name] = cb; },
        armGsPageScrollRestore: { reload() { reloads++; } },
    };
    const context = vm.createContext({
        window, fetch, CustomEvent,
        document: {
            dispatchEvent: () => {},
            addEventListener: (name, cb) => cb(),
            querySelector: () => table, getElementById: () => button,
        },
    });
    for (const file of ['consumption_live_save.js', 'demand_summary_live_save.js']) {
        vm.runInContext(fs.readFileSync('app/static/js/energy_consumption/' + file, 'utf8'), context);
    }
    return {
        emit(name, target, extra = {}) { events[name]({ target, ...extra }); },
        click() { return events['button:click'](); },
        get reloads() { return reloads; },
        get alerts() { return alerts; },
        get disabled() { return button.disabled; },
        unload() {
            const event = { prevented: false, preventDefault() { this.prevented = true; } };
            windowEvents.beforeunload(event);
            return event.prevented;
        },
    };
}

test('change saves one cell with CSRF and marks green only after confirmation', async () => {
    const input = field();
    let finish;
    const requests = [];
    const ui = start([input], (url, options) => {
        requests.push({ url, options });
        return new Promise(resolve => { finish = resolve; });
    });
    input.value = '12,345';
    ui.emit('change', input);
    assert.equal(requests[0].url, '/cell');
    assert.equal(requests[0].options.headers['X-CSRFToken'], 'csrf');
    const payload = JSON.parse(requests[0].options.body);
    assert.equal(payload.value, '12,345');
    assert.equal(payload.slice_key, 2025);
    assert.equal(payload.summary_log_scope, 'oes');
    assert.equal(input.classList.contains('is-save-success'), false);
    assert.equal(ui.unload(), true);
    finish(response({ ok: true }));
    await tick();
    assert.equal(input.classList.contains('is-save-success'), true);
    assert.equal(input.dataset.initial, '12,345');
    assert.equal(ui.unload(), false);
});

test('server rejection stays red, keeps entered text, and can be retried', async () => {
    const input = field();
    let fail = true;
    const ui = start([input], async () => response(fail ? { ok: false, error: 'Invalid number' } : { ok: true }, !fail));
    input.value = 'bad';
    ui.emit('change', input);
    await tick();
    assert.equal(input.classList.contains('is-save-error'), true);
    assert.equal(input.value, 'bad');
    assert.equal(input.dataset.initial, '10');
    assert.equal(input.title, 'Invalid number');
    assert.equal(ui.unload(), true);
    fail = false;
    input.value = '20';
    ui.emit('change', input);
    await tick();
    assert.equal(input.classList.contains('is-save-success'), true);
    assert.equal(input.classList.contains('is-save-error'), false);
    assert.equal(input.title, 'Full precision');
    assert.equal(ui.unload(), false);
});

test('rapid changes are serialized and the latest value is not lost', async () => {
    const input = field();
    const requests = [];
    const finishes = [];
    const ui = start([input], (url, options) => {
        requests.push(JSON.parse(options.body).value);
        return new Promise(resolve => finishes.push(resolve));
    });
    input.value = '11';
    ui.emit('change', input);
    input.value = '12';
    ui.emit('input', input);
    ui.emit('change', input);
    assert.deepEqual(requests, ['11']);
    finishes[0](response({ ok: true }));
    await tick();
    assert.deepEqual(requests, ['11', '12']);
    assert.equal(input.classList.contains('is-save-success'), false);
    finishes[1](response({ ok: true }));
    await tick();
    assert.equal(input.dataset.initial, '12');
    assert.equal(input.classList.contains('is-save-success'), true);
});

test('network failure is red and the save button retries without reloading', async () => {
    const input = field();
    let fail = true;
    const ui = start([input], async () => {
        if (fail) throw new Error('Offline');
        return response({ ok: true });
    });
    input.value = '15';
    ui.emit('change', input);
    await tick();
    assert.equal(input.classList.contains('is-save-error'), true);
    fail = false;
    await ui.click();
    assert.equal(input.dataset.initial, '15');
    assert.equal(input.classList.contains('is-save-success'), true);
});

test('perimeter selection autosaves through the existing block endpoint', async () => {
    const select = field('without_nt', true);
    const requests = [];
    const ui = start([select], async (url, options) => {
        requests.push({ url, payload: JSON.parse(options.body) });
        return response({ ok: true });
    });
    select.value = 'with_nt';
    ui.emit('change', select);
    await tick();
    assert.equal(requests[0].url, '/variant');
    assert.equal(requests[0].payload.perimeter_variant_code, 'with_nt');
    assert.equal(requests[0].payload.from_variant_code, 'without_nt');
    assert.equal(requests[0].payload.summary_log_scope, 'oes');
    assert.equal(select.classList.contains('is-save-success'), true);
});

test('active OES template connects live save with CSRF instead of the legacy reload handler', () => {
    const source = fs.readFileSync('app/templates/energy_consumption/pages/summary_oes_body.html', 'utf8');
    assert.match(source, /<script[^>]+demand_summary_live_save\.js[^>]+defer/);
    const table = source.slice(source.indexOf('<table id="powerDemandSummaryTable"'), source.indexOf('<colgroup>'));
    assert.match(table, /data-csrf-token="\{\{ csrf_token \}\}"/);
    assert.doesNotMatch(source, /runDemandSummarySave/);
    assert.match(source, /initPowerDemandSummaryRowPaste\(table\)/);
});

test('save button recalculates only after all cell saves succeed', async () => {
    const input = field();
    const requests = [];
    let reject = true;
    const ui = start([input], async (url) => {
        requests.push(url);
        return response({ ok: !reject }, !reject);
    }, { persistComputedUrl: '/computed' });
    input.value = '20';
    await ui.click();
    assert.deepEqual(requests, ['/cell']);
    assert.equal(ui.reloads, 0);
    assert.equal(input.classList.contains('is-save-error'), true);
    reject = false;
    await ui.click();
    assert.deepEqual(requests, ['/cell', '/cell', '/computed']);
    assert.equal(ui.reloads, 1);
    assert.equal(input.classList.contains('is-save-success'), true);
});

test('recalculation failure leaves saved cells intact and enables retry without reload', async () => {
    const input = field();
    const ui = start([input], async url => url === '/computed'
        ? response({ ok: false, error: 'Calculation failed' }, false)
        : response({ ok: true }), { persistComputedUrl: '/computed' });
    input.value = '25';
    await ui.click();
    assert.equal(input.dataset.initial, '25');
    assert.equal(input.classList.contains('is-save-success'), true);
    assert.deepEqual(ui.alerts, ['Calculation failed']);
    assert.equal(ui.disabled, false);
    assert.equal(ui.reloads, 0);
});
