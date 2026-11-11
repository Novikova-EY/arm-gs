const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('app/static/js/rational_structure/technical_characteristics.js', 'utf8');

function element(properties = {}) {
    const handlers = {};
    return Object.assign({
        dataset: {}, value: '', disabled: false,
        classList: { add() {}, remove() {} },
        addEventListener(event, handler) { handlers[event] = handler; },
        emit(event) { return handlers[event]?.call(this, { preventDefault() {} }); },
    }, properties);
}

function fixture({ card = false, importPage = false, fail = false, pgu = false, htmlStatus = null, redirected = false } = {}) {
    const input = card ? element({ value: 'old-001', dataset: { machineId: '7', saveUrl: '/save' } }) : null;
    if (pgu && input) {
        delete input.dataset.machineId;
        input.dataset.pguMachineId = '161';
    }
    const year = element({ value: '2024' });
    const hiddenYear = element();
    let submitted = false;
    const form = importPage ? element({ requestSubmit() { submitted = true; } }) : null;
    const button = element();
    const file = element({ files: ['data.xlsx'], click() {} });
    const calls = [];
    const alerts = [];
    let ready;
    const context = {
        document: {
            addEventListener(event, handler) { assert.equal(event, 'DOMContentLoaded'); ready = handler; },
            getElementById(id) {
                return { 'rs-year': year, rsImportForm: form, 'rs-import-year': hiddenYear,
                    'rs-import-button': button, 'rs-file': file }[id] || null;
            },
            querySelector(selector) {
                if (selector === 'input[name="technical_inspection_code"]') return input;
                if (selector === 'meta[name="csrf-token"]') return { content: 'csrf' };
                return null;
            },
            querySelectorAll() { return [{}]; },
        },
        window: { alert(message) { alerts.push(message); } },
        fetch: async (url, options) => {
            const body = JSON.parse(options.body);
            calls.push({ url, options, body });
            return {
                ok: !fail && (htmlStatus === null || htmlStatus < 400),
                status: htmlStatus ?? (fail ? 400 : 200), redirected,
                headers: { get: () => htmlStatus === null ? 'application/json' : 'text/html' },
                json: async () => {
                    assert.equal(htmlStatus, null, 'HTML must not be parsed as JSON');
                    return fail ? { ok: false, error: 'Ошибка' } :
                        { ok: true, equipment_code: body.equipment_code };
                },
            };
        },
    };
    vm.runInNewContext(source, context);
    // Bootstrap is loaded after the content block, before DOMContentLoaded.
    context.bootstrap = { Tooltip: function () {} };
    ready();
    return { input, year, hiddenYear, form, button, file, calls, alerts,
        submitted: () => submitted };
}

test('machine card sends previous code and updates it after a successful save', async () => {
    const ui = fixture({ card: true });
    assert.equal(ui.input.dataset.original, 'old-001');
    ui.input.value = 'new-002';
    await ui.input.emit('change');
    assert.equal(ui.calls.length, 1);
    assert.deepEqual(ui.calls[0].body, {
        machine_id: '7', pgu_machine_id: null, equipment_code: 'new-002', previous_code: 'old-001',
    });
    assert.equal(ui.calls[0].options.headers['X-CSRFToken'], 'csrf');
    assert.equal(ui.input.dataset.original, 'new-002');
    assert.equal(ui.input.disabled, false);
    await ui.input.emit('change');
    assert.equal(ui.calls.length, 1);
});

test('machine card restores the saved code after a failed request', async () => {
    const ui = fixture({ card: true, fail: true });
    ui.input.value = 'bad-code';
    await ui.input.emit('change');
    assert.equal(ui.input.value, 'old-001');
    assert.equal(ui.input.dataset.original, 'old-001');
    assert.equal(ui.input.disabled, false);
    assert.deepEqual(ui.alerts, ['Ошибка']);
});

test('PGU card sends the component ID as provided by the HTML dataset', async () => {
    const ui = fixture({ card: true, pgu: true });
    ui.input.value = 'new-002';
    await ui.input.emit('change');
    assert.deepEqual(ui.calls[0].body, {
        machine_id: null, pgu_machine_id: '161', equipment_code: 'new-002', previous_code: 'old-001',
    });
    assert.equal(ui.input.value, 'new-002');
    assert.equal(ui.input.disabled, false);
    assert.deepEqual(ui.alerts, []);
});

for (const status of [403, 404, 500, 502]) {
    test(`machine card reports HTTP ${status} without parsing HTML as JSON`, async () => {
        const ui = fixture({ card: true, htmlStatus: status });
        ui.input.value = 'new-002';
        await ui.input.emit('change');
        assert.equal(ui.input.value, 'old-001');
        assert.equal(ui.input.dataset.original, 'old-001');
        assert.equal(ui.input.disabled, false);
        assert.equal(ui.alerts.length, 1);
        assert.match(ui.alerts[0], new RegExp(`HTTP ${status}`));
    });
}

for (const options of [{ htmlStatus: 200, redirected: true }, { htmlStatus: 401 }]) {
    test(`machine card reports an expired session (${JSON.stringify(options)})`, async () => {
        const ui = fixture({ card: true, ...options });
        ui.input.value = 'new-002';
        await ui.input.emit('change');
        assert.equal(ui.input.value, 'old-001');
        assert.equal(ui.input.disabled, false);
        assert.deepEqual(ui.alerts, ['Сессия истекла. Обновите страницу и войдите снова.']);
    });
}

test('import keeps the year only as a return filter and submits the selected file', () => {
    const ui = fixture({ importPage: true });
    assert.equal(ui.hiddenYear.value, '2024');
    ui.year.value = '2023';
    ui.year.emit('change');
    assert.equal(ui.hiddenYear.value, '2023');
    ui.file.emit('change');
    assert.equal(ui.submitted(), true);
    ui.form.emit('submit');
    assert.equal(ui.button.disabled, true);
});
